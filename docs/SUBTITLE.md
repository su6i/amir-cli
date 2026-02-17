<div align="center">
  <img src="../assets/project_logo.svg" width="350" alt="Subtitle Generator Logo">
  <h1>🎬 Multi-Language Video Subtitle Generator</h1>

  ![Version](https://img.shields.io/badge/Version-1.1.0-blue.svg)
  ![Python](https://img.shields.io/badge/Python-3.8+-yellow.svg)
  ![License](https://img.shields.io/badge/License-MIT-green.svg)
  <a href="https://www.linkedin.com/in/su6i/">
    <img src="../assets/linkedin_su6i.svg" height="20" alt="LinkedIn">
  </a>
</div>

## Overview
Automatically transcribe videos and translate subtitles into multiple languages using Whisper AI and DeepSeek API. Generate SRT/ASS files and render videos with embedded multilingual subtitles with real-time progress tracking.

## ✨ Features

- 🎙️ **Automatic Speech Recognition** using Faster-Whisper (Large-v3 / MLX Optimized)
- 🌍 **32 Languages Supported** (Top 25 by YouTube reach 2026 + 7 extras)
  - **Top Priority:** Chinese, English, Spanish, Hindi, Arabic, Bengali, Portuguese, Russian, Japanese, French
  - **Growing Markets:** Urdu, Punjabi, Vietnamese, Turkish, Korean, Indonesian, German, Persian, Gujarati, Italian
  - **Regional Focus:** Marathi, Telugu, Tamil, Thai, Hausa (West Africa)
  - **Additional:** Greek, Hebrew, Malagasy, Dutch, Polish, Ukrainian
- 🤖 **AI-Powered Translation** via DeepSeek API with enhanced typography for all languages
- 🔁 **Resume Capability** - Continue incomplete translations with `-c/--continue` flag
- ✅ **Quality Validation** - Interactive prompts ensure 100% translation before rendering
- 🏛️ **Technical Term Preservation** - Maintains English terms in parentheses (e.g., "هوش مصنوعی عمومی (AGI)")
- 📏 **Granular UI Control** - Dynamic alignment (Top/Bottom) and font-size overrides
- 📝 **Multiple Output Formats** (SRT, ASS)
- 🎨 **Language-Specific Fonts** with automatic configuration and RTL support
- 🎥 **Smart Video Rendering** - Resolution-adaptive bitrates (480p: 1.5M → 4K: 8M)
- 📊 **Real-Time Progress Bar** during video encoding
- 💾 **Smart Caching** - SHA-256 keyed cache for transcriptions and translations
- 🔄 **Batch Processing** - Optimized API usage (25 lines/call DeepSeek, 40 Gemini, 20 LiteLLM)
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

# Resume incomplete translation (e.g., after interruption)
amir subtitle video.mp4 -t en fa -rc

# Pro Customization: Top Alignment
amir subtitle video.mp4 -t fa --alignment 8

# Translate to multiple languages
amir subtitle video.mp4 -s en -t fa ar es zh

# Render video with embedded subtitles (smart bitrate adaptation)
amir subtitle video.mp4 -s en -t fa -r

# Force re-transcription (ignore cache)
amir subtitle video.mp4 -s en -t fa -f

# List all 32 supported languages
amir subtitle -l
```

## 📖 Usage Guide

### Command Line Options

```
usage: video_multilang_translate.py [-h] [-s SOURCE] [-t TARGET [TARGET ...]] 
                                     [-m {tiny,base,small,medium,large}] 
                                     [-r] [-f] [-l] 
                                     [--alignment ALIGNMENT] [--font-size FONT_SIZE]
                                     [--sec-font-size SEC_FONT_SIZE] [--style STYLE]
                                     [video]

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
  --alignment           ASS alignment (2=Bottom, 8=Top, 5=Center)
  --font-size           Primary font size override
  --sec-font-size       Secondary font size override (for bilingual)
  --style               Style template (lecture, vlog, movie, news)

  # Pro Visual Overrides (New in 2026)
  --shadow              Shadow depth (default: 0)
  --outline             Outline width (default: 2)
  --back-color          Background color (ASS hex, e.g., &H80000000)
  --primary-color       Primary color (ASS hex, e.g., &H00FFFFFF)

  # Pro AI Tuning (New in 2026)
  --initial-prompt      Whisper initial prompt (context injection)
  --temperature         Model temperature (0.0-1.0)
  --openai-fallback     Use OpenAI if DeepSeek fails

  # Pro Logic Overrides
  --min-duration        Minimum subtitle duration (seconds)
```

### Examples (Pro Scenarios)

#### 1. Cinematic Bilingual Layout
```bash
# Top English (Gray/Small) + Bottom Persian (White/Bold)
# Enforced by 2026 Pro Protocol
amir subtitle video.mp4 -t en fa -r
```

#### 2. Top-Aligned Commentary (Vlog Style)
```bash
# Push subtitles to the TOP of the screen
amir subtitle video.mp4 -t fa -r --alignment 8 --style vlog
```

#### 3. Custom Sizing for High-Res (4K)
```bash
# Larger fonts for high-resolution displays
amir subtitle video.mp4 -t fa -r --font-size 45
```

#### 4. Sentence-Aware Splitting (2 Lines)
```bash
# Allow long sentences to break into two clean lines
amir subtitle video.mp4 -t fa -r --max-lines 2
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

## 🌐 Supported Languages (30 Total)

### Top 25 (YouTube Priority 2026)
| Priority | Code | Language | Native Font | RTL | Notes |
|----------|------|----------|-------------|-----|-------|
| 1 | `zh` | Chinese (Mandarin/Simplified) | SimHei | ❌ | 1.35B speakers, 19.4% internet users |
| 2 | `en` | English | Arial | ❌ | Global lingua franca, 25.9% internet |
| 3 | `es` | Spanish | Arial | ❌ | Latin America + Spain market |
| 4 | `hi` | Hindi | Mangal (Devanagari) | ❌ | Fastest growing YouTube market |
| 5 | `ar` | Arabic (Standard) | Arial | ✅ | Unified across Arab countries |
| 6 | `bn` | Bengali | Noto Sans Bengali | ❌ | Bangladesh + West Bengal focus |
| 7 | `pt` | Portuguese | Arial | ❌ | Brazil's massive YouTube presence |
| 8 | `ru` | Russian | Arial (Cyrillic) | ❌ | Eurasia + Eastern Europe |
| 9 | `ja` | Japanese | MS Gothic | ❌ | High purchasing power, loyal users |
| 10 | `fr` | French | Arial | ❌ | France, Canada, Africa |
| 11 | `ur` | Urdu | B Nazanin (Arabic script) | ✅ | Phonetically close to Hindi |
| 12 | `pa` | Punjabi | Noto Sans Gurmukhi | ❌ | India + Pakistan population |
| 13 | `vi` | Vietnamese | Arial | ❌ | High engagement in entertainment |
| 14 | `tr` | Turkish | Arial | ❌ | Very active social media users |
| 15 | `ko` | Korean | Malgun Gothic (Hangul) | ❌ | K-Culture global trend |
| 16 | `id` | Indonesian | Arial | ❌ | Explosive internet growth |
| 17 | `de` | German | Arial | ❌ | Strong European economy |
| 18 | `fa` | Persian (Dari/Tajik) | B Nazanin | ✅ | High engagement vs. population |
| 19 | `gu` | Gujarati | Noto Sans Gujarati | ❌ | Wealthy Gujarat state audience |
| 20 | `it` | Italian | Arial | ❌ | High-quality European audience |
| 21 | `mr` | Marathi | Mangal (Devanagari) | ❌ | Maharashtra (Mumbai) |
| 22 | `te` | Telugu | Noto Sans Telugu | ❌ | Hyderabad tech hub |
| 23 | `ta` | Tamil | Noto Sans Tamil | ❌ | Language-loyal South India |
| 24 | `th` | Thai | Noto Sans Thai | ❌ | Growing Southeast Asia market |
| 25 | `ha` | Hausa | Arial | ❌ | West Africa video gateway |

### Additional Languages (5)
| Code | Language | Native Font | RTL | Region |
|------|----------|-------------|-----|--------|
| `el` | Greek | Arial | ❌ | Greece, Cyprus |
| `mg` | Malagasy | Arial | ❌ | Madagascar |
| `nl` | Dutch | Arial | ❌ | Netherlands, Belgium |
| `pl` | Polish | Arial | ❌ | Poland |
| `uk` | Ukrainian | Arial (Cyrillic) | ❌ | Ukraine |

**Total Coverage:** 95.1% of global internet users | 60.3% of world population

View complete list: `amir subtitle -l`

## 🔧 How It Works

1. **Transcription**: Uses Faster-Whisper (or MLX-Whisper on Apple Silicon) to generate accurate speech-to-text from video
2. **Smart Caching**: SHA-256 hash-keyed cache (`~/.amir_cache/`) prevents redundant API calls
3. **Translation Pipeline**:
   - **Batch Processing:** 25 lines per call (DeepSeek), 40 lines (Gemini), 20 lines (LiteLLM)
   - **Multi-Format Parser:** Handles numbered, JSON, and plain text responses
   - **Digit Normalization:** Converts Persian/Arabic numerals (`۱۲۳` → `123`)
   - **Quality Threshold:** 80% valid lines required per batch
4. **Quality Validation**:
   - **Character Range Check:** Verifies target language Unicode presence (non-Latin scripts)
   - **Source Comparison:** Ensures translation differs from original (Latin scripts)
   - **Interactive Prompts:** User retry options for incomplete batches (max 3 attempts)
   - **Guarantee:** No rendering until 100% translation or user decline
5. **Resume Capability**: `-c/--continue` flag ingests partial SRT files to recover existing translations
6. **Technical Term Preservation**: Maintains English terms in parentheses for all languages (e.g., "هوش مصنوعی عمومی (AGI)")
7. **Typography Enhancement**: Automatically fixes Persian text (adds proper ZWNJ: می‌کنم, صحبت‌های)
8. **Subtitle Generation**: Creates SRT files with proper timing
9. **Styling**: Converts to ASS format with:
   - Language-appropriate fonts (B Nazanin for Persian, etc.)
   - RTL support for Arabic/Persian/Urdu/Hebrew
   - Resolution-adaptive sizing: `font_size = (height / 1080) * 25`
   - Bilingual layout (primary: bottom white bold, secondary: top gray)
10. **Smart Video Rendering** (optional):
    - **Resolution Detection:** ffprobe extracts width × height
    - **Adaptive Bitrates:** 480p: 1.5M | 720p: 2.5M | 1080p: 4M | 4K: 8M
    - **Hardware Acceleration:** VideoToolbox (Apple Silicon) or libx264 CRF-23 (CPU)
    - **Audio Preservation:** Lossless copy (`-c:a copy`)
    - **Real-time Progress:** FFmpeg pipe with percentage tracking

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
2. Find `SubtitleStyle` class
3. Change size values
4. Delete old ASS files and re-run with `-f` flag

### Progress bar not showing
- Ensure you're using `-r` flag to enable rendering
- Progress shows as: `Encoding: 0%` → `Encoding: 100% ✓`
- If stuck, check FFmpeg is properly installed

## 🛑 Troubleshooting & Best Practices (2026 Edition)

### 1. Persian/Arabic Text Rendering (The "Nuclear Option")
If you see **disjointed or reversed** Persian text (e.g., "م‌ا‌ل‌س" instead of "سلام"), it means there is a conflict between Python's shaping and FFmpeg's internal shaping.

**The Fix:**
- **Do NOT** use `arabic-reshaper` or `python-bidi` if your FFmpeg has `libharfbuzz` enabled (which most modern versions do).
- **Inject Font Path:** FFmpeg in sandboxed environments (like Python subprocesses) often cannot find system fonts. You **MUST** explicitly pass the font directory.
  ```python
  # processor.py logic
  vf_arg = f"ass={sub_path}:fontsdir={'~/Library/Fonts'}"
  ```
- **Font Choice:** With `fontsdir` injection, you can use any user font like `B Nazanin` without installation issues.

### 2. Double Subtitles (Ghosting)
If you see **two sets of subtitles** (one usually white/yellow, one stylized):
- **Cause:** You are playing a video with *burned-in* subtitles (hardcoded) AND the player (VLC/QuickTime) is *also* loading the external `.srt` file.
- **Fix:** Turn off subtitles in your media player (`View > Subtitles > Off`). The video itself already has them permanently.

### 3. Color Theory for Subtitles
- **Professional Standard:**
  - **Target Language (FA):** White (`&H00FFFFFF`) + Black Outline. Maximum readability.
  - **Source Language (EN):** Gray (`&H808080`) + Smaller Size (18 vs 24). Less distraction.
- **Why not Yellow?** Yellow is high-contrast looking "cheap" or "retro". It creates visual fatigue. The White/Gray combo mimics Netflix/YouTube premium styles.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Adding New Languages

1. Add to `LANGUAGE_CONFIG` in the script:
```python
'xx': {'name': 'Language Name', 'font': 'Font Name', 'font_size': 20, 'rtl': False}
```

2. Test with sample video
3. Submit PR with language code documentation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## 🙏 Acknowledgments

- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper) - Fast Whisper implementation
- [DeepSeek](https://www.deepseek.com/) - AI translation API
- [FFmpeg](https://ffmpeg.org/) - Video processing

## 📈 Performance Tips

- **Best Speed**: Use `base` model for quick results
- **Best Quality**: Use `large-v3` model for detailed transcription (default)
- **Smart Caching**: SHA-256 hash-keyed cache prevents redundant work - use `-f` to force refresh
- **Batch Translations**: Optimized batching (DeepSeek: 25 lines, Gemini: 40, LiteLLM: 20)
- **Resume Translations**: Use `-c/--continue` to recover from interruptions and save API costs
- **Multiple Languages**: Specify all targets in one command for parallel processing
- **Video Quality**: Smart bitrate adaptation (480p: 1.5M → 4K: 8M) prevents file bloat
- **Hardware Acceleration**: Automatic VideoToolbox (Apple Silicon) or libx264 CRF-23 (CPU) selection
- **API Token Conservation**: Validation system ensures 100% quality before costly re-runs

## 🛠️ Pro CLI Features (Advanced Control)

### 🎨 Visual Customization
- **`--shadow <int>`**: Controls the drop shadow depth. Default is 0 (Flat). Set to 1-4 for depth.
- **`--outline <int>`**: Thickness of the black border. Default is 2.
- **`--back-color <hex>`**: ASS Hex code for background box.
  - Transparent: `&H00000000` (Default)
  - Semi-Opaque Black: `&H80000000`
- **`--primary-color <hex>`**: Text color.
  - White: `&H00FFFFFF`
  - Yellow: `&H00FFFF00`

### 🧠 AI Inference Tuning
- **`--temperature 0.0-1.0`**: Controls creativity.
  - `0.0`: Deterministic (Best for factual/technical)
  - `0.3`: Balanced (Default for translation)
  - `0.8`: Creative (Poetic)
- **`--initial-prompt "..."`**: Provide context to Whisper.
  - Example: `--initial-prompt "This is a technical tutorial about Kubernetes."`
- **`--openai-fallback`**: If set, automatically switches to OpenAI GPT-4o if DeepSeek fails.

### ⚡ Logic Overrides
- **`--min-duration <float>`**: Ensures subtitles stay on screen for at least X seconds (Default: 1.0s).

## 💡 Tips & Best Practices

- **Best Quality**: Use `-m large` for important content or noisy audio
- **Fast Processing**: Use `-m tiny` or `base` for quick drafts  
- **Multiple Languages**: Always specify all targets in one command (e.g., `-t en fa ar`)
- **Video Quality**: CRF 23 maintains excellent quality with reasonable file size
- **Persian Content**: Script automatically adds proper ZWNJ - no manual editing needed