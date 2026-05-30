---
title: "Persian TTS — Training and Fine-Tuning Guide"
description: Best approach for commercial-quality Persian (Farsi) TTS — ManaTTS, XTTS fine-tune, GPT-SoVITS on Persian, Google Colab setup
location: .agent/skills/persian-tts-training.md
agent_priority: Standard
last_updated: 2026-05-30
---

# Persian TTS — Training and Fine-Tuning Guide

Practical guide for producing commercial-quality Persian (Farsi) TTS, from zero-effort pretrained models to full fine-tuning on a custom voice.

---

## Available Persian TTS Models — Ranked by Quality

| Rank | Model | Type | Quality | Notes |
|---|---|---|---|---|
| 1 | XTTS v2 fine-tuned on Persian | Voice cloning | High | Needs 1–10h Persian audio |
| 2 | GPT-SoVITS (Persian audio) | Few-shot clone | High | Works with ~1 min reference |
| 3 | karim23657/Persian-tts-coqui VITS | Pretrained | Good | Best open-source baseline |
| 4 | MMS-TTS (`facebook/mms-tts-fas`) | Pretrained | Acceptable | Instant use, no training needed |
| 5 | SpeechT5 (not Persian-native) | — | Poor | Not recommended for Persian |

**Quick start:** If you just need Persian TTS now with no training → use MMS-TTS (`facebook/mms-tts-fas`). If you need a specific voice → GPT-SoVITS.

---

## Option 1: MMS-TTS — Zero Setup, Instant Persian (Baseline)

```python
from transformers import pipeline
import soundfile as sf

tts = pipeline("text-to-speech", model="facebook/mms-tts-fas")
result = tts("سلام، خوش آمدید به دنیای متن به گفتار.")
sf.write("output.wav", result["audio"].squeeze(), result["sampling_rate"])
```

Pros: No training, runs on CPU, MIT-like license.
Cons: Robotic quality, no voice control, single speaker.

---

## Option 2: GPT-SoVITS — Few-Shot Voice Cloning (Best Quality/Effort Ratio)

GPT-SoVITS can clone a voice from ~1 minute of audio. Works well with Persian.
- Repo: https://github.com/RVC-Boss/GPT-SoVITS (58k+ stars)
- Stars indicate wide community support and active maintenance

### Setup (Google Colab / Linux)

```bash
git clone https://github.com/RVC-Boss/GPT-SoVITS
cd GPT-SoVITS
pip install -r requirements.txt
```

### Persian Voice Cloning Workflow

```
1. Prepare reference audio:
   - 1–5 minutes of clean Persian speech (WAV, 44100 Hz mono)
   - Same speaker you want to clone
   - No music, no background noise

2. Run training (SoVITS):
   python webui.py
   → Upload reference audio
   → Slice → Transcribe (use Whisper for Persian)
   → Train SoVITS model (15–30 min on T4 GPU)
   → Train GPT model (30–60 min on T4 GPU)

3. Inference:
   → Select trained model
   → Input Persian text
   → Export WAV
```

### Transcription of Persian Audio (for GPT-SoVITS dataset)

```bash
# Use faster-whisper or mlx-whisper for Persian transcription
pip install faster-whisper

python - <<'EOF'
from faster_whisper import WhisperModel
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, _ = model.transcribe("persian_audio.wav", language="fa")
with open("transcription.txt", "w", encoding="utf-8") as f:
    for seg in segments:
        f.write(f"{seg.start:.3f}\t{seg.end:.3f}\t{seg.text.strip()}\n")
EOF
```

---

## Option 3: XTTS v2 Fine-Tuned on Persian

XTTS v2 natively supports 17 languages (Persian is NOT included), but fine-tuning on Persian data achieves excellent quality.

### Dataset Preparation

```
Required format (LJSpeech-style):
dataset/
  wavs/
    001.wav
    002.wav
    ...
  metadata.csv   ← filename|transcription (no extension in filename)

metadata.csv example:
001|سلام این یک جمله آزمایشی است
002|امروز هوا بسیار خوب است
```

### Persian Datasets Available

| Dataset | Size | Source |
|---|---|---|
| persian-tts-dataset-female | ~5h | Kaggle: magnoliasis |
| persian-tts-dataset-male | ~5h | Kaggle: magnoliasis |
| persian-tts-dataset-male1 | ~5h | Kaggle: magnoliasis |
| ParsiGoo | ~2h | github.com/karim23657/ParsiGoo |
| Common Voice Persian (Mozilla) | ~50h (varied quality) | commonvoice.mozilla.org |
| GPTInformal-Persian | Informal speech | HuggingFace: MahtaFetrat |

### XTTS v2 Fine-Tuning

```bash
git clone https://github.com/coqui-ai/TTS
pip install -e ".[all,dev]"

# Fine-tune (recipe base — adapt config for Persian)
python TTS/bin/train_tts.py \
  --config_path recipes/ljspeech/xtts_v2/train_xtts.py \
  --coqpit-overrides \
    output_path=./output/persian_xtts \
    datasets.0.path=./dataset \
    datasets.0.meta_file_train=metadata.csv \
    datasets.0.language=fa
```

### Inference with Fine-Tuned XTTS

```python
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

config = XttsConfig()
config.load_json("./output/persian_xtts/config.json")
model = Xtts.init_from_config(config)
model.load_checkpoint(config, checkpoint_dir="./output/persian_xtts/")
model.cuda()

gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
    audio_path=["persian_reference.wav"]
)
out = model.inference(
    "سلام، این یک آزمایش صوتی است.",
    "fa",
    gpt_cond_latent,
    speaker_embedding,
)
import soundfile as sf
sf.write("output_fa.wav", out["wav"], 24000)
```

---

## Option 4: Coqui VITS Fine-Tuned on Persian (Lightest Option)

Pre-trained Persian VITS models from karim23657 (203 stars — most-starred Persian TTS repo):
- Repo: https://github.com/karim23657/Persian-tts-coqui
- Models on HuggingFace: `Kamtera/persian-tts-female-vits`, `Kamtera/persian-tts-male1-vits`

### Use Pretrained Model Directly

```bash
pip install TTS espeak-ng

tts --text "شیش سیخ جیگر" \
    --model_path "https://huggingface.co/Kamtera/persian-tts-male1-vits/resolve/main/checkpoint_88000.pth" \
    --config_path "https://huggingface.co/Kamtera/persian-tts-male1-vits/resolve/main/config.json" \
    --out_path output.wav
```

```python
from TTS.api import TTS

tts = TTS(
    model_path="https://huggingface.co/Kamtera/persian-tts-male1-vits/resolve/main/checkpoint_88000.pth",
    config_path="https://huggingface.co/Kamtera/persian-tts-male1-vits/resolve/main/config.json"
)
tts.tts_to_file("زندگی فقط یک بار است؛ از آن به خوبی استفاده کن", file_path="output.wav")
```

### Fine-Tune VITS on Custom Persian Voice

```
Minimum audio: 1 hour clean speech → acceptable
Optimal audio: 5–10 hours → high quality
Training time (T4 GPU): ~4–8 hours for 100k steps
```

---

## Google Colab GPU Setup

```python
# Cell 1: Check GPU
!nvidia-smi
# Free Colab: T4 (16GB VRAM) — sufficient for VITS and GPT-SoVITS
# Colab Pro: A100 (40GB) — for XTTS v2 fine-tuning

# Cell 2: Mount Drive for persistent storage
from google.colab import drive
drive.mount('/content/drive')

# Cell 3: Install TTS
!pip install TTS
!apt-get install -y espeak-ng

# Cell 4: Upload dataset to Drive and symlink
import os
os.makedirs("/content/dataset/wavs", exist_ok=True)
# Copy from Drive:
!cp -r /content/drive/MyDrive/persian_tts_dataset/* /content/dataset/

# Cell 5: Train
!python TTS/bin/train_tts.py --config_path config.json
```

**Colab gotcha:** Free Colab disconnects after 90 min idle. Use checkpointing every 10k steps and save to Drive.

---

## GPU Rental Options

| Provider | Price/hr (A100) | Price/hr (H100) | Notes |
|---|---|---|---|
| **vast.ai** | ~$1.5–2.5 | ~$3–5 | Cheapest, peer-to-peer, spot available |
| **RunPod** | ~$2–3 | ~$3.5–5 | Reliable, persistent storage |
| **Lambda Labs** | ~$2.5–3.5 | ~$4–6 | Clean UX, on-demand |
| **Google Colab Pro** | ~$10/mo flat | — | Easiest setup, limited hours |
| **Paperspace** | ~$2.5–4 | ~$5 | Good GPU selection |

**Recommended for training:**
- Short fine-tune (VITS, ~5h): vast.ai spot A100 = ~$7–12 total
- XTTS v2 full fine-tune (~24h): RunPod A100 = ~$50–75 total
- GPT-SoVITS (1–2h): Colab T4 free tier sufficient

---

## Minimum Audio Requirements

| Model | Minimum | Quality | Optimal |
|---|---|---|---|
| GPT-SoVITS | 1 min | Acceptable | 5–10 min |
| XTTS v2 fine-tune | 1 hour | Good | 10 hours |
| VITS fine-tune | 1 hour | Good | 5 hours |
| MMS-TTS (no training) | 0 | Pre-trained | — |

**Audio quality checklist:**
- Sample rate: 22050 Hz or 44100 Hz
- Format: WAV (PCM 16-bit)
- Noise: < -40 dB background noise
- Clipping: none (keep peaks below -3 dBFS)
- Silence: trim leading/trailing silence to < 0.2s
- Consistent recording environment across all clips

---

## Expected Training Times

| Model | Dataset | GPU | Time |
|---|---|---|---|
| GPT-SoVITS (SoVITS stage) | 5 min audio | T4 16GB | 15–30 min |
| GPT-SoVITS (GPT stage) | 5 min audio | T4 16GB | 30–60 min |
| VITS (100k steps) | 5h audio | T4 16GB | 6–8 hours |
| XTTS v2 fine-tune | 10h audio | A100 40GB | 12–24 hours |

---

## Persian Text Preprocessing

Persian text needs normalization before TTS inference:

```python
# Install: pip install hazm
from hazm import Normalizer

normalizer = Normalizer()
text = normalizer.normalize("این یک متن آزمایشی است!")
# Fixes: half-space, punctuation, Arabic vs Persian chars (ک vs ك, ی vs ي)

# Also useful: parsivar
# pip install parsivar
from parsivar import Normalizer as PNorm
pnorm = PNorm()
text = pnorm.sub_alphabets("این متن را نرمال کن")
```

Common Persian TTS issues:
- Arabic `ي` vs Persian `ی` → causes mispronunciation; normalize first
- Numbers: spell out or use `num2words` with `lang='fa'`
- English words in Persian text: transliterate or skip

---

## Related Skills

- `xtts-v2.md` — Full XTTS v2 reference (inference, streaming, fine-tuning base)
- `huggingface-tts.md` — MMS-TTS and Parler-TTS (MMS has out-of-box Persian)
- `mlx-whisper.md` — Transcribing Persian audio (needed for dataset preparation)
