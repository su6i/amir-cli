# FFmpeg & FFprobe Technical Reference

> [!IMPORTANT]
> This guide documents the "Proven Recipes" used in Amir CLI.
> **Core Principle:** Always use `-hide_banner -loglevel error -stats` for clean, professional CLI output.

## 1. 🔍 FFprobe Analysis (The Surgeon's Knife)
**Why:** Extraction of technical metadata without parsing JSON (faster/simpler).

### A. Get Exact Duration (Seconds)
```bash
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$input")
# Output: 145.2304
```

### B. Get Resolution & Codec
```bash
# Returns wide format info (e.g. "h264, 1920, 1080, 2500 kb/s")
ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,width,height,bit_rate \
    -of csv=p=0 "$input"
```

---

## 2. 📉 Video Compression (The "Smart" Way)
**Protocol:** Use **CRF** (Constant Rate Factor) for quality control, not bitrate.

### A. Standard CPU Compression (H.264)
**Best for:** Compatibility & Quality/Size balance.
```bash
ffmpeg -hide_banner -loglevel error -stats -y \
    -i "$input" \
    -c:v libx264 -crf 23 -preset medium \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    "$output"
```
*   **`-crf 23`**: Default quality (Lower = Better). Range 18-28 is sane.
*   **`-preset medium`**: Balance speed vs compression. Use `fast` for iteration, `veryslow` for archiving.
*   **`-movflags +faststart`**: Optimizes MP4 for web streaming (moves metadata to start).

### B. Hardware Acceleration (macOS / Apple Silicon)
**Best for:** Speed on Mac.
```bash
ffmpeg ... -c:v h264_videotoolbox -b:v 2000k ...
```
*Note: Hardware encoders usually use Bitrate (`-b:v`), not CRF.*

---

## 3. 🎧 Audio Operations
**Why:** `amir mp3` implementation logic.

### A. Extract Audio (MP3)
```bash
ffmpeg -hide_banner -loglevel error -stats -y \
    -i "$video_input" \
    -vn \
    -c:a libmp3lame -b:a 320k \
    "$audio_output.mp3"
```
*   **`-vn`**: "Video No" (Drop video stream).
*   **`-b:a 320k`**: Highest quality MP3 bitrate.

### B. Remove Audio
```bash
ffmpeg -i "$input" -c copy -an "$output"
```
*   **`-an`**: "Audio No".
*   **`-c copy`**: No re-encoding (Instant).

---

## 4. 🎹 Subtitle Handling
**Why:** Hardcoding subtitles (burning) vs Soft subs.

### A. Soft Subtitles (Embed)
Adds subtitles as a selectable stream (toggleable).
```bash
ffmpeg -i "$video" -i "$subs.srt" \
    -c copy -c:s mov_text \
    -metadata:s:s:0 language=eng \
    "$output"
```

### B. Hard Subtitles (Burn-in)
**Critical:** Requires re-encoding. Text becomes part of the image.
```bash
ffmpeg -i "$video" -vf "subtitles='$subs.srt':force_style='FontName=Arial,FontSize=24'" \
    -c:a copy \
    "$output"
```
*Note: Special chars in filename must be escaped for the `subtitles` filter.*

---

## 5. 🛠️ Useful Filters & Tricks

### A. Scale (Resize)
```bash
# Resize to 720p height, auto width (keep aspect ratio)
ffmpeg -i "$input" -vf "scale=-2:720" ...
```
*   `scale=-2:720` ensures width is divisible by 2 (required by some encoders).

### B. Cut/Trim
```bash
# Keep from 00:01:00 to 00:02:30 (No re-encode)
ffmpeg -ss 00:01:00 -to 00:02:30 -i "$input" -c copy "$output"
```
*   **Tip:** Put `-ss` *before* `-i` for faster seeking.
