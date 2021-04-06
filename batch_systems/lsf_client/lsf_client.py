'''
Submit and monitor LSF jobs
'''
import os
import re
import subprocess
import json
import logging
from random import randint
from django.conf import settings
from toil_orchestrator.models import Status

logger = logging.getLogger('LSF_client')

def submit(command, job_args, stdout):
    '''
    Submit command to LSF and store log in stdout

        Args:
            command (str): command to submit
            stdout (str): log file path

        Returns:
            int: lsf job id
    '''
    bsub_command = ['bsub', '-sla', settings.LSF_SLA, '-oo', stdout] + job_args
    toil_lsf_args = '-sla %s %s' % (settings.LSF_SLA, " ".join(job_args))

    bsub_command.extend(command)
    current_env = os.environ
    current_env['TOIL_LSF_ARGS'] = toil_lsf_args
    logger.debug("Running command: %s\nEnv: %s", bsub_command, current_env)
    process = subprocess.run(
        bsub_command, check=True, stdout=subprocess.PIPE,
        universal_newlines=True, env=current_env)
    return _parse_procid(process.stdout)

def get_outputs(job_id):
    job_work_dir = os.path.join(settings.TOIL_WORK_DIR_ROOT, job_id)

    error_message = None
    result_json = None
    lsf_log_path = os.path.join(job_work_dir, 'lsf.log')
    try:
        with open(lsf_log_path, 'r') as f:
            data = f.readlines()
            data = ''.join(data)
            substring = data.split('\n{')[1]
            result = ('{' + substring).split('-----------')[0]
            result_json = json.loads(result)
    except (IndexError, ValueError):
        error_message = 'Could not parse json from %s' % lsf_log_path
    except FileNotFoundError:
        error_message = 'Could not find %s' % lsf_log_path

    return result_json, error_message

def abort(external_job_id):
    '''
    Kill LSF job

        Args:
            external_job_id (str): external_job_id

        Returns:
            bool: successful
    '''
    bkill_command = ['bkill', external_job_id]
    process = subprocess.run(
        bkill_command, check=True, stdout=subprocess.PIPE,
        universal_newlines=True)
    if process.returncode == 0:
        return True
    return False

def _parse_bjobs(bjobs_output_str):
    """
    Parse the output of bjobs into a descriptive dict

        Args:
            bjobs_output_str (str): Stdout from bjobs

        Returns:
            Dict: bjobs records
    """
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
            logger.error("Could not parse bjobs output: %s", bjobs_output_str)

        if 'RECORDS' in bjobs_dict:
            bjobs_records = bjobs_dict['RECORDS']
        if bjobs_records is None:
            logger.error("Could not find bjobs output json in: %s", bjobs_output_str)

    return bjobs_records


def _parse_procid(stdout):
    """
    Parse bsub output and retrieve the LSF id

    Args:
        stdout (str): bsub output

    Returns:
        int: LSF id
    """
    logger.debug("LSF returned %s", stdout)
    lsf_job_id_search = re.search('Job <(.*)> is submitted', stdout)
    if lsf_job_id_search:
        lsf_job_id = int(lsf_job_id_search[1])
        logger.debug("Got the job id: %s", lsf_job_id)
    else:
        logger.error("Could not submit job\nReason: %s", stdout)
        temp_id = randint(10000000, 99999999)
        lsf_job_id = "NOT_SUBMITTED_{}".format(temp_id)
    return lsf_job_id

def _handle_status( record):
    """
    Map LSF status to Ridgeback status

    Args:
        process_status (str): LSF status of process
        process_output (dict): LSF record dict
        external_job_id (str): LSF job id

    Returns:
        tuple: (Ridgeback Status int, extra info)
    """
    status = record['STAT']
    job_id = record['JOBID']
    if status == 'DONE':
        logger.debug(
            "Job [%s] completed", job_id)
        return (Status.COMPLETED, None)
    if status == 'PEND':
        pending_info = record['PEND_REASON'] if 'PEND_REASON' in record and record['PEND_REASON'] else ""
        logger.debug("Job [%s] pending with: %s", job_id, pending_info)
        return (Status.PENDING, pending_info.strip())
    if status == 'EXIT':
        exit_code = 1
        exit_info = ""
        if 'EXIT_CODE' in record and record['EXIT_CODE']:
            exit_code = record['EXIT_CODE']
            exit_info = "\nexit code: {}".format(exit_code)
        elif 'EXIT_REASON' in record and record['EXIT_REASON']:
            exit_reason = record['EXIT_REASON']
            exit_info += "\nexit reason: {}".format(exit_reason)
        logger.error(
            "Job [%s] failed with: %s", job_id, exit_info)
        return (Status.FAILED, exit_info.strip())
    if status == 'RUN':
        logger.debug(
            "Job [%s] is running", job_id)
        return (Status.RUNNING, None)
    if status in {'PSUSP', 'USUSP', 'SSUSP'}:
        logger.debug(
            "Job [%s] is suspended", job_id)
        suspended_info = "Job suspended"
        return (Status.PENDING, suspended_info.strip())
    logger.debug(
        "Job [%s] is in an unhandled state (%s)", job_id, status)
    status_info = "Job is in an unhandles state: {}".format(status)
    return (Status.UNKNOWN, status_info.strip())


def _parse_status(record):
    """Parse LSF stdout helper

    Args:
        record (Object): stdout of bjob
        external_job_id (int): LSF id

    Returns:
        tuple: (Ridgeback Status int, extra info)
    """
    if 'STAT' in record:
        process_status = record['STAT']
        return _handle_status(record)
    elif 'ERROR' in record:
        error_message = ""
        if record['ERROR']:
            error_message = record['ERROR']
        return (Status.UNKNOWN, error_message.strip())

def get_statuses(external_job_ids):
    """Parse LSF status

    Args:
        external_job_id (int): LSF id

    Returns:
        tuple: (Ridgeback Status int, extra info)
    """
    bsub_command = ["bjobs", "-json", "-o",
                    "id user exit_code stat exit_reason pend_reason"] + [str(job_id) for job_id in
                                                                         external_job_ids]

    logger.debug("Checking lsf status for jobs: %s", external_job_ids)
    process = subprocess.run(bsub_command, check=True, stdout=subprocess.PIPE,
                             universal_newlines=True)

    bjob_records = _parse_bjobs(process.stdout)
    return {record['JOBID']: _parse_status(record) for record in bjob_records}
