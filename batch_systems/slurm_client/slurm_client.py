"""
Submit, monitor, and control SLURM jobs
"""

import os
import re
import subprocess
import logging
from django.conf import settings
from orchestrator.models import Status
from orchestrator.exceptions import FailToSubmitToSchedulerException, FetchStatusException
from batch_systems.batch_system import BatchClient


class SLURMClient(BatchClient):
    """
    Client for SLURM

    Attributes:
        logger (logging): logging module
    """

    def __init__(self):
        """
        init function
        """
        self.logger = logging.getLogger("SLURM_client")
        self.logfileName = "slurm.log"
        self.name = "slurm"

    def submit(self, command, job_args, stdout, job_id, env={}):
        """
        Submit command to SLURM and store log in stdout

        Args:
            command (str): command to submit
            job_args (list): Additional options for leader sbatch
            stdout (str): log file path
            job_id (str): job_id
            env (dict): Environment variables

        Returns:
            int: slurm job id
        """
        work_dir = os.path.dirname(stdout)

        sbatch_command = (
            ["sbatch"]
            + self.set_service_queue()
            + self.set_group(job_id)
            + self.set_stdout_file(stdout)
            + job_args
            + [f"--wrap=exec {command}"]
        )
        current_env = os.environ.copy()
        for k, v in env.items():
            if v:
                current_env[k] = v
            elif k in current_env:
                current_env.pop(k)
        self.logger.debug("Running command: %s\nEnv: %s", sbatch_command, current_env)
        process = subprocess.run(
            sbatch_command,
            check=True,
            stdout=subprocess.PIPE,
            universal_newlines=True,
            cwd=work_dir,
            env=current_env,
        )
        if process.returncode != 0:
            self.logger.exception(f"Failed to submit job to SLURM. Process return_code: {process.returncode}")
            raise FailToSubmitToSchedulerException(
                f"Failed to submit job to SLURM. Process return_code: {process.returncode}"
            )
        return self._parse_procid(process.stdout)

    def terminate(self, job_id):
        """
        Kill SLURM job

        Args:
            job_id (str): job_id

        Returns:
            bool: successful
        """
        self.logger.debug("Terminating SLURM jobs for job %s", job_id)
        scancel_command = ["scancel", f"--wckey={job_id}"]
        process = subprocess.run(scancel_command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        if process.returncode in (0, 255):
            return True
        return False

    def set_walltime(self, expected_limit, hard_limit):
        walltime_args = []
        if expected_limit:
            walltime_args = walltime_args + [f"--t={expected_limit}"]
        if hard_limit:
            self.logger.debug(
                "Hard limits on submit are no supported, please check the cluster KillWait and OverTimeLimit params"
            )
        return walltime_args

    def set_memlimit(self, mem_limit, default=None):
        mem_limit_args = []
        if default:
            mem_limit = [f"--mem={default}"]
        if mem_limit:
            mem_limit_args = [f"--mem={mem_limit}"]
        return mem_limit_args

    def set_group(self, group_id):
        group_id_args = []
        if group_id:
            group_id_args = [f"--wckey={group_id}"]
        return group_id_args

    def set_stdout_file(self, stdout_file):
        if stdout_file:
            return [f"--output={stdout_file}"]
        return [f"--output={self.logfileName}"]

    def set_service_queue(self):
        service_queue_args = []
        if settings.SLURM_PARTITION:
            service_queue_args = [f"--partition={settings.SLURM_PARTITION}"]
        return service_queue_args

    def _parse_sacct(self, sacct_output_str, external_job_id):
        """
        Parse the output of sacct into a descriptive dict

        Args:
            sacct_output_str (str): Stdout from sacct
            external_job_id (str): SLURM job id

        Returns:
            tuple: sacct job record (id,status,batch_system_exitcode,tool_exitcode)
        """
        sacct_record = None
        if sacct_output_str:
            output_lines = sacct_output_str.strip().split("\n")
            for single_sacct_line in output_lines:
                slurm_job_info = single_sacct_line.strip().split("|")
                slurm_id = slurm_job_info[0]
                if slurm_id == external_job_id:
                    status = slurm_job_info[1]
                    exitcode_batch = slurm_job_info[2].split(":")[0]
                    exitcode_tool = slurm_job_info[2].split(":")[1]
                    sacct_record = (slurm_id, status, exitcode_batch, exitcode_tool)
        if not sacct_record:
            self.logger.error(f"Error - sacct command could not find job {external_job_id}")
        return sacct_record

    def _parse_procid(self, stdout):
        """
        Parse sbatch output and retrieve the SLURM id

        Args:
            stdout (str): sbatch output

        Returns:
            int: SLURM id
        """
        self.logger.debug("SLURM returned %s", stdout)
        slurm_job_id_search = re.search("Submitted batch job (.*)", stdout)
        if slurm_job_id_search:
            slurm_job_id = int(slurm_job_id_search[1])
            self.logger.debug("Got the job id: %s", slurm_job_id)
            return slurm_job_id
        else:
            self.logger.error("Could not parse job_id. Job is not submitted to SLURM\nReason: %s", stdout)
            raise FailToSubmitToSchedulerException(f"Reason: {stdout}")

    def _handle_status(self, process_status, batchsystem_exitcode, tool_exitcode, external_job_id):
        """
        Map SLURM status to Ridgeback status

        Args:
            process_status (str): SLURM status of process
            batchsystem_exitcode (str): Exitcode from the batchsystem
            tool_exitcode (str): Exitcode form the tool

        Returns:
            tuple: (Ridgeback Status int, extra info)
        """

        # If a job is in one of these states, it might eventually move to a different
        # state.

        if process_status == "COMPLETED":
            self.logger.debug("Job [%s] completed", external_job_id)
            return Status.COMPLETED, None
        if process_status in [
            "PENDING",
            "CONFIGURING",
            "REQUEUED",
            "REQUEUE_FED",
            "REQUEUE_HOLD",
            "RESIZING",
            "RESV_DEL_HOLD",
            "POWER_UP_NODE",
        ]:
            self.logger.debug("Job [%s] is pending", external_job_id)
            return Status.PENDING, None
        if process_status in [
            "BOOT_FAIL",
            "LAUNCH_FAILED",
            "CANCELLED",
            "DEADLINE",
            "FAILED",
            "NODE_FAIL",
            "OUT_OF_MEMORY",
            "PREEMPTED",
            "REVOKED",
            "SPECIAL_EXIT",
            "RECONFIG_FAIL",
            "TIMEOUT",
        ]:
            exit_info = (
                f"{process_status}, tool exit code: {tool_exitcode}, batchsystem exit code: {batchsystem_exitcode}"
            )
            self.logger.error("Job [%s] failed with: %s", external_job_id, exit_info)
            return Status.FAILED, exit_info.strip()
        if process_status in ["RUNNING", "COMPLETING", "STAGE_OUT"]:
            self.logger.debug("Job [%s] is running", external_job_id)
            return Status.RUNNING, None
        if process_status in ["SUSPENDED", "STOPPED"]:
            self.logger.debug("Job [%s] is suspended", external_job_id)
            suspended_info = "Job suspended"
            return Status.SUSPENDED, suspended_info.strip()
        self.logger.debug("Job [%s] is in an unhandled state (%s)", external_job_id, process_status)
        status_info = "Job is in an unhandles state: {}".format(process_status)
        return Status.UNKNOWN, status_info.strip()

    def _parse_status(self, stdout, external_job_id):
        """Parse SLURM stdout helper

        Args:
            stdout (str): stdout of bjobs
            external_job_id (str): SLURM id

        Returns:
            tuple: (Ridgeback Status int, extra info)
        """

        sacct_record = self._parse_sacct(stdout, external_job_id)
        if sacct_record:
            status = sacct_record[1]
            exit_batch = sacct_record[2]
            exit_tool = sacct_record[3]
            return self._handle_status(status, exit_batch, exit_tool, external_job_id)

        raise FetchStatusException(f"Failed to get status for job {external_job_id}")

    def status(self, external_job_id):
        """Parse SLURM status

        Args:
            external_job_id (str): SLURM id

        Returns:
            tuple: (Ridgeback Status int, extra info)
        """
        saact_command = ["sacct", f"--jobs={external_job_id}.batch", "--format='jobid,state,exitcode'", "-n", "-P"]
        self.logger.debug("Checking slurm status for job: %s", external_job_id)
        process = subprocess.run(saact_command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        status = self._parse_status(process.stdout, str(external_job_id))
        return status

    def _get_job_list(self, job_id):
        """Get slurm job ids in a group

        Args:
            job_id (str): id of job

        Returns:
            list: SLURM job ids
        """

        slurm_jobs = []
        saact_command = ["sacct", f"--wckeys={job_id}", "--format='jobid'", "-n", "-P"]
        process = subprocess.run(saact_command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        output = process.stdout
        for single_line in output.strip().split("\n"):
            single_slurm_id = single_line.split(".")[0]
            if single_slurm_id and single_slurm_id not in slurm_jobs:
                slurm_jobs.append(single_slurm_id)
        return slurm_jobs

    def suspend(self, job_id):
        """
        Suspend SLURM job
        Args:
            job_id (str): id of job
        Returns:
            bool: successful
        """
        self.logger.debug("Suspending SLURM jobs for job %s", job_id)
        job_list = self._get_job_list(job_id)
        job_list_str = ",".join(job_list)
        scontrol_command = ["scontrol", "suspend", f"{job_list_str}"]
        process = subprocess.run(scontrol_command, stdout=subprocess.PIPE, universal_newlines=True)
        if process.returncode == 0:
            return True
        return False

    def resume(self, job_id):
        """
        Resume SLURM job
        Args:
            job_id (str): id of job
        Returns:
            bool: successful
        """
        self.logger.debug("Resuming SLURM jobs for job %s", job_id)
        job_list = self._get_job_list(job_id)
        job_list_str = ",".join(job_list)
        scontrol_command = ["scontrol", "resume", f"{job_list_str}"]
        process = subprocess.run(scontrol_command, stdout=subprocess.PIPE, universal_newlines=True)
        if process.returncode == 0:
            return True
        return False
