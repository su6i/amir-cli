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
    # Default to /usr/local/share/zsh/site-functions for both Mac and Linux usually
    # Users can add this to fpath if not present
    TARGET_ZSH_DIR="/usr/local/share/zsh/site-functions"
    
    echo "🔗 Linking Zsh completions to $TARGET_ZSH_DIR..."
    if [[ ! -d "$TARGET_ZSH_DIR" ]]; then
        echo "   (Creating directory)"
        sudo mkdir -p "$TARGET_ZSH_DIR"
    fi
    sudo ln -sf "$PROJECT_DIR/completions/_amir" "$TARGET_ZSH_DIR/_amir"
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

# Image processing tool check
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! check_dep sips; then 
        echo "❌ Sips not found (unexpected on macOS)."
        ((MISSING_DEPS++))
    fi
else
    # Check for ImageMagick (magick or convert)
    if ! check_dep magick && ! check_dep convert; then 
        echo "❌ ImageMagick not found."
        ((MISSING_DEPS++))
    fi
fi

if [[ $MISSING_DEPS -gt 0 ]]; then
    echo "⚠️  Found $MISSING_DEPS missing required dependencies."
    echo "🔄 Starting automatic installation..."
    install_deps
else
    echo "✅ All dependencies are already met."
fi


# 4. Configuration (Environment Variables)
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

echo "-------------------------------------"
echo "🎉 Installation Complete! Run 'amir help' to start."
