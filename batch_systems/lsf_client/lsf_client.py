"""
Submit, monitor, and control LSF jobs
"""

import os
import re
import subprocess
import json
import logging
from django.conf import settings
from orchestrator.models import Status
from orchestrator.exceptions import FailToSubmitToSchedulerException, FetchStatusException


def format_lsf_job_id(job_id):
    return "/{}".format(job_id)


class LSFClient(object):
    """
    Client for LSF

    Attributes:
        logger (logging): logging module
    """

    def __init__(self):
        """
        init function
        """
        self.logger = logging.getLogger("LSF_client")

    def submit(self, command, job_args, stdout, job_id, env={}):
        """
        Submit command to LSF and store log in stdout

        Args:
            command (str): command to submit
            job_args (list): Additional options for leader bsub
            stdout (str): log file path
            job_id (str): job_id
            env (dict): Environment variables

        Returns:
            int: lsf job id
        """
        if settings.LSF_SLA:
            bsub_command = ["bsub", "-sla", settings.LSF_SLA, "-g", format_lsf_job_id(job_id), "-oo", stdout] + job_args
        else:
            bsub_command = ["bsub", "-g", format_lsf_job_id(job_id), "-oo", stdout] + job_args

        bsub_command.extend(command)
        current_env = os.environ.copy()
        for k, v in env.items():
            if v:
                current_env[k] = v
            elif k in current_env:
                current_env.pop(k)
        self.logger.debug("Running command: %s\nEnv: %s", bsub_command, current_env)
        process = subprocess.run(
            bsub_command,
            check=True,
            stdout=subprocess.PIPE,
            universal_newlines=True,
            env=current_env,
        )
        if process.returncode != 0:
            self.logger.exception(f"Failed to submit job to LSF. Process return_code: {process.returncode}")
            raise FailToSubmitToSchedulerException(
                f"Failed to submit job to LSF. Process return_code: {process.returncode}"
            )
        return self._parse_procid(process.stdout)

    def terminate(self, job_id):
        """
        Kill LSF job

        Args:
            job_id (str): job_id

        Returns:
            bool: successful
        """
        self.logger.debug("Terminating LSF jobs for job %s", job_id)
        bkill_command = ["bkill", "-g", format_lsf_job_id(job_id), "0"]
        process = subprocess.run(bkill_command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        if process.returncode in (0, 255):
            return True
        return False

    def parse_bjobs(self, bjobs_output_str):
        """
        Parse the output of bjobs into a descriptive dict

        Args:
            bjobs_output_str (str): Stdout from bjobs

        Returns:
            Dict: bjobs records
        """
        bjobs_dict = None
        bjobs_records = None
        # Handle Cannot connect to LSF. Please wait ... type messages
        dict_start = bjobs_output_str.find("{")
        dict_end = bjobs_output_str.rfind("}")
        if dict_start != -1 and dict_end != -1:
            bjobs_output = bjobs_output_str[dict_start : (dict_end + 1)]
            try:
                bjobs_dict = json.loads(bjobs_output)
            except json.decoder.JSONDecodeError:
                self.logger.error("Could not parse bjobs output: %s", bjobs_output_str)
            if "RECORDS" in bjobs_dict:
                bjobs_records = bjobs_dict["RECORDS"]
        if bjobs_records is None:
            self.logger.error("Could not find bjobs output json in: %s", bjobs_output_str)

        return bjobs_records

    def _parse_procid(self, stdout):
        """
        Parse bsub output and retrieve the LSF id

        Args:
            stdout (str): bsub output

        Returns:
            int: LSF id
        """
        self.logger.debug("LSF returned %s", stdout)
        lsf_job_id_search = re.search("Job <(.*)> is submitted", stdout)
        if lsf_job_id_search:
            lsf_job_id = int(lsf_job_id_search[1])
            self.logger.debug("Got the job id: %s", lsf_job_id)
            return lsf_job_id
        else:
            self.logger.error("Could not parse job_id. Job is not submitted to LSF\nReason: %s", stdout)
            raise FailToSubmitToSchedulerException(f"Reason: {stdout}")

    def _handle_status(self, process_status, process_output, external_job_id):
        """
        Map LSF status to Ridgeback status

        Args:
            process_status (str): LSF status of process
            process_output (dict): LSF record dict
            external_job_id (str): LSF job id

        Returns:
            tuple: (Ridgeback Status int, extra info)
        """
        if process_status == "DONE":
            self.logger.debug("Job [%s] completed", external_job_id)
            return Status.COMPLETED, None
        if process_status == "PEND":
            pending_info = ""
            if "PEND_REASON" in process_output:
                if process_output["PEND_REASON"]:
                    pending_info = process_output["PEND_REASON"]
            self.logger.debug("Job [%s] pending with: %s", external_job_id, pending_info)
            return Status.PENDING, pending_info.strip()
        if process_status == "EXIT":
            exit_info = ""
            if "EXIT_CODE" in process_output:
                if process_output["EXIT_CODE"]:
                    exit_code = process_output["EXIT_CODE"]
                    exit_info = "\nexit code: {}".format(exit_code)
            if "EXIT_REASON" in process_output:
                if process_output["EXIT_REASON"]:
                    exit_reason = process_output["EXIT_REASON"]
                    exit_info += "\nexit reason: {}".format(exit_reason)
            self.logger.error("Job [%s] failed with: %s", external_job_id, exit_info)
            return Status.FAILED, exit_info.strip()
        if process_status == "RUN":
            self.logger.debug("Job [%s] is running", external_job_id)
            return Status.RUNNING, None
        if process_status in {"PSUSP", "USUSP", "SSUSP"}:
            self.logger.debug("Job [%s] is suspended", external_job_id)
            suspended_info = "Job suspended"
            return Status.SUSPENDED, suspended_info.strip()
        self.logger.debug("Job [%s] is in an unhandled state (%s)", external_job_id, process_status)
        status_info = "Job is in an unhandles state: {}".format(process_status)
        return Status.UNKNOWN, status_info.strip()

    def _parse_status(self, stdout, external_job_id):
        """Parse LSF stdout helper

        Args:
            stdout (str): stdout of bjobs
            external_job_id (str): LSF id

        Returns:
            tuple: (Ridgeback Status int, extra info)
        """
        bjobs_records = self.parse_bjobs(stdout)
        if bjobs_records:
            process_output = bjobs_records[0]
            if "STAT" in process_output:
                process_status = process_output["STAT"]
                return self._handle_status(process_status, process_output, str(external_job_id))
            if "ERROR" in process_output:
                error_message = ""
                if process_output["ERROR"]:
                    error_message = process_output["ERROR"]
                return Status.UNKNOWN, error_message.strip()
        raise FetchStatusException(f"Failed to get status for job {external_job_id}")

    def status(self, external_job_id):
        """Parse LSF status

        Args:
            external_job_id (str): LSF id

        Returns:
            tuple: (Ridgeback Status int, extra info)
        """
        bsub_command = [
            "bjobs",
            "-json",
            "-o",
            "user exit_code stat exit_reason pend_reason",
            str(external_job_id),
        ]
        self.logger.debug("Checking lsf status for job: %s", external_job_id)
        process = subprocess.run(bsub_command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        status = self._parse_status(process.stdout, external_job_id)
        return status

    def suspend(self, job_id):
        """
        Suspend LSF job
        Args:
            extrnsl_job_id (str): id of job
        Returns:
            bool: successful
        """
        self.logger.debug("Suspending LSF jobs for job %s", job_id)
        bsub_command = ["bstop", "-g", format_lsf_job_id(job_id), "0"]
        process = subprocess.run(bsub_command, stdout=subprocess.PIPE, universal_newlines=True)
        if process.returncode == 0:
            return True
        return False

    def resume(self, job_id):
        """
        Resume LSF job
        Args:
            job_id (str): id of job
        Returns:
            bool: successful
        """
        self.logger.debug("Unsuspending LSF jobs for job %s", job_id)
        bsub_command = ["bresume", "-g", format_lsf_job_id(job_id), "0"]
        process = subprocess.run(bsub_command, stdout=subprocess.PIPE, universal_newlines=True)
        if process.returncode == 0:
            return True
        return False
