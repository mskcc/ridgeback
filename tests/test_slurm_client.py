from django.test import TestCase
from mock import patch, Mock
from batch_systems.slurm_client.slurm_client import SLURMClient
from orchestrator.models import Status


class TestSLURMClient(TestCase):
    """
    Test LSF Client
    """

    def setUp(self):
        self.example_id = "12345678"
        self.example_job_id = "d736e17e-d67a-4897-901b-decab9942398"
        self.submit_response = "Submitted batch job {}".format(self.example_id)
        self.slurm_client = SLURMClient()
        self.example_partion = "partition1"
        self.status_completed_response = """
        {}|COMPLETED|0:0
        {}.batch|COMPLETED|0:0
        {}.extern|COMPLETED|0:0
        """.format(
            self.example_id, self.example_id, self.example_id
        )
        self.status_failed_response = """
        {}|FAILED|1:0
        {}.batch|FAILED|1:0
        {}.extern|COMPLETED|0:0
        """.format(
            self.example_id, self.example_id, self.example_id
        )
        self.status_pend_response = """
        {}|PENDING|0:0
        """.format(
            self.example_id
        )
        self.exit_reason = "FAILED, tool exit code: 0, batchsystem exit code: 1"
        self.pend_reason = None

    @patch("subprocess.run")
    def test_submit(self, submit_process):
        """
        Test SLURM submit
        """
        command = "ls"
        args = []
        stdout_file = f"{self.slurm_client.logfileName}"
        submit_process_obj = Mock()
        submit_process_obj.stdout = self.submit_response
        submit_process_obj.returncode = 0
        submit_process.return_value = submit_process_obj
        with self.settings(SLURM_PARTITION=self.example_partion):
            slurm_id = self.slurm_client.submit([command], args, stdout_file, self.example_job_id, {})
            expected_command = (
                [
                    "sbatch",
                    f"--partition={self.example_partion}",
                    f"--wckey={self.example_job_id}",
                    f"--output={self.slurm_client.logfileName}",
                ]
                + args
                + [f"--wrap=exec {command}"]
            )
        self.assertEqual(f"{slurm_id}", self.example_id)
        self.assertEqual(submit_process.call_args[0][0], expected_command)

    @patch("subprocess.run")
    def test_submit_with_args(self, submit_process):
        """
        Test SLURM submit with mem and walltime args
        """
        command = "ls"
        args = []
        stdout_file = f"{self.slurm_client.logfileName}"
        submit_process_obj = Mock()
        submit_process_obj.stdout = self.submit_response
        submit_process_obj.returncode = 0
        submit_process.return_value = submit_process_obj
        expected_limit = 10
        mem_limit = 8
        args = self.slurm_client.set_walltime(expected_limit, None)
        args.extend(self.slurm_client.set_memlimit(mem_limit))
        with self.settings(SLURM_PARTITION=self.example_partion):
            slurm_id = self.slurm_client.submit([command], args, stdout_file, self.example_job_id, {})
            expected_command = (
                [
                    "sbatch",
                    f"--partition={self.example_partion}",
                    f"--wckey={self.example_job_id}",
                    f"--output={self.slurm_client.logfileName}",
                ]
                + args
                + [f"--wrap=exec {command}"]
            )
        self.assertEqual(f"{slurm_id}", self.example_id)
        self.assertEqual(submit_process.call_args[0][0], expected_command)

    @patch("subprocess.run")
    def test_terminate(self, terminate_process):
        """
        Test SLURM terminate
        """
        terminate_process_obj = Mock()
        terminate_process_obj.returncode = 0
        terminate_process.return_value = terminate_process_obj
        expected_command = ["scancel", f"--wckey={self.example_job_id}"]
        terminated = self.slurm_client.terminate(self.example_job_id)
        self.assertEqual(terminate_process.call_args[0][0], expected_command)
        self.assertEqual(terminated, True)

    @patch("subprocess.run")
    def test_suspend(self, suspend_process):
        """
        Test SLURM suspend
        """
        sacct_process_obj = Mock()
        sacct_process_obj.stdout = f"{self.example_id}"
        sacct_process_obj.returncode = 0
        scontrol_process_obj = Mock()
        scontrol_process_obj.returncode = 0
        suspend_process.side_effect = [sacct_process_obj, scontrol_process_obj]
        expected_command = ["scontrol", "suspend", f"{self.example_id}"]
        suspended = self.slurm_client.suspend(self.example_job_id)
        self.assertEqual(suspend_process.call_args[0][0], expected_command)
        self.assertEqual(suspended, True)

    @patch("subprocess.run")
    def test_resume(self, resume_process):
        """
        Test SLURM resume
        """
        sacct_process_obj = Mock()
        sacct_process_obj.stdout = f"{self.example_id}"
        sacct_process_obj.returncode = 0
        scontrol_process_obj = Mock()
        scontrol_process_obj.returncode = 0
        resume_process.side_effect = [sacct_process_obj, scontrol_process_obj]
        expected_command = ["scontrol", "resume", f"{self.example_id}"]
        resumed = self.slurm_client.resume(self.example_job_id)
        self.assertEqual(resume_process.call_args[0][0], expected_command)
        self.assertEqual(resumed, True)

    @patch("subprocess.run")
    def test_failed_status(self, status_process):
        """
        Test SLURM failed status
        """
        status_process_obj = Mock()
        status_process_obj.returncode = 0
        status_process_obj.stdout = self.status_failed_response
        status_process.return_value = status_process_obj
        status = self.slurm_client.status(self.example_id)
        expected_status = Status.FAILED, self.exit_reason
        self.assertEqual(status, expected_status)

    @patch("subprocess.run")
    def test_pend_status(self, status_process):
        """
        Test SLURM pending status
        """
        status_process_obj = Mock()
        status_process_obj.returncode = 0
        status_process_obj.stdout = self.status_pend_response
        status_process.return_value = status_process_obj
        status = self.slurm_client.status(self.example_id)
        expected_status = Status.PENDING, self.pend_reason
        self.assertEqual(status, expected_status)
