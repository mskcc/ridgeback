SHELL:=/bin/bash
UNAME:=$(shell uname)
CURDIR_BASE:=$(shell basename "$(CURDIR)")
export LOG_DIR_ABS:=$(shell python -c 'import os; print(os.path.realpath("logs"))')

$(LOG_DIR_ABS):
	mkdir -p "$(LOG_DIR_ABS)"

define help
This is the Makefile for setting up Ridgeback development instance

Basic dev instance setup instructions:
-------------------------------------

1. install dependencies in the current directory with:
make install

2. initialize the database with:
make db-init

3. initialize the Django database and set a admin (superuser) account with:
make django-init

4. to run Riodgeback, first start Postgres, RabbitMQ, and Celery with:
make start-services

5. start the main Django development server with:
make runserver

Extras
------

Shutdown all services:
make stop-services

Check if pre-configured ports are already occupied on your system:
make check-port-collision

Consult the contents of this Makefile for other management recipes.

endef
export help
help:
	@printf "$$help"

.PHONY : help


# ~~~~~ Python and nextflow installation ~~~~~~ #
PATH:=$(CURDIR)/conda/bin:$(PATH)
unexport PYTHONPATH
unexport PYTHONHOME

ifeq ($(UNAME), Darwin)
CONDASH:=Miniconda3-4.7.12.1-MacOSX-x86_64.sh
endif

ifeq ($(UNAME), Linux)
CONDASH:=Miniconda3-4.7.12.1-Linux-x86_64.sh
endif

CONDAURL:=https://repo.continuum.io/miniconda/$(CONDASH)

conda:
	@echo ">>> Setting up conda..."
	@wget "$(CONDAURL)" && \
	bash "$(CONDASH)" -b -p conda && \
	rm -f "$(CONDASH)"

# NOTE: RabbitMQ sometimes has installation problems on macOS 10.12
install: conda
	conda install -y \
	anaconda::postgresql \
	conda-forge::ncurses \
	rabbitmq-server && \
	pip install -r requirements.txt

install-requirements:
	pip install -r requirements.txt

install-local:
	cd toil-pip && \
	pip install .


make rabbit:
	rabbitmqctl
# Ridgeback environment variables for configuration
export RIDGEBACK_DB_NAME:=db
export RIDGEBACK_DB_USERNAME:=$(shell whoami)
export RIDGEBACK_DB_PASSWORD:=admin
export RIDGEBACK_DB_URL:=/tmp
export RIDGEBACK_PORT:=1112
export RIDGEBACK_TOIL_DIR:=$(CURDIR)/toil
export RIDGEBACK_TOIL_JOB_STORE:=$(RIDGEBACK_TOIL_DIR)/job_store
export RIDGEBACK_TOIL_JOB_STORE_ROOT:=$(RIDGEBACK_TOIL_DIR)/job_store_root
export RIDGEBACK_TOIL_WORK_DIR_ROOT:=$(RIDGEBACK_TOIL_DIR)/work
export RIDGEBACK_TOIL_TMP_DIR_ROOT:=$(RIDGEBACK_TOIL_DIR)/tmp
export RIDGEBACK_LSF_WALLTIME:=2880
# export RIDGEBACK_LSF_SLA:=CMOPI

$(RIDGEBACK_TOIL_DIR):
	mkdir -p "$(RIDGEBACK_TOIL_DIR)"
$(RIDGEBACK_TOIL_JOB_STORE):
	mkdir -p "$(RIDGEBACK_TOIL_JOB_STORE)"
$(RIDGEBACK_TOIL_JOB_STORE_ROOT):
	mkdir -p "$(RIDGEBACK_TOIL_JOB_STORE_ROOT)"
$(RIDGEBACK_TOIL_WORK_DIR_ROOT):
	mkdir -p "$(RIDGEBACK_TOIL_WORK_DIR_ROOT)"
$(RIDGEBACK_TOIL_TMP_DIR_ROOT):
	mkdir -p "$(RIDGEBACK_TOIL_TMP_DIR_ROOT)"

toil-init: $(RIDGEBACK_TOIL_DIR) $(RIDGEBACK_TOIL_JOB_STORE) $(RIDGEBACK_TOIL_JOB_STORE_ROOT) $(RIDGEBACK_TOIL_WORK_DIR_ROOT) $(RIDGEBACK_TOIL_TMP_DIR_ROOT)

# ~~~~~ Postgres Databse Setup ~~~~~ #
export PGDATA:=$(RIDGEBACK_DB_NAME)
export PGUSER:=$(RIDGEBACK_DB_USERNAME)
export PGPASSWORD:=$(RIDGEBACK_DB_PASSWORD)
export PGHOST:=$(RIDGEBACK_DB_URL)
export PGPORT:=$(RIDGEBACK_PORT)
export PGLOG:=$(LOG_DIR_ABS)/postgres.log
export PGDATABASE:=$(RIDGEBACK_DB_NAME)

$(PGDATA):
	mkdir -p "$(PGDATA)"
db-start:
	pg_ctl -o "-p $(PGPORT)" -D "$(PGDATA)" -l "$(PGLOG)" start
db-stop:
	pg_ctl -D "$(PGDATA)" stop
db-check:
	pg_ctl status

# set up the Postgres instance
db-init: $(PGDATA) $(LOG_DIR_ABS)
	set -x && \
	pg_ctl -D "$(PGDATA)" initdb && \
	pg_ctl -D "$(PGDATA)" -l "$(PGLOG)" start && \
	createdb

# some commands that might be needed to set up a fresh databse:
# echo "DROP USER IF EXISTS $(PGUSER);" > database.sql && \
# echo "CREATE USER $(PGUSER) WITH PASSWORD '$(PGPASSWORD)';" >> database.sql && \
# echo "DROP DATABASE IF EXISTS $(PGDATABASE);" >> database.sql && \
# echo "CREATE DATABASE $(PGDATABASE);" >> database.sql && \
# echo "GRANT ALL PRIVILEGES ON DATABASE $(PGDATABASE) TO $(PGUSER);" >> database.sql && \
# echo "\c $(PGDATABASE);" >> database.sql && \
# psql -f database.sql && \
# pg_ctl -D "$(PGDATA)" stop
# createuser -s $(PGUSER) && \

# interactive Postgres session
db-login:
	psql -U $(PGUSER)

# set up the Django db in Postgres
# do this after setting up the db above
django-init: $(LOG_DIR_ABS) toil-init
	python manage.py makemigrations
	python manage.py migrate
	python manage.py createsuperuser

# ~~~~~~ Celery tasks & RabbitMQ setup ~~~~~ #
# !! need to start RabbitMQ before celery, and both before running app servers !!
export RABBITMQ_CONFIG_FILE:=$(CURDIR)/rabbitmq
export RABBITMQ_NODENAME:=rabbit_$(CURDIR_BASE)
export RABBITMQ_NODE_IP_ADDRESS:=127.0.0.1
export RABBITMQ_NODE_PORT:=5674
export RABBITMQ_LOG_BASE:=$(LOG_DIR_ABS)
export RABBITMQ_LOGS:=rabbitmq.log
export RABBITMQ_PID_FILE:=$(RABBITMQ_LOG_BASE)/rabbitmq.pid
export CELERY_BEAT_PID_FILE:=$(LOG_DIR_ABS)/celery.beat.pid
export CELERY_BEAT_LOGFILE:=$(LOG_DIR_ABS)/celery.beat.log
export CELERY_BEAT_SCHEDULE:=$(LOG_DIR_ABS)/celerybeat-schedule
export CELERY_WORKER_PID_FILE:=$(LOG_DIR_ABS)/celery.worker.pid
export CELERY_WORKER_LOGFILE:=$(LOG_DIR_ABS)/celery.worker.log
export CELERY_BROKER_URL:=amqp://$(RABBITMQ_NODE_IP_ADDRESS):$(RABBITMQ_NODE_PORT)
# https://www.rabbitmq.com/configure.html#supported-environment-variables
# https://www.rabbitmq.com/relocate.html#environment-variables
# https://www.rabbitmq.com/rabbitmq-server.8.html

rabbitmq-start:
	rabbitmq-server -detached
rabbitmq-start-inter:
	rabbitmq-server
rabbitmq-stop:
	rabbitmqctl stop
rabbitmq-check:
	rabbitmqctl status

celery-start:
	celery -A toil_orchestrator beat \
	-l info \
	--pidfile "$(CELERY_BEAT_PID_FILE)" \
	--logfile "$(CELERY_BEAT_LOGFILE)" \
	--schedule "$(CELERY_BEAT_SCHEDULE)" \
	--detach
	celery -A toil_orchestrator worker \
	-l info \
	-Q toil \
	--pidfile "$(CELERY_WORKER_PID_FILE)" \
	--logfile "$(CELERY_WORKER_LOGFILE)" \
	--detach

celery-check:
	-ps auxww | grep 'celery' | grep -v 'grep' | grep -v 'make' | grep "$(CURDIR)"
# ps auxww | grep 'celery worker'

celery-stop:
	ps auxww | grep 'celery' | grep -v 'grep' | grep -v 'make' | grep "$(CURDIR)" | awk '{print $$2}' | xargs kill -9
# you can also just get the PID from the files and kill those;
# head -1 "$(CELERY_PID_FILE)" | xargs kill -9


start-services:
	-$(MAKE) db-start
	$(MAKE) rabbitmq-start
	$(MAKE) celery-start

stop-services:
	$(MAKE) celery-stop
	$(MAKE) rabbitmq-stop
	$(MAKE) db-stop

# ~~~~~ Run ~~~~~ #
export DJANGO_TEST_LOGFILE:=$(LOG_DIR_ABS)/dj_server.log
export DJANGO_RIDGEBACK_IP:=localhost
export DJANGO_RIDGEBACK_PORT:=7001
# start running the Ridgeback server; make sure RabbitMQ and Celery and Postgres are all running first; make start-services
runserver: $(LOG_DIR_ABS)
	python manage.py runserver "$(DJANGO_RIDGEBACK_IP):$(DJANGO_RIDGEBACK_PORT)"

# enter interactive bash session with the Makefile environment set
bash:
	bash

# check the jobs running on Ridgeback
# curl http://localhost:8000/v0/status/
jobs:
	curl "http://$(DJANGO_RIDGEBACK_IP):$(DJANGO_RIDGEBACK_PORT)/v0/jobs/"

# submit a sample job to Ridgeback
submit:
	curl -H "Content-Type: application/json" -X POST --data @fixtures/tests/job.json "http://$(DJANGO_RIDGEBACK_IP):$(DJANGO_RIDGEBACK_PORT)/v0/jobs/"


# check if the ports needed for services and servers are already in use on this system
ifeq ($(UNAME), Darwin)
# On macOS High Sierra, use this command: lsof -nP -i4TCP:$PORT | grep LISTEN
check-port-collision:
	@for i in \
	"RIDGEBACK_PORT:$(RIDGEBACK_PORT)" \
	"RABBITMQ_NODE_PORT:$(RABBITMQ_NODE_PORT)" \
	"DJANGO_RIDGEBACK_PORT:$(DJANGO_RIDGEBACK_PORT)" \
	"PGPORT:$(PGPORT)" ; do ( \
	label="$$(echo $$i | cut -d ':' -f1)" ; \
	port="$$(echo $$i | cut -d ':' -f2)" ; \
	lsof -ni | grep LISTEN | tr -s ' ' | cut -d ' ' -f9 | sed -e 's|.*:\([0-9]*\)$$|\1|g' | sort -u | grep -qw "$$port" && echo ">>> $$label port has a collision; something is already running on port $$port" || : ; \
	) ; done

port-check:
	lsof -i:$(RIDGEBACK_PORT),$(RABBITMQ_NODE_PORT),$(DJANGO_RIDGEBACK_PORT),$(PGPORT) | \
	grep LISTEN
endif

ifeq ($(UNAME), Linux)
check-port-collision:
	@for i in \
	"RIDGEBACK_PORT:$(RIDGEBACK_PORT)" \
	"RABBITMQ_NODE_PORT:$(RABBITMQ_NODE_PORT)" \
	"DJANGO_RIDGEBACK_PORT:$(DJANGO_RIDGEBACK_PORT)" \
	"PGPORT:$(PGPORT)" ; do ( \
	label="$$(echo $$i | cut -d ':' -f1)" ; \
	port="$$(echo $$i | cut -d ':' -f2)" ; \
	ss -lntu | tr -s ' ' | cut -d ' ' -f5 | sed -e 's|.*:\([0-9]*$$\)|\1|g' | sort -u | grep -qw "$$port" && echo ">>> $$label port has a collision; something is already running on port $$port" || : ; \
	) ; done
PORT=
# check if a port is already in use on the system
port-check:
	ss -lntup | grep ':$(PORT)'
endif

export:
	export RIDGEBACK_DB_NAME=db \
	export RIDGEBACK_DB_USERNAME=$(shell whoami) \
	export RIDGEBACK_DB_PASSWORD=admin \
	export RIDGEBACK_DB_URL='/tmp' \
	export RIDGEBACK_PORT=5432 \
	export RIDGEBACK_TOIL_DIR=$(CURDIR)/toil \
	export RIDGEBACK_TOIL_JOB_STORE=$(RIDGEBACK_TOIL_DIR)/job_store \
	export RIDGEBACK_TOIL_JOB_STORE_ROOT=$(RIDGEBACK_TOIL_DIR)/job_store_root \
	export RIDGEBACK_TOIL_WORK_DIR_ROOT=$(RIDGEBACK_TOIL_DIR)/work \
	export RIDGEBACK_TOIL_TMP_DIR_ROOT=$(RIDGEBACK_TOIL_DIR)/tmp \
	export RIDGEBACK_LSF_WALLTIME=100 \
	export RIDGEBACK_LSF_SLA=CMOPI


