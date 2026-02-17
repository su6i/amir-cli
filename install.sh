#!/bin/bash

# ==============================================================================
# Amir CLI Installer
# ==============================================================================

INSTALL_DIR="/usr/local/bin"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXECUTABLE_NAME="amir"

# ------------------------------------------------------------------------------
# 0. Ensure `uv` is installed (Mandatory preference)
# ------------------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    echo "🔁 'uv' not found — Installing uv (mandatory for project environment)..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh || {
            echo "⚠️  uv standalone installation failed. Trying to install via system package manager..."
            case "$OSTYPE" in
                darwin*) brew install uv ;;
                linux-gnu*) 
                    if command -v apt >/dev/null 2>&1; then
                        sudo apt update && sudo apt install -y uv || echo "⚠️  apt install uv failed."
                    fi
                    ;;
            esac
        }
        
        # Add local uv bin to PATH if it was just installed but not yet in PATH
        [[ -d "$HOME/.cargo/bin" ]] && export PATH="$HOME/.cargo/bin:$PATH"
        [[ -d "$HOME/.local/bin" ]] && export PATH="$HOME/.local/bin:$PATH"
        
        # Verify if it worked
        if ! command -v uv >/dev/null 2>&1; then
             # Try common locations explicitly
             if [[ -f "$HOME/.cargo/bin/uv" ]]; then
                 export PATH="$HOME/.cargo/bin:$PATH"
             elif [[ -f "/usr/local/bin/uv" ]]; then
                 export PATH="/usr/local/bin:$PATH"
             fi
        fi
    else
        echo "❌ 'curl' not found. Please install 'curl' or 'uv' manually."
        exit 1
    fi
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "⚠️  Failed to install 'uv'. Falling back to native 'venv' and 'pip' logic."
    HAS_UV=0
else
    echo "✅ 'uv' is available."
    HAS_UV=1
    # Self-update uv if available
    uv self update >/dev/null 2>&1 || true
fi

# --- Helper Functions ---

check_dep() {
    command -v "$1" &> /dev/null
}

install_deps() {
    echo "📦 Installing system dependencies (FFmpeg, libx265, bc, qrencode)..."
    
    case "$OSTYPE" in
        darwin*)
            if ! check_dep brew; then
                 echo "🍺 Installing Homebrew..."
                 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install ffmpeg --with-libx265 --with-tools
            brew install bc qrencode uv imagemagick
            ;;
        linux-gnu*)
            if check_dep apt; then
                sudo add-apt-repository -y ppa:jonathonf/ffmpeg-4
                sudo apt update
                sudo apt install -y ffmpeg libx265-dev bc qrencode imagemagick
            elif check_dep yum; then
                sudo yum install -y ffmpeg bc qrencode
            elif check_dep dnf; then
                sudo dnf install -y ffmpeg bc qrencode
            elif check_dep pacman; then
                sudo pacman -S --noconfirm ffmpeg bc qrencode
            fi
            ;;
        msys*|cygwin*|win32*)
            echo "⚠️  On Windows, please install manually:"
            echo "   winget install ImageMagick.ImageMagick"
            echo "   choco install ffmpeg-full bc qrencode"
            ;;
        *)
            echo "❌ Unsupported OS for auto-install."
            if ! check_dep uv; then
                echo "ℹ️  Installing uv manually..."
                curl -LsSf https://astral.sh/uv/install.sh | sh
            fi
            exit 1
            ;;
    esac
}

# --- Main Execution ---

AUTO_MODE=0
INSTALL_ML=0
for arg in "$@"; do
    case $arg in
        --auto) AUTO_MODE=1 ;;
        --with-ml) INSTALL_ML=1 ;;
    esac
done

if [[ $AUTO_MODE -eq 0 ]]; then
    echo "🚀 Starting Amir CLI Installation..."
    echo "-------------------------------------"
fi

# 1. Hardware/OS Check (Informational)
OS_TYPE=$(uname -s)
ARCH=$(uname -m)
if [[ $AUTO_MODE -eq 0 ]]; then
    echo "🖥️  System Detected: $OS_TYPE ($ARCH)"
fi

# 2. Link Executable
if [[ $AUTO_MODE -eq 0 ]]; then
    if [[ ! -d "$INSTALL_DIR" ]]; then
        echo "📂 Creating $INSTALL_DIR..."
        sudo mkdir -p "$INSTALL_DIR"
    fi

    # Remove existing link if present
    if [[ -L "$INSTALL_DIR/$EXECUTABLE_NAME" ]]; then
        sudo rm "$INSTALL_DIR/$EXECUTABLE_NAME"
    fi

    # Link Zsh completions
    if [[ -f "$PROJECT_DIR/completions/_amir" ]]; then
        TARGET_ZSH_DIR="/usr/local/share/zsh/site-functions"
        echo "🔗 Linking Zsh completions to $TARGET_ZSH_DIR..."
        if [[ ! -d "$TARGET_ZSH_DIR" ]]; then
            sudo mkdir -p "$TARGET_ZSH_DIR"
        fi
        sudo ln -sf "$PROJECT_DIR/completions/_amir" "$TARGET_ZSH_DIR/_amir"
    fi
    # Force link
    echo "🔗 Linking executable..."
    sudo ln -s "$PROJECT_DIR/amir" "$INSTALL_DIR/$EXECUTABLE_NAME"
fi

# 3. Check & Install Dependencies
[[ $AUTO_MODE -eq 0 ]] && echo "🔍 Checking dependencies..."

MISSING_DEPS=0
if ! check_dep ffmpeg; then ((MISSING_DEPS++)); fi
if ! check_dep ffprobe; then ((MISSING_DEPS++)); fi
if ! check_dep bc; then ((MISSING_DEPS++)); fi
if ! check_dep qrencode; then ((MISSING_DEPS++)); fi
if ! check_dep uv; then ((MISSING_DEPS++)); fi

if [[ $MISSING_DEPS -gt 0 ]]; then
    echo "⚠️  Found $MISSING_DEPS missing required dependencies."
    echo "🔄 Starting automatic installation..."
    install_deps
elif [[ $AUTO_MODE -eq 0 ]]; then
    echo "✅ All dependencies are already met."
fi


# 4. Configuration (Environment Variables)
if [[ $AUTO_MODE -eq 0 ]]; then
    echo "-------------------------------------"
    echo "🔧 Configuration"
    echo "Would you like to configure API keys now? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "Enter your GEMINI_API_KEY (Leave empty if none):"
        read -r gemini_key
        
        if [[ -n "$gemini_key" ]]; then
            echo "GEMINI_API_KEY=\"$gemini_key\"" > "$PROJECT_DIR/.env"
            echo "✅ Saved to .env"
        else
            echo "ℹ️  Skipped."
        fi
    else
        echo "ℹ️  Skipped configuration. You can add .env manually later."
    fi
fi

# 5. Tools Setup (Real-ESRGAN)
echo "-------------------------------------"
echo "🛠️  Setting up AI Background Tools..."
mkdir -p "$HOME/.amir-cli/tools/realesrgan"
if [[ ! -f "$HOME/.amir-cli/tools/realesrgan/realesrgan-cli" ]]; then
    echo "ℹ️  Real-ESRGAN binary is required for 'amir img upscale'."
    echo "   Please follow instructions in docs/TECHNICAL.md to install it."
fi

# ----------------------
# 6. Python environment and dependencies
# ----------------------
echo "-------------------------------------"
echo "🐍 Setting up Python project environment..."

VENV_DIR="$PROJECT_DIR/.venv"

install_via_uv() {
    echo "📦 Using 'uv' to sync project environment..."
    # uv sync handles venv creation and requirements installation efficiently
    if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
        uv pip install -r "$PROJECT_DIR/requirements.txt"
    fi
    
    if [[ $INSTALL_ML -eq 1 ]] && [[ -f "$PROJECT_DIR/requirements-ml.txt" ]]; then
        echo "🧠 Installing ML/Heavy dependencies (this may take a while)..."
        uv pip install -r "$PROJECT_DIR/requirements-ml.txt"
    fi
}

install_via_pip() {
    PYTHON_CMD="python3"
    if ! command -v "$PYTHON_CMD" >/dev/null 2>&1; then
        echo "❌ python3 not found. Cannot proceed with pip fallback."
        return 1
    fi
    
    if [[ ! -d "$VENV_DIR" ]]; then
        echo "🔧 Creating virtualenv at $VENV_DIR"
        "$PYTHON_CMD" -m venv "$VENV_DIR"
    fi

    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    
    echo "🔩 Ensuring pip is up to date..."
    "$VENV_DIR/bin/python" -m ensurepip --upgrade || true
    "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel || true

    echo "📦 Installing Python packages from requirements.txt"
    "$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"
    
    if [[ $INSTALL_ML -eq 1 ]] && [[ -f "$PROJECT_DIR/requirements-ml.txt" ]]; then
        echo "🧠 Installing ML/Heavy dependencies via pip..."
        "$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/requirements-ml.txt"
    fi
    deactivate || true
}

if [[ $HAS_UV -eq 1 ]]; then
    # ensure .venv exists even for uv
    if [[ ! -d "$VENV_DIR" ]]; then
        uv venv "$VENV_DIR"
    fi
    # Use uv pip as it is a drop-in extremely fast replacement
    # We set VIRTUAL_ENV env var so uv pip uses our .venv
    export VIRTUAL_ENV="$VENV_DIR"
    install_via_uv || {
        echo "⚠️  'uv' installation failed. Falling back to native 'pip'..."
        install_via_pip
    }
else
    install_via_pip
fi

echo "-------------------------------------"
echo "🎉 Installation Complete! Run 'amir help' to start."
if [[ $INSTALL_ML -eq 0 ]]; then
    echo "💡 Note: ML requirements (transformers, torch, whisper) were skipped."
    echo "   Run './install.sh --with-ml' if you need BERT scoring or local transcription."
fi
