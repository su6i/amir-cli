---
title: "DaVinci Resolve Python Scripting"
description: Automate DaVinci Resolve via its Python API — project management, MediaPool, timeline assembly, and render queue
location: .agent/skills/davinci-resolve-scripting.md
agent_priority: Standard
last_updated: 2026-05-30
---

# Skill: DaVinci Resolve Python Scripting

DaVinci Resolve exposes a Python (and Lua) scripting API via `DaVinciResolveScript`. Scripts run against a **live Resolve instance** — Resolve must be open before calling any API.

Supported runtimes: Python 3.6+ (64-bit) or Lua 5.1. Free version has some limits; Studio unlocks full automation.

---

## Environment Setup

Set these **before** importing `DaVinciResolveScript`:

### macOS
```bash
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```

### Windows
```bat
set RESOLVE_SCRIPT_API=%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting
set RESOLVE_SCRIPT_LIB=C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll
set PYTHONPATH=%PYTHONPATH%;%RESOLVE_SCRIPT_API%\Modules\
```

### Linux
```bash
export RESOLVE_SCRIPT_API="/opt/resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/opt/resolve/libs/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```

### Programmatic setup helper (cross-platform)
```python
import os, sys

def setup_resolve_env():
    if sys.platform == "darwin":
        api = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/"
        lib = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
    elif sys.platform == "win32":
        api = os.path.join(os.environ.get("PROGRAMDATA", ""), "Blackmagic Design",
                           "DaVinci Resolve", "Support", "Developer", "Scripting")
        lib = os.path.join(os.environ.get("PROGRAMFILES", ""), "Blackmagic Design",
                           "DaVinci Resolve", "fusionscript.dll")
    else:
        api = "/opt/resolve/Developer/Scripting/"
        lib = "/opt/resolve/libs/Fusion/fusionscript.so"
    os.environ.setdefault("RESOLVE_SCRIPT_API", api)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", lib)
    modules = os.path.join(os.environ["RESOLVE_SCRIPT_API"], "Modules")
    if modules not in sys.path:
        sys.path.insert(0, modules)

setup_resolve_env()
import DaVinciResolveScript as dvr_script
```

---

## Connection

```python
resolve = dvr_script.scriptapp("Resolve")
if not resolve:
    raise RuntimeError("Cannot connect — is DaVinci Resolve running?")
```

---

## Object Hierarchy

```
resolve                   ← Resolve  (entry point)
└── GetProjectManager()   ← ProjectManager
    └── GetCurrentProject()  ← Project
        ├── GetMediaPool()   ← MediaPool
        │   ├── GetRootFolder()  ← Folder
        │   │   └── GetClipList()  → [MediaPoolItem, ...]
        │   └── CreateEmptyTimeline() → Timeline
        └── GetCurrentTimeline()  ← Timeline
            └── GetItemListInTrack("video", 1)  → [TimelineItem, ...]
                └── GetMediaPoolItem()  ← MediaPoolItem
```

---

## Project Management

```python
pm = resolve.GetProjectManager()

# Load or create
project = pm.LoadProject("MyProject") or pm.CreateProject("MyProject")
project = pm.GetCurrentProject()
print(project.GetName())

# Project settings
project.SetSetting("timelineFrameRate", "24")
project.SetSetting("timelineResolutionWidth", "1920")
project.SetSetting("timelineResolutionHeight", "1080")

# Save / close
pm.SaveProject()
pm.CloseProject(project)   # closes without saving

# Folder navigation
pm.GotoRootFolder()
for folder in pm.GetFolderListInCurrentFolder():
    print(folder)
pm.OpenFolder("ClientWork")
pm.GotoParentFolder()
```

---

## MediaPool — Import & Organize

```python
media_pool = project.GetMediaPool()
root = media_pool.GetRootFolder()

# Import files
clips = media_pool.ImportMedia([
    "/path/to/video.mov",
    "/path/to/audio.wav",
])

# Import image sequence
clips = media_pool.ImportMedia([{
    "FilePath": "/path/to/frames/image_%04d.exr",
    "StartIndex": 1001,
    "EndIndex": 1100,
}])

# Organize into bins
footage_bin = media_pool.AddSubFolder(root, "Footage")
media_pool.SetCurrentFolder(footage_bin)
media_pool.MoveClips(clips, footage_bin)

# Inspect clip properties
clip = clips[0]
print(clip.GetClipProperty("File Path"))
print(clip.GetClipProperty("Resolution"))
print(clip.GetClipProperty("FPS"))
print(clip.GetClipProperty("Frames"))
clip.SetClipProperty("Clip Name", "hero_shot")
clip.SetClipProperty("FPS", "24.0")
clip.SetClipProperty("Alpha mode", "None")
```

---

## Timeline Creation & Assembly

```python
# Create empty timeline
timeline = media_pool.CreateEmptyTimeline("Main Timeline")
project.SetCurrentTimeline(timeline)

# Append clips (simplest — adds to end of V1/A1)
items = media_pool.AppendToTimeline(clips)

# Precise placement
items = media_pool.AppendToTimeline([{
    "mediaPoolItem": clips[0],
    "startFrame": 0,          # source in-point
    "endFrame": 100,           # source out-point
    "trackIndex": 1,           # 1-based track index
    "recordFrame": 0,          # destination frame on timeline
    "mediaType": 1,            # 1 = video only, 2 = audio only
}])

# Import timeline from XML/AAF/EDL/FCPXML/OTIO
timeline = media_pool.ImportTimelineFromFile("/path/to/cut.xml", {
    "timelineName": "ImportedCut",
    "importSourceClips": True,
    "sourceClipsPath": "/path/to/media/",
})

# Timeline info
print(timeline.GetName())
print(timeline.GetStartFrame(), timeline.GetEndFrame())
print(timeline.GetStartTimecode())
print(timeline.GetTrackCount("video"))

# Navigate all timelines
for i in range(1, project.GetTimelineCount() + 1):
    tl = project.GetTimelineByIndex(i)
    print(i, tl.GetName())
```

### Add / manage tracks
```python
timeline.AddTrack("video")
timeline.AddTrack("audio", "stereo")
timeline.AddTrack("subtitle")
timeline.SetTrackName("video", 1, "Master")
timeline.SetTrackEnable("video", 2, True)
timeline.SetTrackLock("video", 1, False)
timeline.DeleteTrack("video", 3)
```

### Read timeline items
```python
for item in timeline.GetItemListInTrack("video", 1):
    print(item.GetName(), item.GetStart(), item.GetEnd(), item.GetDuration())
    mp_item = item.GetMediaPoolItem()
    if mp_item:
        print("  File:", mp_item.GetClipProperty("File Path"))
```

### Timeline item transforms
```python
item.SetProperty("Pan", 100.0)
item.SetProperty("ZoomX", 110.0)
item.SetProperty("RotationAngle", 15.0)
item.SetProperty("Opacity", 80.0)       # 0.0–100.0
item.SetProperty("CropTop", 120.0)
item.SetProperty("RetimeProcess", 3)    # 3 = Optical Flow
item.SetClipEnabled(False)
```

### Timeline markers
```python
timeline.AddMarker(100, "Blue", "Scene Start", "Note text", 1)
markers = timeline.GetMarkers()   # {frame: {color, duration, name, note}, ...}
timeline.DeleteMarkerAtFrame(100)
timeline.DeleteMarkersByColor("All")
```

### Timeline export
```python
timeline.Export("/out/cut.edl",    resolve.EXPORT_EDL,        resolve.EXPORT_NONE)
timeline.Export("/out/cut.fcpxml", resolve.EXPORT_FCPXML_1_10, resolve.EXPORT_NONE)
timeline.Export("/out/cut.otio",   resolve.EXPORT_OTIO,        resolve.EXPORT_NONE)
```

---

## Render Queue

```python
# Navigate to Deliver page first
resolve.OpenPage("deliver")
import time; time.sleep(0.5)

# Configure format/codec
project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")

# Set render settings
project.SetRenderSettings({
    "SelectAllFrames": True,
    "TargetDir": "/output/",
    "CustomName": "final",
    "ExportVideo": True,
    "ExportAudio": True,
    "FrameRate": 24.0,
    "AudioCodec": "aac",
    "AudioBitDepth": 24,
    "AudioSampleRate": 48000,
})

# Queue and render
job_id = project.AddRenderJob()
project.StartRendering([job_id])

# Monitor
while project.IsRenderingInProgress():
    s = project.GetRenderJobStatus(job_id)
    print(f"{s.get('CompletionPercentage', 0)}%", end="\r")
    time.sleep(1.0)

# Check result
status = project.GetRenderJobStatus(job_id)
if status["JobStatus"] == "Complete":
    print("Done in", status.get("TimeTakenToRenderInMs", 0) / 1000, "s")
else:
    print("Failed:", status.get("Error", "unknown"))

project.DeleteRenderJob(job_id)
pm.SaveProject()
```

### Batch render multiple segments
```python
shots = [
    {"name": "shot_001", "mark_in": 0,   "mark_out": 100},
    {"name": "shot_002", "mark_in": 101, "mark_out": 250},
]

project.DeleteAllRenderJobs()
project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")

for shot in shots:
    project.SetRenderSettings({
        "SelectAllFrames": False,
        "MarkIn": shot["mark_in"],
        "MarkOut": shot["mark_out"],
        "TargetDir": "/output/shots/",
        "CustomName": shot["name"],
    })
    job_id = project.AddRenderJob()
    project.StartRendering([job_id])
    while project.IsRenderingInProgress():
        s = project.GetRenderJobStatus(job_id)
        print(f"{shot['name']}: {s.get('CompletionPercentage', 0)}%", end="\r")
        time.sleep(0.5)
    s = project.GetRenderJobStatus(job_id)
    print(f"{shot['name']}: {s['JobStatus']}")
    project.DeleteRenderJob(job_id)
```

---

## Utility Functions

### Timecode conversion
```python
def timecode_to_frames(tc: str, fps: float) -> int:
    h, m, s, f = map(int, tc.split(":"))
    return (h * 3600 + m * 60 + s) * round(fps) + f

def frames_to_timecode(frames: int, fps: float) -> str:
    r = round(fps)
    f = frames % r
    total_s = frames // r
    s, total_s = total_s % 60, total_s // 60
    m, h = total_s % 60, total_s // 60
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"
```

### Check for offline/missing clips
```python
def check_offline_media(timeline):
    from pathlib import Path
    problems = []
    for track_idx in range(1, timeline.GetTrackCount("video") + 1):
        for item in (timeline.GetItemListInTrack("video", track_idx) or []):
            mp = item.GetMediaPoolItem()
            if not mp:
                problems.append((item.GetName(), "no media pool item"))
                continue
            path = (mp.GetClipProperty() or {}).get("File Path", "")
            if not path or not Path(path).exists():
                problems.append((item.GetName(), f"missing: {path}"))
    return problems
```

---

## Complete End-to-End Example

```python
#!/usr/bin/env python3
import os, sys, time

# --- env setup (see above) ---
setup_resolve_env()
import DaVinciResolveScript as dvr_script

resolve = dvr_script.scriptapp("Resolve")
assert resolve, "Resolve is not running"

pm = resolve.GetProjectManager()
project = pm.LoadProject("Demo") or pm.CreateProject("Demo")

project.SetSetting("timelineFrameRate", "24")
project.SetSetting("timelineResolutionWidth", "1920")
project.SetSetting("timelineResolutionHeight", "1080")

mp = project.GetMediaPool()
clips = mp.ImportMedia(["/media/video.mov", "/media/audio.wav"])
assert clips, "Import failed"

timeline = mp.CreateEmptyTimeline("Main")
project.SetCurrentTimeline(timeline)

video_frames = int(clips[0].GetClipProperty("Frames")) - 1
audio_frames = int(clips[1].GetClipProperty("Frames")) - 1

mp.AppendToTimeline([
    {"mediaPoolItem": clips[0], "startFrame": 0, "endFrame": video_frames,
     "trackIndex": 1, "recordFrame": timeline.GetStartFrame(), "mediaType": 1},
    {"mediaPoolItem": clips[1], "startFrame": 0, "endFrame": audio_frames,
     "trackIndex": 1, "recordFrame": timeline.GetStartFrame(), "mediaType": 2},
])

resolve.OpenPage("deliver")
time.sleep(0.5)
project.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
project.SetRenderSettings({"SelectAllFrames": True, "TargetDir": "/output/",
                            "CustomName": "final", "ExportVideo": True, "ExportAudio": True})
job_id = project.AddRenderJob()
project.StartRendering([job_id])
while project.IsRenderingInProgress():
    s = project.GetRenderJobStatus(job_id)
    print(f"\rRendering {s.get('CompletionPercentage', 0)}%", end="")
    time.sleep(1)
print("\nDone:", project.GetRenderJobStatus(job_id)["JobStatus"])
project.DeleteRenderJob(job_id)
pm.SaveProject()
```

---

## Important Notes

- **nodeIndex** parameters are 1-based from Resolve v16.2.0 onward (was 0-based before).
- Scripts placed in `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/` (macOS) appear in the Workspace > Scripts menu.
- The Free version of Resolve restricts some automation features — Studio is required for full render queue automation from external scripts.
- `resolve.OpenPage(name)` accepts: `"media"`, `"cut"`, `"edit"`, `"fusion"`, `"color"`, `"fairlight"`, `"deliver"`.

---

## References
- Official scripting guide (inside Resolve install): `Developer/Scripting/README.txt`
- ReadTheDocs intro: https://resolvedevdoc.readthedocs.io/en/latest/API_intro.html
- Community gists: https://gist.github.com/X-Raym/2f2bf453fc481b9cca624d7ca0e19de8
