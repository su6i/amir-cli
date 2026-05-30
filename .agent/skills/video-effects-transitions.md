---
title: "Video Effects — Transitions, Intro & Outro"
description: FFmpeg and Python recipes for fade, crossfade, wipe, zoom transitions, and building intro/outro sequences
location: .agent/skills/video-effects-transitions.md
agent_priority: Standard
last_updated: 2026-05-30
---

# Video Effects — Transitions, Intro & Outro

Sources synthesized from: mifi/lossless-cut, scriptituk/xfade-easing, remotion-dev/transitions-video, kapishdima/remocn.

---

## 1. FFmpeg xfade — Full Transition List

`xfade` requires re-encoding. Both clips must have identical frame size and frame rate.

**Syntax:**
```bash
ffmpeg -i clip_a.mp4 -i clip_b.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=TRANSITION:duration=SECS:offset=OFFSET[v]" \
  -map "[v]" -c:v libx264 -crf 18 out.mp4
# offset = when transition starts (seconds from start of clip_a)
# duration = how long transition lasts (keep ≤ 1.5s for natural feel)
```

**All built-in transition names:**

| Category | Transitions |
|---|---|
| Fade | `fade`, `fadeblack`, `fadewhite`, `fadegrays` |
| Wipe | `wipeleft`, `wiperight`, `wipeup`, `wipedown` |
| Slide | `slideleft`, `slideright`, `slideup`, `slidedown` |
| Smooth Slide | `smoothleft`, `smoothright`, `smoothup`, `smoothdown` |
| Rect / Circle | `rectcrop`, `circlecrop` |
| Dissolve | `dissolve`, `pixelize` |
| Radial | `radial`, `hblur` |
| Zoom | `zoomin` |
| Special | `distance`, `squeezev`, `squeezeh`, `hlslice`, `hrslice`, `vuslice`, `vdslice` |
| Diagonal | `diagtl`, `diagtr`, `diagbl`, `diagbr` |

---

## 2. Fade In / Fade Out

### Fade in from black (first 1s)
```bash
ffmpeg -i input.mp4 -vf "fade=t=in:st=0:d=1" -c:v libx264 -crf 18 out.mp4
```

### Fade out to black (last 1s, video is 60s long)
```bash
ffmpeg -i input.mp4 -vf "fade=t=out:st=59:d=1" -c:v libx264 -crf 18 out.mp4
```

### Fade in + fade out in one pass
```bash
DURATION=60  # total seconds
ffmpeg -i input.mp4 \
  -vf "fade=t=in:st=0:d=1,fade=t=out:st=$((DURATION-1)):d=1" \
  -c:v libx264 -crf 18 out.mp4
```

### Audio fade in/out (afade)
```bash
# fade audio in over 1s, out starting at 59s
ffmpeg -i input.mp4 \
  -af "afade=t=in:ss=0:d=1,afade=t=out:st=59:d=1" \
  -c:a aac out.mp4
```

### Fade video + audio together
```bash
ffmpeg -i input.mp4 \
  -vf "fade=t=in:st=0:d=1,fade=t=out:st=59:d=1" \
  -af "afade=t=in:ss=0:d=1,afade=t=out:st=59:d=1" \
  -c:v libx264 -crf 18 -c:a aac out.mp4
```

---

## 3. Crossfade Between Two Clips

```bash
# clip_a.mp4 = 30s, crossfade last 1s of A with first 1s of B
ffmpeg -i clip_a.mp4 -i clip_b.mp4 \
  -filter_complex \
    "[0:v][1:v]xfade=transition=fade:duration=1:offset=29[v];
     [0:a][1:a]acrossfade=d=1[a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -crf 18 -c:a aac out.mp4
```

**Tip — get exact duration of clip_a:**
```bash
ffprobe -v quiet -show_entries format=duration -of csv=p=0 clip_a.mp4
# offset = duration - xfade_duration
```

---

## 4. Wipe, Zoom, Slide — Ready-to-Use Commands

### Wipe right (horizontal wipe, B enters from left)
```bash
ffmpeg -i clip_a.mp4 -i clip_b.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=wiperight:duration=0.8:offset=29[v]" \
  -map "[v]" -c:v libx264 -crf 18 out.mp4
```

### Zoom in (scale-up reveal)
```bash
ffmpeg -i clip_a.mp4 -i clip_b.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=zoomin:duration=1:offset=29[v]" \
  -map "[v]" -c:v libx264 -crf 18 out.mp4
```

### Diagonal wipe (top-left)
```bash
ffmpeg -i clip_a.mp4 -i clip_b.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=diagtl:duration=0.8:offset=29[v]" \
  -map "[v]" -c:v libx264 -crf 18 out.mp4
```

### Radial sweep (clock wipe)
```bash
ffmpeg -i clip_a.mp4 -i clip_b.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=radial:duration=1.2:offset=29[v]" \
  -map "[v]" -c:v libx264 -crf 18 out.mp4
```

### Pixelize (dissolve into pixels)
```bash
ffmpeg -i clip_a.mp4 -i clip_b.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=pixelize:duration=0.6:offset=29[v]" \
  -map "[v]" -c:v libx264 -crf 18 out.mp4
```

---

## 5. Python — Batch Transitions with moviepy

```python
from moviepy.editor import VideoFileClip, concatenate_videoclips

clips = [VideoFileClip(f) for f in ["a.mp4", "b.mp4", "c.mp4"]]

# Hard cuts (no re-encode possible with moviepy)
result = concatenate_videoclips(clips, method="compose")
result.write_videofile("out.mp4", codec="libx264", fps=30)
```

### Fade between clips (moviepy)
```python
from moviepy.editor import VideoFileClip, concatenate_videoclips

def fade_clip(clip, duration=0.5):
    return clip.fadein(duration).fadeout(duration)

clips = [fade_clip(VideoFileClip(f)) for f in ["a.mp4", "b.mp4", "c.mp4"]]
result = concatenate_videoclips(clips, padding=-0.5, method="compose")
result.write_videofile("out.mp4", codec="libx264")
```

### Crossfade with overlap (moviepy)
```python
from moviepy.editor import VideoFileClip, CompositeVideoClip

a = VideoFileClip("a.mp4")
b = VideoFileClip("b.mp4").set_start(a.duration - 1).crossfadein(1)
result = CompositeVideoClip([a, b])
result.write_videofile("out.mp4")
```

---

## 6. Python — Batch FFmpeg via subprocess

```python
import subprocess
from pathlib import Path

def xfade_concat(clips: list[str], output: str,
                 transition: str = "fade", duration: float = 1.0) -> None:
    """Concatenate clips with xfade transitions. All clips must be same size/fps."""
    inputs = []
    for c in clips:
        inputs += ["-i", c]

    filter_parts = []
    prev = "[0:v]"
    for i in range(1, len(clips)):
        dur_cmd = ["ffprobe", "-v", "quiet", "-show_entries",
                   "format=duration", "-of", "csv=p=0", clips[i - 1]]
        clip_dur = float(subprocess.check_output(dur_cmd).decode().strip())
        offset = clip_dur - duration
        out_label = f"[v{i}]"
        filter_parts.append(
            f"{prev}[{i}:v]xfade=transition={transition}"
            f":duration={duration}:offset={offset:.3f}{out_label}"
        )
        prev = out_label

    filter_complex = ";".join(filter_parts)
    cmd = (["ffmpeg", "-y"] + inputs +
           ["-filter_complex", filter_complex,
            "-map", prev, "-c:v", "libx264", "-crf", "18", output])
    subprocess.run(cmd, check=True)

# Usage
xfade_concat(["a.mp4", "b.mp4", "c.mp4"], "out.mp4", transition="wiperight")
```

---

## 7. Intro / Outro Template

### Black screen + text overlay (5s intro)
```bash
# Step 1: generate 5s black screen with text
ffmpeg -f lavfi -i color=c=black:size=1920x1080:rate=30 \
  -vf "drawtext=text='My Channel':fontcolor=white:fontsize=72:\
       x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,1,4)',\
       fade=t=in:st=0:d=1,fade=t=out:st=4:d=1" \
  -t 5 -c:v libx264 -crf 18 intro.mp4
```

### Intro + main video + outro
```bash
# Step 2: concat intro + main + outro with fade transitions
ffmpeg -i intro.mp4 -i main.mp4 -i outro.mp4 \
  -filter_complex \
    "[0:v][1:v]xfade=transition=fade:duration=1:offset=4[tmp];
     [tmp][2:v]xfade=transition=fade:duration=1:offset=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 main.mp4 | awk '{printf "%.0f", $1+3}')[v]" \
  -map "[v]" -c:v libx264 -crf 18 final.mp4
```

### Intro with music fade-in
```bash
ffmpeg -f lavfi -i color=c=black:size=1920x1080:rate=30 \
  -i music.mp3 \
  -vf "drawtext=text='My Channel':fontcolor=white:fontsize=72:\
       x=(w-text_w)/2:y=(h-text_h)/2" \
  -af "afade=t=in:ss=0:d=1,afade=t=out:st=4:d=1" \
  -t 5 -c:v libx264 -crf 18 -c:a aac -shortest intro_music.mp4
```

---

## 8. Lossless Concat (No Transitions — LosslessCut style)

When re-encoding is undesirable (e.g., keeping original quality), use concat demuxer:

```bash
# concat.txt
# file 'clip_a.mp4'
# file 'clip_b.mp4'
# file 'clip_c.mp4'
printf "file '%s'\n" clip_a.mp4 clip_b.mp4 clip_c.mp4 > concat.txt
ffmpeg -f concat -safe 0 -i concat.txt -c copy out.mp4
# No transitions possible — hard cuts only. Clips must share codec/resolution.
```

---

## 9. Remotion (React) — @remotion/transitions API

Install: `npm i @remotion/transitions`

```tsx
import { TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";

export const MyVideo = () => (
  <TransitionSeries>
    <TransitionSeries.Sequence durationInFrames={60}>
      <ClipA />
    </TransitionSeries.Sequence>

    {/* Fade: 30 frames = 1s at 30fps */}
    <TransitionSeries.Transition presentation={fade()} timing={{ durationInFrames: 30 }} />

    <TransitionSeries.Sequence durationInFrames={60}>
      <ClipB />
    </TransitionSeries.Sequence>

    {/* Wipe from left */}
    <TransitionSeries.Transition presentation={wipe({ direction: "from-left" })} timing={{ durationInFrames: 20 }} />

    <TransitionSeries.Sequence durationInFrames={60}>
      <ClipC />
    </TransitionSeries.Sequence>
  </TransitionSeries>
);
```

**Available @remotion/transitions presentations:**
`fade`, `slide`, `wipe`, `flip`, `clockWipe`, `none`

Render to MP4:
```bash
npx remotion render MyVideo out.mp4 --codec=h264
```

---

## 10. Quick Reference — Transition Duration Guidelines

| Use case | Duration |
|---|---|
| Hard social cut | 0s (concat demuxer) |
| Snappy broadcast wipe | 0.3 – 0.5s |
| Standard YouTube fade | 0.5 – 1.0s |
| Cinematic dissolve | 1.0 – 2.0s |
| Intro/outro fade | 1.0s in, 1.0s out |

**Performance note:** xfade forces full re-encode. For batch processing many clips, use `-preset fast` or `-preset ultrafast` with `-crf 23` to trade quality for speed during draft, then re-render with `-crf 18 -preset slow` for final output.
