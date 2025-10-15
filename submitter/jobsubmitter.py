import os
import shutil
from submitter.app import App
from django.conf import settings
from submitter.userswitcher import userswitch
from getpass import getuser
from batch_systems.batch_system import get_batch_system


class JobSubmitter(object):
    def __init__(
        self,
        job_id,
        app,
        inputs,
        root_dir,
        resume_jobstore,
        walltime,
        tool_walltime,
        memlimit,
        log_dir=None,
        log_prefix="",
        app_name="NA",
        root_permissions=settings.OUTPUT_DEFAULT_PERMISSION,
        user=getuser(),
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
        self.root_permissions = root_permissions
        self.user = user
        self.pipeline_config = None
        self.partition_isolated = None
        pipeline_config = settings.PIPELINE_CONFIG.get(self.app_name)
        if not pipeline_config:
            pipeline_config = settings.PIPELINE_CONFIG["NA"]
        self.resume_jobstore = resume_jobstore
        if resume_jobstore:
            self.job_store_dir = resume_jobstore
        else:
            self.job_store_dir = os.path.join(pipeline_config["JOB_STORE_ROOT"], self.job_id)
        self.partition = pipeline_config["PARTITION"]
        self.job_work_dir = os.path.join(pipeline_config["WORK_DIR_ROOT"], self.job_id)
        self.job_outputs_dir = root_dir
        self.job_tmp_dir = os.path.join(pipeline_config["TMP_DIR_ROOT"], self.job_id)
        self.batch_system = get_batch_system()

    def prepare_to_submit(self):
        """
        Prepare directories to submit job
        """
        pass

    def get_submit_command(self):
        """
        return: command_line, args, log_path, job_id, partition, env_map
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

    @userswitch
    def _prepare_directories(self):
        """
        Prepare execution directories
        :return:
        """

        if not os.path.exists(self.job_work_dir):
            os.mkdir(self.job_work_dir)
        if self.user:
            shutil.chown(self.job_work_dir, user=self.user)

        if os.path.exists(self.job_store_dir) and not self.resume_jobstore:

            shutil.rmtree(self.job_store_dir)

        if self.resume_jobstore:
            if not os.path.exists(self.resume_jobstore):
                raise Exception("The jobstore indicated to be resumed could not be found")

        if not os.path.exists(self.job_tmp_dir):
            os.mkdir(self.job_tmp_dir)

        if self.log_dir:
            if not os.path.exists(self.log_dir):
                mode_int = int(self.root_permissions, 8)
                os.makedirs(self.log_dir, mode=mode_int, exist_ok=True)

    def _job_args(self):
        pass

    def _command_line(self):
        pass
