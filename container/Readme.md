## Ridgeback Server

#### Build SIF

```
export SINGULARITYENV_RIDGEBACK_BRANCH=master # branch on github to use on build; can set to any existing branch in repo
sudo -E singularity build ridgeback_service.sif ridgeback_service.def
```

#### Expected Instance Run Variables

Here are both the essential and optional environment variables needed by the instance

> Note: Singularity passes environment variables to the SIF container by prepending variable names with
> `SINGULARITYENV_`. For example, to set `RIDGEBACK_PORT` in the container, you must set
> `SINGULARITYENV_RIDGEBACK_PORT`.

##### General

 Variable       | Description
 :------------- |:-------------
SINGULARITYENV_SINGULARITY_PATH | The path to the singularity executable
SINGULARITYENV_RIDGEBACK_VENV | The path to the venv containing toil and other python dependencies

Optional Variable       | Description | Default
:------------- |:------------- |:-------------
SINGULARITYENV_RIDGEBACK_PATH | The path to the ridgeback repo | /usr/bin/ridgeback (in container)
SINGULARITYENV_RIDGEBACK_PORT | The port to run the ridgeback webserver | 8000

##### Rabbitmq

 Variable       | Description
 :------------- |:-------------
 SINGULARITYENV_RIDGEBACK_DEFAULT_QUEUE | Default rabbitmq queue
 SINGULARITYENV_RIDGEBACK_RABBITMQ_USERNAME | rabbitmq username
 SINGULARITYENV_RIDGEBACK_RABBITMQ_PASSWORD | rabbitmq password


##### Database

Variable       | Description
:------------- |:-------------
SINGULARITYENV_RIDGEBACK_DB_NAME | Database name
SINGULARITYENV_RIDGEBACK_DB_USERNAME | Database username
SINGULARITYENV_RIDGEBACK_DB_PASSWORD | Database password
SINGULARITYENV_RIDGEBACK_DB_PORT | Database port


##### Toil

Variable       | Description
:------------- |:-------------
SINGULARITYENV_RIDGEBACK_TOIL_JOB_STORE_ROOT | TOIL jobstore
SINGULARITYENV_RIDGEBACK_TOIL_WORK_DIR_ROOT | TOIL workdir
SINGULARITYENV_RIDGEBACK_TOIL_TMP_DIR_ROOT | TOIL tmp dir


##### LSF

Variable       | Description
:------------- |:-------------
SINGULARITYENV_LSF_LIBDIR | The path to the lsf lib dir
SINGULARITYENV_LSF_SERVERDIR | The path to the lsf etc dir
SINGULARITYENV_LSF_ENVDIR | The path to the lsf.conf
SINGULARITYENV_LSF_BINDIR | The path to the lsf bin dir
SINGULARITYENV_RIDGEBACK_LSF_SLA | Service SLA for LSF jobs

Optional Variable       | Description | Default
:------------- |:------------- |:-------------
SINGULARITYENV_RIDGEBACK_LSF_WALLTIME | walltime limit for LSF jobs | None
SINGULARITYENV_RIDGEBACK_LSF_STACKLIMIT | Stacklimit for LSF | None


##### Celery

Optional Variable       | Description | Default
:--- | :--- | :---
SINGULARITYENV_CELERY_LOG_PATH | Path to store the celery log files | /tmp
SINGULARITYENV_CELERY_PID_PATH | Path to store the celery pid files | /tmp
SINGULARITYENV_CELERY_BEAT_SCHEDULE_PATH | Path to store the beat schedule path | /tmp




#### Configure singularity mount points

Since we will be running our instance in a singularity container, we need to make sure it has the right paths mounted for LSF and TOIL to work properly. Running the following command will mount the lsf directories and /juno

```
export SINGULARITY_BIND="/juno,$SINGULARITYENV_LSF_LIBDIR,$SINGULARITYENV_LSF_SERVERDIR,$SINGULARITYENV_LSF_ENVDIR,$SINGULARITYENV_LSF_BINDIR"
```

#### Running an instance

Running the following command will create a ridgeback instance named `ridgeback_service`
```
singularity instance start ridgeback_service.sif ridgeback_service
```

This is accessible through the port number set through `SINGULARITYENV_RIDGEBACK_PORT`

For example, if `SINGULARITYENV_RIDGEBACK_PORT=4003` on a machine called `silo`:

```
http://silo:4003
```
