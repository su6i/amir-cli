---
title: "Open-Source TTS — Multilingual Voice Synthesis"
description: Free alternatives to ElevenLabs — edge-tts, F5-TTS, GPT-SoVITS, OpenVoice, Piper for Persian, English, French
location: .agent/skills/opensource-tts.md
agent_priority: Standard
last_updated: 2026-05-30
---

# Open-Source TTS — Multilingual Voice Synthesis

## Quick Decision Table

| Tool | Persian (fa) | French (fr) | English (en) | Quality | Speed | Setup | Best For |
|------|:---:|:---:|:---:|---------|-------|-------|----------|
| **edge-tts** | fa-IR (4 voices) | fr-FR/fr-CA | Yes | Good | Instant | Trivial | Quick narration, no GPU |
| **F5-TTS** | Via cloning | Via cloning | Native | Excellent | Fast (GPU) | Moderate | Zero-shot voice cloning |
| **GPT-SoVITS** | Via training | Via training | Native | Best | Medium | Complex | Fine-tuned voice, 1 min sample |
| **OpenVoice V2** | Cross-lingual | Native | Native | Very good | Fast | Moderate | Multi-lingual from one reference |
| **Piper** | No | Yes (fr_FR) | Yes | Good | Very fast | Easy | Offline, embedded systems |

**Decision guide:**
- Need Persian voice fast with no GPU → `edge-tts` with `fa-IR-DilaraNeural`
- Need to clone a specific person's voice → `F5-TTS` (zero-shot, 5s ref) or `GPT-SoVITS` (1 min training)
- Need French narration, offline → `Piper` (fr_FR-siwis-medium)
- Need same voice across EN/FR/ZH from one sample → `OpenVoice V2`

---

## 1. edge-tts

Microsoft Edge TTS via Python — no GPU, needs internet.

### Install

```bash
pip install edge-tts
# or isolated:
pipx install edge-tts
```

### List voices (fa-IR, fr-FR, en-US)

```bash
edge-tts --list-voices | grep -E "^(fa-IR|fr-FR|en-US)"
# Key voices:
# fa-IR-DilaraNeural   Female  Persian
# fa-IR-FaridNeural    Male    Persian
# fr-FR-DeniseNeural   Female  French (best quality)
# fr-FR-HenriNeural    Male    French
# en-US-AriaNeural     Female  English
```

### CLI generate

```bash
edge-tts --voice fa-IR-DilaraNeural \
  --text "سلام، این یک آزمایش است." \
  --write-media out.mp3 \
  --write-subtitles out.srt

# With rate/pitch adjustment (note: negative values need = syntax)
edge-tts --voice fr-FR-DeniseNeural \
  --rate=-10% --pitch=-5Hz \
  --text "Bonjour le monde." \
  --write-media fr_out.mp3
```

### Python API (async)

```python
import asyncio
import edge_tts

async def synthesize(text: str, voice: str, output: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output)

# Single file
asyncio.run(synthesize("سلام دنیا", "fa-IR-DilaraNeural", "output.mp3"))

# With subtitles
async def synthesize_with_subs(text: str, voice: str, mp3_out: str, srt_out: str):
    communicate = edge_tts.Communicate(text, voice)
    submaker = edge_tts.SubMaker()
    with open(mp3_out, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
    with open(srt_out, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())
```

---

## 2. F5-TTS

Zero-shot voice cloning with flow matching. Requires GPU (MPS on Apple Silicon works).

### Install

```bash
# Inference only:
pip install f5-tts

# Apple Silicon — install PyTorch first:
pip install torch torchaudio
pip install f5-tts
```

### CLI — zero-shot cloning

```bash
# ref_audio: 3–12s WAV of the target voice
# ref_text: exact transcript of ref_audio
# gen_text: what you want synthesized
f5-tts_infer-cli \
  --model F5TTS_v1_Base \
  --ref_audio reference_voice.wav \
  --ref_text "The quick brown fox jumps over the lazy dog." \
  --gen_text "Hello, this is a cloned voice speaking new text." \
  --output_file output.wav

# Leave --ref_text "" to auto-transcribe (uses Whisper, extra VRAM)
f5-tts_infer-cli \
  --model F5TTS_v1_Base \
  --ref_audio reference_voice.wav \
  --ref_text "" \
  --gen_text "Text to synthesize."
```

### Python API

```python
from f5_tts.api import F5TTS

tts = F5TTS()  # downloads F5TTS_v1_Base automatically

wav, sr, _ = tts.infer(
    ref_file="reference_voice.wav",
    ref_text="Transcript of the reference audio.",
    gen_text="Text you want the cloned voice to speak.",
    file_wave="output.wav",   # optional: save to file
)
# wav is a numpy array, sr = sample rate (24000)

# For Persian cloning — use a fa-IR speaker as ref_audio:
wav, sr, _ = tts.infer(
    ref_file="persian_speaker_sample.wav",
    ref_text="متن نمونه صدای مرجع",
    gen_text="این متن با صدای کلون شده خوانده می‌شود",
)
```

**Notes:** ref audio must be under 12s; model is CC-BY-NC; pre-trained EN+ZH — use cloning for other languages.
Gradio UI: `f5-tts_infer-gradio` — Fine-tune UI: `f5-tts_finetune-gradio`

---

## 3. GPT-SoVITS

Few-shot TTS: 5s zero-shot or 1-min fine-tune for high voice similarity.
Officially supports: EN, ZH, JA, KO, Cantonese.

### Install (macOS/Linux)

```bash
conda create -n GPTSoVits python=3.10
conda activate GPTSoVits
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS
# macOS (MPS or CPU):
bash install.sh --device MPS --source HF
# Linux CUDA:
bash install.sh --device CU128 --source HF
```

### 1-minute voice training workflow

```bash
# 1. Launch WebUI
python webui.py

# In the WebUI (http://localhost:9874):
# Tab: "1. ASR & Label" → upload audio → slice → denoise → ASR → proofread
# Tab: "2. Fine-tune" → select sliced dataset → train GPT + SoVITS models
# Tab: "3. Inference" → load trained models → generate
```

### Inference API (Python — via local HTTP server)

```python
import requests

# Start server first: python GPT_SoVITS/inference_webui.py
resp = requests.post("http://localhost:9880/tts", json={
    "text": "Hello, synthesized speech.",
    "text_lang": "en",
    "ref_audio_path": "reference.wav",
    "prompt_text": "Reference audio transcript",
    "prompt_lang": "en",
})
with open("output.wav", "wb") as f:
    f.write(resp.content)  # response is audio/wav
```

---

## 4. OpenVoice

Tone color cloning + cross-lingual synthesis. V2 natively supports EN, ES, FR, ZH, JA, KO.

### Install (V2)

```bash
conda create -n openvoice python=3.9 && conda activate openvoice
git clone https://github.com/myshell-ai/OpenVoice.git && cd OpenVoice
pip install -e .
pip install git+https://github.com/myshell-ai/MeloTTS.git
python -m unidic download
# Checkpoints: https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip → checkpoints_v2/
```

### Python API — tone color cloning

```python
import torch
from openvoice import se_extractor
from openvoice.api import ToneColorConverter

device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
ckpt_dir = "checkpoints_v2"

# Load converter
converter = ToneColorConverter(f"{ckpt_dir}/converter/config.json", device=device)
converter.load_ckpt(f"{ckpt_dir}/converter/checkpoint.pth")

# Extract tone color from reference audio (any language)
target_se, _ = se_extractor.get_se(
    "reference_voice.wav",
    converter,
    vad=True
)

# Generate base TTS with MeloTTS (V2)
from melo.api import TTS

# Supported speed param: EN, FR, ES, ZH, JP, KR
tts_model = TTS(language="EN", device=device)
speaker_ids = tts_model.hps.data.spk2id
src_path = "base_tts.wav"
tts_model.tts_to_file(
    "Text to synthesize in English.",
    speaker_ids["EN-Default"],
    src_path,
    speed=1.0
)

# Apply tone color cloning
source_se = torch.load(f"{ckpt_dir}/base_speakers/ses/en-default.pth", map_location=device)
converter.convert(
    audio_src_path=src_path,
    src_se=source_se,
    tgt_se=target_se,
    output_path="cloned_output.wav",
    message="@MyShell"
)
```

**Cross-lingual:** generate base audio with `TTS(language="FR")`, apply same `target_se` extracted from any reference voice.

---

## 5. Piper

Fast offline neural TTS — no internet, no GPU required. Used in Home Assistant.

### Install

```bash
pip install piper-tts
python3 -m piper.download_voices fr_FR-siwis-medium   # → ~/.local/share/piper/voices/
```

### CLI

```bash
echo "Bonjour le monde" | piper \
  --model fr_FR-siwis-medium \
  --output_file out.wav

# List available voices: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md
```

### Python API

```python
import wave
from piper import PiperVoice
from piper.download import ensure_voice_exists, find_voice, get_voices

# Load voice (model must be downloaded first)
voice_path = "/path/to/fr_FR-siwis-medium.onnx"
voice = PiperVoice.load(voice_path)  # add use_cuda=True for GPU

with wave.open("output.wav", "wb") as wav_file:
    voice.synthesize_wav("Bonjour le monde.", wav_file)

# Streaming synthesis
for chunk in voice.synthesize("Long text here..."):
    # chunk.audio_int16_bytes, chunk.sample_rate, chunk.sample_width
    process_audio_chunk(chunk)

# Adjust synthesis parameters
from piper import SynthesisConfig
config = SynthesisConfig(
    length_scale=1.2,   # slower speech (>1 = slower)
    noise_scale=0.667,
    noise_w_scale=0.8,
)
voice.synthesize_wav("Text", wav_file, syn_config=config)
```

**French voices:** `fr_FR-siwis-medium` (best), `fr_FR-upmc-medium`. No Persian in Piper's official models.

---

## Persian TTS — Best Approaches

**Option 1: edge-tts (fastest, no GPU)**
```python
import asyncio, edge_tts

async def persian_tts(text: str, output: str = "output.mp3"):
    c = edge_tts.Communicate(text, "fa-IR-DilaraNeural")
    await c.save(output)

asyncio.run(persian_tts("سلام دنیا، این یک آزمایش است."))
```

**Option 2: F5-TTS cloning from fa-IR sample (GPU, best quality)**
```python
from f5_tts.api import F5TTS

tts = F5TTS()
# Use any native Persian speaker audio as reference
tts.infer(
    ref_file="native_persian_speaker.wav",   # 5–12s, clear speech
    ref_text="متن دقیق صدای مرجع",
    gen_text="هر متن فارسی که می‌خواهید تولید کنید",
    file_wave="persian_output.wav",
)
```

**Option 3: GPT-SoVITS with 1-min Persian recording** — highest similarity, requires training run.

---

## French TTS — Best Approaches

**edge-tts (no GPU, instant):**
```bash
edge-tts --voice fr-FR-DeniseNeural \
  --text "Bonjour, je suis votre assistant." \
  --write-media french.mp3
```

**Piper (offline, fast):**
```bash
pip install piper-tts
python3 -m piper.download_voices fr_FR-siwis-medium
echo "Bonjour le monde" | piper --model fr_FR-siwis-medium --output_file out.wav
```

**OpenVoice V2 (clone a specific French voice):**
- Generate base audio with `TTS(language="FR")`
- Apply `target_se` from any reference speaker
- Produces the target person's voice speaking French

---

## Batch Pipeline — Async Multi-file Generation

```python
import asyncio
from pathlib import Path
import edge_tts

async def generate_one(item: dict) -> str:
    """item: {text, voice, output}"""
    c = edge_tts.Communicate(item["text"], item["voice"])
    await c.save(item["output"])
    return item["output"]

async def batch_generate(items: list[dict], max_concurrent: int = 5) -> list[str]:
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded(item):
        async with semaphore:
            return await generate_one(item)

    return await asyncio.gather(*[bounded(i) for i in items])

# Usage:
items = [
    {"text": "سلام دنیا",         "voice": "fa-IR-DilaraNeural", "output": "fa_01.mp3"},
    {"text": "Bonjour le monde",  "voice": "fr-FR-DeniseNeural", "output": "fr_01.mp3"},
    {"text": "Hello world",       "voice": "en-US-AriaNeural",   "output": "en_01.mp3"},
]
results = asyncio.run(batch_generate(items))
print(results)  # ['fa_01.mp3', 'fr_01.mp3', 'en_01.mp3']
```

**For F5-TTS batch (GPU):**
```python
from f5_tts.api import F5TTS

tts = F5TTS()  # load once

texts = ["First sentence.", "Second sentence.", "Third sentence."]
for i, text in enumerate(texts):
    tts.infer(
        ref_file="reference.wav",
        ref_text="Reference transcript.",
        gen_text=text,
        file_wave=f"output_{i:03d}.wav",
    )
```
