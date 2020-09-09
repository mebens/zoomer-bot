import random
import math
import glob
import os

import moviepy.editor as mp
import numpy as np
import numpy.random as np_rand

from typing import List, Callable

ALL_EFFECTS: List[Callable] = []
CHANCE_MULTIPLIER = 1
LOW_CHANCE = 0.6
HIGH_CHANCE = 1
MEME_SONGS_DIR = "meme_songs"
MEME_SOUNDS_DIR = "meme_sounds"


def apply(clip: mp.VideoClip) -> mp.VideoClip:
    for func in ALL_EFFECTS:
        clip = func(clip)
    return clip


def swap_chance_multiplier() -> None:
    global CHANCE_MULTIPLIER

    if CHANCE_MULTIPLIER == HIGH_CHANCE:
        CHANCE_MULTIPLIER = LOW_CHANCE
    else:
        CHANCE_MULTIPLIER = HIGH_CHANCE


def add_song(clip: mp.VideoClip) -> mp.VideoClip:
    return add_sound(clip, dirname = MEME_SONGS_DIR)


def add_sound(clip: mp.VideoClip, dirname: str = MEME_SOUNDS_DIR) -> mp.VideoClip:
    sound = mp.AudioFileClip(random.choice(glob.glob(os.path.join(dirname, "*.m4a"))))
    start = random.uniform(0, max(sound.duration - clip.duration, 0))
    sound = sound.subclip(start, min(start + clip.duration, sound.duration))
    sound = sound.volumex(1 + 30*random.lognormvariate(0, 1))
    sound.set_duration(clip.duration)  # needed to work
    clip.audio = mp.CompositeAudioClip([clip.audio, sound])
    return clip


def clip_effect(func: Callable) -> Callable:
    ALL_EFFECTS.append(func)
    return func


@clip_effect
def distort(clip: mp.VideoClip) -> mp.VideoClip:
    if random.random() < 0.4 * CHANCE_MULTIPLIER:
        print("Distort")
        return clip.fx(mp.afx.volumex, 20 + 120*random.lognormvariate(0, 1))
    else:
        return clip



@clip_effect
def disco(clip: mp.VideoClip) -> mp.VideoClip:
    if random.random() < 0.15 * CHANCE_MULTIPLIER:
        print("Disco")
        rate = random.uniform(1, 10)

        def disco_filter(get_frame: Callable, t: float) -> np.array:
            frame: np.array = np.copy(get_frame(t))
            frame[:, :, 0] = frame[:, :, 0] * (1 + math.sin(rate*math.pi*t)/2)
            frame[:, :, 1] = frame[:, :, 1] * (1 + math.cos(rate*math.pi*t)/2)
            frame[:, :, 2] = frame[:, :, 2] * (1 + math.sin(rate*math.pi*t + math.pi*0.25)/2)
            return frame

        return clip.fl(disco_filter)
    else:
        return clip


@clip_effect
def speed(clip: mp.VideoClip) -> mp.VideoClip:
    var = random.random()
    if var < 0.3 * CHANCE_MULTIPLIER:
        print("Speed up")
        return clip.fx(mp.vfx.speedx, random.uniform(2, 8))
    elif var < 0.6 * CHANCE_MULTIPLIER:
        print("Slow down")
        speed = random.uniform(0.1, 0.8)
        return clip.set_duration(clip.duration * speed).fx(mp.vfx.speedx, speed)
    else:
        return clip


# this needs to zoom
#@clip_effect
def crop(clip: mp.VideoClip) -> mp.VideoClip:
    if random.random() < 0.3 * CHANCE_MULTIPLIER:
        print("Crop")
        return clip.fx(
            mp.vfx.crop,
            x1=int(random.uniform(0.1, 0.4) * clip.w),
            y1=int(random.uniform(0.1, 0.4) * clip.h),
            x2=int(random.uniform(0.6, 0.9) * clip.w),
            y2=int(random.uniform(0.6, 0.9) * clip.h),
        )
    else:
        return clip


@clip_effect
def mirror(clip: mp.VideoClip) -> mp.VideoClip:
    if random.random() < 0.2 * CHANCE_MULTIPLIER:
        print("Mirror X")
        clip = clip.fx(mp.vfx.mirror_x)
    if random.random() < 0.05 * CHANCE_MULTIPLIER:
        print("Mirror Y")
        clip = clip.fx(mp.vfx.mirror_y)
    return clip


# very CPU heavy
#@clip_effect
def supersample(clip: mp.VideoClip) -> mp.VideoClip:
    if random.random() < 0.05 * CHANCE_MULTIPLIER:
        print("Supersample")
        return clip.fx(mp.vfx.supersample, random.uniform(0.5, 2), random.randint(3, 5))
    else:
        return clip


@clip_effect
def invert(clip: mp.VideoClip) -> mp.VideoClip:
    if random.random() < 0.1 * CHANCE_MULTIPLIER:
        print("Invert")
        return clip.fx(mp.vfx.invert_colors)
    else:
        return clip


@clip_effect
def reverse_or_palindrome(clip: mp.VideoClip) -> mp.VideoClip:
    var = random.random()
    if var < 0.1 * CHANCE_MULTIPLIER:
        print("Reverse")
        return clip.fx(mp.vfx.time_mirror)
    elif var < 0.25 * CHANCE_MULTIPLIER:
        print("Palindrome")
        return clip.subclip(t_end=clip.duration / 2).fx(mp.vfx.time_symmetrize)
    else:
        return clip


@clip_effect
def broken_record(clip: mp.VideoClip) -> mp.VideoClip:
    if random.random() < 0.25 * CHANCE_MULTIPLIER:
        print("Broken record")
        subclip = clip.subclip(t_end=random.uniform(0.01, 0.08))
        num_repeats = random.randint(2, 12)
        clips = [subclip] * num_repeats
        if clip.duration > subclip.duration * num_repeats:
            clips.append(clip.subclip(t_start=subclip.duration * num_repeats))
        return mp.concatenate_videoclips(clips)
    else:
        return clip


# also high CPU
#@clip_effect
def glitch_motion(clip: mp.VideoClip) -> mp.VideoClip:
    if random.random() < 0.2 * CHANCE_MULTIPLIER:
        print("Glitch motion")

        def glitch(get_frame, t: float) -> np.array:
            f1 = get_frame(t)
            f2 = get_frame(max(0, t - random.uniform(0.05, 0.25)))
            f3 = get_frame(max(0, t - random.uniform(0.1, 0.75)))
            decider = np.transpose(np.tile(np_rand.randint(1, 4, f1.shape[1::-1]), (3, 1, 1)))
            return f1*(decider == 1) + f2*(decider == 2) + f3*(decider == 3)

        return clip.fl(glitch)
    else:
        return clip

