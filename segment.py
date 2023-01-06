import os
import subprocess

import cv2
import mediapipe as mp
mp_pose = mp.solutions.pose
import numpy as np
from tqdm import trange

from params import *


def get_dancer_mask(poser, img):
    return poser.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).segmentation_mask


def save_dancer_masks():
    if os.path.exists('media/frames/dancers_mask'):
        return
    prinnit('Collecting dancer pose masks...')
    subprocess.run('mkdir -p media/frames/dancers_mask', check=True, shell=True)

    pose_params = {
        'enable_segmentation'      : True,
        'min_detection_confidence' : 0.2,
        'min_tracking_confidence'  : 0.2,
        'model_complexity'         : 2,
    }

    # 1. single dancer in frame, up to the bridge synth arp.
    with mp_pose.Pose(**pose_params) as pose:
        for frame_num in trange(dancer_entrance_frame, s_to_f(synth_arp_start)):
            out_frame = frame_num + 1
            dancer = cv2.imread(f'media/frames/dancers/{out_frame:06d}.png')
            mask = get_dancer_mask(pose, dancer)
            if mask is not None:
                np.save(f'media/frames/dancers_mask/{out_frame:06d}.npy', mask)

    # 2. two dancers in the frame, outro.
    # mediapipe's pose segmentation does not support multiple people,
    # but luckily the dancers are mirrored,
    # so we split it into two images exactly in the middle
    # and run pose segmentation on each half,
    # then piece together the full mask.
    with mp_pose.Pose(**pose_params) as pose_left, mp_pose.Pose(**pose_params) as pose_right:
        for frame_num in trange(s_to_f(outro_start), get_num_dancer_frames()+1):
            in_path = f'media/frames/dancers/{frame_num:06d}.png'
            dancers = cv2.imread(in_path)
            dancer_left, dancer_right = np.hsplit(dancers, 2)
            mask = get_dancer_mask(pose_left, dancer_left)
            mask_sum = -1 if mask is None else np.sum(mask)
            # the left dancer has some super faint masks...skip em
            # if the mask is unusable, we'll use the last one
            if mask_sum > 25000:
                mask_left = mask
            mask = get_dancer_mask(pose_right, dancer_right)
            if mask is not None:
                mask_right = mask
            full_mask = np.hstack((mask_left, mask_right))
            np.save(f'media/frames/dancers_mask/{frame_num:06d}.npy', full_mask)
