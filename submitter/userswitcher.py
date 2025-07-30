import sys
import marshal
import subprocess
import dill
import contextlib
import io
import logging
from pathlib import Path
from functools import wraps
from getpass import getuser

log = logging.getLogger(__name__)


def userscript():
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exception_raised = False
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        try:
            func_serialized, args, kwargs = marshal.loads(sys.stdin.buffer.read())
            func = dill.loads(func_serialized)
            output = func(*args, **kwargs)
        except Exception as e:
            log.exception("Exception when running the function as another user")
            exception_raised = True
    script_tuple = (output, stdout_buffer.getvalue())
    sys.stderr.buffer.write(stderr_buffer.getvalue())
    sys.stdout.buffer.write(dill.dumps(script_tuple))
    if exception_raised:
        sys.exit(1)


def userswitch(func):
    @wraps(func)
    def dzdo_wrapper(*args, **kwargs):
        # jobsubmitter/batchsystem objects will have the user attribute in self
        user = args[0].user
        if user == getuser():
            return func(args, kwargs)
        else:
            proc_command = ["dzdo", "-u", f"{user}", sys.executable, "-c", Path(__file__).absolute()]
            serialized_func = dill.dumps(func)
            func_data = marshal.dumps((serialized_func, args, kwargs))
        try:
            dzdo_process = subprocess.run(proc_command, input=func_data, check=True, capture_output=True)
            log.error(dzdo_process.stderr)
            output, stdout = dill.loads(dzdo_process.stdout)
            log.info(stdout)
            return output
        except subprocess.CalledProcessError as e:
            exception_message = f"""
            Error while userswitching:
            Command: {e.cmd}
            Return Code: {e.returncode}
            Output: {e.output}
            Error: {e.stderr}
            """
            raise Exception(exception_message)
        except FileNotFoundError as e:
            exception_message = f"""
            Error, command not found while userswitching:
            {e.filename} not found.
            """
            raise Exception(exception_message)

    return dzdo_wrapper


if __name__ == "__main__":
    userscript()
