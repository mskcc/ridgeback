import os
from submitter.app import App
from django.conf import settings
from batch_systems.lsf_client.lsf_client import LSFClient


class JobSubmitter(object):

    def __init__(self, app, inputs):
        self.app = App.factory(app)
        self.inputs = inputs
        self.lsf_client = LSFClient()

    def submit(self):
        """
        Submit pipeline job to lsf
        :return: lsf id, job store directory, job working directory, output directory
        """
        self._prepare_directories()
        command_line = self._command_line()
        job_args = self._job_args()
        log_path = os.path.join(self.job_work_dir, 'lsf.log')
        external_id = self.lsf_client.submit(command_line, job_args, log_path)
        return external_id, self.job_store_dir, self.job_work_dir, self.job_outputs_dir

    def status(self, external_id):
        return self.lsf_client.status(external_id)

    def abort(self, external_id):
        return self.lsf_client.abort(external_id)

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

