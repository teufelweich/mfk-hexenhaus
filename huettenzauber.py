#! /usr/bin/env python
from argparse import ArgumentParser
import random
import time
import configparser
import csv
from pprint import pprint
import asyncio
from os.path import expanduser, isfile
from typing import Tuple
import json

from python_mpv_jsonipc import MPV
import asyncpio
import aiohttp

HOME_PATH = expanduser('~')

CONFIG = configparser.ConfigParser()
CONFIG.read('pyconfig.ini')
BUTTONS = json.loads(CONFIG['buttons']['gpio_pins'])
buttons_callbacks = set()
mpv = None

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

def play_video(clip_path: str, clip_name: str):
    global mpv
    print('stop current video output and play new clip', clip_name)
    # stops video and clears playlist
    # await mpv.send(['stop'])
    mpv.command('stop')

    # add files to playlist
    # await mpv.send(['loadfile', CONFIG['file_locations']['TV_ON_VIDEO'], 'append-play'])
    # await mpv.send(['loadfile', clip_path, 'append'])
    mpv.command('loadfile', CONFIG['file_locations']['TV_ON_VIDEO'].replace('~', HOME_PATH), 'append-play')
    mpv.command('loadfile', clip_path.replace('~', HOME_PATH), 'append')
    mpv.command('loadfile', CONFIG['file_locations']['TV_OFF_VIDEO'].replace('~', HOME_PATH), 'append')


async def wled_idle():
    async with aiohttp.ClientSession() as session:
            async with session.get(CONFIG['led']['wled_url']+CONFIG['led']['off_command']):
                print('reset wled with:', CONFIG['led']['wled_url']+CONFIG['led']['off_command'])
                pass

async def play_wled(command):
    print(f'send command {command} to wled')
    # send command to config['led']['wled_url]
    async with aiohttp.ClientSession() as session:
        async with session.get(CONFIG['led']['wled_url']+command):
            pass


async def play_fog(steps):
    print('trying fog')
    try:
        pin = int(CONFIG['servo']['gpio_pin'])
        pwm_frequency = int(CONFIG['servo']['pwm_frequency'])
        rest_duty = int(CONFIG['servo']['rest_duty'])
        off_duty = int(CONFIG['servo']['off_duty'])

        pi = asyncpio.pi()

        await pi.connect()

        await pi.set_mode(pin, asyncpio.OUTPUT)

        await pi.set_PWM_frequency(pin, pwm_frequency)
        await pi.set_PWM_range(pin, int(CONFIG['servo']['pwm_range']))

        # set servo to off position
        await pi.set_PWM_dutycycle(pin, rest_duty)
        await pi.set_PWM_dutycycle(pin, off_duty)
        # wait for the initial delay until starting fog
        print('wait until FOG ON for', steps[0], 's')
        await asyncio.sleep(steps[0])

        while True:
            # turn fog on
            print('FOG ON for', steps[1], 's')
            await pi.set_PWM_dutycycle(pin, int(CONFIG['servo']['on_duty']))
            # keep fog on for steps[1] seconds
            await asyncio.sleep(steps[1])

            # turn fog off
            print('FOG OFF for', steps[2], 's')
            await pi.set_PWM_dutycycle(pin, rest_duty)
            await pi.set_PWM_dutycycle(pin, off_duty)
            # keep fog off for steps[2] seconds
            await asyncio.sleep(steps[2])
    except Exception as e:
        print(e)
        raise

    finally:
        # turn fog off
        await pi.set_PWM_dutycycle(pin, rest_duty)
        await pi.set_PWM_dutycycle(pin, off_duty)
        print('FOG FINAL OFF')
        await pi.set_mode(pin, asyncpio.INPUT)
        await pi.stop()



async def play_water(steps):
    try:
        pin = int(CONFIG['water']['gpio_pin'])
        
        pi = asyncpio.pi()

        await pi.connect()

        await pi.set_mode(pin, asyncpio.OUTPUT)
        # wait for the initial delay until starting water
        print('wait until WATER ON for', steps[0], 's')
        await asyncio.sleep(steps[0])

        while True:
            # turn water on
            print('WATER ON for', steps[1], 's')
            await pi.write(pin, 1)
            # keep water on for steps[1] seconds
            await asyncio.sleep(steps[1])

            # turn water off
            print('WATER OFF for', steps[2], 's')
            await pi.write(pin, 0)
            # keep water off for steps[2] seconds
            await asyncio.sleep(steps[2])
    except Exception as e:
        print(e)
        raise

    finally:
        # turn water off
        await pi.write(pin, 0)
        print('WATER FINAL OFF')
        await pi.stop()

async def run_scene(scene):
    background_tasks = set()
    print(f'\n-----------------\nstart playing scene {scene["clip_name"]} with wled_cmd={scene["wled_command"]} fog_steps={scene["fog_steps"]} water_steps={scene["water_steps"]}')
    try:
        # play clip on screen
        play_video(scene['clip_path'], scene['clip_name'])

        # create concurrent tasks
        fog_steps = parse_steps(scene['fog_steps'])
        if fog_steps:
            fog_task = asyncio.create_task(play_fog(fog_steps), name='fog_task')
            background_tasks.add(fog_task)

        water_steps = parse_steps(scene['water_steps'])
        if water_steps:
            water_task = asyncio.create_task(play_water(water_steps), name='water_task')
            background_tasks.add(water_task)

        wled_command = scene['wled_command']
        if wled_command:
            await play_wled(wled_command)

        # give mpv time to load video and start playing before checking for scene end
        await asyncio.sleep(5)
        # wait until callback was called
        while True:
            if mpv.idle_active: # idle means playing has finished so we stop the scene
                print('currently idling, so finished playing')
                await wled_idle()
                break

            remaining_time = mpv.playtime_remaining
            if not remaining_time:
                await asyncio.sleep(1)
                continue
            print(f'remaining {remaining_time}s to play')
            await asyncio.sleep(mpv.playtime_remaining / 2)

    except Exception as e:
        print(e)
        raise


    finally:
        for task in background_tasks:
            print('cancelling task', task.get_name())
            task.cancel()

async def user_button_pressed(pin, level, tick):
    try:
        global buttons_callbacks
        print(f'pin {pin} changed to level {level}')
        pi = asyncpio.pi()

        await pi.connect()
        # read all buttons
        buttons_levels = {}
        for pin in BUTTONS:
            buttons_levels[pin] = await pi.read(pin)
        if all(buttons_levels.values()): # all buttons are pressed
            print('all buttons pressed, start scene')
            
            # run new scene
            print('run scene')
            scene = random.choices(SCENE_CSV, [int(scene['probability_weight']) for scene in SCENE_CSV], k=1)[0]
            await run_scene(scene)

            # disable all callbacks and remove them from the set
            while buttons_callbacks:
                cb = buttons_callbacks.pop()
                await cb.cancel()
        await pi.stop()
    except Exception as e:
        print(e)
        raise e


async def main():
    global buttons_callbacks, mpv

    args = parse_args()
    # Use MPV that is running and connected to /tmp/mpv-socket.
    mpv = MPV(start_mpv=False, ipc_socket=f"/tmp/mpv-socket-{args.screen}")
    
    mpv.volume = args.volume

    pi = asyncpio.pi()

    await pi.connect()
    await wled_idle()

    try:
        await pi.connect()

        for pin in BUTTONS: # setup gpio for buttons
            await pi.set_mode(pin, asyncpio.INPUT)
            await pi.set_pull_up_down(pin, asyncpio.PUD_DOWN)  # read 0 when not pressed, read 1 when pressed

        while True:
            await asyncio.sleep(int(CONFIG['buttons']['delay']))
            if len(buttons_callbacks) == 0:
                print('setting callbacks')
                for pin in BUTTONS:
                    buttons_callbacks.add(await pi.callback(pin, edge=asyncpio.RISING_EDGE, func=user_button_pressed))
            await asyncio.sleep(0.1)

    finally:
        # disable all callbacks and remove them from the set
        while buttons_callbacks:
            cb = buttons_callbacks.pop()
            await cb.cancel()
        await pi.stop()

    


if __name__ == '__main__':
    max_retries = 10
    retries = 1
    print('loaded config:')
    pprint(CONFIG)
    print(f'\n\nloaded clip csv with {len(SCENE_CSV)} clips')
    pprint(SCENE_CSV)
    for scene in SCENE_CSV:
        assert isfile(scene['clip_path']), f'path is wrong: {scene["clip_path"]}'

    while True:
        try:
            asyncio.run(main(), debug=False)
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