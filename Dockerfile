# STAGE: get the emulator tarball and inflate it which will be used in another stage
FROM debian:buster-slim as mpeg-dash-server
RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --allow-unauthenticated --no-install-recommends \
        wget \
        iproute2 \
        iputils-ping \
        python2.7-minimal \
        python-argparse \
        python-pip \
        python-setuptools \
        python-dev \
        liblzma-dev \
        libmagic1 \
        libc6-dbg:i386 \
        gcc \
        iptables \
        tcpdump \
        uml-utilities \
        bridge-utils \
        busybox \
    && /bin/busybox --install \
    && rm -rf /var/lib/apt/lists/*

# install python packages
COPY /python/requirements.txt /requirements.txt
RUN pip install --upgrade pip==19.2.2
RUN pip install -r /requirements.txt
COPY /entrypoint.sh /entrypoint.sh
COPY /wondershaper /wondershaper
COPY /python /python
COPY /dash_contents /dash_contents

ENTRYPOINT ["/entrypoint.sh"]