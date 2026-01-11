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
