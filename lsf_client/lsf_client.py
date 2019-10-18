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
        print(process.stdout)
        # check response

    def status(self, job):
        pass
