from django.test import TestCase
from mock import patch, Mock
from django.conf import settings
from batch_systems.lsf_client.lsf_client import LSFClient
from orchestrator.models import Status


class TestLSFClient(TestCase):
    """
    Test LSF Client
    """

    def setUp(self):
        please_wait_str = """Cannot connect to LSF. Please wait ...
        Cannot connect to LSF. Please wait ...
        Cannot connect to LSF. Please wait ...
        """
        self.example_id = 12345678
        self.submit_response = "Job <{}> is submitted".format(self.example_id)
        self.submit_response_please_wait = please_wait_str + self.submit_response
        self.lsf_client = LSFClient()
        self.exist_reason = "TERM_OWNER: job killed by owner"
        self.pend_reason = "New job is waiting for scheduling;"
        self.status_failed_response = """
        {
          "COMMAND":"bjobs",
          "JOBS":1,
          "RECORDS":[
            {
              "USER":"nikhil",
              "EXIT_CODE":"",
              "STAT":"EXIT",
              "EXIT_REASON":"TERM_OWNER: job killed by owner",
              "PEND_REASON":""
            }
          ]
        }
        """
        self.status_pend_response = """
        {
          "COMMAND":"bjobs",
          "JOBS":1,
          "RECORDS":[
            {
              "USER":"nikhil",
              "EXIT_CODE":"",
              "STAT":"PEND",
              "EXIT_REASON":"",
              "PEND_REASON":"New job is waiting for scheduling;"
            }
          ]
        }
        """
        self.status_failed_please_wait = please_wait_str + self.status_failed_response
        self.status_pend_please_wait = please_wait_str + self.status_pend_response

    @patch("subprocess.run")
    def test_submit(self, submit_process):
        """
        Test LSF submit
        """
        command = ["ls"]
        args = []
        stdout_file = "stdout.txt"
        submit_process_obj = Mock()
        submit_process_obj.stdout = self.submit_response
        submit_process.return_value = submit_process_obj
        lsf_id = self.lsf_client.submit(command, args, stdout_file, {})
        expected_command = ["bsub", "-sla", settings.LSF_SLA, "-oo", stdout_file] + args + command
        self.assertEqual(lsf_id, self.example_id)
        self.assertEqual(submit_process.call_args[0][0], expected_command)

    @patch("subprocess.run")
    def test_submit_slow_lsf(self, submit_process):
        """
        Test LSF submit when LSF is slow
        """
        command = ["ls"]
        args = []
        stdout_file = "stdout.txt"
        submit_process_obj = Mock()
        submit_process_obj.stdout = self.submit_response_please_wait
        submit_process.return_value = submit_process_obj
        lsf_id = self.lsf_client.submit(command, args, stdout_file, {})
        self.assertEqual(lsf_id, self.example_id)

    @patch("subprocess.run")
    def test_abort(self, abort_process):
        """
        Test LSF abort
        """
        abort_process_obj = Mock()
        abort_process_obj.returncode = 0
        abort_process.return_value = abort_process_obj
        expected_command = ["bkill", self.example_id]
        aborted = self.lsf_client.abort(self.example_id)
        self.assertEqual(abort_process.call_args[0][0], expected_command)
        self.assertEqual(aborted, True)

    @patch("subprocess.run")
    def test_failed_status(self, status_process):
        """
        Test LSF failed status
        """
        status_process_obj = Mock()
        status_process_obj.returncode = 0
        status_process_obj.stdout = self.status_failed_response
        status_process.return_value = status_process_obj
        status = self.lsf_client.status(self.example_id)
        expected_status = Status.FAILED, "exit reason: {}".format(self.exist_reason)
        self.assertEqual(status, expected_status)

    @patch("subprocess.run")
    def test_pend_status(self, status_process):
        """
        Test LSF pending status
        """
        status_process_obj = Mock()
        status_process_obj.returncode = 0
        status_process_obj.stdout = self.status_pend_response
        status_process.return_value = status_process_obj
        status = self.lsf_client.status(self.example_id)
        expected_status = Status.PENDING, self.pend_reason
        self.assertEqual(status, expected_status)

    @patch("subprocess.run")
    def test_failed_status_slow_lsf(self, status_process):
        """
        Test LSF failed status when LSF is slow
        """
        status_process_obj = Mock()
        status_process_obj.returncode = 0
        status_process_obj.stdout = self.status_failed_please_wait
        status_process.return_value = status_process_obj
        status = self.lsf_client.status(self.example_id)
        expected_status = Status.FAILED, "exit reason: {}".format(self.exist_reason)
        self.assertEqual(status, expected_status)

    @patch("subprocess.run")
    def test_pend_status_slow_lsf(self, status_process):
        """
        Test LSF pending status when LSF is slow
        """
        status_process_obj = Mock()
        status_process_obj.returncode = 0
        status_process_obj.stdout = self.status_pend_please_wait
        status_process.return_value = status_process_obj
        status = self.lsf_client.status(self.example_id)
        expected_status = Status.PENDING, self.pend_reason
        self.assertEqual(status, expected_status)
