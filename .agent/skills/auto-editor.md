---
title: "Auto-Editor — Automated Video Editing"
description: Remove silences, jump cuts, and automate video pacing with auto-editor and FFmpeg
location: .agent/skills/auto-editor.md
agent_priority: Standard
last_updated: 2026-05-30
---

**🔗 Related Media Tools:**
- [FFmpeg Recipes](ffmpeg-recipes.md) - Low-level FFmpeg filters and encoding
- [FFmpeg Reference](ffmpeg-reference.md) - Technical flags and codec reference
- [yt-dlp Web Download](youtube-dlp-web-download.md) - Download source videos before editing

[Back to README](../../README.md)

---

# Skill: Auto-Editor — Automated Video Editing

Auto-editor (by WyattBlue) is a CLI tool that automatically edits video and audio by analyzing audio loudness, motion, or subtitles. It removes dead space (silence / still frames), speeds up sections, and exports to standard formats or NLE-compatible timelines.

Repo: https://github.com/WyattBlue/auto-editor
PyPI: `auto-editor`
Requires: Python ≥ 3.10, FFmpeg in PATH

---

## 1. Installation

```bash
# Recommended — isolated install via pipx (no venv pollution)
pipx install auto-editor

# Or via uv tool
uv tool install auto-editor

# Verify
auto-editor --version
```

> Do NOT install into the project venv; it ships its own FFmpeg bindings.

---

## 2. Basic Silence Removal

```bash
# Default: remove segments where audio < -40 dB for > 0.3s
auto-editor input.mp4

# Output is written to input_ALTERED.mp4 by default
# Specify output path explicitly
auto-editor input.mp4 -o output.mp4
```

---

## 3. Key CLI Flags

### 3.1 `--edit` — Detection Method

```bash
# Audio loudness (default)
auto-editor input.mp4 --edit audio

# Silence threshold: audio below -35 dB is "silent"
auto-editor input.mp4 --edit audio:threshold=-35dB

# Motion detection (good for screen recordings / slides)
auto-editor input.mp4 --edit motion

# Motion with sensitivity tuning (0.0–1.0, lower = more sensitive)
auto-editor input.mp4 --edit motion:threshold=0.02

# No auto-editing (manual cut-out only)
auto-editor input.mp4 --edit none
```

### 3.2 `--margin` — Padding Around Loud Sections

Adds buffer before/after each kept segment so cuts feel natural.

```bash
# Symmetric margin: 0.2s before and after each loud region (default)
auto-editor input.mp4 --margin 0.2sec

# Asymmetric: 0.1s before, 0.3s after
auto-editor input.mp4 --margin 0.1sec,0.3sec
```

### 3.3 Speed Ramping

```bash
# Speed up silent sections (default: 99999 = skip)
auto-editor input.mp4 --silent-speed 6

# Slow down loud sections (default: 1.0 = normal)
auto-editor input.mp4 --video-speed 0.9

# Reverse roles: keep silence, speed up speech (e.g. for b-roll review)
auto-editor input.mp4 --video-speed 99999 --silent-speed 1
```

### 3.4 `--cut-out` / `--add-in` — Manual Regions

```bash
# Remove a specific time range (e.g. first 5 seconds)
auto-editor input.mp4 --edit none --cut-out 0,5sec

# Keep only a specific range
auto-editor input.mp4 --edit none --cut-out 0,10sec --cut-out 30sec,end
```

### 3.5 Audio Track Selection

```bash
# Analyze track 1 instead of track 0 (0-indexed)
auto-editor input.mp4 --edit audio:stream=1
```

---

## 4. Export Formats

```bash
# Default: re-encoded mp4 (libx264 + aac)
auto-editor input.mp4

# Premiere Pro XML (import into Premiere as a sequence)
auto-editor input.mp4 --export premiere

# Final Cut Pro 7 XML
auto-editor input.mp4 --export final-cut-pro

# DaVinci Resolve / generic EDL
auto-editor input.mp4 --export resolve

# Multiple video clips (one file per kept segment)
auto-editor input.mp4 --export clip-sequence

# Audio-only output
auto-editor input.mp3 -o output.mp3
```

> NLE exports do NOT re-encode — they produce XML/EDL timelines that reference the original file. Use these for lossless workflows.

---

## 5. Codec & Quality Options

```bash
# Change video codec
auto-editor input.mp4 --video-codec libx265

# Change audio codec
auto-editor input.mp4 --audio-codec aac

# Set video bitrate
auto-editor input.mp4 --video-bitrate 4000k

# Copy streams without re-encoding (fast, lossless — may have seek issues)
auto-editor input.mp4 --video-codec copy --audio-codec copy
```

---

## 6. Batch Processing

auto-editor accepts multiple inputs; they are concatenated and silence-detected independently per file.

```bash
# Process multiple files → one combined output
auto-editor lecture1.mp4 lecture2.mp4 lecture3.mp4 -o combined.mp4

# Shell glob (zsh/bash)
auto-editor recordings/*.mp4 -o batch_output.mp4

# Process files in a loop, keep separate outputs
for f in *.mp4; do
    auto-editor "$f" -o "edited_${f}"
done
```

---

## 7. Python API (Subprocess Pattern)

auto-editor does not expose a stable public Python API — it is a CLI tool. The recommended pattern is `subprocess`:

```python
import subprocess
from pathlib import Path

def remove_silence(
    input_path: str | Path,
    output_path: str | Path,
    threshold_db: float = -40,
    margin: str = "0.2sec",
    silent_speed: float = 99999,
) -> int:
    """Run auto-editor to strip silence. Returns exit code."""
    cmd = [
        "auto-editor", str(input_path),
        "--edit", f"audio:threshold={threshold_db}dB",
        "--margin", margin,
        "--silent-speed", str(silent_speed),
        "-o", str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"auto-editor failed:\n{result.stderr}")
    return result.returncode
```

---

## 8. Integration with `amir video`

When used inside the `amir` pipeline, call after `yt-dlp` download:

```bash
# Download then edit
amir video "https://youtube.com/..." --output /tmp/raw.mp4
auto-editor /tmp/raw.mp4 --edit audio:threshold=-35dB --margin 0.3sec -o /tmp/edited.mp4
```

For subtitle-then-edit workflows, run auto-editor **before** `amir subtitle` so timestamps in the SRT align with the edited video.

---

## 9. Common Recipes

| Goal | Command |
|------|---------|
| Remove silence, keep natural feel | `auto-editor input.mp4 --margin 0.3sec` |
| Aggressive cut (lectures, tutorials) | `auto-editor input.mp4 --edit audio:threshold=-30dB --margin 0.1sec` |
| Speed up silence 4×, don't cut | `auto-editor input.mp4 --silent-speed 4` |
| Premiere-ready edit without re-encode | `auto-editor input.mp4 --export premiere` |
| Motion-based (talking-head + slides) | `auto-editor input.mp4 --edit motion:threshold=0.02` |
| Batch rename pattern | `for f in *.mp4; do auto-editor "$f" -o "cut_$f"; done` |

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Too many cuts, choppy feel | Threshold too aggressive | Raise `--margin` to `0.4sec` or lower threshold to `-45dB` |
| Almost nothing cut | Threshold too lenient | Lower threshold: `-30dB` or `-25dB` |
| `ffmpeg not found` error | FFmpeg not in PATH | `brew install ffmpeg` or `apt install ffmpeg` |
| NLE import fails | Wrong export format | Match: Premiere=`premiere`, Resolve=`resolve` |
| Slow processing on long files | Re-encoding at default quality | Add `--video-codec copy --audio-codec copy` for fast pass |
