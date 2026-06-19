#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

apt-get update
apt-get install -y \
  ffmpeg \
  libsndfile1 \
  portaudio19-dev \
  libportaudio2 \
  libportaudiocpp0 \
  python3-pip

python3 -m pip install --upgrade pip
python3 -m pip install -r "${SCRIPT_DIR}/requirements.txt"
