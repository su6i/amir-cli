<div align="center">
  <img src="assets/project_logo.svg" width="350" alt="Amir CLI Logo">
  <h1>Amir CLI 🚀</h1>

  ![Version](https://img.shields.io/badge/Version-1.0.0-blue.svg)
  ![Bash](https://img.shields.io/badge/Shell-Bash/Zsh-black.svg)
  ![License](https://img.shields.io/badge/License-MIT-green.svg)
  [![Technical Docs](https://img.shields.io/badge/Docs-Technical-orange.svg)](docs/TECHNICAL.md)
  [![Apply Tracker](https://img.shields.io/badge/Docs-Apply%20Tracker-green.svg)](docs/APPLY_TRACKER.md)
  [![Apply Tracker FA](https://img.shields.io/badge/Docs-Apply%20Tracker%20🇮🇷-green.svg)](docs/fa/APPLY_TRACKER_FA.md)
  <a href="https://www.linkedin.com/in/su6i/">
    <img src="assets/linkedin_su6i.svg" height="20" alt="LinkedIn">
  </a>
</div>

**Amir CLI** is a powerful, all-in-one terminal assistant designed for **simplicity**, **automation**, and **productivity**. It streamlines your daily workflow by bringing together advanced video compression, system maintenance, AI integration, and file management into a single, cohesive command-line interface.

Built with modularity and ease of use in mind, `amir` works seamlessly across **macOS**, **Linux**, and **Windows (via WSL/Git Bash)**.

## ✨ Features

- **🎬 Smart Video Processing:** Compress, cut (multi-range single-pass), convert formats, picture-in-picture overlay, screen recording, and concat with mixed-codec support (H.264 + HEVC MOV). Auto-detects hardware (Apple Silicon VideoToolbox), handles Apple HEVC `hvc1` correctly, and features **Local Machine Learning** to accurately predict compression size and processing time based on your hardware.
- **🧠 Skill Management:** `amir skill harvest` searches GitHub by stars, fetches READMEs, and synthesizes `.agent/skills/` reference files for AI agents. Covers YouTube automation, TTS (Fish Speech, GPT-SoVITS, XTTS v2), video production, ComfyUI, music generation, and analytics.
- **🖼️ Advanced Image Processing:** AI-powered upscaling (Real-ESRGAN), document enhancement lab (140 variations), smart stacking (front/back), professional corner rounding, and perfect SVG rendering via `librsvg`.
- **🌍 Advanced Subtitle System:** AI-powered multilingual subtitles supporting **32 languages**. Features automatic translation, multi-platform hardware encoding (Mac/Ubuntu) with 1:1 size parity, Whisper Turbo as default, and document export via `--save` (no argument defaults to `pdf`).
- **🤖 AI Powered:** Chat with Gemini/Gemma, generate code, and fetch model lists from 5 LLM providers (Gemini, OpenAI, DeepSeek, Groq, Anthropic).
- **🎓 Apply Tracker:** Full PhD and job application pipeline — SQLite backend, FastAPI web UI, Textual TUI, Gmail sync with one click, bidirectional sort, reject/sent/reply tracking, and experience requirements field.
- **📡 Research & Trends:** Multi-Agent RAG pipeline that searches YouTube, GitHub, arXiv, Reddit, ProductHunt, and Indie Hackers. Find trending content, filter by language/region, and generate cross-source ideas.
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
| **`GEMINI_API_KEY`** | Enables the free tier of `amir router` (gemini/gemma), smart summaries, and intelligent help responses. | [Google AI Studio](https://aistudio.google.com/app/apikey) |
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
| `amir download <URL> [opts]` (alias: `amir dl`) | **Universal Downloader**: YouTube, Instagram (photos/carousels/reels), TikTok, Twitter/X, Vimeo and 1000+ sites. Instagram photo posts auto-detected and downloaded via gallery-dl (auto-installed). Key flags: `--resolution <h>`, `--formats`, `--subtitle`, `--yt-subs`, `--translate`, `--extreme`, `--get-link`, `--browser`, `--cookies`, `--normalize`, `--po-token`, `--yt-dlp-args`. Instagram images: `--format jpg\|png\|webp` (default: jpg). |
| `amir video <file/dir> [--gpu|--cpu]` | Advanced video processing (compress, cut, batch). Supports `extreme` (max compression profile), `--fps <N>` (e.g., 10fps), and `--split <MB>` (split encoded output to chunks). `--gpu` for hardware acceleration (default on Apple Silicon), `--cpu` for better compression ratio. |
| `amir video convert <file> [--to fmt] [-o out] [--cpu]` | Convert video container format (MOV→MP4, MKV, WEBM, AVI). Defaults to stream-copy (instant, no quality loss). Handles Apple HEVC (`hvc1`) correctly — no tag mangling. `--cpu` re-encodes with libx264 CRF 23 — sharper text and slides, smaller output. |
| `amir video pip <main> --pip <file> [--start T] [--end T] [--pos tl\|tr\|bl\|br\|X:Y] [--size %] ...` | Picture-in-picture overlay: place one or more videos on a main video at specific time windows and positions. Multiple `--pip` flags supported. Audio from each pip is mixed into the output during its active window. |
| `amir video concat <files...> [-o out.mp4]` | Concatenate multiple videos in the exact order provided. Uses `filter_complex` per-input decoding — handles mixed codecs (H.264 MP4 + HEVC MOV) without freeze artifacts. Creates `<first>_merged.mp4` when `-o` is omitted. Alias: `amir video merge ...`. |
| `amir video cut <file> [opts]` | Cut video segments without re-encoding (instant) or with rendering. Supports `-d/--delete <start> <end>` (repeatable — multiple ranges removed in a **single pass**) and `-x/--extract <start> <end>` to keep only that range. Multiple `-d` flags: `amir video cut v.mp4 -d 00:01:10 00:01:22 -d 00:08:45 00:09:02 -o out.mp4`. |
| `amir video split <file> <mb>` | Split an existing video into approximate MB chunks (keyframe-bound, non re-encode). |
| `amir split <file> <mb>` | Global splitter for both audio and video files (approximate MB chunks, no re-encode). |
| `amir video tiktok <url> [opts]` | TikTok-optimized wrapper around `video download` with the same subtitle/translate pipeline flags. |
| `amir video stats` | View AI learning statistics & compression history. |
| `amir audio extract <video(s)> [bitrate] [--split <MB>]` | Extract high-quality MP3 audio from one or more video files, optionally split into chunks. Batch: `amir audio extract *.mp4 192`. |
| `amir audio convert <file(s)> [mp3\|wav\|ogg\|m4a\|flac]` | Convert audio format. Batch: `amir audio convert *.wav mp3`. |
| `amir audio cut <file(s)> [-s start] [-e end]` | Trim or delete segments. `-s`/`-e`: keep range (stream copy, instant). `-d START END`: delete a range and keep the rest. Multiple `-d` flags for multi-delete in one pass. `-x START END`: extract a named clip. Batch: `amir audio cut *.mp3 -s 00:01:00 -e 00:05:00`. |
| `amir audio normalize <file(s)> [--target -16] [--peak -1]` | Two-pass EBU R128 loudness normalize. Default target `-16 LUFS` (YouTube standard). Use `--target -14` for Spotify, `--target -23` for broadcast. Batch: `amir audio normalize *.mp3`. |
| `amir audio fade <file(s)> [--in N] [--out N]` | Fade-in and/or fade-out. Duration in seconds. Fade-out start is computed from file length automatically. Batch: `amir audio fade *.mp3 --in 2 --out 4`. |
| `amir audio trim-silence <file(s)> [--threshold -40] [--pad 0.3]` | Remove leading and trailing silence. `--threshold` sets the dB cutoff (higher = more aggressive). `--pad` keeps a short margin at each edge. Batch: `amir audio trim-silence *.mp3`. |
| `amir audio split <file(s)> <mb>` | Split audio into approximate MB chunks. Batch: `amir audio split *.mp3 10`. |
| `amir audio concat <files...> [-o output]` | Join multiple audio files into one. |
| `amir audio youtube <url> [format] [bitrate] [--split <MB>]` | Download audio from YouTube (mp3/wav/ogg) and optionally split the final output into chunks. |
| `amir audio to-video <audio> [-i image] [-o output] [--waveform]` | Create a video from an audio file and a static (or waveform-animated) background image. |
| `amir audio transcribe <file> [--source fa\|en\|...] [subtitle-opts]` | Transcribe audio via Whisper (faster-whisper VAD + MLX fallback). Saves both `.srt` (with timestamps) and `.txt` (plain text) alongside the source file. All `amir subtitle` flags accepted. |
| `amir img upscale <file> [scale] [model]` | AI-Upscale or quality enhancement (1x mode). |
| `amir img lab <file> [-s scale] [-m model]` | Generate 60/420 enhancement variations for testing. |
| `amir img stack <files> [opts]` | Combine images vertically (A4/B5 presets). |
| `amir img rotate <file...> <angle|--smart>` | Rotate image(s) by degrees or auto-straighten (deskew). Supports batch processing. |
| `amir img convert <svg> [fmt] [size]` | Convert SVG/Image to PNG/JPG. Uses **librsvg** for perfect font/geometry rendering. Supports **Animated SVGs**. |
| `amir img resize <file> <size> [circle]` | Resize. Optional `circle` crop (transparent corners). |
| `amir img crop <file> [size] [--smart]` | Smart Content-Aware Crop (Auto-detect subject) or Manual Crop. |
| `amir img pad <file> <size> [color]` | Resize & Fill with Color (Contain). |
| `amir img round <file> [radius] [fmt]` | Round image corners (PNG/JPG). |
| `amir img compress <file(s)> [opts]` | Compress images to target size (default 300KB). Binary-search quality then auto-resize. `--target KB`, `--uniform` (same scale for all files in batch), `--grayscale` (ideal for official documents/scans), `--overwrite`, `-o dir`. |
| `amir img extend <file> [opts]` | Extend image borders (custom/auto color). |
| `amir img <file> <size> [g]` | Legacy mode (detects resize vs crop). |
| `amir pdf [files] [opts]` | **Multi-Engine PDF Generator**: Render Markdown/Text/Images/LaTeX to PDF. Supports piping (e.g., `amir clip | amir pdf`), Puppeteer (Default), WeasyPrint, PIL (Robust Fallback), and **xelatex** for `.tex` files. Features: High-fidelity Persian RTL (Vazirmatn), auto-pagination, ExFAT compatibility, `--free-size` (`-f`) for continuous/custom dimensions, `--page-width/--page-height` (Puppeteer, pixels) for manual page sizing, `--theme carousel` (square 1080px LinkedIn slides, `##` = one slide), `--theme guide` (clean professional A4 long-form document — coloured headings, boxed blockquotes, clickable links; works LTR + RTL), and **`--force-rtl`** (alias `--rtl`) to force the whole document right-to-left. For LaTeX, custom `.sty` and `.cls` styles can be placed in `lib/latex/` to automatically include them. Common widths: 1200, 1440, 1600, 1800, 2000, 2480. |
| `amir pdf linkedin-post <folder> [carousel \| guide [fr en fa tri]]` | **Trilingual LinkedIn post builder (WeasyPrint)**: from `<folder>/guide.{fr,en,fa}.md` + `<folder>/post.yml` it renders the three guides, `guide.trilingue.pdf`, and `carrousel.linkedin.pdf`. Subcommands rebuild only what changed: `carousel`, or `guide <fr en fa tri>` (one or several targets, e.g. `guide fa` rebuilds just the Persian guide; `tri` = the merged trilingual PDF). Fonts are vendored in `lib/fonts/` and a restricted `fontconfig` keeps Persian/RTL correct on macOS. See `docs/TRILINGUAL_POSTS.md`. Example: `amir pdf linkedin-post posts/04_my_post`. |
| `amir watermark <file> [text]` | Add watermark to image (auto-saved or `-o output`). |
| `amir subtitle <file/URL> [options]` | **AI-Powered Multilingual Subtitles**: Transcribe, translate (32 languages), and render. Source is auto-detected by default; practical default layout is source-top + Persian-bottom (`--sub auto fa`). Key flags: `--yt-subs` (force YouTube internal subs), `--ass-input <srt/ass>` (render from manual file; `.srt` files are automatically styled with Vazirmatn), `--resolution <h>` and `--quality <0-100>` (final render controls), `--style channel_brand_blue|shorts_brand_blue|news_guest_blue`, `--subtitle-banner-image/--subtitle-banner-color`, `--subtitle-logo [--subtitle-logo-animated]`, `--guest-tag "start,duration,name,title[,pos]"`, `--brand-kit <logo> [--brand-kit-shorts]`, `--save` (default export: `pdf`), and `--no-render` (SRT only). Default render height follows input video height when not provided. See [SUBTITLE.md](docs/SUBTITLE.md). |
| `amir video record [--list] [--screen N] [--audio N] [--fps N] [-o FILE]` | Record screen to MP4 using macOS AVFoundation. `--list` shows available screens/audio devices. Ctrl+C to stop. Alias: `amir video rec`. |
| `amir info <file>` | Show detailed technical metadata for any file. |

### 🧠 Skill Management

| Command | Description |
| :--- | :--- |
| `amir skill search <query> [--min-stars N]` | Search GitHub for repos matching query, ranked by stars — discover tools worth learning. |
| `amir skill harvest <query> [--pick N] [-o file]` | Search GitHub → fetch top READMEs → synthesize a `.agent/skills/` reference file for AI agents. |
| `amir skill list [--grep PATTERN]` | List all existing skill files in `.agent/skills/` with descriptions. |
| `amir skill show <name>` | Display contents of a skill file. |

### 📡 Research & Trends

Bridge to the [Research Toolkit](https://github.com/su6i/research-toolkit) — a Multi-Agent RAG pipeline across 6 platforms.

| Command | Description |
| :--- | :--- |
| `amir trend` | Most-viewed videos globally (YouTube trending, no keyword needed) |
| `amir trend "AI tools"` | Search YouTube for a topic, sorted by views |
| `amir trend --region IR` | Trending in Iran |
| `amir trend "موزیک" --lang fa` | Filter results in Persian language |
| `amir trend "LLM" --source github --metric stars` | Top GitHub repos by stars |
| `amir trend "deep learning" --source arxiv` | Academic papers (arXiv) |
| `amir trend "devops" --source reddit --metric comments` | Reddit posts by comments |
| `amir trend "SaaS" --ideas` | Generate AI-powered ideas from collected data |
| `amir trend "ML" --semantic` | Semantic (multilingual) vector search |
| `amir research` | Alias for `amir trend` |

**All options (Tab-complete supported):**

| Option | Values | Default |
| :--- | :--- | :--- |
| `--source` | `youtube` `github` `arxiv` `reddit` `producthunt` `indiehackers` | `youtube` |
| `--lang` | `fa` `en` `de` `ar` `zh` `es` `fr` `ru` `ja` `ko` `tr` `pt` `hi` | any |
| `--region` | `IR` `US` `GB` `DE` `FR` `JP` `KR` `AU` `CA` `IN` ... | global |
| `--metric` | `views` `likes` `stars` `citations` `comments` `published_at` | `views` |
| `--limit` | number | `10` |
| `--semantic` | flag | keyword search |
| `--ideas` | flag | — |
| `--count` | number (with `--ideas`) | `10` |

**Setup:** Set `RESEARCH_TOOLKIT_DIR` in your `.env` if the toolkit is not at `~/@-github/research_toolkit`:
```bash
export RESEARCH_TOOLKIT_DIR=/path/to/research_toolkit
```

### 🧠 AI & Productivity
| Command | Description |
| :--- | :--- |
| `amir router "<prompt>"` | **AI gateway** — routes to gemini/gemma (free), deepseek, minimax, grok. Add `--model M` to pick a model, `--session S` for conversation memory. Replaces `amir chat`/`amir code`. |
| `amir router audit` | Show the cost/usage ledger (provider-echoed proof of which model actually ran). |
| `amir router models <provider> [-e fmt]` | Fetch model lists from LLM providers (gemini, openai, deepseek, groq, anthropic). Export to PDF/MD/JPG. |
| `amir todo "task"` | Add a task to the local to-do list. |
| `amir todo list` | Show all pending tasks. |
| `amir todo done <n>` | Remove task number `<n>` from the list. |
| `amir todo clear` | Clear all tasks. |
| `amir dashboard` | Show a system status dashboard (CPU, RAM, Space). |

### 🎓 Apply Tracker

Full PhD and job application tracker with SQLite backend, web UI, and Gmail sync. See [full docs](docs/APPLY_TRACKER.md).

| Command | Description |
| :--- | :--- |
| `amir apply` | Urgent deadline alerts + help |
| `amir apply phd` | Pending PhD positions sorted by urgency |
| `amir apply phd sent` | List sent PhD applications |
| `amir apply phd reject <id>` | Mark a position as rejected |
| `amir apply phd draft <id>` | Generate email draft with DeepSeek AI |
| `amir apply job` | Pending job positions |
| `amir apply job reject <id>` | Reject a job position |
| `amir apply web [port]` | Launch web UI — auto-opens browser, status chip filters (À examiner/Draft prêt/Envoyé/Refusé), rejected hidden by default |
| `amir apply tui [phd\|job]` | Terminal UI — arrow navigation, `m`=sent, `x`=reject, `s`=sort, `/`=filter |
| `amir apply stats` | Bar chart statistics by status and country |
| `amir apply sync` | Fetch AMIR-SYNC Gmail drafts via OAuth → create positions + trash drafts automatically |

**Gmail Sync setup** (one-time): see [APPLY_TRACKER.md → Gmail Sync](docs/APPLY_TRACKER.md#gmail-sync----راه‌اندازی).

### 🛠 Utilities
| Command | Description |
| :--- | :--- |
| `amir transfer <file>` | Upload file to temporary cloud storage & copy link. |
| `amir qr <content>` | Create QR Code (URL, WiFi, Email, Phone, Text). |
| `amir short <url>` | Shorten a long URL. |
| `amir clip [input]` | **Piped Clipboard**: Copies text/files to clipboard, or outputs clipboard content to stdout when piped (e.g., `amir clip | amir pdf`). Single-word arg naming a file that doesn't exist yet (e.g. `amir clip notes.md`) saves the current clipboard content into that file instead. |
| `amir pass [len]` | Generate a strong, random password. |
| `amir lock <file>` | Encrypt a file (GPG). |
| `amir unlock <file>` | Decrypt a file. |
| `amir clean` | Interactive cleanup menu — toggle items on/off with Space/numbers, navigate with ↑↓, confirm with Enter. Covers: Trash, User Caches, System Logs, VS Code workspaceStorage, macOS Aerials Screensaver, Claude Desktop VM. |
| `amir speed` | Test internet connection speed. |
| `amir weather [city]` | Check weather (specify city or use default). |
| `amir keyboard [fr\|en\|fa\|auto]` | Show keyboard layout for Apple Compact keyboard. Flags: `--opt` (Option layer), `--shift` (Shift layer), `--normal`, `--find <char>` (locate any character), `--auto` (detect active OS layout). Alias: `amir kb`. |
| `amir init-project [dir]` | Scaffold a project: links `.agent/constitution` to one central clone (symlink, not a submodule — override its location with `AGENT_CONSTITUTION_DIR`, its clone URL with `AGENT_CONSTITUTION_URL`), standard dirs (`src/ tests/ docs/ assets/` with `.gitkeep`), curated `.gitignore` (enforces `.storage/`/`.env`/`.agent/constitution`), starter `CLAUDE.md`/`README.md`/`.env.example`, and — for Python/unspecified stacks — `uv init` (`pyproject.toml` + pinned interpreter). `SESSION.md` is created in the project's vault workspace (`~/.local/share/agent-projects/<slug>/workspace/`, never in the repo); tasks go ONLY to the central `_memory/TODO.md` under a `## <project>` section — no per-project TODO is created (rules 035/040/045/050). The generated `CLAUDE.md` points storage at the vault `data/` dir and contains no absolute personal paths. Installs the constitution `pre-commit`/`pre-merge-commit`/`commit-msg` hooks (blocks `main` commits + enforces the docs checklist, the privacy and skill-version gates — on merges too — + no AI co-authorship) and refuses to nest inside an existing git repo (override: `AMIR_ALLOW_NESTED=1`). Safe on existing repos: stages **only the files it created** (never whole directories, so your WIP stays unstaged), asks before Python-scaffolding a repo with no stack markers (skips silently when non-interactive), and refuses to run on a legacy submodule checkout of `.agent/constitution` (prints the migration steps instead). |
| `amir sync-constitution [dir]` | Sync `.agent/` rules and skills from the `agent-constitution` repo into an existing project. Preserves project-specific files; migrates legacy `.agents/`/`.cursor/` directories automatically. Override source with `AGENT_CONSTITUTION_PATH`. |
| `amir update-projects [base-dir]` | Propagate across **all** projects under `base-dir` (default `$AMIR_PROJECTS_DIR` or `~/@-github`) that link the constitution — either pattern: refreshes the symlink (pulling the one central clone once, up front) for current projects, or updates the git submodule in place for legacy ones — + (re)installs the `pre-commit`/`pre-merge-commit`/`commit-msg` hooks. Idempotent, non-destructive. Flags: `--dry-run`, `--no-hook`, `--no-link` (alias: `--no-submodule`), `--exclude "a b"`. Excludes `amir-cli`/`agent-constitution` by default. |


## 🤝 Contributing

Contributions are welcome! Please check the issues page or submit a Pull Request.


