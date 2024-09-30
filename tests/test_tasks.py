from unittest import skip
from django.test import TestCase
from orchestrator.models import Job, Status, PipelineType
from orchestrator.tasks import (
    prepare_job,
    submit_job_to_lsf,
    process_jobs,
    cleanup_completed_jobs,
    cleanup_failed_jobs,
    check_job_status,
)
from datetime import datetime, timedelta
from mock import patch, call
import uuid
from batch_systems.lsf_client.lsf_client import format_lsf_job_id

from submitter.toil_submitter import ToilJobSubmitter

MAX_RUNNING_JOBS = 3


class TestTasks(TestCase):
    fixtures = ["orchestrator.job.json"]

    def setUp(self):
        self.current_job = Job.objects.first()
        self.preparing_job = Job.objects.filter(status=Status.CREATED).first()
        self.submitting_job = Job.objects.filter(status=Status.SUBMITTING).first()

    @patch("submitter.toil_submitter.toil_jobsubmitter.ToilJobSubmitter.__init__")
    @patch("orchestrator.tasks.submit_job_to_lsf")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.submit")
    @skip("Need to mock memcached lock")
    def test_submit_polling(self, job_submitter, submit_job_to_lsf, init):
        init.return_value = None
        job_submitter.return_value = (
            self.current_job.external_id,
            self.current_job.job_store_location,
            self.current_job.working_dir,
            self.current_job.output_directory,
        )
        submit_job_to_lsf.return_value = None
        created_jobs = len(Job.objects.filter(status=Status.CREATED))
        process_jobs()
        self.assertEqual(submit_job_to_lsf.delay.call_count, created_jobs)
        submit_job_to_lsf.reset_mock()
        process_jobs()
        self.assertEqual(submit_job_to_lsf.delay.call_count, 0)

    @patch("submitter.toil_submitter.toil_jobsubmitter.ToilJobSubmitter.prepare_to_submit")
    def test_prepare_job(self, prepare_to_submit):
        prepare_to_submit.return_value = (
            "/new/job_store_location",
            self.preparing_job.working_dir,
            self.preparing_job.root_dir,
        )
        prepare_job(self.preparing_job)
        self.preparing_job.refresh_from_db()
        self.assertEqual(self.preparing_job.job_store_location, "/new/job_store_location")
        self.assertEqual(self.preparing_job.status, Status.PREPARED)

    @patch("batch_systems.lsf_client.lsf_client.LSFClient.submit")
    @patch("orchestrator.tasks.save_job_info")
    def test_submit(self, save_job_info, submit):
        save_job_info.return_value = None
        submit.return_value = self.submitting_job.external_id
        submit_job_to_lsf(self.submitting_job)
        self.submitting_job.refresh_from_db()
        self.assertEqual(self.submitting_job.finished, None)
        self.assertEqual(self.submitting_job.status, Status.SUBMITTED)

    def test_job_args(self):
        job_id = str(uuid.uuid4())
        app = {"github": {"repository": "awesome_repo", "entrypoint": "test.cwl"}}
        root_dir = "test_root"
        resume_jobstore = None
        walltime = None
        tool_walltime = None
        memlimit = None
        inputs = {}
        expected_job_group = "-g {}".format(format_lsf_job_id(job_id))
        jobsubmitterObject = ToilJobSubmitter(
            job_id, app, inputs, root_dir, resume_jobstore, walltime, tool_walltime, memlimit
        )
        job_group = " ".join(jobsubmitterObject._job_group())
        self.assertEqual(job_group, expected_job_group)

    def test_job_args_walltime(self):
        job_id = str(uuid.uuid4())
        app = {"github": {"repository": "awesome_repo", "entrypoint": "test.cwl"}}
        root_dir = "test_root"
        resume_jobstore = None
        walltime = 7200
        tool_walltime = 24
        memlimit = None
        inputs = {}
        expected_job_args = "-W {}".format(walltime)
        jobsubmitterObject = ToilJobSubmitter(
            job_id, app, inputs, root_dir, resume_jobstore, walltime, tool_walltime, memlimit
        )
        leader_args_list = jobsubmitterObject._leader_args()
        leader_args = " ".join([str(single_arg) for single_arg in leader_args_list])
        self.assertEqual(leader_args, expected_job_args)

    def test_job_args_tool_walltime(self):
        job_id = str(uuid.uuid4())
        app = {"github": {"repository": "awesome_repo", "entrypoint": "test.cwl"}}
        root_dir = "test_root"
        resume_jobstore = None
        walltime = 7200
        tool_walltime = 24
        walltime_hard = 24
        walltime_expected = 8
        memlimit = None
        inputs = {}
        expected_tool_args = "-We {} -W {}".format(walltime_expected, walltime_hard)
        jobsubmitterObject = ToilJobSubmitter(
            job_id, app, inputs, root_dir, resume_jobstore, walltime, tool_walltime, memlimit
        )
        tool_args_list = jobsubmitterObject._tool_args()
        tool_args = " ".join([str(single_arg) for single_arg in tool_args_list])
        self.assertEqual(tool_args, expected_tool_args)

    def test_job_args_memlimit(self):
        job_id = str(uuid.uuid4())
        app = {"github": {"repository": "awesome_repo", "entrypoint": "test.cwl"}}
        root_dir = "test_root"
        resume_jobstore = None
        walltime = None
        tool_walltime = None
        memlimit = 10
        inputs = {}
        expected_leader_args = "-M {}".format(memlimit)
        jobsubmitterObject = ToilJobSubmitter(
            job_id, app, inputs, root_dir, resume_jobstore, walltime, tool_walltime, memlimit
        )
        leader_args_list = jobsubmitterObject._leader_args()
        leader_args = " ".join([str(single_arg) for single_arg in leader_args_list])
        self.assertEqual(leader_args, expected_leader_args)

    def test_job_args_all_options(self):
        job_id = str(uuid.uuid4())
        app = {"github": {"repository": "awesome_repo", "entrypoint": "test.cwl"}}
        root_dir = "test_root"
        resume_jobstore = None
        walltime = 7200
        tool_walltime = 24
        tool_walltime = 24
        walltime_hard = 24
        walltime_expected = 8
        memlimit = 10
        inputs = {}
        expected_leader_args = "-W {} -M {}".format(walltime, memlimit)
        expected_job_group = "-g {}".format(format_lsf_job_id(job_id))
        expected_tool_args = "-We {} -W {} -M {}".format(walltime_expected, walltime_hard, memlimit)
        jobsubmitterObject = ToilJobSubmitter(
            job_id, app, inputs, root_dir, resume_jobstore, walltime, tool_walltime, memlimit
        )
        leader_args_list = jobsubmitterObject._leader_args()
        leader_args = " ".join([str(single_arg) for single_arg in leader_args_list])
        job_group = " ".join(jobsubmitterObject._job_group())
        tool_args_list = jobsubmitterObject._tool_args()
        tool_args = " ".join([str(single_arg) for single_arg in tool_args_list])
        self.assertEqual(leader_args, expected_leader_args)
        self.assertEqual(job_group, expected_job_group)
        self.assertEqual(tool_args, expected_tool_args)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("orchestrator.tasks.get_job_info_path")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    @patch("submitter.toil_submitter.ToilJobSubmitter.get_outputs")
    @patch("orchestrator.tasks.set_permissions_job.delay")
    def test_complete(self, permission, get_outputs, status, get_job_info_path, command_processor):
        self.current_job.status = Status.PENDING
        self.current_job.save()
        permission.return_value = None
        command_processor.return_value = True
        get_outputs.return_value = {"outputs": True}, None
        get_job_info_path.return_value = "sample/job/path"
        status.return_value = Status.COMPLETED, None
        check_job_status(self.current_job)
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status, Status.COMPLETED)
        self.assertNotEqual(self.current_job.finished, None)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("orchestrator.tasks.get_job_info_path")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_fail(self, status, get_job_info_path, command_processor):
        self.current_job.status = Status.PENDING
        self.current_job.save()
        command_processor.return_value = True
        get_job_info_path.return_value = "sample/job/path"
        status.return_value = Status.FAILED, "submitter reason"
        check_job_status(self.current_job)
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status, Status.FAILED)
        self.assertNotEqual(self.current_job.finished, None)
        info_message = self.current_job.message["info"]
        failed_jobs = self.current_job.message["failed_jobs"]
        unknown_jobs = self.current_job.message["unknown_jobs"]
        expected_failed_jobs = {
            "failed_job_1": ["failed_job_1_id"],
            "failed_job_2": ["failed_job_2_id"],
            "running_job": ["running_job_id"],
        }
        expected_unknown_jobs = {"unknown_job": ["unknown_job_id_1", "unknown_job_id_2"]}
        self.assertEqual(info_message, "submitter reason")
        self.assertEqual(failed_jobs, expected_failed_jobs)
        self.assertEqual(unknown_jobs, expected_unknown_jobs)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("orchestrator.tasks.get_job_info_path")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_running(self, status, get_job_info_path, command_processor):
        self.current_job.status = Status.PENDING
        self.current_job.save()
        command_processor.return_value = True
        get_job_info_path.return_value = "sample/job/path"
        status.return_value = Status.RUNNING, None
        check_job_status(self.current_job)
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status, Status.RUNNING)
        self.assertNotEqual(self.current_job.started, None)
        self.assertEqual(self.current_job.finished, None)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    @skip("We are no longer failing tests on pending status, and instead letting the task fail it")
    def test_fail_not_submitted(self, status, command_processor):
        command_processor.return_value = True
        status.return_value = Status.PENDING, None
        self.current_job.status = Status.PENDING
        self.current_job.external_id = None
        self.current_job.save()
        check_job_status(self.current_job)
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status, Status.FAILED)
        self.assertNotEqual(self.current_job.finished, None)
        info_message = self.current_job.message["info"]
        failed_jobs = self.current_job.message["failed_jobs"]
        unknown_jobs = self.current_job.message["unknown_jobs"]
        expected_failed_jobs = {}
        expected_unknown_jobs = {}
        self.assertTrue("External id not provided" in info_message)
        self.assertEqual(failed_jobs, expected_failed_jobs)
        self.assertEqual(unknown_jobs, expected_unknown_jobs)

    @patch("orchestrator.tasks.cleanup_folders")
    def test_cleanup(self, cleanup_folders):
        Job.objects.create(
            type=PipelineType.CWL,
            app={"app": "link"},
            status=Status.COMPLETED,
            created_date=datetime.now() - timedelta(days=1),
            finished=datetime.now() - timedelta(days=1),
        )
        testtime = datetime.now() - timedelta(days=32)
        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = testtime
            job_old_completed = Job.objects.create(
                type=PipelineType.CWL, app={"app": "link"}, status=Status.COMPLETED, finished=testtime
            )
            job_old_failed = Job.objects.create(
                type=PipelineType.CWL, app={"app": "link"}, status=Status.FAILED, finished=testtime
            )

        cleanup_completed_jobs()
        cleanup_failed_jobs()

        calls = [
            call(str(job_old_completed.id), exclude=["input.json", "lsf.log"]),
            call(str(job_old_failed.id), exclude=["input.json", "lsf.log"]),
        ]

        cleanup_folders.delay.assert_has_calls(calls, any_order=True)
