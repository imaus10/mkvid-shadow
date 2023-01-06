# mkvid-shadow

An open source found footage glitch art music video for the song "Shadow" by DC band [Near Northeast](https://www.instagram.com/nearnortheast/).

![verse 1](/gifs/verse1.gif?raw=true)

![chorus](/gifs/chorus.gif?raw=true)

![verse2](/gifs/verse2.gif?raw=true)

![outro](/gifs/outro.gif?raw=true)

## usage

To "build from source," run:

```
source mkvid.sh
```

*Sometimes* after running, something with the terminal control codes causes my terminal to not show keyboard input...this resets it.

```
stty echo
```

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

- chorus 2: adjust luma/crop
- bridge: elbow luma
- title/credits? (dancers bowing?)
- encoding settings
- pretty up code
- test full process w setup (and time it)
