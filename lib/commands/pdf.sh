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
    [[ "$radius" =~ ^[0-9]+$ ]] || radius=0
    [[ "$rotate_angle" =~ ^-?[0-9]+$ ]] || rotate_angle=0
    [[ "$compression_quality" =~ ^[0-9]+$ ]] || compression_quality=75
    [[ "$compression_resize" =~ ^[0-9]+$ ]] || compression_resize=75
    
    local compression_resize=$(get_config "pdf" "resize" "75")
    local do_deskew=true
    
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
            --deskew|--straighten)
                do_deskew=true
                shift
                ;;
            --no-deskew|--no-straighten)
                do_deskew=false
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
        echo "   --no-deskew      : Disable auto-straightening (Default: Deskew enabled)."
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

    # Smart File Naming (Auto-increment if exists)
    local base_output="${output%.*}"
    local ext_output="${output##*.}"
    local counter=1
    
    while [[ -f "$output" || -f "$output_compressed" ]]; do
        output="${base_output}_${counter}.${ext_output}"
        # Recalculate compressed name based on new output name
        output_compressed="${output%.*}_compressed_q${compression_quality}.pdf"
        ((counter++))
    done
    
    if [[ $counter -gt 1 ]]; then
        echo "⚠️  File exists. Saving as: $output"
    fi

    echo "📄 Composing ${#inputs[@]} file(s) into A4 PDF..."
    echo " Output: $output"

    # Create professional A4 pages
    local tmp_dir=$(mktemp -d "/tmp/amir_pdf_XXXXXX")
    local ready_pages=()
    
    if [[ "$multi_page" == "true" ]]; then
        echo "📄 Mode: Multi-page (One A4 page per image)"
        for i in "${!inputs[@]}"; do
            local img="${inputs[$i]}"
            local tmp_page="$tmp_dir/page_$(printf "%03d" $i).png"
            
            $cmd -density 300 -size 2480x3508 xc:white \
                \( -density 300 "$img" -auto-orient +repage \
                   $( [[ "$do_deskew" == "true" ]] && echo "-deskew 40% +repage" ) \
                   $( [[ "$rotate_angle" -ne 0 ]] && echo "-rotate $rotate_angle +repage" ) \
                   -resize 2480x3508 \
                \) \
                -gravity center -compose over -composite \
                -alpha remove -alpha off \
                -density 300 -units PixelsPerInch "$tmp_page"
                
            [[ -f "$tmp_page" ]] && ready_pages+=("$tmp_page")
        done
    else
        echo "📄 Mode: Collage (Fitting multiple images on a single A4 page)"
        local tmp_collage="$tmp_dir/collage_source.png"
        local final_page="$tmp_dir/final_a4.png"
        
        # 1. Process all inputs into oriented, deskewed, and resized segments
        local processed_imgs=()
        for i in "${!inputs[@]}"; do
            local img="${inputs[$i]}"
            local p_img="$tmp_dir/p_$(printf "%03d" $i).png"
            
            $cmd -density 300 "$img" -auto-orient +repage \
                $( [[ "$do_deskew" == "true" ]] && echo "-deskew 40% +repage" ) \
                $( [[ "$rotate_angle" -ne 0 ]] && echo "-rotate $rotate_angle +repage" ) \
                $( [[ ${#inputs[@]} -eq 1 ]] && echo "-resize 2480x3508" || echo "-resize 2480x1754" ) \
                -alpha remove -alpha off \
                "$p_img"
            
            [[ -f "$p_img" ]] && processed_imgs+=("$p_img")
        done
        
        # 2. Append processed images vertically
        $cmd "${processed_imgs[@]}" -background None -gravity center -append "$tmp_collage"
        
        # 3. Fit collage onto a standardized A4 canvas (300 DPI)
        $cmd -density 300 -size 2480x3508 xc:white \
            -density 300 "$tmp_collage" \
            -gravity center -compose over -composite \
            -alpha remove -alpha off \
            -density 300 -units PixelsPerInch "$final_page"
            
        [[ -f "$final_page" ]] && ready_pages+=("$final_page")
    fi
    
    if [[ ${#ready_pages[@]} -eq 0 ]]; then
        echo "❌ Critical Error: No pages were successfully processed."
        rm -rf "$tmp_dir"
        return 1
    fi
 
    echo "📚 Assembling A4 PDF (HQ)..."
    $cmd -density 300 -units PixelsPerInch "${ready_pages[@]}" -compress jpeg -quality 100 "$output"
    
    # Cleanup temp pages
    rm -rf "$tmp_dir"

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
