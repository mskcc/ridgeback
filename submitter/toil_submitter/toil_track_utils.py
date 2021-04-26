"""
Track commandline status of toil jobs
"""
#!/usr/bin/env python3
import os
import sys
import logging
import pickle
import re
import time
import copy
import json
import glob
from enum import IntEnum
from datetime import datetime
from json.decoder import JSONDecodeError
from tenacity import retry, wait_fixed, wait_random, stop_after_attempt, after_log
from toil.jobStores.fileJobStore import FileJobStore
from toil.toilState import ToilState as toil_state
from toil.cwl.cwltoil import CWL_INTERNAL_JOBS
from toil.jobStores.abstractJobStore import NoSuchJobException, NoSuchJobStoreException


logger = logging.getLogger(__name__)
WAITTIME = 10
JITTER = 5
ATTEMPTS = 5


def _get_method(file_job_store, method):
    """
    Helper function to return method if it exists and is callable
    """
    if hasattr(file_job_store, method):
        method_function = getattr(file_job_store, method)
        if callable(method_function):
            return method_function
    return None


def _check_job_method(file_job_store):
    """
    TOIL Adapter function to check for job existence using method under diffrent
    names from TOIL 5.4 and 3.21
    """
    check_function = _get_method(file_job_store, "_checkJobStoreIdExists")

    if check_function:
        return check_function

    fallback_function = _get_method(file_job_store, "_checkJobStoreId")

    if fallback_function:
        return fallback_function

    raise Exception("Unable to check jobs, possible incompatibility with the current TOIL version")


def _check_retry_count(job):
    """
    TOIL Adapter function to check for the job retry count using attributes under
    diffrent names from TOIL 5.4 and 3.21
    """
    if hasattr(job, "_remainingTryCount"):
        return getattr(job, "_remainingTryCount")

    if hasattr(job, "remainingRetryCount"):
        return getattr(job, "remainingRetryCount")

    raise Exception(
        """Unable to check retry for jobs, possible incompatibility
        with the current TOIL version"""
    )


def _check_job_stats(job):
    """
    TOIL Adapter function to check for job status using
    the proper attributes from TOIL 5.4 and 3.21
    """
    disk = None
    memory = None
    cores = None
    if hasattr(job, "_requirementOverrides"):
        requirement_overrides = getattr(job, "_requirementOverrides")
        disk = requirement_overrides.get("disk")
        memory = requirement_overrides.get("memory")
        cores = requirement_overrides.get("cores")
    else:
        if hasattr(job, "_disk"):
            disk = getattr(job, "_disk")
        if hasattr(job, "_memory"):
            memory = getattr(job, "_memory")
        if hasattr(job, "_cores"):
            cores = getattr(job, "_cores")
    return cores, disk, memory


def _get_job_stream_path(text):
    """
    TOIL helper function to parse the
    job stream path from text
    """
    job_stream = re.search("files.*stream", text)
    if job_stream:
        return job_stream[0]
    return None


def _read_stats_file(stats_path):
    """
    TOIL Adapter function to read the stats file
    """
    stats_info = []
    if os.path.exists(stats_path):
        with open(stats_path, "rb") as stats_file:
            try:
                stats_json = json.load(stats_file)
            except JSONDecodeError:
                logger.error("Could not load stats file: %s", stats_path)
                stats_json = {}
            worker_logs = stats_json.get("workers", {}).get("logsToMaster", [])
            jobs = stats_json.get("jobs", [])
            for single_worker, single_job in zip(worker_logs, jobs):
                worker_text = single_worker.get("text", "")
                job_stream = _get_job_stream_path(worker_text)
                job_mem = single_job.get("memory")
                job_cpu = single_job.get("clock")
                if job_stream and job_mem and job_cpu:
                    stats_info.append((job_stream, job_mem, job_cpu))
    return stats_info


def _clean_job_store(read_only_job_store_obj, job_store_cache):
    """
    TOIL track helper to clean the jobstore
    """
    root_job = read_only_job_store_obj.clean(jobCache=job_store_cache)
    return root_job


# @retry(
#    wait=wait_fixed(WAITTIME) + wait_random(0, JITTER),
#    stop=stop_after_attempt(ATTEMPTS),
#    after=after_log(logger, logging.DEBUG),
# )
def _resume_job_store(job_store_path, total_attempts):
    """
    TOIL track helper to load a created file jobstore
    into a TOIL jobstore object and avoid random filesystem
    issues
    """
    if not os.path.exists(job_store_path):
        raise Exception("Job store path %s not found" % job_store_path)
    read_only_job_store_obj = ReadOnlyFileJobStore(job_store_path, total_attempts)
    read_only_job_store_obj.resume()
    read_only_job_store_obj.set_job_cache()
    job_store_cache = read_only_job_store_obj.job_cache
    root_job = _clean_job_store(read_only_job_store_obj, job_store_cache)
    return (read_only_job_store_obj, root_job)


@retry(
    wait=wait_fixed(WAITTIME) + wait_random(0, JITTER),
    stop=stop_after_attempt(ATTEMPTS),
    after=after_log(logger, logging.DEBUG),
)
def _load_job_store(job_store, root_job):
    """
    TOIL track helper to load a file jobstore
    into a TOIL state object and avoid random filesystem
    issues
    """
    current_attempt = _load_job_store.retry.statistics["attempt_number"]
    if current_attempt > 1:
        job_store.setJobCache()
        toil_state_obj = toil_state(job_store, root_job)
    else:
        job_store_cache = job_store.job_cache
        toil_state_obj = toil_state(job_store, root_job, jobCache=job_store_cache)

    return toil_state_obj


def _check_job_state(work_log_path, jobs_path):
    """
    Check for job state files given a specific work
    directory path and report its job id
    """
    work_dir_path = os.path.dirname(work_log_path)
    job_state_glob = os.path.join(work_dir_path, "**", ".jobState")
    job_state_files = glob.glob(job_state_glob, recursive=True)
    job_stream = None
    for single_job_state_path in job_state_files:
        if os.path.exists(single_job_state_path):
            with open(single_job_state_path, "rb") as job_state_file:
                job_state_contents = pickle.load(job_state_file)
            job_stream = _get_job_stream_path(job_state_contents["jobName"])
    if job_stream and job_stream in jobs_path:
        return jobs_path[job_stream]

    return None


@retry(
    wait=wait_fixed(WAITTIME) + wait_random(0, JITTER),
    stop=stop_after_attempt(ATTEMPTS),
    after=after_log(logger, logging.DEBUG),
)
def _check_worker_logs(work_dir, work_log_to_job_id, jobs_path):
    """
    Check the work directory for worker logs and report
    the last time it was modified
    """
    worker_log_glob = os.path.join(work_dir, "**", "worker_log.txt")
    worker_log_files = glob.glob(worker_log_glob, recursive=True)
    worker_dict = {}
    for single_worker_log in worker_log_files:
        last_modified = _get_file_modification_time(single_worker_log)
        job_id = None
        if single_worker_log in work_log_to_job_id:
            job_id = work_log_to_job_id[single_worker_log]
        else:
            job_id = _check_job_state(single_worker_log, jobs_path)
        if job_id:
            worker_dict[job_id] = (single_worker_log, last_modified)
    return worker_dict


def _get_file_modification_time(file_path):
    """
    Get file modification time, return None if file does not exist
    """
    if os.path.exists(file_path):
        last_modified_epoch = os.path.getmtime(file_path)
        last_modified = str(datetime.fromtimestamp(last_modified_epoch))
        return last_modified

    return None


def _get_current_jobs(toil_state_obj):
    """
    TOIL Adapter function to get updated jobs
    from the toil_state_obj
    """
    updated_jobs = toil_state_obj.updatedJobs
    if not updated_jobs:
        return []

    job_list = []
    if isinstance(updated_jobs, set):
        for single_job in updated_jobs:
            job_list.append(single_job[0])
    elif isinstance(updated_jobs, dict):
        for single_job in updated_jobs.values():
            job_list.append(single_job[0])
    else:
        raise Exception(
            "Unable to check TOIL state, possible incompatibility with the current TOIL version"
        )
    return job_list


def _get_job_display_name(job):
    """
    TOIL adapter to get the display name of the job from TOIL job.
    Use the field job_name or display_name depending on the TOIL version
    Example:
        job_name: file:///Users/kumarn1/work/ridgeback/tests/test_jobstores/
                  test_cwl/sleep.cwl#simpleWorkflow/sleep/sleep
        returns "sleep"
    When id is not specified in the cwl it will return the name of the cwl
    Example:
        job_name: file:///Users/kumarn1/work/ridgeback/tests/test_jobstores/
                  test_cwl/sleep.cwl
        returns "sleep"
    """
    job_name = job.jobName
    display_name = job.displayName
    cwl_path = None
    if "cwl" in job_name:
        cwl_path = job_name
    elif "cwl" in display_name:
        cwl_path = display_name
    else:
        raise Exception("Could not find name in possible values %s %s" % (job_name, display_name))
    job_basename = os.path.basename(cwl_path)
    display_name = os.path.splitext(job_basename)[0]
    return display_name


class ReadOnlyFileJobStore(FileJobStore):
    """
    TOIL FileJobStore which can only perform Read operations
    for status retrieval
    """

    def __init__(self, path, total_attempts):
        super().__init__(path)
        self.failed_jobs = []
        self.total_attempts = total_attempts
        self.retry_jobs = []
        self.job_cache = {}
        self.stats_cache = {}
        self.job_store_path = path

    def check_if_job_exists(self, job_store_id):
        """
        Check if the job exists in the job store
        """
        check_function = _check_job_method(self)
        try:
            check_function(job_store_id)
            return True
        except NoSuchJobException:
            return False

    def load(self, jobStoreID):
        if jobStoreID in self.job_cache:
            return self.job_cache[jobStoreID]
        self.check_if_job_exists(jobStoreID)
        job_file = self._getJobFileName(jobStoreID)
        with open(job_file, "rb") as file_handle:
            job = pickle.load(file_handle)
        return job

    def set_job_cache(self):
        """
        Set the job cache of the job store
        """
        job_cache = {}
        for single_job in self.jobs():
            job_id = single_job.jobStoreID
            job_cache[job_id] = single_job
            if single_job.logJobStoreFileID is not None:
                failed_job = copy.deepcopy(single_job)
                self.failed_jobs.append(failed_job)
            retry_count = _check_retry_count(single_job)
            if retry_count is not None and retry_count < self.total_attempts:
                retry_job = copy.deepcopy(single_job)
                self.retry_jobs.append(retry_job)
        self.job_cache = job_cache

    def get_failed_jobs(self):
        """
        List all the failed jobs
        """
        return self.failed_jobs

    def get_restarted_jobs(self):
        """
        List all the restarted jobs
        """
        return self.retry_jobs

    def update(self, job):
        job_id = job.jobStoreID
        self.job_cache[job_id] = job

    def updateFile(self, jobStoreFileID, localFilePath):
        pass

    def get_stats_files(self):
        """
        Read the stats files
        """
        stats_file_list = []
        stats_directories = []
        if hasattr(self, "_statsDirectories"):
            stats_directories = self._statsDirectories()

        for temp_dir in stats_directories:
            stats_glob = os.path.join(temp_dir, "stats*")
            for single_stats_file_path in glob.glob(stats_glob):
                if single_stats_file_path not in self.stats_cache:
                    stats_file_list.append(single_stats_file_path)
                    self.stats_cache[single_stats_file_path] = None
        return stats_file_list

    def delete(self, jobStoreID):
        del self.job_cache[jobStoreID]

    def deleteFile(self, jobStoreFileID):
        pass

    def destroy(self):
        pass

    def create(self, jobDescription):
        pass

    @classmethod
    def _writeToUrl(cls, readable, url, executable=False):
        pass

    def writeFile(self, localFilePath, jobStoreID=None, cleanup=False):
        pass

    # pylint: disable=too-many-arguments
    def writeFileStream(
        self, jobStoreID=None, cleanup=False, basename=None, encoding=None, errors=None
    ):
        pass

    # pylint: enable=too-many-arguments

    def writeSharedFileStream(self, sharedFileName, isProtected=None, encoding=None, errors=None):
        pass

    def writeStatsAndLogging(self, statsAndLoggingString):
        pass

    def readStatsAndLogging(self, callback, readAll=False):
        pass


class ToolStatus(IntEnum):
    """
    Status enum for command line tools
    """

    PENDING = 0
    RUNNING = 2
    COMPLETED = 3
    FAILED = 4
    UNKNOWN = 5


class ToilTrack:
    """
    Toil Track class to parse commandline status of a TOIL run
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self, job_store_and_work_path, restart=False, show_cwl_internal=False, retry_count=1
    ):
        self.job_store_path = job_store_and_work_path[0]
        self.work_dir = job_store_and_work_path[1]
        self.jobs_path = {}
        self.workflow_id = ""
        self.jobs = {}
        self.work_log_to_job_id = {}
        self.retry_job_ids = {}
        self.job_store_obj = None
        self.restart = restart
        self.total_attempts = retry_count + 1
        self.show_cwl_internal = show_cwl_internal

    # pylint: enable=too-many-instance-attributes

    def create_job_id(self, job_store_id, id_prefix_param=None, id_suffix_param=None):
        """
        Create a job id using the Id in the TOIL jobstore with
        resume and restart information
        """
        restart = self.restart
        retry_job_ids = self.retry_job_ids
        id_suffix = id_suffix_param
        id_prefix = id_prefix_param
        if not id_prefix:
            if restart:
                id_prefix = "0"
            else:
                id_prefix = "1"
        if not id_suffix:
            if job_store_id not in retry_job_ids:
                id_suffix = "0"
            else:
                id_suffix = "1"
        if "instance" in job_store_id:
            job_store_id_split = job_store_id.split("instance")
            if len(job_store_id_split) > 1:
                job_id = job_store_id_split[1].replace("-", "")
            else:
                raise Exception("Malformed job id %s" % job_store_id)
        else:
            job_id = job_store_id
        id_string = "%s-%s-%s" % (id_prefix, job_id, id_suffix)
        return id_string

    def mark_job_as_failed(self, job_id, job_name, job):
        """
        Mark a job as failed
        """
        job_dict = self.jobs
        if job_name not in CWL_INTERNAL_JOBS or self.show_cwl_internal:
            if job_id in job_dict:
                job_dict[job_id]["status"] = ToolStatus.FAILED
                job_dict[job_id]["finished"] = datetime.now()
            else:
                cores, disk, memory = _check_job_stats(job)
                display_name = _get_job_display_name(job)
                new_job = {
                    "name": display_name,
                    "disk": disk,
                    "status": ToolStatus.FAILED,
                    "job_stream": None,
                    "memory_req": memory,
                    "cores_req": cores,
                    "cpu_usage": [],
                    "mem_usage": [],
                    "started": datetime.now(),
                    "submitted": datetime.now(),
                    "last_modified": datetime.now(),
                    "finished": datetime.now(),
                }
                job_dict[job_id] = new_job

    def _update_job_stats(self, job_key, job_mem, job_cpu):
        """
        Parse and update job stats
        """
        job_dict = self.jobs
        if job_key not in job_dict:
            return
        job_obj = job_dict[job_key]
        mem_list = job_obj.get("mem_usage", [])
        cpu_list = job_obj.get("cpu_usage", [])
        if len(mem_list) == 0:
            mem_list.append(job_mem)
        elif mem_list[-1] != job_mem:
            mem_list.append(job_mem)
        if len(cpu_list) == 0:
            cpu_list.append(job_cpu)
        elif cpu_list[-1] != job_cpu:
            cpu_list.append(job_cpu)
        job_obj["mem_usage"] = mem_list
        job_obj["cpu_usage"] = cpu_list
        job_dict[job_key] = job_obj

    def check_stats(self, job_store_obj):
        """
        Check TOIL mem and cpu stats for jobs
        """
        jobs_path = self.jobs_path
        if not job_store_obj:
            return
        stats_file_list = job_store_obj.get_stats_files()
        for single_stats_path in stats_file_list:
            stats_info = _read_stats_file(single_stats_path)
            for job_stream, job_mem, job_cpu in stats_info:
                job_key = jobs_path.get(job_stream)
                if job_key:
                    self._update_job_stats(job_key, job_mem, job_cpu)

    def handle_failed_jobs(self, job_store):
        """
        Check TOIL jobstore for failed jobs and mark
        them as failed
        """
        for single_job in job_store.get_failed_jobs():
            retry_count = _check_retry_count(single_job)
            if retry_count is not None:
                previous_suffix = self.total_attempts - (retry_count + 1)
                jobstore_id = single_job.jobStoreID
                job_id = self.create_job_id(jobstore_id, id_suffix_param=previous_suffix)
                job_name = single_job.jobName
                self.mark_job_as_failed(job_id, job_name, single_job)

    def handle_restarted_jobs(self, job_store):
        """
        Check TOIL jobstore for restarted jobs and check
        that the predecessor is marked as failed
        """
        retry_job_ids = self.retry_job_ids
        job_dict = self.jobs
        for single_job in job_store.get_restarted_jobs():
            retry_count = _check_retry_count(single_job)
            jobstore_id = single_job.jobStoreID
            previous_retry_count = self.total_attempts - (retry_count + 1)
            retry_job_ids[jobstore_id] = previous_retry_count
            job_id = self.create_job_id(jobstore_id, id_suffix_param=previous_retry_count)
            if job_id in job_dict and job_dict[job_id]["status"] != ToolStatus.FAILED:
                job_name = single_job.jobName
                self.mark_job_as_failed(job_id, job_name, single_job)

    def handle_current_jobs(self, toil_state_obj):
        """
        Check TOIL jobstore for current/new jobs, add new
        jobs, and collect stats on new jobs
        """
        jobs_dict = self.jobs
        current_jobs = []
        for single_job in _get_current_jobs(toil_state_obj):
            job_name = single_job.jobName
            if job_name not in CWL_INTERNAL_JOBS or self.show_cwl_internal:
                cores, disk, memory = _check_job_stats(single_job)
                jobstore_id = single_job.jobStoreID
                job_id = self.create_job_id(jobstore_id)
                current_jobs.append(job_id)
                job_stream = None
                if single_job.command:
                    job_stream = _get_job_stream_path(single_job.command)
                if not job_stream:
                    logger.debug("Could not find job_stream for job %s [%s]", job_name, job_id)
                if job_stream and job_id not in jobs_dict:
                    self.jobs_path[job_stream] = job_id
                    display_name = _get_job_display_name(single_job)
                    new_job = {
                        "name": display_name,
                        "disk": disk,
                        "status": ToolStatus.PENDING,
                        "job_stream": job_stream,
                        "memory_req": memory,
                        "cores_req": cores,
                        "cpu_usage": [],
                        "mem_usage": [],
                        "started": None,
                        "submitted": datetime.now(),
                        "last_modified": None,
                        "finished": None,
                    }
                    jobs_dict[job_id] = new_job
        return current_jobs

    def handle_finished_jobs(self, current_jobs):
        """
        Check for finished jobs
        """
        job_dict = self.jobs
        for job_id, job_obj in job_dict.items():
            if job_id not in current_jobs:
                status = job_obj["status"]
                if status not in (ToolStatus.COMPLETED, ToolStatus.FAILED):
                    job_obj["status"] = ToolStatus.COMPLETED
                    job_obj["finished"] = datetime.now()

    def handle_running_jobs(self):
        """
        Check for running jobs
        """
        job_dict = self.jobs
        worker_log_to_job_dict = self.work_log_to_job_id
        worker_info = _check_worker_logs(self.work_dir, worker_log_to_job_dict, self.jobs_path)
        for single_job_id in worker_info:
            worker_log, last_modified = worker_info[single_job_id]
            job_obj = job_dict[single_job_id]
            if job_obj["status"] == ToolStatus.PENDING or job_obj["status"] == ToolStatus.UNKNOWN:
                job_obj["status"] = ToolStatus.RUNNING
            if not job_obj["started"]:
                job_obj["started"] = datetime.now()
            if last_modified:
                job_obj["last_modified"] = last_modified
            if worker_log not in worker_log_to_job_dict:
                worker_log_to_job_dict[worker_log] = single_job_id

    def check_status(self):
        """
        Check the status of all jobs
        """
        try:
            job_store, root_job = _resume_job_store(self.job_store_path, self.total_attempts)
        except NoSuchJobStoreException:
            logger.warning("Jobstore not valid, toil job may be finished or just starting")
            return
        root_job_id = root_job.jobStoreID
        if not job_store.check_if_job_exists(root_job_id):
            logger.warning("Jobstore root not found, toil job may be finished or just starting")
        toil_state_obj = _load_job_store(job_store, root_job)
        if not toil_state_obj:
            logger.warning("TOIL state is unexpectedly empty")

        self.handle_failed_jobs(job_store)
        self.handle_restarted_jobs(job_store)
        current_jobs = self.handle_current_jobs(toil_state_obj)
        self.handle_finished_jobs(current_jobs)
        self.handle_running_jobs()
        self.check_stats(job_store)


def script_track_status(toil_track_obj):
    """
    Loop to track status of a job
    """
    jobs_path = {}
    jobs = {}
    work_log_to_job_id = {}
    while True:
        toil_track_obj.jobs_path = jobs_path
        toil_track_obj.jobs = jobs
        toil_track_obj.work_log_to_job_id = work_log_to_job_id
        toil_track_obj.check_status()
        jobs_path = toil_track_obj.jobs_path
        jobs = toil_track_obj.jobs
        work_log_to_job_id = toil_track_obj.work_log_to_job_id
        print(json.dumps(jobs, indent=4, sort_keys=True, default=str))
        time.sleep(4)


def script_snapshot_status(toil_track_obj_1, toil_track_obj_2):
    """
    Generate status using TOIL snapshots
    """
    toil_track_obj_1.check_status()
    toil_track_obj_2.jobs_path = toil_track_obj_1.jobs_path
    toil_track_obj_2.jobs = toil_track_obj_1.jobs
    toil_track_obj_2.work_log_to_job_id = toil_track_obj_1.work_log_to_job_id
    toil_track_obj_2.check_status()
    jobs = toil_track_obj_2.jobs
    print(json.dumps(jobs, indent=4, sort_keys=True, default=str))


def main():
    """
    Runs toil_track_utils through the command line
    """

    usage_str = """
              USAGE:
              toil_track_utils.py track [job_store_path] [work_dir_path]
              toil_track_utils.py snapshot [job_store_path_1] [work_dir_path_1] [job_store_path_2] [work_dir_path_2]
            """

    if len(sys.argv) not in [4, 6]:
        print(usage_str)
        sys.exit(0)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    if sys.argv[1] == "track":
        job_store_path = sys.argv[2]
        work_dir_path = sys.argv[3]
        toil_track_obj = ToilTrack([job_store_path, work_dir_path])
        script_track_status(toil_track_obj)
    elif sys.argv[1] == "snapshot":
        job_store_path_1 = sys.argv[2]
        work_dir_path_1 = sys.argv[3]
        job_store_path_2 = sys.argv[4]
        work_dir_path_2 = sys.argv[5]
        toil_track_obj_1 = ToilTrack([job_store_path_1, work_dir_path_1])
        toil_track_obj_2 = ToilTrack([job_store_path_2, work_dir_path_2])
        script_snapshot_status(toil_track_obj_1, toil_track_obj_2)
    else:
        print(usage_str)
        sys.exit(0)


if __name__ == "__main__":
    main()
