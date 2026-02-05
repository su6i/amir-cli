#!/bin/bash

# A4 Dimensions at 300 DPI: 2480 x 3508 pixels

run_pdf() {
    # 1. Dependency Check
    local cmd="magick"
    if ! command -v magick &> /dev/null; then
        if command -v convert &> /dev/null; then
            cmd="convert"
        else
            echo "❌ Error: ImageMagick (magick) is not installed."
            return 1
        fi
    fi

    # Source Config
    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local LIB_DIR="$(dirname "$SCRIPT_DIR")"
    if [[ -f "$LIB_DIR/config.sh" ]]; then
        source "$LIB_DIR/config.sh"
        init_config
    else
        # Fallback if config.sh is missing
        get_config() { echo "$3"; }
    fi

    # 2. Argument Parsing
    local inputs=()
    local output=""
    # Load defaults from Config
    local compression_quality=$(get_config "pdf" "quality" "75")
    local compression_resize=$(get_config "pdf" "resize" "75")
    
    # Ensure values are integers (simple validation)
    [[ "$radius" =~ ^[0-9]+$ ]] || radius=10
    [[ "$rotate_angle" =~ ^-?[0-9]+$ ]] || rotate_angle=0
    [[ "$compression_quality" =~ ^[0-9]+$ ]] || compression_quality=75
    [[ "$compression_resize" =~ ^[0-9]+$ ]] || compression_resize=75
    
    local multi_page=false
    
    while [[ $# -gt 0 ]]; do
        key="$1"
        case $key in
            -o|--output)
                output="$2"
                shift; shift
                ;;
            --no-round|--square)
                radius=0
                shift
                ;;
            --radius)
                radius="$2"
                shift; shift
                ;;
            -r|--rotate)
                if [[ "$2" =~ ^-?[0-9]+$ ]]; then
                    rotate_angle="$2"
                    shift; shift
                else
                    # Fallback for old flag usage (toggle 90)
                    rotate_angle=90
                    shift
                fi
                ;;
            -q|--quality)
                compression_quality="$2"
                shift; shift
                ;;
            --resize)
                compression_resize="$2"
                shift; shift
                ;;
            --pages|--merge)
                multi_page=true
                shift
                ;;
            *)
                if [[ -f "$1" ]]; then
                    inputs+=("$1")
                else
                    echo "⚠️  Warning: File not found '$1', skipping."
                fi
                shift
                ;;
        esac
    done

    if [[ ${#inputs[@]} -eq 0 ]]; then
        echo "Usage: amir pdf <files...> [-o output.pdf] [options]"
        echo "   Combines images/PDFs into a single A4 page (Portrait)."
        echo "   --radius <px>    : Set corner radius (default 10)."
        echo "   -r <angle>       : Rotate images by angle (e.g. 90)."
        echo "   -q <quality>     : JPEG Quality for compressed version (default 75)."
        echo "   --resize <%>     : Resize percentage for compressed version (default 75)."
        echo "   --pages          : Create multi-page PDF (1 image per page) instead of collage."
        return 1
    fi
    
    # Auto-name output if default and input exists
    if [[ -z "$output" && -n "${inputs[0]}" ]]; then
        local base=$(basename "${inputs[0]}")
        local suffix=""
        if [[ "$rotate_angle" -ne 0 ]]; then
            suffix="_r${rotate_angle}"
        fi
        output="${base%.*}${suffix}.pdf"
    fi

    # Overwrite Protection
    local output_compressed="${output%.*}_compressed_q${compression_quality}.pdf"

    # Overwrite Protection (Checks both Main and Compressed output)
    if [[ -f "$output" || -f "$output_compressed" ]]; then
        local msg="⚠️  Output files already exist:"
        [[ -f "$output" ]] && msg+="\n    - $output"
        [[ -f "$output_compressed" ]] && msg+="\n    - $output_compressed"
        
        echo -e "$msg"
        echo -n "Overwrite? (y/N): "
        read -r ans
        if [[ ! "$ans" =~ ^[Yy]$ ]]; then
            echo "❌ Cancelled."
            return 1
        fi
    fi

    echo "📄 Composing ${#inputs[@]} file(s) into A4 PDF..."
    if [[ "$rotate_angle" -ne 0 ]]; then
        echo "🔄 Option: Rotating inputs by ${rotate_angle}°."
    fi
    if [[ "$radius" -gt 0 ]]; then
        echo "🎨 Option: Rounding corners (Radius: ${radius}px)."
    fi
    echo "🎯 Output: $output"

    # Refactored Logic: Process each file individually
    # density 300 is critical for high-quality PDF reading/writing
    local final_cmd=()
    final_cmd+=("-density" "300") 
    
    if [[ "$multi_page" == "false" ]]; then
        final_cmd+=("-size" "2480x3508" "xc:white")
        final_cmd+=("(")
    fi
    
    for img in "${inputs[@]}"; do
        final_cmd+=("(")
        
        if [[ "$multi_page" == "true" ]]; then
            # Multi-Page: Start with a Fresh A4 Canvas for this page
            final_cmd+=("-size" "2480x3508" "xc:white") 
            final_cmd+=("(")
        fi
        
        # Read the input file (handles PDF pages too)
        final_cmd+=("$img")
        
        # Respect EXIF Orientation - FIRST step is normalizing geometry
        final_cmd+=("-auto-orient" "+repage")

        # Apply Manual Rotation if requested
        if [[ "$rotate_angle" -ne 0 ]]; then
             final_cmd+=("-rotate" "$rotate_angle" "+repage")
        fi
        
        # Apply Rounding if requested
        if [[ "$radius" -gt 0 ]]; then
            final_cmd+=("-alpha" "on") # Ensure alpha channel exists
            
            # Create a separate, clean mask in memory
            final_cmd+=("(")
            final_cmd+=("+clone" "-alpha" "transparent") # Create blank transparent canvas of same size
            final_cmd+=("-fill" "white" "-draw" "roundrectangle 0,0 %[fx:w-1],%[fx:h-1] $radius,$radius")
            final_cmd+=(")")
            
            # Apply mask to the image (DstIn keeps only what's inside the drawing)
            final_cmd+=("-compose" "DstIn" "-composite")
        fi
        
        # Flatten onto white background (handles both alpha from rounding and original)
        final_cmd+=("-compose" "Over" "-background" "white" "-flatten")
        
        # Resize & Border or Fit to Page
        # Resize & Border or Fit to Page
        if [[ "$multi_page" == "true" ]]; then
             # Multi-Page: Resize to fit INSIDE A4 (leaving margin)
             final_cmd+=("-resize" "2400x3400>")
             final_cmd+=(")") # End Input Image Processing
             
             # Composite processed image onto the local A4 Canvas
             final_cmd+=("-gravity" "center" "-composite")
             final_cmd+=("+repage") 
        else
             # Collage: Resize to width, append later
             final_cmd+=("-resize" "2400x")
             final_cmd+=("-bordercolor" "white" "-border" "0x20")
        fi
             # Collage: Resize to width, append later
             final_cmd+=("-resize" "2400x")
             final_cmd+=("-bordercolor" "white" "-border" "0x20")
        fi
        
        final_cmd+=(")")
    done
    
    # Layout & Output
    if [[ "$multi_page" == "false" ]]; then
        final_cmd+=("-background" "white" "-append" "+repage")
        final_cmd+=("-resize" "2480x3508>" "+repage")
        final_cmd+=(")") # End of process group (Collage Canvas)
        
        final_cmd+=("-gravity" "center" "-composite")
    else
        # Multi-Page: Just end the sequence (Each item is now a full A4 image)
        final_cmd+=(")")
    fi
    final_cmd+=("-units" "PixelsPerInch") # Ensure density metadata is correct
    # Ensure HQ file uses high-quality JPEG compression instead of raw/deflate to save space
    final_cmd+=("-compress" "jpeg" "-quality" "100") 
    final_cmd+=("$output")

    echo "CMD: $cmd ${final_cmd[@]}"
    $cmd "${final_cmd[@]}"

    if [[ $? -eq 0 ]]; then
        echo "✅ HQ PDF Created: $output"
        
        # ---------------------------------------------------------
        # Post-Process: Generate Compressed Version
        # ---------------------------------------------------------
        # output_compressed defined above at start
        
        echo "🗜️  Generating Compressed Version (Resize: ${compression_resize}%, Quality: ${compression_quality})..."
        
        # Optimization Strategy:
        # Resize percent + JPEG Comp
        
        local compress_cmd=(
            "-density" "300"
            "$output"
            "-strip" # Remove metadata to save space
            "-resize" "${compression_resize}%"
            "-define" "jpeg:sampling-factor=1x1" 
            "-compress" "jpeg"
            "-quality" "$compression_quality"
            "$output_compressed"
        )
        
        $cmd "${compress_cmd[@]}"
            
        if [[ $? -eq 0 ]]; then
            local size_hq=$(ls -lh "$output" | awk '{print $5}')
            local size_lq=$(ls -lh "$output_compressed" | awk '{print $5}')
            echo "✅ Compressed PDF Created: $output_compressed"
            echo "📊 Stats: [HQ: $size_hq] ➡️  [LQ: $size_lq]"
        else
            echo "⚠️  Compression failed (HQ file preserved)."
        fi
        
    else
        echo "❌ PDF Creation Failed."
        return 1
    fi
}

run_pdf "$@"
