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
            executor = app['github'].get('executor', 'toil')
            return GithubApp(github = repo, entrypoint = entrypoint, version = version, executor = executor)
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

    def __init__(self, github, entrypoint, executor = 'toil', version='master'):
        super(App, self).__init__()
        self.github = github
        self.entrypoint = entrypoint
        self.version = version
        self.executor = executor

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
        executor = self.app.executor
        if executor == 'nextflow':
            # generate a custom 'run.sh' script that will set up the environment
            # in order to run the Nextflow pipeline
            app_location, inputs_location = self._dump_app_inputs()
            app_dir = os.path.dirname(app_location)
            # the path returned as the "app_location" has '.git' at the end for some reason, need to remove that and fix the path
            if os.path.realpath(app_dir).endswith('.git'):
                app_dir = os.path.realpath(app_dir).rsplit('.git')[0]
                app_location = os.path.join(app_dir, os.path.basename(app_location))
            run_script_path = os.path.join(self.job_work_dir, 'run.sh')
            NXF_WORK = os.path.join(self.job_work_dir, 'work')
            NXF_TEMP = os.path.join(NXF_WORK, 'tmp')
            NXF_HOME = os.path.join(self.job_work_dir, '.nextflow')
            NXF_LOG = os.path.join(self.job_work_dir, 'nextflow.log')
            NXF_OUTPUT = os.path.join(self.job_work_dir, 'output')
            # write out the custom script
            with open(run_script_path, 'w') as fout:
                print("""
#!/bin/bash
export PATH={NXF_PATH}:$PATH
export NXF_ANSI_LOG=false
export NXF_HOME={NXF_HOME}
export NXF_WORK={NXF_WORK}
export NXF_TEMP={NXF_TEMP}
export NXF_EXECUTOR=lsf

nextflow -log {NXF_LOG} run {app_location} -params-file {inputs_location} --outputDir {NXF_OUTPUT}
""".format(
NXF_PATH = settings.NXF_PATH,
NXF_HOME = NXF_HOME,
NXF_WORK = NXF_WORK,
NXF_TEMP = NXF_TEMP,
app_location = app_location,
inputs_location = inputs_location,
NXF_LOG = NXF_LOG,
NXF_OUTPUT = NXF_OUTPUT
), file = fout)
            command_line = ['bash', run_script_path]
            # print("command_line: {}".format(command_line), file = open(os.environ['DJANGO_TEST_LOGFILE'], "a"))
        else:
            command_line = [settings.CWLTOIL, '--singularity', '--logFile', 'toil_log.log', '--batchSystem', 'lsf', '--stats', '--debug', '--disableCaching', '--preserve-environment', 'PATH', 'TMPDIR', 'TOIL_LSF_ARGS', 'SINGULARITY_PULLDIR', 'PWD', '--defaultMemory', '8G', '--maxCores', '16', '--maxDisk', '128G', '--maxMemory', '256G', '--not-strict', '--realTimeLogging', '--jobStore', self.job_store_dir, '--tmpdir-prefix', self.job_tmp_dir, '--workDir', self.job_work_dir, '--outdir', self.job_outputs_dir, '--maxLocalJobs', '500']
            command_line.extend(self._dump_app_inputs())
        return command_line
