#!/bin/bash
(trap 'kill 0' SIGINT; DISPLAY=:0 mpv --profile=tiktok & python huettenzauber.py)