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
        if "access" in self.app.github.lower():
            return ["-W", "3600", "-M", "10"]
        elif settings.LSF_WALLTIME:
            return ['-W', settings.LSF_WALLTIME]
        return []


    def _command_line(self):
        """
        :return: CommandLine for submitting pipeline
        """
        if "access" in self.app.github.lower():
            """
            Start ACCESS-specific code
            """
            path = "PATH=/juno/home/accessbot/miniconda3/envs/ACCESS_2.0.0/bin:{}".format(os.environ.get('PATH'))
            command_line = [path, 'toil-cwl-runner', '--no-container', '--logFile', 'toil_log.log',
                            '--batchSystem','lsf','--logLevel', 'DEBUG','--stats', '--cleanWorkDir',
                            'onSuccess', '--disableCaching', '--defaultMemory', '10G',
                            '--disableChaining', '--preserve-environment', 'PATH', 'TMPDIR',
                            'TOIL_LSF_ARGS', 'SINGULARITY_PULLDIR', 'SINGULARITY_CACHEDIR', 'PWD',
                            '_JAVA_OPTIONS', 'PYTHONPATH', 'TEMP', '--jobStore', self.job_store_dir,
                            '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir,
                            '--outdir', self.job_outputs_dir]
            """
            End ACCESS-specific code
            """
        else:
            command_line = [settings.CWLTOIL, '--singularity', '--logFile', 'toil_log.log', '--batchSystem','lsf','--disable-user-provenance','--disable-host-provenance','--stats', '--debug', '--disableCaching', '--preserve-environment', 'PATH', 'TMPDIR', 'TOIL_LSF_ARGS', 'SINGULARITY_PULLDIR', 'SINGULARITY_CACHEDIR', 'PWD','SINGULARITY_DOCKER_USERNAME','SINGULARITY_DOCKER_PASSWORD', '--defaultMemory', '8G', '--maxCores', '16', '--maxDisk', '128G', '--maxMemory', '256G', '--not-strict', '--realTimeLogging', '--jobStore', self.job_store_dir, '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir, '--outdir', self.job_outputs_dir, '--maxLocalJobs', '500']


        app_location, inputs_location = self._dump_app_inputs()
        if self.resume_jobstore:
            command_line.extend(['--restart',app_location])
        else:
            command_line.extend([app_location, inputs_location])
        return command_line

