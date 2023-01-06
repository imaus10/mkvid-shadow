#!/usr/bin/env bash

mkdir -p media
curl -o media/dancers.mp4 https://ia802308.us.archive.org/33/items/csfpal_000175/csfpal_000175_access.mp4
curl -o media/waves.mp4 https://archive.org/download/waves_20161117/waves_20161117.mp4
youtube-dl -f 137 -o media/fire.mp4 https://www.youtube.com/watch?v=VzR9Fbs8Cs0
youtube-dl -f 137 -o media/mushroom_timelapse.mp4 https://www.youtube.com/watch?v=VTNYjHYjYPU
