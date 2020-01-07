#!/usr/bin/env python3
import os
import logging
from builtins import super
logging.getLogger("rdflib").setLevel(logging.WARNING)
logging.getLogger("toil.jobStores.fileJobStore").setLevel(logging.ERROR)
logging.getLogger("toil.jobStores.abstractJobStore").disabled = True
logging.getLogger("toil.toilState").setLevel(logging.WARNING)
from toil.common import Toil, safeUnpickleFromStream
from toil.jobStores.fileJobStore import FileJobStore
from toil.toilState import ToilState as toil_state
from toil.job import Job
from toil.cwl.cwltoil import CWL_INTERNAL_JOBS
from toil.job import JobException
from toil.jobStores.abstractJobStore import NoSuchJobStoreException, NoSuchFileException
from threading import Thread, Event
import pickle
from string import punctuation
import re
import datetime
import time
import copy
from subprocess import PIPE, Popen
import dill
import json
import sys
import copy
import traceback
import glob
from django.utils import timezone
time_format="%Y-%m-%d %H:%M:%S"
log_format="(%(current_time)s) [%(name)s:%(levelname)s] %(message)s"
### logging wrappers ###

def print_error(*args, **kwargs):
    print(*args,file=sys.stderr, **kwargs)

def add_stream_handler(logger,stream_format,logging_level):
    if not stream_format:
        formatter = logging.Formatter(log_format)
    else:
        formatter = logging.Formatter(stream_format)
    logger.propagate = False
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging_level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

def add_file_handler(logger,file_path,file_format,logging_level):
    if not file_format:
        formatter = logging.Formatter(log_format)
    else:
        formatter = logging.Formatter(file_format)
    logger.propagate = False
    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(logging_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

def log(logger,log_level,message):
    current_time = get_current_time()
    if not logger:
        if 'error' in log_level:
            print_error(message)
        else:
            print(message)
    try:
        logging_function = getattr(logger,log_level)
        logging_function(str(message), extra={'current_time':str(current_time)})
    except:
        logger.error("Log Level: "+ str(log_level) + " not found.\nOriginal message: "+ str(message), extra={'current_time':str(current_time)})

### time wrappers ###

def get_current_time():
    current_time = timezone.now()
    return current_time

def get_time_difference(first_time_obj,second_time_obj):
    #first_time_obj = datetime.datetime.strptime(first_time,time_format)
    #second_time_obj = datetime.datetime.strptime(second_time,time_format)
    time_delta =  first_time_obj - second_time_obj
    total_seconds = time_delta.total_seconds()
    minute_seconds = 60
    hour_seconds = 3600
    day_seconds = 86400
    days = divmod(total_seconds,day_seconds)
    hours = divmod(days[1],hour_seconds)
    minutes = divmod(hours[1],minute_seconds)
    seconds = minutes[1]
    days_abs = abs(int(days[0]))
    hours_abs = abs(int(hours[0]))
    minutes_abs = abs(int(minutes[0]))
    seconds_abs = abs(int(seconds))
    total_seconds_abs = abs(int(total_seconds))
    time_difference = {'days':days_abs,'hours':hours_abs,'minutes':minutes_abs,'seconds':seconds_abs,'total_seconds':total_seconds_abs}
    return time_difference


def get_time_difference_from_now(time_obj_str):
    current_time_str = get_current_time()
    time_difference = get_time_difference(current_time_str,time_obj_str)
    return time_difference

def time_difference_to_string(time_difference,max_number_of_time_units):
    number_of_time_units = 0
    time_difference_string = ""
    time_unit_list = ['day(s)','hour(s)','minute(s)','second(s)']
    for single_time_unit in time_unit_list:
        if time_difference[single_time_unit] != 0 and max_number_of_time_units > number_of_time_units:
            time_difference_string = time_difference_string + str(time_difference[single_time_unit]) + " " + str(single_time_unit) + " "
            number_of_time_units = number_of_time_units + 1
    if not time_difference_string:
        return "0 seconds "
    return time_difference_string

def get_status_names():
    status_name_dict = {'running':2,'pending':1,'done':3,'exit':4,'unknown':0}
    return status_name_dict

class ReadOnlyFileJobStore(FileJobStore):

    def __init__(self, path):
        super(ReadOnlyFileJobStore,self).__init__(path)
        self.failed_jobs = []
        #this assumes we start toil with retryCount=1
        self.default_retry_count = 1
        self.retry_jobs = []
        self.job_cache = {}
        self.stats_cache = {}
        self.job_store_path = path
        self.logger = None

    def check_if_job_exists(self,job_store_id):
        try:
            self._checkJobStoreId(job_store_id)
            return True
        except:
            return False

    def load(self,job_store_id):
        self._checkJobStoreId(job_store_id)
        if job_store_id in self.job_cache:
            return self.job_cache[job_store_id]
        job_file = self._getJobFileName(job_store_id)
        with open(job_file, 'rb') as file_handle:
            job = pickle.load(file_handle)
        return job

    def setJobCache(self):
        job_cache = {}
        for single_job in self.jobs():
            job_id = single_job.jobStoreID
            job_cache[job_id] = single_job
            if single_job.logJobStoreFileID != None:
                failed_job = copy.deepcopy(single_job)
                self.failed_jobs.append(failed_job)
            if single_job.remainingRetryCount == self.default_retry_count:
                retry_job = copy.deepcopy(single_job)
                self.retry_jobs.append(retry_job)
        self.job_cache = job_cache

    def getFailedJobs(self):
        return self.failed_jobs

    def getRestartedJobs(self):
        return self.retry_jobs

    def getFullLogPath(self,logPath):
        job_store_path = self.job_store_path
        full_path = os.path.join(job_store_path,'tmp',logPath)
        return full_path

    def writeFile(self, localFilePath, jobStoreID=None):
        pass

    def update(self, job):
        job_id = job.jobStoreID
        self.job_cache[job_id] = job

    def updateFile(self, jobStoreFileID, localFilePath):
        pass

    def getStatsFiles(self):
        stats_file_list = []
        for tempDir in self._tempDirectories():
            for tempFile in os.listdir(tempDir):
                if tempFile.startswith('stats'):
                    stats_file_path = os.path.join(tempDir, tempFile)
                    if stats_file_path not in self.stats_cache:
                        stats_file_list.append(stats_file_path)
                        self.stats_cache[stats_file_path] = None
        return stats_file_list

    def delete(self,job_store_id):
        del self.job_cache[job_store_id]

    def deleteFile(self, jobStoreFileID):
        pass

    def robust_rmtree(self, path, max_retries=3):
        pass

    def destroy(self):
        pass

    def create(self, jobNode):
        pass

    def _writeToUrl(cls, readable, url):
        pass

    def writeFile(self, localFilePath, jobStoreID=None):
        pass

    def writeFileStream(self, jobStoreID=None):
        pass

    def writeSharedFileStream(self, sharedFileName, isProtected=None):
        pass

    def writeStatsAndLogging(self, statsAndLoggingString):
        pass

    def readStatsAndLogging(self, callback, readAll=False):
        pass

    def _getTempSharedDir(self):
        pass

    def _getTempFile(self, jobStoreID=None):
        pass


class ToilTrack():

    def __init__(self,job_store_path,work_dir,restart,run_attempt,show_cwl_internal,logger):
        self.job_store_path = job_store_path
        self.work_dir = work_dir
        self.jobs_path = {}
        self.job_info_to_update = {}
        self.run_attempt = run_attempt
        self.workflow_id = ''
        self.jobs = {}
        self.retry_job_ids = {}
        self.current_jobs = []
        self.failed_jobs = []
        self.worker_jobs = {}
        self.job_store_obj = None
        self.job_store_resume_attempts = 5
        self.restart = restart
        self.restart_num = 2
        if not logger:
            logger = logging.getLogger('toil_track')
        self.logger = logger
        self.show_cwl_internal = show_cwl_internal


    def create_job_id(self,jobStoreID,remainingRetryCount):
        logger = self.logger
        restart = self.restart
        restart_num =  self.restart_num
        retry_job_ids = self.retry_job_ids
        run_attempt = int(self.run_attempt)
        first_run_attempt = run_attempt
        second_run_attempt = run_attempt + 1
        id_suffix = None
        id_prefix = None
        if restart:
            id_prefix = str(second_run_attempt) + '-'
        else:
            id_prefix = str(first_run_attempt) + '-'
        if remainingRetryCount == restart_num:
            id_suffix = '-0'
        else:
            if jobStoreID not in retry_job_ids:
                id_suffix = '-0'
            else:
                id_suffix = '-1'
        id_string = id_prefix + str(jobStoreID) + id_suffix
        return id_string

    def resume_job_store(self):
        logger = self.logger
        job_store_path = self.job_store_path
        read_only_job_store_obj = ReadOnlyFileJobStore(job_store_path)
        read_only_job_store_obj.resume()
        read_only_job_store_obj.setJobCache()
        job_store_cache = read_only_job_store_obj.job_cache
        try:
            root_job = read_only_job_store_obj.clean(jobCache=job_store_cache)
        except:
            retry_message = "Could not clean job store from jobCache, retrying"
            root_job = read_only_job_store_obj.clean()
            logger.debug(retry_message)
        self.job_store_obj = read_only_job_store_obj
        return {"job_store":read_only_job_store_obj,"root_job":root_job}

    def get_file_modification_time(self,file_path):
        if os.path.exists(file_path):
            last_modified_epoch = os.path.getmtime(file_path)
            last_modified = str(timezone.make_aware(datetime.datetime.fromtimestamp(last_modified_epoch)))
        else:
            last_modified = str(get_current_time())
        return last_modified

    def mark_job_as_failed(self,job_id,job_name):
        failed_job_list = self.failed_jobs
        job_dict = self.jobs
        current_time = get_current_time()
        if job_id not in failed_job_list:
            failed_job_list.append(job_id)
            if job_name not in CWL_INTERNAL_JOBS or self.show_cwl_internal:
                job_key = self.make_key_from_file(job_name,True)
                if job_key in job_dict:
                    tool_dict = job_dict[job_key]
                    if job_id in tool_dict['submitted']:
                        tool_dict['exit'][job_id] = current_time
                        if job_id in tool_dict['done']:
                            del tool_dict['done'][job_id]
    def check_stats(self):
        jobs_path = self.jobs_path
        job_dict = self.jobs
        logger = self.logger
        if self.job_store_obj:
            stats_file_list = self.job_store_obj.getStatsFiles()
            for single_stats_path in stats_file_list:
                try:
                    with open(single_stats_path, 'rb') as single_file:
                        single_stats_data = json.load(single_file)
                        if 'jobs' in single_stats_data:
                            for single_job_index, single_job in enumerate(single_stats_data['jobs']):
                                single_job_worker_log = single_stats_data['workers']['logsToMaster'][single_job_index]['text']
                                single_job_stream_path = single_job_worker_log.split(" ")[1]
                                if single_job_stream_path in jobs_path:
                                    tool_key = jobs_path[single_job_stream_path]
                                    if tool_key in job_dict:
                                        tool_dict = job_dict[tool_key]
                                        for single_job_key in tool_dict['workers']:
                                            single_worker_obj = tool_dict['workers'][single_job_key]
                                            if single_worker_obj["job_stream"]:
                                                if single_worker_obj["job_stream"].split("/")[2] == single_job_stream_path.split("/")[2]:
                                                    single_worker_obj["job_memory"] = single_job['memory']
                                                    single_worker_obj["job_cpu"] = single_job['clock']
                except IOError:
                    continue

    def check_jobs(self):
        logger = self.logger
        job_dict = self.jobs
        jobs_path = self.jobs_path
        job_info_to_update = self.job_info_to_update
        job_store_resume_attempts = self.job_store_resume_attempts
        retry_job_ids = self.retry_job_ids
        current_attempt = 0
        job_store_obj = None
        if not job_store_obj:
            try:
                job_store_obj = self.resume_job_store()
            except:
                retry_message = "Jobstore not created yet, toil job may be finished or just starting"
                debug_message = traceback.format_exc()
                logger.warn(retry_message)
                logger.debug(debug_message)
        if not job_store_obj:
            return
        current_jobs = []
        job_store = job_store_obj["job_store"]
        root_job = job_store_obj["root_job"]
        job_store_cache = job_store.job_cache
        self.workflow_id = job_store.config.workflowID
        toil_state_obj = None
        current_attempt = 0
        if not toil_state_obj:
            try:
                root_job_id = root_job.jobStoreID
                if not job_store.check_if_job_exists(root_job_id):
                    return
                if current_attempt != 0:
                    job_store.setJobCache()
                    toil_state(job_store,root_job)
                else:
                    job_store_cache = job_store.job_cache
                    toil_state_obj = toil_state(job_store,root_job,jobCache=job_store_cache)
            except:
                warning_message = "Jobstore not loaded properly, toil job may be finished or just starting"
                debug_message = traceback.format_exc()
                logger.warn(retry_message)
                logger.debug(debug_message)
        if not toil_state_obj:
            return
        current_time = get_current_time()
        for single_job in job_store.getFailedJobs():
            job_name = single_job.jobName
            failed_job_log_file = single_job.logJobStoreFileID
            retry_count = single_job.remainingRetryCount
            jobstore_id = single_job.jobStoreID
            if retry_count == 0 and jobstore_id not in retry_job_ids:
                continue
            retry_count = retry_count + 1
            job_id = self.create_job_id(single_job.jobStoreID,retry_count)
            self.mark_job_as_failed(job_id,job_name)
        for single_job in job_store.getRestartedJobs():
            jobstore_id = single_job.jobStoreID
            retry_count = single_job.remainingRetryCount
            previous_retry_count = retry_count + 1
            retry_job_ids[jobstore_id] = retry_count
            job_name = single_job.jobName
            job_id = self.create_job_id(jobstore_id,previous_retry_count)
            self.mark_job_as_failed(job_id,job_name)
        for single_job, result in toil_state_obj.updatedJobs:
            job_name = single_job.jobName
            if job_name not in CWL_INTERNAL_JOBS or self.show_cwl_internal:
                job_disk = single_job._disk/float(1e9)
                job_memory = single_job._memory/float(1e9)
                job_cores = single_job._cores
                jobstore_id = single_job.jobStoreID
                retry_count = single_job.remainingRetryCount
                if jobstore_id in retry_job_ids:
                    retry_count = retry_job_ids[jobstore_id]
                job_id = self.create_job_id(jobstore_id,retry_count)
                job_stream = None
                job_info = None
                if single_job.command:
                    job_stream = single_job.command.split(" ")[1]
                job_key = self.make_key_from_file(job_name,True)
                if job_stream:
                    jobs_path[job_stream] = job_key
                    job_stream_obj = self.read_job_stream(job_store,job_stream)
                    job_info = job_stream_obj['job_info']
                    if not job_info:
                        single_job_info_to_update = {'job_key':job_key,'job_id':job_id}
                        job_info_to_update[job_stream] = single_job_info_to_update
                current_jobs.append(job_id)
                worker_obj = {"disk":job_disk,"memory":job_memory,"cores":job_cores,"job_stream":job_stream,"job_info":job_info,'job_memory':None,'job_cpu':None}
                if job_key not in job_dict:
                    job_dict[job_key] = {'started':{},'submitted':{},'workers':{},'done':{},'exit':{}}
                tool_dict = job_dict[job_key]
                if job_id not in tool_dict['submitted']:
                    tool_dict['submitted'][job_id] = current_time
                if job_id not in tool_dict['workers']:
                    tool_dict['workers'][job_id] = worker_obj
        updated_list = []
        for single_job_to_update in job_info_to_update.keys():
            job_stream = single_job_to_update
            job_key = job_info_to_update[single_job_to_update]['job_key']
            job_id = job_info_to_update[single_job_to_update]['job_id']
            job_stream_obj = self.read_job_stream(job_store,job_stream)
            job_info = job_stream_obj['job_info']
            if job_info:
                tool_dict = job_dict[job_key]
                worker_obj = tool_dict['workers'][job_id]
                worker_obj['job_info'] = job_info
                tool_dict['workers'][job_id] = worker_obj
                updated_list.append(single_job_to_update)
        for single_job_updated in updated_list:
            if single_job_updated in job_info_to_update:
                del job_info_to_update[single_job_updated]
        self.job_info_to_update = job_info_to_update
        self.jobs_path = jobs_path
        self.current_jobs = current_jobs

    def make_key_from_file(self,job_name,use_basename):
        work_dir = self.work_dir
        workflow_id = 'toil-' + self.workflow_id
        if use_basename:
            job_id_with_extension = os.path.basename(job_name)
            job_id = os.path.splitext(job_id_with_extension)[0]
        else:
            job_id = os.path.relpath(job_name,work_dir)
            job_id.replace(workflow_id,"")
        safe_key = re.sub("["+punctuation+"]","_",job_id)
        return safe_key

    def read_job_stream(self,job_store_obj,job_stream_path):
        logger = self.logger
        job_id = ""
        job_info = None
        try:
            job_stream_file = job_store_obj.readFileStream(job_stream_path)
            job_stream_abs_path = job_store_obj._getAbsPath(job_stream_path)
            if os.path.exists(job_stream_abs_path):
                with job_stream_file as job_stream:
                    job_stream_contents = safeUnpickleFromStream(job_stream)
                    job_stream_contents_dict = job_stream_contents.__dict__
                    job_name = job_stream_contents_dict['jobName']
                    if job_name not in CWL_INTERNAL_JOBS or self.show_cwl_internal:
                        job_id = self.make_key_from_file(job_name,True)
                        if 'cwljob' in job_stream_contents_dict:
                            job_info = job_stream_contents_dict['cwljob']
        except:
            debug_message = "Could not read job path: " +str(job_stream_path) + ".\n"+traceback.format_exc()
            logger.debug(debug_message)

        return {"job_id":job_id,"job_info":job_info}

    def read_worker_log(self,worker_log_path):
        worker_jobs = self.worker_jobs
        logger = self.logger
        job_dict = self.jobs
        jobs_path = self.jobs_path
        read_only_job_store_obj = self.job_store_obj
        current_time = get_current_time()
        worker_log_key = self.make_key_from_file(worker_log_path,False)
        if os.path.isfile(worker_log_path):
            update_worker_jobs = False
            last_modified = self.get_file_modification_time(worker_log_path)
            if worker_log_key not in worker_jobs:
                worker_info = None
                worker_directory = os.path.dirname(worker_log_path)
                list_of_tools = []
                if worker_directory:
                    for root, dirs, files in os.walk(worker_directory):
                        for single_file in files:
                            if single_file == '.jobState':
                                job_state = {}
                                job_info = {}
                                job_name = ''
                                job_state_path = os.path.join(root,single_file)
                                tool_key = None
                                job_stream_path = ""
                                if os.path.exists(job_state_path):
                                    with open(job_state_path,'rb') as job_state_file:
                                        job_state_contents = dill.load(job_state_file)
                                        job_state = job_state_contents
                                        job_stream_path = job_state_contents['jobName']
                                        if job_stream_path in jobs_path:
                                            tool_key = jobs_path[job_stream_path]
                                if tool_key:
                                    if tool_key in job_dict:
                                        tool_dict = job_dict[tool_key]
                                        for single_job_key in tool_dict['workers']:
                                            single_worker_obj = tool_dict['workers'][single_job_key]
                                            if single_worker_obj["job_stream"] == job_stream_path:
                                                update_worker_jobs = True
                                                worker_info = {'job_state':job_state,'log_path':worker_log_path,'started':current_time,'last_modified': last_modified}
                                                tool_dict['started'][single_job_key] = current_time
                                                single_worker_obj.update(worker_info)
                                                tool_info = (tool_key,single_job_key)
                                                list_of_tools.append(tool_info)
                                else:
                                    update_worker_jobs = False
                if update_worker_jobs:
                    worker_jobs[worker_log_key] = {'list_of_tools':list_of_tools}
            else:
                worker_jobs_tool_list = worker_jobs[worker_log_key]['list_of_tools']
                for single_tool,single_job_key in worker_jobs_tool_list:
                    worker_info = job_dict[single_tool]['workers'][single_job_key]
                    worker_info['last_modified'] = last_modified


    def check_for_running(self):
        work_dir = self.work_dir
        job_dict = self.jobs
        workflow_id = self.workflow_id
        if work_dir:
            for root, dirs, files in os.walk(work_dir):
                for single_file in files:
                    if single_file == "worker_log.txt":
                        worker_log_path = os.path.join(root,single_file)
                        try:
                            worker_info = self.read_worker_log(worker_log_path)
                        except:
                            pass

    def check_for_finished_jobs(self):
        job_dict = self.jobs
        current_jobs = self.current_jobs
        current_time = get_current_time()
        finished_jobs = False
        for single_tool_name in job_dict:
            single_tool = job_dict[single_tool_name]
            submitted_dict = single_tool['submitted']
            for single_job in submitted_dict:
                if single_job not in single_tool['done']:
                    if single_job not in current_jobs:
                        finished_jobs = True
                        self.check_stats()
                        if single_job not in single_tool['exit']:
                            single_tool['done'][single_job] = current_time

    def get_pending_and_running_jobs(self,submitted_dict,done_dict,exit_dict,workers_dict):
        logger = self.logger
        pending_dict = {}
        running_dict = {}
        current_time = get_current_time()
        for single_job in submitted_dict:
            if single_job not in done_dict and single_job not in exit_dict:
                if single_job in workers_dict:
                    single_worker_obj = workers_dict[single_job]
                    if 'started' not in single_worker_obj:
                        pending_dict[single_job] = current_time
                    else:
                        started_time = single_worker_obj['started']
                        last_modified = single_worker_obj['last_modified']
                        running_obj = {'started':started_time,'last_modified':last_modified}
                        running_dict[single_job] = running_obj
                else:
                    error_message = str(single_job) + " not found in worker dictionary"
                    logger.error(error_message)

        return {'pending':pending_dict,'running':running_dict}


    def prepare_job_status(self):
        job_dict = self.jobs
        current_jobs = self.current_jobs
        job_status ={}
        for single_tool_name in job_dict:
            single_tool = job_dict[single_tool_name]
            submitted_dict = single_tool['submitted']
            workers_dict = single_tool['workers']
            exit_dict = single_tool['exit']
            done_dict = single_tool['done']
            pending_and_running_dict = self.get_pending_and_running_jobs(submitted_dict, done_dict, exit_dict, workers_dict)
            pending_dict = pending_and_running_dict['pending']
            running_dict = pending_and_running_dict['running']
            job_status[single_tool_name] = {'submitted':submitted_dict,'running':running_dict,'exit':exit_dict,'done':done_dict,'pending':pending_dict}
        return job_status

    def check_status(self):
        logger = self.logger
        job_status = {}
        self.check_jobs()
        self.check_for_running()
        self.check_stats()
        self.check_for_finished_jobs()
        new_job_status = self.prepare_job_status()
        jobs_dict = self.jobs
        status_name_dict = get_status_names()
        status_list = []
        for single_tool in new_job_status:
            for single_status in status_name_dict.keys():
                if single_status in new_job_status[single_tool]:
                    job_list = new_job_status[single_tool][single_status]
                    if job_list:
                        for single_job in job_list.keys():
                            single_job_obj = job_list[single_job]
                            single_worker_obj = None
                            if single_tool in jobs_dict:
                                if 'workers' in jobs_dict[single_tool]:
                                    if single_job in jobs_dict[single_tool]['workers']:
                                        single_worker_obj = jobs_dict[single_tool]['workers'][single_job]
                            job_status = status_name_dict[single_status]
                            job_status_name = single_status
                            job_id = single_job
                            job_details = {}
                            job_submitted = None
                            job_started = None
                            job_finished = None
                            if job_status == 3 or job_status == 4:
                                job_finished = single_job_obj
                            if 'started' in jobs_dict[single_tool]:
                                if single_job in jobs_dict[single_tool]['started']:
                                    job_started = jobs_dict[single_tool]['started'][single_job]
                            if 'submitted' in new_job_status[single_tool]:
                                if single_job in new_job_status[single_tool]['submitted']:
                                    job_submitted = new_job_status[single_tool]['submitted'][single_job]
                            if single_worker_obj:
                                job_details = copy.deepcopy(single_worker_obj)
                                if "job_stream" in job_details:
                                    job_details.pop("job_stream")
                                if "job_state" in job_details:
                                    job_details.pop("job_state")
                                if "started" in job_details:
                                    job_details.pop("started")
                            if job_started == None and job_finished != None and job_submitted != None:
                                job_started = job_submitted
                            job_obj = {'name':single_tool,'status':job_status,'id':job_id,'details':job_details,'submitted':job_submitted,'started':job_started,'finished':job_finished}
                            status_list.append(job_obj)
        return status_list

    def get_change_status(self,old_job_status, new_job_status):
        status_format = {'running':{'message':'{} is now running'},
                       'exit':{'message':'{} has exited'},
                       'done':{'message':'{} has finished'},
                       'pending':{'message':'{} is now pending'}}
        status_type = status_format.keys()
        status_name_dict = get_status_names()
        status_change = {}
        for single_tool in new_job_status:
            single_tool_obj = new_job_status[single_tool]
            for single_status in status_type:
                single_tool_status = single_tool_obj[single_status]
                if single_tool_status:
                    for single_job_id in single_tool_status.keys():
                        update_running_last_modified = False
                        update_status = False
                        if single_status == 'running':
                            update_running_last_modied = True
                        if not old_job_status or single_tool not in old_job_status or single_status not in old_job_status[single_tool] or single_job_id not in old_job_status[single_tool][single_status]:
                            update_status = True
                        if update_status or update_running_last_modified:
                            status_template = status_format[single_status]['message']
                            message = None
                            if update_status:
                                job_name = single_tool + '( ID: ' + single_job_id + ' )'
                                message = status_template.format(job_name)
                            status = status_name_dict[single_status]
                            job_obj = {'single_tool_status':single_tool_status,'job_name':single_tool,'job_id':single_job_id,'status':status}
                            status_change[single_job_id] = {'message':message,'job_obj':job_obj}
        return status_change

    def print_change_status(self,status_change):
        logger = self.logger
        for single_job in status_change:
            single_job_obj = status_change[single_job]
            single_job_message = single_job_obj['message']
            if single_job_message:
                logger.info(single_job_message)

    def print_job_status(self,job_status):
        logger = self.logger
        if not job_status:
            return
        overview_status_list = []
        status_list = []
        status_dict = {'running':{'header':'Running:','status':'','total':0},
                       'exit':{'header':'Exit:','status':'','total':0},
                       'done':{'header':'Done:','status':'','total':0},
                       'pending':{'header':'Pending:','status':'','total':0}}
        status_items = status_dict.keys()
        logger.info(job_status)
        for single_tool in job_status:
            single_tool_obj = job_status[single_tool]
            for single_status_key in status_dict:
                single_tool_status = single_tool_obj[single_status_key]
                single_status_dict = status_dict[single_status_key]
                tool_status_num = 0
                tool_status_str = single_status_dict['status']
                if single_status_key == 'running':
                    if len(single_tool_status) != 0:
                        tool_status_str = tool_status_str + "\t- " + str(single_tool) + "\n"
                    for single_running_job_key in single_tool_status:
                        single_running_job = single_tool_status[single_running_job_key]
                        last_modified = single_running_job['last_modified']
                        time_difference = get_time_difference(last_modified)
                        time_difference_string = time_difference_to_string(time_difference,2)
                        tool_status_str = tool_status_str + "\t\t- [ last modified: " + time_difference_string + " ago ]\n"
                        tool_status_num = tool_status_num + 1
                    if tool_status_num != 0:
                        tool_status_str = tool_status_str + "\t\t- Total: " + str(tool_status_num) + "\n"
                else:
                    tool_status_num = len(single_tool_status)
                    if tool_status_num != 0:
                        job_or_jobs_str = "jobs"
                        if tool_status_num == 1:
                            job_or_jobs_str = "job"
                        tool_status_str = tool_status_str + "\t- " + str(single_tool) + " [ "+str(tool_status_num) + " " + job_or_jobs_str + " ]\n"
                single_status_dict['total'] = single_status_dict['total'] + tool_status_num
                single_status_dict['status'] = tool_status_str
        total_jobs = 0
        for single_status_key in status_dict:
            single_status_dict = status_dict[single_status_key]
            status_jobs = single_status_dict["total"]
            total_jobs = total_jobs + single_status_dict["total"]
            if status_jobs != 0:
                status_header = single_status_dict['header']
                status_str = status_header + "\n" + single_status_dict['status']
                status_jobs = status_header + " " + str(status_jobs)
                overview_status_list.append(status_jobs)
                status_list.append(status_str)
        overview_status = "Total Job(s): " + str(total_jobs) + " ( " + " ".join(overview_status_list) + " )"
        status = overview_status + "\n" +"\n".join(status_list)
        logger.info(status)

def main():
    current_jobs = []
    jobs_path = {}
    jobs = {}
    worker_jobs = {}
    while True:
        roslin_track = ToilTrack('/Users/kumarn1/work/roslin-variants/roslin-core/bin/jobstore','/Users/kumarn1/work/roslin-variants/roslin-core/bin/work_dir',False,0,False,None)
        roslin_track.current_jobs = current_jobs
        roslin_track.jobs_path = jobs_path
        roslin_track.jobs = jobs
        roslin_track.worker_jobs = worker_jobs
        roslin_track.check_status()
        current_jobs = roslin_track.current_jobs
        jobs_path = roslin_track.jobs_path
        jobs = roslin_track.jobs
        worker_jobs = roslin_track.worker_jobs
        time.sleep(1)


if __name__ == "__main__":
    main()
