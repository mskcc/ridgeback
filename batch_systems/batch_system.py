from django.conf import settings
import logging


def get_batch_system():
    if settings.BATCH_SYSTEM == "LSF":
        from batch_systems.lsf_client.lsf_client import LSFClient

        return LSFClient()
    elif settings.BATCH_SYSTEM == "SLURM":
        from batch_systems.slurm_client.slurm_client import SLURMClient

        return SLURMClient()
    else:
        raise Exception(f"Batch system {settings.BATCH_SYSTEM} not supported, please use either LSF or SLURM")


class BatchClient(object):
    """
    Client for a generic Batch system

    Attributes:
        logger (logging): logging module
    """

    def __init__(self):
        """
        init function
        """
        self.logger = logging.getLogger("BATCH_client")
        self.logfileName = "batch.log"
        self.name = "batch"

    def submit(self, command, job_args, stdout, job_id, env={}):
        """
        Submit command to LSF and store log in stdout

        Args:
            command (str): command to submit
            job_args (list): Additional options for leader job
            stdout (str): log file path
            job_id (str): job_id
            env (dict): Environment variables

        Returns:
            int: batch job id
        """

    def terminate(self, job_id):
        """
        Kill Batch job

        Args:
            job_id (str): job_id

        Returns:
            bool: successful
        """

    def set_walltime(self, expected_limit, hard_limit):
        """
        Set the walltime args of the batch job
        """
        walltime_args = []
        return walltime_args

    def set_memlimit(self, mem_limit, default=None):
        """
        Set the memlimit args of the batch job
        """
        mem_limit_args = []
        return mem_limit_args

    def set_group(self, group_id):
        """
        Set the group args of the batch job
        """
        group_id_args = []
        return group_id_args

    def set_stdout_file(self, stdout_file):
        """
        Set the output path of the log file
        """
        return []

    def set_service_queue(self):
        """
        Set the service queue parameter
        """
        service_queue_args = []
        return service_queue_args

    def status(self, external_job_id):
        """Parse Batch status

        Args:
            external_job_id (str): Batch id

        Returns:
            tuple: (Ridgeback Status int, extra info)
        """
        status = None
        return status

    def suspend(self, job_id):
        """
        Suspend Batch job
        Args:
            job_id (str): id of job
        Returns:
            bool: successful
        """

    def resume(self, job_id):
        """
        Resume Batch job
        Args:
            job_id (str): id of job
        Returns:
            bool: successful
        """
