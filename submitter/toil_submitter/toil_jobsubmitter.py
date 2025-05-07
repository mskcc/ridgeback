import os
import json
import shutil
import copy
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from orchestrator.models import Status
from submitter import JobSubmitter
from .toil_track_utils import ToilTrack, ToolStatus
from batch_systems.batch_system import get_batch_system


def translate_toil_to_model_status(status):
    """
    Translate status objects from Toil to Ridgeback
    """
    translation_dict = {
        ToolStatus.PENDING: Status.PENDING,
        ToolStatus.RUNNING: Status.RUNNING,
        ToolStatus.COMPLETED: Status.COMPLETED,
        ToolStatus.FAILED: Status.FAILED,
        ToolStatus.UNKNOWN: Status.UNKNOWN,
    }
    return translation_dict[status]


class ToilJobSubmitter(JobSubmitter):
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
    ):
        JobSubmitter.__init__(
            self,
            job_id,
            app,
            inputs,
            walltime,
            tool_walltime,
            memlimit,
            log_dir,
            log_prefix,
            app_name,
            root_permissions,
        )
        dir_config = settings.PIPELINE_CONFIG.get(self.app_name)
        if not dir_config:
            dir_config = settings.PIPELINE_CONFIG["NA"]
        self.resume_jobstore = resume_jobstore
        if resume_jobstore:
            self.job_store_dir = resume_jobstore
        else:
            self.job_store_dir = os.path.join(dir_config["JOB_STORE_ROOT"], self.job_id)
        self.job_work_dir = os.path.join(dir_config["WORK_DIR_ROOT"], self.job_id)
        self.job_outputs_dir = root_dir
        self.job_tmp_dir = os.path.join(dir_config["TMP_DIR_ROOT"], self.job_id)
        self.batch_system = get_batch_system()
        self.batch_system_args_env = None
        if settings.BATCH_SYSTEM == "LSF":
            self.batch_system_args_env = "TOIL_LSF_ARGS"
        elif settings.BATCH_SYSTEM == "SLURM":
            self.batch_system_args_env = "TOIL_SLURM_ARGS"

    def prepare_to_submit(self):
        self._prepare_directories()
        self._dump_app_inputs()
        self.app.resolve(self.job_work_dir)
        return self.job_store_dir, self.job_work_dir, self.job_outputs_dir, self.log_dir, self.log_prefix

    def get_submit_command(self):
        command_line = self._command_line()
        log_path = os.path.join(self.job_work_dir, self.batch_system.logfileName)
        env = dict()
        toil_batch_system_args = "%s %s %s" % (
            " ".join(self._service_queue()),
            " ".join(self._job_group()),
            " ".join(self._tool_args()),
        )
        env["JAVA_HOME"] = None
        env[self.batch_system_args_env] = toil_batch_system_args.strip()
        return command_line, self._leader_args(), log_path, self.job_id, env

    def get_commandline_status(self, cache):
        """
        Get the status of the command line tools in the TOIL job
        """
        restart = False
        track_cache = {}
        if self.resume_jobstore:
            restart = True
        if cache:
            track_cache = json.loads(cache)
        cache_keys = set(["jobs_path", "jobs", "work_log_to_job_id"])
        jobs_path = {}
        jobs = {}
        work_log_to_job_id = {}
        if cache_keys.issubset(track_cache.keys()):
            jobs_path = track_cache["jobs_path"]
            jobs = track_cache["jobs"]
            work_log_to_job_id = track_cache["work_log_to_job_id"]
        toil_track_obj = ToilTrack([self.job_store_dir, self.job_work_dir], restart=restart)
        toil_track_obj.jobs_path = jobs_path
        toil_track_obj.jobs = jobs
        toil_track_obj.work_log_to_job_id = work_log_to_job_id
        toil_track_obj.check_status()
        jobs_path = toil_track_obj.jobs_path
        jobs = toil_track_obj.jobs
        work_log_to_job_id = toil_track_obj.work_log_to_job_id
        new_cache = {
            "jobs_path": jobs_path,
            "jobs": jobs,
            "work_log_to_job_id": work_log_to_job_id,
        }
        new_track_cache = json.dumps(new_cache, sort_keys=True, indent=1, cls=DjangoJSONEncoder)
        formatted_jobs = copy.deepcopy(jobs)
        for job_id, single_job in formatted_jobs.items():
            single_job["status"] = translate_toil_to_model_status(single_job["status"])
            single_job["details"] = {
                "cores_req": single_job["cores_req"],
                "cpu_usage": single_job["cpu_usage"],
                "job_stream": single_job["job_stream"],
                "last_modified": single_job["last_modified"],
                "log_path": single_job["log_path"],
                "mem_usage": single_job["mem_usage"],
                "memory_req": single_job["memory_req"],
            }
        job_safe = json.dumps(formatted_jobs, default=str)
        track_cache_safe = json.dumps(new_track_cache, default=str)

        return job_safe, track_cache_safe

    def get_outputs(self):
        error_message = None
        result_json = None
        log_path = os.path.join(self.job_work_dir, self.batch_system.logfileName)
        try:
            with open(log_path, "r") as f:
                data = f.readlines()
                data = "".join(data)
                substring = data.split("\n{")[1]
                if "-----------" in substring:
                    result = ("{" + substring).split("-----------")[0]
                else:
                    result_segment = substring.split("}[")[0]
                    result = "{" + result_segment + "}"
                result_json = json.loads(result)
        except (IndexError, ValueError):
            error_message = "Could not parse json from %s" % log_path
        except FileNotFoundError:
            error_message = "Could not find %s" % log_path

        if self.log_dir:
            output_log_name = f"{self.log_prefix}.output.json" if self.log_prefix else "output.json"
            output_log_location = os.path.join(self.log_dir, output_log_name)
            with open(output_log_location, "w") as f:
                json.dump(result_json, f)

        return result_json, error_message

    @property
    def app_location(self):
        return self.app.get_app_path(self.job_work_dir)

    @property
    def inputs_location(self):
        return os.path.join(self.job_work_dir, "input.json")

    def _dump_app_inputs(self):
        inputs_location = self.inputs_location
        with open(inputs_location, "w") as f:
            json.dump(self.inputs, f)
        if self.log_dir:
            inputs_log_name = f"{self.log_prefix}.input.json" if self.log_prefix else "input.json"
            inputs_log_location = os.path.join(self.log_dir, inputs_log_name)
            with open(inputs_log_location, "w") as f:
                json.dump(self.inputs, f)

    def _prepare_directories(self):
        if not os.path.exists(self.job_work_dir):
            os.mkdir(self.job_work_dir)

        if self.log_dir:
            if not os.path.exists(self.log_dir):
                mode_int = int(self.root_permissions, 8)
                os.makedirs(self.log_dir, mode=mode_int, exist_ok=True)

        if os.path.exists(self.job_store_dir) and not self.resume_jobstore:
            shutil.rmtree(self.job_store_dir)

        if self.resume_jobstore:
            if not os.path.exists(self.resume_jobstore):
                raise Exception("The job_store indicated to be resumed could not be found")

        if not os.path.exists(self.job_tmp_dir):
            os.mkdir(self.job_tmp_dir)

    def _leader_args(self):
        args = self._walltime()
        args.extend(self._memlimit())
        return args

    def _tool_args(self):
        args = []
        if self.tool_walltime:
            expected_limit = max(1, int(self.tool_walltime / 3))
            hard_limit = self.tool_walltime
            args = self.batch_system.set_walltime(expected_limit, hard_limit)
        return args

    def _service_queue(self):
        return self.batch_system.set_service_queue()

    def _walltime(self):
        return self.batch_system.set_walltime(None, self.walltime)

    def _memlimit(self):
        return self.batch_system.set_memlimit(self.memlimit)

    def _job_group(self):
        return self.batch_system.set_group(self.job_id)

    def _command_line(self):
        single_machine_mode_workflows = ["nucleo_qc", "argos-qc"]
        single_machine = any([w in self.app.github.lower() for w in single_machine_mode_workflows])
        if settings.ACCESS_LEGACY_APP in self.app.github.lower():
            """
            Start ACCESS-specific code
            """
            access_path = "PATH=/home/accessbot/miniconda3/envs/ACCESS_cmplx_geno_test/bin:{}"
            path = access_path.format(os.environ.get("PATH"))
            command_line = [
                path,
                "toil-cwl-runner",
                "--no-container",
                "--logFile",
                "toil_log.log",
                "--batchSystem",
                self.batch_system.name,
                "--logLevel",
                "DEBUG",
                "--stats",
                "--cleanWorkDir",
                "onSuccess",
                "--disableCaching",
                "--defaultMemory",
                "10G",
                "--retryCount",
                "2",
                "--disableChaining",
                "--preserve-environment",
                "PATH",
                "TMPDIR",
                self.batch_system_args_env,
                "CWL_SINGULARITY_CACHE",
                "PWD",
                "_JAVA_OPTIONS",
                "PYTHONPATH",
                "TEMP",
                "--jobStore",
                self.job_store_dir,
                "--tmpdir-prefix",
                self.job_tmp_dir,
                "--workDir",
                self.job_work_dir,
                "--outdir",
                self.job_outputs_dir,
            ]
            """
            End ACCESS-specific code
            """
        elif single_machine:
            command_line = [
                settings.CWLTOIL,
                "--singularity",
                "--coalesceStatusCalls",
                "--logFile",
                "toil_log.log",
                "--batchSystem",
                "single_machine",
                "--statePollingWait",
                str(settings.TOIL_STATE_POLLING_WAIT),
                "--disable-user-provenance",
                "--disable-host-provenance",
                "--cleanWorkDir",
                "onSuccess",
                "--disableProgress",
                "--doubleMem",
                "True",
                "--disableCaching",
                "--preserve-environment",
                "PATH",
                "TMPDIR",
                "CWL_SINGULARITY_CACHE",
                "SINGULARITYENV_LC_ALL",
                "PWD",
                "--defaultMemory",
                settings.TOIL_DEFAULT_MEMORY,
                "--maxCores",
                settings.TOIL_MAX_CORES,
                "--maxDisk",
                "128G",
                "--maxMemory",
                "256G",
                "--not-strict",
                "--runCwlInternalJobsOnWorkers",
                "--realTimeLogging",
                "True",
                "--jobStore",
                self.job_store_dir,
                "--tmpdir-prefix",
                self.job_tmp_dir,
                "--workDir",
                self.job_work_dir,
                "--outdir",
                self.job_outputs_dir,
                "--maxLocalJobs",
                "500",
                "--no-prepull",
                "--reference-inputs",
            ]
        else:
            command_line = [
                settings.CWLTOIL,
                "--singularity",
                "--coalesceStatusCalls",
                "--logFile",
                "toil_log.log",
                "--batchSystem",
                self.batch_system.name,
                "--statePollingWait",
                str(settings.TOIL_STATE_POLLING_WAIT),
                "--disable-user-provenance",
                "--disable-host-provenance",
                "--cleanWorkDir",
                "onSuccess",
                "--disableProgress",
                "--doubleMem",
                "True",
                "--disableCaching",
                "--preserve-environment",
                "PATH",
                "TMPDIR",
                self.batch_system_args_env,
                "CWL_SINGULARITY_CACHE",
                "SINGULARITYENV_LC_ALL",
                "PWD",
                "--defaultMemory",
                settings.TOIL_DEFAULT_MEMORY,
                "--maxCores",
                settings.TOIL_MAX_CORES,
                "--maxDisk",
                "128G",
                "--maxMemory",
                "256G",
                "--not-strict",
                "--runCwlInternalJobsOnWorkers",
                "--realTimeLogging",
                "True",
                "--jobStore",
                self.job_store_dir,
                "--tmpdir-prefix",
                self.job_tmp_dir,
                "--workDir",
                self.job_work_dir,
                "--outdir",
                self.job_outputs_dir,
                "--maxLocalJobs",
                "500",
                "--no-prepull",
                "--reference-inputs",
            ]
        if self.resume_jobstore:
            command_line.extend(["--restart", self.app_location])
        else:
            command_line.extend([self.app_location, self.inputs_location])
        return command_line
