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
To give users helpful hints, we add this to the `case` statement in `completions/_amir`:

```zsh
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

### `compress` (Video)
- **Hardware Acceleration:** Auto-detects macOS Silicon (`videotoolbox`), NVIDIA (`nvenc`), or Intel (`qsv`) to speed up FFmpeg encoding.
- **AI Stats:** Log file tracks compression ratios to optimal settings.

## ⚙️ Configuration & Storage

### Storage Location
By default, Amir CLI stores all its data (logs, stats, temp files) in:
- **`~/.amir/`** (Hidden directory in your User Home)

This prevents home directory pollution. The structure is:
```text
~/.amir/
├── learning_data      # AI stats for video compression
└── (other configs)
```

### Customizing the Location
You can change this location (e.g., if you want to rename the project or store data elsewhere) by setting the `AMIR_CONFIG_DIR` environment variable.

**Example (.bashrc / .zshrc):**
```bash
export AMIR_CONFIG_DIR="$HOME/.my_custom_tool_data"
```

The CLI automatically detects this variable and uses it instead of the default.
