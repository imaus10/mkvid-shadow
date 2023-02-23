from params import *


def drawtext(
    start_time=0, end_time=0,
    fade_in=0, fade_out=0, grey_fade=None,
    style='', random_color=False,
    **kwargs
):
    text = kwargs['text']
    if not isinstance(text, str):
        texts = text
        cmds = []
        for i, text in enumerate(texts):
            y = kwargs['y']
            fontsize = kwargs['fontsize']*i
            new_args = {
                **kwargs,
                'text' : text,
                'y'    : f'{y} + {fontsize}'
            }
            cmd = drawtext(start_time, end_time, fade_in, fade_out, grey_fade, style, **new_args)
            cmds.append(cmd)
        spaces = ' '*10
        return f',\n{spaces}'.join(cmds)

    drawtext_args = {}
    if start_time and end_time:
        dur = end_time - start_time
        # this is the default, but can be overridden
        drawtext_args['enable'] = f'between(t,{start_time},{end_time})'
    elif start_time:
        drawtext_args['enable'] = f'gte(t,{start_time})'
    elif end_time:
        drawtext_args['enable'] = f'lt(t,{end_time})'
    drawtext_args.update(kwargs)

    font = drawtext_args['font']
    # Mac-specific! :|
    fontfile = f'/System/Library/Fonts/Supplemental/{font}.ttc'
    if style:
        fontfile += f'\:style={style}'
    drawtext_args['fontfile'] = fontfile

    # auto fade-in and fade-outs
    fade_in_condition = f'lt(t,{start_time + fade_in})'
    fade_in_cmd = f'(t-{start_time})/{fade_in}'
    fade_out_condition = f'gte(t,{end_time - fade_out})'
    fade_out_cmd = f'({end_time}-t)/{fade_out}'
    if fade_in and not fade_out:
        drawtext_args['alpha'] = f'if({fade_in_condition}, {fade_in_cmd}, 1)'
    elif fade_out and not fade_in:
        drawtext_args['alpha'] = f'if({fade_out_condition}, {fade_out_cmd}, 1)'
    elif fade_in and fade_out:
        drawtext_args['alpha'] = f'if({fade_in_condition}, {fade_in_cmd}, if({fade_out_condition}, {fade_out_cmd}, 1))'

    # fading grey values
    # grey values have r,g,b values that are equal
    # for instance, 0xA1A1A1
    # so we can reduce the full range of gray values to 0x00-0xFF (0-255)
    # and multiple by 0x010101 (65793) to get the full RGB number
    if grey_fade is not None:
        if len(grey_fade) != 2:
            raise ValueError('grey_fade argument should have 2 values: grey_start and grey_end')
        for v in grey_fade:
            if v > 255 or v < 0:
                raise ValueError(f'Invalid grey_fade value {v}')
        grey_start, grey_end = grey_fade
        grey_diff = grey_end - grey_start
        grey_eq = f'floor({grey_start}+(t-{start_time})/{dur}*{grey_diff})*65793'
        # use this eif func to print in hex
        drawtext_args['fontcolor_expr'] = f'0x%{{eif\:{grey_eq}\:x\:6}}'

    if random_color:
        # chooses a new color every single frame
        drawtext_args['fontcolor_expr'] = '0x%{eif\:rand(0,16777215)\:x\:6}'

    del_keys = []
    for key in drawtext_args:
        if key.endswith('_change'):
            end_val = drawtext_args[key]
            del_keys.append(key)
            key = key.replace('_change', '')
            start_val = drawtext_args[key]
            drawtext_args[key] = f'{start_val} + (t-{start_time})/{dur}*{end_val}'
    for key in del_keys:
        del drawtext_args[key]

    # escape string args
    for k,v in drawtext_args.items():
        if isinstance(v, str):
            if ':' in v or ',' in v or ' ' in v:
                drawtext_args[k] = f"'{v}'"
    spaces = ' '*12
    drawtext_args = f':\n{spaces}'.join([ f'{k}={v}' for k,v in drawtext_args.items() ])
    return f'''drawtext=
            {drawtext_args}'''


def drawtext_video(
    input_vid, input_overlay,
    start_time=0, end_time=0,
    fade_in=None, fade_out=None,
    eof_action='pass',
    **drawtext_args
):
    text_dur = end_time - start_time
    text_cmd = drawtext(
        fontcolor='white',
        **drawtext_args
    )

    fades = ''
    if fade_in:
        fades = f', fade=type=in:duration={fade_in}'
    if fade_out:
        fades += f', fade=type=out:start_time={text_dur-fade_out}:duration={fade_out}'

    tpad = ''
    if start_time > 0:
        tpad = f', tpad=start_duration={start_time}'

    text_luma_a = f'text_luma_a_{input_vid}'
    text_luma_b = f'text_luma_b_{input_vid}'
    text_vid = f'text_vid_{input_vid}'
    text_mask = f'text_mask_{input_vid}'
    text_vid_overlay = f'text_vid_overlay_{input_vid}'
    return f'''{text_cmd},
            trim=duration={text_dur},
            lumakey=threshold=1:tolerance=0.01:softness=1, gblur=sigma=1.5,
            split
        [{text_luma_a}][{text_luma_b}];
        [{input_vid}][{text_luma_a}]
          overlay=eof_action=endall
        [{text_vid}];
        [{text_luma_b}]
          negate=negate_alpha=1, alphaextract
        [{text_mask}];
        [{text_vid}][{text_mask}]
            alphamerge {fades} {tpad}
        [{text_vid_overlay}];
        [{input_overlay}][{text_vid_overlay}]
            overlay=enable='between(t,{start_time},{end_time})':eof_action={eof_action}'''



def add_opening_titles():
    # the titles come in at different times
    # but fade out together
    end_time = 15
    upper_shared_args = {
        'start_time' : 5,
        'end_time'   : end_time,
        'font'       : 'Avenir Next',
        'fontcolor'  : '0xA0A0A0',
        'x'          : '(w-text_w)/2',
        'fade_in'    : 1,
        'fade_out'   : 1,
    }
    nne = drawtext(
        text     = 'NEAR NORTHEAST',
        style    = 'Regular',
        fontsize = 60,
        y        = 215,
        **upper_shared_args,
    )
    presents = drawtext(
        text     = 'presents',
        style    = 'Italic',
        fontsize = 40,
        y        = 285,
        **upper_shared_args
    )
    # make a dynamic shadow for "SHADOW" text
    lower_shared_args = {
        'text'     : 'SHADOW',
        'font'     : 'Avenir Next',
        'style'    : 'Medium',
        'fontsize' : 150,
        'x'        : '(w-text_w)/2',
        'y'        : 350,
    }
    lower_start = 7
    lower_dur = end_time - lower_start
    # the main title flickers out
    flicker_dur = 3
    flicker_start = lower_dur - flicker_dur
    flicker = f'lt(random(1), ({lower_dur}-t)/{flicker_dur})'
    shadow_static = drawtext_video(
        'static_flipped', 'main',
        start_time = lower_start,
        end_time   = end_time,
        fade_in    = 1,
        fade_out   = 1,
        enable     = f'if(lt(t,{flicker_start}), 1, {flicker})',
        **lower_shared_args,
    )
    shadow_shadow = drawtext(
        start_time      = lower_start,
        end_time        = end_time-1,
        # shadow text goes from black to 0x101010,
        grey_fade       = (0,16),
        # grows bigger by 25 sizes,
        fontsize_change = 25,
        # moves left 50,
        x_change        = 50,
        # and moves down 25.
        y_change        = 25,
        fade_in         = 1,
        fade_out        = 1,
        **lower_shared_args,
    )
    return f'''split [static][rest];
        [rest]
            {nne},
            {presents},
            {shadow_shadow}
        [main];
        [static]
            trim=start={lower_start}:duration={lower_dur},
            setpts=PTS-STARTPTS,
            hflip
        [static_flipped];
        [3:v] {shadow_static}'''


def add_credits():
    # my initial tests were done on a slice
    # starting at 4:40,
    # but this starts from the outro
    start_offset = total_dur - outro_start - 20
    last_second = total_dur - outro_start - 1
    directed_by = drawtext(
        text       = 'directed by',
        font       = 'Avenir Next',
        style      = 'Ultra Light Italic',
        fontcolor  = 'white',
        fontsize   = 60,
        x          = '(w-text_w)/2',
        y          = 200,
        fade_in    = 2,
        start_time = start_offset + 13.3,
    )
    director_start = start_offset + 15.3
    director_stop = director_start + 10
    director_common_args = {
        'font'  : 'Avenir Next',
        'style' : 'Heavy',
        'x'     : '(w-text_w)/2',
    }
    director_size = 100
    # text with video of lion's mane mushroom timelapse underneath
    director_mushroom = drawtext_video(
        'mushroom', 'credits_director',
        start_time = director_start,
        end_time   = director_stop,
        text       = ['ART','FUNGUS'],
        fontsize   = director_size,
        y          = '(h-text_h)/2',
        fade_out   = 3,
        eof_action = 'endall',
        **director_common_args
    )
    # every second add a random color underneath
    director_colors = []
    colors_start = last_second - 1
    for i in range(8,0,-1):
        director_color_args = {
            **director_common_args,
            'start_time'   : colors_start + i-1,
            'random_color' : True,
        }
        color_cmd = drawtext(
            text     = 'ART',
            fontsize = director_size + i*10,
            y        = '(h-text_h)/2',
            **director_color_args,
        )
        director_colors.append(color_cmd)
        color_cmd = drawtext(
            text     = 'FUNGUS',
            fontsize = director_size + i*5,
            y        = f'(h-text_h)/2+{director_size}',
            **director_color_args,
        )
        director_colors.append(color_cmd)
    spaces = ' '*10
    director_color_cascade = f',\n{spaces}'.join(director_colors)
    # and add the IG handle for good measure
    ig_handle = drawtext(
        text       = '@art.fungus',
        font       = 'Courier New',
        style      = 'Bold',
        fontcolor  = 'white',
        fontsize   = 60,
        x          = '(w-text_w)/2',
        y          = 600,
        start_time = colors_start,
    )
    # and then show the NNE lineup
    lineup = []
    lineup_common_args = {
        'font'       : 'Avenir Next',
        'fontcolor'  : 'white',
        'fontsize'   : 100,
        'start_time' : start_offset+25,
        'end_time'   : start_offset+35,
        'fade_in'    : 3,
        'fade_out'   : 3,
    }
    lineup.append(drawtext(
        text  = 'Near Northeast is',
        style = 'Italic',
        x     = '(w-text_w)/2',
        y     = 80,
        **lineup_common_args,
    ))
    lineup_common_args = {
        **lineup_common_args,
        'style'    : 'Ultra Light',
        'fontsize' : 60,
    }
    top_y = 320
    bottom_y = top_y + 200
    left_x = '(w-text_w)/6'
    right_x = '(w-text_w)*5/6'
    lineup.append(drawtext(
        text = 'Kelly Servick',
        x    = left_x,
        y    = top_y,
        **lineup_common_args,
    ))
    lineup.append(drawtext(
        text = 'Avy Mallik',
        x    = right_x,
        y    = top_y,
        **lineup_common_args,
    ))
    lineup.append(drawtext(
        text = 'Antonio Skarica',
        x    = left_x,
        y    = bottom_y,
        **lineup_common_args,
    ))
    lineup.append(drawtext(
        text = 'Austin Blanton',
        x    = right_x,
        y    = bottom_y,
        **lineup_common_args,
    ))
    lineup_common_args = {
        **lineup_common_args,
        'font'     :'Courier New',
        'style'    : 'Regular',
        'fontsize' : 30,
    }
    lineup.append(drawtext(
        text = '(Art Fungus)',
        x    = f'{right_x}-50',
        y    = bottom_y+80,
        **lineup_common_args,
    ))
    spaces = ' '*10
    lineup = f',\n{spaces}'.join(lineup)

    return f'''[4:v]
          trim=duration=7.3, {get_stretch_cmd(7.3, 10*fps)}, fps=30,
          {crop_filter}
        [mushroom];
        [2:v]
          loop=loop=6:size={fps}:start={s_to_f(last_second)},
          {directed_by},
          {director_color_cascade},
          {ig_handle}
        [credits_director];
        [3:v]
          {director_mushroom},
          fade=type=out:start_time={start_offset+22.3}:duration=3,
          tpad=stop_duration=9.7,
          {lineup}
        [outro_credits]'''
