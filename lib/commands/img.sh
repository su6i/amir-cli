#!/bin/bash

run_img() {
    # Source Config
    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local LIB_DIR="$(dirname "$SCRIPT_DIR")"
    if [[ -f "$LIB_DIR/config.sh" ]]; then
        source "$LIB_DIR/config.sh"
    else
        get_config() { echo "$3"; }
    fi
    
    local DEFAULT_SIZE=$(get_config "img" "default_size" "1080")

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

    # Helper: Process Size (with Presets)
    parse_size() {
        local size="$1"
        case "$size" in
            "yt-banner") echo "2560x1440" ;;
            "yt-logo") echo "800x800" ;;
            "yt-watermark") echo "150x150" ;;
            *) 
                if [[ ! "$size" == *"x"* ]]; then size="${size}x${size}"; fi
                echo "$size"
                ;;
        esac
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

    # Helper: Apply Circle Mask (Internal)
    apply_circle_mask() {
        local input="$1"
        local size="$2"
        local output="$3"
        local bg_color="${4:-none}" # Default to none/transparent
        
        local width=$(echo $size | cut -dx -f1)
        local height=$(echo $size | cut -dx -f2)

        echo "🟣 Applying Circular Mask..."

        if [[ "$cmd" == "sips" ]]; then
             echo "⚠️ Sips does not support circular masking. Skipping."
             cp "$input" "$output"
        else
            # Calculate coordinates for the circle
            local cx=$((width / 2))
            local cy=$((height / 2))
            
            # Method: Resize to Fill^ -> Extent to Square -> Draw Circle on alpha -> Composite
            # Note: We apply input_cmd processing first
            # Using 'magick' syntax flexibility if available, otherwise strict arguments
            
            if [[ "$bg_color" != "none" && "$bg_color" != "transparent" ]]; then
                 $cmd -background "$bg_color" "$input" -flatten -resize "${width}x${height}^" -gravity center -extent "${width}x${height}" \
                    \( +clone -threshold -1 -negate -fill white -draw "circle $cx,$cy $cx,0" \) \
                    -alpha off -compose CopyOpacity -composite \
                    "$output"
            else
                 $cmd "$input" -background none -resize "${width}x${height}^" -gravity center -extent "${width}x${height}" \
                    \( +clone -threshold -1 -negate -fill white -draw "circle $cx,$cy $cx,0" \) \
                    -alpha off -compose CopyOpacity -composite \
                    "$output"
            fi
        fi
    }

    do_resize() {
        local input="$1"
        local size_arg="${2:-$DEFAULT_SIZE}"
        local size=$(parse_size "$size_arg")
        local option="$3" # Optional: 'circle'
        local width=$(echo $size | cut -dx -f1)
        local height=$(echo $size | cut -dx -f2)
        local output="${input%.*}_resized_${width}x${height}.${input##*.}"
        
        # If circle, force png output for transparency
        if [[ "$option" == "circle" ]]; then
            output="${output%.*}.png"
        fi

        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        if [[ -z "$size" ]]; then echo "❌ Size required."; return 1; fi

        if [[ "$option" == "circle" ]]; then
            apply_circle_mask "$input" "$size" "$output"
        else
            echo "🖼  Resizing to fit $size..."
            if [[ "$cmd" == "sips" ]]; then
                sips -Z $width "$input" --out "$output" > /dev/null
            else
                $cmd "$input" -resize "${width}x${height}" "$output"
            fi
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
    
    do_convert() {
        # Parse Flags
        local background="none"
        local args=()
        
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -bg|--background)
                    if [[ -n "$2" && "$2" != -* ]]; then
                        background="$2"
                        shift 2
                    else
                        echo "❌ Error: --background requires a color argument."
                        return 1
                    fi
                    ;;
                *)
                    args+=("$1")
                    shift
                    ;;
            esac
        done
        
        # Restore positional args
        set -- "${args[@]}"

        local input="$1"
        local format="${2:-png}"
        local size_raw="${3:-$DEFAULT_SIZE}"
        local option="$4" # Optional: 'circle'
        local size=$(parse_size "$size_raw") # Parse presets!
        
        # Standardize format (remove dot)
        format="${format#.}"
        
        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        
        # Build Output Filename with Suffixes
        local suffix=""
        
        # 1. Add Size
        suffix="${suffix}_${size}"
        
        # 2. Add Background if set (and not transparent/none)
        if [[ "$background" != "none" && "$background" != "transparent" ]]; then
            # Clean hex code '#' for filename stability
            local clean_bg="${background/\#/}"
            suffix="${suffix}_bg-${clean_bg}"
        fi
        
        # 3. Add Circle
        if [[ "$option" == "circle" ]]; then
            suffix="${suffix}_circle"
        fi
        
        # Construct output name
        local output="${input%.*}${suffix}.$format"
        
        # Overwrite Check
        if [[ -f "$output" ]]; then
            echo -n "⚠️  File '$output' already exists. Overwrite? (y/N): "
            read -r ans
            if [[ ! "$ans" =~ ^[Yy]$ ]]; then
                echo "❌ Cancelled."
                return 1
            fi
        fi
        
        # --- SVG Special Handling (Last Frame for Animated SVGs) ---
        local ext="${input##*.}"
        # Convert to lowercase safely (macOS default bash is 3.2, lacks ${var,,})
        ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
        if [[ "$ext" == "svg" ]]; then
             # Check for animation keywords (CSS or SMIL)
             if grep -q -E "<animate|@keyframes" "$input"; then
                  echo "🎥 Animated SVG detected. Baking final frame (Static Processing)..."
                  
                  local temp_svg="${input%.*}_baked_static.svg"
                  
                  # 1. Bake Animation End-State using Python (No Browser)
                  if python3 "$LIB_DIR/python/svg_bake.py" "$input" "$temp_svg"; then
                       echo "✅ Animation baked successfully."
                       input="$temp_svg" # Switch input to baked version
                  else
                       echo "⚠️  Static baking failed. Using original file."
                  fi
                  
                  # Cleanup trap (ensure temp file is removed on exit/return)
                  # Simple deferred removal logic for this block:
                  # We will remove it after conversion at the end of function if it matches temp name
             fi
        fi
        # -----------------------------------------------------------
        
        if [[ "$option" == "circle" ]]; then
            apply_circle_mask "$input" "$size" "$output" "$background"
        else
            echo "🔄 Converting to $format (Size: $size px)..."
            
            if [[ "$cmd" == "sips" ]]; then
                # Sips limited support
                sips -s format "$format" --resampleHeightWidthMax "$size" "$input" --out "$output" > /dev/null
            else
                # Magick: Use parsed background (default: none)
                # -resize: geometry (width if just number)
                $cmd -background "$background" "$input" -resize "$size" "$output"
            fi
        fi
        
        # Cleanup baked file if it exists
        if [[ "$input" == *"_baked_static.svg"* ]]; then
            rm -f "$input"
        fi
        
        if [[ $? -eq 0 ]]; then
            echo "✅ Saved: $output"
        else
            echo "❌ Conversion failed."
            return 1
        fi
    }

    do_round() {
        local input="$1"
        local radius="${2:-20}"
        
        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        
        # Output filename: force png for transparency
        local base="${input%.*}"
        local output="${base}_rounded_${radius}px.png"
        
        # Validation for radius
        if [[ ! "$radius" =~ ^[0-9]+$ ]]; then
            echo "❌ Error: Radius must be an integer."
            return 1
        fi

        echo "🎨 Rounding corners (Radius: ${radius}px)..."
        
        if [[ "$cmd" == "sips" ]]; then
             echo "⚠️ Sips does not support corner rounding."
             return 1
        else
            # Magick: Clean Canvas Masking Strategy
            # 1. auto-orient + repage (Normalize)
            # 2. Clone + Transparent Canvas + Draw White RoundRect (Mask creation)
            # 3. DstIn Composite (Apply Mask)
            $cmd "$input" \
                -auto-orient +repage \
                -format png -alpha on \
                \( +clone -alpha transparent -fill white -draw "roundrectangle 0,0 %[fx:w-1],%[fx:h-1] $radius,$radius" \) \
                -compose DstIn -composite \
                "$output"
        fi
        
        if [[ $? -eq 0 ]]; then
            echo "✅ Saved: $output"
        else
            echo "❌ Rounding failed."
            return 1
        fi
    }

    do_rotate() {
        local input="$1"
        local angle="$2"

        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        if [[ -z "$angle" ]]; then echo "❌ Angle required (e.g. 90, -90)."; return 1; fi

        local base="${input%.*}"
        local output="${base}_rotated_${angle}.${input##*.}"

        echo "🔄 Rotating image by ${angle} degrees..."

        if [[ "$cmd" == "sips" ]]; then
             sips -r "$angle" "$input" --out "$output" > /dev/null
        else
            $cmd "$input" -rotate "$angle" "$output"
        fi

        if [[ $? -eq 0 ]]; then
            echo "✅ Saved: $output"
        else
            echo "❌ Rotation failed."
            return 1
        fi
    }

    # --- Router ---

    local action="$1"
    
    if [[ "$action" == "resize" ]]; then
        shift; do_resize "$@"
    elif [[ "$action" == "crop" ]]; then
        shift; do_crop "$@"
    elif [[ "$action" == "round" ]]; then
        shift; do_round "$@"
    elif [[ "$action" == "pad" ]]; then
        shift; do_pad "$@"
    elif [[ "$action" == "rotate" ]]; then
        shift; do_rotate "$@"
    elif [[ "$action" == "convert" ]]; then
        shift; do_convert "$@"
    elif [[ "$action" == "extend" ]]; then
        shift
        # Get script dir relative to this function logic if needed, but assuming LIB_DIR is available
        # LIB_DIR is inherited from main script 'amir'
        local EXTEND_SCRIPT="$LIB_DIR/commands/extend.sh"
        if [[ -f "$EXTEND_SCRIPT" ]]; then
            "$EXTEND_SCRIPT" "$@"
        else
            echo "❌ Error: extend.sh not found."
            return 1
        fi
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
        echo "  amir img resize  <file> <size|preset> [circle]   (Scale & opt. Circle Crop)"
        echo "  amir img crop    <file> <size|preset> <g>        (Fill & Crop, g=1-9)"
        echo "  amir img round   <file> [radius]                 (Round corners, def: 20px)"
        echo "  amir img rotate  <file> <angle>                  (Rotate image)"
        echo "  amir img pad     <file> <size|preset> [color]    (Fit & Pad, def: white)"
        echo "  amir img convert <file> [fmt] [size|preset] [circle] (Convert & opt. Circle)"
        echo "  amir img extend  -i <file> [opts]                (Extend borders)"
        echo ""
        echo "Presets:"
        echo "  yt-banner    : 2560x1440"
        echo "  yt-logo      : 800x800"
        echo "  yt-watermark : 150x150"
        return 1
    fi
}