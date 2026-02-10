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
        local input=""
        local size=""
        local gravity="Center"
        local smart=false

        # Argument Parsing Loop
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --smart) 
                    smart=true
                    shift 
                    ;;
                -g|--gravity) 
                    gravity="$2"
                    shift 2 
                    ;;
                *) 
                    if [[ -z "$input" ]]; then 
                        input="$1"
                        shift
                    elif [[ -z "$size" && "$smart" == "false" ]]; then 
                        # Only consume size if not smart mode (smart mode fits to content)
                        size=$(parse_size "$1")
                        shift
                    else 
                        shift
                    fi 
                    ;;
            esac
        done

        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi

        # --- Smart Crop Logic ---
        if [[ "$smart" == true ]]; then
            echo "🧠 Detecting subject and cropping smart..."
            local python_script="${LIB_DIR}/python/smart_crop.py"
            
            local output="${input%.*}_smart.png"
            
            # Absolute paths for robustness
            local abs_input=$(cd "$(dirname "$input")" && pwd)/$(basename "$input")
            local abs_output_dir=$(cd "$(dirname "$output")" && pwd)
            local abs_output="${abs_output_dir}/$(basename "$output")"

            # Execute Python Script via UV
            uv run --with opencv-python --with numpy "$python_script" "$abs_input" "$abs_output" "20"
            
            if [[ $? -eq 0 ]]; then
                echo "✅ Smart crop successful: $output"
                [[ "$OSTYPE" == "darwin"* ]] && open "$output"
                return 0
            else
                echo "❌ Smart crop failed (Fallback to manual? No size provided)."
                return 1
            fi
        fi

        # --- Standard Logic ---
        if [[ -z "$size" ]]; then echo "❌ Size required for manual crop."; return 1; fi
        
        local width=$(echo $size | cut -dx -f1)
        local height=$(echo $size | cut -dx -f2)
        local output="${input%.*}_crop_${width}x${height}.${input##*.}"
        
        local g=$(get_gravity "$gravity") # Resolve gravity string/code
        echo "✂️  Cropping (Fill & Cut) with gravity: $g..."

        if [[ "$cmd" == "sips" ]]; then
             sips -Z $width "$input" --out "$output" > /dev/null
             sips --cropToHeightWidth $height $width "$output" > /dev/null
        else
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
        local out_spec="${3:-png}" # Can be format (jpg) or full filename
        
        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        
        # Validation for radius
        if [[ ! "$radius" =~ ^[0-9]+$ ]]; then
            echo "❌ Error: Radius must be an integer."
            return 1
        fi

        # Determine Output Filename
        local output=""
        if [[ "$out_spec" == *"."* ]]; then
            output="$out_spec"
        else
            # It's a format (e.g. "jpg" or "png")
            local base="${input%.*}"
            output="${base}_rounded_${radius}px.${out_spec#.}"
        fi
        
        local out_ext="${output##*.}"
        local out_ext_upper=$(echo "$out_ext" | tr '[:lower:]' '[:upper:]')
        echo "🎨 Rounding corners (Radius: ${radius}px) -> $out_ext_upper..."
        
        if [[ "$cmd" == "sips" ]]; then
             echo "⚠️ Sips does not support corner rounding."
             return 1
        else
            # Verified Robust Strategy: CopyOpacity
            # This strictly separates Alpha Channel from Color Channels, preventing color bleed/whiteout.
            local out_ext="${output##*.}"
            out_ext=$(echo "$out_ext" | tr '[:upper:]' '[:lower:]')

            # 1. Start with Input (Color Preserved)
            # 2. Setup Alpha Channel
            # 3. Create Mask (Black Bg = Transparent, White Shape = Opaque)
            # 4. Copy Mask to Alpha (CopyOpacity)
            
            local flatten_arg=""
            if [[ "$out_ext" == "jpg" || "$out_ext" == "jpeg" ]]; then
                flatten_arg="-background white -alpha remove -alpha off"
            fi

            $cmd "$input" -auto-orient +repage \
                -alpha set \
                \( +clone -fill black -colorize 100 -fill white \
                   -draw "roundrectangle 0,0 %[fx:w-1],%[fx:h-1] $radius,$radius" \) \
                -alpha off -compose CopyOpacity -composite \
                $flatten_arg \
                "$output"
        fi
        
        if [[ $? -eq 0 ]]; then
            echo "✅ Saved: $output"
        else
            echo "❌ Rounding failed."
            return 1
        fi
    }

    do_stack() {
        local gap=20  # Default gap in pixels (reduced from 50)
        local bg_color="white"
        local files=()
        local output=""
        local paper_size=""
        local deskew=false
        
        # Helper: Get paper size (bash 3.2 compatible - no associative arrays)
        get_paper_size() {
            case "$1" in
                a4|A4) echo "1240x1754" ;;   # 210x297mm at 150dpi
                b5|B5) echo "1039x1476" ;;   # 176x250mm at 150dpi
                *) echo "" ;;
            esac
        }
        
        # Parse arguments
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -g|--gap)
                    gap="$2"
                    shift 2
                    ;;
                -bg|--background)
                    bg_color="$2"
                    shift 2
                    ;;
                -o|--output)
                    output="$2"
                    shift 2
                    ;;
                -p|--paper)
                    paper_size="$2"
                    shift 2
                    ;;
                --deskew)
                    deskew=true
                    shift
                    ;;
                *)
                    if [[ -f "$1" ]]; then
                        files+=("$1")
                    fi
                    shift
                    ;;
            esac
        done
        
        if [[ ${#files[@]} -lt 2 ]]; then
            echo "❌ Error: At least 2 image files required."
            echo "Usage: amir img stack <file1> <file2> [...] [-g gap] [-bg color] [-o output] [-p a4|b5] [--deskew]"
            return 1
        fi
        
        # Default output name with option suffixes
        if [[ -z "$output" ]]; then
            local base="${files[0]%.*}"
            local suffix="_stacked"
            
            # Add option indicators to filename
            if [[ "$deskew" == true ]]; then
                suffix="${suffix}_deskew"
            fi
            if [[ -n "$paper_size" ]]; then
                suffix="${suffix}_${paper_size}"
            fi
            if [[ "$gap" != "20" ]]; then
                suffix="${suffix}_g${gap}"
            fi
            
            output="${base}${suffix}.jpg"
        fi
        
        echo "📚 Stacking ${#files[@]} images (gap: ${gap}px, bg: $bg_color)..."
        
        if [[ "$cmd" == "sips" ]]; then
            echo "⚠️ Sips does not support image stacking. Install ImageMagick."
            return 1
        fi
        
        # Build processing options
        local process_opts="-auto-orient"  # Always fix EXIF rotation
        
        if [[ "$deskew" == true ]]; then
            process_opts="$process_opts -deskew 40%"
            echo "   📐 Deskew enabled"
        fi
        
        # Get target size if paper size specified
        local resize_opt=""
        local target_size=$(get_paper_size "$paper_size")
        if [[ -n "$target_size" ]]; then
            resize_opt="-resize ${target_size}"
            echo "   📄 Resizing to $paper_size ($target_size)"
        fi
        
        # Build smush command with auto-orient and optional processing
        # Note: resize is AFTER smush so final stacked image is resized
        $cmd -background "$bg_color" \
            "${files[@]}" \
            $process_opts \
            -gravity center -smush $gap \
            $resize_opt \
            -quality 95 \
            "$output"
        
        if [[ $? -eq 0 ]]; then
            echo "✅ Saved: $output"
        else
            echo "❌ Stacking failed."
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

    do_upscale() {
        # echo "DEBUG: do_upscale args: '$@'"
        local input=""
        local scale=$(get_config "img" "upscale_scale" "4")
        local model=$(get_config "img" "upscale_model" "ultrasharp")
        local output=""
        
        # Robust Shift-Based Parsing
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -s|--scale)
                    if [[ -n "$2" && ! "$2" =~ ^- ]]; then
                        scale="$2"
                        shift 2
                    else
                        shift
                    fi
                    ;;
                -m|--model)
                    if [[ -n "$2" && ! "$2" =~ ^- ]]; then
                        model="$2"
                        shift 2
                    else
                        shift
                    fi
                    ;;
                -o|--output)
                    if [[ -n "$2" && ! "$2" =~ ^- ]]; then
                        output="$2"
                        shift 2
                    else
                        shift
                    fi
                    ;;
                -*)
                    # Unknown flag, skip
                    shift
                    ;;
                *)
                    # Positional input
                    if [[ -z "$input" ]]; then
                        input="$1"
                    fi
                    shift
                    ;;
            esac
        done
        
        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found: $input"; return 1; fi
        
        local tool_dir="$HOME/.amir-cli/tools/realesrgan"
        local tool_bin="$tool_dir/realesrgan-cli"
        local models_dir="$tool_dir/models"
        
        if [[ ! -f "$tool_bin" ]]; then
            echo "❌ Real-ESRGAN tool not found in $tool_bin"
            return 1
        fi
        
        local base="${input%.*}"
        local ext="${input##*.}"
        
        local suffix="_upscaled_${scale}x_${model}"
        if [[ "$scale" == "1" ]]; then
            suffix="_enhanced_1x_${model}"
        fi
        
        if [[ -z "$output" ]]; then
            output="${base}${suffix}.${ext}"
        fi
        
        echo "🚀 Enhancing image using $model model..."
        
        local ai_scale="4"
        local tmp_output="${output}.tmp.${ext}"
        
        # Run Real-ESRGAN with a surgically clean progress filter
        # Hides all metadata noise and only updates the percentage on one line (\r)
        # Using a more robust regex and explicit flushing
        "$tool_bin" -i "$input" -o "$tmp_output" -s "$ai_scale" -n "$model-4x" -m "$models_dir" -t 0 2>&1 | \
            python3 -u -c 'import sys,re; [print(f"\r   ⏳ {m.group(1)}", end="", flush=True) for l in sys.stdin for m in [re.search(r"([0-9.]+\s*%)", l)] if m]'
        local exit_code=${PIPESTATUS[0]}
        
        # Clear the progress line
        echo -ne "\r\033[K"
        
        if [[ $exit_code -eq 0 && -f "$tmp_output" ]]; then
             # proceed with resizing if needed
             if [[ "$scale" == "1" ]]; then
                 echo "   📉 Finalizing 1x enhancement (Downsampling 25%)..."
                 magick "$tmp_output" -resize 25% "$output"
                 rm "$tmp_output"
             elif [[ "$scale" == "2" ]]; then
                  echo "   📉 Finalizing 2x upscale (Downsampling 50%)..."
                  magick "$tmp_output" -resize 50% "$output"
                  rm "$tmp_output"
             elif [[ "$scale" == "3" ]]; then
                  echo "   📉 Finalizing 3x upscale (Downsampling 75%)..."
                  magick "$tmp_output" -resize 75% "$output"
                  rm "$tmp_output"
             else
                  # 4x
                  mv "$tmp_output" "$output"
             fi
             echo "✅ Saved: $output"
             return 0
        else
             echo "❌ AI Upscale failed or output file missing."
             # Cleanup if partial
             [[ -f "$tmp_output" ]] && rm "$tmp_output"
             return 1
        fi
    }

    do_lab() {
        local input=""
        local scale=$(get_config "img" "upscale_scale" "4")
        local requested_model=$(get_config "img" "upscale_model" "ultrasharp")
        
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -s|--scale) scale="$2"; shift 2 ;;
                -m|--model) requested_model="$2"; shift 2 ;;
                *) input="$1"; shift ;;
            esac
        done
        
        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        
        local base=$(basename "$input")
        local base_noext="${base%.*}"
        local root_lab_dir="lab_${base_noext}"
        
        mkdir -p "$root_lab_dir"
        
        # Robust absolute path resolution (Bash-native)
        local abs_lab_dir="$(cd "$root_lab_dir" && pwd)"
        
        echo "📍 Target Laboratory: $abs_lab_dir"
        
        local models=("$requested_model")
        if [[ "$requested_model" == "all" ]]; then
            models=("ultrasharp" "digital-art" "high-fidelity" "remacri" "ultramix-balanced" "upscayl-lite" "upscayl-standard")
        fi

        # Pure ImageMagick Optimization: If scale is 1, we don't need AI models.
        if [[ "$scale" == "1" ]]; then
            models=("native")
            echo "✨ Pure ImageMagick Mode enabled (No AI Upscale)."
        else
            [[ "$requested_model" == "all" ]] && echo "🧪 Multi-model mode enabled. Testing ${#models[@]} models..."
        fi
        
        # Pre-process models (AI Upscale) if scale > 1
        if [[ "$scale" != "1" ]]; then
            local upscale_dir="${root_lab_dir}/_upscaled"
            for current_model in "${models[@]}"; do
                echo "🚀 [$current_model] Pre-processing with AI Upscale ($scale x)..."
                mkdir -p "$upscale_dir"
                local upscaled_file="${upscale_dir}/upscaled_${scale}x_${current_model}.png"
                do_upscale -s "$scale" -m "$current_model" -o "$upscaled_file" "$input"
                if [[ $? -ne 0 ]]; then
                    echo "❌ [$current_model] Pre-scaling failed. Using original."
                fi
            done
        fi

        # Variation Progress Tracking
        local progress_idx=0
        local total_variations=60 # Fixed for now as we have 60 variations
        local total_steps=$(( total_variations * ${#models[@]} ))
        
        _print_lab_progress() {
            local current=$1
            local total=$2
            local percent=$(( current * 100 / total ))
            local filled=$(( percent / 5 ))
            local empty=$(( 20 - filled ))
            local bar=""
            for ((i=0; i<filled; i++)); do bar="${bar}█"; done
            for ((i=0; i<empty; i++)); do bar="${bar}░"; done
            printf "\r   🧪 Lab Progress: |%s| %d%% (%d/%d)" "$bar" "$percent" "$current" "$total"
        }

        # Reorganized Variation Engine: Loop through Alg -> then Models
        _run_variations() {
            local var_name="$1"
            shift 1
            
            # Smart Categorization:
            # If scale is 1, we put all 60 files in one folder named 'lab'.
            # If scale > 1 (multi-model), we use subfolders per algorithm (420+ files).
            local var_dir=""
            if [[ "$scale" == "1" ]]; then
                var_dir="${root_lab_dir}/lab"
            else
                var_dir="${root_lab_dir}/${var_name}"
            fi
            mkdir -p "$var_dir"

            for m in "${models[@]}"; do
                local m_input="$input"
                if [[ "$m" != "native" ]]; then
                    m_input="${root_lab_dir}/_upscaled/upscaled_${scale}x_${m}.png"
                fi
                [[ ! -f "$m_input" ]] && m_input="$input"
                
                local output_file=""
                if [[ "$scale" == "1" ]]; then
                    output_file="${var_dir}/${var_name}.jpg"
                else
                    output_file="${var_dir}/${m}.jpg"
                fi

                magick "$m_input" "$@" "$output_file"
                
                ((progress_idx++))
                _print_lab_progress "$progress_idx" "$total_steps"
            done
        }

        echo "🔬 Generating 60 enhancement combinations for ${#models[@]} models..."
            
            # Standard Series
            _run_variations "01_norm_only" -normalize
            _run_variations "02_auto_level" -auto-level
            _run_variations "03_auto_gamma" -auto-gamma
            _run_variations "04_norm_sharp1.0" -normalize -sharpen 0x1.0
            _run_variations "05_norm_sharp1.5" -normalize -sharpen 0x1.5
            _run_variations "06_norm_sharp2.0" -normalize -sharpen 0x2.0
            _run_variations "07_lev10-90_sharp1.5" -normalize -level 10%,90% -sharpen 0x1.5
            _run_variations "08_lev5-95_sharp1.5" -normalize -level 5%,95% -sharpen 0x1.5
            _run_variations "09_lev2-98_sharp1.0" -normalize -level 2%,98% -sharpen 0x1.0
            _run_variations "10_unsharp_soft" -normalize -unsharp 0x0.5+0.5+0
            _run_variations "11_unsharp_std" -normalize -unsharp 0x1+1+0.05
            _run_variations "12_unsharp_hard" -normalize -unsharp 0x2+1.5+0.1
            _run_variations "13_bright+10_cont+20" -brightness-contrast 10x20
            _run_variations "14_bright-10_cont+40" -brightness-contrast -10x40
            _run_variations "15_sigmoidal_contrast" -sigmoidal-contrast 5x50%
            _run_variations "16_adaptive_blur" -adaptive-sharpen 0x2
            _run_variations "17_local_contrast" -unsharp 0x5+1.0+0
            _run_variations "18_clahe_lite" -clahe 25x25%+64+3
            _run_variations "19_doc_threshold" -white-threshold 90% -black-threshold 10% -sharpen 0x1.5
            _run_variations "20_final_boost" -normalize -level 5%,95% -unsharp 0x1+1+0.05 -quality 98
            
            # --- Advanced Series ---
            _run_variations "21_despeckle" -despeckle
            _run_variations "22_lat_shadow_removal" -lat 25x25+10%
            _run_variations "23_morph_dilate_thicken" -morphology Dilate Disk:1
            _run_variations "24_morph_erode_thin" -morphology Erode Disk:1
            _run_variations "25_text_cleaner_sim" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x100 \) -compose Divide -composite -linear-stretch 1%x1%
            _run_variations "26_gamma_lighten" -gamma 1.2
            _run_variations "27_gamma_darken" -gamma 0.8
            _run_variations "28_median_denoise" -statistic median 3x3
            _run_variations "29_posterize_6" -posterize 6
            _run_variations "30_monochrome_lat" -colorspace gray -lat 20x20+10%
            
            # --- Heritage Classic Series ---
            _run_variations "31_heritage_bg_clean" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x20 \) -compose Divide -composite
            _run_variations "32_heritage_bg_flatten" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x50 \) -compose Divide -composite -normalize
            _run_variations "33_heritage_ink_thicken" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x20 \) -compose Divide -composite -morphology Dilate Disk:1
            _run_variations "34_heritage_ink_darken" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x30 \) -compose Divide -composite -level 20%,80%
            _run_variations "35_heritage_manuscript_bw" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x25 \) -compose Divide -composite -lat 25x25+5%
            _run_variations "36_heritage_sauvola_sim" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x15 \) -compose Divide -composite -threshold 50% -despeckle
            _run_variations "37_heritage_bleed_removal" -colorspace gray -level 15%,85% -sharpen 0x2
            _run_variations "38_heritage_handwritten_soft" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x20 \) -compose Divide -composite -unsharp 0x5+1.0+0
            _run_variations "39_heritage_script_restore" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x20 \) -compose Divide -composite -morphology Close Disk:1 -sharpen 0x1
            _run_variations "40_heritage_final_archive" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x30 \) -compose Divide -composite -normalize -sharpen 0x1.5

            # --- Heritage Pro Series ---
            _run_variations "41_hpro_bg_clean_p100" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x100 \) -compose Divide -composite -normalize
            _run_variations "42_hpro_bg_flatten_p200" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x200 \) -compose Divide -composite -linear-stretch 1x1%
            _run_variations "43_hpro_dog_text_isolation" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x1 \) \( -clone 0 -blur 0x2 \) -compose minus -composite -negate -normalize
            _run_variations "44_hpro_sauvola_clean" -colorspace gray -level 10%,90% -lat 25x25+10%
            _run_variations "45_hpro_ink_restore_close" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x100 \) -compose Divide -composite -morphology Close Disk:1
            _run_variations "46_hpro_shadow_removal_lat" -colorspace gray -lat 50x50+5%
            _run_variations "47_hpro_contrast_stretch" -colorspace gray -linear-stretch 5x5%
            _run_variations "48_hpro_script_focus" -colorspace gray -statistic median 3x3 -unsharp 0x5+1.0+0
            _run_variations "49_hpro_binarize_adaptive" -colorspace gray -negate -lat 20x20+10% -negate
            _run_variations "50_hpro_master_archive" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x150 \) -compose Divide -composite -normalize -sharpen 0x1

            # --- Forensic Series ---
            _run_variations "51_forensic_k_isolator" -colorspace CMYK -separate -delete 0,1,2 -negate -normalize
            _run_variations "52_forensic_red_pass" -channel R -separate -normalize
            _run_variations "53_forensic_highpass_conv" -colorspace gray -convolve "-1,-1,-1,-1,8,-1,-1,-1,-1" -normalize
            _run_variations "54_forensic_dog_precise" -colorspace gray -respect-parenthesis \( -clone 0 -blur 0x1 \) \( -clone 0 -blur 0x1.5 \) -compose minus -composite -negate -normalize
            _run_variations "55_forensic_adaptive_binarize" -colorspace gray -negate -lat 15x15+5% -negate
            _run_variations "56_forensic_ink_extract" -fuzz 20% -fill white +opaque black -normalize
            _run_variations "57_forensic_edge_enhance" -colorspace gray -edge 1 -negate -normalize
            _run_variations "58_forensic_contrast_crush" -colorspace gray -contrast-stretch 2x98% -sharpen 0x3
            _run_variations "59_forensic_bilateral_denoise" -statistic median 3x3 -unsharp 0x2+1+0.05
            _run_variations "60_forensic_ultimate_k" -colorspace CMYK -separate -delete 0,1,2 -negate -lat 25x25+10%

        echo -e "\n\n✅ Success! All Variations saved to:"
        local final_out_dir="$abs_lab_dir"
        [[ "$scale" == "1" ]] && final_out_dir="${abs_lab_dir}/lab"
        echo "👉 $final_out_dir"
        
        # Automatically open the folder for the user (macOS specific)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            open "$final_out_dir"
        fi
    }

    do_scan() {
        local input=""
        local output=""
        local requested_mode=""
        
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --fast) requested_mode="fast"; shift ;;
                --pro) requested_mode="pro"; shift ;;
                --ocr) requested_mode="ocr"; shift ;;
                --py|--python) requested_mode="py"; shift ;;
                --all) requested_mode="all"; shift ;;
                -o|--output) output="$2"; shift 2 ;;
                *) input="$1"; shift ;;
            esac
        done
        
        if [[ -z "$input" || ! -f "$input" ]]; then echo "❌ File not found."; return 1; fi
        
        local base=$(basename "$input")
        local base_noext="${base%.*}"
        local root_scan_dir="lab_${base_noext}"
        local scan_dir="${root_scan_dir}/scans"
        
        mkdir -p "$scan_dir"
        local abs_scan_dir="$(cd "$scan_dir" && pwd)"
        
        # Internal helper to execute specific methods
        _exec_scan_method() {
            local method="$1"
            local m_output="${scan_dir}/${base_noext}_scan_${method}.png"
            
            case "$method" in
                "fast")
                    echo "� Running Quick Scan (Method 1)..."
                    magick "$input" -colorspace Gray -auto-level -contrast-stretch 0 "$m_output"
                    ;;
                "pro")
                    echo "🟡 Running Professional Scan (Method 2)..."
                    magick "$input" -colorspace Gray \
                        \( +clone -blur 0x150 \) -compose Divide -composite \
                        -normalize -level 10%,90% -white-threshold 90% -despeckle \
                        "$m_output"
                    ;;
                "ocr")
                    echo "🔵 Running OCR-Grade Scan (Method 3)..."
                    magick "$input" -colorspace Gray \
                        \( +clone -blur 0x200 \) -compose Divide -composite \
                        -normalize -white-threshold 95% -despeckle \
                        "$m_output"
                    ;;
                "py")
                    echo "🐍 Running High-Fidelity Python Scan (OpenCV)..."
                    local python_script="${LIB_DIR}/python/doc_scan.py"
                    uv run --with opencv-python "$python_script" "$input" "$m_output"
                    ;;
            esac
        }

        if [[ -n "$requested_mode" && "$requested_mode" != "all" ]]; then
            _exec_scan_method "$requested_mode"
        else
            echo "🧪 Comparison Mode: Generating all 4 scanning levels..."
            _exec_scan_method "fast"
            _exec_scan_method "pro"
            _exec_scan_method "ocr"
            _exec_scan_method "py"
        fi
            
        if [[ $? -eq 0 ]]; then
            echo -e "\n✅ Success! Scans are ready for comparison in:"
            echo "👉 $abs_scan_dir"
            [[ "$OSTYPE" == "darwin"* ]] && open "$abs_scan_dir"
        else
            echo "❌ Scan processing failed."
            return 1
        fi
    }

    do_deskew() {
        # Check for batch mode:
        # 1. More than 2 arguments
        # 2. Exactly 2 arguments, but the second one is an existing file (implies batch of 2)
        local is_batch=0
        if [[ $# -gt 2 ]]; then
            is_batch=1
        elif [[ $# -eq 2 && -f "$2" ]]; then
            is_batch=1
        fi

        if [[ $is_batch -eq 1 ]]; then
            echo "📐 Batch Deskew Mode detected. Processing $# files..."
            for file in "$@"; do
                if [[ -f "$file" ]]; then
                   do_deskew "$file" # Recursive call for single file auto-naming
                else
                   echo "⚠️ Skipped (not found): $file"
                fi
            done
            return 0
        fi

        # Single file mode (logical fall-through)
        local input="$1"
        local output="$2"
        
        if [[ -z "$input" ]]; then echo "❌ Input file required."; return 1; fi
        if [[ ! -f "$input" ]]; then echo "❌ File not found: $input"; return 1; fi
        
        # Default output name if not provided
        if [[ -z "$output" ]]; then
            local dir=$(dirname "$input")
            local base=$(basename "$input")
            local name="${base%.*}"
            local ext="${base##*.}"
            output="${dir}/${name}_deskew.${ext}"
        fi
        
        echo "📐 Deskewing: $input -> $output"
        magick "$input" -deskew 40% "$output"
        echo "✅ Saved as: $output"
    }

    do_burst() {
        local recursive=0
        local inputs=()
        local output=""

        # 1. Parse Options
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -r|--recursive) recursive=1; shift ;;
                -o|--output) output="$2"; shift 2 ;;
                *) inputs+=("$1"); shift ;;
            esac
        done

        if [[ ${#inputs[@]} -eq 0 ]]; then
            echo "Usage: amir img burst <files|dirs...> [-o output] [-r]"
            return 1
        fi

        # 2. Heuristic for output if not provided via -o
        # If the last input doesn't exist AND has an extension, treat as output
        if [[ -z "$output" ]]; then
            local last_input="${inputs[${#inputs[@]}-1]}"
            if [[ ! -e "$last_input" && "$last_input" == *.* ]]; then
                output="$last_input"
                unset 'inputs[${#inputs[@]}-1]'
            fi
        fi

        # 3. Resolve all files
        local final_files=()
        for item in "${inputs[@]}"; do
            if [[ -d "$item" ]]; then
                # Find images in directory
                if [[ $recursive -eq 1 ]]; then
                    # Recursive find
                    while IFS= read -r f; do
                        final_files+=("$f")
                    done < <(find "$item" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.tiff" \) | sort)
                else
                    # Non-recursive find (maxdepth 1)
                    while IFS= read -r f; do
                        final_files+=("$f")
                    done < <(find "$item" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.tiff" \) | sort)
                fi
            elif [[ -f "$item" ]]; then
                final_files+=("$item")
            else
                echo "⚠️ Warning: Input not found or not a valid image/dir: $item"
            fi
        done

        if [[ ${#final_files[@]} -lt 2 ]]; then
            echo "❌ Error: At least 2 image files required for burst reconstruction (found ${#final_files[@]})."
            return 1
        fi

        # 4. Default output if still empty
        if [[ -z "$output" ]]; then
            local first_base=$(basename "${final_files[0]}")
            local name="${first_base%.*}"
            local ext="${first_base##*.}"
            output="reconstructed_${name}.${ext}"
        fi

        # Resolve absolute path for clarity
        local abs_output=$(python3 -c "import os; print(os.path.abspath('$output'))")

        echo "📸 Multi-frame Burst Mode: Aligning and merging ${#final_files[@]} frames..."
        echo "📍 Target Output: $abs_output"
        [[ $recursive -eq 1 ]] && echo "🔍 Recursive search enabled."
        
        # Verify and install deps if needed (handled by uv)
        # Python script is in lib/python/mfsr.py
        local MFSR_SCRIPT="$LIB_DIR/python/mfsr.py"
        
        # Use uv run for automatic dependency management
        uv run --with opencv-python --with numpy "$MFSR_SCRIPT" "$output" "${final_files[@]}"
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
    elif [[ "$action" == "stack" ]]; then
        shift; do_stack "$@"
    elif [[ "$action" == "upscale" ]]; then
        shift; do_upscale "$@"
    elif [[ "$action" == "lab" ]]; then
        shift; do_lab "$@"
    elif [[ "$action" == "scan" ]]; then
        shift; do_scan "$@"
    elif [[ "$action" == "convert" ]]; then
        shift; do_convert "$@"
    elif [[ "$action" == "deskew" ]]; then
        shift; do_deskew "$@"
    elif [[ "$action" == "burst" ]]; then
        shift; do_burst "$@"
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
        echo "  amir img upscale <file> [scale] [model]          (AI-Upscale, def: 4x, ultrasharp)"
        echo "  amir img lab     <file> [-s scale] [-m model]    (Generate 60/420 enhancement combinations)"
        echo "  amir img scan    <file> [--bw] [-o output]       (Professional Doc Cleanup: White BG, Black Ink)"
        echo "  amir img round   <file> [radius] [fmt|out]       (Round corners, def: 20px, PNG/JPG)"
        echo "  amir img rotate  <file> <angle>                  (Rotate image)"
        echo "  amir img pad     <file> <size|preset> [color]    (Fit & Pad, def: white)"
        echo "  amir img convert <file> [fmt] [size|preset] [circle] (Convert & opt. Circle)"
        echo "  amir img stack   <file1> <file2> [...] [-g gap] [-p a4|b5] [--deskew]"
        echo "  amir img extend  -i <file> [opts]                (Extend borders)"
        echo "  amir img deskew  <file> [output]                 (Auto-straighten image)"
        echo "  amir img burst   <files...> [output]             (Multi-frame Reconstruction)"
        echo ""
        echo "Presets:"
        echo "  yt-banner    : 2560x1440"
        echo "  yt-logo      : 800x800"
        echo "  yt-watermark : 150x150"
        return 1
    fi
}