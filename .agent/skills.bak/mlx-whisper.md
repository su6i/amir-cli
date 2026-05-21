---
description: MLX Whisper transcription on Apple Silicon — model variants, performance profiles, and integration with amir-cli subtitle pipeline.
updated: 2026-05-20
---

# MLX Whisper (Apple Silicon Transcription)

## Overview

MLX Whisper is a port of OpenAI Whisper to Apple's MLX framework, optimized for M-series chips (M1/M2/M3/M4). It runs on the Neural Engine + GPU via Metal and is significantly faster than CPU-based faster-whisper for long-form audio on macOS.

**When to use MLX Whisper vs faster-whisper:**

| Condition | Use |
|---|---|
| macOS + Apple Silicon + single job | MLX Whisper (faster, lower latency) |
| macOS + parallel jobs (RAM pressure) | faster-whisper (CPU, isolated memory) |
| `AMIR_FORCE_FASTER_WHISPER=1` | faster-whisper (forced) |
| Low-RAM mode active | faster-whisper (MLX fallback disabled) |

## Installation

```bash
# Requires: Python 3.11+, Apple Silicon
pip install mlx-whisper

# Models are downloaded on first use to ~/.cache/huggingface/hub/
# Or pre-download:
python -c "import mlx_whisper; mlx_whisper.load_models.load_model('mlx-community/whisper-large-v3-mlx')"
```

## Model Variants (MLX community)

| Model | Size | Speed | RAM | Quality |
|---|---|---|---|---|
| `whisper-large-v3-mlx` | ~3GB | ~2–3x realtime | ~6GB | Best |
| `whisper-large-v3-turbo-mlx` | ~1.6GB | ~5x realtime | ~3.5GB | Near-large |
| `whisper-medium-mlx` | ~1.5GB | ~6x realtime | ~3GB | Good |
| `whisper-small-mlx` | ~500MB | ~10x realtime | ~1.5GB | Fast |

**Default in amir-cli:** `large-v3` (falls back to MLX variant when available).

## Basic Usage

```python
import mlx_whisper

result = mlx_whisper.transcribe(
    "video.mp4",
    path_or_hf_repo="mlx-community/whisper-large-v3-mlx",
    language="en",          # None = auto-detect
    word_timestamps=True,   # Required for SRT generation
    verbose=False,
)

# result["segments"] → list of {start, end, text, words}
# result["language"] → detected language code
```

## Integration with amir-cli

**Entry point:** `lib/python/subtitle/workflow/transcription_stage.py`

The pipeline selects MLX vs faster-whisper based on:
```python
# Selection logic (simplified):
use_mlx = (
    platform.system() == "Darwin"
    and not os.environ.get("AMIR_FORCE_FASTER_WHISPER")
    and not low_ram_mode
    and mlx_whisper_available()
)
```

**Environment controls:**
```bash
AMIR_FORCE_FASTER_WHISPER=1   # Force CPU faster-whisper
AMIR_SUBTITLE_ADAPTIVE_RAM=0  # Disable adaptive RAM profiling
```

## Performance Tuning

### Chunked transcription (long videos)
MLX Whisper can OOM on very long videos (>1h) if run in one pass. Use chunked mode:

```python
# Split audio into chunks, transcribe each, stitch timestamps
CHUNK_DURATION_SECONDS = 600  # 10 min chunks
```

amir-cli already implements this in `transcription_stage.py` for low-RAM mode.

### Beam size vs speed
```python
# Fast (beam=1, greedy):
result = mlx_whisper.transcribe(audio, beam_size=1)

# Balanced (beam=5, default):
result = mlx_whisper.transcribe(audio, beam_size=5)
```

For subtitle generation, beam_size=5 is recommended (better word boundary detection).

## Known Issues & Gotchas

1. **MallocStackLogging warnings:** MLX may trigger macOS memory logging spam. Unset:
   ```bash
   env -u MallocStackLogging -u MallocStackLoggingNoCompact python3 -m subtitle ...
   ```
   amir-cli already handles this in `_subtitle_run()` in `lib/commands/subtitle.sh`.

2. **Parallel jobs:** MLX uses GPU/ANE shared with other processes. If two MLX jobs run simultaneously, they compete for Metal memory. Use `AMIR_SUBTITLE_ADAPTIVE_RAM=1` (default) to auto-detect and fall back to faster-whisper for secondary jobs.

3. **Word timestamp alignment:** MLX Whisper word timestamps can drift slightly from faster-whisper. amir-cli's `normalize_and_fix_timing()` handles this.

4. **Model lock:** When `AMIR_FORCE_MODEL_LOCK=1`, the pipeline keeps `large-v3` regardless of RAM. Override with `AMIR_SUBTITLE_MODEL=medium` to reduce memory.

## References

- MLX community models: `https://huggingface.co/mlx-community`
- MLX Whisper GitHub: `https://github.com/ml-explore/mlx-examples/tree/main/whisper`
- faster-whisper comparison: see `.agent/skills/subtitle-generator.md`
