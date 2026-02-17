# 🏗 Technical Documentation & Architecture

[← Back to README](../README.md)

This document provides a deep dive into the internal structure, logic, and design patterns of **Amir CLI**. It is intended for advanced users, contributors, and those who want to extend the tool.

---

## 📂 Project Structure

```bash
amir-cli/
├── amir                  # The main executable (Bash script entry point)
├── install.sh            # Automated installer (symlinks & dependencies)
├── completions/
│   └── _amir             # Zsh autocompletion definitions
├── lib/
│   ├── amir_lib.sh       # Core libraries (colors, helpers, error handling)
│   ├── python/           # Python helper scripts (standard library ONLY)
│   └── commands/         # Individual subcommand scripts
│       ├── img.sh        # Image processing logic
│       ├── mp3.sh        # Audio extraction
│       ├── qr.sh         # QR code generation
│       └── ...
└── docs/
    └── TECHNICAL.md      # This file
```

---

## 🧠 Core Logic & Design

### 1. Entry Point (`amir`)
The `amir` script is the brain of the operation. It performs the following steps on every run:
1.  **Symlink Resolution:** It robustly resolves its own physical location, even if invoked via a symlink (e.g., from `/usr/local/bin/amir`). This ensures relative paths to `lib/` always work.
2.  **Environment Setup:** Sources `lib/amir_lib.sh` to load global variables (like `LIB_DIR`, `py_script`) and helper functions.
3.  **Command Routing:**
    - It checks the first argument (`$1`) to determine the requested command.
    - It looks for a corresponding script in `lib/commands/$1.sh`.
    - If found, it sources that script and calls the `run_$1` function (dashing naming convention: `run_img`, `run_qr`).

### 2. Dependency Management
To ensure maximum portability and zero setup friction:
- **No Pip/Venv:** We deliberately avoid using `pip` or virtual environments.
- **Python Standard Library:** Any Python logic (in `lib/python/`) uses **only** the standard library (`json`, `os`, `sys`, `urllib`, etc.). This guarantees the CLI runs on any machine with Python 3 installed.
- **External Tools:** We rely on robust system binaries like `ffmpeg` (media), `magick` (images), and `bc` (math), which the installer checks for.

### 3. Zsh Autocompletion
The completion script (`completions/_amir`) is a sophisticated Zsh function that:
- Dynamically handles subcommands.
- Provides context-aware suggestions (e.g., listing image sizes for `img resize` or gravity options for `img crop`).
- Is properly registered to `fpath` by the installer.

---

## 🛠 Extending Amir CLI

Adding a new command is designed to be trivial.

### Step 1: Create the Script
Create a new file in `lib/commands/mycmd.sh`.

### Step 2: Define the Function
Inside the file, define a function named `run_mycmd`.

```bash
run_mycmd() {
    echo "This is my new custom command!"
    echo "Arguments passed: $@"
}
```

### Step 3: Usage
No registration needed! Just run:
```bash
amir mycmd "hello world"
```
The router automatically detects the file `mycmd.sh` and executes `run_mycmd`.

### Step 4: Autocompletion (Optional)
To get tab-completion for your new command:
1. Open `completions/_amir`.
2. Add your command to the logic (look for the `_arguments` or `case` block).
3. Restart your shell.

### Real-World Example: `qr` Command

Here is a simplified look at how the `amir qr` command is implemented in `lib/commands/qr.sh`:

```bash
run_qr() {
    local input="$1"
    
    # 1. Validation
    if [[ -z "$input" ]]; then 
        echo "❌ Error: Input required."
        return 1
    fi

    # 2. Logic (Detect protocol)
    if [[ "$input" =~ ^[0-9+]+$ ]]; then
        input="tel:$input"
    elif [[ "$input" == *@*.* ]]; then
        input="mailto:$input"
    fi

    # 3. Execution (Use external tool)
    echo "📌 Generating QR for: $input"
    qrencode -t ANSIUTF8 "$input"
}
```
This shows how you can mix shell logic, argument parsing (`$1`), and external tools (`qrencode`) seamlessly.

### 4. Autocompletion (Zsh)
To give users helpful hints, we need to update `completions/_amir` in **two places**.

#### A. Register the Command
First, add your command to the main list (around line 20):

```zsh
    if (( CURRENT == 2 )); then
        local -a commands
        commands=(
            # ... existing commands ...
            'qr:Create smart QR Code'  # <--- Add this line
        )
        _describe -t commands 'commands' commands
```

#### B. Define Logic
Then, add the argument handling logic to the main `case` statement:

```zsh
    case "$words[2]" in
        qr)
            case $((CURRENT)) in
                3) _message "Enter URL, phone number, email or text" ;;
                4) _message "Output filename (optional)" ;;
            esac
            ;;
```

### 5. Usage
Now you can run:
```bash
# Generate in terminal
amir qr "https://google.com"

# Save as image
amir qr "+989123456789" contact.png
```

---

## 🔍 Specific Command Logics

### `img` (Image Processing)
- **Architecture:** Split into sub-functions `do_resize`, `do_crop`, and `do_pad`.
- **Tool Abstraction:** It attempts to use `magick` (ImageMagick v7) first. If not found, it falls back to `convert` (IM v6). On macOS, it has a limited fallback to `sips` (Apple's native image tool) for basic operations.
- **Smart Legacy Mode:** If no subcommand (`resize`/`crop`) is given, it inspects arguments to guess the user's intent (e.g., presence of gravity code = crop).
- **Extend Subcommand:** Uses `magick` -splice capabilities to add borders. Supports auto-average background color calculating and independent per-side coloring.
- **Smart File Naming**: Output filenames automatically append used options (e.g., `_bg-blue_circle`) to prevent accidental overwrites. Includes interactive overwrite protection if a collision occurs.

#### 🎨 Image Corner Rounding (`round`)
- **Format Support**: `amir img round` now supports both PNG (for transparency) and JPG (flattened against a white background).
- **macOS Compatibility**: Uses shell-safe `tr` translations instead of Bash 4+ `${var^^}` syntax to maintain full compatibility with macOS default Bash 3.2.
- **Robust Masking (CopyOpacity Strategy)**: Uses `-compose CopyOpacity` to strictly separate alpha channel manipulation from color channels. This prevents the "white page" bug where DstIn composition could replace image color with mask color on certain ImageMagick versions.

#### 🧠 Smart Crop (Content-Aware)
- **Algorithm:** Uses `lib/python/smart_crop.py` with OpenCV.
- **Pipeline:**
  1. **Preprocessing:** Gaussian Blur + Canny Edge Detection.
  2. **Morphology:** Dilates edges to connect disjoint parts (e.g., text lines in a receipt) into a single "blob".
  3. **Detection:** Finds the largest external contour and computes its bounding box.
  4. **Fallback:** If no distinct subject is found, it returns the original image to prevent accidental data loss.
- **Integration:** Available in `amir img crop --smart` and `amir pdf --smart` (auto-crops before merging).

#### 🎥 Static SVG Baking (Animated SVGs)
When converting a `.svg` file that contains CSS animations (`@keyframes`), Amir CLI uses a custom Python script (`lib/python/svg_bake.py`) instead of a headless browser.
- **Mechanism:** It parses the SVG text, identifies keyframe animations, calculates the final state properties, and injects them as inline `style` overrides with `!important`.
- **Why?** Eliminates the heavy dependency on Puppeteer/Chromium, making the CLI faster and more portable (no installation of Node.js required).
- **Whitespace Handling:** Uses literal `\u00A0` (Non-Breaking Space) and `xml:space="preserve"` to ensure `rsvg-convert` renders text spacing correctly.

### `img scan` (Document Scanning)
- **Purpose:** Converts photos of documents into "Official Administrative" scans (Pure white background, sharp black text).
- **Architecture:** Hybrid Shell/Python pipeline.
- **Modes:**
  1.  **Fast (Shell/IM):** Simple histogram stretch.
  2.  **Pro (Shell/IM):** Uses "Global Illumination Normalization" (Divide by large version of self) + Histogram Crushing.
  3.  **OCR (Shell/IM):** Aggressive binary-like grayscale for machine reading.
  4.  **Python (OpenCV):** Uses `uv run` to execute `lib/python/doc_scan.py`. Implements adaptive Gaussian thresholding and median blurring for "Official Letter" quality.
- **Dependencies:** The Python mode automatically manages `opencv-python` via `uv`, requiring no manual user installation.


### `compress` (Video)
- **Unified Entry:** Single command handles single files, multiple files, and the `batch` subcommand.
- **Batch Mode:** Optimized for directories (e.g., `amir compress batch ./Videos`). Subcommand filtering ensures only directories are suggested during completion.
- **Orientation Awareness:** Automatically detects Portrait vs. Landscape orientation. Portrait videos (e.g., 720x1280) are scaled correctly to avoid black landscape padding.
- **Hardware Acceleration:** Auto-detects macOS Silicon (`videotoolbox`), NVIDIA (`nvenc`), or Intel (`qsv`).
- **Clean Progress:** Uses a custom `while read -d $'\r'` filter to capture FFmpeg status and display it as a single, updating line in the terminal, preventing scroll-spam on all platforms.
- **Table Alignment:** Uses Python's `unicodedata` library to strictly calculate visual string width (East Asian Width).
- **AI Stats:** Log file tracks compression ratios to optimal settings.

### `pdf` (Multi-Engine High-Fidelity Rendering)
- **Architecture:** Hybrid system utilizing specialized rendering engines with a robust fallback pipeline.
- **Engines:**
    - **Puppeteer (Default):** Chromium-based rendering for highest fidelity. Supports CSS3, complex layouts, and modern typography.
    - **WeasyPrint:** Python-based CSS/HTML renderer (optimized for print).
    - **Pandoc:** Vector-based conversion for document formats.
    - **PIL (Fallback):** Ultra-robust image-based renderer. Used automatically if advanced engines fail to ensure no content loss. Supports infinite vertical pagination.
- **Key Technical Features:**
    - **Base64 Font Embedding:** To bypass browser security restrictions (`file://`), the **B Nazanin** Persian font is injected directly as a Base64 Data URI into the Puppeteer HTML stream.
    - **Smart Pagination:** Uses CSS `page-break-inside: avoid` to prevent element splitting. The assembly loop in `pdf.sh` uses explicit page selection (`[0-999]`) to ensure ImageMagick captures every page from multi-page PDFs.
    - **Finder Optimization:** On macOS, the script executes `touch` on the final output to force Finder to refresh "Date Added" and "Date Modified" metadata, ensuring the new file appears at the top of lists.
    - **Disk Space Overflow:** If the internal disk is full (100% capacity), the script automatically redirects `TMPDIR`, `UV_CACHE_DIR`, and Chrome profiles to `/Volumes/SanDisk/amir_data`.
    - **Dynamic Naming:** Default output follows the pattern `{input}_{engine}.pdf` for easy identification.

### `img` (Image Manipulation) - AI & Laboratory
- **Upscaling Architecture:** Uses the `realesrgan-ncnn-vulkan` binary. 
  - **Tiling Fix:** ESRGAN models are native 4x. To prevent tiling artifacts at other scales, the CLI always upscales to 4x internally and then downsamples via ImageMagick to the target scale (1x, 2x, 3x).
  - **Hardware Support:** Utilizes Vulkan for acceleration (Metal on macOS).
- **Enhancement Lab (`lab`):** 
  - **Logic:** Automates the testing of 20 unique ImageMagick filter chains per model.
  - **Single Mode (Default):** Runs on 1 selected model (default: ultrasharp) → **20 images**.
  - **Multi Mode (`-m all`):** Iterates through all 7 AI models → **140 images** (7 models × 20 filters).
  - **Hierarchical Storage:** Organizes results into `lab_{base}/{model}/{filter}.jpg` for easy comparison.
- **Stacking:** Combines images with auto-orient and deskew. Uses paper-size presets (A4/B5 at 150DPI) for standardized document preparation.

### `subtitle` (AI-Powered Multilingual Subtitle System)
**Architecture:** Hybrid Python/FFmpeg pipeline with intelligent caching, validation, and rendering.

#### Component Stack
1. **Transcription Engine:**
   - **Primary:** `faster-whisper` (CPU-optimized Whisper)
   - **Apple Silicon:** `mlx-whisper` (Metal acceleration via MLX framework)
   - **Model:** Default `large-v3` (highest accuracy)
   - **Optimization:** Smart caching with SHA-256 hash keying (`~/.amir_cache/transcriptions/`)

2. **Translation System:**
   - **Primary Provider:** DeepSeek API (GPT-4 class quality, cost-effective)
   - **Fallback Chain:** LiteLLM → Gemini
   - **Batch Processing:** 25 lines per API call (DeepSeek), 40 lines (Gemini), 20 lines (LiteLLM)
   - **Cache:** SHA-256 keyed translations (`~/.amir_cache/translations/`)

3. **Language Support (32 Languages):**
   - **Centralized Registry:** `LANGUAGE_REGISTRY` dataclass-based configuration
   - **Components:** Language code, display name, Unicode char range, RTL flag
   - **Top 25 (YouTube Priority 2026):**
     ```
     zh (Chinese), en (English), es (Spanish), hi (Hindi), ar (Arabic),
     bn (Bengali), pt (Portuguese), ru (Russian), ja (Japanese), fr (French),
     ur (Urdu), pa (Punjabi), vi (Vietnamese), tr (Turkish), ko (Korean),
     id (Indonesian), de (German), fa (Persian), gu (Gujarati), it (Italian),
     mr (Marathi), te (Telugu), ta (Tamil), th (Thai), ha (Hausa)
     ```
   - **Additional:** Greek, Hebrew, Malagasy, Dutch, Polish, Ukrainian

4. **Quality Assurance:**
   - **Multi-Stage Parser:**
     - Numbered format (`1. text\n2. text`)
     - JSON format (`[{"index": 1, "text": "..."}]`)
     - Plain text (line-by-line)
     - Persian/Arabic digit normalization (`۱۲۳` → `123`)
     - 80% valid line threshold
   - **Post-Translation Validation:**
     - Character range check for non-Latin scripts
     - Source comparison for Latin scripts
     - Technical term pattern detection (parenthetical English)
     - Interactive user prompts for incomplete batches (max 3 retries)
     - **Guarantee:** No rendering until 100% translation or user decline

5. **Resume Capability:**
   - **Mechanism:** Ingests partial SRT files to recover existing translations
   - **Smart Mapping:** Time-based alignment (prevents line count desync)
   - **Use Case:** Continue interrupted translation jobs with `-c/--continue` flag
   - **Cost Savings:** Avoids re-translating already completed batch segments

6. **Technical Term Preservation:**
   - **Pattern:** Maintains English terms in parentheses (e.g., "هوش مصنوعی عمومی (AGI)")
   - **Scope:** All 32 languages (configurable per language)
   - **Mechanism:** Prompt engineering + validation regex

7. **Video Rendering (Smart Bitrate System):**
   - **Resolution Detection:** ffprobe extracts width × height
   - **Adaptive Mapping:**
     ```
     ≤480p  (≤500K pixels):  1.5 Mbps
     ≤720p  (≤1M pixels):    2.5 Mbps
     ≤1080p (≤2.5M pixels):  4.0 Mbps
     4K+    (>2.5M pixels):  8.0 Mbps
     ```
   - **Hardware Acceleration:**
     - **Apple Silicon:** `h264_videotoolbox` with bitrate targeting
     - **Fallback:** `libx264 -crf 23 -preset medium` (quality-based)
   - **Audio:** `-c:a copy` (lossless passthrough)
   - **Font Injection:** Explicit `fontsdir` for sandboxed FFmpeg environments
   - **File Size:** Optimized for minimal increase (typically 1.5-2x original)

8. **ASS Styling (Advanced SubStation Alpha):**
   - **Bilingual Layout:**
     - **Primary:** Bottom, white, bold, 24px
     - **Secondary:** Top, gray, 18px (e.g., English commentary over Persian)
   - **RTL Support:** Proper alignment for Arabic/Persian/Urdu/Hebrew
   - **Font Selection:** `B Nazanin` (Persian), `Noto Sans` (Fallback)
   - **Resolution Scaling:** `font_size = (height / 1080) * 25`

#### Workflow Example
```bash
# Full pipeline: Transcribe + Translate + Render
amir subtitle video.mp4 -t en fa -r

# Resume interrupted translation
amir subtitle video.mp4 -t en fa -rc

# Multiple languages
amir subtitle video.mp4 -t en fa ar es -r
```

#### Technical Implementation Details
- **File:** `lib/python/subtitle/processor.py` (2164 lines)
- **Class:** `SubtitleProcessor`
- **Key Methods:**
  - `run_workflow()`: Orchestrates full pipeline
  - `_parse_translated_batch_output()`: Robust multi-format parser
  - `translate_with_deepseek()`: Batch translation with retry logic
  - `create_ass_with_font()`: ASS generation with bilingual support
  - `_ingest_partial_srt()`: Resume translation recovery

### `llm-lists` (LLM Model Discovery)
**Purpose:** Fetch and export available models from AI providers for quick reference.

#### Supported Providers
1. **Gemini:** Google's latest models via `google-genai` SDK
2. **OpenAI:** GPT models via official SDK
3. **DeepSeek:** Chat/Coder models (OpenAI-compatible endpoint)
4. **Groq:** Ultra-fast inference models
5. **Anthropic:** Claude models (manually curated list)

#### Architecture
- **Implementation:** Hybrid Bash/Python (`lib/commands/llm-lists.sh`)
- **Python Script:** Dynamically generated with embedded code
- **Environment:** Uses `.env` for API keys
- **Execution:** Prefers virtual environment Python if available

#### Usage
```bash
# List models
amir llm-lists gemini
amir llm-lists deepseek

# Export formats
amir llm-lists openai -e md        # Markdown
amir llm-lists groq --export pdf   # PDF (requires pandoc)
```

#### Export Features
- **Markdown:** Timestamped code block format
- **PDF:** Converted via Pandoc with metadata
- **Naming:** `{provider}_models_YYYYMMDD.{ext}`

## ⚙️ Configuration & Storage

### Centralized Configuration System

Amir CLI implements a **global configuration system** via `~/.amir/config.yaml`. This allows users to customize default behaviors without modifying code.

#### Architecture

**`lib/config.sh`:**
- Provides `get_config <section> <key> <default>` function
- Uses `awk` for YAML parsing (no external dependencies)
- Auto-creates `config.yaml` with sensible defaults on first run
- Handles `~` expansion in file paths

**Integration Pattern:**
Each command sources `lib/config.sh` and reads defaults:
```bash
# Source Config
local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
local LIB_DIR="$(dirname "$SCRIPT_DIR")"
if [[ -f "$LIB_DIR/config.sh" ]]; then
    source "$LIB_DIR/config.sh"
else
    get_config() { echo "$3"; }  # Fallback
fi

# Read defaults
local quality=$(get_config "compress" "quality" "60")
```

**Supported Commands:**
- `pdf`: `radius`, `rotate`
- `compress`: `resolution`, `quality`
- `mp3`: `bitrate`
- `img`: `default_size`
- `qr`: `size`
- `pass`: `length`
- `weather`: `default_city`
- `todo`: `file`
- `short`: `provider`

### Storage Location
By default, Amir CLI stores all its data (logs, stats, config, temp files) in:
- **`~/.amir/`** (Hidden directory in your User Home)

This prevents home directory pollution. The structure is:
```text
~/.amir/
├── config.yaml        # User configuration
├── learning_data      # AI stats for video compression
├── todo_list.txt      # Todo items
├── chat_history.md    # AI chat logs
└── code_history.md    # Code generation logs
```

### Customizing the Location
You can change this location (e.g., if you want to rename the project or store data elsewhere) by setting the `AMIR_CONFIG_DIR` environment variable.

**Example (.bashrc / .zshrc):**
```bash
export AMIR_CONFIG_DIR="$HOME/.my_custom_tool_data"
```

The CLI automatically detects this variable and uses it instead of the default.
