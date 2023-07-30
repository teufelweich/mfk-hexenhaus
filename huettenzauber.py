#! /usr/bin/env python
from argparse import ArgumentParser
import random
import time
import tomllib
import csv
from pprint import pprint
import asyncio
from typing import Tuple

from python_mpv_jsonipc import MPV

CONFIG = None
with open ('pyconfig.toml', 'rb') as f:
    CONFIG = tomllib.load(f)
assert CONFIG is not None, 'failed to load config'

SCENE_CSV = []
with open(CONFIG['file_locations']['SCENE_LIST'], 'r') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    SCENE_CSV = [ r for r in csv_reader]
assert len(SCENE_CSV) > 0, 'no clips inside clip csv'

def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--volume', '-v', default=80)
    parser.add_argument('--screen', '-s', default=1)

    return parser.parse_args()

def parse_steps(steps: str) -> Tuple:
    s = steps.split('-')
    if len(s) < 3:
        return None
    else:
        assert len(s) == 3, f'need 3 intervals not {steps}'
        return [int(i) for i in s]

def play_video(mpv: MPV, clip_path: str, clip_name: str):
    print('stop current video output and play new clip', clip_name)
    # stops video and clears playlist
    # await mpv.send(['stop'])
    mpv.command('stop')

    # add files to playlist
    # await mpv.send(['loadfile', CONFIG['file_locations']['TV_ON_VIDEO'], 'append-play'])
    # await mpv.send(['loadfile', clip_path, 'append'])
    mpv.command('loadfile', CONFIG['file_locations']['TV_ON_VIDEO'], 'append-play')
    mpv.command('loadfile', clip_path, 'append')

async def play_wled(command):
    try:
        print('send command to wled')
        # TODO send command to config['led']['wled_url]
        # probably use https://docs.aiohttp.org/en/stable/
        await asyncio.sleep(1)
    finally:
        # TODO turn wled off
        print('turn wled off')

async def play_fog(steps):
    try:
        # wait for the initial delay until starting fog
        print('wait until FOG ON for', steps[0], 's')
        await asyncio.sleep(steps[0])

        while True:
            # TODO turn fog on
            print('FOG ON for', steps[1], 's')
            # keep fog on for steps[1] seconds
            await asyncio.sleep(steps[1])

            # TODO turn fog off
            print('FOG OFF for', steps[2], 's')
            # keep fog off for steps[2] seconds
            await asyncio.sleep(steps[2])

    finally:
        # TODO turn fog off
        print('FOG FINAL OFF')


async def play_water(steps):
    try:
        # wait for the initial delay until starting water
        print('wait until WATER ON for', steps[0], 's')
        await asyncio.sleep(steps[0])

        while True:
            # TODO turn water on
            print('WATER ON for', steps[1], 's')
            # keep water on for steps[1] seconds
            await asyncio.sleep(steps[1])

            # TODO turn water off
            print('WATER OFF for', steps[2], 's')
            # keep water off for steps[2] seconds
            await asyncio.sleep(steps[2])

    finally:
        # TODO turn water off
        print('WATER FINAL OFF')

async def run_scene(mpv, scene):
    background_tasks = set()
    print(f'\n-----------------\nstart playing scene {scene["clip_name"]} with wled_cmd={scene["wled_command"]} fog_steps={scene["fog_steps"]} water_steps={scene["water_steps"]}')
    try:
        # play clip on screen
        play_video(mpv, scene['clip_path'], scene['clip_name'])

        # create concurrent tasks
        fog_steps = parse_steps(scene['fog_steps'])
        if fog_steps:
            fog_task = asyncio.create_task(play_fog(fog_steps), name='fog_task')
            background_tasks.add(fog_task)

        water_steps = parse_steps(scene['water_steps'])
        if water_steps:
            water_task = asyncio.create_task(play_water(water_steps), name='water_task')
            background_tasks.add(water_task)

        # give mpv time to load video and start playing before checking for scene end
        await asyncio.sleep(5)
        # wait until callback was called
        while True:
            if mpv.idle_active: # idle means playing has finished so we stop the scene
                print('currently idling, so finished playing')
                break

            remaining_time = mpv.playtime_remaining
            if not remaining_time:
                await asyncio.sleep(1)
                continue
            print(f'remaining {remaining_time}s to play')
            await asyncio.sleep(mpv.playtime_remaining / 2)

    finally:
        for task in background_tasks:
            print('cancelling task', task.get_name())
            task.cancel()


async def main():
    args = parse_args()
    # Use MPV that is running and connected to /tmp/mpv-socket.
    mpv = MPV(start_mpv=False, ipc_socket=f"/tmp/mpv-socket-{args.screen}")
    
    mpv.volume = args.volume

    for i in range(10):
        scene = random.choices(SCENE_CSV, [int(scene['probability_weight']) for scene in SCENE_CSV], k=1)[0]

        await run_scene(mpv, scene)
        await asyncio.sleep(5)
    


if __name__ == '__main__':
    max_retries = 10
    retries = 1
    print('loaded config:')
    pprint(CONFIG)
    print(f'\n\nloaded clip csv with {len(SCENE_CSV)} clips')
    pprint(SCENE_CSV)
    while True:
        try:
            asyncio.run(main())
        except ConnectionRefusedError as e:
            print('no MPV IPC socket available, please start MPV, retry in 10 seconds')
            time.sleep(10)
        except BrokenPipeError as e:
            print(f'pipe broke, trying reconnect {retries} of {max_retries} in 2s')
            if retries <= max_retries:
                time.sleep(2)
            else:
                break
        time.sleep(1)
    print('Goodbye')