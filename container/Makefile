SHELL:=/bin/bash

# build the Docker container with Singularity in it
export DOCKERTAG:=singularity-3.3.0
singularity-docker-container-build:
	cd Singularity-3.3.0 && \
	docker build -t "$(DOCKERTAG)" .

# build the singularity container
# on HPC: module load singularity/3.3.0 &&
export SINGULARITYENV_RIDGEBACK_BRANCH=develop
export SINGULARITYDIR:=$(CURDIR)
singularity-build-docker:
	docker run \
	--privileged \
	--rm \
	-ti \
	-v "$(SINGULARITYDIR):/image" "$(DOCKERTAG)" \
	bash -c 'cd /image && singularity build ridgeback_service.sif ridgeback_service.def'

singularity-build:
	sudo -E singularity build ridgeback_service.sif ridgeback_service.def
