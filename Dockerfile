FROM python:3.13-slim

LABEL org.opencontainers.image.vendor="MSKCC" \
      org.opencontainers.image.authors="Nikhil Kumar (kumarn1@mskcc.org)" \
      org.opencontainers.image.created="2026-11-12T16:04:00Z" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.source="https://github.com/mskcc/ridgeback" \
      org.opencontainers.image.title="Ridgeback" \
      org.opencontainers.image.description="API for running Toil and Nextflow jobs, supports LSF, SLURM, and singleMachine mode"

ENV DEBIAN_FRONTEND noninteractive
ENV PIP_ROOT_USER_ACTION ignore
ENV PIP_BREAK_SYSTEM_PACKAGES 1
COPY requirements.txt /app/data/requirements.txt
COPY requirements-toil.txt /app/data/requirements-toil.txt

RUN apt-get update \
     # Install dependencies
        && apt-get -y --no-install-recommends install \
            wget curl libldap2-dev libsasl2-dev procps libssl-dev libxml2-dev libxslt-dev \
            libpq-dev gawk nodejs git build-essential openssh-client \
        && pip install --upgrade pip \
        && pip install -r /app/data/requirements.txt \
        && pip install -r /app/data/requirements-toil.txt \
    # Clean up image
        && apt-get -y purge --auto-remove build-essential \
        && apt-get -y --no-install-recommends install openssh-client \
        && rm -rf /var/lib/apt/lists/*


