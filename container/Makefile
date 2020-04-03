SHELL:=/bin/bash

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
	build /image/ridgeback_service.sif /image/ridgeback_service.def

# on HPC: module load singularity/3.3.0 &&
singularity-build:
	sudo -E singularity build ridgeback_service.sif ridgeback_service.def
