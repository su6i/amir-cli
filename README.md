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

- **🎬 Smart Video Compression:** Auto-detects hardware (Apple Silicon, NVENC, QSV) and optimizes settings for the best quality/size ratio. Features "AI Learning" to adapt to your preferences over time.
- **🖼️ Advanced Image Processing:** AI-powered upscaling (Real-ESRGAN), document enhancement lab (140 variations), smart stacking (front/back), and professional corner rounding.
- **🤖 AI Powered:** Chat with Gemini/Gemma directly from your terminal and generate code snippets.
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
Amir CLI uses **Python 3** for some helper tasks (like data formatting).
- **No Virtual Environment Needed:** We strictly use Python's **Standard Library** (modules like `os`, `json`, `sys`). You do **NOT** need to install any pip packages or create a venv.
- **System Requirements:**
    - `ffmpeg` (for media tools)
    - `bc` (for calculations)
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
| `amir compress <file/dir>` | Smart video compression. Supports **Batch Mode** (directories) & multiple files. |
| `amir compress stats` | View AI learning statistics & compression history. |
| `amir mp3 <file>` | Extract high-quality MP3 audio from a video file. |
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
| `amir pdf <files> [opts]` | Merge images into A4 PDF. Dual output (HQ+XS). Opts: `-q`, `-r`, `--radius`. |
| `amir watermark <file> [text]` | Add watermark to image (auto-saved or `-o output`). |
| `amir subtitle <file> [opts]` | Generate multi-language subtitles. See [SUBTITLE.md](docs/SUBTITLE.md) for details. |
| `amir info <file>` | Show detailed technical metadata for any file. |

### 🧠 AI & Productivity
| Command | Description |
| :--- | :--- |
| `amir chat "hello"` | Ask the AI assistant a question. |
| `amir code "fix this"` | Request code generation or refactoring. |
| `amir todo add "task"` | Manage a lightweight local to-do list. |
| `amir dashboard` | Show a system status dashboard (CPU, RAM, Space). |

### 🛠 Utilities
| Command | Description |
| :--- | :--- |
| `amir transfer <file>` | Upload file to temporary cloud storage & copy link. |
| `amir qr <content>` | Create QR Code (URL, WiFi, Email, Phone, Text). |
| `amir short <url>` | Shorten a long URL. |
| `amir clip <text/file>` | Smart clipboard: copies text, file content & supports pipes. |
| `amir pass [len]` | Generate a strong, random password. |
| `amir lock <file>` | Encrypt a file (GPG). |
| `amir unlock <file>` | Decrypt a file. |
| `amir clean` | Deep clean system trash and caches (macOS/Linux). |
| `amir speed` | Test internet connection speed. |
| `amir weather [city]` | Check weather (specify city or use default). |


## 🤝 Contributing

Contributions are welcome! Please check the issues page or submit a Pull Request.


