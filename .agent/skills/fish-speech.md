---
title: "Fish Speech 1.5 — Multilingual Zero-Shot TTS"
description: High-quality multilingual TTS with voice cloning in seconds — Fish Speech 1.5 installation, inference, fine-tuning
location: .agent/skills/fish-speech.md
agent_priority: Standard
last_updated: 2026-05-30
---

# Fish Speech 1.5 — Multilingual Zero-Shot TTS

Fish Speech (now at S2 / S2 Pro) is a state-of-the-art open-source TTS system with zero-shot voice cloning. Trained on 10M+ hours of audio across 80+ languages. Architecture: Dual-Autoregressive (slow 4B + fast 400M).

- GitHub: https://github.com/fishaudio/fish-speech (30k+ stars)
- Docs: https://speech.fish.audio/
- Model: https://huggingface.co/fishaudio/s2-pro

---

## Installation

### pip (standard)

```bash
pip install fish-speech
```

### Apple Silicon (MPS)

```bash
# Requires Python 3.10+, PyTorch ≥ 2.5.1 with MPS support
pip install fish-speech

# Verify MPS availability
python -c "import torch; print(torch.backends.mps.is_available())"
```

### From source

```bash
git clone https://github.com/fishaudio/fish-speech
cd fish-speech
pip install -e .
```

### Docker

```bash
docker pull fishaudio/fish-speech:latest
docker run -it --gpus all -p 7860:7860 fishaudio/fish-speech:latest
```

---

## Model Download

```bash
# HuggingFace (recommended outside China)
huggingface-cli download fishaudio/fish-speech-1.5 --local-dir ./checkpoints/fish-speech-1.5

# Or S2 Pro (latest)
huggingface-cli download fishaudio/s2-pro --local-dir ./checkpoints/s2-pro
```

---

## CLI Inference

```bash
# Basic synthesis
fish_speech infer \
  --text "Hello, this is a test." \
  --output output.wav

# With reference audio (zero-shot voice cloning)
fish_speech infer \
  --text "مرحبا، این یک آزمایش است." \
  --reference-audio ref_voice.wav \
  --reference-text "This is the reference transcript." \
  --output output_cloned.wav

# Specify checkpoint
fish_speech infer \
  --checkpoint ./checkpoints/fish-speech-1.5 \
  --text "Bonjour le monde" \
  --output fr_output.wav

# With emotion tags (S2 Pro)
fish_speech infer \
  --text "[excited] Welcome to the future of TTS! [pause] Incredible, right?" \
  --output emotional.wav
```

---

## Python API

```python
from fish_speech.inference import TTSInferencer

# Initialize (loads model once)
tts = TTSInferencer(
    checkpoint="./checkpoints/fish-speech-1.5",
    device="mps",          # "cuda" / "cpu" / "mps"
    compile=False,         # set True for GPU speed boost
)

# Simple synthesis
audio = tts.infer(text="Hello world")
tts.save(audio, "output.wav")

# Zero-shot voice cloning
audio = tts.infer(
    text="The cloned voice says this.",
    reference_audio="my_voice_10s.wav",
    reference_text="This is what I said in the reference clip.",
)
tts.save(audio, "cloned.wav")
```

---

## Voice Cloning with Reference Audio

Zero-shot cloning: provide 10–30 seconds of clean reference audio — no fine-tuning needed.

```python
from fish_speech.inference import TTSInferencer
import soundfile as sf

tts = TTSInferencer(checkpoint="./checkpoints/fish-speech-1.5", device="cuda")

audio = tts.infer(
    text="این جمله با صدای کلون‌شده گفته می‌شود.",   # Persian
    reference_audio="persian_speaker_30s.wav",
    reference_text="متن دقیق آنچه در فایل مرجع گفته شده.",
    top_p=0.7,
    temperature=0.7,
    repetition_penalty=1.3,
)
sf.write("persian_cloned.wav", audio, samplerate=44100)
```

**Tips for best cloning quality:**
- Use 10–30 seconds of clean, single-speaker audio
- Provide accurate `reference_text` (improves similarity)
- Avoid background music/noise in reference
- Consistent microphone and room across reference clips

---

## Supported Languages

Fish Speech supports 80+ languages. Key languages for this project:

| Language | Code | Quality |
|---|---|---|
| Persian / Farsi | `fa` | Tier 2 |
| French | `fr` | Tier 2 |
| English | `en` | Tier 1 |
| Arabic | `ar` | Tier 2 |
| Chinese | `zh` | Tier 1 |
| Japanese | `ja` | Tier 1 |

No language-specific preprocessing or phoneme dictionaries required — the model handles all languages natively.

---

## Emotion / Prosody Control (S2 Pro)

Inline `[tag]` syntax for fine-grained control:

```python
text = "[excited] این خبر فوق‌العاده است! [pause] بگذارید توضیح دهم. [whisper] در واقع..."
text = "[professional broadcast tone] Bienvenue sur notre chaîne. [pause] Aujourd'hui..."
text = "[sad] I can't believe it's over. [sigh] Everything must end eventually."
```

Supported tags include: `[pause]` `[emphasis]` `[laughing]` `[whisper]` `[excited]` `[angry]` `[sad]` `[sigh]` `[chuckle]` `[shouting]` `[low voice]` `[volume up/down]` — and thousands more free-form descriptions.

---

## Streaming Output

```python
from fish_speech.inference import TTSInferencer

tts = TTSInferencer(checkpoint="./checkpoints/fish-speech-1.5", device="cuda")

# Stream audio chunks as they are generated
for chunk in tts.infer_stream(
    text="This is a longer text that will be streamed chunk by chunk.",
    chunk_length=200,       # characters per chunk
):
    # chunk is a numpy array — play or write incrementally
    play_audio(chunk)       # your playback function
```

**Streaming performance (H200 single GPU):**
- TTFA (Time-to-First-Audio): ~100ms
- RTF: 0.195
- Throughput: 3000+ acoustic tokens/s

---

## Batch Generation

```python
from fish_speech.inference import TTSInferencer
from pathlib import Path

tts = TTSInferencer(checkpoint="./checkpoints/fish-speech-1.5", device="cuda")

texts = [
    "First sentence to synthesize.",
    "Deuxième phrase en français.",
    "سومین جمله به فارسی.",
]

for i, text in enumerate(texts):
    audio = tts.infer(text=text)
    tts.save(audio, f"output_{i:03d}.wav")
```

---

## Fine-Tuning on Custom Voice

Fine-tuning improves consistency for production use beyond zero-shot cloning.

**Minimum data:** 1–5 minutes clean audio, single speaker, with accurate transcripts.

```bash
# 1. Prepare dataset (wav files + transcript .list file)
# Format: path/to/audio.wav|speaker_name|language|transcript text
# Example: data/amir_001.wav|amir|fa|این یک جمله آزمایشی است.

# 2. Fine-tune
fish_speech train \
  --data-dir ./data/my_voice \
  --output-dir ./checkpoints/my_voice_ft \
  --base-checkpoint ./checkpoints/fish-speech-1.5 \
  --epochs 10 \
  --batch-size 4

# 3. Infer with fine-tuned model
fish_speech infer \
  --checkpoint ./checkpoints/my_voice_ft \
  --text "Hello with my fine-tuned voice." \
  --output ft_output.wav
```

**Hardware requirements:**
- Zero-shot cloning: 4GB VRAM (MPS supported)
- Fine-tuning: 8GB+ VRAM recommended (16GB for comfortable training)
- Apple Silicon: MPS supported for inference; fine-tuning uses CPU (slower but works)

---

## HTTP Inference Server

```bash
# Start server
fish_speech server --checkpoint ./checkpoints/fish-speech-1.5 --port 8080

# Query via curl
curl -X POST http://localhost:8080/v1/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello from the API server.",
    "reference_audio": "base64_encoded_wav_here",
    "reference_text": "Reference transcript.",
    "format": "wav"
  }' --output result.wav
```

---

## WebUI

```bash
fish_speech webui --checkpoint ./checkpoints/fish-speech-1.5
# Opens at http://localhost:7860
```

---

## Notes for Persian (Farsi) Use

- Fish Speech handles Persian script natively — no transliteration needed
- Use UTF-8 encoded text; right-to-left is handled internally
- For best results, provide a Persian-language reference audio clip
- Mix Persian+French or Persian+English is supported in one synthesis call
- Emotion tags work in Persian text contexts
