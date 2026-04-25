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

# Prefer a writable local temp root over system /tmp.
amir_preferred_temp_dir() {
    local hint_dir="${1:-}"
    local -a candidates=()

    [[ -n "$hint_dir" ]] && candidates+=("$hint_dir")
    [[ -n "$PWD" ]] && candidates+=("$PWD")
    [[ -n "$AMIR_ROOT" ]] && candidates+=("$AMIR_ROOT")
    [[ -n "$HOME" ]] && candidates+=("$HOME")
    [[ -n "$TMPDIR" ]] && candidates+=("$TMPDIR")
    candidates+=("/tmp")

    local base
    for base in "${candidates[@]}"; do
        [[ -n "$base" && -d "$base" && -w "$base" ]] || continue
        base="${base%/}/.amir_tmp"
        mkdir -p "$base" 2>/dev/null || continue
        printf '%s' "$base"
        return 0
    done

    return 1
}

amir_mktemp_file() {
    local prefix="$1"
    local suffix="${2:-}"
    local hint_dir="${3:-}"
    local temp_root
    temp_root="$(amir_preferred_temp_dir "$hint_dir")" || return 1
    mktemp "${temp_root%/}/${prefix}.XXXXXX${suffix}"
}

amir_mktemp_dir() {
    local prefix="$1"
    local hint_dir="${2:-}"
    local temp_root
    temp_root="$(amir_preferred_temp_dir "$hint_dir")" || return 1
    mktemp -d "${temp_root%/}/${prefix}.XXXXXX"
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
# ==============================================================================
# Media Configuration API (Centralized Standards)
# ==============================================================================
# Industry Best Practice: Single Source of Truth for encoding parameters
# Used by: compress.sh, subtitle/processor.py, and all media tools

get_media_config() {
    local key_path="$1"
    local config_file="${AMIR_ROOT:-$SCRIPT_DIR}/lib/config/media.json"
    
    if [[ ! -f "$config_file" ]]; then
        echo "ERROR: Media config not found" >&2
        return 1
    fi
    
    # Use Python's JSON parser (guaranteed to be available since we require it)
    python3 -c "
import json
import sys

try:
    with open('$config_file') as f:
        config = json.load(f)
    
    # Navigate nested keys (e.g., 'encoding.bitrate.multiplier')
    keys = '$key_path'.split('.')
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            sys.exit(1)
    
    print(value)
except:
    sys.exit(1)
" 2>/dev/null
}

# Convenience functions for common media parameters
get_bitrate_multiplier() {
    get_media_config "encoding.bitrate.multiplier"
}

get_fallback_bitrate() {
    get_media_config "encoding.bitrate.fallback"
}

get_default_crf() {
    get_media_config "encoding.quality.default_crf"
}

get_hw_encoder() {
    local platform="$1"
    get_media_config "encoding.hardware_acceleration.$platform"
}
# Detect best available hardware encoder automatically
# Returns: "encoder|codec|platform" format (e.g., "hevc_videotoolbox|h265|apple_silicon")
detect_best_hw_encoder() {
    local config_file="${AMIR_ROOT:-$SCRIPT_DIR}/lib/config/media.json"
    
    if [[ ! -f "$config_file" ]]; then
        echo "libx264|h264|cpu"
        return
    fi
    
    # Use Python to run the detection logic
    python3 -c "
import sys
sys.path.insert(0, '${AMIR_ROOT:-$SCRIPT_DIR}/lib/python')
from media_config import detect_best_hw_encoder

result = detect_best_hw_encoder()
print(f\"{result['encoder']}|{result['codec']}|{result['platform']}\")
" 2>/dev/null || echo "libx264|h264|cpu"
}

# ==============================================================================
# UI & Table Helpers (Modularized for reuse)
# ==============================================================================

# Calculate visual width (2 for wide/emoji, 1 for normal) using Python unicodedata
get_visual_width() {
    python3 -c "import unicodedata, sys; s=sys.argv[1]; print(sum(2 if unicodedata.east_asian_width(c) in 'WF' else 0 if unicodedata.category(c) in ('Mn','Me','Cf') else 1 for c in s))" "$1" 2>/dev/null || echo ${#1}
}

# Pad to target visual width
pad_to_width() {
    local text="$1"
    local target="$2"
    local current=$(get_visual_width "$text")
    local diff=$((target - current))
    echo -n "$text"
    if [[ $diff -gt 0 ]]; then
        printf "%${diff}s" ""
    fi
}

# ==============================================================================
# FFmpeg Progress Bar (Universal Parser)
# ==============================================================================

# Parse FFmpeg output and display an elegant progress bar
# Usage: ffmpeg -i in.mp4 ... 2>&1 | ffmpeg_progress_bar 120.5
ffmpeg_progress_bar() {
    local total_duration="$1"
    local start_time=$(date +%s)
    
    # Check if we have a valid duration; if not default to 0
    if [[ -z "$total_duration" || "$total_duration" == "N/A" ]]; then
        total_duration=0
    fi
    
    # Read from FFmpeg stderr line by line (using \r as delimiter)
    while read -d $'\r' -r line || [[ -n "$line" ]]; do
        # Clean the line
        local clean_line=$(echo "$line" | tr -d '\n' | sed -E 's/^[[:space:]]+//')
        
        # We only care about lines starting with "frame=" or containing "time="
        if [[ "$clean_line" == frame=* || "$clean_line" == *"time="* ]]; then
            # Extract time in HH:MM:SS.xx format using regex/awk
            local current_time_str=$(echo "$clean_line" | grep -o 'time=[0-9][0-9]*:[0-9][0-9]*:[0-9][0-9]*\.[0-9]*' | cut -d'=' -f2)
            
            # Additional extraction: Bitrate, Speed
            local bitrate=$(echo "$clean_line" | grep -o 'bitrate=[^ ]*' | cut -d'=' -f2)
            local speed=$(echo "$clean_line" | grep -o 'speed=[^ ]*' | cut -d'=' -f2)
            
            if [[ -n "$current_time_str" ]]; then
                # Convert time string to seconds
                local h=$(echo "$current_time_str" | cut -d':' -f1)
                local m=$(echo "$current_time_str" | cut -d':' -f2)
                local s=$(echo "$current_time_str" | cut -d':' -f3)
                
                # Using awk for floating point math
                local current_sec=$(awk -v h="$h" -v m="$m" -v s="$s" 'BEGIN {print (h*3600) + (m*60) + s}')
                
                local elapsed=$(( $(date +%s) - start_time ))
                local elapsed_fmt=$(date -u -r "$elapsed" +%M:%S 2>/dev/null || date -u -d "@$elapsed" +%M:%S 2>/dev/null)
                
                if [[ $(echo "$total_duration > 0" | bc) -eq 1 ]]; then
                    # Calculate percentage
                    local pct=$(awk -v cur="$current_sec" -v tot="$total_duration" 'BEGIN { p = (cur/tot)*100; if(p>100)p=100; printf "%.1f", p }')
                    
                    # Calculate ETA
                    local eta_fmt="--:--"
                    if [[ $(echo "$current_sec > 0" | bc) -eq 1 ]]; then
                        local remaining_sec=$(awk -v cur="$current_sec" -v tot="$total_duration" -v elapsed="$elapsed" 'BEGIN { rate=cur/(elapsed+0.001); if(rate>0) print int((tot-cur)/rate); else print 0 }')
                        eta_fmt=$(date -u -r "$remaining_sec" +%M:%S 2>/dev/null || date -u -d "@$remaining_sec" +%M:%S 2>/dev/null)
                    fi
                    
                    # Print progress (using carriage return to write over the same line)
                    printf "\r\033[K⏳ %-4s | %5s%% | Speed: %-6s | ETA: %s | Time: %s" "Run" "$pct" "${speed:-N/A}" "$eta_fmt" "$elapsed_fmt"
                else
                    # Fallback if duration is unknown
                    printf "\r\033[K⏳ Processing... | Time: %s | Bitrate: %-10s | Speed: %-6s" "$current_time_str" "${bitrate:-N/A}" "${speed:-N/A}"
                fi
            fi
        else
            # Print non-progress lines normally (e.g. errors, config) if they match specific words
            if echo "$clean_line" | grep -qiE "(error|warning|failed|complete|finished)"; then
                echo -e "\n$clean_line"
            fi
        fi
    done
    echo "" # Final newline
}
