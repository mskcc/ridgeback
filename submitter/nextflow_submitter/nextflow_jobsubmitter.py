import os
import csv
import glob
import shutil
import hashlib
from django.conf import settings
from submitter import JobSubmitter
from submitter.userswitcher import userswitch
from getpass import getuser

# Written into the work dir of every Nextflow job and attached with -c
PUBLISHED_MANIFEST_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "published-manifest.config")


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
        log_prefix="",
        app_name="NA",
        root_permissions=settings.OUTPUT_DEFAULT_PERMISSION,
        user=getuser(),
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
        JobSubmitter.__init__(
            self,
            job_id,
            app,
            inputs,
            root_dir,
            resume_jobstore,
            walltime,
            tool_walltime,
            memlimit,
            log_dir,
            log_prefix,
            app_name,
            root_permissions=root_permissions,
            user=user,
        )
        if self.app.nfcore_template:
            self.cli_output_name = "--outdir"
        else:
            self.cli_output_name = "--outDir"

    def prepare_to_submit(self):
        self._prepare_directories()
        self._dump_app_inputs()
        return self.job_store_dir, self.job_work_dir, self.job_outputs_dir, self.log_dir, self.log_prefix

    @userswitch
    def get_submit_command(self):
        command_line = self._command_line()
        log_path = os.path.join(self.job_work_dir, self.batch_system.logfileName)
        env = dict()
        env["NXF_OPTS"] = settings.NEXTFLOW_NXF_OPTS
        env["JAVA_HOME"] = settings.NEXTFLOW_JAVA_HOME
        env["PATH"] = env["JAVA_HOME"] + "bin:" + os.environ["PATH"]
        env["TMPDIR"] = self.job_tmp_dir
        env["NXF_CACHE_DIR"] = self.job_store_dir
        env["NXF_SLURM_PARTITION"] = self.partition
        # Read by published-manifest.config; covers apps that use --outDir instead of --outdir
        env["NXF_MANIFEST_DIR"] = self.job_outputs_dir
        return command_line, self._leader_args(), log_path, self.job_id, self.partition, env

    def _leader_args(self):
        args = self._walltime()
        args.extend(self._memlimit())
        return args

    def _walltime(self):
        return self.batch_system.set_walltime(None, self.walltime)

    def _memlimit(self):
        return self.batch_system.set_memlimit(self.memlimit, default="20")

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

    def _output_construct(self, path):
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
        return file_obj

    @userswitch
    def get_outputs(self):
        published_manifest = self._latest_published_manifest()
        if published_manifest:
            result, error_message = self._parse_published_manifest(published_manifest)
        else:
             try:
                with open(self.inputs["outputs"]) as f:
                    files = f.readlines()
                    for f in files:
                        path = f.strip()
                        file_obj = self._output_construct(path)
                        result.append(file_obj)
            except FileNotFoundError:
                error_message = "Could not find %s" % self.inputs["outputs"]
            except Exception:
                error_message = "Could not parse %s" % self.inputs["outputs"]
        result_json = {"outputs": result}
        return result_json, error_message

    def _latest_published_manifest(self):
        """
        Newest published_manifest_<runName>.tsv in the output directory (a resumed job leaves one per run)
        """
        manifests = glob.glob(os.path.join(self.job_outputs_dir, "published_manifest_*.tsv"))
        if not manifests:
            return None
        return max(manifests, key=os.path.getmtime)

    def _parse_published_manifest(self, manifest_path):
        result = list()
        try:
            with open(manifest_path, "r", newline="") as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    path = row["full_path"]
                    if path.startswith("file://"):
                        path = path[len("file://") :]
                    result.append(self._output_construct(path))
        except (KeyError, csv.Error, OSError):
            return [], "Could not parse %s" % manifest_path
        return result, None

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
            file_path = os.path.join(self.job_work_dir, i["name"])
            extension = i.get("extension", "")
            if extension:
                file_path = file_path + extension
            input_map[i["name"]] = file_path
        return input_map

    @property
    def config_location(self):
        return os.path.join(self.job_work_dir, "nf.config")

    @property
    def published_manifest_config_location(self):
        return os.path.join(self.job_work_dir, "published-manifest.config")

    @userswitch
    def _dump_app_inputs(self):
        input_map = dict()
        inputs = self.inputs.get("inputs", [])
        for i in inputs:
            input_map[i["name"]] = self._dump_input(i["name"], i["content"], i.get("extension", ""), self.job_work_dir)

        config = self.inputs.get("config")
        if config:
            self._dump_config(config)

        self._dump_published_manifest_config()

    def _dump_published_manifest_config(self):
        return shutil.copyfile(PUBLISHED_MANIFEST_CONFIG, self.published_manifest_config_location)

    def _dump_input(self, name, content, extension, root_dir):
        file_path = os.path.join(root_dir, name)
        if extension:
            file_path = file_path + extension
        with open(file_path, "w") as f:
            f.write(content)
        return file_path

    def _dump_config(self, config):
        file_path = self.config_location
        with open(file_path, "w") as f:
            f.write(config)
        return file_path

    def _command_line(self):
        profile = self.inputs["profile"]
        config = self.inputs.get("config")
        if not profile:
            profile = "''"
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
            self.job_work_dir,
            self.cli_output_name,
            self.job_outputs_dir,
        ]
        for k, v in self.inputs_location.items():
            command_line.extend(["--%s" % k, v])
        # Before the job config, so anything the job config sets takes precedence
        if os.path.exists(self.published_manifest_config_location):
            command_line.extend(["-c", self.published_manifest_config_location])
        if config:
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
