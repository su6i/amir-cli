---
title: "ComfyUI & Stable Diffusion — Image Generation via Python API"
description: Generate thumbnails, B-roll images, and backgrounds for YouTube automation using ComfyUI API and SDXL
location: .agent/skills/comfyui-stable-diffusion.md
agent_priority: Standard
last_updated: 2026-05-30
---

# ComfyUI & Stable Diffusion — Image Generation via Python API

Sources: comfyanonymous/ComfyUI · AUTOMATIC1111/stable-diffusion-webui · ltdrdata/ComfyUI-Manager

---

## 1. Local Setup

### GPU requirements
| Model | VRAM min | Notes |
|-------|----------|-------|
| SD 1.5 | 2 GB | 512×512 default |
| SDXL base | 8 GB | 1024×1024; use `--lowvram` on 6 GB |
| SDXL + refiner | 12 GB | two-pass pipeline |

ComfyUI uses smart memory offloading — can run on 1 GB VRAM with `--cpu` (slow).

### Install ComfyUI
```bash
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt          # or: uv pip install -r requirements.txt

# Download SDXL base model (~6.5 GB)
mkdir -p models/checkpoints
wget -O models/checkpoints/sd_xl_base_1.0.safetensors \
  "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
```

### Start server
```bash
# Default: localhost:8188
python main.py

# Expose to network, low VRAM mode
python main.py --listen 0.0.0.0 --port 8188 --lowvram

# CPU only (no GPU)
python main.py --cpu
```

### Install ComfyUI-Manager (custom nodes hub)
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager comfyui-manager
# Restart ComfyUI — Manager tab appears in the UI
```

---

## 2. ComfyUI Python Client

The API is a simple HTTP+WebSocket interface. Real pattern from `script_examples/websockets_api_example.py`:

```python
# pip install websocket-client pillow
import json, uuid, io, urllib.request, urllib.parse
import websocket
from PIL import Image

class ComfyClient:
    def __init__(self, host="127.0.0.1:8188"):
        self.host = host
        self.client_id = str(uuid.uuid4())
        self.ws = websocket.WebSocket()
        self.ws.connect(f"ws://{host}/ws?clientId={self.client_id}")

    def _queue(self, workflow: dict) -> str:
        prompt_id = str(uuid.uuid4())
        payload = json.dumps({
            "prompt": workflow,
            "client_id": self.client_id,
            "prompt_id": prompt_id,
        }).encode()
        req = urllib.request.Request(f"http://{self.host}/prompt", data=payload)
        urllib.request.urlopen(req).read()
        return prompt_id

    def _wait(self, prompt_id: str) -> None:
        while True:
            msg = self.ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                if data.get("type") == "executing":
                    node = data["data"].get("node")
                    pid  = data["data"].get("prompt_id")
                    if node is None and pid == prompt_id:
                        break  # done

    def _download(self, prompt_id: str) -> list[bytes]:
        url = f"http://{self.host}/history/{prompt_id}"
        with urllib.request.urlopen(url) as r:
            history = json.loads(r.read())
        images = []
        for node_output in history[prompt_id]["outputs"].values():
            for img in node_output.get("images", []):
                params = urllib.parse.urlencode({
                    "filename": img["filename"],
                    "subfolder": img["subfolder"],
                    "type": img["type"],
                })
                with urllib.request.urlopen(f"http://{self.host}/view?{params}") as r:
                    images.append(r.read())
        return images

    def generate(self, workflow: dict) -> list[Image.Image]:
        prompt_id = self._queue(workflow)
        self._wait(prompt_id)
        raw = self._download(prompt_id)
        return [Image.open(io.BytesIO(b)) for b in raw]

    def close(self):
        self.ws.close()
```

---

## 3. SDXL Thumbnail Workflow (1280×720)

Export any workflow from ComfyUI via **File → Export (API)** to get the raw JSON.
This is the minimal SDXL workflow for 1280×720 thumbnails:

```python
def build_sdxl_thumbnail_workflow(
    positive: str,
    negative: str = "",
    seed: int = 42,
    steps: int = 25,
    cfg: float = 7.0,
    ckpt: str = "sd_xl_base_1.0.safetensors",
) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 1], "text": positive}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 1], "text": negative}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": 1280, "height": 720, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {
                  "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                  "latent_image": ["4", 0], "seed": seed, "steps": steps,
                  "cfg": cfg, "sampler_name": "dpmpp_2m", "scheduler": "karras",
                  "denoise": 1.0,
              }},
        "6": {"class_type": "VAEDecode",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"images": ["6", 0], "filename_prefix": "thumb"}},
    }
```

---

## 4. Prompt Engineering for YouTube Thumbnails

```python
# Template — fill in subject/emotion/topic
THUMB_POSITIVE = (
    "{subject}, {emotion} facial expression, looking at camera, "
    "dramatic cinematic lighting, shallow depth of field, "
    "high contrast vivid colors, bold {color} background with empty left third for text, "
    "professional photography, 8k resolution, sharp focus"
)

THUMB_NEGATIVE = (
    "text, watermark, logo, blurry, low quality, grainy, "
    "overexposed, underexposed, multiple people, busy background, "
    "low contrast, dull colors, cartoon, illustration"
)

# Examples per format
PRESETS = {
    "face_closeup": {
        "positive": "close-up portrait of a surprised person, wide eyes, open mouth, "
                    "dramatic studio lighting, high contrast, vivid colors, "
                    "empty right side for text overlay, 8k, sharp",
        "cfg": 8.0, "steps": 30,
    },
    "comparison": {
        "positive": "split screen comparison image, left side vs right side, "
                    "bold colors, professional infographic style, clean background",
        "cfg": 7.0, "steps": 25,
    },
    "cinematic": {
        "positive": "cinematic wide shot, dramatic sky, golden hour lighting, "
                    "empty upper third for title text, high contrast, vivid",
        "cfg": 7.5, "steps": 28,
    },
}
```

Key rules:
- Reserve left or right third of frame as empty space for text overlay
- High contrast + vivid colors outperform realistic/muted tones in CTR tests
- Specify `looking at camera` for face shots — avoids profile views
- `cfg` 7–9 for SDXL; higher = more literal prompt, lower = more creative

---

## 5. Batch Generation — 5 Variants for A/B Testing

```python
import random
from pathlib import Path

def generate_variants(
    client: ComfyClient,
    positive: str,
    output_dir: str = "thumbnails",
    n: int = 5,
    **kwargs,
) -> list[Path]:
    Path(output_dir).mkdir(exist_ok=True)
    paths = []
    for i in range(n):
        seed = random.randint(0, 2**32 - 1)
        wf = build_sdxl_thumbnail_workflow(positive, seed=seed, **kwargs)
        images = client.generate(wf)
        for img in images:
            p = Path(output_dir) / f"variant_{i+1}_seed{seed}.png"
            img.save(p)
            paths.append(p)
    return paths

# Usage
client = ComfyClient()
paths = generate_variants(
    client,
    positive=PRESETS["face_closeup"]["positive"],
    negative=THUMB_NEGATIVE,
    n=5,
    cfg=PRESETS["face_closeup"]["cfg"],
    steps=PRESETS["face_closeup"]["steps"],
)
client.close()
```

---

## 6. Text Overlay with Pillow

```python
from PIL import Image, ImageDraw, ImageFont

def add_text_overlay(
    img: Image.Image,
    title: str,
    font_size: int = 80,
    font_path: str | None = None,  # None = default PIL font
    position: tuple[int, int] = (40, 300),
    color: tuple = (255, 255, 255),
    shadow: bool = True,
) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    font = (
        ImageFont.truetype(font_path, font_size)
        if font_path
        else ImageFont.load_default(size=font_size)
    )
    if shadow:
        # Drop shadow: offset (4, 4), black semi-transparent
        sx, sy = position[0] + 4, position[1] + 4
        draw.text((sx, sy), title, font=font, fill=(0, 0, 0, 180))
    draw.text(position, title, font=font, fill=color)
    return out

# Usage after generation
for path in paths:
    img = Image.open(path)
    img = add_text_overlay(img, "5 AI Tools That Changed Everything", font_size=72)
    img.save(path)  # overwrite with overlay
```

---

## 7. AUTOMATIC1111 WebUI API

Start A1111 with API enabled:
```bash
./webui.sh --api --nowebui          # Linux/macOS
# Windows: webui-user.bat --api --nowebui
```

```python
import requests, base64, io
from PIL import Image

A1111_URL = "http://127.0.0.1:7860"

def a1111_txt2img(
    prompt: str,
    negative: str = "",
    width: int = 1280,
    height: int = 720,
    steps: int = 25,
    cfg_scale: float = 7.0,
    seed: int = -1,
    model: str | None = None,   # override checkpoint
    n_iter: int = 1,
) -> list[Image.Image]:
    payload = {
        "prompt": prompt,
        "negative_prompt": negative,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "seed": seed,
        "n_iter": n_iter,
        "batch_size": 1,
        "sampler_name": "DPM++ 2M Karras",
    }
    if model:
        # switch checkpoint before generation
        requests.post(f"{A1111_URL}/sdapi/v1/options",
                      json={"sd_model_checkpoint": model})

    r = requests.post(f"{A1111_URL}/sdapi/v1/txt2img", json=payload)
    r.raise_for_status()
    images = []
    for b64 in r.json()["images"]:
        images.append(Image.open(io.BytesIO(base64.b64decode(b64))))
    return images

# List available models
def list_models() -> list[str]:
    r = requests.get(f"{A1111_URL}/sdapi/v1/sd-models")
    return [m["title"] for m in r.json()]
```

---

## 8. Choosing Between ComfyUI and A1111

For YouTube thumbnail automation, **prefer ComfyUI**: node graph enables ControlNet pose control, face detailer, and upscaler in one queued job. A1111 is simpler for quick one-shot generation — use `POST /sdapi/v1/txt2img` with a flat JSON payload; ComfyUI requires workflow JSON but gives full pipeline control. A1111 uses polling (`/sdapi/v1/progress`); ComfyUI uses WebSocket for real-time execution events.
