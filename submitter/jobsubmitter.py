import os
import git
import json
import shutil
from django.conf import settings
from lsf_client.lsf_client import LSFClient


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
        inputs_location = os.path.join(self.job_work_dir, 'input.json')
        with open(inputs_location, 'w') as f:
            json.dump(self.inputs, f)
        return app_location, inputs_location

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
        command_line = [settings.CWLTOIL, '--singularity', '--logFile', 'toil_log.log', '--batchSystem','lsf','--disable-user-provenance','--disable-host-provenance','--stats', '--debug', '--disableCaching', '--preserve-environment', 'PATH', 'TMPDIR', 'TOIL_LSF_ARGS', 'SINGULARITY_PULLDIR', 'SINGULARITY_CACHEDIR', 'PWD', '--defaultMemory', '8G', '--maxCores', '16', '--maxDisk', '128G', '--maxMemory', '256G', '--not-strict', '--realTimeLogging', '--jobStore', self.job_store_dir, '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir, '--outdir', self.job_outputs_dir, '--maxLocalJobs', '500']
        command_line.extend(self._dump_app_inputs())
        return command_line

