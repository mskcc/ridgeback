FROM python:3.10-slim

LABEL maintainer="Nikhil Kumar (kumarn1@mskcc.org)" \
      version.image="1.0.0" \
      source.ridgeback="https://github.com/mskcc/ridgeback"

ENV DEBIAN_FRONTEND noninteractive
ENV PIP_ROOT_USER_ACTION ignore
ENV PIP_BREAK_SYSTEM_PACKAGES 1
ENV RIDGEBACK_BRANCH feature/IRIS_update

RUN apt-get update \
     # Install dependencies
        && apt-get -y --no-install-recommends install \
            wget curl libldap2-dev libsasl2-dev libssl-dev libxml2-dev libxslt-dev \
            libpq-dev gawk nodejs git build-essential \
     # Install Ridgeback
        && cd /usr/bin \
        && git clone https://github.com/mskcc/ridgeback --branch $RIDGEBACK_BRANCH \
        && cd /usr/bin/ridgeback \
     # Install python packages
        && pip3 install --upgrade pip \
        && pip3 install python-ldap setuptools==57.5.0 \
        && pip3 install "pyyaml==5.4.1" --no-build-isolation \
        && pip3 install -r requirements.txt \
        && pip3 install -r requirements-toil.txt \
    # Clean up image
        && apt-get -y purge --auto-remove build-essential \
        && rm -rf /var/lib/apt/lists/*


