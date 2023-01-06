from functools import partial
import json
from multiprocessing import Pool
import os
import shutil
import subprocess

from tqdm import tqdm

from multisubprocess import subprocess_pool
from params import *


# 0x30306463 signals the end of a frame.
frame_header = bytes.fromhex('30306463')
# 0x0001B0 signals the beginning of an iframe
iframe = bytes.fromhex('0001B0')
# 0x0001B6 signals a pframe
pframe = bytes.fromhex('0001B6')

def remove_iframes():
    if os.path.exists('media/glitch_output.avi'):
        return
    prinnit(f'Removing iframes after {glitch_start_frame+1}...')
    with open('media/glitch_input.avi', 'rb') as in_file:
        frames = in_file.read().split(frame_header)
    removed_iframes = []
    with open('media/glitch_output.avi', 'wb') as out_file:
        # write header
        out_file.write(frames.pop(0))
        for index, frame in enumerate(frames):
            # remove iframes until the end
            if index >= glitch_start_frame:
                frame_type = frame[5:8]
                if frame_type == iframe:
                    removed_iframes.append(index)
                    # use the last frame to keep song alignment
                    frame = last_frame
            # add back the frame separator token
            out_file.write(frame_header + frame)
            last_frame = frame
    print(f'Removed {len(removed_iframes)} iframes')

# this is the original size of the mushroom timelapse
motion_scale = '1920:1080'
# we need 12 clips for the outro
# ( start, duration )
mushroom_chunks = [
    [
        (  9.2, 4.5 ),
        (  13.9, 4.4 )
    ], [
        (  45.8, 4.5 ),
        ( 183.0, 6.7 )
    ], [
        ( 123.5, 2.2 ),
        ( 109.9, 4.4 )
    ], [
        ( 114.3, 4.5 ),
        ( 125.8, 4.6 )
    ], [
        ( 27.5, 4.5 ),
        ( 130.4, 3.4 ),
        ( 133.8, 4.5 ),
        ( 138.3, 8 )
    ]
]
num_chunks = len(mushroom_chunks)

def cut_outro():
    if os.path.exists('media/outro_cut0.mp4'):
        return
    split_outputs = ''
    trim_cmds = []
    ffmpeg_outputs = []
    for chunk_num in range(num_chunks):
        # first four chunks are half of the riff duration
        # (to keep the motion transfer from turning everything pink)
        previous_dur = 4*bar_dur*chunk_num
        start_frame = s_to_f(previous_dur)
        trim_args = f'start_frame={start_frame}'
        # but last chunk is the rest of the song
        if chunk_num < num_chunks-1:
            chunk_dur = 4*bar_dur
            end_frame = s_to_f(previous_dur + chunk_dur)
            trim_args += f':end_frame={end_frame}'
        trim_input = f'[outro{chunk_num}]'
        trim_output = f'[outrocut{chunk_num}]'
        trim_cmds.append(
            # scale up to the size of the mushroom timelapse
            # for higher quality glitching
            f'{trim_input} trim={trim_args}, setpts=PTS-STARTPTS, scale={motion_scale} {trim_output}'
        )
        split_outputs += trim_input
        ffmpeg_outputs.append(f'-map {trim_output} -an media/outro_cut{chunk_num}.mp4')

    trim_cmds = ';\n        '.join(trim_cmds)
    ffmpeg_outputs = '\n      '.join(ffmpeg_outputs)
    ffmpeg(f'''
      -i media/glitch_output.avi
      -filter_complex
       "[0:v]
          trim=start_frame={s_to_f(outro_start)},
          setpts=PTS-STARTPTS,
          split={num_chunks}
        {split_outputs};
        {trim_cmds}"
      {ffmpeg_outputs}
    ''')


def cut_mushroom_timelapse(chunk_num, mushroom_alignments, send_pipe):
    mushroom_cut_path = f'media/mushroom_cut{chunk_num}.mp4'
    if os.path.exists(mushroom_cut_path):
        return
    send_pipe.send('We gonna cut')

    # each clip is 2 bars
    target_duration = bar_dur*2
    align_cmds = []
    split_outputs = []
    concat_inputs = []
    for i, (start_time, duration) in enumerate(mushroom_alignments):
        align_input = f'[mushrooms{i}]'
        align_output = f'[aligned{i}]'
        is_slower = target_duration > duration
        stretch_cmd = get_stretch_cmd(
            duration,
            s_to_f(target_duration),
            use_minterpolate=is_slower
        )
        # if it's sped up, we should use minterpolate after to get from 25 to 30 fps
        fps_cmd = f'fps={fps}' if is_slower else f'minterpolate=fps={fps}:mi_mode=mci'
        cmd = f'''{align_input}
            trim=start={start_time}:duration={duration},
            {stretch_cmd},
            {fps_cmd},
            trim=end_frame={s_to_f(target_duration)}
        {align_output}'''
        align_cmds.append(cmd)
        split_outputs.append(align_input)
        concat_inputs.append(align_output)

    # also crop out the labels/logo and rescale,
    # they cause distracting blocks in the glitch
    split_outputs = ''.join(split_outputs)
    align_cmds = ';\n        '.join(align_cmds)
    concat_inputs = ''.join(concat_inputs)
    ffmpeg(f'''
      -i media/mushroom_timelapse.mp4
      -filter_complex
       "[0:v] split={len(mushroom_alignments)} {split_outputs};
        {align_cmds};
        {concat_inputs} concat=n={len(mushroom_alignments)}:v=1:a=0 [cut];
        [cut]
          crop=h=915:y=50,
          scale={motion_scale}:force_original_aspect_ratio=increase,
          crop={motion_scale}, setsar=1
        [cutcrop]"
      -map [cutcrop] -an {mushroom_cut_path}
    ''', output_pipe=send_pipe)

# code for motion vector transfer modified from:
# https://github.com/tiberiuiancu/datamoshing

def get_motion_vectors(chunk_num, input_video, send_pipe):
    # extract video data using ffedit
    motion_vid = f'tmp{chunk_num}.mpg'
    ffgac(f'''
      -i {input_video} -an
      -mpv_flags +nopimb+forcemv -qscale:v 0 -g 1000
      -vcodec mpeg2video -f rawvideo -y
      {motion_vid}
    ''', output_pipe=send_pipe)
    motion_json = f'tmp{chunk_num}.json'
    ffedit(f'-i {motion_vid} -f mv:0 -e {motion_json}', output_pipe=send_pipe)
    os.remove(motion_vid)

    # from the data we extracted,
    # grab the motion vector in each frame
    with open(motion_json, 'r') as f:
        raw_data = json.load(f)
    os.remove(motion_json)
    frames = raw_data['streams'][0]['frames']
    vectors = []
    for frame in frames:
        try:
            vectors.append(frame['mv']['forward'])
        except:
            vectors.append([])
    return vectors


def transfer_motion_vectors(chunk_num, send_pipe, method='add', iframe_interval=10000):
    output_video = f'media/outro_mushroom_motion{chunk_num}.mpg'
    if os.path.exists(output_video):
        return
    vector_video = f'media/mushroom_cut{chunk_num}.mp4'
    input_video = f'media/outro_cut{chunk_num}.mp4'
    vectors = get_motion_vectors(chunk_num, vector_video, send_pipe)
    motion_vid = f'tmp{chunk_num}.mpg'
    ffgac(f'''
      -i {input_video}
      -an -mpv_flags +nopimb+forcemv -qscale:v 0 -g {iframe_interval}
      -vcodec mpeg2video -f rawvideo -y
      {motion_vid}
    ''', output_pipe=send_pipe)

    # assemble a JS script string to apply the motion vectors
    # TODO: new versions of ffedit support python script inputs...
    to_add = '+' if method == 'add' else ''
    script_contents = '''
        var vectors = ''' + json.dumps(vectors) + ''';
        var n_frames = 0;

        function glitch_frame(frame) {
            frame["mv"]["overflow"] = "truncate";
            let fwd_mvs = frame["mv"]["forward"];
            if (!fwd_mvs || !vectors[n_frames]) {
                n_frames++;
                return;
            }

            for ( let i = 0; i < fwd_mvs.length; i++ ) {
                let row = fwd_mvs[i];
                for ( let j = 0; j < row.length; j++ ) {
                    let mv = row[j];
                    try {
                        mv[0] ''' + to_add + '''= vectors[n_frames][i][j][0];
                        mv[1] ''' + to_add + '''= vectors[n_frames][i][j][1];
                    } catch {}
                }
            }

            n_frames++;
        }
    '''

    # write the code to a .js file
    # and apply the script
    script_path = f'apply_vectors{chunk_num}.js'
    with open(script_path, 'w') as f:
        f.write(script_contents)
    ffedit(
        f'-i {motion_vid} -f mv -s {script_path} -o {output_video}',
        output_pipe=send_pipe,
        last_stage=True
    )

    os.remove(script_path)
    os.remove(motion_vid)


def mushroom_motion_chunk(chunk_num, mushroom_alignments, send_pipe):
    cut_mushroom_timelapse(chunk_num, mushroom_alignments, send_pipe)
    transfer_motion_vectors(chunk_num, send_pipe)


def add_mushroom_motion():
    if os.path.exists('media/frames/outro_mushroom_motion'):
        return
    prinnit('Applying mushroom timelapse motion vectors to outro...')
    # cut the outro into chunks
    cut_outro()
    # cut the mushroom timelapse into same-sized chunks
    # and transfer the motion from the mushroom chunks
    # to the outro chunks (in parallel)
    subprocess_pool(mushroom_motion_chunk, list(enumerate(mushroom_chunks)))
    # and then combine the chunks
    subprocess.run('mkdir -p media/frames/outro_mushroom_motion', check=True, shell=True)
    ffmpeg_inputs, concat_inputs = zip(*[
        (f'-i media/outro_mushroom_motion{chunk_num}.mpg', f'[{chunk_num}:v]')
        for chunk_num in range(num_chunks)
    ])
    ffmpeg_inputs = '\n      '.join(ffmpeg_inputs)
    concat_inputs = ''.join(concat_inputs)
    ffmpeg(f'''
      {ffmpeg_inputs}
      -filter_complex "{concat_inputs} concat=n={num_chunks}:v=1:a=0, scale={crop} [outv]"
      -map [outv] "media/frames/outro_mushroom_motion/%06d.png"
    ''')


def overlay_one_frame(
    dancer_fade_in,fade_out_start, dancer_fade_out,
    blend_start, dancer_blend, frame_num
):
    original_frame_num = frame_num-1+s_to_f(outro_start)
    out_path = f'media/frames/outro_masked/{frame_num:06d}.png'
    mushrooms_path = f'media/frames/outro_mushroom_motion/{frame_num:06d}.png'
    dancer_path = f'media/frames/dancers/{original_frame_num:06d}.png'
    dancer_glitch_path = f'media/frames/outro_dancers_glitch/{frame_num:06d}.png'
    mask_path = f'media/frames/dancers_mask/{original_frame_num:06d}.npy'

    fade_in_end = len(dancer_fade_in)
    fade_out_end = fade_out_start + len(dancer_fade_out)

    if frame_num >= fade_out_end:
        shutil.copyfile(mushrooms_path, out_path)
        return

    mask = get_mask(mask_path)
    if frame_num < fade_in_end:
        mask = mask * dancer_fade_in[frame_num-1]
    if frame_num >= fade_out_start:
        mask = mask * dancer_fade_out[frame_num-fade_out_start]
    mask = np.stack((mask,) * 3, axis=-1)

    mushrooms = cv2.imread(mushrooms_path)
    dancers = cv2.imread(dancer_path)
    dancers_glitch = cv2.imread(dancer_glitch_path)
    if frame_num >= blend_start:
        dancer_pct = dancer_blend[frame_num-blend_start]
        dancers_blended = cv2.addWeighted(dancers, dancer_pct, dancers_glitch, 1-dancer_pct, 0)
    else:
        dancers_blended = dancers
    final_img = apply_mask(mask, dancers_blended, mushrooms)
    cv2.imwrite(out_path, final_img)


def overlay_dancers_on_mushroom_motion():
    if os.path.exists('media/frames/outro_masked'):
        return
    prinnit('Overlaying dancers on glitched mushroom motion outro...')
    subprocess.run('mkdir -p media/frames/outro_masked', check=True, shell=True)

    if not os.path.exists('media/frames/outro_dancers_glitch'):
        subprocess.run('mkdir -p media/frames/outro_dancers_glitch', check=True, shell=True)
        ffmpeg(f'''
          -i media/glitch_output.avi
          -vf "trim=start_frame={s_to_f(outro_start)}, setpts=PTS-STARTPTS"
          "media/frames/outro_dancers_glitch/%06d.png"
        ''')

    # fade the dancers in to not diminish mushroom explosion
    fade_in_end = s_to_f(2*bar_dur) + 1
    dancer_fade_in = np.linspace(0, 1, num=fade_in_end)
    # halfway thru the 3rd round, fade away the dancer to pinkness
    fade_out_start = s_to_f(20*bar_dur) + 1
    fade_out_end = s_to_f(24*bar_dur) + 1
    dancer_fade_out = np.linspace(1, 0, num=fade_out_end-fade_out_start)
    # gradually blend in the glitched dancer
    blend_start = s_to_f(8*bar_dur) + 1
    dancer_blend = np.linspace(1, 0, num=fade_out_end - blend_start)
    pfunc = partial(
        overlay_one_frame,
        dancer_fade_in,
        fade_out_start,
        dancer_fade_out,
        blend_start,
        dancer_blend
    )

    num_frames = min(
        len(glob('media/frames/outro_dancers_glitch/*.png')),
        len(glob('media/frames/outro_mushroom_motion/*.png'))
    )
    with Pool() as party:
        for _ in tqdm(party.imap(pfunc, range(1, num_frames+1)), total=num_frames):
            pass
