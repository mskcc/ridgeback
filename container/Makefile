SHELL:=/bin/bash
define help
This is the Makefile for building the Singularity container

On Mac
-------
Use Docker to build the Singularity container:

make singularity-build-docker


On Juno HPC
-----------
make singularity-build

endef
export help
help:
	@printf "$$help"

.PHONY : help

# build the singularity container using Docker
export DOCKERTAG:=singularityware/singularity:v3.3.0
export SINGULARITYENV_RIDGEBACK_BRANCH=develop
export SINGULARITYDIR:=$(CURDIR)
singularity-build-docker:
	docker run \
	--privileged \
	--rm \
	-ti \
	-v "$(SINGULARITYDIR):/image" "$(DOCKERTAG)" \
	build /image/celery_services.sif /image/celery_services.def

# on Juno HPC
singularity-build:
	module load singularity/3.3.0 && \
	sudo -E singularity build ridgeback_service.sif ridgeback_service.def
