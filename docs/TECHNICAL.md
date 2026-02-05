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
- **Smart File Naming:** Output filenames automatically append used options (e.g., `_bg-blue_circle`) to prevent accidental overwrites. Includes interactive overwrite protection if a collision occurs.

#### 🎥 Static SVG Baking (Animated SVGs)
When converting a `.svg` file that contains CSS animations (`@keyframes`), Amir CLI uses a custom Python script (`lib/python/svg_bake.py`) instead of a headless browser.
- **Mechanism:** It parses the SVG text, identifies keyframe animations, calculates the final state properties, and injects them as inline `style` overrides with `!important`.
- **Why?** Eliminates the heavy dependency on Puppeteer/Chromium, making the CLI faster and more portable (no installation of Node.js required).
- **Whitespace Handling:** Uses literal `\u00A0` (Non-Breaking Space) and `xml:space="preserve"` to ensure `rsvg-convert` renders text spacing correctly.

### `compress` (Video)
- **Unified Entry:** Single command handles single files, multiple files, and directories (Batch Mode).
- **Batch Mode:** If a directory is passed (e.g., `amir compress ./Videos`), it automatically finds and processes all video files inside.
- **Smart Arguments:** Allows flexible mixing of inputs (files/dirs) and settings (Resolution/Quality).
- **Hardware Acceleration:** Auto-detects macOS Silicon (`videotoolbox`), NVIDIA (`nvenc`), or Intel (`qsv`) to speed up FFmpeg encoding.
- **Quiet Progress:** Uses `script -q /dev/null` (macOS) to force pseudo-TTY allocation, allowing FFmpeg to print single-line progress updates (`\r`) without buffering or log spam.
- **Table Alignment:** Uses Python's `unicodedata` library to strictly calculate visual string width (East Asian Width), properly handling zero-width combining characters (e.g., Variation Selectors). This ensures standard-compliant table alignment across Linux and macOS.
- **AI Stats:** Log file tracks compression ratios to optimal settings.

### `pdf` (Document Construction)
- **Problem:** Merging images into PDF often results in either huge file sizes (raw bitmaps) or poor quality (blurry text).
- **Dual Output Strategy:** Generates **two** files automatically to satisfy administrative needs:
    1. **HQ (Master):** 
        - 300 DPI (Archive/Print safe).
        - Uses `-compress jpeg -quality 100` to avoid raw bitmap bloat (13MB -> 4MB).
        - Preserves rounding and alpha.
    2. **Compressed (XS):** 
        - Optimized for <1MB file size (Email/Admin upload safe).
        - **Density Fix:** Explicitly reads HQ input at `-density 300` to prevent ImageMagick from reading at 72 DPI (which causes blur).
        - **Settings:** Resize 75% + Quality 75 + Strip Metadata.
        - **Chroma Subsampling:** Disabled (`4:4:4`) to ensure text sharpness even at lower quality.
- **Simplified Pipeline:** Uses a robust "Resize & Center" strategy (`-resize` + `extent`) to ensure reliability. Legacy masking (for rounded corners) is disabled by default to prevent "white page" issues on complex inputs.
- **Overwrite Protection:** Interactive check prevents accidental data loss. Checks *both* HQ and Compressed filenames before proceeding.

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
