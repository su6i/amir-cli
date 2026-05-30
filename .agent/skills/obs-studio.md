---
title: "OBS Studio Scripting"
description: Control OBS Studio via in-process obspython scripts or external obsws-python WebSocket SDK
location: .agent/skills/obs-studio.md
agent_priority: Standard
last_updated: 2026-05-30
---

# Skill: OBS Studio Scripting

Two distinct control modes exist:
- **In-process (obspython)** — Python script loaded inside OBS via Tools > Scripts. Full access to the C API via `import obspython as S`. Runs in the OBS process.
- **External (obsws-python)** — Python process outside OBS connecting over WebSocket v5 (port 4455). Included by default in OBS >= 28.

---

## In-Process: obspython Basics

### Script lifecycle hooks
```python
import obspython as S

def script_description():   return "My Script"
def script_load(settings):  pass   # called once on load
def script_unload():        pass   # called once on unload
def script_save(settings):  pass   # persist hotkey bindings etc.
def script_defaults(settings): pass
def script_properties():    return S.obs_properties_create()
def script_update(settings): pass  # called when settings change
```

### Scene switching
```python
def set_scene_by_name(scene_name: str):
    scenes = S.obs_frontend_get_scenes()
    for scene in scenes:
        if S.obs_source_get_name(scene) == scene_name:
            S.obs_frontend_set_current_scene(scene)
            break
    # no release needed — obs_frontend_get_scenes releases on gc
```

### Source visibility toggle
```python
def toggle_source_visibility(source_name: str):
    current_scene = S.obs_frontend_get_current_scene()
    scene = S.obs_scene_from_source(current_scene)
    scene_item = S.obs_scene_find_source(scene, source_name)
    if scene_item:
        visible = not S.obs_sceneitem_visible(scene_item)
        S.obs_sceneitem_set_visible(scene_item, visible)
    S.obs_source_release(current_scene)
```

### Recording start / stop
```python
# Check state
def is_recording() -> bool:
    return S.obs_frontend_recording_active()

def is_recording_paused() -> bool:
    return S.obs_frontend_recording_paused()

# Control (no return value)
S.obs_frontend_recording_start()
S.obs_frontend_recording_stop()
S.obs_frontend_recording_pause(True)   # pause
S.obs_frontend_recording_pause(False)  # resume
```

### Streaming start / stop
```python
S.obs_frontend_streaming_start()
S.obs_frontend_streaming_stop()
is_live = S.obs_frontend_streaming_active()
```

### Add a source to current scene
```python
def add_text_source(text: str, source_name: str):
    settings = S.obs_data_create()
    S.obs_data_set_string(settings, "text", text)
    source = S.obs_source_create_private("text_gdiplus", source_name, settings)
    scene = S.obs_scene_from_source(S.obs_frontend_get_current_scene())
    S.obs_scene_add(scene, source)
    S.obs_data_release(settings)
    S.obs_source_release(source)
```

Source type identifier strings:
| Source | ID string |
|---|---|
| Browser | `browser_source` |
| Display Capture | `monitor_capture` |
| Game Capture | `game_capture` |
| Image | `image_source` |
| Media Source | `ffmpeg_source` |
| Text (GDI+) | `text_gdiplus` |
| Window Capture | `window_capture` |
| Color Source | `color_source` |

### Add a filter to a source
```python
def add_opacity_filter(source_name: str, opacity: int = 50):
    source = S.obs_get_source_by_name(source_name)
    settings = S.obs_data_create()
    S.obs_data_set_int(settings, "opacity", opacity)
    f = S.obs_source_create_private("color_filter", f"opacity_{opacity}", settings)
    S.obs_source_filter_add(source, f)
    S.obs_data_release(settings)
    S.obs_source_release(f)
    S.obs_source_release(source)
```

### Events (frontend callbacks)
```python
def on_event(event):
    if event == S.OBS_FRONTEND_EVENT_SCENE_CHANGED:
        current = S.obs_frontend_get_current_scene()
        print("Scene changed to:", S.obs_source_get_name(current))
        S.obs_source_release(current)
    elif event == S.OBS_FRONTEND_EVENT_RECORDING_STARTED:
        print("Recording started")
    elif event == S.OBS_FRONTEND_EVENT_RECORDING_STOPPED:
        print("Recording stopped")

def script_load(settings):
    S.obs_frontend_add_event_callback(on_event)
```

Key frontend event constants:
`OBS_FRONTEND_EVENT_SCENE_CHANGED`, `OBS_FRONTEND_EVENT_RECORDING_STARTED`,
`OBS_FRONTEND_EVENT_RECORDING_STOPPED`, `OBS_FRONTEND_EVENT_STREAMING_STARTED`,
`OBS_FRONTEND_EVENT_STREAMING_STOPPED`, `OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED`

### Timers (in-script polling)
```python
def tick():
    print("tick")

def script_load(settings):
    S.timer_add(tick, 1000)   # every 1 s

def script_unload():
    S.timer_remove(tick)
```

### Hotkey registration (persistent)
```python
HOTKEY_ID = S.OBS_INVALID_HOTKEY_ID

def on_hotkey(pressed):
    if pressed:
        set_scene_by_name("Gaming")

def script_load(settings):
    global HOTKEY_ID
    HOTKEY_ID = S.obs_hotkey_register_frontend(
        "switch_to_gaming", "Switch to Gaming scene", on_hotkey
    )
    saved = S.obs_data_get_array(settings, "hotkey_switch")
    S.obs_hotkey_load(HOTKEY_ID, saved)
    S.obs_data_array_release(saved)

def script_save(settings):
    arr = S.obs_hotkey_save(HOTKEY_ID)
    S.obs_data_set_array(settings, "hotkey_switch", arr)
    S.obs_data_array_release(arr)
```

### Debug tips
- No stdin — use `print()` (goes to OBS log, also in Help > Log Files > View Current Log)
- VS Code attach: install `debugpy`, place `debugpy.breakpoint()`, attach by Process ID (obs64.exe on Windows)

---

## External: obsws-python (WebSocket v5)

### Install
```bash
pip install obsws-python
```

### Config file (optional) — `~/config.toml`
```toml
[connection]
host = "localhost"
port = 4455
password = "mystrongpass"
```

### Request client — basic usage
```python
import obsws_python as obs

cl = obs.ReqClient(host='localhost', port=4455, password='mystrongpass', timeout=3)

# Get OBS version
resp = cl.get_version()
print(resp.obs_version)

# Scene switching
cl.set_current_program_scene("Gaming")

# List all scenes
resp = cl.get_scene_list()
for scene in resp.scenes:
    print(scene['sceneName'])

# Source visibility
cl.set_scene_item_enabled(
    scene_name="Main",
    item_id=3,          # scene item ID, not source name
    enabled=True
)

# Mute toggle
cl.toggle_input_mute('Mic/Aux')

# Recording
cl.start_record()
cl.stop_record()
resp = cl.get_record_status()
print(resp.output_active)   # True/False

# Streaming
cl.start_stream()
cl.stop_stream()
resp = cl.get_stream_status()
print(resp.output_active)
```

### Event client — async callbacks
```python
import obsws_python as obs

cl = obs.EventClient(host='localhost', port=4455, password='mystrongpass')

def on_scene_created(data):
    print("New scene:", data.attrs())

def on_input_mute_state_changed(data):
    print("Mute changed:", data.input_name, data.input_muted)

cl.callback.register([on_scene_created, on_input_mute_state_changed])

# Block main thread
import time
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    cl.disconnect()
```

### Raw send (for unlisted requests)
```python
resp = cl.send("GetVersion", raw=True)
print(resp)   # raw dict
```

### Error handling
```python
from obsws_python import OBSSDKRequestError, OBSSDKTimeoutError

try:
    cl.set_current_program_scene("NonExistent")
except OBSSDKRequestError as e:
    print(f"Request failed: {e.req_name} code={e.code}")
except OBSSDKTimeoutError:
    print("Timeout — OBS not responding")
```

### Key WebSocket requests (snake_case method names)
| API call | obsws-python method |
|---|---|
| `GetVersion` | `get_version()` |
| `GetSceneList` | `get_scene_list()` |
| `SetCurrentProgramScene` | `set_current_program_scene(scene_name)` |
| `GetInputList` | `get_input_list()` |
| `ToggleInputMute` | `toggle_input_mute(input_name)` |
| `StartRecord` | `start_record()` |
| `StopRecord` | `stop_record()` |
| `GetRecordStatus` | `get_record_status()` |
| `StartStream` | `start_stream()` |
| `StopStream` | `stop_stream()` |
| `SaveReplayBuffer` | `save_replay_buffer()` |
| `GetSceneItemId` | `get_scene_item_id(scene_name, source_name)` |
| `SetSceneItemEnabled` | `set_scene_item_enabled(scene_name, item_id, enabled)` |
| `SetInputSettings` | `set_input_settings(input_name, settings, overlay)` |

---

## Choosing the Right Approach

| Criterion | obspython (in-process) | obsws-python (external) |
|---|---|---|
| Access to C API | Full | Limited to WS protocol |
| Requires OBS restart on change | Yes | No |
| Can run from another machine | No | Yes |
| Complexity | Higher | Lower |
| Best for | Custom filters, raw frame access, tight integration | Automation scripts, remote control, CI/CD |

---

## References
- OBS docs: https://obsproject.com/docs/scripting.html
- obspython full export: https://github.com/upgradeQ/Streaming-Software-Scripting-Reference/blob/master/src/export.md
- WebSocket protocol: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md
- obsws-python PyPI: https://pypi.org/project/obsws-python
