from mock import patch
from django.test import TestCase
from toil_orchestrator.models import Job, Status
from toil_orchestrator.tasks import submit_jobs_to_lsf, check_status_of_jobs, on_failure_to_submit, get_message


class TestTasks(TestCase):
    fixtures = [
    "toil_orchestrator.job.json"
    ]

    def setUp(self):
        self.current_job = Job.objects.first()

    def test_failure_to_submit(self):
        on_failure_to_submit(None,None,None,[self.current_job.id],None,None)
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status,Status.FAILED)
        self.assertNotEqual(self.current_job.finished,None)
        info_message = get_message(self.current_job)['info']
        log_path = get_message(self.current_job)['log']
        self.assertEqual(info_message,'Failed to submit job')
        self.assertNotEqual(log_path,None)

    @patch('submitter.jobsubmitter.JobSubmitter.__init__')
    @patch('submitter.jobsubmitter.JobSubmitter.submit')
    @patch('toil_orchestrator.tasks.save_job_info')
    def test_submit(self, save_job_info, submit, init):
        init.return_value = None
        save_job_info.return_value = None
        submit.return_value = self.current_job.external_id, self.current_job.job_store_location, self.current_job.working_dir, self.current_job.output_directory
        submit_jobs_to_lsf(self.current_job.id)
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status,Status.PENDING)
        self.assertEqual(self.current_job.finished,None)

    @patch('toil_orchestrator.tasks.get_job_info_path')
    @patch('submitter.jobsubmitter.JobSubmitter.__init__')
    @patch('submitter.jobsubmitter.JobSubmitter.status')
    @patch('submitter.jobsubmitter.JobSubmitter.get_outputs')
    def test_complete(self, get_outputs, status, init, get_job_info_path):
        self.current_job.status = Status.PENDING
        self.current_job.save()
        init.return_value = None
        get_outputs.return_value = {'outputs': True}, None
        get_job_info_path.return_value = "sample/job/path"
        status.return_value = Status.COMPLETED, None
        check_status_of_jobs()
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status, Status.COMPLETED)
        self.assertNotEqual(self.current_job.finished, None)

    @patch('toil_orchestrator.tasks.get_job_info_path')
    @patch('submitter.jobsubmitter.JobSubmitter.__init__')
    @patch('submitter.jobsubmitter.JobSubmitter.status')
    def test_fail(self, status, init, get_job_info_path):
        self.current_job.status = Status.PENDING
        self.current_job.save()
        init.return_value = None
        get_job_info_path.return_value = "sample/job/path"
        status.return_value = Status.FAILED, "submitter reason"
        check_status_of_jobs()
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status, Status.FAILED)
        self.assertNotEqual(self.current_job.finished, None)
        info_message = get_message(self.current_job)['info']
        failed_jobs = get_message(self.current_job)['failed_jobs']
        unknown_jobs = get_message(self.current_job)['unknown_jobs']
        expected_failed_jobs = {
        'failed_job_1': ['failed_job_1_id'],
        'failed_job_2': ['failed_job_2_id']
        }
        expected_unknown_jobs = {
        'unknown_job': ['unknown_job_id_1', 'unknown_job_id_2']
        }
        self.assertEqual(info_message,'submitter reason')
        self.assertEqual(failed_jobs, expected_failed_jobs)
        self.assertEqual(unknown_jobs,expected_unknown_jobs)

    @patch('toil_orchestrator.tasks.get_job_info_path')
    @patch('submitter.jobsubmitter.JobSubmitter.__init__')
    @patch('submitter.jobsubmitter.JobSubmitter.status')
    def test_running(self, status, init, get_job_info_path):
        self.current_job.status = Status.PENDING
        self.current_job.save()
        init.return_value = None
        get_job_info_path.return_value = "sample/job/path"
        status.return_value = Status.RUNNING, None
        check_status_of_jobs()
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status, Status.RUNNING)
        self.assertNotEqual(self.current_job.started, None)
        self.assertEqual(self.current_job.finished, None)

    def test_fail_not_submitted(self):
        self.current_job.status = Status.PENDING
        self.current_job.external_id = None
        self.current_job.save()
        check_status_of_jobs()
        self.current_job.refresh_from_db()
        self.assertEqual(self.current_job.status, Status.FAILED)
        self.assertNotEqual(self.current_job.finished, None)
        info_message = get_message(self.current_job)['info']
        failed_jobs = get_message(self.current_job)['failed_jobs']
        unknown_jobs = get_message(self.current_job)['unknown_jobs']
        expected_failed_jobs = {}
        expected_unknown_jobs = {}
        self.assertTrue('External id not provided' in info_message)
        self.assertEqual(failed_jobs, expected_failed_jobs)
        self.assertEqual(unknown_jobs,expected_unknown_jobs)

