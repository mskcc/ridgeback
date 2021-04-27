from django.test import TestCase
import toil
import os
import toil_mock
from orchestrator.models import Job, Status, PipelineType, CommandLineToolJob
from orchestrator.tasks import check_status_of_command_line_jobs


class TestToil(TestCase):
    def setUp(self):
        Job.objects.all().delete()
        self.toil_version = toil.version.baseVersion
        if self.toil_version not in ["3.21.0", "5.3.0"]:
            raise Exception("TOIL version: %s not supported" % self.toil_version)
        mock_base_path = os.path.abspath(toil_mock.__path__[0])
        self.toil_mock = os.path.join(mock_base_path, "toil_%s" % self.toil_version)

    def mock_track(self, run_type):
        mock_data_path = os.path.join(self.toil_mock, run_type)
        first_jobstore = os.path.join(mock_data_path, "0", "jobstore")
        first_work = os.path.join(mock_data_path, "0", "work")
        second_jobstore = os.path.join(mock_data_path, "1", "jobstore")
        second_work = os.path.join(mock_data_path, "1", "work")
        job = Job(
            type=PipelineType.CWL,
            app={"mock": True},
            root_dir="mock",
            job_store_location=first_jobstore,
            working_dir=first_work,
            status=Status.RUNNING,
        )
        job.save()
        check_status_of_command_line_jobs()
        job.refresh_from_db()
        job.job_store_location = second_jobstore
        job.working_dir = second_work
        check_status_of_command_line_jobs()

    def test_running(self):
        self.mock_track("running")
        mock_num_completed = 0
        mock_num_running = 0
        if self.toil_version == "3.21.0":
            mock_num_completed = 2
            mock_num_running = 1
        elif self.toil_version == "5.3.0":
            mock_num_completed = 2
            mock_num_running = 1
        num_running = CommandLineToolJob.objects.filter(status__in=(Status.RUNNING))
        num_completed = CommandLineToolJob.objects.filter(status__in=(Status.COMPLETED))

        self.assertEqual(num_running, mock_num_running)
        self.assertEqual(num_completed, mock_num_completed)

    def test_failed(self):
        self.mock_track("failed")
        mock_num_failed = 2
        num_failed = CommandLineToolJob.objects.filter(status__in=(Status.FAILED))
        self.assertEqual(num_failed, mock_num_failed)
