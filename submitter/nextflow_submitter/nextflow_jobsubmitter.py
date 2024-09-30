import os
import shutil
import hashlib
from django.conf import settings
from submitter import JobSubmitter


class NextflowJobSubmitter(JobSubmitter):
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
        app_name="NA",
    ):
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
            ],
            "outputs": "file_name",
            "params": {
                "param_1": True,
                "param_2": "val2"
            }
        }
        :param root_dir:
        :param resume_jobstore:
        """
        JobSubmitter.__init__(self, job_id, app, inputs, walltime, tool_walltime, memlimit, log_dir, app_name)
        self.resume_jobstore = resume_jobstore
        dir_config = settings.PIPELINE_CONFIG.get(self.app_name)
        if not dir_config:
            dir_config = settings.PIPELINE_CONFIG["NA"]
        if resume_jobstore:
            self.job_store_dir = resume_jobstore
        else:
            self.job_store_dir = os.path.join(dir_config["JOB_STORE_ROOT"], self.job_id)
        self.job_work_dir = os.path.join(dir_config["WORK_DIR_ROOT"], self.job_id)
        self.job_outputs_dir = root_dir
        self.job_tmp_dir = os.path.join(dir_config["TMP_DIR_ROOT"], self.job_id)

    def prepare_to_submit(self):
        self._prepare_directories()
        self._dump_app_inputs()
        return self.job_store_dir, self.job_work_dir, self.job_outputs_dir, self.log_dir

    def get_submit_command(self):
        command_line = self._command_line()
        log_path = os.path.join(self.job_work_dir, "lsf.log")
        env = dict()
        env["NXF_OPTS"] = settings.NEXTFLOW_NXF_OPTS
        env["JAVA_HOME"] = settings.NEXTFLOW_JAVA_HOME
        env["PATH"] = env["JAVA_HOME"] + "bin:" + os.environ["PATH"]
        env["TMPDIR"] = self.job_tmp_dir
        env["NXF_CACHE_DIR"] = self.job_store_dir
        return command_line, self._leader_args(), log_path, self.job_id, env

    def _leader_args(self):
        args = self._walltime()
        args.extend(self._memlimit())
        return args

    def _walltime(self):
        return ["-W", str(self.walltime)] if self.walltime else []

    def _memlimit(self):
        return ["-M", self.memlimit] if self.memlimit else ["-M", "20"]

    def _sha1(self, path, buffersize=1024 * 1024):
        try:
            hasher = hashlib.sha1()
            with open(path, "rb") as f:
                contents = f.read(buffersize)
                while contents != b"":
                    hasher.update(contents)
                    contents = f.read(buffersize)
            return "sha1$%s" % hasher.hexdigest().lower()
        except Exception:
            return None

    def _nameext(self, path):
        return path.split(".")[-1]

    def _basename(self, path):
        return path.split("/")[-1]

    def _location(self, path):
        return "file://{path}".format(path=path)

    def _nameroot(self, path):
        return path.split("/")[-1].split(".")[0]

    def _checksum(self, path):
        return self._sha1(path)

    def _size(self, path):
        try:
            return os.path.getsize(path)
        except Exception:
            return 0

    def get_outputs(self):
        result = list()
        error_message = None
        try:
            with open(self.inputs["outputs"]) as f:
                files = f.readlines()
                for f in files:
                    path = f.strip()
                    location = self._location(path)
                    basename = self._basename(path)
                    checksum = self._checksum(path)
                    size = self._size(path)
                    nameroot = self._nameroot(path)
                    nameext = self._nameext(path)
                    file_obj = {
                        "location": location,
                        "basename": basename,
                        "checksum": checksum,
                        "size": size,
                        "nameroot": nameroot,
                        "nameext": nameext,
                        "class": "File",
                    }
                    result.append(file_obj)
        except FileNotFoundError:
            error_message = "Could not find %s" % self.inputs["outputs"]
        except Exception:
            error_message = "Could not parse %s" % self.inputs["outputs"]
        result_json = {"outputs": result}
        return result_json, error_message

    @property
    def app_location(self):
        return self.app.resolve(self.job_work_dir)

    @property
    def inputs_location(self):
        """
        returns inputs_map
        """
        inputs = self.inputs.get("inputs", [])
        input_map = dict()
        for i in inputs:
            input_map[i["name"]] = os.path.join(self.job_work_dir, i["name"])
        return input_map

    @property
    def config_location(self):
        return os.path.join(self.job_work_dir, "nf.config")

    def _dump_app_inputs(self):
        input_map = dict()
        inputs = self.inputs.get("inputs", [])
        for i in inputs:
            input_map[i["name"]] = self._dump_input(i["name"], i["content"], self.job_work_dir)
            if self.log_dir:
                input_map[i["name"]] = self._dump_input(i["name"], i["content"], self.log_dir)
        config = self.inputs.get("config")
        if config:
            self._dump_config(config)

    def _dump_input(self, name, content, root_dir):
        file_path = os.path.join(root_dir, name)
        with open(file_path, "w") as f:
            f.write(content)
        return file_path

    def _dump_config(self, config):
        file_path = self.config_location
        with open(file_path, "w") as f:
            f.write(config)
        return file_path

    def _prepare_directories(self):
        if not os.path.exists(self.job_work_dir):
            os.mkdir(self.job_work_dir)

        if os.path.exists(self.job_store_dir) and not self.resume_jobstore:
            shutil.rmtree(self.job_store_dir)

        if self.resume_jobstore:
            if not os.path.exists(self.resume_jobstore):
                raise Exception("The jobstore indicated to be resumed could not be found")

        if not os.path.exists(self.job_tmp_dir):
            os.mkdir(self.job_tmp_dir)

        if self.log_dir:
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir, exist_ok=True)

    def _command_line(self):
        profile = self.inputs["profile"]
        params = self.inputs.get("params", {})
        command_line = [
            settings.NEXTFLOW,
            "-log",
            "%s/nextflow.log" % self.job_work_dir,
            "run",
            self.app_location,
            "-profile",
            profile,
            "-w",
            self.job_store_dir,
            "--outDir",
            self.job_outputs_dir,
        ]
        for k, v in self.inputs_location.items():
            command_line.extend(["--%s" % k, v])
        if self.config_location:
            command_line.extend(["-c", self.config_location])
        if params:
            for k, v in params.items():
                if v is None:
                    continue
                elif isinstance(v, bool) and v:
                    command_line.extend([f"--{k}"])
                elif isinstance(v, bool):
                    if v:
                        command_line.extend([f"--{k}"])
                    else:
                        continue
                else:
                    command_line.extend([f"--{k}", v])
        if self.resume_jobstore:
            command_line.extend(["-resume"])
        return command_line
