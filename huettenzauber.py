from python_mpv_jsonipc import MPV
from argparse import ArgumentParser
import random
import time

VIDEO_PATHS = ['/local/marius/Downloads/The Rotating Moon [bDgVFwWBSVg].mkv',
               '/local/marius/Downloads/mfk-videos/A girl opens a bottle of champagne Fail [YGgx7x8VCKo].webm',
               '/local/marius/Downloads/Animals Being Derps pt. 8 [OzIoOABfIq0].webm',
               '/local/marius/Downloads/A tiny angry squeaking Frog 🐸 ｜ Super Cute Animals - BBC [HBxn56l9WcU].webm',
               '/local/marius/Downloads/Derp Animals [CNj6u3eOEzY].webm',
               '/local/marius/Downloads/Epic Turtle Jump [ZwipCJoWpsQ].webm',
               '/local/marius/Downloads/Sneezing Baby Panda ｜ Original Video [93hq0YU3Gqk].webm']

TV_ON_VIDEO = '/local/marius/Downloads/TV turn ON effect [gp5DWmsXUtw].webm'

def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--volume', '-v', default=80)

    return parser.parse_args()

def check_pause(mpv, name: str):
    if mpv.pause:
        print('video was paused @', name,', unpause now')
        mpv.pause = False
    else:
        print('video should play')

def play_random_video(mpv: MPV):
    mpv.pause = False

    video_path = random.choice(VIDEO_PATHS)

    # stops video and clears playlist
    mpv.stop()

    # add files to playlist
    mpv.command('loadfile' , TV_ON_VIDEO, 'append-play')
    mpv.command('loadfile' , video_path, 'append')
    
    check_pause(mpv, 'TV_ON')
    time.sleep(10)

    # # wait for the value to change once
    # mpv.wait_for_property("eof-reached")
    # mpv.play(video_path)
    # check_pause('random')




def main():
    args = parse_args()
    # Use MPV that is running and connected to /tmp/mpv-socket.
    mpv = MPV(start_mpv=False, ipc_socket="/tmp/mpv-socket")

    # setting properties
    mpv.volume = args.volume

    # Bind to key press events with a decorator
    # @mpv.on_key_press("space")
    # def space_handler():
    #     print('pressed space')
    #     play_random_video(mpv)

    # You can also observe and wait for properties.
    # @mpv.property_observer("eof-reached")
    # def handle_eof(name, value):
    #     print(f'eof for {name} reached ({value=})')
    play_random_video(mpv)
    


if __name__ == '__main__':
    max_retries = 10
    retries = 1
    while True:
        try:
            main()
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