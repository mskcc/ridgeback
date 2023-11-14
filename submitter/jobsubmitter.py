from submitter.app import App
from batch_systems.lsf_client.lsf_client import LSFClient


class JobSubmitter(object):
    def __init__(self, job_id, app, inputs, leader_walltime, tool_walltime, memlimit, log_dir=None):
        self.app = App.factory(app)
        self.job_id = job_id
        self.inputs = inputs
        self.lsf_client = LSFClient()
        self.leader_walltime = leader_walltime
        self.tool_walltime = tool_walltime
        self.memlimit = memlimit
        self.log_dir = log_dir

    def submit(self):
        """
        Submit pipeline job to lsf
        :return: lsf id, job store directory, job working directory, output directory
        """
        pass

    def status(self, external_id):
        return self.lsf_client.status(external_id)

    def terminate(self):
        """
        Terminates the job
        """
        return self.lsf_client.terminate(self.job_id)

    def resume(self):
        """
        Resumes the job
        """
        return self.lsf_client.resume(self.job_id)

    def suspend(self):
        """
        Suspends the job
        """
        return self.lsf_client.suspend(self.job_id)

    def get_commandline_status(self, cache):
        """
        Get the status of the command line tools in the job
        """

    def get_outputs(self):
        """
        :return: Parse outputs and return output files in json format
        """

    def _dump_app_inputs(self):
        """
        Prepare app, and inputs
        :return: app location, inputs, location
        """

    def _prepare_directories(self):
        """
        Prepare execution directories
        :return:
        """

    def _job_args(self):
        pass

    def _command_line(self):
        pass
