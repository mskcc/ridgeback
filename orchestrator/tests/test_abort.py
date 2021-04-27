from django.test import TestCase
from unittest.mock import patch
from orchestrator.commands import CommandType, Command
from orchestrator.tasks import abort_job, check_job_status, command_processor
from orchestrator.exceptions import RetryException, StopException
from orchestrator.models import Status
from orchestrator.models import Job, PipelineType


class AbortTest(TestCase):

    def setUp(self):
        self.job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.CREATED)

    def test_abort_from_created(self):
        """
        Test reciving ABORT command when Job is in CREATED state
        """
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.CREATED)
        abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)

    @patch('lib.memcache_lock.memcache_task_lock')
    def test_abort_from_submitting(self, memcache_task_lock):
        """
        Testing when ABORT command is received when Job is in SUBMITTING state.
        Test if SUBMIT command received after is handled correctly and also the check status
        """
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.SUBMITTING)
        memcache_task_lock.return_value = True
        abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)
        command_processor(Command(CommandType.SUBMIT, str(job.id)).to_dict())
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.abort')
    def test_abort_from_submitted(self, abort):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.SUBMITTED)
        abort.return_value = True
        abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.abort')
    def test_abort_fail_from_submitted(self, abort):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.SUBMITTED)
        abort.return_value = False
        with self.assertRaises(RetryException, msg='Invalid question kind'):
            abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.SUBMITTED)

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.abort')
    def test_abort_from_running(self, abort):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.RUNNING)
        abort.return_value = True
        abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.abort')
    def test_abort_fail_from_running(self, abort):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.RUNNING)
        abort.return_value = False
        with self.assertRaises(RetryException, msg='Invalid question kind'):
            abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.RUNNING)

    def test_abort_from_completed(self):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.COMPLETED)
        abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.COMPLETED)

    def test_abort_from_failed(self):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.FAILED)
        abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.abort')
    def test_abort_from_unknown(self, abort):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.UNKNOWN)
        abort.return_value = True
        abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.abort')
    def test_abort_from_suspended(self, abort):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.SUSPENDED)
        abort.return_value = True
        abort_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.ABORTED)
