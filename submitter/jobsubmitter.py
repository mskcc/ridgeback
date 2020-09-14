import os
import git
import json
import shutil
from django.conf import settings
from batch_systems.lsf_client.lsf_client import LSFClient


class App(object):

    def factory(app):
        if app.get('github'):
            repo = app['github']['repository']
            entrypoint = app['github']['entrypoint']
            version = app['github'].get('version', 'master')
            return GithubApp(repo, entrypoint, version)
        elif app.get('base64'):
            raise Exception('Base64 app not implemented yet')
        elif app.get('app'):
            raise Exception('Json app not implemented yet')
        else:
            raise Exception('Invalid app reference type')
    factory = staticmethod(factory)

    def resolve(self, location):
        pass

    def _cleanup(self, location):
        shutil.rmtree(location)


class GithubApp(App):
    type = "github"

    def __init__(self, github, entrypoint, version='master'):
        super().__init__()
        self.github = github
        self.entrypoint = entrypoint
        self.version = version

    def resolve(self, location):
        git.Git(location).clone(self.github, '--branch', self.version, '--recurse-submodules')
        dirname = self._extract_dirname_from_github_link()
        return os.path.join(location, dirname, self.entrypoint)

    def _extract_dirname_from_github_link(self):
        return self.github.rsplit('/', 2)[1] if self.github.endswith('/') else self.github.rsplit('/', 1)[1]


class JobSubmitter(object):

    def __init__(self, job_id, app, inputs, root_dir, resume_jobstore):
        self.job_id = job_id
        self.app = App.factory(app)
        self.inputs = inputs
        self.lsf_client = LSFClient()
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
        job_args = self._job_args()
        log_path = os.path.join(self.job_work_dir, 'lsf.log')
        external_id = self.lsf_client.submit(command_line, job_args, log_path)
        return external_id, self.job_store_dir, self.job_work_dir, self.job_outputs_dir

    def status(self, external_id):
        return self.lsf_client.status(external_id)

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
        if "access" in self.app.github.lower():
            return ["-W", "3600"]
        elif settings.LSF_WALLTIME:
            return ['-W', settings.LSF_WALLTIME]
        return []


    def _command_line(self):
        if "access" in self.app.github.lower():
            """
            Start ACCESS-specific code
            In addition to different arguments and required bins, ACCESS requires a specific version of Toil that prevents the following PATH from recursively appending itself on every job, causing "OSExit Too many argument".
            """
            path = "PATH=/juno/work/ci/access-pipelines/env/conda/envs/ACCESS/bin:{}".format(os.environ.get('PATH'))
            command_line = [path, 'toil-cwl-runner', '--no-container', '--logFile', 'toil_log.log', '--batchSystem','lsf','--disable-user-provenance','--logLevel', 'DEBUG','--disable-host-provenance','--stats', '--debug', '--cleanWorkDir', 'always', '--disableCaching', '--disableChaining', '--preserve-environment', 'PATH', 'TMPDIR', 'TOIL_LSF_ARGS', 'SINGULARITY_PULLDIR', 'SINGULARITY_CACHEDIR', 'PWD', '_JAVA_OPTIONS', 'PYTHONPATH', 'TEMP', '--maxCores', '16', '--realTimeLogging', '--jobStore', self.job_store_dir, '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir, '--outdir', self.job_outputs_dir]
            """
            End ACCESS-specific code
            """
        else:
            command_line = [settings.CWLTOIL, '--singularity', '--logFile', 'toil_log.log', '--batchSystem','lsf','--disable-user-provenance','--disable-host-provenance','--stats', '--debug', '--disableCaching', '--preserve-environment', 'PATH', 'TMPDIR', 'TOIL_LSF_ARGS', 'SINGULARITY_PULLDIR', 'SINGULARITY_CACHEDIR', 'PWD', '--defaultMemory', '8G', '--maxCores', '16', '--maxDisk', '128G', '--maxMemory', '256G', '--not-strict', '--realTimeLogging', '--jobStore', self.job_store_dir, '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir, '--outdir', self.job_outputs_dir, '--maxLocalJobs', '500']


        app_location, inputs_location = self._dump_app_inputs()
        if self.resume_jobstore:
            command_line.extend(['--restart',app_location])
        else:
            command_line.extend([app_location, inputs_location])
        return command_line

