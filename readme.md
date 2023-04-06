# mkvid-shadow

An open source found footage glitch art music video for the song "Shadow" by DC band [Near Northeast](https://www.instagram.com/nearnortheast/).

![verse 1](/gifs/verse1.gif?raw=true)

![chorus](/gifs/chorus.gif?raw=true)

![verse2](/gifs/verse2.gif?raw=true)

![outro](/gifs/outro.gif?raw=true)

## usage

To generate the video, run:

```
source mkvid.sh
```

This will download the video sources, set up the environment, install all the required libraries (except the prereqs below, which you must install), and create the video.

## prereqs

This was built for MacOS. If you're using another OS, you'll likely need to change some things.

- python3 (I'm using 3.9)
- [homebrew](https://brew.sh/)

## credits

### video

- [dancers](https://archive.org/details/csfpal_000175)
- [wildfire](https://www.youtube.com/watch?v=VzR9Fbs8Cs0)
- [waves](https://archive.org/details/waves_20161117)
- [mushroom timelapse](https://www.youtube.com/watch?v=VTNYjHYjYPU) (motion vectors for outro glitch)

### code

- [ffmpeg](https://ffmpeg.org/): video editing
- [mediapipe](https://google.github.io/mediapipe/): pose segmentation
- [ffglitch](https://ffglitch.org/): motion transfer

## TODO

- align dancer entrance jump
- encoding settings? (https://trac.ffmpeg.org/wiki/Encode/H.264)
- test full process w setup (and time it)
