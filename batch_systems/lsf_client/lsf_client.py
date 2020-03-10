import os
import re
import subprocess
import json
import logging
from random import randint
from django.conf import settings
from toil_orchestrator.models import Status


class LSFClient(object):

    def __init__(self):
        self.logger = logging.getLogger('LSF_client')

    def submit(self, command, stdout):
        bsub_command = ['bsub', '-sla', settings.LSF_SLA, '-oo', stdout]
        toil_lsf_args = '-sla %s' % settings.LSF_SLA
        if settings.LSF_WALLTIME:
            bsub_command.extend(['-W', settings.LSF_WALLTIME])
            toil_lsf_args = '%s -W %s' % (toil_lsf_args, settings.LSF_WALLTIME)
        bsub_command.extend(command)
        current_env = os.environ
        current_env['TOIL_LSF_ARGS'] = toil_lsf_args
        self.logger.debug("Running command: %s\nEnv: %s" % (bsub_command,current_env))
        process = subprocess.run(
            bsub_command, check=True, stdout=subprocess.PIPE, universal_newlines=True, env=current_env)
        return self._parse_procid(process.stdout)

    def parse_bjobs(self,bjobs_output_str):
        bjobs_dict = None
        bjobs_records = None
        # Handle Cannot connect to LSF. Please wait ... type messages
        dict_start = bjobs_output_str.find('{')
        dict_end = bjobs_output_str.rfind('}')
        if dict_start != -1 and dict_end != -1:
            bjobs_output = bjobs_output_str[dict_start:(dict_end+1)]
            try:
                bjobs_dict = json.loads(bjobs_output)
            except json.decoder.JSONDecodeError:
                self.logger.error("Could not parse bjobs output: {}".format(bjobs_output_str))
            if 'RECORDS' in bjobs_dict:
                bjobs_records = bjobs_dict['RECORDS']
        if bjobs_records == None:
            self.logger.error("Could not find bjobs output json in: {}".format(bjobs_output_str))

        return bjobs_records


    def _parse_procid(self, stdout):
        self.logger.debug("LSF returned %s" % stdout)
        lsf_job_id_search = re.search('Job <(.*)> is submitted', stdout)
        if lsf_job_id_search:
            lsf_job_id = int(lsf_job_id_search[1])
            self.logger.debug("Got the job id: {}".format(lsf_job_id))
        else:
            self.logger.error("Could not submit job\nReason: {}".format(stdout))
            temp_id = randint(10000000, 99999999)
            result = "NOT_SUBMITTED_{}".format(temp_id)
        return lsf_job_id

    def _parse_status(self, stdout, external_job_id):
        bjobs_records = self.parse_bjobs(stdout)
        status = None
        if bjobs_records:
            process_output = bjobs_records[0]
            if 'STAT' in process_output:
                process_status = process_output['STAT']
                if process_status == 'DONE':
                    self.logger.debug(
                        "Job [{}] completed".format(external_job_id))
                    return (Status.COMPLETED, None)
                if process_status == 'PEND':
                    pending_info = None
                    if 'PEND_REASON' in process_output:
                        if process_output['PEND_REASON']:
                            pending_info = process_output['PEND_REASON']
                    self.logger.debug("Job [{}] pending with: {}".format(external_job_id, pending_info))
                if process_status == 'EXIT':
                    return (Status.PENDING, pending_info.strip())
                    exit_code = 1
                    exit_info = None
                    if 'EXIT_CODE' in process_output:
                        if process_output['EXIT_CODE']:
                            exit_code = process_output['EXIT_CODE']
                            exit_info = "\nexit code: {}".format(exit_code)
                    if 'EXIT_REASON' in process_output:
                        if process_output['EXIT_REASON']:
                            exit_reason = process_output['EXIT_REASON']
                            exit_info += "\nexit reason: {}".format(exit_reason)
                    self.logger.error(
                        "Job [{}] failed with: {}".format(external_job_id, exit_info))
                if process_status == 'RUN':
                    return (Status.FAILED, exit_info.strip())
                    self.logger.debug(
                        "Job [{}] is running".format(external_job_id))
                    return (Status.RUNNING, None)
                if process_status in {'PSUSP', 'USUSP', 'SSUSP'}:
                    self.logger.debug(
                        "Job [{}] is suspended".format(external_job_id))
                    suspended_info = "Job suspended"
                    return (Status.PENDING, suspended_info)
        return status

    def status(self, external_job_id):
        bsub_command = ["bjobs", "-json", "-o","user exit_code stat exit_reason pend_reason", str(external_job_id)]
        self.logger.debug("Checking lsf status for job: {}".format(external_job_id))
        process = subprocess.run(bsub_command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        status = self._parse_status(process.stdout, external_job_id)
        return status
