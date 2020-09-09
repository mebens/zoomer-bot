#!/usr/bin/env python

import re
import random
import subprocess
import os
import sys
import argparse
import pathlib
import datetime as dt
import shutil

import requests
import moviepy.editor as mp

import effects

from typing import Optional, Any, List, Dict


WORD_LIST: List[str]
API_KEY: str

MAX_SOURCE_SECONDS = 240
VIDEO_SEARCH_ATTEMPTS = 10
MAX_SEARCH_WORDS = 1
YT_SEARCH_ORDER = "viewCount"

TMP_FILE_NAME = "TMP_VIDEO"
OUT_FILE = "A_HORRIBLE_MESS.mp4"
OUT_DEFAULT_TARGET = 15
OUT_HEIGHT = 720
SAVED_OUTPUT_DIR = "saved"
SAVED_SOURCES_DIR = "sources"

SPLIT_CHANCE = 0.9  # chance to split one second clip
MIN_INIT_SUBCLIPS = 4  # per 10 seconds
MAX_INIT_SUBCLIPS = 6  # per 10 seconds

MEME_SONG_CHANCE = 0.15
MEME_SOUND_CHANCE = 0.2


def make_zoomer_humour(
    output_target: int,
    file: Optional[str] = None,
    search: Optional[str] = None,
    use_last: bool = False,
) -> None:
    setup_global_info()

    if file:
        if re.match("^https?\:\/\/", file):
            print(f"Downloading video from {file}")
            remove_any_tmp_file()
            if not download_temp_video(file):
                return
            new_file = find_tmp_file()
        elif not os.path.isfile(file):
            print(f"Could not find file '{file}'")
            return
        else:
            new_file = file
    else:
        tmp_file = find_tmp_file()

        if use_last and tmp_file:
            print(f"Using last video file: {tmp_file}")
            new_file = tmp_file
        else:
            remove_any_tmp_file()
            url = get_random_video_url(search)
            if url is None:
                return

            if not download_temp_video(url):
                return

            new_file = find_tmp_file()

    in_clip = mp.VideoFileClip(new_file)
    print(f"Using video file at '{new_file}' with duration {in_clip.duration:.2f}s")
    if in_clip.h > OUT_HEIGHT:
        orig_w, orig_h = in_clip.w, in_clip.h
        in_clip = in_clip.resize(height=OUT_HEIGHT)
        print(f"Resized input from {orig_w}x{orig_h} to {in_clip.w}x{in_clip.h}")

    print("Zoomifying video")
    out_clip = zoomify(in_clip, output_target=output_target)
    print(f"Writing out video file to {OUT_FILE}")
    out_clip.write_videofile(OUT_FILE)


def setup_global_info():
    global WORD_LIST, API_KEY
    with open("apikey.txt") as f:
        API_KEY = f.readline().strip()
    with open("words.txt") as f:
        WORD_LIST = [line.strip() for line in f]


def find_tmp_file() -> Optional[str]:
    try:
        return next(f for f in os.listdir('.') if f.startswith(TMP_FILE_NAME))
    except StopIteration:
        return None


def remove_any_tmp_file() -> None:
    tmp_file = find_tmp_file()
    if tmp_file:
        os.remove(tmp_file)
        print(f"Deleted previous tempory video file: {tmp_file}")

    
def get_youtube_items(endpoint: str, args: Dict[str, str]) -> Dict[str, Any]:
    resp: requests.Response = requests.get(
        f"https://www.googleapis.com/youtube/v3/{endpoint}", params={"key": API_KEY, **args}
    )

    if 200 <= resp.status_code < 300:
        return resp.json()["items"]
    else:
        raise requests.HTTPError(f"Error in YouTube request '{endpoint}': {resp.status_code} {resp.reason}")


def get_random_video_url(search: Optional[str] = None) -> Optional[str]:
    video_id: Optional[str] = None

    for i in range(VIDEO_SEARCH_ATTEMPTS):
        if search:
            if i > 0:
                print(f"Could not find any suitable videos for search term: {search}")
                return None
            query = search
        else:
            query = " ".join(random.sample(WORD_LIST, random.randint(1, MAX_SEARCH_WORDS)))

        print(f"#{i}: Searching: {query}")
        items = get_youtube_items("search", {
            "part": "id", "q": query, "order": YT_SEARCH_ORDER, "maxResults": 25
        })

        if not len(items):
            print("#{i}: Empty result")
            continue
        random.shuffle(items)

        for item in items:
            if "id" not in item or "videoId" not in item["id"]:
                print(f"Could not find video ID. Skipping this item.")
                continue

            current_id = item["id"]["videoId"]
            vid_info = get_youtube_items("videos", {"part": "snippet,contentDetails", "id": current_id})[0]
            vid_duration = vid_info["contentDetails"]["duration"]
            dur_matches = re.match("PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", vid_duration)

            if dur_matches:
                duration = (
                    int(dur_matches[1] or 0) * 60 * 60
                    + int(dur_matches[2] or 0) * 60
                    + int(dur_matches[3] or 0)
                )

                if duration < MAX_SOURCE_SECONDS:
                    video_id = current_id
                    print(
                        f"Chosen video '{vid_info['snippet']['title']}', "
                        f"length {duration} seconds"
                    )
                    break
                else:
                    print(f"#{i}: Video rejected with too long duration: {duration} seconds")
            else:
                print(f"#{i}: Video rejected with invalid duration string: {vid_duration}")
        else:
            continue
        break

    if video_id is None:
        print(f"Unable to find a suitable YouTube video after {VIDEO_SEARCH_ATTEMPTS} tries")
        return None
    return f"https://www.youtube.com/watch?v={video_id}"


def download_temp_video(url: str) -> bool:
    process = subprocess.Popen(
        ["youtube-dl", url, "-o", TMP_FILE_NAME],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    
    while True:
        output = process.stdout.readline()
        if output:
            print(output.decode().strip())
        elif process.poll() is not None:
            break
    rc = process.poll()

    if rc == 0:
        return True
    else:
        print("Error downloading YouTube video")
        return False


clip_id = 0

def zoomify(clip: mp.VideoClip, output_target: int, initial_split: bool = True) -> mp.VideoClip:
    global clip_id

    if initial_split:
        # at top level select a number of random clips
        num_subclips = int(
            random.randint(MIN_INIT_SUBCLIPS, MAX_INIT_SUBCLIPS) * (output_target / 10)
        )

        clip_len = output_target / num_subclips
        subclips: List[mp.VideoClip] = []
        print(f"Split source clip into {num_subclips} initial subclips")

        for i in range(num_subclips):
            # pick random start in this subclip's "section" of the main clip
            start = random.uniform(0, max(clip.duration / num_subclips * i - clip_len, 0))
            effects.swap_chance_multiplier()  # use chance multiplier as a pseudo-tempo
            subclip = zoomify(
                clip.subclip(start, start + clip_len),
                output_target=output_target,
                initial_split=False,
            )

            if random.random() < MEME_SONG_CHANCE:
                print("MEME song")
                subclip = effects.add_song(subclip)
            subclips.append(subclip)

        return mp.concatenate_videoclips(subclips)
    elif random.random() < (SPLIT_CHANCE * min(effects.CHANCE_MULTIPLIER, 1) * min(1, clip.duration)):
        # apply subclip splitting for random effects
        if clip.duration > output_target:
            clip_len = output_target / 2
            start1 = random.uniform(0, clip.duration / 2 - clip_len)
            start2 = random.uniform(clip.duration / 2, clip.duration - clip_len)
        else:
            clip_len = clip.duration / 2
            start1 = 0
            start2 = clip.duration / 2

        end1 = start1 + clip_len
        end2 = start2 + clip_len
        print(f"Splitting: {start1}-{end1} and {start2}-{end2}")

        return mp.concatenate_videoclips([
            zoomify(
                clip.subclip(start1, start1 + clip_len),
                output_target=output_target,
                initial_split=False
            ),
            zoomify(
                clip.subclip(start2, start2 + clip_len),
                output_target=output_target,
                initial_split=False
            ),
        ])
    else:
        # apply effects
        print(f"Applying effects to subclip {clip_id}")
        clip_id += 1
        clip = effects.apply(clip)
        if random.random() < MEME_SOUND_CHANCE * effects.CHANCE_MULTIPLIER:
            print("MEME sound")
            return effects.add_sound(clip)
        else:
            return clip


def save_last_output() -> None:
    if not os.path.isfile(OUT_FILE):
        print(f"No file named {OUT_FILE}")
        return
    if not os.path.isdir(SAVED_OUTPUT_DIR):
        print(f"Created saved output directory: {SAVED_OUTPUT_DIR}")
        os.mkdir(SAVED_OUTPUT_DIR)
    path = os.path.join(SAVED_OUTPUT_DIR, dt.datetime.now().strftime("%Y-%m-%d %H-%M-%S") + ".mp4")
    print(f"Copying {OUT_FILE} to {path}")
    shutil.copyfile(OUT_FILE, path)


def save_last_temp_file() -> None:
    tmp_file = find_tmp_file()
    if not tmp_file:
        print("No temporary video file could be found")
        return
    if not os.path.isdir(SAVED_SOURCES_DIR):
        print(f"Created saved sources directory: {SAVED_SOURCES_DIR}")
        os.mkdir(SAVED_SOURCES_DIR)
    path = os.path.join(SAVED_SOURCES_DIR, dt.datetime.now().strftime("%Y-%m-%d %H-%M-%S") + ".mp4")
    print(f"Copying {tmp_file} to {path}")
    shutil.copyfile(tmp_file, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Absolute unfiltered cancer")
    parser.add_argument(
        "-l", "--last", action="store_true", help="Use last downloaded video if available"
    )
    parser.add_argument(
        "-t", "--time", default=OUT_DEFAULT_TARGET, type=int, help="Target output length in seconds"
    )
    parser.add_argument(
        "-s",
        "--search",
        help="Use this as a YouTube search term instead of a random one",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Saves the last generated file to saved/<datetime> and quits",
    )
    parser.add_argument(
        "--save-tmp",
        action="store_true",
        help="Saves the last temporary file downloaded to sources/<datetime> and quits",
    )
    parser.add_argument(
        "file", nargs="?", help="File or URL to use instead of random youtube video"
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    if args.save:
        save_last_output()
    elif args.save_tmp:
        save_last_temp_file()
    else:
        make_zoomer_humour(
            output_target=args.time,
            file=args.file,
            search=args.search,
            use_last=args.last
        )

