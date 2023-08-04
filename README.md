# MFK-Hexenhaus
An interactive exhibit for Keep Yourself 2023

## Prepare Videos
1. Download videos from a `.txt` containing the links
`yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b" -a urls.txt`
2. Cut video from timestamp to timestamp 
```bash
ffmpeg -i input.mp4 -ss 00:05:10 -to 00:15:30 -c:v copy -c:a copy output2.mp4
```
3. Convert to `h264`
```bash
for i in *.mp4; do ffmpeg -i "$i" -c:a copy -c:v libx264 "${i%.*}_h264.mp4"; done
```

## Scenes and Config
`fog-steps` and `water-steps` encode the following values:
```
<start delay>-<on time>-<off time>
```
`<start delay>` is the initial delay in seconds after the scene starts. Then the following loop starts: Output is on for `<on time>` seconds and then off for `<off time>` seconds. This loop runs till the end of the scene.

So `1-1-5` waits at the beginning 1s, is then 1s on and 5s off and then again 1s on and 5s off again and again until the end of the clip.

To disable it completely set the value to `0` (not `0-0-0`).