## Ridgeback Server

#### Build SIF

```
sudo singularity build ridgeback_service.sif ridgeback_service.def
```

#### Expected Variables

The following environment variables must be set so that the instance can run properly.

Note: Singularity passes environment variables to the SIF container by prepending variable names with `SINGULARITYENV_`. For example, to set `RIDGEBACK_PORT` in the container, you must set `SINGULARITYENV_RIDGEBACK_PORT`.

```
SINGULARITYENV_RIDGEBACK_DB_NAME
SINGULARITYENV_RIDGEBACK_DB_USERNAME
SINGULARITYENV_RIDGEBACK_DB_PASSWORD
SINGULARITYENV_RIDGEBACK_TOIL_JOB_STORE_ROOT
SINGULARITYENV_RIDGEBACK_TOIL_WORK_DIR_ROOT
SINGULARITYENV_RIDGEBACK_TOIL_TMP_DIR_ROOT
SINGULARITYENV_RIDGEBACK_LSF_WALLTIME
SINGULARITYENV_RIDGEBACK_LSF_SLA
SINGULARITYENV_RIDGEBACK_LSF_STACKLIMIT
SINGULARITYENV_RIDGEBACK_RABBITMQ_USERNAME
SINGULARITYENV_RIDGEBACK_RABBITMQ_PASSWORD
SINGULARITYENV_RIDGEBACK_TOIL
SINGULARITYENV_SINGULARITY_CACHEDIR
SINGULARITYENV_SINGULARITY_TMPDIR
SINGULARITYENV_TOIL_LSF_ARGS
SINGULARITYENV_TMPDIR
SINGULARITYENV_RIDGEBACK_PORT
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
