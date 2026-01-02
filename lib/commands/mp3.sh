#!/bin/bash

run_mp3() {
    mp3() {
        if [[ -z "$1" || ! -f "$1" ]]; then
            echo "❌ Error: File not found."
            return 1
        fi
    
        local kbps=${2:-320}
        echo "🎧 Extracting Audio at ${kbps}kbps: $1 ..."
        ffmpeg -hide_banner -loglevel error -stats -y -i "$1" -vn -c:a libmp3lame -b:a "${kbps}k" "${1%.*}.mp3"
        echo "✅ Done!"
    }
    mp3 "$@"
}
