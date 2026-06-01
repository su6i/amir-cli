---
title: "AI Video Generation APIs"
description: Generate video from text/image prompts via RunwayML, Kling, Luma, Pika, and Minimax APIs
location: .agent/skills/ai-video-generation.md
agent_priority: Standard
last_updated: 2026-05-30
---

# AI Video Generation APIs

## Overview

Five major APIs for programmatic AI video generation as of mid-2026. All use async job patterns:
submit request → receive task_id → poll until complete → download MP4.

**Install all SDKs:**
```bash
pip install runwayml lumaai fal-client requests python-jose
```

---

## 1. RunwayML (Gen-3 Alpha / Gen-4 Turbo)

**Official docs:** https://docs.dev.runwayml.com  
**Python SDK:** https://github.com/runwayml/sdk-python  
**Install:** `pip install runwayml`

### Authentication
```python
import os
from runwayml import RunwayML

client = RunwayML(api_key=os.environ["RUNWAYML_API_SECRET"])
```

### Image-to-Video (primary use case)
```python
task = client.image_to_video.create(
    model="gen4_turbo",           # or "gen3a_turbo" (older, cheaper)
    prompt_image="https://example.com/frame.jpg",
    ratio="1280:720",             # "1280:720" | "720:1280" | "1104:832" | "832:1104" | "960:960"
    prompt_text="Camera slowly zooms in, cinematic lighting",
    duration=5,                   # 5 or 10 seconds
)
task_id = task.id
```

### Text-to-Video (Gen-4.5+, no image needed)
```python
task = client.image_to_video.create(
    model="gen4_turbo",
    prompt_text="A serene mountain lake at dawn, cinematic drone shot",
    ratio="1280:720",
    duration=5,
)
```

### Polling for completion
```python
import time

# Option A — built-in helper (recommended)
output = task.wait_for_task_output()   # blocks up to 10 min by default
print(output.output[0])                # URL to MP4

# Option B — manual polling with exponential backoff
def poll_runway(client, task_id: str, max_wait: int = 600) -> str:
    delay = 5
    elapsed = 0
    while elapsed < max_wait:
        task = client.tasks.retrieve(task_id)
        if task.status == "SUCCEEDED":
            return task.output[0]
        if task.status == "FAILED":
            raise RuntimeError(f"Runway task failed: {task.failure}")
        time.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 30)  # cap at 30s
    raise TimeoutError("Runway task timed out")
```

### Key parameters
| Parameter | Values | Notes |
|-----------|--------|-------|
| `model` | `gen4_turbo`, `gen3a_turbo` | gen4_turbo = higher quality |
| `ratio` | `1280:720`, `720:1280`, `960:960` | landscape / portrait / square |
| `duration` | `5`, `10` | seconds |
| `prompt_text` | string | motion/style description |

### Pricing (2026)
- **Gen-4 Turbo:** ~$0.05/sec ($0.25 for 5s, $0.50 for 10s)
- **Gen-3 Alpha Turbo:** ~$0.05/sec (5 credits/sec via subscription)
- API access requires Runway Standard plan ($15/mo) or higher

---

## 2. Kling AI (v1 / v2 / v3)

**Official docs:** https://app.klingai.com/global/dev/document-api  
**Base URL:** `https://api.klingai.com`  
**Auth:** JWT from Access Key + Secret Key (expires 30 min)

### Authentication — JWT generation
```python
import time
import requests
from jose import jwt   # pip install python-jose

def _get_kling_jwt(access_key: str, secret_key: str) -> str:
    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + 1800,   # 30 minutes
        "nbf": now - 5,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")

def kling_headers(access_key: str, secret_key: str) -> dict:
    token = _get_kling_jwt(access_key, secret_key)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
```

### Text-to-Video
```python
BASE_URL = "https://api.klingai.com"

def kling_text_to_video(
    prompt: str,
    model_name: str = "kling-v2.6-pro",   # or "kling-v3-text-to-video"
    duration: str = "5",                    # "5" or "10" (str, not int)
    aspect_ratio: str = "16:9",             # "16:9" | "9:16" | "1:1"
    mode: str = "pro",                      # "std" | "pro"
    negative_prompt: str = "",
    cfg_scale: float = 0.5,
) -> str:
    """Returns task_id."""
    headers = kling_headers(
        os.environ["KLING_ACCESS_KEY"],
        os.environ["KLING_SECRET_KEY"],
    )
    payload = {
        "model_name": model_name,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "cfg_scale": cfg_scale,
        "mode": mode,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
    }
    resp = requests.post(f"{BASE_URL}/v1/videos/text2video", json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["task_id"]
```

### Image-to-Video
```python
def kling_image_to_video(
    image_url: str,
    prompt: str,
    model_name: str = "kling-v2.6-pro",
    duration: str = "5",
    aspect_ratio: str = "16:9",
) -> str:
    headers = kling_headers(
        os.environ["KLING_ACCESS_KEY"],
        os.environ["KLING_SECRET_KEY"],
    )
    payload = {
        "model_name": model_name,
        "image": image_url,
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
    }
    resp = requests.post(f"{BASE_URL}/v1/videos/image2video", json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()["data"]["task_id"]
```

### Polling
```python
def poll_kling(task_id: str, max_wait: int = 600) -> str:
    headers = kling_headers(
        os.environ["KLING_ACCESS_KEY"],
        os.environ["KLING_SECRET_KEY"],
    )
    delay = 5
    elapsed = 0
    while elapsed < max_wait:
        resp = requests.get(f"{BASE_URL}/v1/tasks/{task_id}", headers=headers)
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data["task_status"]
        if status == "succeed":
            return data["task_result"]["videos"][0]["url"]
        if status == "failed":
            raise RuntimeError(f"Kling failed: {data.get('task_status_msg')}")
        time.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 30)
    raise TimeoutError("Kling task timed out")
```

### Models available (2026)
| Model | Max duration | Notes |
|-------|-------------|-------|
| `kling-v1-standard` | 10s | Budget |
| `kling-v2.6-pro` | 10s | Good quality/cost ratio |
| `kling-v3-text-to-video` | 15s | Latest, native audio-visual sync |

### Pricing (2026)
- ~$0.07/sec (Kling 3.0 standard mode)
- Subscription: $6.99/mo (Kling Standard)

---

## 3. Luma Dream Machine (Ray 2 / Ray Flash)

**Official docs:** https://docs.lumalabs.ai/docs/video-generation  
**Python SDK:** https://github.com/lumalabs/lumaai-python  
**Install:** `pip install lumaai`

### Authentication
```python
import os
from lumaai import LumaAI

client = LumaAI(auth_token=os.environ["LUMAAI_API_KEY"])
# Or set env var LUMAAI_API_KEY — SDK picks it up automatically
```

### Text-to-Video
```python
generation = client.generations.create(
    model="ray-2",             # "ray-2" | "ray-flash-2" (faster/cheaper)
    prompt="A bioluminescent forest at midnight, slow dolly shot",
    aspect_ratio="16:9",       # "16:9" | "9:16" | "4:3" | "3:4" | "21:9" | "9:21" | "1:1"
    loop=False,
)
generation_id = generation.id
```

### Image-to-Video
```python
generation = client.generations.create(
    model="ray-2",
    prompt="Camera pulls back slowly to reveal the city",
    aspect_ratio="16:9",
    keyframes={
        "frame0": {
            "type": "image",
            "url": "https://example.com/start_frame.jpg",
        }
    },
)
```

### Video-to-Video (extend / interpolate)
```python
# Extend an existing video
generation = client.generations.create(
    model="ray-2",
    prompt="Continue the motion forward",
    keyframes={
        "frame0": {
            "type": "generation",
            "id": "<previous_generation_id>",
        }
    },
)
```

### Polling
```python
def poll_luma(client: LumaAI, generation_id: str, max_wait: int = 600) -> str:
    delay = 3
    elapsed = 0
    while elapsed < max_wait:
        gen = client.generations.get(generation_id)
        if gen.state == "completed":
            return gen.assets.video   # direct MP4 URL
        if gen.state == "failed":
            raise RuntimeError(f"Luma failed: {gen.failure_reason}")
        time.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 20)
    raise TimeoutError("Luma generation timed out")
```

### Key parameters
| Parameter | Values | Notes |
|-----------|--------|-------|
| `model` | `ray-2`, `ray-flash-2` | ray-flash-2 = ~2x faster, lower cost |
| `aspect_ratio` | `16:9`, `9:16`, `1:1`, `4:3`, `21:9` | |
| `loop` | `True`/`False` | Seamless loop for background videos |

### Pricing (2026)
- Ray 2: ~$0.09/video (5s) via subscription
- API: pay-per-generation via https://lumalabs.ai/dream-machine/api/keys

---

## 4. Pika 2.2 (via fal.ai)

**fal.ai model page:** https://fal.ai/models/fal-ai/pika/v2.2/text-to-video  
**Install:** `pip install fal-client`

Pika 2.2 API is officially hosted on fal.ai (announced December 2025). Direct Pika API requires applying at pika.art/api for enterprise access. The fal.ai route is the standard developer path.

### Authentication
```python
import os
import fal_client

# Set FAL_KEY env var — fal_client picks it up automatically
os.environ["FAL_KEY"] = "your-fal-key"   # or set in shell
```

### Text-to-Video
```python
result = fal_client.subscribe(
    "fal-ai/pika/v2.2/text-to-video",
    arguments={
        "prompt": "A glowing jellyfish drifting in deep ocean, cinematic",
        "negative_prompt": "blurry, distorted, low quality",
        "resolution": "1080p",      # "720p" | "1080p"
        "duration": 5,              # 5 or 10 seconds
        "aspect_ratio": "16:9",     # "16:9" | "9:16" | "1:1" | "4:5" | "5:4" | "3:2" | "2:3"
        "fps": 24,
    },
    with_logs=True,
    on_queue_update=lambda u: print(u.logs) if hasattr(u, "logs") else None,
)
video_url = result["video"]["url"]
```

### Image-to-Video
```python
result = fal_client.subscribe(
    "fal-ai/pika/v2.2/image-to-video",
    arguments={
        "image_url": "https://example.com/input.jpg",
        "prompt": "Gentle ripples move across the surface",
        "resolution": "1080p",
        "duration": 5,
    },
)
video_url = result["video"]["url"]
```

### Async pattern (non-blocking)
```python
handler = fal_client.submit(
    "fal-ai/pika/v2.2/text-to-video",
    arguments={"prompt": "...", "resolution": "720p", "duration": 5},
)
request_id = handler.request_id

# ... do other work ...

result = fal_client.result("fal-ai/pika/v2.2/text-to-video", request_id)
```

### Pricing (2026)
- 5s at 720p: $0.20/video
- 5s at 1080p: $0.45/video
- 10s at 1080p: $0.90/video

---

## 5. Minimax / Hailuo (Video-01, Hailuo-02, Hailuo-2.3)

**Official docs:** https://platform.minimax.io/docs/guides/video-generation  
**Base URL:** `https://api.minimax.io/v1`

### Authentication
```python
import os, requests

MINIMAX_API_KEY = os.environ["MINIMAX_API_KEY"]
MINIMAX_HEADERS = {
    "Authorization": f"Bearer {MINIMAX_API_KEY}",
    "Content-Type": "application/json",
}
```

### Text-to-Video
```python
def minimax_text_to_video(
    prompt: str,
    model: str = "MiniMax-Hailuo-02",   # or "video-01", "MiniMax-Hailuo-2.3"
    duration: int = 6,                   # 6 seconds (Hailuo-02 default)
    resolution: str = "1080P",           # "720P" | "1080P"
) -> str:
    """Returns task_id."""
    resp = requests.post(
        "https://api.minimax.io/v1/video_generation",
        json={"prompt": prompt, "model": model, "duration": duration, "resolution": resolution},
        headers=MINIMAX_HEADERS,
    )
    resp.raise_for_status()
    return resp.json()["task_id"]
```

### Image-to-Video
```python
def minimax_image_to_video(
    prompt: str,
    image_url: str,
    model: str = "MiniMax-Hailuo-02",
    duration: int = 6,
    resolution: str = "1080P",
) -> str:
    resp = requests.post(
        "https://api.minimax.io/v1/video_generation",
        json={
            "prompt": prompt,
            "model": model,
            "first_frame_image": image_url,
            "duration": duration,
            "resolution": resolution,
        },
        headers=MINIMAX_HEADERS,
    )
    resp.raise_for_status()
    return resp.json()["task_id"]
```

### Polling
```python
def poll_minimax(task_id: str, max_wait: int = 600) -> str:
    delay = 5
    elapsed = 0
    while elapsed < max_wait:
        resp = requests.get(
            f"https://api.minimax.io/v1/query/video_generation?task_id={task_id}",
            headers=MINIMAX_HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data["status"]
        if status == "Success":
            return data["file_id"]   # use retrieve_file endpoint to get download URL
        if status == "Fail":
            raise RuntimeError(f"Minimax failed: {data.get('base_resp', {}).get('status_msg')}")
        time.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 30)
    raise TimeoutError("Minimax task timed out")

def minimax_get_video_url(file_id: str) -> str:
    resp = requests.get(
        f"https://api.minimax.io/v1/files/retrieve?file_id={file_id}",
        headers=MINIMAX_HEADERS,
    )
    resp.raise_for_status()
    return resp.json()["file"]["download_url"]
```

### Models available (2026)
| Model | Resolution | Notes |
|-------|-----------|-------|
| `video-01` | 720p | Original, widely supported |
| `MiniMax-Hailuo-02` | 1080p | Improved quality |
| `MiniMax-Hailuo-2.3` | 1080p | Best current quality |
| `hailuo-3.0` (beta) | 4K | Next-gen, limited access |

### Pricing (2026)
- ~$0.07/sec ($0.42 for 6s at 1080p)
- Direct API access: https://platform.minimax.io

---

## Comparison Table

| Provider | Max Duration | Max Res | Cost/5s | Auth Method | Best For |
|----------|-------------|---------|---------|-------------|----------|
| **RunwayML Gen-4 Turbo** | 10s | 1280×720 | ~$0.25 | API secret key | Cinematic motion, image-to-video |
| **Kling v3** | 15s | 1080p | ~$0.35 | JWT (30 min TTL) | Long clips, audio-visual sync |
| **Luma Ray 2** | ~5s | 1080p | ~$0.09 | Bearer token | Fluid motion, looping background |
| **Pika 2.2** | 10s | 1080p | $0.45 | fal.ai key | Stylized, creative effects |
| **Minimax Hailuo-02** | 6s | 1080p | ~$0.35 | Bearer token | Realism, cost-effective |

**Recommended by use case:**
- Cinematic quality: RunwayML Gen-4 Turbo or Luma Ray 2
- Lowest cost: Minimax Hailuo or Kling v2.6 standard
- Longest clip: Kling v3 (15 seconds)
- Easiest Python integration: Luma (official SDK) or Runway (official SDK)
- Batch production: Minimax or Kling (REST API, no special SDK needed)

---

## Common Pattern: Async Job Polling with Exponential Backoff

Use this generic poller for any provider that returns a task_id:

```python
import time
from typing import Callable, Any

def poll_with_backoff(
    check_fn: Callable[[], tuple[str, Any]],
    success_status: str,
    failure_status: str,
    initial_delay: float = 5.0,
    backoff_factor: float = 1.5,
    max_delay: float = 30.0,
    max_wait: float = 600.0,
    jitter: float = 0.5,
) -> Any:
    """
    Generic exponential backoff poller.

    check_fn() must return (status_str, result_or_None).
    Returns result when status == success_status.
    Raises RuntimeError on failure_status.
    """
    import random
    delay = initial_delay
    elapsed = 0.0
    while elapsed < max_wait:
        status, result = check_fn()
        if status == success_status:
            return result
        if status == failure_status:
            raise RuntimeError(f"Job failed with status: {status}")
        sleep_time = delay + random.uniform(0, jitter)
        time.sleep(sleep_time)
        elapsed += sleep_time
        delay = min(delay * backoff_factor, max_delay)
    raise TimeoutError(f"Job did not complete within {max_wait}s")
```

**Usage example (Minimax):**
```python
task_id = minimax_text_to_video("A volcano erupting at night")

def check():
    resp = requests.get(
        f"https://api.minimax.io/v1/query/video_generation?task_id={task_id}",
        headers=MINIMAX_HEADERS,
    )
    data = resp.json()
    return data["status"], data.get("file_id")

file_id = poll_with_backoff(check, success_status="Success", failure_status="Fail")
url = minimax_get_video_url(file_id)
```

---

## Batch Generation Pipeline

Generate multiple videos concurrently with a rate-limit-aware worker pool:

```python
import asyncio
import aiohttp
import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

@dataclass
class VideoJob:
    prompt: str
    provider: str          # "runway" | "kling" | "luma" | "pika" | "minimax"
    output_path: Path
    image_url: Optional[str] = None
    duration: int = 5
    aspect_ratio: str = "16:9"
    task_id: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None


async def submit_job(job: VideoJob) -> VideoJob:
    """Submit one job to the appropriate provider and store task_id."""
    try:
        if job.provider == "luma":
            client = LumaAI()
            gen = client.generations.create(
                model="ray-2",
                prompt=job.prompt,
                aspect_ratio=job.aspect_ratio,
                keyframes={"frame0": {"type": "image", "url": job.image_url}} if job.image_url else None,
            )
            job.task_id = gen.id

        elif job.provider == "runway":
            client = RunwayML()
            task = client.image_to_video.create(
                model="gen4_turbo",
                prompt_image=job.image_url or "",
                prompt_text=job.prompt,
                ratio="1280:720",
                duration=job.duration,
            )
            job.task_id = task.id

        elif job.provider == "minimax":
            if job.image_url:
                job.task_id = minimax_image_to_video(job.prompt, job.image_url)
            else:
                job.task_id = minimax_text_to_video(job.prompt)

        elif job.provider == "kling":
            if job.image_url:
                job.task_id = kling_image_to_video(job.image_url, job.prompt)
            else:
                job.task_id = kling_text_to_video(job.prompt)

    except Exception as e:
        job.error = str(e)
    return job


def collect_results(jobs: list[VideoJob]) -> list[VideoJob]:
    """Poll all submitted jobs until done. Returns updated jobs list."""
    pending = [j for j in jobs if j.task_id and not j.error]
    deadline = time.time() + 600

    while pending and time.time() < deadline:
        still_pending = []
        for job in pending:
            try:
                if job.provider == "luma":
                    client = LumaAI()
                    gen = client.generations.get(job.task_id)
                    if gen.state == "completed":
                        job.video_url = gen.assets.video
                    elif gen.state == "failed":
                        job.error = gen.failure_reason
                    else:
                        still_pending.append(job)

                elif job.provider == "runway":
                    client = RunwayML()
                    t = client.tasks.retrieve(job.task_id)
                    if t.status == "SUCCEEDED":
                        job.video_url = t.output[0]
                    elif t.status == "FAILED":
                        job.error = t.failure
                    else:
                        still_pending.append(job)

                elif job.provider == "minimax":
                    resp = requests.get(
                        f"https://api.minimax.io/v1/query/video_generation?task_id={job.task_id}",
                        headers=MINIMAX_HEADERS,
                    )
                    data = resp.json()
                    if data["status"] == "Success":
                        job.video_url = minimax_get_video_url(data["file_id"])
                    elif data["status"] == "Fail":
                        job.error = "Minimax generation failed"
                    else:
                        still_pending.append(job)

                elif job.provider == "kling":
                    headers = kling_headers(
                        os.environ["KLING_ACCESS_KEY"],
                        os.environ["KLING_SECRET_KEY"],
                    )
                    resp = requests.get(
                        f"https://api.klingai.com/v1/tasks/{job.task_id}",
                        headers=headers,
                    )
                    data = resp.json()["data"]
                    if data["task_status"] == "succeed":
                        job.video_url = data["task_result"]["videos"][0]["url"]
                    elif data["task_status"] == "failed":
                        job.error = data.get("task_status_msg", "Kling failed")
                    else:
                        still_pending.append(job)

            except Exception as e:
                job.error = str(e)

        pending = still_pending
        if pending:
            time.sleep(10)

    return jobs


def download_videos(jobs: list[VideoJob]) -> None:
    """Download completed videos to their output paths."""
    for job in jobs:
        if job.video_url and not job.error:
            resp = requests.get(job.video_url, stream=True)
            resp.raise_for_status()
            job.output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(job.output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Saved: {job.output_path}")
        elif job.error:
            print(f"Failed [{job.provider}]: {job.error}")


# --- Example usage ---
if __name__ == "__main__":
    import asyncio

    jobs = [
        VideoJob(
            prompt="Aerial shot of Paris at golden hour",
            provider="luma",
            output_path=Path("output/paris.mp4"),
            aspect_ratio="16:9",
        ),
        VideoJob(
            prompt="Underwater coral reef, fish swimming",
            provider="minimax",
            output_path=Path("output/coral.mp4"),
            duration=6,
        ),
        VideoJob(
            prompt="Cyberpunk cityscape at night, neon rain",
            provider="kling",
            output_path=Path("output/cyberpunk.mp4"),
            duration=5,
        ),
    ]

    # Submit all jobs concurrently
    submitted = asyncio.run(asyncio.gather(*[submit_job(j) for j in jobs]))

    # Wait for all to finish
    completed = collect_results(list(submitted))

    # Download results
    download_videos(completed)
```

---

## Environment Variables

```bash
# ~/.amir/config.yaml or .env
RUNWAYML_API_SECRET=rw-...
KLING_ACCESS_KEY=...
KLING_SECRET_KEY=...
LUMAAI_API_KEY=...
FAL_KEY=...              # for Pika via fal.ai
MINIMAX_API_KEY=...
```

---

## Notes and Gotchas

1. **Kling JWT refresh:** tokens expire in 30 min. In long batch jobs, regenerate before each request rather than caching once.

2. **Runway ratio format:** use `"1280:720"` (string with colon), not `"16:9"`. SDK will reject `"16:9"`.

3. **Pika via fal.ai:** `fal_client.subscribe()` blocks until done. Use `fal_client.submit()` + `fal_client.result()` for non-blocking batch work.

4. **Minimax file_id:** the polling endpoint returns a `file_id`, not a direct URL. Always call the `/v1/files/retrieve` endpoint to get the actual download URL.

5. **Luma keyframes:** `frame0` = start frame, `frame1` = end frame. Both can be set simultaneously for start+end image interpolation.

6. **Rate limits (2026 estimates):** Runway ~10 concurrent tasks; Kling ~5/min on standard plans; Luma ~10/min; Minimax varies by plan.

7. **Video downloads expire:** all provider URLs are time-limited (typically 24–72h). Download immediately after generation.

8. **Audio:** none of these five APIs generate audio natively (Kling v3 has audio-visual sync but requires prompting). Use `amir` + ElevenLabs/Gemini TTS separately, then merge with FFmpeg.
