#!/bin/bash

run_mp3() {
    mp3() {
        if [[ -z "$1" || ! -f "$1" ]]; then
            echo "❌ Error: File not found."
            return 1
        fi
        
        # Source Config
        local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local LIB_DIR="$(dirname "$SCRIPT_DIR")"
        if [[ -f "$LIB_DIR/config.sh" ]]; then
            source "$LIB_DIR/config.sh"
            # init_config not needed if we assume it exists or fallback
        else
            get_config() { echo "$3"; }
        fi
    
        # Default bitrate from config
        local default_kbps=$(get_config "mp3" "bitrate" "320")
        local kbps=${2:-$default_kbps}
        
        echo "🎧 Extracting Audio at ${kbps}kbps: $1 ..."
        ffmpeg -hide_banner -loglevel error -stats -y -i "$1" -vn -c:a libmp3lame -b:a "${kbps}k" "${1%.*}.mp3"
        echo "✅ Done!"
    }
    mp3 "$@"
}
