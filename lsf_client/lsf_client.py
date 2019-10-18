import subprocess
from django.conf import settings


class LSFClient(object):

    def submit(self, command):
        command = ['bsub', '-sla', settings.LSF_SLA]
        if settings.LSF_WALLTIME:
            command.extend(['-W', settings.LSF_WALLTIME])
        process = subprocess.run(command, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        print(process.stdout)
        # check response

    def status(self, job):
        pass
