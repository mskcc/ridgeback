FROM python:3.10-slim

LABEL org.opencontainers.image.vendor="MSKCC" \
      org.opencontainers.image.authors="Nikhil Kumar (kumarn1@mskcc.org)" \
      org.opencontainers.image.created="2025-09-15T16:04:00Z" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.source="https://github.com/mskcc/ridgeback" \
      org.opencontainers.image.title="Ridgeback" \
      org.opencontainers.image.description="API for running Toil and Nextflow jobs, supports LSF, SLURM, and singleMachine mode"

ENV DEBIAN_FRONTEND noninteractive
ENV PIP_ROOT_USER_ACTION ignore
ENV PIP_BREAK_SYSTEM_PACKAGES 1
ENV RIDGEBACK_BRANCH feature/IRIS_update

RUN apt-get update \
     # Install dependencies
        && apt-get -y --no-install-recommends install \
            wget curl libldap2-dev libsasl2-dev procps libssl-dev libxml2-dev libxslt-dev \
            libpq-dev gawk nodejs git build-essential openssh-client \
     # Install Ridgeback
        && git clone https://github.com/mskcc/ridgeback --branch $RIDGEBACK_BRANCH /usr/bin/ridgeback\
     # Install alternative ssl library
        && wget http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2_amd64.deb \
        && dpkg -i libssl1.1_1.1.1f-1ubuntu2_amd64.deb \
      # Install libffi6 for TOIL
        && wget http://archive.ubuntu.com/ubuntu/pool/main/libf/libffi/libffi6_3.2.1-8_amd64.deb \
        && dpkg -i libffi6_3.2.1-8_amd64.deb \
     # Install python packages
        && pip3 install --upgrade pip \
        && pip3 install python-ldap \
        && pip3 install --use-pep517 -r /usr/bin/ridgeback/requirements.txt \
        && pip3 install --use-pep517 -r /usr/bin/ridgeback/requirements-toil.txt \
    # Clean up image
        && rm -rf /var/lib/apt/lists/*


