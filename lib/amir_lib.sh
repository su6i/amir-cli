#!/bin/bash

# ==============================================================================
# Amir CLI Core Library
# Contains: Global variables, colors, logging, and shared helpers.
# ==============================================================================

# --- Global Configuration ---

# Default configuration directory.
# Users can override this by setting AMIR_CONFIG_DIR in their .bashrc/.zshrc
export AMIR_CONFIG_DIR="${AMIR_CONFIG_DIR:-$HOME/.amir}"

# Ensure the directory exists
if [[ ! -d "$AMIR_CONFIG_DIR" ]]; then
    mkdir -p "$AMIR_CONFIG_DIR"
fi

# --- Colors ---
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- Logging Helpers ---

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}${BOLD}❌ ERROR:${NC} $1"
}

print_header() {
    echo -e "${BOLD}${CYAN}$1${NC}"
    echo -e "${CYAN}══════════════════════${NC}"
}

# --- Shared Utilities ---

copy_to_clipboard() {
    local response="$1"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -n "$response" | pbcopy
        echo "📋 Copied to clipboard (macOS)"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v xclip &> /dev/null; then
            echo -n "$response" | xclip -selection clipboard
            echo "📋 Copied to clipboard (xclip)"
        elif command -v xsel &> /dev/null; then
            echo -n "$response" | xsel --clipboard
            echo "📋 Copied to clipboard (xsel)"
        fi
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        if command -v clip.exe &> /dev/null; then
            echo -n "$response" | clip.exe
            echo "📋 Copied to clipboard (Windows)"
        fi
    else
        # Fallback for systems without recognized clipboard tools
        echo "📋 (Clipboard not supported on this OS: $OSTYPE)"
    fi
}

# Helper to find the full-featured FFmpeg (with libass support)
get_ffmpeg_path() {
    local SUBTITLE_DIR="$SCRIPT_DIR/lib/python/subtitle"
    
    # Try using our projects local static-ffmpeg managed via uv
    if [[ -d "$SUBTITLE_DIR" ]] && command -v uv &> /dev/null; then
        # Use uv run to get the path from the python package we installed
        local static_ffmpeg_path=$(uv run --project "$SUBTITLE_DIR" python -c "import static_ffmpeg; print(static_ffmpeg.get_ffmpeg_bin())" 2>/dev/null)
        if [[ -x "$static_ffmpeg_path" ]]; then
            echo "$static_ffmpeg_path"
            return 0
        fi
    fi

    # Fallback to system ffmpeg if nothing else found
    which ffmpeg
}
