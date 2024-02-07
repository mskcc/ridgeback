### Set the database env variable

#export RIDGEBACK_DB_NAME=travis_ci_test
#export RIDGEBACK_DB_USERNAME=postgres
#export RIDGEBACK_DB_PASSWORD=
#export RIDGEBACK_DB_PORT=5433

### Set general env variable

export SINGULARITY_PATH=/sample_singularity
export RIDGEBACK_VENV=/sample_path
export RIDGEBACK_PATH=/sample_path
export RIDGEBACK_PORT=4009

### Set the rabbitmq env variable

export RIDGEBACK_DEFAULT_QUEUE=sample_queue
export RIDGEBACK_RABBITMQ_USERNAME=sample_username
export RIDGEBACK_RABBITMQ_PASSWORD=sample_password

### Set the toil env variable

export RIDGEBACK_TOIL_JOB_STORE_ROOT=/sample_path
export RIDGEBACK_TOIL_WORK_DIR_ROOT=/sample_path
export RIDGEBACK_TOIL_TMP_DIR_ROOT=/sample_path

### Set the nextflow env variable

export RIDGEBACK_NEXTFLOW_JOB_STORE_ROOT=/sample_path
export RIDGEBACK_NEXTFLOW_WORK_DIR_ROOT=/sample_path
export RIDGEBACK_NEXTFLOW_TMP_DIR_ROOT=/sample_path

### Set the LSF env variable

export RIDGEBACK_LSF_WALLTIME=10:00
export RIDGEBACK_LSF_SLA=sample_SLA

### Set the celery env variable

export CELERY_LOG_PATH=/sample_path
export CELERY_PID_PATH=/sample_path
export CELERY_BEAT_SCHEDULE_PATH=/sample_path
