#!/bin/bash

run_img() {
    # Helper: Detect ImageMagick
    detect_magic() {
        if command -v magick &> /dev/null; then echo "magick"
        elif [[ "$OSTYPE" == "darwin"* && -f "/opt/homebrew/bin/magick" ]]; then echo "/opt/homebrew/bin/magick"
        elif [[ "$OSTYPE" == "darwin"* && -f "/usr/local/bin/magick" ]]; then echo "/usr/local/bin/magick"
        elif command -v convert &> /dev/null; then echo "convert"
        elif [[ "$OSTYPE" == "darwin"* ]]; then echo "sips"
        else echo ""; fi
    }

    local cmd=$(detect_magic)
    if [[ -z "$cmd" ]]; then
        echo "❌ Error: ImageMagick is not installed."
        return 1
    fi

    # Helper: Process Size
    parse_size() {
        local size="$1"
        if [[ ! "$size" == *"x"* ]]; then size="${size}x${size}"; fi
        echo "$size"
    }

    # Helper: Get standard gravity name
    get_gravity() {
        case "$1" in
            "7") echo "northwest" ;; "8") echo "north" ;; "9") echo "northeast" ;;
            "4") echo "west"      ;; "5") echo "center" ;; "6") echo "east"      ;;
            "1") echo "southwest" ;; "2") echo "south"  ;; "3") echo "southeast" ;;
            *) echo "center" ;; # Default
        esac
    }

    # --- Subcommands ---

    do_resize() {
        local input="$1"
        local size=$(parse_size "$2")
        local width=$(echo $size | cut -dx -f1)
        local height=$(echo $size | cut -dx -f2)
        local output="${input%.*}_resized_${width}x${height}.${input##*.}"

        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        if [[ -z "$size" ]]; then echo "❌ Size required."; return 1; fi

        echo "🖼  Resizing to fit $size..."
        if [[ "$cmd" == "sips" ]]; then
            sips -Z $width "$input" --out "$output" > /dev/null
        else
            # Resize to FIT within box (no crop, no distortion)
            $cmd "$input" -resize "${width}x${height}" "$output"
        fi
        echo "✅ Saved: $output"
    }

    do_crop() {
        local input="$1"
        local size=$(parse_size "$2")
        local g_code="$3"
        local width=$(echo $size | cut -dx -f1)
        local height=$(echo $size | cut -dx -f2)
        local output="${input%.*}_cropped_${width}x${height}.${input##*.}"

        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        if [[ -z "$size" ]]; then echo "❌ Size required."; return 1; fi
        
        local g=$(get_gravity "$g_code")
        echo "✂️  Cropping (Fill & Cut) with gravity: $g..."

        if [[ "$cmd" == "sips" ]]; then
             # Sips fallback (limited)
             sips -Z $width "$input" --out "$output" > /dev/null
             sips --cropToHeightWidth $height $width "$output" > /dev/null
        else
            # Resize to FILL (^) then Extent (Crop)
            $cmd "$input" -resize "${width}x${height}^" -gravity "$g" -extent "${width}x${height}" "$output"
        fi
        echo "✅ Saved: $output"
    }
    
    do_pad() {
        local input="$1"
        local size=$(parse_size "$2")
        local color="${3:-white}" # Default color: white
        local width=$(echo $size | cut -dx -f1)
        local height=$(echo $size | cut -dx -f2)
        local output="${input%.*}_padded_${width}x${height}.${input##*.}"

        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        if [[ -z "$size" ]]; then echo "❌ Size required."; return 1; fi
        
        echo "🎨 Resizing with Pad (Contain) | Color: $color..."

        if [[ "$cmd" == "sips" ]]; then
             # Sips pad allows (rudimentary)
             sips --padToHeightWidth $height $width --padColor "$color" "$input" --out "$output" > /dev/null
        else
            # Resize to FIT then Extent (Pad)
            $cmd "$input" -resize "${width}x${height}" -background "$color" -gravity center -extent "${width}x${height}" "$output"
        fi
        echo "✅ Saved: $output"
    }

    # --- Router ---

    local action="$1"
    
    if [[ "$action" == "resize" ]]; then
        shift; do_resize "$@"
    elif [[ "$action" == "crop" ]]; then
        shift; do_crop "$@"
    elif [[ "$action" == "pad" ]]; then
        shift; do_pad "$@"
    elif [[ -f "$action" ]]; then
        # Legacy Mode: amir img <file> <size> [gravity]
        local input="$1"
        local size="$2"
        local gravity="$3"
        
        # Determine intent based on gravity presence
        if [[ -n "$gravity" ]]; then
            do_crop "$@"
        else
            # Legacy default: Resize (Fit)
            do_resize "$@"
        fi
    else
        echo "Usage:"
        echo "  amir img resize <file> <size>          (Scale to fit, no crop)"
        echo "  amir img crop   <file> <size> <g>      (Fill & Crop, g=1-9)"
        echo "  amir img pad    <file> <size> [color]  (Fit & Pad, def: white)"
        echo "  amir img <file> <size> [g]             (Legacy / Smart detect)"
        return 1
    fi
}