import time
from django.test import TestCase
from django.conf import settings
from unittest.mock import patch
from orchestrator.tasks import check_status_of_jobs
from orchestrator.models import Status
from orchestrator.models import Job, PipelineType


class CheckStatusOfJobsTest(TestCase):

    def setUp(self):
        pass

    def test_status_transition(self):
        created = Status.CREATED
        self.assertTrue(created.transition(Status.CREATED))
        self.assertTrue(created.transition(Status.PENDING))
        self.assertTrue(created.transition(Status.ABORTED))
        self.assertTrue(created.transition(Status.SUSPENDED))
        self.assertTrue(created.transition(Status.UNKNOWN))
        self.assertFalse(created.transition(Status.RUNNING))
        self.assertFalse(created.transition(Status.COMPLETED))
        self.assertFalse(created.transition(Status.FAILED))

        pending = Status.PENDING
        self.assertTrue(pending.transition(Status.PENDING))
        self.assertTrue(pending.transition(Status.RUNNING))
        self.assertTrue(pending.transition(Status.ABORTED))
        self.assertTrue(pending.transition(Status.SUSPENDED))
        self.assertTrue(pending.transition(Status.UNKNOWN))
        self.assertFalse(pending.transition(Status.CREATED))
        self.assertFalse(pending.transition(Status.COMPLETED))
        self.assertFalse(pending.transition(Status.FAILED))

        running = Status.RUNNING
        self.assertTrue(running.transition(Status.RUNNING))
        self.assertFalse(running.transition(Status.CREATED))
        self.assertTrue(running.transition(Status.ABORTED))
        self.assertFalse(running.transition(Status.PENDING))
        self.assertTrue(running.transition(Status.SUSPENDED))
        self.assertTrue(running.transition(Status.FAILED))
        self.assertTrue(running.transition(Status.UNKNOWN))
        self.assertTrue(running.transition(Status.COMPLETED))

        aborted = Status.ABORTED
        self.assertFalse(aborted.transition(Status.CREATED))
        self.assertFalse(aborted.transition(Status.PENDING))
        self.assertFalse(aborted.transition(Status.RUNNING))
        self.assertFalse(aborted.transition(Status.COMPLETED))
        self.assertFalse(aborted.transition(Status.FAILED))
        self.assertFalse(aborted.transition(Status.ABORTED))
        self.assertFalse(aborted.transition(Status.SUSPENDED))
        self.assertFalse(aborted.transition(Status.UNKNOWN))

        suspended = Status.SUSPENDED
        self.assertFalse(suspended.transition(Status.SUSPENDED))
        self.assertFalse(suspended.transition(Status.COMPLETED))
        self.assertFalse(suspended.transition(Status.FAILED))
        self.assertFalse(suspended.transition(Status.UNKNOWN))
        self.assertTrue(suspended.transition(Status.CREATED))
        self.assertTrue(suspended.transition(Status.PENDING))
        self.assertTrue(suspended.transition(Status.RUNNING))
        self.assertTrue(suspended.transition(Status.ABORTED))

        unknown = Status.UNKNOWN
        self.assertTrue(unknown.transition(Status.RUNNING))
        self.assertTrue(unknown.transition(Status.COMPLETED))
        self.assertTrue(unknown.transition(Status.FAILED))
        self.assertTrue(unknown.transition(Status.ABORTED))
        self.assertTrue(unknown.transition(Status.SUSPENDED))
        self.assertTrue(unknown.transition(Status.UNKNOWN))
        self.assertTrue(unknown.transition(Status.PENDING))
        self.assertTrue(unknown.transition(Status.CREATED))

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
    def test_pending_to_running(self, dump_info_file, status):
        job = Job.objects.create(type=PipelineType.CWL,
                           app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                           external_id='ext_id', status=Status.PENDING)
        dump_info_file.return_value = None
        status.return_value = Status.RUNNING, ""
        check_status_of_jobs()
        job.refresh_from_db()
        self.assertEqual(job.status, Status.RUNNING)

    @patch('batch_systems.lsf_client.lsf_client.LSFClient.status')
    @patch('orchestrator.tasks.dump_info_file')
    def test_load_test(self, dump_info_file, status):
        def make_sleeper(rv):
            def _(*args, **kwargs):
                time.sleep(0.1)
                return rv
            return _

        for i in range(1000):
            Job.objects.create(type=PipelineType.CWL,
                               app={"github": {"version": "1.0.0", "entrypoint": "test.cwl", "repository": ""}},
                               external_id='ext_id', status=Status.PENDING)
        dump_info_file.return_value = None
        status.side_effect = make_sleeper((Status.RUNNING, ""))
        start = time.time()
        check_status_of_jobs()
        end = time.time()
        print(end - start)
