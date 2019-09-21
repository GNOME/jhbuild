FROM ubuntu:disco

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    apt-file \
    autoconf \
    automake \
    autopoint \
    gettext \
    git \
    libtool \
    make \
    patch \
    pkg-config \
    python \
    python-flake8 \
    python-pytest \
    python3 \
    python3-flake8 \
    python3-pytest \
    sudo \
    trang \
    yelp-tools

RUN useradd -u 1000 -ms /bin/bash user
RUN echo 'user ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
USER user

ENV LANG C.UTF-8
