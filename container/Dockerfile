FROM ubuntu:18.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y software-properties-common gcc && \
    add-apt-repository -y ppa:deadsnakes/ppa

RUN apt install -y wget build-essential checkinstall
RUN apt install -y libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev
RUN apt install -y curl

WORKDIR /opt
RUN wget https://www.python.org/ftp/python/3.9.16/Python-3.9.16.tgz

RUN tar xzf Python-3.9.16.tgz
WORKDIR Python-3.9.16

RUN ./configure --enable-optimizations
RUN make install
RUN rm -f /opt/Python-3.9.6.tgz

RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && python3 get-pip.py
