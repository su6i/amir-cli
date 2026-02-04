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
    local radius=$(get_config "pdf" "radius" "10")
    local rotate_angle=$(get_config "pdf" "rotate" "0")
    
    # Ensure values are integers (simple validation)
    [[ "$radius" =~ ^[0-9]+$ ]] || radius=10
    [[ "$rotate_angle" =~ ^-?[0-9]+$ ]] || rotate_angle=0
    
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
        echo "Usage: amir pdf <files...> [-o output.pdf] [--radius <px>] [-r <angle>]"
        echo "   Combines images/PDFs into a single A4 page (Portrait)."
        echo "   --radius <px> : Set corner radius (default 10). Use 0 or --no-round for square."
        echo "   -r <angle>    : Rotate images by angle (e.g. 90)."
        return 1
    fi
    
    # Auto-name output if default and input exists
    if [[ -z "$output" && -n "${inputs[0]}" ]]; then
        local base=$(basename "${inputs[0]}")
        output="${base%.*}.pdf"
    fi

    # Overwrite Protection
    if [[ -f "$output" ]]; then
        echo -n "⚠️  File '$output' already exists. Overwrite? (y/N): "
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
    final_cmd+=("-size" "2480x3508" "xc:white")
    final_cmd+=("(")
    
    for img in "${inputs[@]}"; do
        final_cmd+=("(")
        
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
        
        # Resize & Border
        # Resize to fit within A4 width (minus margins) - roughly 2400px wide
        final_cmd+=("-resize" "2400x")
        final_cmd+=("-bordercolor" "white" "-border" "0x20")
        
        final_cmd+=(")")
    done
    
    # Layout & Output
    final_cmd+=("-background" "white" "-append" "+repage")
    final_cmd+=("-resize" "2480x3508>" "+repage")
    final_cmd+=(")") # End of process group
    
    final_cmd+=("-gravity" "center" "-composite")
    final_cmd+=("-units" "PixelsPerInch") # Ensure density metadata is correct
    final_cmd+=("$output")

    $cmd "${final_cmd[@]}"

    if [[ $? -eq 0 ]]; then
        echo "✅ PDF Created Successfully!"
    else
        echo "❌ PDF Creation Failed."
        return 1
    fi
}

run_pdf "$@"
