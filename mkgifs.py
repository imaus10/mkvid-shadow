import subprocess

from params import ffmpeg

# modified from https://github.com/happyhorseskull/you-can-datamosh-on-linux/blob/master/video_to_gif.py
# with advice on reducing gif size from https://superuser.com/a/1695537
if __name__ == '__main__':
    gif_dir = 'gifs'
    subprocess.run(f'mkdir -p {gif_dir}', check=True, shell=True)

    gifs = [
        ('verse1', 77, 5, 10),
        # this one has the flickers so we want full framerate
        ('chorus', 89, 6, 30),
        ('verse2', 117, 6, 10),
        ('outro', 220, 11, 10),
    ]
    for filename, start, duration, fps in gifs:
        filters = f''
        ffmpeg(f'''
          -ss {start} -t {duration} -i media/shadow10.mp4
          -filter_complex
           "fps={fps}, scale=480:-1:flags=lanczos, split [img1][img2];
            [img1] palettegen=max_colors=32 [palette];
            [img2][palette] paletteuse=dither=bayer"
          -y {gif_dir}/{filename}.gif
        ''')
