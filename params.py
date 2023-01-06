from glob import glob
import shlex
import subprocess

import cv2
import numpy as np

from multisubprocess import pipe_subprocess_output


# video output settings
fps = 30
crop = '1280:720'
cropx = '1280x720'
crop_filter = f'scale={crop}:force_original_aspect_ratio=increase, crop={crop}, setsar=1'

def s_to_f(seconds):
    '''
    Convert seconds to number of frames (at static FPS).
    '''
    num_frames = int(seconds * fps)
    return num_frames

def get_frame_count(alignments):
    return sum(list(zip(*alignments))[2])

# song event markers
total_dur = 5*60
total_frames = s_to_f(total_dur)
bpm = 84
beat_dur = 60 / bpm
bar_dur = beat_dur * 4 # in 4/4
bass_synth_start = 20.119
bass_synth_start_frame = s_to_f(bass_synth_start)
guitar_start = 25.446
guitar_start_frame = s_to_f(guitar_start)
verse1_start = 54.375
verse1_start_frame = s_to_f(verse1_start)
chorus1_start = 88.661
chorus1_duration = 4*bar_dur
chorus1_end = chorus1_start + chorus1_duration
verse2_start = 111.5
verse2_duration = 8*bar_dur
chorus2_start = verse2_start + 12*bar_dur
chorus2_duration = chorus1_duration * 2
bridge_start = chorus2_start + chorus2_duration
bridge_violin_start = bridge_start + 4*bar_dur
synth_arp_start = bridge_violin_start + 6*bar_dur
outro_start = synth_arp_start + 8*bar_dur

# stretch the clips to fit the song structure
dancer_alignments = [
    # cut out black at beginning.
    # starts with what looks like VHS static,
    # until bass synth starts...
    [ 10, 7.5, bass_synth_start_frame, '' ],
    # then a stage appears,
    # the stage curtains open while the camera zooms in,
    # and when guitar & drums enter...
    [ 17.5, 4.5, guitar_start_frame - bass_synth_start_frame, '' ],
]
# a figure floats onto the stage ethereally at about half speed...
trim_start = 22
trim_duration = 87.5
dancer_entrance_frame = get_frame_count(dancer_alignments)
stretch_duration_frames = s_to_f(synth_arp_start) - dancer_entrance_frame
dancer_alignments.append(
    [ trim_start, trim_duration, stretch_duration_frames, '' ]
)
# until the synth arp enters
# when we cut to another dancer standing and fidgeting with hands...
trim_start = 3*60 + 58
# align the hand sweep with the start of the violin gesture
hand_gesture = 4*60 + 6.25
trim_duration = hand_gesture - trim_start
violin_gesture = bridge_violin_start + 10*bar_dur
stretch_duration_frames = s_to_f(violin_gesture - synth_arp_start)
dancer_alignments.append(
    [ trim_start, trim_duration, stretch_duration_frames, 'threshold=0:tolerance=0.1:softness=0.2' ]
)
# then back to normal speed...
trim_start = hand_gesture
trim_duration = bar_dur*2
stretch_duration_frames = s_to_f(trim_duration)
dancer_alignments.append(
    [ trim_start, trim_duration, stretch_duration_frames, 'threshold=0:tolerance=0.1:softness=0.2' ]
)
# slow down to half speed during 2-bar lull before outro...
trim_start = hand_gesture + trim_duration
trim_duration = bar_dur/2
stretch_duration_frames = s_to_f(outro_start) - get_frame_count(dancer_alignments)
dancer_alignments.append(
    [ trim_start, trim_duration, stretch_duration_frames, 'threshold=0:tolerance=0.1:softness=0.2' ]
)
# cut to unnaturally sluggish man/woman mirror for the whole outro.
# TODO: for some reason, this starts a frame early.
# s_to_f(outro_start) is 6602 (zero-indexed).
# because ffmpeg outputs frames starting at 1 (one-indexed),
# it should start at 006603.png, but it starts at 006602.png.
# a frame was axed...mystery!!!
# the consequence is that whenever we're dealing with frames
# after the outro, we DO NOT add 1 to the frame number.
trim_start = 8*60 + 35.4
outro_trim_duration = 9.18
outro_frames = total_frames - get_frame_count(dancer_alignments)
dancer_alignments.append(
    [ trim_start, outro_trim_duration, outro_frames, '' ]
)

# video FX markers
fire_trail_start = s_to_f(chorus1_end + 4*bar_dur)
fire_trail_end = s_to_f(chorus2_start - 4*bar_dur)
fire_trail_dur = fire_trail_end - fire_trail_start
fire_trail_memory_fade = 2*bar_dur
fade2_start = bridge_start
fade2_start_frame = s_to_f(fade2_start)
fade2_end = bridge_violin_start
fade2_end_frame = s_to_f(fade2_end)
glitch_start_frame = s_to_f(bridge_violin_start)
bridge_fire_start = s_to_f(synth_arp_start)

# utility functions
def prinnit(it):
    print('*' * 50)
    print(it)
    print('*' * 50)

def ffmpeg(multiline_cmd, alt_binary=None, output_pipe=None, quiet=True, **kwargs):
    quiet_args = ['-v', 'warning'] if quiet else []
    # ffedit doesn't have the -stats arg
    if quiet and alt_binary != 'ffedit':
        quiet_args.append('-stats')
    cmd = [
        alt_binary or 'ffmpeg',
        *quiet_args,
        *shlex.split(multiline_cmd.replace('\n', ''))
    ]

    if output_pipe is None:
        subprocess.run(cmd, check=True)
    else:
        pipe_subprocess_output(cmd, output_pipe, **kwargs)

def ffgac(multiline_cmd, **kwargs):
    ffmpeg(multiline_cmd, alt_binary='ffgac', **kwargs)

def ffedit(multiline_cmd, **kwargs):
    ffmpeg(multiline_cmd, alt_binary='ffedit', **kwargs)

def get_stretch_cmd(duration, stretch_duration_frames, use_minterpolate=False, gradually=False):
    '''
    Get the ffmpeg setpts command to stretch (or compress) the clip to the given duration.
    '''
    # TODO: accept frames or duration
    stretch_duration = stretch_duration_frames / fps
    stretch = stretch_duration / duration
    stretch_cmd = f'setpts={stretch}*(PTS-STARTPTS)'
    if use_minterpolate:
        stretch_cmd = f'minterpolate=mi_mode=mci:fps={int(fps*stretch)}, {stretch_cmd}'
    if gradually:
        # slow it down linearly
        # TODO: why does adding this cause a freeze?
        # minterpolate=mi_mode=mci:fps={int(fps*stretch)}, \\
        stretch_cmd = f"setpts=PTS-STARTPTS, setpts='((T/{stretch_duration}*{stretch-1})+1)*PTS'"
    return stretch_cmd

def get_num_dancer_frames():
    return len(glob('media/frames/dancers/*.png'))

num_wave_frames = None
num_slow_wave_frames = None
# loop the 17 seconds of waves
def get_wave_file(frame_num, is_slow=False):
    if num_wave_frames is None:
        num_wave_frames = len(glob('media/frames/waves/*.png'))
    if num_slow_wave_frames is None:
        num_slow_wave_frames = len(glob('media/frames/waves_slow/*.png'))
    num_frames = num_slow_wave_frames if is_slow else num_wave_frames
    wave_frame = (frame_num % num_frames) + 1
    dir = 'waves'
    if is_slow:
        dir += '_slow'
    return f'media/frames/{dir}/{wave_frame:06d}.png'

def oscillate(value1, value2, pulse_dur, how_many=1, num_frames=None, offset=0):
    num_frames = num_frames or s_to_f(pulse_dur * how_many)
    x = np.arange(num_frames)
    # a tempo-synced sine wave
    pulse_freq = 1/pulse_dur
    x = np.sin(2*np.pi * pulse_freq * (x/fps) + (np.pi/2)*offset)
    # and in the correct range
    pulse_amplitude = abs(value1 - value2) / 2
    return x * pulse_amplitude + (pulse_amplitude + min(value1, value2))

def get_mask(mask_file, as_alpha=False):
    mask = np.load(mask_file)
    mask = np.asarray(mask * 255, dtype='uint8')
    # mask = cv2.bilateralFilter(mask, 10, 75, 75)
    # mask = cv2.dilate(mask, None)
    mask = cv2.blur(mask, (15, 15))
    if as_alpha:
        return mask
    return mask / 255

def apply_mask(mask, foreground, background, is_img=True):
    masked = (foreground*mask) + (background*(1-mask))
    if is_img:
        masked = np.asarray(masked, dtype='uint8')
    return masked
