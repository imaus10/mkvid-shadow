from multiprocessing import freeze_support, set_start_method
import os
import shutil
import subprocess

from tqdm import trange

from credits import *
from extract import *
from glitch import *
from params import *


def interweave():
    if os.path.exists('media/frames/interweaved'):
        return
    prinnit('Interweaving fire, wave masking, randomizing...')
    subprocess.run('mkdir -p media/frames/interweaved', check=True, shell=True)

    # sometimes the real value does not equal the theoretical value...
    total_frames = get_num_dancer_frames()

    dancer_frames_start = 60
    dancer_frames_slow = 30
    dancer_frames_fast = 3

    # once the verse enters,
    # move the dancer into random chaos and back out in one verse, peaking at...
    random_bars = 12
    # the maximum random radius of frames around the current frame
    max_deviation = 15

    fire_sections = [
        # start with infrequent fire frames, increasing linearly up to stage reveal, then disappear
        [ 0, np.linspace(dancer_frames_start, dancer_frames_slow, num=s_to_f(bass_synth_start)).astype(int), 1 ],
        # reappear at chorus, oscillate to high intensity two times
        [ chorus1_start, oscillate(dancer_frames_slow, dancer_frames_fast, chorus1_duration / 2, how_many=2, offset=1).astype(int), 1 ],
        # same at 2nd chorus (twice length)
        [ chorus2_start, oscillate(dancer_frames_slow, dancer_frames_fast, chorus1_duration / 2, how_many=4, offset=1).astype(int), 1 ],
    ]

    # after verse, oscillate random dancer deviation
    total_random_frames = total_frames - verse1_start_frame
    deviation_radius = oscillate(0, max_deviation, bar_dur * random_bars, num_frames=total_random_frames, offset=-1)
    deviation_radius = np.rint(deviation_radius)
    random_deviation = np.random.rand(total_random_frames) * deviation_radius*2 - deviation_radius
    random_deviation = random_deviation.astype(int)

    # use the dancer mask
    mask_start_frame = guitar_start_frame + s_to_f(bar_dur*4)
    # to fade out background by verse start
    fade1_end_frame = verse1_start_frame
    mask_fade1_pct = np.linspace(1, 0, num=fade1_end_frame - mask_start_frame)
    # fade in waves over dancer by verse start
    waves_fade_in1_pct = np.linspace(0, 1, num=fade1_end_frame - dancer_entrance_frame)
    mask_fade2_pct = np.linspace(0, 0.9, num=fade2_end_frame - fade2_start_frame)

    # on the 2nd verse, make a fire motion trail
    dancer_motion_history = np.empty((720,1280,0))
    # the trail is at most a bar
    fire_trail_max_memory = s_to_f(bar_dur)
    # and it fades out
    fire_trail_decay = (
        np.arange(fire_trail_max_memory, 0, -1) / fire_trail_max_memory
    ).reshape((1,1,-1))
    # but it grows with the guitar crashes and shrinks as they fade
    fire_trail_memory = oscillate(
        0, fire_trail_max_memory, fire_trail_memory_fade,
        num_frames=fire_trail_dur, offset=-1
    ).astype(int)

    fire_section = 0
    for frame_num in trange(total_frames):
        out_frame = frame_num+1
        in_file = f'{out_frame:06d}.png'
        out_file = f'media/frames/interweaved/{in_file}'
        fire_frame = f'media/frames/fire/{in_file}'

        fire_section_start, dancer_rates, num_fire_frames = fire_sections[fire_section]
        fire_section_start_frame = s_to_f(fire_section_start)
        fire_section_end_frame = fire_section_start_frame + len(dancer_rates)
        is_fire_section = frame_num >= fire_section_start_frame and frame_num < fire_section_end_frame
        if is_fire_section:
            if frame_num == fire_section_start_frame:
                dancer_frame_count = 0
                fire_frame_count = 0
            if frame_num == fire_section_end_frame - 1 and fire_section + 1 < len(fire_sections):
                fire_section += 1

            num_dancer_frames = dancer_rates[frame_num - fire_section_start_frame]
            is_fire = dancer_frame_count >= num_dancer_frames
            if is_fire:
                fire_frame_count += 1
                if fire_frame_count >= num_fire_frames:
                    dancer_frame_count = 0
                    fire_frame_count = 0
                shutil.copyfile(fire_frame, out_file)
                continue

            dancer_frame_count += 1

        # before dancer enters,
        # and after cut to multiple dancers,
        # just copy the original image
        dancer_file = f'media/frames/dancers/{in_file}'
        if frame_num < dancer_entrance_frame or frame_num >= s_to_f(synth_arp_start):
            shutil.copyfile(dancer_file, out_file)
            continue

        # after dancer enters, blend waves with dancer
        if frame_num < fade2_end_frame:
            if frame_num < fade2_start_frame:
                wave_file = get_wave_file(frame_num - dancer_entrance_frame)
            else:
                wave_file = get_wave_file(frame_num - fade2_start_frame, is_slow=True)
            waves = cv2.imread(wave_file)
            if frame_num < fade1_end_frame:
                dancer_original = cv2.imread(dancer_file)
                waves_pct = waves_fade_in1_pct[frame_num - dancer_entrance_frame]
                dancer = cv2.addWeighted(waves, waves_pct, dancer_original, 1 - waves_pct, 0)
            else:
                dancer = waves
        else:
            dancer = cv2.imread(dancer_file)

        # before we have the dancer mask, just write the blended image
        if frame_num < mask_start_frame:
            cv2.imwrite(out_file, dancer)
            continue

        # at the first verse, start choosing dancer masks randomly
        # within a window around the playhead
        if frame_num < verse1_start_frame:
            mask_frame = frame_num
        else:
            dancer_deviation = random_deviation[frame_num - verse1_start_frame]
            mask_frame = frame_num + dancer_deviation
            mask_frame = max(mask_frame, 0)
            mask_frame = min(mask_frame, total_frames)
        mask_file = f'media/frames/dancers_mask/{mask_frame+1:06d}.npy'

        # after we have a mask...
        if os.path.exists(mask_file):
            mask = get_mask(mask_file)
            # if the pose wasn't found, use the last mask available
            last_mask = mask
        # fade out the background
        is_fade1 = frame_num < fade1_end_frame
        is_fade2 = fade2_start_frame <= frame_num < fade2_end_frame
        if is_fade1 or is_fade2:
            if is_fade1:
                background_pct = mask_fade1_pct[frame_num - mask_start_frame]
            else:
                background_pct = mask_fade2_pct[frame_num - fade2_start_frame]
            background_fade = np.full(last_mask.shape, background_pct)
            mask_fade_in = np.clip(last_mask + background_pct, 0, 1)
            mask = apply_mask(last_mask, mask_fade_in, background_fade, is_img=False)
        else:
            mask = last_mask

        # on the 2nd verse, make a fire motion trail
        has_fire_trail = fire_trail_start <= frame_num < fire_trail_end
        if has_fire_trail:
            trail_len = min(
                fire_trail_memory[frame_num - fire_trail_start],
                dancer_motion_history.shape[2]
            )
            if trail_len < 1:
                has_fire_trail = False
            else:
                trail = dancer_motion_history[:,:,:trail_len]
                decay = fire_trail_decay[:,:,:trail_len]
                motion_mask = trail * decay
                motion_mask = np.amax(motion_mask, axis=2)
                # let the dancer come thru
                motion_mask = (1-mask) * motion_mask
                motion_mask = np.stack((motion_mask,)*3, axis=-1)
            dancer_motion_history = np.dstack((mask, dancer_motion_history))
            if dancer_motion_history.shape[2] > fire_trail_max_memory:
                dancer_motion_history = dancer_motion_history[:,:,:fire_trail_max_memory]

        mask = np.stack((mask,)*3, axis=-1)
        # after fade, overlay dancer directly on waves
        if frame_num >= fade2_end_frame:
            wave_file = get_wave_file(frame_num - fade2_start_frame, is_slow=True)
            waves = cv2.imread(wave_file)
            dancer_final = apply_mask(mask, dancer, waves)
        else:
            dancer_final = np.asarray(dancer * mask, dtype='uint8')

        if has_fire_trail:
            fire = cv2.imread(f'media/frames/fire_trail/{in_file}')
            dancer_final = apply_mask(motion_mask, fire, dancer_final)

        cv2.imwrite(out_file, dancer_final)


def overlay():
    if os.path.exists('media/glitch_input.avi'):
        return
    prinnit('Adding dancer overlays and encoding frames for glitching...')
    # add group dances over the 1st/2nd chorus and bridge using lumakey
    # end on the curtain close
    elbow_dancers_end = 17*60 + 21
    # start with violin and last until the 1-bar violin plucks
    elbow_dancers_duration = outro_start - 1*bar_dur - bridge_violin_start
    elbow_dancers_start = elbow_dancers_end - elbow_dancers_duration
    group_dancers_overlays = [
        [
            971, chorus1_duration, chorus1_start,
            'tolerance=0.03:softness=0.2', ''
        ],
        [
            894.25, chorus2_duration, chorus2_start,
            'tolerance=0.03:softness=0.2', ''
        ],
        [
            elbow_dancers_start, elbow_dancers_duration, bridge_violin_start,
            'tolerance=0.1:softness=0.2', f'fade=in:st=0:d={3*bar_dur}:alpha=1,'
        ],
    ]
    split_outputs = ''
    overlay_cmds = []
    last_overlay = '[1:v]'
    for i, params in enumerate(group_dancers_overlays):
        trim_start, trim_duration, overlay_start, lumakey_params, xtra_filter = params
        trim_input = f'[dancers{i}]'
        overlay_output = f'[dancers{i}overlay]'
        overlay_cmd = f'''{trim_input}
            trim=start={trim_start}:duration={trim_duration}, setpts=PTS-STARTPTS,
            {dancers_crop_filter}, fps={fps},
            lumakey=threshold=0:{lumakey_params},
            {xtra_filter}
            tpad=start_duration={overlay_start}
        [dancers{i}trim];
        {last_overlay}[dancers{i}trim]
            overlay=enable='between(t,{overlay_start},{overlay_start+trim_duration})':eof_action=pass
        {overlay_output}'''
        split_outputs += trim_input
        last_overlay = overlay_output
        overlay_cmds.append(overlay_cmd)

    overlay_cmds = ';\n        '.join(overlay_cmds)
    ffmpeg(f'''
      -i media/dancers.mp4
      -framerate {fps} -i "media/frames/interweaved/%06d.png"
      -filter_complex
       "[0:v] split={len(group_dancers_overlays)} {split_outputs};
        {overlay_cmds}"
      -map {last_overlay} -c:v libxvid -q:v 1 -g 1000 -qmin 1 -qmax 1 -flags qpel+mv4
      media/glitch_input.avi
    ''')


def recombine():
    prinnit('Recombining glitched 2nd half, adding bridge fire, audio, and opening titles/credits...')
    metadata_description = f'''
        An open source music video for Near Northeast by Austin Blanton (aka Art Fungus).
    '''
    ffmpeg(f'''
      -i media/glitch_output.avi
      -framerate {fps} -i "media/frames/fire_bridge/%06d.png"
      -framerate {fps} -i "media/frames/outro_masked/%06d.png"
      -f lavfi -i "color=black:s=1280x720"
      -ss 00:02:19 -i media/mushroom_timelapse.mp4
      -i media/shadow.wav
      -filter_complex
       "[0:v] split=3 [a][b][c];
        [a]
          trim=duration=15,
          {add_opening_titles()}
        [opening_titles];
        [b] trim=start=15:end_frame={bridge_fire_start}, setpts=PTS-STARTPTS [prebridge];
        [c]
          trim=start_frame={bridge_fire_start}:end_frame={s_to_f(outro_start)},
          setpts=PTS-STARTPTS,
          lumakey=threshold=0:tolerance=0.1:softness=0.01
        [bridge_luma];
        [1:v] eq=brightness='if(lt(n,{s_to_f(6*bar_dur)}), n/(r*{6*bar_dur})*0.5-0.5)':eval=frame [fire];
        [fire][bridge_luma] overlay=shortest=1 [bridge];
        {add_credits()};
        [opening_titles][prebridge][bridge][outro_credits] concat=n=4:v=1:a=0 [outv];
        [5:a]
          aloop=loop=15:start=44100*({total_dur}-1):size=44100,
          afade=type=out:start_time={total_dur+5}:duration=10
        [outa]"
      -map [outv] -map [outa]
      -c:v libx264 -pix_fmt yuv420p -r {fps}
      -metadata title="Near Northeast - Shadow"
      -metadata description="{metadata_description}"
      media/shadow11.mp4
    ''')


def mkvid():
    # EXTRACT FRAMES
    extract_fire_frames()
    extract_wave_frames()
    extract_dancer_frames()#align_test=True)
    # INTERWEAVE FIRE FRAMES,
    # FADE WAVES INTO DANCER,
    # RANDOMIZE DANCER MASKS
    interweave()
    # OVERLAY GROUP DANCERS
    overlay()
    # GLITCH BRIDGE AND OUTRO
    remove_iframes()
    add_mushroom_motion()
    overlay_dancers_on_mushroom_motion()
    # FINAL OUTPUT
    recombine()

    # TODO: clean up
    # subprocess.run('rm -r media/frames', check=True, shell=True)
    # rm media/outro_cut0.mp4 media/outro_cut1.mp4 media/outro_mushroom_motion0.mpg media/outro_mushroom_motion1.mpg media/shadow_glitch_input.avi media/shadow_glitch_output.avi
    # rm -r media/frames/interweaved/ media/frames/outro_dancer_glitch/ media/frames/outro_masked/ media/frames/outro_mushroom_motion/


if __name__ == '__main__':
    freeze_support()
    set_start_method('spawn')
    mkvid()
    # something with the terminal control codes
    # causes my terminal to not show keyboard input...
    # this resets it.
    subprocess.run('stty echo', check=True, shell=True)
