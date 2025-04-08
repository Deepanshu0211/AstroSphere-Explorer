#!/usr/bin/env bash

# install portaudio
apt-get update
apt-get install -y portaudio19-dev

# continue normal build
pip install -r requirements.txt
