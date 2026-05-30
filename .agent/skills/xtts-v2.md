---
title: "XTTS v2 — Multilingual Voice Cloning (Coqui)"
description: Production-grade multilingual TTS with 6-second voice cloning — XTTS v2 inference, streaming, fine-tuning
location: .agent/skills/xtts-v2.md
agent_priority: Standard
last_updated: 2026-05-30
---

# XTTS v2 — Multilingual Voice Cloning (Coqui)

XTTS v2 is Coqui's production TTS model. It supports 17 languages, clones any voice from a 6-second reference audio, and streams with under 200ms latency. License: MPL 2.0.

- Repo: https://github.com/coqui-ai/TTS
- Docs: https://tts.readthedocs.io/en/dev/models/xtts.html
- HuggingFace model: `coqui/XTTS-v2`

---

## Installation

```bash
# Requires Python >= 3.9, < 3.12
pip install TTS

# For training / fine-tuning (full install)
git clone https://github.com/coqui-ai/TTS
pip install -e ".[all,dev,notebooks]"

# System dependency for some phonemizers
sudo apt-get install espeak-ng   # Linux
brew install espeak               # macOS
```

---

## Supported Languages

17 languages in v2: English (`en`), Spanish (`es`), French (`fr`), German (`de`), Italian (`it`), Portuguese (`pt`), Polish (`pl`), Turkish (`tr`), Russian (`ru`), Dutch (`nl`), Czech (`cs`), Arabic (`ar`), Chinese (`zh-cn`), Japanese (`ja`), Hungarian (`hu`), Korean (`ko`), Hindi (`hi`).

**Persian (Farsi) is NOT natively supported by XTTS v2.** For Persian, use VITS fine-tuned on Persian data (see `persian-tts-training.md`) or MMS-TTS (see `huggingface-tts.md`).

---

## Quick Inference — Python API

```python
import torch
from TTS.api import TTS

device = "cuda" if torch.cuda.is_available() else "cpu"

# List all available models
print(TTS().list_models())

# Load XTTS v2
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# Voice cloning — needs a 6-24s WAV reference (16kHz, mono recommended)
tts.tts_to_file(
    text="Hello, this is a cloned voice speaking.",
    speaker_wav="reference.wav",
    language="en",
    file_path="output.wav"
)
```

---

## Quick Inference — CLI

```bash
# List models
tts --list_models

# Basic synthesis (XTTS v2 voice cloning)
tts --text "Bonjour, comment ça va ?" \
    --model_name "tts_models/multilingual/multi-dataset/xtts_v2" \
    --speaker_wav reference.wav \
    --language_idx fr \
    --out_path output.wav

# Multi-speaker model (no voice cloning)
tts --text "Hello world" \
    --model_name "tts_models/en/vctk/vits" \
    --speaker_idx "p230" \
    --out_path output.wav
```

---

## Voice Cloning — Best Practices

```python
# Reference audio requirements:
# - Duration: 6–24 seconds (6s minimum, 24s optimal)
# - Format: WAV, 22050 Hz or 16000 Hz, mono
# - Content: clear speech, minimal background noise, no music
# - Same language as target synthesis helps quality

# Multiple reference clips (averages embeddings — better quality)
tts.tts_to_file(
    text="Cloning from multiple references.",
    speaker_wav=["ref1.wav", "ref2.wav", "ref3.wav"],
    language="en",
    file_path="output.wav"
)
```

---

## Streaming (< 200ms latency)

```python
from TTS.api import TTS

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

# Stream to speakers in real-time
tts.tts_with_vc_to_file(...)  # file-based

# Direct streaming via xtts model
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

config = XttsConfig()
config.load_json("/path/to/xtts_v2/config.json")
model = Xtts.init_from_config(config)
model.load_checkpoint(config, checkpoint_dir="/path/to/xtts_v2/")
model.cuda()

# Get speaker embedding from reference
gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
    audio_path=["reference.wav"]
)

# Stream chunks
chunks = model.inference_stream(
    "Text to stream goes here.",
    "en",
    gpt_cond_latent,
    speaker_embedding,
)

import wave, numpy as np
with wave.open("streamed_output.wav", "w") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(24000)
    for chunk in chunks:
        wf.writeframes((chunk.squeeze().cpu().numpy() * 32767).astype(np.int16).tobytes())
```

---

## Batch Generation

```python
# Process list of texts efficiently
texts = ["First sentence.", "Second sentence.", "Third sentence."]

for i, text in enumerate(texts):
    tts.tts_to_file(
        text=text,
        speaker_wav="reference.wav",
        language="en",
        file_path=f"batch_output_{i:03d}.wav"
    )

# Then join with FFmpeg:
# ffmpeg -f concat -safe 0 -i filelist.txt -c copy joined.wav
```

---

## Fine-Tuning on Custom Dataset

```bash
# Recipe directory: recipes/ljspeech/ in the TTS repo
# Dataset format: LJSpeech-compatible
# metadata.csv  →  filename|transcription

# Fine-tune XTTS v2
python TTS/bin/train_tts.py \
    --config_path recipes/ljspeech/xtts_v2/train_xtts.py \
    --coqpit-overrides \
        output_path=./output \
        datasets.0.path=./dataset \
        datasets.0.meta_file_train=metadata.csv

# Minimum dataset size for acceptable quality:
# - ~1 hour of clean speech = decent clone
# - ~10 hours = high quality custom voice
# - ~30 hours = near-perfect reproduction
```

---

## GPU vs CPU

| Hardware | Speed | Notes |
|---|---|---|
| NVIDIA GPU (CUDA) | ~30× realtime | Recommended for production |
| Apple Silicon (MPS) | ~5–8× realtime | Supported via PyTorch MPS |
| CPU only | ~0.5–1× realtime | Usable for short texts |

```python
# Force CPU (useful for testing)
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")

# Apple Silicon
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("mps")
```

---

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `espeak not found` | Missing system dep | `brew install espeak` / `apt install espeak-ng` |
| `RuntimeError: CUDA out of memory` | GPU VRAM < 4GB | Use CPU or reduce batch size |
| `ValueError: Speaker wav is too short` | Reference < 3s | Use a longer reference clip |
| Robotic / distorted output | Reference has noise/music | Clean reference audio first |
| Wrong language pronunciation | Language mismatch | Set `language` param to match reference language |
| `ModuleNotFoundError: TTS` | Not installed | `pip install TTS` |

---

## Docker (No Install)

```bash
docker run --rm -it -p 5002:5002 --entrypoint /bin/bash ghcr.io/coqui-ai/tts-cpu
python3 TTS/server/server.py --list_models
python3 TTS/server/server.py --model_name tts_models/multilingual/multi-dataset/xtts_v2
# Web UI: http://localhost:5002
```

---

## Related Skills

- `persian-tts-training.md` — Persian-specific TTS: VITS fine-tune, Coqui on Persian datasets
- `huggingface-tts.md` — Parler-TTS, MMS (includes Persian), SpeechT5
- `voice-synthesis-multilingual.md` — broader multilingual pipeline patterns
