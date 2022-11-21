from django.test import TestCase
from unittest.mock import patch
from orchestrator.commands import CommandType, Command
from orchestrator.tasks import term_job, check_job_status
from orchestrator.exceptions import RetryException
from orchestrator.models import Status
from orchestrator.models import Job, PipelineType


class TermTest(TestCase):
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
        )

    @patch("orchestrator.tasks.command_processor.delay")
    def test_term_from_created(self, command_processor):
        """
        Test reciving TERM command when Job is in CREATED state
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
        )
        term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    def test_term_from_submitting(self, add, delete, command_processor):
        """
        Testing when TERM command is received when Job is in SUBMITTING state.
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
        )
        add.return_value = True
        delete.return_value = True
        term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
        command_processor(Command(CommandType.SUBMIT, str(job.id)).to_dict())
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.term")
    def test_term_from_submitted(self, term, command_processor):
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
        )
        term.return_value = True
        command_processor.return_value = True
        term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("batch_systems.lsf_client.lsf_client.LSFClient.term")
    def test_term_fail_from_submitted(self, term):
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
        )
        term.return_value = False
        with self.assertRaises(RetryException, msg="Invalid question kind"):
            term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.SUBMITTED)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.term")
    def test_term_from_running(self, term, command_processor):
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
        )
        term.return_value = True
        command_processor.return_value = True
        term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("batch_systems.lsf_client.lsf_client.LSFClient.term")
    def test_term_fail_from_running(self, term):
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
        )
        term.return_value = False
        with self.assertRaises(RetryException, msg="Invalid question kind"):
            term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.RUNNING)

    def test_term_from_completed(self):
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
        )
        term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.COMPLETED)

    def test_term_from_failed(self):
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
        )
        term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)

    @patch("batch_systems.lsf_client.lsf_client.LSFClient.term")
    def test_term_from_unknown(self, term):
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
        )
        term.return_value = True
        term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)

    @patch("batch_systems.lsf_client.lsf_client.LSFClient.term")
    def test_term_from_suspended(self, term):
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
        )
        term.return_value = True
        term_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.TERMINATED)
