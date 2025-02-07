"""
Tests for commandline status handling
"""

import os
from shutil import unpack_archive, copytree, copy
import tempfile
from django.test import TestCase, override_settings
import toil
from orchestrator.models import Job, Status, PipelineType, CommandLineToolJob
from orchestrator.tasks import check_status_of_command_line_jobs, check_job_hanging, check_leader_not_running


class TestToil(TestCase):
    """
    Test toil track functions
    """

    def get_toil_mock(self, toil_version):
        """
        Download TOIL mock data from s3
        """
        resource_name = "toil_%s.tar.gz" % toil_version
        resource_path = os.path.join(os.path.dirname(__file__), "data", resource_name)
        folder_path = "toil_%s" % toil_version
        self.mock_full_path = os.path.join(self.mock_dir.name, folder_path)
        if not os.path.exists(resource_path):
            raise Exception("Could not find TOIL mock data from: %s" % resource_path)
        if not os.path.exists(self.mock_full_path):
            copy(resource_path, self.mock_dir.name)
            unpack_archive(resource_path, self.mock_dir.name)

    def setUp(self):
        Job.objects.all().delete()
        self.toil_version = toil.version.baseVersion
        if self.toil_version not in ["3.21.0", "5.4.0a1"]:
            raise Exception("TOIL version: %s not supported" % self.toil_version)
        self.mock_dir = tempfile.TemporaryDirectory()
        self.job = Job(
            type=PipelineType.CWL,
            app={"github": {"entrypoint": "mock", "repository": "mock"}},
            root_dir="mock",
            job_store_location=None,
            working_dir=None,
            status=Status.RUNNING,
            metadata={"pipeline_name": "NA"},
        )
        self.job.save()
        self.get_toil_mock(self.toil_version)

    def tearDown(self):
        self.mock_dir.cleanup()

    def mock_track(self, run_type):
        """
        Mock track using TOIL snapshots
        """
        mock_data_path = os.path.join(self.mock_full_path, run_type)
        first_jobstore = os.path.join(mock_data_path, "0", "jobstore")
        first_work = os.path.join(mock_data_path, "0", "work")
        second_jobstore = os.path.join(mock_data_path, "1", "jobstore")
        second_work = os.path.join(mock_data_path, "1", "work")
        with tempfile.TemporaryDirectory() as tmpdir:
            self.check_status(first_jobstore, first_work, tmpdir)
        with tempfile.TemporaryDirectory() as tmpdir:
            self.check_status(second_jobstore, second_work, tmpdir)

    def check_status(self, jobstore, work_dir, tmp_dir):
        """
        Check status of command line jobs
        """
        job_id = str(self.job.id)
        tmp_work_dir = os.path.join(tmp_dir, "work")
        tmp_jobstore = os.path.join(tmp_dir, "jobstore")
        new_work_dir = os.path.join(tmp_work_dir, job_id)
        new_jobstore = os.path.join(tmp_jobstore, job_id)
        copytree(jobstore, new_jobstore)
        copytree(work_dir, new_work_dir)
        with override_settings(
            PIPELINE_CONFIG={
                "NA": {"JOB_STORE_ROOT": tmp_jobstore, "WORK_DIR_ROOT": tmp_work_dir, "TMP_DIR_ROOT": "/tmp"}
            }
        ):
            check_status_of_command_line_jobs(self.job)

    def test_running(self):
        """
        Test if running and completed jobs are properly parsed
        """
        self.mock_track("running")
        mock_num_completed = 0
        mock_num_running = 0
        if self.toil_version == "3.21.0":
            mock_num_completed = 1
            mock_num_running = 2
        elif self.toil_version == "5.4.0a1":
            mock_num_completed = 2
            mock_num_running = 1
        num_running = CommandLineToolJob.objects.filter(status=(Status.RUNNING)).count()
        num_completed = CommandLineToolJob.objects.filter(status=(Status.COMPLETED)).count()

        self.assertEqual(num_running, mock_num_running)
        self.assertEqual(num_completed, mock_num_completed)

    def test_failed(self):
        """
        Test if failed jobs are properly parsed
        """
        self.mock_track("failed")
        mock_num_failed = 2
        num_failed = CommandLineToolJob.objects.filter(status=(Status.FAILED)).count()
        self.assertEqual(num_failed, mock_num_failed)

    def test_details_set(self):
        """
        Test if the metadata is being set for commandLineJObs
        """
        self.mock_track("running")
        first_running_job = CommandLineToolJob.objects.filter(status=(Status.RUNNING)).first()
        details = first_running_job.details
        self.assertIsNotNone(details)
        self.assertIsNotNone(details["cores_req"])
        self.assertIsNotNone(details["cpu_usage"])
        self.assertIsNotNone(details["job_stream"])
        self.assertIsNotNone(details["last_modified"])
        self.assertIsNotNone(details["log_path"])
        self.assertIsNotNone(details["mem_usage"])
        self.assertIsNotNone(details["memory_req"])

    def test_hanging_toil_leader_not_running(self):
        """
        Test detection of a hanging toil leader job before its running
        """
        self.mock_track("running")
        self.job.status = Status.PENDING
        self.job.save()
        with override_settings(MAX_HANGING_HOURS=0):
            check_leader_not_running()
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.message)
        self.assertIsNotNone(self.job.message["alerts"][0])

    def test_hanging_no_duplicated_alerts(self):
        """
        Test to make sure the same alert does not get triggered twice
        """
        self.mock_track("running")
        self.job.status = Status.PENDING
        self.job.save()
        with override_settings(MAX_HANGING_HOURS=0):
            check_leader_not_running()
        self.job.refresh_from_db()
        with override_settings(MAX_HANGING_HOURS=0):
            check_leader_not_running()
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.message)
        self.assertTrue(len(self.job.message["alerts"]) == 1)

    def test_hanging_toil_leader_running(self):
        """
        Test detection of a hanging toil leader job while its running
        """
        self.mock_track("running")
        for single_job in CommandLineToolJob.objects.all():
            single_job.status = Status.COMPLETED
            single_job.save()
        with override_settings(MAX_HANGING_HOURS=0):
            check_job_hanging(self.job)
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.message)
        self.assertIsNotNone(self.job.message["alerts"][0])

    def test_hanging_toil_commandline_not_running(self):
        """
        Test detection of a hanging command that has not started yet
        """
        self.mock_track("running")
        all_tool_jobs = CommandLineToolJob.objects.all()
        count = all_tool_jobs.count()
        for single_job in CommandLineToolJob.objects.all():
            single_job.status = Status.PENDING
            single_job.save()
        with override_settings(MAX_HANGING_HOURS=0):
            check_job_hanging(self.job)
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.message)
        self.assertIsNotNone(self.job.message["alerts"][0])
        self.assertTrue(len(self.job.message["alerts"]) == count)

    def test_hanging_toil_commandline_running(self):
        """
        Test detection of a hanging command that have started running
        """
        self.mock_track("running")
        all_tool_jobs = CommandLineToolJob.objects.all()
        count = all_tool_jobs.count()
        for single_job in CommandLineToolJob.objects.all():
            single_job.status = Status.RUNNING
            single_job.save()
        with override_settings(MAX_HANGING_HOURS=0):
            check_job_hanging(self.job)
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.message)
        self.assertIsNotNone(self.job.message["alerts"][0])
        self.assertTrue(len(self.job.message["alerts"]) == count)

    def test_hanging_toil_commandline_mix(self):
        """
        Test detection of a hanging command that has not started yet and some that are running
        """
        self.mock_track("running")
        first_command = CommandLineToolJob.objects.first()
        first_command.status = Status.RUNNING
        first_command.save()
        last_command = CommandLineToolJob.objects.last()
        last_command.status = Status.PENDING
        last_command.save()
        with override_settings(MAX_HANGING_HOURS=0):
            check_job_hanging(self.job)
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.message)
        self.assertIsNotNone(self.job.message["alerts"][0])

    def test_hanging_message_for_toil_leader_running(self):
        """
        Test alert sent of a hanging toil leader job while its running
        """
        self.mock_track("running")
        MOCK_LOG_PATH = "path/to/log.log"
        for single_job in CommandLineToolJob.objects.all():
            single_job.status = Status.COMPLETED
            single_job.save()
        self.job.message["log"] = MOCK_LOG_PATH
        self.job.save()
        with override_settings(MAX_HANGING_HOURS=0):
            check_job_hanging(self.job)
        self.job.refresh_from_db()
        self.assertEqual(self.job.message["log"], MOCK_LOG_PATH)
        self.assertIsNotNone(self.job.message["alerts"][0])
        self.assertTrue(MOCK_LOG_PATH in self.job.message["alerts"][0]["message"])

    def test_hanging_message_for_tool_running(self):
        """
        Test alert sent of a hanging tool while its running
        """
        self.mock_track("running")
        for single_job in CommandLineToolJob.objects.all():
            single_job.status = Status.COMPLETED
            single_job.save()
        first_command = CommandLineToolJob.objects.first()
        first_command.status = Status.RUNNING
        first_command.save()
        command_log_path = first_command.details["log_path"]
        with override_settings(MAX_HANGING_HOURS=0):
            check_job_hanging(self.job)
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.message["alerts"][0])
        self.assertTrue(command_log_path in self.job.message["alerts"][0]["message"])
