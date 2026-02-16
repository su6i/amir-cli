<div align="center">
  <img src="../assets/project_logo.svg" width="350" alt="Subtitle Generator Logo">
  <h1>🎬 Multi-Language Video Subtitle Generator</h1>

  ![Version](https://img.shields.io/badge/Version-1.0.0-blue.svg)
  ![Python](https://img.shields.io/badge/Python-3.8+-yellow.svg)
  ![License](https://img.shields.io/badge/License-MIT-green.svg)
  <a href="https://www.linkedin.com/in/su6i/">
    <img src="../assets/linkedin_su6i.svg" height="20" alt="LinkedIn">
  </a>
</div>

## Overview
Automatically transcribe videos and translate subtitles into multiple languages using Whisper AI and DeepSeek API. Generate SRT/ASS files and render videos with embedded multilingual subtitles with real-time progress tracking.

## ✨ Features

- 🎙️ **Automatic Speech Recognition** using Faster-Whisper
- 🌍 **15+ Languages Supported** (English, Persian, Arabic, Spanish, French, German, Russian, Japanese, Korean, Chinese, and more)
- 🤖 **AI-Powered Translation** via DeepSeek API with enhanced Persian typography
- 📝 **Multiple Output Formats** (SRT, ASS)
- 🎨 **Language-Specific Fonts** with automatic configuration
- 🎥 **Video Rendering** with embedded subtitles (single or multiple languages)
- 📊 **Real-Time Progress Bar** during video encoding
- 💾 **Smart Caching** - Skip existing subtitles to save time
- 🔄 **Batch Processing** - Efficient API usage
- ✍️ **Persian Typography Fix** - Automatic ZWNJ correction (نیم‌فاصله)

## 🛠️ Developer & Technical Documentation

> [!NOTE]
> This is the **internal technical documentation** for the subtitle module.
> Normal users should simply use the `amir subtitle` command from the main [Amir CLI Project](https://github.com/su6i/amir-cli).

This module is a self-contained Python project managed by `uv` within the `amir-cli` repository.

## 📦 Project Structure

- **Manager**: `uv` (replaces pip/venv manual management)
- **Engine**: `processor.py` (Core logic and `SubtitleProcessor` class)
- **CLI**: `cli.py` (Argument parsing and terminal orchestration)
- **Entry**: `__main__.py` (Standard Python package entry point)
- **Config**: `.config` (INI format)
- **Assets**: `assets/` (Fonts, Logos)
- **Output**: Generates `srt` and `ass` files alongside the video.

## 🚀 Development Setup (Standalone)

If you want to work on this module independently:

1. **Install uv**:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Run via uv**:
   ```bash
   cd lib/python/subtitle
   uv run main.py --help
   ```

## 💻 CLI Interface (How `amir` calls it)

The `amir` bash wrapper (`lib/commands/subtitle.sh`) executes this module using:
```bash
uv run --project "lib/python/subtitle" python -m subtitle "$@"
```

### 🛠️ Configuration

The module requires a `.config` file in its directory (created automatically by `amir` installer):

```ini
[DEFAULT]
DEEPSEEK_API = sk-your-key
```

### ⚡ Basic Usage

You can run these commands via `amir subtitle` (production) or `uv run python -m subtitle` (dev).

```bash
# Transcribe English video and translate to Persian
amir subtitle video.mp4 -s en -t fa

# Translate to multiple languages
amir subtitle video.mp4 -s en -t fa ar es

# Render video with embedded subtitles (with progress bar)
amir subtitle video.mp4 -s en -t fa -r

# Force re-transcription
amir subtitle video.mp4 -s en -t fa -f

# List all supported languages
amir subtitle -l
```

## 📖 Usage Guide

### Command Line Options

```
usage: video_multilang_translate.py [-h] [-s SOURCE] [-t TARGET [TARGET ...]] 
                                     [-m {tiny,base,small,medium,large}] 
                                     [-r] [-f] [-l] [video]

positional arguments:
  video                 Video file path

optional arguments:
  -h, --help            Show this help message and exit
  -s, --source SOURCE   Source language code (default: en)
  -t, --target TARGET   Target language code(s) - can specify multiple
  -m, --model MODEL     Whisper model size (default: base)
                        Options: tiny, base, small, medium, large
  -r, --render          Render video with embedded subtitles
  -f, --force-transcribe  Force re-transcription even if subtitle exists
  -l, --list-languages  List all supported languages
```

### Examples

#### 1. Basic Translation
```bash
# English to Persian
python video_multilang_translate.py my_video.mp4 -s en -t fa
```

**Output:**
- `my_video_en.srt` - English subtitles
- `my_video_fa.srt` - Persian subtitles
- `my_video_en.ass` - English styled subtitles
- `my_video_fa.ass` - Persian styled subtitles

#### 2. Multiple Target Languages
```bash
# Translate to Persian, Arabic, and Spanish
python video_multilang_translate.py lecture.mp4 -s en -t fa ar es
```

**Output:**
- Original + 3 translated subtitle files in both SRT and ASS formats

#### 3. Video with Embedded Subtitles
```bash
# Create video with Persian subtitles burned in
python video_multilang_translate.py tutorial.mp4 -s en -t fa -r
```

**Output:**
- `tutorial_fa_subtitled.mp4` - Video with Persian subtitles
- Real-time encoding progress: `Encoding: 47%`

#### 3b. Multiple Language Subtitles
```bash
# Create video with both English and Persian subtitles
python video_multilang_translate.py tutorial.mp4 -s en -t en fa -r
```

**Output:**
- `tutorial_en_fa_subtitled.mp4` - Video with both languages stacked

#### 4. Different Source Language
```bash
# Transcribe French video and translate to English
python video_multilang_translate.py french_film.mp4 -s fr -t en
```

#### 5. Force Re-transcription
```bash
# Re-process even if subtitle files exist
python video_multilang_translate.py video.mp4 -s en -t fa -f
```

#### 6. High-Quality Transcription
```bash
# Use larger Whisper model for better accuracy
python video_multilang_translate.py podcast.mp4 -s en -t fa -m large
```

## 🌐 Supported Languages

| Code | Language | Native Font |
|------|----------|-------------|
| `en` | English | Arial |
| `fa` | Persian (Farsi) | B Nazanin (MANDATORY LAW) |
| `ar` | Arabic | Arial |
| `es` | Spanish | Arial |
| `fr` | French | Arial |
| `de` | German | Arial |
| `it` | Italian | Arial |
| `pt` | Portuguese | Arial |
| `ru` | Russian | Arial |
| `ja` | Japanese | MS Gothic |
| `ko` | Korean | Malgun Gothic |
| `zh` | Chinese | SimHei |
| `hi` | Hindi | Mangal |
| `tr` | Turkish | Arial |
| `nl` | Dutch | Arial |
| `mg` | Malagasy | Arial |

View full list: `python video_multilang_translate.py -l`

## 🔧 How It Works

1. **Transcription**: Uses Faster-Whisper to generate accurate speech-to-text from video
2. **Smart Caching**: Checks for existing subtitle files to avoid redundant processing
3. **Translation**: Sends text to DeepSeek API in optimized batches (20 lines per call)
4. **Typography Enhancement**: Automatically fixes Persian text (adds proper ZWNJ: می‌کنم, صحبت‌های)
5. **Subtitle Generation**: Creates SRT files with proper timing
6. **Styling**: Converts to ASS format with language-appropriate fonts and sizes
7. **Resolution Matching**: Adjusts subtitle size based on actual video resolution
8. **Video Rendering** (optional): Burns subtitles into video using FFmpeg with real-time progress

## 📁 Output Files

For a video named `example.mp4` with source `en` and target `fa`:

```
example.mp4                    # Original video
example_en.srt                 # English subtitles (SRT)
example_fa.srt                 # Persian subtitles (SRT)
example_en.ass                 # English subtitles (ASS - styled)
example_fa.ass                 # Persian subtitles (ASS - styled)
example_fa_subtitled.mp4       # Video with Persian subtitle (if -r used)
```

For multiple languages (`-t en fa`):
```
example_combined.ass           # Combined subtitle file (temporary)
example_en_fa_subtitled.mp4    # Video with both subtitles stacked
```

**Note**: Temporary `_fixed.ass` files are automatically deleted after rendering.

## ⚙️ Configuration

### Whisper Model Selection

Choose based on your needs:

| Model | Speed | Accuracy | VRAM |
|-------|-------|----------|------|
| `tiny` | Fastest | Basic | ~1 GB |
| `base` | Fast | Good | ~1 GB |
| `small` | Medium | Better | ~2 GB |
| `medium` | Slow | Great | ~5 GB |
| `large` | Slowest | Best | ~10 GB |

### API Configuration

The script uses DeepSeek's chat model with:
- **Model**: `deepseek-chat`
- **Temperature**: 0.3 (more consistent translations)
- **Max Tokens**: 4000 per request
- **Batch Size**: 20 lines per API call
- **Persian Enhancement**: Special prompt with ZWNJ rules and typography fixes

### Font Size Configuration

Default font sizes are optimized for 1080p videos. To adjust for different resolutions, edit `LANGUAGE_CONFIG` in the script:

```python
LANGUAGE_CONFIG = {
    'en': {'name': 'English', 'font': 'Arial', 'font_size': 36, 'rtl': False},
    'fa': {'name': 'Persian', 'font': 'B Nazanin', 'font_size': 36, 'rtl': True},
    # ...
}
```

**Recommended sizes by resolution:**
- 720p: 24-28
- 1080p: 32-40 (default: 36)
- 1440p: 48-56
- 4K: 72-84

## 🐛 Troubleshooting

### "FFmpeg not found"
# Professional Setup (Internal)
# The amir CLI automatically installs FFmpeg 8.0 with libass support to ~/.local/bin/
# This ensures perfect subtitle rendering regardless of system defaults.
```

### "API key not found"
Make sure `.config` file exists in the same directory with:
```ini
[DEFAULT]
DEEPSEEK_API = sk-your-actual-key-here
```

### "Font not found" warnings
The script will fall back to Arial if specific fonts are missing. To get optimal results:
- **Windows**: Fonts usually included by default
- **Linux**: Install language-specific fonts
  ```bash
  sudo apt-get install fonts-noto
  ```

### Translation quality issues
- Use larger Whisper model (`-m medium` or `-m large`)
- Check source language is correctly specified (`-s` parameter)
- Verify audio quality of the video
- For Persian: Script automatically fixes common issues like:
  - Missing ZWNJ: `صحبتهای` → `صحبت‌های`
  - Verb prefixes: `می کنم` → `می‌کنم`

### Subtitle too small or too large
The script automatically adjusts subtitle size based on video resolution. If you need manual adjustment:
1. Open the script file
2. Find `LANGUAGE_CONFIG` at the top (around line 16)
3. Change `'font_size'` values (default: 36)
4. Delete old ASS files and re-run with `-f` flag

### Progress bar not showing
- Ensure you're using `-r` flag to enable rendering
- Progress shows as: `Encoding: 0%` → `Encoding: 100% ✓`
- If stuck, check FFmpeg is properly installed

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Adding New Languages

1. Add to `LANGUAGE_CONFIG` in the script:
```python
'xx': {'name': 'Language Name', 'font': 'Font Name', 'font_size': 20, 'rtl': False}
```

2. Test with sample video
3. Submit PR with language code documentation

## 🤝 Contributing
Contributions are welcome! Please check the issues page or submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## 🙏 Acknowledgments

- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper) - Fast Whisper implementation
- [DeepSeek](https://www.deepseek.com/) - AI translation API
- [FFmpeg](https://ffmpeg.org/) - Video processing

## 📊 Performance Tips

- **Best Speed**: Use `base` model for quick results (recommended for most use cases)
- **Best Quality**: Use `large` model for important content or complex audio
- **Smart Caching**: Script automatically skips existing files - use `-f` to override
- **Batch Translations**: Handles 20 lines per API call for efficiency
- **Multiple Languages**: Specify all targets in one command to avoid re-transcription
- **Video Quality**: Rendered videos maintain original quality (CRF 23)
- **Progress Tracking**: Real-time percentage during encoding with `-r` flag

## 🔮 Roadmap

- [x] Real-time encoding progress bar
- [x] Automatic Persian typography correction (ZWNJ)
- [x] Dynamic font size based on video resolution
- [x] Smart file cleanup (remove temporary files)
- [ ] Support for audio files (MP3, WAV, etc.)
- [ ] GUI interface
- [ ] Subtitle timing adjustment tools
- [ ] Support for multiple translation services
- [ ] Batch processing multiple videos

## 💡 Tips & Best Practices

- **Best Quality**: Use `-m large` for important content or noisy audio
- **Fast Processing**: Use `-m tiny` or `base` for quick drafts  
- **Multiple Languages**: Always specify all targets in one command (e.g., `-t en fa ar`)
- **Video Quality**: CRF 23 maintains excellent quality with reasonable file size
- **Persian Content**: Script automatically adds proper ZWNJ - no manual editing needed
- **Force Refresh**: Use `-f` if you updated font sizes or want fresh transcription
- **Check Progress**: With `-r` flag, you'll see real-time encoding percentage
- **File Management**: Temporary files are auto-deleted; only keep final SRT/ASS/MP4

---

**Star ⭐ this repo if you find it useful!**

For issues and feature requests, please open an issue on GitHub.