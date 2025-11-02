# Ridgeback Docker‑Compose Overview

This document explains the `docker-compose.yml` configuration used to run Ridgeback.  It covers each service, its purpose, key environment variables, and how the components interact.

---

## Service Overview
| Service | Purpose |
|---------|---------|
| `ridgeback_create_volumes` | Create host directories (postgres, logs, celery, rabbitmq, server, logrotate) with the correct UID/GID. |
| `ridgeback_postgres` | PostgreSQL database instance for Ridgeback. |
| `ridgeback_memcached` | Memcached cache server. |
| `ridgeback_rabbitmq` | RabbitMQ message broker with management UI. |
| `ridgeback` | Django application that hosts the Ridgeback web interface and API. |
| `ridgeback_celery_beat` | Celery beat scheduler that triggers periodic tasks. |
| `ridgeback_celery_*_queue` | Various Celery workers that process different task queues (command, action, status, submit‑job, set‑permission, cleanup). |
| `ridgeback_logrotate` | Periodically rotates application logs. |
| `ridgeback_db_backup` | Schedules regular database backups. |

---

## Detailed Service Configuration
### 1. `ridgeback_create_volumes`
* **Image**: Alpine 3.8 (minimal base). 
* **Entrypoint**: Bash script that `chown -R ${DOCKER_UID}:${DOCKER_GID}` for each host directory.
* **Volumes**: Maps the following directories into the container:
  * `./postgres:/postgres`
  * `./logs:/logs`
  * `./celery:/celery`
  * `./rabbitmq:/rabbitmq`
  * `./server/:/server`
  * `./logrotate:/logrotate`
  * `${DB_BACKUP_PATH}:/db_backup`

### 2. Database & Cache Services
| Service | Image | Key Environment Variables | Notes |
|---------|-------|--------------------------|-------|
| `ridgeback_postgres` | `postgres:17` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Exposes port `${RIDGEBACK_DB_PORT}` (default 5432). Healthcheck via `pg_isready`. |
| `ridgeback_memcached` | `bitnami/memcached:1.6.37` | N/A | Exposes port 11211; healthcheck via `nc`. |
| `ridgeback_rabbitmq` | `rabbitmq:4.0.6-management-alpine` | `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS` | Management UI on `${RIDGEBACK_RABBITMQ_MANAGEMENT_PORT}` (default 15672). Healthcheck via `rabbitmq-diagnostics`. |

All three depend on the volume‑creation service.

### 3. Core Django Application (`ridgeback`)
* **Image**: `mskcc/ridgeback:${RIDGEBACK_VERSION}`
* **Environment**: Uses the same DB, cache, and RabbitMQ URLs as the workers.
* **Volumes**:
  * `./logs/:/ridgeback/server/`
  * `./server/:/ridgeback_staticfiles/`
* **Command**: Runs migrations, creates a superuser if none exists, collects static files, then starts the Django development server on `${RIDGEBACK_PORT}`.
* **Healthcheck**: Simple `curl` to the web endpoint.
* **Dependencies**: PostgreSQL, Memcached, RabbitMQ.

### 4. Celery Workers & Beat
All workers share the anchor `x-ridgeback_celery` for common settings (image, user, network, env_file, volumes).  Each worker overrides the `command` to start its specific queue.

| Worker | Queue | Concurrency | Command |
|--------|-------|-------------|---------|
| `ridgeback_celery_beat` | N/A (beat) | 1 | Starts Celery beat with schedule file. |
| `ridgeback_celery_command_queue` | `${RIDGEBACK_COMMAND_QUEUE}` | 30 | Worker for command queue. |
| `ridgeback_celery_action_queue` | `${RIDGEBACK_ACTION_QUEUE}` | 10 | Worker for action queue. |
| `ridgeback_celery_check_status_queue` | `${RIDGEBACK_CHECK_STATUS_QUEUE}` | 10 | Worker for status checks. |
| `ridgeback_celery_submit_job_queue` | `${RIDGEBACK_SUBMIT_JOB_QUEUE}` | 5 | Worker for job submission. |
| `ridgeback_celery_set_permission_queue` | `${RIDGEBACK_SET_PERMISSIONS_QUEUE}` | 10 | Worker for permission setting. |
| `ridgeback_celery_cleanup_queue` | `${RIDGEBACK_CLEANUP_QUEUE}` | 2 | Worker for cleanup tasks. |

All depend on PostgreSQL, Memcached, RabbitMQ, and `ridgeback_celery_beat` for health.

### 5. Auxiliary Services
| Service | Image | Purpose |
|---------|-------|----------|
| `ridgeback_logrotate` | `mskcc/voyager-compose-utils:1.0.0` | Rotates logs weekly; uses supercronic to schedule logrotate runs. |
| `ridgeback_db_backup` | Same image | Schedules database backups via supercronic; uses `pg_dump`. |

Both depend on the beat and command‑queue workers.

### 6. Network
* **`voyager_net`** – Bridge network shared by all services.

---

## Key Environment Variables
| Variable | Description |
|----------|-------------|
| `RIDGEBACK_VERSION` | Docker image tag for Ridgeback. |
| `DOCKER_UID`, `DOCKER_GID` | UID/GID for container processes. |
| `RIDGEBACK_DB_USERNAME`, `_PASSWORD`, `_NAME` | PostgreSQL credentials. |
| `RIDGEBACK_RABBITMQ_USERNAME`, `_PASSWORD` | RabbitMQ credentials. |
| `CLUSTER_FILESYSTEM_MOUNT`, `CLUSTER_SCRATCH_MOUNT`, `CLUSTER_ADMIN_MOUNT` | Bind mounts for cluster file system access. |
| `LOGROTATE_*`, `DB_BACKUP_*` | Log rotation and backup scheduling options. |

---

This document provides a high‑level understanding of the Ridgeback Docker compose stack. For deeper configuration details, refer to the inline comments in `docker-compose.yml` and the respective service Dockerfiles.
