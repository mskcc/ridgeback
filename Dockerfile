FROM ubuntu:22.04

LABEL maintainer="Nikhil Kumar (kumarn1@mskcc.org)" \
      version.image="1.0.0" \
      source.ridgeback="https://github.com/mskcc/ridgeback"

ENV DEBIAN_FRONTEND noninteractive
ENV RIDGEBACK_BRANCH master

RUN apt-get clean && apt-get update -qq \
    # Install dependencies
    && apt-get -y install \
        python3 python3-dev python3-pip python3-virtualenv wget \
        libldap2-dev libsasl2-dev libssl-dev libxml2-dev libxslt-dev \
        postgresql postgresql-contrib libpq-dev \
        gawk build-essential nodejs \
        git \
        default-jdk \
    && cd /usr/bin \
    # Install Ridgeback
    && git clone https://github.com/mskcc/ridgeback --branch $RIDGEBACK_BRANCH \
    && cd /usr/bin/ridgeback \
    # Install python packages
    && pip3 install --upgrade pip \
    && python3 -m pip install python-ldap \
    && pip3 install setuptools==57.5.0 \
    && pip install "cython<3.0.0" wheel \
    && pip install "pyyaml==5.4.1" --no-build-isolation \
    && pip3 install -r requirements.txt \
    && pip3 install -r requirements-toil.txt