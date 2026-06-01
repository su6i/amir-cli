---
title: "HeyGen API — AI Avatar Video Generation"
description: Generate AI avatar videos from text, manage templates, voices, and automate video production pipelines with HeyGen API
location: .agent/skills/heygen-api.md
agent_priority: Standard
last_updated: 2026-05-30
---

# Skill: HeyGen API — AI Avatar Video Generation

HeyGen generates talking-head avatar videos from text scripts. Useful for faceless YouTube channels, product demos, multilingual content at scale.

**Active API version:** v3 (v2 endpoints remain functional until Oct 2026)
**Cost:** credit-based (~0.5–3 credits per video depending on length)

---

## Authentication

```bash
export HEYGEN_API_KEY="your-api-key"  # from app.heygen.com → Settings → API
```

```python
import os, requests

HEYGEN_KEY = os.environ["HEYGEN_API_KEY"]
HEADERS = {"X-Api-Key": HEYGEN_KEY, "Content-Type": "application/json"}
BASE = "https://api.heygen.com"
```

---

## Discovery: List Avatars & Voices

```python
# List available avatars
avatars = requests.get(f"{BASE}/v2/avatars", headers=HEADERS).json()["data"]["avatars"]
for a in avatars[:5]:
    print(a["avatar_id"], a["avatar_name"])

# List available voices
voices = requests.get(f"{BASE}/v2/voices", headers=HEADERS).json()["data"]["voices"]
fr_voices = [v for v in voices if v.get("language") == "French"]
```

---

## Create Avatar Video (v2)

```python
def create_avatar_video(
    script: str,
    avatar_id: str,
    voice_id: str,
    title: str = "My Video",
    width: int = 1280,
    height: int = 720,
    bg_color: str = "#ffffff",
) -> str:
    payload = {
        "title": title,
        "dimension": {"width": width, "height": height},
        "video_inputs": [{
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal",
            },
            "voice": {
                "type": "text",
                "input_text": script,
                "voice_id": voice_id,
                "speed": 1.0,
            },
            "background": {
                "type": "color",
                "value": bg_color,
            },
        }],
    }
    resp = requests.post(f"{BASE}/v2/video/generate", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()["data"]["video_id"]
```

---

## Poll for Completion + Download

```python
import time, urllib.request

def wait_and_download(video_id: str, output_path: str, poll_interval: int = 15) -> str:
    url = f"{BASE}/v2/video_status.get?video_id={video_id}"
    while True:
        data = requests.get(url, headers=HEADERS).json()["data"]
        status = data["status"]
        if status == "completed":
            video_url = data["video_url"]
            urllib.request.urlretrieve(video_url, output_path)
            return output_path
        elif status == "failed":
            raise RuntimeError(f"HeyGen failed: {data.get('error')}")
        print(f"  [{status}] waiting {poll_interval}s...")
        time.sleep(poll_interval)
```

---

## Vertical (Shorts/Reels) Format

```python
video_id = create_avatar_video(
    script="Bonjour, voici notre analyse de données...",
    avatar_id="Vanessa-invest-20220722",
    voice_id="<fr-FR-voice-id>",
    width=720,
    height=1280,     # 9:16 vertical
    title="Short vertical",
)
```

---

## Multi-Scene Video (v2)

```python
payload = {
    "title": "Multi-scene demo",
    "dimension": {"width": 1280, "height": 720},
    "video_inputs": [
        # Scene 1 — avatar on left, slide background
        {
            "character": {"type": "avatar", "avatar_id": "...", "avatar_style": "normal"},
            "voice": {"type": "text", "input_text": "Introduction...", "voice_id": "..."},
            "background": {"type": "image", "url": "https://your-cdn.com/slide1.jpg"},
        },
        # Scene 2 — different script
        {
            "character": {"type": "avatar", "avatar_id": "...", "avatar_style": "normal"},
            "voice": {"type": "text", "input_text": "Conclusion...", "voice_id": "..."},
            "background": {"type": "color", "value": "#1a1a2e"},
        },
    ],
}
```

---

## Template API (for repeatable formats)

```python
# List templates
templates = requests.get(f"{BASE}/v2/templates", headers=HEADERS).json()["data"]

# Generate from template
resp = requests.post(
    f"{BASE}/v2/template/{template_id}/generate",
    headers=HEADERS,
    json={
        "title": "Weekly Report",
        "variables": {
            "headline": {"name": "headline", "type": "text", "properties": {"content": "Q2 Results"}},
            "avatar_script": {"name": "avatar_script", "type": "text",
                              "properties": {"content": "This week we achieved..."}},
        },
    },
)
video_id = resp.json()["data"]["video_id"]
```

---

## Video Translation (Multilingual)

```python
# Translate an existing video to another language
resp = requests.post(
    f"{BASE}/v2/video_translate",
    headers=HEADERS,
    json={
        "video_id": "existing_video_id",
        "output_language": "French",
        "title": "French version",
    },
)
translate_id = resp.json()["data"]["video_translate_id"]
```

---

## Full Pipeline: Script → Avatar Video → Download

```python
def heygen_pipeline(script: str, avatar_id: str, voice_id: str, output: str) -> str:
    print("🎬 Creating video...")
    vid_id = create_avatar_video(script, avatar_id, voice_id)
    print(f"   video_id: {vid_id}")
    path = wait_and_download(vid_id, output)
    print(f"✅ Downloaded: {path}")
    return path

# Usage
heygen_pipeline(
    script="Bonjour! Aujourd'hui nous allons explorer les données...",
    avatar_id="Vanessa-invest-20220722",
    voice_id="fr-FR-DeniseNeural",
    output="video_fr.mp4",
)
```

---

## Common Parameters

| Parameter | Values | Notes |
|---|---|---|
| `avatar_style` | `normal`, `circle`, `closeUp` | crop style |
| `speed` | 0.5–2.0 | voice speed |
| `dimension` | 1280×720, 1920×1080, 720×1280 | 16:9 or 9:16 |
| `background.type` | `color`, `image`, `video`, `transparent` | |
| `voice.type` | `text`, `audio` | audio = upload mp3 |

## Quotas & Errors

- **429 Rate limit:** back off 60s
- **402 Insufficient credits:** check `GET /v2/user/remaining.quota`
- **Video processing:** typically 1–3 min per minute of output
- Use **webhooks** in production instead of polling: set `callback_id` in request

## v3 Quick (Agent-mode)

```python
# v3: simpler prompt-based generation (no avatar_id needed)
resp = requests.post(
    f"{BASE}/v3/video-agents",
    headers={"X-Api-Key": HEYGEN_KEY},
    json={"prompt": "Explain our Q2 data analysis results in 30 seconds, professional tone"},
)
video_id = resp.json()["data"]["video_id"]
```
