---
title: "AI Music Generation — MusicGen, AudioCraft, Suno, Udio"
description: Generate background music, jingles and sound beds for YouTube automation — MusicGen (local), Suno API, Udio API
location: .agent/skills/music-generation.md
agent_priority: Standard
last_updated: 2026-05-30
---

# AI Music Generation

## Decision Table

| Tool | Cost | Quality | Latency | Commercial? | Best for |
|------|------|---------|---------|-------------|----------|
| **MusicGen (local)** | Free | Good (32kHz) | 1–5 min/clip | CC-BY-NC (weights) | Dev/testing, non-commercial |
| **AudioGen (local)** | Free | Good | 1–3 min | CC-BY-NC (weights) | Sound FX, ambience, not music |
| **Bark (local)** | Free (MIT) | Medium | Slow on CPU | Yes (MIT) | Voice + music hybrid, jingles |
| **Suno API (unofficial)** | Paid (credits) | Excellent | ~30s | Check TOS | Full songs with vocals |
| **Udio API (unofficial)** | Paid (credits) | Excellent | ~30s | Check TOS | Iterative/extended tracks |
| **Replicate MusicGen** | Pay-per-use | Good | ~20s | Yes | Cloud, no GPU needed |

**Rule of thumb:** Local MusicGen for background instrumentals (free, controllable duration). Suno/Udio for full produced songs with lyrics. Bark for spoken-word + music blends.

---

## 1. MusicGen / AudioCraft (Local)

### Install

```bash
# Requires Python 3.9, PyTorch 2.1
# In project venv:
uv pip install audiocraft
# FFmpeg required:
brew install ffmpeg  # macOS
```

Model cache location: `~/.cache/huggingface/hub/` — override with `AUDIOCRAFT_CACHE_DIR`.

### Generate music from text prompt

```python
import torchaudio
from audiocraft.models import MusicGen
from audiocraft.data.audio import audio_write

model = MusicGen.get_pretrained("facebook/musicgen-small")  # or -medium, -large, -melody
model.set_generation_params(duration=30)  # seconds — max ~30s per call

descriptions = ["upbeat electronic background music, 120bpm, no vocals"]
wav = model.generate(descriptions)  # shape: [batch, channels, samples]

# Save to WAV
audio_write(
    "output",           # filename without extension
    wav[0].cpu(),
    model.sample_rate,  # 32000 Hz
    strategy="loudness",
    loudness_compressor=True,
)
# Output: output.wav
```

### Generate longer loops (chaining)

```python
model.set_generation_params(duration=30)
segments = []
prompt = "calm lo-fi hip hop, piano, soft drums, no vocals"

# Generate 3 segments → ~90s total
for _ in range(3):
    wav = model.generate([prompt])
    segments.append(wav[0].cpu())

import torch
full = torch.cat(segments, dim=-1)
audio_write("music_90s", full, model.sample_rate, strategy="loudness")
```

### Model size guide

| Model | Size | VRAM | Notes |
|-------|------|------|-------|
| `musicgen-small` | 300M | ~4GB | Fast, decent quality |
| `musicgen-medium` | 1.5B | ~8GB | Best quality/speed trade-off |
| `musicgen-large` | 3.3B | ~16GB | Best quality |
| `musicgen-melody` | 1.5B | ~8GB | Melody conditioning supported |

### AudioGen (sound effects)

```python
from audiocraft.models import AudioGen

model = AudioGen.get_pretrained("facebook/audiogen-medium")
model.set_generation_params(duration=5)
wav = model.generate(["birds chirping in forest", "rain on window"])
audio_write("sfx_birds", wav[0].cpu(), model.sample_rate)
```

### License note

Code: MIT. **Model weights: CC-BY-NC 4.0** — non-commercial only. For commercial YouTube monetization, use Replicate API (which has its own commercial terms) or Suno/Udio.

---

## 2. Bark (Local, MIT License)

Bark is a TTS-plus model: speech, music, sound effects — all in one. MIT license = commercial use allowed.

```bash
uv pip install git+https://github.com/suno-ai/bark.git
```

```python
from bark import SAMPLE_RATE, generate_audio, preload_models
from scipy.io.wavfile import write as write_wav

preload_models()  # downloads ~5GB on first run

# Music with lyrics — wrap in ♪ notes
audio = generate_audio("♪ Hello world, this is my YouTube intro ♪")
write_wav("bark_music.wav", SAMPLE_RATE, audio)
# SAMPLE_RATE = 24000
```

**Limitation:** Bark is non-deterministic and short (seconds per call). Not suited for 3-minute background tracks. Use for short jingles or voice+music blends.

---

## 3. Suno API (Unofficial Python Client)

Suno requires a browser cookie from `app.suno.ai` — not a formal API key.

```bash
uv pip install SunoAI
```

```python
from suno import Suno, ModelVersions

client = Suno(
    cookie="YOUR_SUNO_COOKIE",     # from browser DevTools → Network → _clerk_js_version
    model_version=ModelVersions.CHIRP_V3_5,
)

# Generate a song (returns list of Song objects)
songs = client.generate(
    prompt="upbeat corporate background music, no vocals, 120bpm",
    is_custom=False,    # True = custom mode with lyrics/style fields
    wait_audio=True,    # blocks until audio is ready
)

for song in songs:
    print(song.id, song.audio_url)
    client.download(song=song, root_dir="./music_output/")
```

**Polling (non-blocking):**

```python
songs = client.generate(prompt="...", wait_audio=False)
import time
while not all(s.audio_url for s in songs):
    time.sleep(5)
    songs = [client.get(s.id) for s in songs]
```

**Notes:**
- Cookie expires — regenerate when getting 401.
- Suno TOS restricts monetization of generated tracks. Verify current policy before publishing.

---

## 4. Udio API (Unofficial Python Client)

```bash
uv pip install udio_wrapper
```

Get token: Browser DevTools → Application → Cookies → `sb-api-auth-token`.

```python
from udio_wrapper import UdioWrapper

udio = UdioWrapper("YOUR_AUTH_TOKEN")

# Generate track
result = udio.generate(
    prompt="calm ambient background, piano, lo-fi, no vocals",
    seed=-1,           # -1 = random
)
# result contains audio_url and track_id

# Extend/continue an existing track (Udio's unique feature)
extended = udio.generate(
    prompt="continue in the same style, build up",
    conditioning_track_id=result["track_id"],
)
```

**Udio advantage:** Iterative extension — generate 30s, extend by 30s repeatedly to build long tracks without quality gaps.

---

## 5. Background Music Pipeline for YouTube

### Full pipeline: generate → loop → fade → mix under voice

```bash
#!/usr/bin/env bash
# Usage: ./music_mix.sh voice.wav music_prompt output.mp4

VOICE="$1"
PROMPT="$2"
OUTPUT="${3:-final_mix.wav}"

# Step 1 — generate 90s instrumental with MusicGen (Python)
python3 - <<PYEOF
from audiocraft.models import MusicGen
from audiocraft.data.audio import audio_write
import torch

m = MusicGen.get_pretrained("facebook/musicgen-small")
m.set_generation_params(duration=30)
segs = [m.generate(["$PROMPT"])[0].cpu() for _ in range(3)]
audio_write("/tmp/bg_raw", torch.cat(segs, dim=-1), m.sample_rate, strategy="loudness")
PYEOF

# Step 2 — get voice duration, trim/loop music to match
VOICE_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VOICE")

ffmpeg -y \
  -stream_loop -1 -i /tmp/bg_raw.wav \
  -t "$VOICE_DUR" \
  -af "afade=t=in:st=0:d=2,afade=t=out:st=$(echo "$VOICE_DUR - 2" | bc):d=2" \
  /tmp/bg_looped.wav

# Step 3 — mix voice (0dB) + music (-18dB ducking)
ffmpeg -y \
  -i "$VOICE" \
  -i /tmp/bg_looped.wav \
  -filter_complex "[1:a]volume=0.12[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=3[out]" \
  -map "[out]" \
  "$OUTPUT"

echo "Mixed: $OUTPUT"
```

### Fade in/out only (FFmpeg)

```bash
# Fade in 2s, fade out last 3s of a 60s file
ffmpeg -i music.wav \
  -af "afade=t=in:st=0:d=2,afade=t=out:st=57:d=3" \
  music_faded.wav
```

### Duck music under voice (sidechain)

```bash
ffmpeg -i voice.wav -i music.wav \
  -filter_complex "
    [1:a]volume=0.15[bg];
    [0:a][bg]amix=inputs=2:duration=longest:weights=1 0.15[mix]
  " \
  -map "[mix]" output_mixed.wav
```

---

## 6. Music Categories for YouTube

| Category | MusicGen Prompt | Duration |
|----------|----------------|----------|
| Upbeat intro | `"upbeat corporate pop, energetic, 128bpm, no vocals, bright piano"` | 10–15s |
| Calm background | `"lo-fi hip hop, soft piano, relaxed drums, ambient, no vocals"` | 60–180s |
| Tech explainer | `"modern electronic background, minimal, focused, 100bpm, no vocals"` | 60–120s |
| Outro fade | `"gentle acoustic guitar, resolving, fade out, calm, no vocals"` | 15–20s |
| Suspense/reveal | `"cinematic tension build, strings, percussion crescendo"` | 5–10s |

**Tip:** Append `", 32kHz, high quality, stereo"` to any MusicGen prompt — it conditions the model toward broadcast quality output.

---

## 7. Licensing Summary

| Tool | Weights/Model License | Code License | Commercial YouTube Use |
|------|-----------------------|--------------|------------------------|
| MusicGen / AudioGen | CC-BY-NC 4.0 | MIT | No (non-commercial only) |
| Bark | MIT | MIT | Yes |
| Suno (generated audio) | Suno TOS | N/A | Check current TOS |
| Udio (generated audio) | Udio TOS | N/A | Check current TOS |
| Replicate MusicGen | Pay-per-use API TOS | N/A | Generally yes |

For monetized YouTube channels, safest options: Bark (MIT) or Suno/Udio with paid plan (verify TOS). MusicGen is free but restricted to non-commercial unless using via a licensed API wrapper.
