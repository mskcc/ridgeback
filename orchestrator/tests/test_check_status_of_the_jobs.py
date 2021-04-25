import time
from django.test import TestCase
from django.conf import settings
from unittest import skip
from unittest.mock import patch
from orchestrator.tasks import check_job_status
from orchestrator.models import Status
from orchestrator.models import Job, PipelineType


class CheckStatusOfJobsTest(TestCase):

    def setUp(self):
        pass

    def test_status_transition(self):
        created = Status.CREATED
        self.assertFalse(created.transition(Status.CREATED))
        self.assertTrue(created.transition(Status.SUBMITTING))
        self.assertFalse(created.transition(Status.SUBMITTED))
        self.assertFalse(created.transition(Status.PENDING))
        self.assertFalse(created.transition(Status.RUNNING))
        self.assertFalse(created.transition(Status.COMPLETED))
        self.assertFalse(created.transition(Status.FAILED))
        self.assertTrue(created.transition(Status.ABORTED))
        self.assertFalse(created.transition(Status.SUSPENDED))
        self.assertFalse(created.transition(Status.UNKNOWN))

        submitting = Status.SUBMITTING
        self.assertFalse(submitting.transition(Status.CREATED))
        self.assertFalse(submitting.transition(Status.SUBMITTING))
        self.assertTrue(submitting.transition(Status.SUBMITTED))
        self.assertFalse(submitting.transition(Status.PENDING))
        self.assertFalse(submitting.transition(Status.RUNNING))
        self.assertFalse(submitting.transition(Status.COMPLETED))
        self.assertFalse(submitting.transition(Status.FAILED))
        self.assertTrue(submitting.transition(Status.ABORTED))
        self.assertFalse(submitting.transition(Status.SUSPENDED))
        self.assertFalse(submitting.transition(Status.UNKNOWN))

        submited = Status.SUBMITTED
        self.assertFalse(submited.transition(Status.CREATED))
        self.assertFalse(submited.transition(Status.SUBMITTING))
        self.assertFalse(submited.transition(Status.SUBMITTED))
        self.assertTrue(submited.transition(Status.PENDING))
        self.assertTrue(submited.transition(Status.RUNNING))
        self.assertTrue(submited.transition(Status.COMPLETED))
        self.assertTrue(submited.transition(Status.FAILED))
        self.assertTrue(submited.transition(Status.ABORTED))
        self.assertTrue(submited.transition(Status.UNKNOWN))
        self.assertTrue(submited.transition(Status.SUSPENDED))

        pending = Status.PENDING
        self.assertFalse(pending.transition(Status.CREATED))
        self.assertFalse(pending.transition(Status.SUBMITTING))
        self.assertFalse(pending.transition(Status.SUBMITTED))
        self.assertTrue(pending.transition(Status.PENDING))
        self.assertTrue(pending.transition(Status.RUNNING))
        self.assertTrue(pending.transition(Status.COMPLETED))
        self.assertTrue(pending.transition(Status.FAILED))
        self.assertTrue(pending.transition(Status.ABORTED))
        self.assertTrue(pending.transition(Status.UNKNOWN))
        self.assertTrue(pending.transition(Status.SUSPENDED))

        running = Status.RUNNING
        self.assertFalse(running.transition(Status.CREATED))
        self.assertFalse(running.transition(Status.SUBMITTING))
        self.assertFalse(running.transition(Status.SUBMITTED))
        self.assertFalse(running.transition(Status.PENDING))
        self.assertTrue(running.transition(Status.RUNNING))
        self.assertTrue(running.transition(Status.COMPLETED))
        self.assertTrue(running.transition(Status.FAILED))
        self.assertTrue(running.transition(Status.ABORTED))
        self.assertTrue(running.transition(Status.UNKNOWN))
        self.assertTrue(running.transition(Status.SUSPENDED))

        aborted = Status.ABORTED
        self.assertFalse(aborted.transition(Status.CREATED))
        self.assertFalse(aborted.transition(Status.SUBMITTING))
        self.assertFalse(aborted.transition(Status.SUBMITTED))
        self.assertFalse(aborted.transition(Status.PENDING))
        self.assertFalse(aborted.transition(Status.RUNNING))
        self.assertFalse(aborted.transition(Status.COMPLETED))
        self.assertFalse(aborted.transition(Status.FAILED))
        self.assertFalse(aborted.transition(Status.ABORTED))
        self.assertFalse(aborted.transition(Status.UNKNOWN))
        self.assertFalse(aborted.transition(Status.SUSPENDED))

        suspended = Status.SUSPENDED
        self.assertFalse(suspended.transition(Status.CREATED))
        self.assertFalse(suspended.transition(Status.SUBMITTING))
        self.assertFalse(suspended.transition(Status.SUBMITTED))
        self.assertTrue(suspended.transition(Status.PENDING))
        self.assertTrue(suspended.transition(Status.RUNNING))
        self.assertFalse(suspended.transition(Status.COMPLETED))
        self.assertFalse(suspended.transition(Status.FAILED))
        self.assertTrue(suspended.transition(Status.ABORTED))
        self.assertFalse(suspended.transition(Status.UNKNOWN))
        self.assertFalse(suspended.transition(Status.SUSPENDED))

        unknown = Status.UNKNOWN
        self.assertFalse(unknown.transition(Status.CREATED))
        self.assertFalse(unknown.transition(Status.SUBMITTING))
        self.assertFalse(unknown.transition(Status.SUBMITTED))
        self.assertTrue(unknown.transition(Status.PENDING))
        self.assertTrue(unknown.transition(Status.RUNNING))
        self.assertTrue(unknown.transition(Status.COMPLETED))
        self.assertTrue(unknown.transition(Status.FAILED))
        self.assertTrue(unknown.transition(Status.ABORTED))
        self.assertTrue(unknown.transition(Status.UNKNOWN))
        self.assertTrue(unknown.transition(Status.SUSPENDED))

        completed = Status.COMPLETED
        self.assertFalse(completed.transition(Status.RUNNING))
        self.assertFalse(completed.transition(Status.COMPLETED))
        self.assertFalse(completed.transition(Status.FAILED))
        self.assertFalse(completed.transition(Status.ABORTED))
        self.assertFalse(completed.transition(Status.SUSPENDED))
        self.assertFalse(completed.transition(Status.UNKNOWN))
        self.assertFalse(completed.transition(Status.PENDING))
        self.assertFalse(completed.transition(Status.CREATED))

        failed = Status.FAILED
        self.assertFalse(failed.transition(Status.RUNNING))
        self.assertFalse(failed.transition(Status.COMPLETED))
        self.assertFalse(failed.transition(Status.FAILED))
        self.assertFalse(failed.transition(Status.ABORTED))
        self.assertFalse(failed.transition(Status.SUSPENDED))
        self.assertFalse(failed.transition(Status.UNKNOWN))
        self.assertFalse(failed.transition(Status.PENDING))
        self.assertFalse(failed.transition(Status.CREATED))

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.status')
    @patch('orchestrator.tasks.dump_info_file')
    def test_submitted_to_pending(self, dump_info_file, status):
        job = Job.objects.create(type=PipelineType.CWL,
                           app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                           external_id='ext_id', status=Status.SUBMITTED)
        dump_info_file.return_value = None
        status.return_value = Status.PENDING, ""
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.PENDING)

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.status')
    @patch('orchestrator.tasks.dump_info_file')
    def test_pending_to_running(self, dump_info_file, status):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.PENDING)
        dump_info_file.return_value = None
        status.return_value = Status.RUNNING, ""
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.RUNNING)

    @patch('submitter.toil_submitter.ToilJobSubmitter.get_outputs')
    @patch('batch_systems.lsf_client.lsf_client.LSFClient.status')
    @patch('orchestrator.tasks.dump_info_file')
    def test_running_to_completed(self, dump_info_file, status, get_outputs):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.RUNNING)
        dump_info_file.return_value = None
        status.return_value = Status.COMPLETED, ""
        outputs = {"output": "test_value"}
        get_outputs.return_value = outputs, None
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.COMPLETED)
        self.assertEqual(job.outputs, outputs)

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.status')
    @patch('orchestrator.tasks.dump_info_file')
    def test_failed(self, dump_info_file, status):
        job = Job.objects.create(type=PipelineType.CWL,
                                 app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                                 external_id='ext_id', status=Status.RUNNING)
        dump_info_file.return_value = None
        status.return_value = Status.FAILED, ""
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)

    @skip("Don't test yet")
    @patch('batch_systems.lsf_client.lsf_client.LSFClient.status')
    @patch('orchestrator.tasks.dump_info_file')
    def test_load_test(self, dump_info_file, status):
        def make_sleeper(rv):
            def _(*args, **kwargs):
                # time.sleep(0.1)
                return rv
            return _

        for i in range(1000):
            Job.objects.create(type=PipelineType.CWL,
                               app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                               external_id='ext_id', status=Status.PENDING)
        dump_info_file.return_value = None
        status.side_effect = make_sleeper((Status.RUNNING, ""))
        start = time.time()
        # check_job_status()
        end = time.time()
        print(end - start)
