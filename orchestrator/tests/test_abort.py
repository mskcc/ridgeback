from django.test import TestCase
from unittest.mock import patch
from orchestrator.commands import CommandType, Command
from orchestrator.tasks import terminate_job, check_job_status
from orchestrator.exceptions import RetryException
from orchestrator.models import Status
from orchestrator.models import Job, PipelineType


class TerminateTest(TestCase):
    def setUp(self):
        self.job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.CREATED,
            metadata={"app_name": "NA"},
        )

    @patch("orchestrator.tasks.command_processor.delay")
    def test_terminate_from_created(self, command_processor):
        """
        Test reciving TERMINATE command when Job is in CREATED state
        """
        command_processor.return_vaule = True
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.CREATED,
            metadata={"app_name": "NA"},
        )
        terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    def test_terminate_from_submitting(self, add, delete, command_processor):
        """
        Testing when TERMINATE command is received when Job is in SUBMITTING state.
        Test if SUBMIT command received after is handled correctly and also the check status
        """
        command_processor.return_value = True
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.SUBMITTING,
            metadata={"app_name": "NA"},
        )
        add.return_value = True
        delete.return_value = True
        terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
        command_processor(Command(CommandType.SUBMIT, str(job.id)).to_dict())
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.terminate")
    def test_terminate_from_submitted(self, terminate, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.SUBMITTED,
            metadata={"app_name": "NA"},
        )
        terminate.return_value = True
        command_processor.return_value = True
        terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("batch_systems.lsf_client.lsf_client.LSFClient.terminate")
    def test_terminate_fail_from_submitted(self, terminate):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.SUBMITTED,
            metadata={"app_name": "NA"},
        )
        terminate.return_value = False
        with self.assertRaises(RetryException, msg="Invalid question kind"):
            terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.SUBMITTED)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.terminate")
    def test_term_from_running(self, terminate, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.RUNNING,
            metadata={"app_name": "NA"},
        )
        terminate.return_value = True
        command_processor.return_value = True
        terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("batch_systems.lsf_client.lsf_client.LSFClient.terminate")
    def test_terminate_fail_from_running(self, terminate):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.RUNNING,
            metadata={"app_name": "NA"},
        )
        terminate.return_value = False
        with self.assertRaises(RetryException, msg="Invalid question kind"):
            terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.RUNNING)

    def test_terminate_from_completed(self):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.COMPLETED,
            metadata={"app_name": "NA"},
        )
        terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.COMPLETED)

    def test_terminate_from_failed(self):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.FAILED,
            metadata={"app_name": "NA"},
        )
        terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)

    @patch("batch_systems.lsf_client.lsf_client.LSFClient.terminate")
    def test_terminate_from_unknown(self, terminate):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.UNKNOWN,
            metadata={"app_name": "NA"},
        )
        terminate.return_value = True
        terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("batch_systems.lsf_client.lsf_client.LSFClient.terminate")
    def test_terminate_from_suspended(self, terminate):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.SUSPENDED,
            metadata={"app_name": "NA"},
        )
        terminate.return_value = True
        terminate_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
