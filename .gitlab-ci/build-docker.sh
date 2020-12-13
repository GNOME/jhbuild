#!/bin/bash

set -e

TAG="registry.gitlab.gnome.org/gnome/jhbuild/jhbuild:v5"

sudo docker build --tag "${TAG}" --file "Dockerfile" .