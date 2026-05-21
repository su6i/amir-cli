# FFmpeg & FFprobe Technical Reference

> [!IMPORTANT]
> This document serves as a technical reference for FFmpeg operations used within the Amir CLI.
> **Standard Flags:** `-hide_banner -loglevel error -stats` (Clean output).

## 1. Metadata Analysis (FFprobe)
**Purpose:** Efficiently extract technical metadata without full JSON parsing.

### A. Duration Extraction
**Operation:** Get exact duration in seconds.
```bash
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$input")
```

### B. Stream Analysis
**Operation:** specific video stream properties (Codec, Resolution, Bitrate).
```bash
ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,width,height,bit_rate \
    -of csv=p=0 "$input"
```

---

## 2. Video Compression Strategy
**Protocol:** Constant Rate Factor (CRF) for quality control.

### A. CPU Encoding (H.264)
**Target:** Compatibility and Archiving.
```bash
ffmpeg -hide_banner -loglevel error -stats -y \
    -i "$input" \
    -c:v libx264 -crf 23 -preset medium \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    "$output"
```
*   **`-crf 23`**: Default quality index (18-28 range).
*   **`-preset medium`**: Encoding speed/ratio balance.
*   **`-movflags +faststart`**: Web-optimized atom placement.

### B. Hardware Acceleration (macOS)
**Target:** Performance on Apple Silicon.
```bash
ffmpeg ... -c:v h264_videotoolbox -b:v 2000k ...
```
*Note:* Hardware encoders typically require target bitrate rather than CRF.

---

## 3. Audio Operations

### A. Extraction (MP3)
**Operation:** Isolate audio stream.
```bash
ffmpeg -hide_banner -loglevel error -stats -y \
    -i "$video_input" \
    -vn \
    -c:a libmp3lame -b:a 320k \
    "$audio_output.mp3"
```
*   **`-vn`**: Disable video recording.

### B. Removal
**Operation:** Strip audio track.
```bash
ffmpeg -i "$input" -c copy -an "$output"
```
*   **`-an`**: Disable audio recording.
*   **`-c copy`**: Stream copy (no re-encoding).

---

## 4. Subtitle Management

### A. Soft Subtitles (Container Stream)
**Operation:** Embed subtitles as selectable track.
```bash
ffmpeg -i "$video" -i "$subs.srt" \
    -c copy -c:s mov_text \
    -metadata:s:s:0 language=eng \
    "$output"
```

### B. Hard Subtitles (Burn-in)
**Operation:** Render text onto video frames.
**Requirement:** Re-encoding.
```bash
ffmpeg -i "$video" -vf "subtitles='$subs.srt':force_style='FontName=Arial,FontSize=24'" \
    -c:a copy \
    "$output"
```

---

## 5. Filters & Editing

### A. Scale
**Operation:** Resize width/height.
```bash
# Set height to 720, auto-calculate width (divisible by 2)
ffmpeg -i "$input" -vf "scale=-2:720" ...
```

### B. Trim
**Operation:** Cut segment without re-encoding.
```bash
ffmpeg -ss 00:01:00 -to 00:02:30 -i "$input" -c copy "$output"
```
*Optimization:* Place `-ss` before `-i` for input seeking.
