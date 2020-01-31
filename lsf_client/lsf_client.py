import os
import subprocess
from django.conf import settings


class LSFClient(object):

    def submit(self, command, stdout):
        bsub_command = ['bsub', '-sla', settings.LSF_SLA, '-oo', stdout]
        toil_lsf_args = '-sla %s' % settings.LSF_SLA
        if settings.LSF_WALLTIME:
            bsub_command.extend(['-W', settings.LSF_WALLTIME])
            toil_lsf_args = '%s -W %s' % (toil_lsf_args,settings.LSF_WALLTIME)
        bsub_command.extend(command)
        current_env = os.environ
        current_env['TOIL_LSF_ARGS'] = toil_lsf_args
        process = subprocess.run(bsub_command, check=True, stdout=subprocess.PIPE, universal_newlines=True, env=current_env)
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
