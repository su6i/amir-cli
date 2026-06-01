---
title: "GPT-SoVITS v2 — Few-Shot Voice Cloning"
description: Train a high-quality voice clone with 1–5 minutes of audio — GPT-SoVITS v2 training pipeline and inference API
location: .agent/skills/gpt-sovits.md
agent_priority: Standard
last_updated: 2026-05-30
---

# GPT-SoVITS v2 — Few-Shot Voice Cloning

GPT-SoVITS is a powerful few-shot voice conversion and TTS system. Zero-shot from 5 seconds; fine-tune with 1 minute for high similarity. Current latest: v2Pro / v4.

- GitHub: https://github.com/RVC-Boss/GPT-SoVITS
- License: MIT
- Colab: https://colab.research.google.com/github/RVC-Boss/GPT-SoVITS/blob/main/Colab-WebUI.ipynb
- User guide (English): https://rentry.co/GPT-SoVITS-guide#/

---

## Version Overview

| Version | Notes |
|---|---|
| v1 | Original, stable |
| v2 | Adds Korean, Cantonese; improved text frontend; 5k hours base |
| v3 | Higher timbre similarity; less data needed; 24kHz output |
| v4 | Fixes v3 metallic artifacts; native 48kHz; replaces v3 |
| v2Pro | Slightly higher VRAM than v2; surpasses v4 quality; best for low-quality recordings |

**Rule of thumb:** for clean studio audio → v4. For average/noisy recordings → v2Pro.

---

## GPU Requirements

| Task | Minimum VRAM | Recommended |
|---|---|---|
| Inference (zero-shot) | 4 GB | 6 GB |
| Fine-tuning (v2/v2Pro) | 6 GB | 8 GB |
| Fine-tuning (v3/v4) | 8 GB | 16 GB |
| Apple Silicon (MPS) | inference only (CPU train) | M1 16GB+ |

RTF benchmarks: 0.028 on RTX 4060 Ti; 0.014 on RTX 4090; 0.526 on M4 CPU.

---

## Installation

### conda (Linux / macOS)

```bash
conda create -n GPTSoVits python=3.10
conda activate GPTSoVits

# Linux (CUDA 12.6)
bash install.sh --device CU126 --source HF

# macOS (Apple Silicon)
bash install.sh --device MPS --source HF

# CPU only
bash install.sh --device CPU --source HF
```

### Windows

```powershell
conda create -n GPTSoVits python=3.10
conda activate GPTSoVits
pwsh -F install.ps1 --Device CU126 --Source HF
```

Or download the all-in-one integrated package from HuggingFace and run `_go-webui.bat`.

### Manual pip

```bash
conda create -n GPTSoVits python=3.10
conda activate GPTSoVits
pip install -r extra-req.txt --no-deps
pip install -r requirements.txt

# macOS FFmpeg
brew install ffmpeg

# Linux FFmpeg
sudo apt install ffmpeg libsox-dev
```

---

## Pretrained Models

```bash
# v4 pretrained (recommended default)
# Place in GPT_SoVITS/pretrained_models/gsv-v4-pretrained/
# Files: s2v4.pth, vocoder.pth
huggingface-cli download lj1995/GPT-SoVITS --local-dir ./GPT_SoVITS/pretrained_models

# v2Pro (better for noisy recordings)
# Files: v2Pro/s2Dv2Pro.pth, v2Pro/s2Gv2Pro.pth, sv/pretrained_eres2netv2w24s4ep4.ckpt
```

---

## Training Pipeline

Full pipeline: Audio prep → Slice → Denoise (optional) → ASR → Proofread → Train

### Step 1: Prepare audio

- Collect 1–5 minutes of clean single-speaker audio
- Recommended: 16kHz or 44.1kHz mono WAV
- Remove background music/noise (use UVR5 tool included in WebUI)
- Split into 3–10 second clips

### Step 2: Run WebUI for training

```bash
conda activate GPTSoVits
python webui.py
# Opens at http://localhost:9874
```

WebUI tabs:
1. **1A - Dataset Formatting** — slice audio into segments
2. **1B - Fine-tuning** — runs ASR + trains GPT + SoVITS models
3. **1C - Inference** — test the trained model

### Step 3: Command-line training (alternative)

```bash
# Slice audio into chunks
python tools/slice_audio.py \
  --input ./data/my_speaker/ \
  --output ./data/sliced/ \
  --min_length 3 \
  --max_length 10

# Run ASR to generate transcripts
python tools/asr/funasr_asr.py \
  --input_folder ./data/sliced/ \
  --output_folder ./data/asr_out/ \
  --language zh   # or 'en', 'ja' — use 'en' for Persian (Whisper fallback)

# Train SoVITS (acoustic model)
python GPT_SoVITS/s2_train.py \
  --config GPT_SoVITS/configs/s2.json \
  --train_list ./data/asr_out/train.list \
  --val_list ./data/asr_out/val.list \
  --save_path ./output/my_speaker_sovits/

# Train GPT (language model)
python GPT_SoVITS/s1_train.py \
  --config GPT_SoVITS/configs/s1longer.yaml \
  --train_list ./data/asr_out/train.list \
  --save_path ./output/my_speaker_gpt/
```

### Dataset .list format

```
path/to/audio.wav|speaker_name|language_code|transcript text
```

Language codes: `zh` (Chinese), `ja` (Japanese), `en` (English), `ko` (Korean), `yue` (Cantonese)

**Persian note:** GPT-SoVITS does not have a native `fa` language code. Use `en` as the language tag and provide romanized/phonetic transcription, OR use the WebUI's Whisper ASR which supports Persian auto-detection.

---

## Inference API (Local HTTP Server)

```bash
# Start the inference API server
python GPT_SoVITS/inference_webui.py
# Default port: 9880

# Or via webui at tab 1C
```

### HTTP API endpoints

```bash
# GET request (simple)
curl "http://localhost:9880/?text=Hello+world&text_lang=en&ref_audio_path=ref.wav&prompt_text=Reference+text&prompt_lang=en&media_type=wav" \
  --output output.wav

# POST request (recommended)
curl -X POST http://localhost:9880/ \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is synthesized speech.",
    "text_lang": "en",
    "ref_audio_path": "/path/to/reference.wav",
    "prompt_text": "What was said in the reference audio.",
    "prompt_lang": "en",
    "top_k": 5,
    "top_p": 1.0,
    "temperature": 1.0,
    "speed_factor": 1.0,
    "media_type": "wav",
    "streaming_mode": false
  }' --output result.wav
```

### Python client

```python
import requests

def synthesize(
    text: str,
    ref_audio: str,
    prompt_text: str,
    lang: str = "en",
    speed: float = 1.0,
    host: str = "http://localhost:9880",
) -> bytes:
    response = requests.post(host, json={
        "text": text,
        "text_lang": lang,
        "ref_audio_path": ref_audio,
        "prompt_text": prompt_text,
        "prompt_lang": lang,
        "speed_factor": speed,
        "media_type": "wav",
        "streaming_mode": False,
    })
    response.raise_for_status()
    return response.content

# Usage
audio_bytes = synthesize(
    text="Hello, this is the cloned voice.",
    ref_audio="/path/to/speaker_ref.wav",
    prompt_text="This is what the speaker said in the reference.",
)
with open("output.wav", "wb") as f:
    f.write(audio_bytes)
```

### Streaming mode

```python
import requests

with requests.post("http://localhost:9880/", json={
    "text": "Long text to be streamed...",
    "text_lang": "en",
    "ref_audio_path": "ref.wav",
    "prompt_text": "Reference transcript.",
    "prompt_lang": "en",
    "streaming_mode": True,
    "media_type": "wav",
}, stream=True) as resp:
    with open("streamed.wav", "wb") as f:
        for chunk in resp.iter_content(chunk_size=4096):
            f.write(chunk)
```

---

## Batch Inference

```python
import requests
from pathlib import Path

texts = [
    "First sentence.",
    "Deuxième phrase en français.",
    "سومین جمله به فارسی.",   # Persian — use lang="en" or Whisper fallback
]

ref_audio = "/path/to/ref_speaker.wav"
ref_text = "The transcript of the reference audio."

for i, text in enumerate(texts):
    audio = requests.post("http://localhost:9880/", json={
        "text": text,
        "text_lang": "en",
        "ref_audio_path": ref_audio,
        "prompt_text": ref_text,
        "prompt_lang": "en",
        "media_type": "wav",
    }).content
    Path(f"batch_{i:03d}.wav").write_bytes(audio)
```

---

## Google Colab Setup

```python
# In Colab notebook:
!git clone https://github.com/RVC-Boss/GPT-SoVITS
%cd GPT-SoVITS

# Install
!pip install -r requirements.txt

# Download pretrained models
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="lj1995/GPT-SoVITS",
    local_dir="GPT_SoVITS/pretrained_models",
)

# Launch WebUI with public URL
import subprocess, threading
def run():
    subprocess.run(["python", "webui.py"])
t = threading.Thread(target=run); t.start()

# Or use the official Colab notebook:
# https://colab.research.google.com/github/RVC-Boss/GPT-SoVITS/blob/main/Colab-WebUI.ipynb
```

---

## Persian Voice Training Notes

GPT-SoVITS does not natively support Persian (`fa`) as a language code. Workarounds:

1. **Whisper ASR path (recommended):** Use the WebUI with English/Japanese Whisper ASR (Faster Whisper Large V3). Whisper detects Persian automatically and produces accurate transcripts. Set language tag to `en` in .list files when ASR output is Latin-romanized, or leave as-is and use `zh` (closest multi-script handling).

2. **Manual transcript:** Provide Persian Unicode text directly in the .list file. Use `en` as the language code — SoVITS handles the phonetics via the audio signal, not text parsing.

3. **Data requirements for Persian:**
   - Minimum: 1 minute clean Persian speech
   - Recommended: 3–5 minutes for stable timbre reproduction
   - Avoid mixing Persian and other languages in a single training set

4. **GPU:** Fine-tuning on Apple Silicon MPS is not supported — training uses CPU, which is very slow. Use Colab (free T4) for fine-tuning Persian voices.

---

## UVR5 Audio Cleaning (Pre-processing)

Before training, use the bundled UVR5 tool to separate vocals from background:

```bash
python tools/uvr5/webui.py cuda 0 9873
# Opens at http://localhost:9873
```

Or via WebUI tab 0 (preprocessing).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Low quality on Mac | Training uses CPU on MPS — use Colab instead |
| Metallic voice artifacts | Switch from v3 to v4 |
| Poor quality on noisy audio | Use v2Pro instead of v4 |
| OOM during training | Reduce batch size; use v2 instead of v3/v4 |
| Persian ASR fails | Use Faster Whisper Large V3 with auto language detection |
| Repetitions/omissions | Use v2Pro or v3 GPT model (more stable than v1/v2) |
