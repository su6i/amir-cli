#!/bin/bash

run_img() {
    img() {
        if [[ -z "$1" || ! -f "$1" ]]; then 
            echo "❌ Image file not found."
            return 1
        fi
        if [[ -z "$2" ]]; then 
            echo "❌ Enter size (e.g., 512 or 800x600)"
            return 1
        fi

        local input="$1"
        local size="$2"

        if [[ ! "$size" == *"x"* ]]; then
            size="${size}x${size}"
        fi

        local output="${input%.*}_${size}.${input##*.}"

        echo "🖼  Resizing image to $size..."
        convert "$input" -resize "$size!" "$output"
        echo "✅ Image saved: $output"
    }
    img "$@"
}
