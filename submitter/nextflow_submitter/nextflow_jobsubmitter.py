import os
import json
import shutil
from django.conf import settings
from submitter import JobSubmitter


class NextflowJobSubmitter(JobSubmitter):

    def __init__(self, job_id, app, inputs, root_dir, resume_jobstore):
        """
        :param job_id:
        :param app: github.url
        :param inputs: {
            "config": "content",
            "profile": "profile_name",
            "inputs": [
                {
                "name": "input_name",
                "content": "content"
                },
                {
                "name": "input_name",
                "content": "content"
                }
            ]
        }
        :param root_dir:
        :param resume_jobstore:
        """
        JobSubmitter.__init__(self, app, inputs)
        self.job_id = job_id
        self.resume_jobstore = resume_jobstore
        if resume_jobstore:
            self.job_store_dir = resume_jobstore
        else:
            self.job_store_dir = os.path.join(settings.NEXTFLOW_JOB_STORE_ROOT, self.job_id)
        self.job_work_dir = os.path.join(settings.NEXTFLOW_WORK_DIR_ROOT, self.job_id)
        self.job_outputs_dir = root_dir
        self.job_tmp_dir = os.path.join(settings.NEXTFLOW_TMP_DIR_ROOT, self.job_id)

    def submit(self):
        self._prepare_directories()
        command_line = self._command_line()
        log_path = os.path.join(self.job_work_dir, 'lsf.log')
        external_id = self.lsf_client.submit(command_line, log_path)
        return external_id, self.job_store_dir, self.job_work_dir, self.job_outputs_dir

    def get_outputs(self):
        with open(os.path.join(self.job_work_dir, 'lsf.log'), 'r') as f:
            return {}

    def _dump_app_inputs(self):
        app_location = self.app.resolve(self.job_work_dir)
        profile = self.inputs.get('profile')
        input_map = dict()
        inputs = self.inputs.get('inputs', [])
        for i in inputs:
            input_map[i['name']] = self._dump_input(i['name'], i['content'])
        config = self.inputs.get('config')
        if config:
            self._dump_config(config)
        return app_location, input_map, config, profile

    def _dump_input(self, name, content):
        file_path = os.path.join(self.job_work_dir, name)
        with open(file_path, 'w') as f:
            f.write(content)
        return file_path

    def _dump_config(self, config):
        file_path = os.path.join(self.job_work_dir, 'nf.config')
        with open(file_path, 'w') as f:
            f.write(config)

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

    def _command_line(self):
        app_location, input_map, config, profile = self._dump_app_inputs()
        command_line = [settings.NEXTFLOW, 'run', app_location, '-profile', profile, '-w', self.job_store_dir, '--outDir', self.job_outputs_dir]
        for k, v in input_map.items():
            command_line.extend(["--%s" % k, v])
        if config:
            command_line.extend(['-c', config])
        if self.resume_jobstore:
            command_line.extend(['-resume'])
        return command_line
