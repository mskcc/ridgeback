import os
import git
import json
import shutil
from django.conf import settings
from lsf_client.lsf_client import LSFClient


class App(object):

    def factory(app):
        if app.get('github'):
            repo = app['github']['repository'].replace(".git", "")
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
        super(App, self).__init__()
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

    def __init__(self, job_id, app, inputs, root_dir):
        self.job_id = job_id
        self.app = App.factory(app)
        self.inputs = inputs
        self.lsf_client = LSFClient()
        self.job_store_dir = os.path.join(settings.TOIL_JOB_STORE_ROOT, self.job_id)
        self.job_work_dir = os.path.join(settings.TOIL_WORK_DIR_ROOT, self.job_id)
        self.job_outputs_dir = os.path.join(root_dir, 'outputs')
        self.job_tmp_dir = os.path.join(settings.TOIL_TMP_DIR_ROOT, self.job_id)

    def submit(self):
        self._prepare_directories()
        command_line = self._command_line()

        envars = os.environ.get('PATH')
        if "PATH" not in command_line[0]:
            print("Adding ENVAR")
            path = "/work/access/testing/users/fraihaa/ridgeback/conda/envs/toil-msk-3.21.1-MSK-rc1/bin:/conda/bin:/home/accessbot/miniconda3/envs/ACCESS_1.3.26/bin/:{}".format(envars)
            command_line.insert(0, "PATH={}".format(path))

        print("Running Submit: {} {} {} {}".format(" ".join(command_line), os.path.join(self.job_work_dir, 'lsf.log'), self.job_store_dir, self.job_work_dir))
        return self.lsf_client.submit(command_line, os.path.join(self.job_work_dir, 'lsf.log')), self.job_store_dir, self.job_work_dir

    def status(self, external_id):
        return self.lsf_client.status(external_id)

    def get_outputs(self):
        with open(os.path.join(self.job_work_dir, 'lsf.log'), 'r') as f:
            data = f.readlines()
            data = ''.join(data)
            substring = data.split('\n{')[1]
            result = ('{' + substring).split('-----------')[0]
            result_json = json.loads(result)
            return result_json

    def _dump_app_inputs(self):
        app_location = self.app.resolve(self.job_work_dir)
        inputs_location = os.path.join(self.job_work_dir, 'inputs.json')
        print("==========================")
        print(inputs_location, self.inputs)
        with open(inputs_location, 'w') as f:
            json.dump(self.inputs, f)
        return app_location, self.inputs

    def _prepare_directories(self):
        if not os.path.exists(self.job_work_dir):
            os.mkdir(self.job_work_dir)

        if os.path.exists(self.job_store_dir):
            # delete job-store directory for now so that execution can work;
            # TODO: Implement resume at a later time
            shutil.rmtree(self.job_store_dir)
            os.mkdir(self.job_store_dir)

        if not os.path.exists(self.job_tmp_dir):
            os.mkdir(self.job_tmp_dir)

    def _command_line(self):
        command_line = ['toil-cwl-runner', '--logFile', 'toil_log.log', '--batchSystem','lsf','--disable-user-provenance','--logLevel', 'DEBUG','--disable-host-provenance','--stats', '--debug', '--cleanWorkDir', 'always', '--disableCaching', '--preserve-environment', 'PATH', 'TMPDIR', 'TOIL_LSF_ARGS', 'SINGULARITY_PULLDIR', 'SINGULARITY_CACHEDIR', 'PWD', '_JAVA_OPTIONS', 'PYTHONPATH', 'TEMP', '--defaultMemory', '10G', '--realTimeLogging', '--jobStore', self.job_store_dir, '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir, '--outdir', self.job_outputs_dir]
        #command_line = [settings.CWLTOIL, '--singularity', '--logFile', 'toil_log.log', '--batchSystem','lsf','--disable-user-provenance','--logLevel', 'DEBUG','--disable-host-provenance','--stats', '--debug', '--cleanWorkDir', 'always', '--disableCaching', '--preserve-environment', 'PATH', 'TMPDIR', 'TOIL_LSF_ARGS', 'SINGULARITY_PULLDIR', 'SINGULARITY_CACHEDIR', 'PWD', '_JAVA_OPTIONS', 'PYTHONPATH', 'TEMP', '--defaultMemory', '10G', '--maxCores', '16', '--defaultDisk', '10G', '--maxDisk', '128G', '--maxMemory', '256G', '--not-strict', '--realTimeLogging', '--jobStore', self.job_store_dir, '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir, '--outdir', self.job_outputs_dir, '--maxLocalJobs', '500']
        # command_line = ['PATH=/work/access/testing/users/fraihaa/ridgeback/conda/envs/toil-msk-3.21.1-MSK-rc1/bin:/conda/bin:/home/accessbot/miniconda3/envs/ACCESS_1.3.26/bin/:$PATH', 'toil-cwl-runner', '--logFile', 'toil_log.log', '--batchSystem','lsf', '--defaultDisk', '10G', '--defaultMem', '10G', '--stats', '--logLevel', 'DEBUG', '--disableCaching', '--debug', '--cleanWorkDir', 'never', '--preserve-environment', 'PATH', 'TMPDIR', 'TMP_DIR', '_JAVA_OPTIONS', 'TMP', 'TEMP', 'PYTHONPATH', 'TOIL_LSF_ARGS', '--writeLogs', self.job_work_dir, '--jobStore', self.job_store_dir, '--workDir', self.job_work_dir, '--outdir', self.job_outputs_dir]
        command_line.extend(self._dump_app_inputs())
        return command_line

