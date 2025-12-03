import os
import sys
import subprocess
import dill
import contextlib
import io
import logging
from pathlib import Path
from functools import wraps
from getpass import getuser
import django
import tempfile
import psutil
import signal
import atexit

from django.conf import settings

log = logging.getLogger(__name__)


def kill_proc_tree():
    current_pid = os.getpid()
    sig = signal.SIGTERM
    main = psutil.Process(current_pid)
    children = main.children(recursive=True)
    for child in children:
        try:
            child.send_signal(sig)
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(children, timeout=5)


atexit.register(kill_proc_tree)


def userscript():
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exception_raised = False
    output = None
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        try:
            env_path = sys.argv[1]
            with open(env_path, "rb") as env_file:
                env_dict = dill.load(env_file)
            for single_env in env_dict:
                if single_env == "PATH":
                    os.environ[single_env] = env_dict[single_env]
                else:
                    os.environ.setdefault(single_env, env_dict[single_env])
            ridgeback_path = env_dict["RIDGEBACK_PATH"]
            sys.path.append(ridgeback_path)
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ridgeback.settings")
            django.setup()
            func_data = sys.stdin.buffer.read()
            func, args, kwargs = dill.loads(func_data)
            output = func(*args, **kwargs)
        except Exception:
            log.exception("Exception when running the function as another user")
            exception_raised = True
    script_tuple = (output, stdout_buffer.getvalue().encode())
    sys.stderr.buffer.write(stderr_buffer.getvalue().encode())
    sys.stdout.buffer.write(dill.dumps(script_tuple))
    if exception_raised:
        sys.exit(1)


def userswitch(func):
    @wraps(func)
    def dzdo_wrapper(*args, **kwargs):
        # jobsubmitter/batchsystem objects will have the user attribute in self
        user = args[0].user
        current_env = {}
        if user == getuser() or not settings.ENABLE_USER_SWITCH:
            return func(*args, **kwargs)
        else:
            for key, value in os.environ.items():
                current_env[key] = value
            proc_command = ["dzdo", "--login", "-u", f"{user}", sys.executable, Path(__file__).absolute()]
        try:
            job_func = dill.dumps((func, args, kwargs))
            with tempfile.NamedTemporaryFile(mode="wb", dir="/tmp") as tmp_env_file:
                os.chmod(tmp_env_file.name, 0o755)
                dill.dump(current_env, tmp_env_file)
                dzdo_process = subprocess.run(
                    proc_command + [tmp_env_file.name],
                    input=job_func,
                    check=True,
                    capture_output=True,
                    env=current_env,
                    start_new_session=True,
                    timeout=43200,
                )
                output, stdout = dill.loads(dzdo_process.stdout)
                func_stdout = stdout.decode().strip()
                func_stderr = dzdo_process.stderr.decode().strip()
                if func_stdout:
                    log.info(func_stdout)
                if func_stderr:
                    log.error(func_stderr)
                return output
        except subprocess.TimeoutExpired as timout_err:
            stdout_str = ""
            stderr_str = ""
            try:
                stderr = timout_err.stderr
                if stderr:
                    stderr_str = stderr.decode().strip()
                output, stdout = dill.loads(timout_err.output)
                if stdout:
                    stdout_str = stdout.decode().strip()
            except Exception:
                stdout_str = "NA"
            exception_message = f"""
            Timeout error while userswitching:
            USER: {user}
            Timeout after {timout_err.timeout} seconds.
            Output: {stdout_str}
            Error: {stderr_str}
            """
            raise Exception(exception_message)
        except subprocess.CalledProcessError as e:
            stdout_str = ""
            stderr_str = ""
            try:
                stderr = e.stderr
                if stderr:
                    stderr_str = stderr.decode().strip()
                output, stdout = dill.loads(e.output)
                if stdout:
                    stdout_str = stdout.decode().strip()
            except Exception:
                stdout_str = "NA"
            exception_message = f"""
            Error while userswitching:
            USER: {user}
            Return Code: {e.returncode}
            Output: {stdout_str}
            Error: {stderr_str}
            """
            raise Exception(exception_message)
        except FileNotFoundError as e:
            exception_message = f"""
            Error, command not found while userswitching:
            {e.filename} not found.
            """
            raise Exception(exception_message)
        finally:
            kill_proc_tree()

    return dzdo_wrapper


if __name__ == "__main__":
    userscript()
