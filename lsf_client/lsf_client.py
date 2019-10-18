import subprocess
from django.conf import settings


class LSFClient(object):

    def submit(self, command):
        print(command)
        bsub_command = ['bsub', '-sla', settings.LSF_SLA]
        if settings.LSF_WALLTIME:
            bsub_command.extend(['-W', settings.LSF_WALLTIME])
        bsub_command.extend(command)
        process = subprocess.run(bsub_command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        return self._parse_procid(process.stdout)

    def _parse_procid(self, stdout):
        part1 = stdout.split('<')[1]
        lsf_job_id = part1.split('>')[0]
        return lsf_job_id

    def status(self, job_id):
        pass
