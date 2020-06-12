from submitter.app import App
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

    def status(self, external_id):
        return self.lsf_client.status(external_id)

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

    def _command_line(self):
        """
        :return: CommandLine for submitting pipeline
        """
