# Subtitle Processor Package

This package constitutes the core Python implementation for the `amir subtitle` command. It is designed as a modular, standalone library for programmatic subtitle generation and rendering.

## 🏗️ Architecture

The logic is encapsulated in the `SubtitleProcessor` class within `processor.py`.

### Key Classes

-   **`SubtitleProcessor`**: The main orchestration engine. Handles state, logging, and workflow execution.
-   **`SubtitleStyle` (Enum)**: Defines visual templates (`LECTURE`, `VLOG`, etc.).
-   **`ProcessingStage` (Enum)**: Tracks workflow progress (`TRANSCRIPTION`, `TRANSLATION`, `RENDERING`) for checkpointing.
-   **`StyleConfig` (DataClass)**: Holds CSS/ASS style definitions (font, alignment, colors).

### Key Methods

-   **`run_workflow(video_path, source_lang, target_langs, ..., post_langs=None)`**: Full pipeline orchestrator. `post_langs` restricts which language posts are generated (default: `['fa']` only).
-   **`generate_posts(original_base, source_lang, result, platforms, post_langs=None)`**: Generates social media posts from SRT files. Returns `{lang_platform: output_path}` dict.
-   **`_get_post_prompt(platform, title, ...)`**: Builds analytical/factual LLM prompt. Analytical journalist tone — no promotional language.
-   **`_telegram_sections_complete(text)`**: Validates all 8 required Telegram post sections (📽️ 🔴 🚨 ✨ 📌 ⏱️ 5×🔹 #). Returns `(bool, missing_list)`.
-   **`_sanitize_post(text, platform)`**: Strips markdown formatting, enforces 1024-char Telegram hard cap.
-   **`_srt_duration_str(entries, lang='fa')`**: Formats video duration — Persian-Indic numerals for `fa`, Latin numerals for all others.
-   **`translate_with_deepseek()`**: Batch translation with retry logic.
-   **`create_ass_with_font()`**: ASS subtitle generation with bilingual support and RTL.
-   **`_ingest_partial_srt()`**: Resume capability — recovers existing translations from partial SRT.

## 💻 Programmatic Usage

You can use this package in your own Python scripts:

```python
from subtitle.processor import SubtitleProcessor, SubtitleStyle

# Initialize with desired configurations
processor = SubtitleProcessor(
    style=SubtitleStyle.VLOG,
    max_lines=2,
    model_size="large-v3" # or "medium", "small"
)

# Run the full workflow
result = processor.run_workflow(
    video_path="input.mp4",
    source_lang="en",
    target_langs=["fa", "fr"],
    render=True,           # Burn subtitles into video
    detect_speakers=True,  # Enable diarization
    post_langs=["fa"],     # Generate FA post only (default); use ["fa", "de"] for multiple
)

print(f"Rendered Video: {result.get('rendered_video')}")

# Generate posts from existing SRTs without re-processing
posts = processor.generate_posts(
    original_base="/path/to/video",
    source_lang="de",
    result={"fa": "/path/to/video_fa.srt", "de": "/path/to/video_de.srt"},
    platforms=["telegram"],
    post_langs=["fa", "de"],  # explicitly request both; default is ["fa"] only
)
```

## 🛠️ Development

### dependencies
Dependencies are managed via `pyproject.toml`.
-   `faster-whisper` / `mlx-whisper`: Transcription.
-   `pyannote.audio`: Speaker Diarization.
-   `openai`: DeepSeek API client for translation.
-   `static-ffmpeg`: For standalone FFmpeg binaries.

### Running Tests
Use the included demo script to verify functionality:
```bash
python -m subtitle demo_pro.py dummy_video.mp4
```