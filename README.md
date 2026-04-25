<div align="center">
  <img src="assets/project_logo.svg" width="350" alt="Amir CLI Logo">
  <h1>Amir CLI 🚀</h1>

  ![Version](https://img.shields.io/badge/Version-1.0.0-blue.svg)
  ![Bash](https://img.shields.io/badge/Shell-Bash/Zsh-black.svg)
  ![License](https://img.shields.io/badge/License-MIT-green.svg)
  [![Technical Docs](https://img.shields.io/badge/Docs-Technical-orange.svg)](docs/TECHNICAL.md)
  <a href="https://www.linkedin.com/in/su6i/">
    <img src="assets/linkedin_su6i.svg" height="20" alt="LinkedIn">
  </a>
</div>

**Amir CLI** is a powerful, all-in-one terminal assistant designed for **simplicity**, **automation**, and **productivity**. It streamlines your daily workflow by bringing together advanced video compression, system maintenance, AI integration, and file management into a single, cohesive command-line interface.

Built with modularity and ease of use in mind, `amir` works seamlessly across **macOS**, **Linux**, and **Windows (via WSL/Git Bash)**.

## ✨ Features

- **🎬 Smart Video Compression:** Auto-detects hardware (Apple Silicon, NVENC, QSV) and optimizes settings for the best quality/size ratio. Features `--gpu`/`--cpu` encoding toggle, `extreme` profile for maximum reduction, custom frame rate via `--fps`, chunking via `--split <MB>`, real-time progress bar with ETA, output size validation, and "AI Learning" to adapt over time.
- **🖼️ Advanced Image Processing:** AI-powered upscaling (Real-ESRGAN), document enhancement lab (140 variations), smart stacking (front/back), and professional corner rounding.
- **🌍 Advanced Subtitle System:** AI-powered multilingual subtitles supporting **32 languages**. Features automatic translation, multi-platform hardware encoding (Mac/Ubuntu) with 1:1 size parity, Whisper Turbo as default, and document export via `--save` (no argument defaults to `pdf`).
- **🤖 AI Powered:** Chat with Gemini/Gemma, generate code, and fetch model lists from 5 LLM providers (Gemini, OpenAI, DeepSeek, Groq, Anthropic).
- **🛠️ System Utilities:** One-command system cleanup, password generation, file locking/unlocking, and QR code generation.
- **☁️ File Transfer:** Instantly upload files to temporary hosting services and get a shareable link.
- **⚡ Super Fast:** Written in optimized Bash/Zsh with minimal overhead.

## 📦 Installation

Installing Amir CLI is fully automated. Just run the installer:

```bash
# 1. Download or clone this repository
git clone https://github.com/su6i/amir-cli.git
cd amir-cli

# 2. Run the automated installer
chmod +x install.sh
./install.sh
```

The installer will:
1. Link the `amir` executable to your system path.
2. Check for dependencies (FFmpeg, etc.) and offer to install them automatically.
3. Set up command auto-completion for Zsh.

### Dependencies & Python Note 🐍
Amir CLI uses **Python 3** for helper tasks (like data formatting and subtitle processing).

- **Zero-setup philosophy:** The installer (`install.sh`) automatically creates a unified Python virtual environment at the root `./.venv`. No manual virtualenv management is required.
- **System Requirements:**
  - `python3` (3.8+)
  - `ffmpeg` (for media tools)
  - `bc` (for calculations)
  - `qrencode`, `uv` and other system tools (the installer attempts to install them automatically where possible)
    
- **uv-first execution:** Where possible, `amir` and its subcommands use `uv` to manage and run Python dependencies (`uv run`).
- **ExFAT & Storage Robustness:** `amir` automatically handles storage on ExFAT drives (like SanDisk) by bypassing file-locking limitations and redirecting temporary data to external volumes when internal space is low.
 
If the installer cannot provision a private or git-hosted package referenced in `requirements.txt`, it will notify you with clear remediation steps.
### 3. Configuration & Installation
Simply run the installer to set up dependencies and API keys in one go:

```bash
chmod +x install.sh
./install.sh
```

During installation, you will be asked to provide the following API key for AI features:

| Key | Purpose (Why do I need this?) | Get it here |
| :--- | :--- | :--- |
| **`GEMINI_API_KEY`** | Enables the `amir chat` command, smart summaries, and intelligent help responses. | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| **`DEEPSEEK_API_KEY`** | Powers the subtitle translation system for 32 languages. Optional: fallback to Gemini if not set. | [DeepSeek Platform](https://platform.deepseek.com/) |
| **`OPENAI_API_KEY`** | For `llm-lists openai` command (optional). | [OpenAI Platform](https://platform.openai.com/api-keys) |
| **`GROQ_API_KEY`** | For `llm-lists groq` command (optional). | [Groq Console](https://console.groq.com/) |
| **`ANTHROPIC_API_KEY`** | For `llm-lists anthropic` command (optional). | [Anthropic Console](https://console.anthropic.com/) |


## ⚙️ Configuration

Amir CLI uses a centralized configuration file located at `~/.amir/config.yaml`. This file is automatically created on first run with sensible defaults, but you can customize it to match your preferences.

**Example Configuration:**
```yaml
pdf:
  radius: 10          # Corner radius for PDF generation
  rotate: 0           # Default rotation angle

compress:
  resolution: 720     # Target video height (480, 720, 1080)
  quality: 60         # Compression quality (0-100)

mp3:
  bitrate: 320        # Audio bitrate in kbps

img:
  default_size: 1080  # Default image resize target
  upscale_model: ultrasharp 
  upscale_scale: 4

qr:
  size: 10            # QR code module size

pass:
  length: 16          # Default password length

weather:
  default_city: Montpellier

todo:
  file: ~/.amir/todo_list.txt

short:
  provider: is.gd     # URL shortener (is.gd, tinyurl.com, da.gd)
```

All commands respect these defaults unless overridden by command-line arguments.


### 4. Other commands

Run `amir help` or just `amir` to see the available commands. You can also rename the executable to whatever you prefer (e.g., `assist`, `do`) to match your workflow.

### 🎬 Multimedia
| Command | Description |
| :--- | :--- |
| `amir video <URL> [opts]` | **Unified Download + Process**: Download from YouTube & 1000+ sites with smart reuse (existing matching downloads are reused to avoid `_2/_3` duplicates). Key flags: `--subtitle en fa` (Whisper AI), `--yt-subs --translate -t en fa` (platform subs → LLM translate), `--sub-only` (SRT only), `--only-subs`, `--formats` (list formats), `--resolution <h>` (explicit download height), `--extreme` (auto-min practical resolution), `--keep-thumb`, `--cookies`. |
| `amir video <file/dir> [--gpu|--cpu]` | Advanced video processing (compress, cut, batch). Supports `extreme` (max compression profile), `--fps <N>` (e.g., 10fps), and `--split <MB>` (split encoded output to chunks). `--gpu` for hardware acceleration (default on Apple Silicon), `--cpu` for better compression ratio. |
| `amir video concat <files...> [-o out.mp4]` | Concatenate multiple videos in the exact order provided. Uses safe re-encode for compatibility and creates `<first>_merged.mp4` when `-o` is omitted. Alias: `amir video merge ...`. |
| `amir video cut <file> [opts]` | Cut video segments without re-encoding (instant) or with rendering. Supports `-d/--delete <start> <end>` to remove a middle range and auto-stitch, and `-x/--extract <start> <end>` to keep only that range (default output name: `_cut_<start>_<end>`). |
| `amir video split <file> <mb>` | Split an existing video into approximate MB chunks (keyframe-bound, non re-encode). |
| `amir split <file> <mb>` | Global splitter for both audio and video files (approximate MB chunks, no re-encode). |
| `amir video tiktok <url> [opts]` | TikTok-optimized wrapper around `video download` with the same subtitle/translate pipeline flags. |
| `amir video stats` | View AI learning statistics & compression history. |
| `amir mp3 <file> [bitrate] [--split <MB>]` | Extract high-quality MP3 audio from a video file and optionally split the output into chunks. |
| `amir audio youtube <url> [format] [bitrate] [--split <MB>]` | Download audio from YouTube (mp3/wav/ogg) and optionally split the final output into chunks. |
| `amir img upscale <file> [scale] [model]` | AI-Upscale or quality enhancement (1x mode). |
| `amir img lab <file> [-s scale] [-m model]` | Generate 60/420 enhancement variations for testing. |
| `amir img stack <files> [opts]` | Combine images vertically (A4/B5 presets + deskew). |
| `amir img rotate <file> <angle>` | Rotate image by degrees. |
| `amir img convert <svg> [fmt] [size]` | Convert SVG/Image to PNG/JPG. Supports **Animated SVGs**. |
| `amir img resize <file> <size> [circle]` | Resize. Optional `circle` crop (transparent corners). |
| `amir img crop <file> [size] [--smart]` | Smart Content-Aware Crop (Auto-detect subject) or Manual Crop. |
| `amir img pad <file> <size> [color]` | Resize & Fill with Color (Contain). |
| `amir img round <file> [radius] [fmt]` | Round image corners (PNG/JPG). |
| `amir img extend <file> [opts]` | Extend image borders (custom/auto color). |
| `amir img deskew <file> [output]` | Auto-straighten scanned documents. |
| `amir img <file> <size> [g]` | Legacy mode (detects resize vs crop). |
| `amir pdf [files] [opts]` | **Multi-Engine A4 PDF Generator**: Render Markdown/Text/Images to PDF. Supports piping (e.g., `amir clip | amir pdf`), Puppeteer (Default), WeasyPrint, PIL (Robust Fallback). Features: High-fidelity Persian RTL (B Nazanin), auto-pagination, ExFAT compatibility, and `--free-size` (`-f`) for continuous/custom dimensions. |
| `amir watermark <file> [text]` | Add watermark to image (auto-saved or `-o output`). |
| `amir subtitle <file/URL> [options]` | **AI-Powered Multilingual Subtitles**: Transcribe, translate (32 languages), and render. Source is auto-detected by default; practical default layout is source-top + Persian-bottom (`--sub auto fa`). Key flags: `--resolution <h>` and `--quality <0-100>` (final render controls), `--save` (default export: `pdf`), `--save txt pdf` (explicit export formats), `-l 120` (test first 120 sec), `--no-render` (SRT only). Default render height follows input video height when not provided. See [SUBTITLE.md](docs/SUBTITLE.md). |
| `amir info <file>` | Show detailed technical metadata for any file. |

### 🧠 AI & Productivity
| Command | Description |
| :--- | :--- |
| `amir chat "hello"` | Ask the AI assistant a question. |
| `amir code "fix this"` | Request code generation or refactoring. |
| `amir llm-lists <provider> [-e fmt]` | **NEW:** Fetch model lists from LLM providers (gemini, openai, deepseek, groq, anthropic). Export to PDF/MD/JPG. |
| `amir todo add "task"` | Manage a lightweight local to-do list. |
| `amir dashboard` | Show a system status dashboard (CPU, RAM, Space). |

### 🛠 Utilities
| Command | Description |
| :--- | :--- |
| `amir transfer <file>` | Upload file to temporary cloud storage & copy link. |
| `amir qr <content>` | Create QR Code (URL, WiFi, Email, Phone, Text). |
| `amir short <url>` | Shorten a long URL. |
| `amir clip [input]` | **Piped Clipboard**: Copies text/files to clipboard, or outputs clipboard content to stdout when piped (e.g., `amir clip | amir pdf`). |
| `amir pass [len]` | Generate a strong, random password. |
| `amir lock <file>` | Encrypt a file (GPG). |
| `amir unlock <file>` | Decrypt a file. |
| `amir clean` | Deep clean system trash and caches (macOS/Linux). |
| `amir speed` | Test internet connection speed. |
| `amir weather [city]` | Check weather (specify city or use default). |


## 🤝 Contributing

Contributions are welcome! Please check the issues page or submit a Pull Request.


