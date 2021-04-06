import os
import json
import shutil
from django.conf import settings
from submitter import JobSubmitter


class ToilJobSubmitter(JobSubmitter):

    def __init__(self, job_id, app, inputs, root_dir, resume_jobstore, walltime, memlimit):
        JobSubmitter.__init__(self, app, inputs, walltime, memlimit)
        self.job_id = job_id
        self.resume_jobstore = resume_jobstore
        if resume_jobstore:
            self.job_store_dir = resume_jobstore
        else:
            self.job_store_dir = os.path.join(settings.TOIL_JOB_STORE_ROOT, self.job_id)
        self.job_work_dir = os.path.join(settings.TOIL_WORK_DIR_ROOT, self.job_id)
        self.job_outputs_dir = root_dir
        self.job_tmp_dir = os.path.join(settings.TOIL_TMP_DIR_ROOT, self.job_id)

    def submit(self):
        self._prepare_directories()
        command_line = self._command_line()
        log_path = os.path.join(self.job_work_dir, 'lsf.log')
        env = dict()
        toil_lsf_args = '-sla %s %s' % (settings.LSF_SLA, " ".join(self._job_args()))
        env['TOIL_LSF_ARGS'] = toil_lsf_args
        external_id = self.lsf_client.submit(command_line, self._job_args(), log_path, env)
        return external_id, self.job_store_dir, self.job_work_dir, self.job_outputs_dir

    def get_outputs(self):
        error_message = None
        result_json = None
        lsf_log_path = os.path.join(self.job_work_dir, 'lsf.log')
        try:
            with open(lsf_log_path, 'r') as f:
                data = f.readlines()
                data = ''.join(data)
                substring = data.split('\n{')[1]
                result = ('{' + substring).split('-----------')[0]
                result_json = json.loads(result)
        except (IndexError, ValueError):
            error_message = 'Could not parse json from %s' % lsf_log_path
        except FileNotFoundError:
            error_message = 'Could not find %s' % lsf_log_path

        return result_json, error_message

    def _dump_app_inputs(self):
        app_location = self.app.resolve(self.job_work_dir)
        inputs_location = os.path.join(self.job_work_dir, 'input.json')
        with open(inputs_location, 'w') as f:
            json.dump(self.inputs, f)
        return app_location, inputs_location

    def _prepare_directories(self):
        if not os.path.exists(self.job_work_dir):
            os.mkdir(self.job_work_dir)

        if os.path.exists(self.job_store_dir) and not self.resume_jobstore:
            shutil.rmtree(self.job_store_dir)

        if self.resume_jobstore:
            if not os.path.exists(self.resume_jobstore):
                raise Exception('The jobstore indicated to be resumed could not be found')

        if not os.path.exists(self.job_tmp_dir):
            os.mkdir(self.job_tmp_dir)

    def _job_args(self):
        args = self._walltime()
        args.extend(self._memlimit())
        return args

    def _walltime(self):
        return ['-W', str(self.walltime)] if self.walltime else []

    def _memlimit(self):
        return ['-M', self.memlimit] if self.memlimit else []

    def _command_line(self):
        if "access" in self.app.github.lower():
            """
            Start ACCESS-specific code
            """
            path = "PATH=/juno/home/accessbot/miniconda3/envs/ACCESS_2.0.0/bin:{}".format(os.environ.get('PATH'))
            command_line = [path, 'toil-cwl-runner', '--no-container', '--logFile', 'toil_log.log',
                            '--batchSystem', 'lsf', '--logLevel', 'DEBUG', '--stats', '--cleanWorkDir',
                            'onSuccess', '--disableCaching', '--defaultMemory', '10G', '--retryCount', '2',
                            '--disableChaining', '--preserve-environment', 'PATH', 'TMPDIR',
                            'TOIL_LSF_ARGS', 'SINGULARITY_PULLDIR', 'SINGULARITY_CACHEDIR', 'PWD',
                            '_JAVA_OPTIONS', 'PYTHONPATH', 'TEMP', '--jobStore', self.job_store_dir,
                            '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir,
                            '--outdir', self.job_outputs_dir]
            """
            End ACCESS-specific code
            """
        else:
            command_line = [settings.CWLTOIL, '--singularity', '--coalesceStatusCalls', '--logFile', 'toil_log.log',
                            '--batchSystem', 'lsf', '--disable-user-provenance', '--disable-host-provenance', '--stats',
                            '--debug', '--disableCaching', '--preserve-environment', 'PATH', 'TMPDIR', 'TOIL_LSF_ARGS',
                            'SINGULARITY_PULLDIR', 'SINGULARITY_CACHEDIR', 'PWD', 'SINGULARITY_DOCKER_USERNAME',
                            'SINGULARITY_DOCKER_PASSWORD', '--defaultMemory', '8G', '--maxCores', '16', '--maxDisk',
                            '128G', '--maxMemory', '256G', '--not-strict', '--realTimeLogging', '--jobStore',
                            self.job_store_dir, '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir,
                            '--outdir', self.job_outputs_dir, '--maxLocalJobs', '500']

        app_location, inputs_location = self._dump_app_inputs()
        if self.resume_jobstore:
            command_line.extend(['--restart', app_location])
        else:
            command_line.extend([app_location, inputs_location])
        return command_line
