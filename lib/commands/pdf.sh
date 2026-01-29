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

    # 2. Argument Parsing
    local inputs=()
    local output="output.pdf"
    local round_corners=false
    
    while [[ $# -gt 0 ]]; do
        key="$1"
        case $key in
            -o|--output)
                output="$2"
                shift; shift
                ;;
            --round)
                round_corners=true
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
        echo "Usage: amir pdf <img1> [img2...] [-o output.pdf] [--round]"
        echo "   Combines images into a single A4 page (Portrait)."
        return 1
    fi
    
    # Auto-name output if default and input exists
    if [[ "$output" == "output.pdf" && -n "${inputs[0]}" ]]; then
        local base=$(basename "${inputs[0]}")
        output="${base%.*}.pdf"
    fi

    echo "📄 Composing ${#inputs[@]} image(s) into A4 PDF..."
    if [[ "$round_corners" == "true" ]]; then
        echo "� Option: Rounding corners enabled."
    fi
    echo "�🎯 Output: $output"

    # 1. Delete old output to ensure fresh write.
    rm -f "$output"

    # Refactored Logic: Process each image individually to apply rounding mask correctly
    local final_cmd=()
    final_cmd+=("-size" "2480x3508" "xc:white")
    final_cmd+=("(")
    
    for img in "${inputs[@]}"; do
        final_cmd+=("(")
        final_cmd+=("$img")
        
        # Apply Rounding if requested (Draw Mask Method)
        if [[ "$round_corners" == "true" ]]; then
            final_cmd+=("-alpha" "set")
            final_cmd+=("(")
            final_cmd+=("+clone" "-alpha" "transparent" "-background" "none")
            final_cmd+=("-fill" "white" "-stroke" "none")
            # Round with 80px radius (Good for 2400px width)
            final_cmd+=("-draw" "roundrectangle 0,0 %[fx:w-1],%[fx:h-1] 80,80")
            final_cmd+=(")")
            final_cmd+=("-compose" "DstIn" "-composite")
            final_cmd+=("-compose" "Over") # Reset compose
        fi
        
        # Flatten onto white (Removes transparency/black corners)
        final_cmd+=("-background" "white" "-alpha" "remove" "-alpha" "off")
        
        # Resize & Border
        final_cmd+=("-resize" "2400x")
        final_cmd+=("-bordercolor" "white" "-border" "0x20")
        
        final_cmd+=(")")
    done
    
    # Layout & Output
    final_cmd+=("-background" "white" "-append" "+repage")
    final_cmd+=("-resize" "2480x3508>" "+repage")
    final_cmd+=(")") # End of process group
    
    final_cmd+=("-gravity" "center" "-composite")
    final_cmd+=("-units" "PixelsPerInch" "-density" "300")
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
