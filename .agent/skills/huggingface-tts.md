---
title: "HuggingFace TTS Models — Parler, MMS, SpeechT5"
description: Open-source TTS via HuggingFace transformers — Parler-TTS, MMS (1100+ languages incl. Persian), SpeechT5
location: .agent/skills/huggingface-tts.md
agent_priority: Standard
last_updated: 2026-05-30
---

# HuggingFace TTS Models — Parler, MMS, SpeechT5

Three production-ready open TTS families available via `transformers` and `pipeline()`. All run locally, no API key needed.

---

## Model Comparison

| Model | Languages | Voice Control | Persian | Best For |
|---|---|---|---|---|
| **Parler-TTS Mini** (880M) | English-dominant | Text description | No | High-quality EN narration |
| **Parler-TTS Large** (2.3B) | English-dominant | Text description | No | Best EN quality |
| **MMS-TTS** | 1100+ incl. Persian | Fixed per checkpoint | Yes (`fas`) | Multilingual, Persian |
| **SpeechT5** | English | Speaker embedding | No | Lightweight EN TTS |

---

## 1. Parler-TTS — Description-Based Voice Control

Parler-TTS is unique: you control voice characteristics (gender, pace, pitch, environment) via a natural language description. No reference audio needed.

- Repo: https://github.com/huggingface/parler-tts
- Models: `parler-tts/parler-tts-mini-v1` (880M), `parler-tts/parler-tts-large-v1` (2.3B)
- Trained on 45k hours of audiobook data

### Install

```bash
pip install git+https://github.com/huggingface/parler-tts.git
pip install soundfile

# Apple Silicon (bfloat16 support):
pip3 install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cpu
```

### Random Voice

```python
import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
import soundfile as sf

device = "cuda:0" if torch.cuda.is_available() else "cpu"

model = ParlerTTSForConditionalGeneration.from_pretrained("parler-tts/parler-tts-mini-v1").to(device)
tokenizer = AutoTokenizer.from_pretrained("parler-tts/parler-tts-mini-v1")

prompt = "Hey, how are you doing today?"
description = "A female speaker delivers a slightly expressive and animated speech with a moderate speed and pitch. The recording is of very high quality, with the speaker's voice sounding clear and very close up."

input_ids = tokenizer(description, return_tensors="pt").input_ids.to(device)
prompt_input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to(device)

generation = model.generate(input_ids=input_ids, prompt_input_ids=prompt_input_ids)
audio_arr = generation.cpu().numpy().squeeze()
sf.write("output.wav", audio_arr, model.config.sampling_rate)
```

### Named Speaker (Consistent Voice)

34 built-in named speakers: Laura, Gary, Jon, Lea, Karen, Rick, Brenda, David, Eileen, Jordan, Mike, Yann, Joy, James, Eric, Lauren, Rose, Will, Jason, Aaron, Naomie, Alisa, Patrick, Jerry, Tina, Jenna, Bill, Tom, Carol, Barbara, Rebecca, Anna, Bruce, Emily.

```python
description = "Jon's voice is monotone yet slightly fast in delivery, with a very close recording that almost has no background noise."

# Same code as above — just change description
```

### Description Tips

- Use `"very clear audio"` for highest quality output
- Use `"very noisy audio"` to simulate room noise
- Punctuation controls prosody: commas add brief pauses
- Controllable features: gender, speaking rate, pitch, reverberation, background noise

### Batch Generation

```python
texts = ["First line.", "Second line.", "Third line."]
descriptions = [description] * len(texts)

input_ids = tokenizer(descriptions, return_tensors="pt", padding=True).input_ids.to(device)
prompt_input_ids = tokenizer(texts, return_tensors="pt", padding=True).input_ids.to(device)

generations = model.generate(input_ids=input_ids, prompt_input_ids=prompt_input_ids)
# generations shape: (batch, samples)
for i, gen in enumerate(generations):
    sf.write(f"out_{i}.wav", gen.cpu().numpy(), model.config.sampling_rate)
```

---

## 2. MMS-TTS — 1100+ Languages including Persian

Facebook MMS (Massively Multilingual Speech) covers 1100+ languages. Persian support: model ID `facebook/mms-tts-fas`.

- Source: https://github.com/facebookresearch/fairseq/tree/main/examples/mms
- HuggingFace hub: `facebook/mms-tts-{lang_code}`
- Persian code: `fas` (ISO 639-3)
- French code: `fra`, English: `eng`

### Install

```bash
pip install transformers torch soundfile
```

### Persian TTS with MMS

```python
from transformers import VitsModel, AutoTokenizer
import torch
import soundfile as sf

# Load Persian model
model = VitsModel.from_pretrained("facebook/mms-tts-fas")
tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-fas")

text = "سلام، حالت چطوره؟"  # Persian text

inputs = tokenizer(text, return_tensors="pt")
with torch.no_grad():
    output = model(**inputs).waveform

# Output is (1, samples) at model.config.sampling_rate (typically 16000 Hz)
sf.write("persian_output.wav", output.squeeze().numpy(), model.config.sampling_rate)
```

### French TTS with MMS

```python
model = VitsModel.from_pretrained("facebook/mms-tts-fra")
tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-fra")

text = "Bonjour, comment allez-vous ?"
inputs = tokenizer(text, return_tensors="pt")
with torch.no_grad():
    output = model(**inputs).waveform

sf.write("french_output.wav", output.squeeze().numpy(), model.config.sampling_rate)
```

### Pipeline API (Simpler)

```python
from transformers import pipeline

# Persian
tts = pipeline("text-to-speech", model="facebook/mms-tts-fas")
result = tts("سلام دنیا")
sf.write("output.wav", result["audio"].squeeze(), result["sampling_rate"])

# French
tts_fr = pipeline("text-to-speech", model="facebook/mms-tts-fra")
result = tts_fr("Bonjour le monde")
sf.write("output_fr.wav", result["audio"].squeeze(), result["sampling_rate"])
```

### MMS Language Code Reference

```
Persian/Farsi  → fas
French         → fra
English        → eng
Arabic         → arb
German         → deu
Spanish        → spa
Turkish        → tur
Russian        → rus
```

Full list: https://huggingface.co/facebook/mms-tts — search by ISO 639-3 code.

---

## 3. SpeechT5 — Lightweight English TTS

SpeechT5 is a fast, lightweight English TTS. Uses speaker embeddings from a speaker library. Good for English-only projects where speed matters more than voice variety.

```python
from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
from datasets import load_dataset
import torch
import soundfile as sf

processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts")
vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan")

# Load speaker embeddings (CMU ARCTIC dataset)
embeddings_dataset = load_dataset("Matthijs/cmu-arctic-xvectors", split="validation")
speaker_embeddings = torch.tensor(embeddings_dataset[7306]["xvector"]).unsqueeze(0)

inputs = processor(text="Hello, my dog is cute.", return_tensors="pt")
speech = model.generate_speech(inputs["input_ids"], speaker_embeddings, vocoder=vocoder)

sf.write("speecht5_output.wav", speech.numpy(), samplerate=16000)
```

---

## Choosing the Right Model

| Use Case | Recommended Model |
|---|---|
| Persian TTS | MMS-TTS (`facebook/mms-tts-fas`) |
| French TTS | MMS-TTS (`facebook/mms-tts-fra`) or Parler-TTS |
| High-quality English narration | Parler-TTS Large |
| Control voice style via text | Parler-TTS Mini/Large |
| 1100+ language coverage | MMS-TTS |
| Lightweight English, fast inference | SpeechT5 |
| Voice cloning from reference audio | XTTS v2 (see `xtts-v2.md`) |

---

## Saving to WAV — Common Pattern

```python
import soundfile as sf
import numpy as np

# From any model that returns a numpy array or tensor:
def save_wav(audio, sample_rate: int, path: str):
    if hasattr(audio, "numpy"):
        audio = audio.numpy()
    audio = audio.squeeze()
    sf.write(path, audio, sample_rate)
```

---

## Common Errors

| Error | Fix |
|---|---|
| `OSError: facebook/mms-tts-fas not found` | Check language code — use ISO 639-3 (`fas` not `fa`) |
| `RuntimeError: CUDA out of memory` | Use CPU or smaller model |
| Silent output (all zeros) | Input text may be empty or tokenized incorrectly |
| `ImportError: soundfile` | `pip install soundfile` |

---

## Related Skills

- `xtts-v2.md` — Coqui XTTS v2 voice cloning (EN/FR and 15 others)
- `persian-tts-training.md` — Fine-tuning TTS specifically for Persian
- `voice-synthesis-multilingual.md` — Pipeline patterns for multilingual projects
