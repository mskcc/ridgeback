from submitter.app import App


class JobSubmitter(object):
    def __init__(
        self, job_id, app, inputs, walltime, tool_walltime, memlimit, log_dir=None, log_prefix="", app_name="NA"
    ):
        self.app = App.factory(app)
        self.job_id = job_id
        self.inputs = inputs
        self.walltime = walltime
        self.tool_walltime = tool_walltime
        self.memlimit = memlimit
        self.log_dir = log_dir
        self.log_prefix = log_prefix
        self.app_name = app_name

    def prepare_to_submit(self):
        """
        Prepare directories to submit job
        """
        pass

    def get_submit_command(self):
        """
        return: command_line, args, log_path, job_id, env_map
        """
        pass

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
