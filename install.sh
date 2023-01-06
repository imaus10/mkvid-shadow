#!/usr/bin/env bash

HOMEBREW_NO_AUTO_UPDATE=1 brew install ffmpeg p7zip
curl -O https://ffglitch.org/pub/bin/mac64/ffglitch-0.9.4-mac64.7z
7za x ffglitch-0.9.4-mac64.7z
export PATH=$PATH:ffglitch-0.9.4-mac64
python3 -m venv .venv
source .venv/bin/activate
pip install youtube-dl mediapipe tqdm
