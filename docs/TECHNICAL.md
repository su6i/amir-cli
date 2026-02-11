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

### `pdf` (PDF Generation)
- **Simplified Pipeline:** Uses a robust "Resize & Center" strategy (`-resize` + `extent`) to ensure reliability. 
- **Overwrite Protection:** Interactive check prevents accidental data loss. Checks *both* HQ and Compressed filenames before proceeding.

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
