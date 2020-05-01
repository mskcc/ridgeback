import os
import subprocess
from django.conf import settings
import random
import string

def randomString(stringLength=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


class LSFClient(object):

    def submit(self, command, stdout):
        
        bsub_command = ['bsub', '-M 10', '-sla', settings.LSF_SLA, '-oo', stdout, '-eo', "/home/fraihaa/ridgeback/bsub-error-{}.log".format(randomString())]
        if settings.LSF_WALLTIME:
            bsub_command.extend(['-W', settings.LSF_WALLTIME])
        bsub_command.extend(command)
        process = subprocess.run(bsub_command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        return self._parse_procid(process.stdout)

    def _parse_procid(self, stdout):
        part1 = stdout.split('<')[1]
        lsf_job_id = part1.split('>')[0]
        return lsf_job_id

    def _parse_status(self, stdout):
        status = stdout.split()[3]
        return status

    def status(self, external_job_id):
        if external_job_id:
            bsub_command = ['bjobs', '-noheader', external_job_id]
            process = subprocess.run(bsub_command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
            status = self._parse_status(process.stdout)
            return status
