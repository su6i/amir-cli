#!/bin/bash

# ==============================================================================
# Amir CLI Installer
# ==============================================================================

INSTALL_DIR="/usr/local/bin"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXECUTABLE_NAME="amir"

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
            brew install bc qrencode
            ;;
        linux-gnu*)
            if check_dep apt; then
                sudo add-apt-repository -y ppa:jonathonf/ffmpeg-4
                sudo apt update
                sudo apt install -y ffmpeg libx265-dev bc qrencode
            elif check_dep yum; then
                sudo yum install -y ffmpeg bc qrencode
            elif check_dep dnf; then
                sudo dnf install -y ffmpeg bc qrencode
            elif check_dep pacman; then
                sudo pacman -S --noconfirm ffmpeg bc qrencode
            fi
            ;;
        msys*|cygwin*|win32*)
            echo "⚠️  On Windows, please install manually via Chocolatey:"
            echo "   choco install ffmpeg-full bc qrencode"
            ;;
        *)
            echo "❌ Unsupported OS for auto-install."
            exit 1
            ;;
    esac
}

# --- Main Execution ---

echo "🚀 Starting Amir CLI Installation..."
echo "-------------------------------------"

# 1. Hardware/OS Check (Informational)
OS_TYPE=$(uname -s)
ARCH=$(uname -m)
echo "🖥️  System Detected: $OS_TYPE ($ARCH)"

# 2. Link Executable
if [[ ! -d "$INSTALL_DIR" ]]; then
    echo "📂 Creating $INSTALL_DIR..."
    sudo mkdir -p "$INSTALL_DIR"
fi

# Remove existing link if present
if [[ -L "$INSTALL_DIR/$EXECUTABLE_NAME" ]]; then
    sudo rm "$INSTALL_DIR/$EXECUTABLE_NAME"
fi

# 2. Link Zsh completions
if [[ -f "$PROJECT_DIR/completions/_amir" ]]; then
    target_comp="/usr/local/share/zsh/site-functions/_amir"
    if [[ -d "/usr/local/share/zsh/site-functions" ]]; then
        sudo ln -sf "$PROJECT_DIR/completions/_amir" "$target_comp"
    elif [[ -d "/usr/share/zsh/site-functions" ]]; then
        sudo ln -sf "$PROJECT_DIR/completions/_amir" "/usr/share/zsh/site-functions/_amir"
    else
        echo "ℹ️  Zsh completion directory not found. You may need to source the completion file manually."
    fi
fi
# Force link
echo "🔗 Linking executable..."
sudo ln -s "$PROJECT_DIR/amir" "$INSTALL_DIR/$EXECUTABLE_NAME"

# 3. Check & Install Dependencies
echo "🔍 Checking dependencies..."

MISSING_DEPS=0
if ! check_dep ffmpeg; then ((MISSING_DEPS++)); fi
if ! check_dep ffprobe; then ((MISSING_DEPS++)); fi
if ! check_dep bc; then ((MISSING_DEPS++)); fi
if ! check_dep qrencode; then ((MISSING_DEPS++)); fi

if [[ $MISSING_DEPS -gt 0 ]]; then
    echo "⚠️  Found $MISSING_DEPS missing required dependencies."
    echo "🔄 Starting automatic installation..."
    install_deps
else
    echo "✅ All dependencies are already met."
fi

echo "-------------------------------------"
echo "🎉 Installation Complete! Run 'amir help' to start."
