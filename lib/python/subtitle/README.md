# Subtitle Processor Package

This package constitutes the core Python implementation for the `amir subtitle` command. It is designed as a modular, standalone library for programmatic subtitle generation and rendering.

## 🏗️ Architecture

The logic is encapsulated in the `SubtitleProcessor` class within `processor.py`.

### Key Classes

-   **`SubtitleProcessor`**: The main orchestration engine. Handles state, logging, and workflow execution.
-   **`SubtitleStyle` (Enum)**: Defines visual templates (`LECTURE`, `VLOG`, etc.).
-   **`ProcessingStage` (Enum)**: Tracks workflow progress (`TRANSCRIPTION`, `TRANSLATION`, `RENDERING`) for checkpointing.
-   **`StyleConfig` (DataClass)**: Holds CSS/ASS style definitions (font, alignment, colors).

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
    render=True,     # Burn subtitles into video
    detect_speakers=True # Enable diarization
)

print(f"Rendered Video: {result.get('rendered_video')}")
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