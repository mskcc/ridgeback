"""
Tests for commandline status handling
"""
import os
from shutil import unpack_archive, rmtree
import requests
from django.test import TestCase
import toil
from orchestrator.models import Job, Status, PipelineType, CommandLineToolJob
from orchestrator.tasks import check_status_of_command_line_jobs


class TestToil(TestCase):
    """
    Test toil track functions
    """

    def download_toil_mock(self, toil_version):
        """
        Download TOIL mock data from s3
        """
        download_url = "https://toilmock.s3.amazonaws.com/toil_%s.tar.gz" % toil_version
        download_path = "toil_%s.tar.gz" % toil_version
        folder_path = "toil_%s" % toil_version
        self.download_full_path = os.path.abspath(download_path)
        self.mock_full_path = os.path.abspath(folder_path)
        if not os.path.exists(self.download_full_path):
            response = requests.get(download_url, stream=True)
            if response.status_code == 200:
                with open(self.download_full_path, "wb") as download:
                    download.write(response.raw.read())
            else:
                raise Exception("Could not download TOIL mock data from: %s" % download_url)
        if not os.path.exists(self.mock_full_path):
            unpack_archive(self.download_full_path)

    def setUp(self):
        Job.objects.all().delete()
        self.toil_version = toil.version.baseVersion
        if self.toil_version not in ["3.21.0", "5.4.0a1"]:
            raise Exception("TOIL version: %s not supported" % self.toil_version)
        self.download_toil_mock(self.toil_version)

    def tearDown(self):
        if os.path.exists(self.mock_full_path):
            rmtree(self.mock_full_path)
        if os.path.exists(self.download_full_path):
            os.remove(self.download_full_path)

    def mock_track(self, run_type):
        """
        Mock track using TOIL snapshots
        """
        mock_data_path = os.path.join(self.mock_full_path, run_type)
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
        job.save()
        check_status_of_command_line_jobs()

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
