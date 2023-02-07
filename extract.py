from glob import glob
import os
import shutil
import subprocess
from tqdm import tqdm, trange

from params import *
from segment import save_dancer_masks


def extract_dancer_frames(align_test=False):
    if os.path.exists('media/frames/dancers'):
        return
    prinnit('Extracting frames from the dancer video...')
    subprocess.run('mkdir -p media/frames/dancers', check=True, shell=True)

    frame_count = 1
    for i, cut_params in enumerate(tqdm(dancer_alignments)):
        start_time, duration, stretch_duration_frames, *more_params = cut_params
        more_params = more_params[0] if more_params else {}
        if i < len(dancer_alignments)-1:
            frame_count += stretch_duration_frames
            continue

        overlay = ''
        if 'lumakey' in more_params:
            lumakey_params = more_params['lumakey']
            overlay = f'lumakey={lumakey_params} [overlay{i}]; [1:v][overlay{i}] overlay=shortest=1,'
            del more_params['lumakey']

        stretch_cmd = get_stretch_cmd(
            duration,
            stretch_duration_frames,
            **more_params
        )

        ffmpeg(f'''
          -ss {start_time} -i media/dancers.mp4
          -f lavfi -i "color=black:s=640x480:r=30"
          -filter_complex
           "{stretch_cmd}, fps={fps},
            trim=end_frame={stretch_duration_frames},
            {overlay} {dancers_crop_filter}"
          -start_number {frame_count} "media/frames/dancers/%06d.png"
        ''')
        frame_count += stretch_duration_frames
        actual_frame_count = len(glob('media/frames/dancers/*.png'))
        assert actual_frame_count == frame_count-1

    # COLLECT DANCER POSE MASKS
    # do this before luma because pose segmentation
    # works better on original images
    save_dancer_masks()

    prinnit('Applying lumakey to outro dancers...')
    ffmpeg(f'''
      -start_number {s_to_f(outro_start)+1} -i "media/frames/dancers/%06d.png"
      -vf "lumakey=threshold=0:tolerance=0.15:softness=0.1"
      -start_number {s_to_f(outro_start)+1} "media/frames/dancers/%06d.png"
    ''')

    # for the outro, overlay the man/woman mirror dancers on top of slow waves
    # (to provide new colors to glitch, since it goes totally pink without new iframes...)
    # 2 beats of waves every 4 bars
    # but the last 8 bars are left to glitch fully pink
    wave_frames = s_to_f(beat_dur*2)
    waves_freq = bar_dur*4
    num_waves = 4

    prinnit('Adding waves to outro...')
    pbar = tqdm(total=num_waves*wave_frames)
    for wave_num in range(num_waves):
        waves_start_frame = s_to_f(outro_start + waves_freq*(wave_num+1)) + 1
        # prevent waves coming thru transparent bodies
        for i in range(wave_frames):
            frame_num = waves_start_frame + i
            in_path = f'media/frames/dancers/{frame_num:06d}.png'
            out_path = in_path
            dancers = cv2.imread(in_path, cv2.IMREAD_UNCHANGED)
            # apply the luma's alpha channel so the color doesn't jump
            luma_mask = dancers[:,:,3] / 255
            dancers = dancers * np.stack((luma_mask,)*4, axis=-1)
            # then use the pose segmentation mask as a new alpha
            pose_mask = get_mask(f'media/frames/dancers_mask/{frame_num:06d}.npy', as_alpha=True)
            dancers[:,:,3] = pose_mask
            cv2.imwrite(out_path, dancers)
            pbar.update()
    loop_frames = s_to_f(waves_freq)
    ffmpeg(f'''
      -i "media/frames/waves_slow/%06d.png"
      -start_number {s_to_f(outro_start)+1} -i "media/frames/dancers/%06d.png"
      -f lavfi -i "color=black:s={cropx}"
      -filter_complex
       "[0:v]
          trim=end_frame={wave_frames},
          tpad=stop={loop_frames-wave_frames+1},
          loop=loop={num_waves-1}:size={loop_frames+1},
          tpad=start={loop_frames}:stop=-1
        [waves];
        [waves][1:v] overlay=shortest=1 [waves_overlay]"
      -map [waves_overlay] -start_number {s_to_f(outro_start)+1} "media/frames/dancers/%06d.png"
    ''')

    if align_test:
        prinnit('Making align test...')
        ffmpeg(f'''
          -framerate {fps} -i "media/frames/dancers/%06d.png"
          -i media/shadow.wav
          -map 0:v -map 1:a -shortest
          -c:v libx264 -pix_fmt yuv420p
          -y media/align_test.mp4
        ''')


def extract_fire_frames():
    if os.path.exists('media/frames/fire'):
        return

    prinnit('Extracting frames from the fire video...')
    subprocess.run('mkdir -p media/frames/fire', check=True, shell=True)
    # on the 2nd verse,
    # the fire flashes brightly with the guitar crashes
    # and dims as they fade
    fade = fire_trail_memory_fade
    ffmpeg(f'''
      -i media/fire.mp4
      -vf "trim=duration={total_dur}, {crop_filter}, fps={fps}"
      "media/frames/fire/%06d.png"
    ''')

    prinnit('Flashing and fading the fire brightness for verse 2...')
    subprocess.run('mkdir -p media/frames/fire_trail', check=True, shell=True)
    ffmpeg(f'''
      -framerate {fps} -start_number {fire_trail_start+1} -i "media/frames/fire/%06d.png"
      -vf
        "trim=end_frame={fire_trail_dur},
         eq=brightness='0.5 - 0.75*mod(n,{fade}*r)/({fade}*r)':eval=frame"
      -start_number {fire_trail_start+1} "media/frames/fire_trail/%06d.png"
    ''')

    prinnit('Making random fire flickers for bridge...')
    subprocess.run('mkdir -p media/frames/fire_bridge', check=True, shell=True)
    black_frame = np.zeros((720, 1280, 3), dtype='uint8')
    # ramp up to when song drops off
    fire_frames_up_slow = s_to_f(5*bar_dur)
    fire_frames_up_fast = s_to_f(1*bar_dur)
    no_fire_frames = s_to_f(outro_start) - bridge_fire_start
    is_fire = np.concatenate((
        np.random.random(fire_frames_up_slow) < np.linspace(0, 0.1, num=fire_frames_up_slow),
        np.random.random(fire_frames_up_fast) < np.linspace(0.1, 0.5, num=fire_frames_up_fast),
        np.full(no_fire_frames, False)
    ))
    for i in trange(len(is_fire)):
        frame_num = i + bridge_fire_start + 1
        in_path = f'media/frames/fire/{frame_num:06d}.png'
        out_path = f'media/frames/fire_bridge/{i+1:06d}.png'
        if is_fire[i]:
            shutil.copyfile(inpath, outpath)
        else:
            cv2.imwrite(out_path, black_frame)


def extract_wave_frames():
    for is_slow in (False, True):
        postfix = '_slow' if is_slow else ''
        filepath = f'media/frames/waves{postfix}'
        if os.path.exists(filepath):
            continue
        prinnit(f'Extracting frames from the waves video to {filepath}...')
        subprocess.run(f'mkdir -p {filepath}', check=True, shell=True)

        waves_input = '-ss 144.5 -i media/waves.mp4'
        trim_cmd = 'duration=17,'
        waves_output = f'"{filepath}/%06d.png"'

        if is_slow:
            # slow down the video before cropping
            # because otherwise it takes a loooong-ass time
            slow_down = 100 # make the footage down this many times slower
            slow_down1_duration = fade2_end - fade2_start
            slow_down1_frames = fade2_end_frame - fade2_start_frame
            slow_down2_duration = synth_arp_start - fade2_end
            slow_down2_frames = s_to_f(synth_arp_start) - fade2_end_frame
            ffmpeg(f'''
              {waves_input}
              -filter_complex
                "[0:v]
                   {trim_cmd} minterpolate=mi_mode=mci:fps={fps*slow_down}, split=2
                 [waves1][waves2];
                 [waves1]
                   setpts='((T/{slow_down1_duration}*{slow_down-1})+1)*PTS',
                   fps={fps}, trim=start_frame=0:end_frame={slow_down1_frames}
                 [waves_slow1];
                 [waves2]
                   setpts='((T/{slow_down2_duration}*{slow_down-1})+1)*PTS',
                   fps={fps}, trim=start_frame=0:end_frame={slow_down2_frames}
                 [waves_slow2];
                 [waves_slow1][waves_slow2]
                   concat=n=2:v=1:a=0
                 [outv]"
              -map [outv] {waves_output}
            ''')
            waves_input = f'-framerate {fps} -i {waves_output}'
            trim_cmd = ''

        ffmpeg(f'''
          {waves_input}
          -vf "{trim_cmd} crop=480:352:80:4, {crop_filter}, fps={fps}"
          {waves_output}
        ''')
