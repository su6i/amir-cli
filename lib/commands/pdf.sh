#!/bin/bash

# Multi-engine PDF Rendering - Final Robust Version
run_pdf() {
    local cmd="magick"
    ! command -v magick &>/dev/null && cmd="convert"
    if ! command -v "$cmd" &>/dev/null; then echo "❌ ImageMagick not found."; return 1; fi

    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local LIB_DIR="$(dirname "$SCRIPT_DIR")"
    
    local inputs=() output="" engine="puppeteer"
    local raw_output=""
    local CLEANUP_FILES=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -o|--output) raw_output="$2"; shift; shift ;;
            --engine) engine="$2"; shift; shift ;;
            --weasyprint) engine="weasyprint"; shift ;;
            --pil) engine="pil"; shift ;;
            --pandoc) engine="pandoc"; shift ;;
            *) [[ -f "$1" ]] && inputs+=("$1"); shift ;;
        esac
    done
    
    # If no files provided, check for piped input
    if [[ ${#inputs[@]} -eq 0 ]]; then
        if [[ ! -t 0 ]]; then
            local stdin_tmp=$(mktemp "/tmp/amir_pdf_stdin_XXXXXX.txt")
            cat > "$stdin_tmp"
            if [[ -s "$stdin_tmp" ]]; then
                inputs+=("$stdin_tmp")
                CLEANUP_FILES+=("$stdin_tmp")
            else
                rm -f "$stdin_tmp"
            fi
        fi
    fi

    [[ ${#inputs[@]} -eq 0 ]] && return 1

    local amir_data="/tmp/amir_data"
    local use_external=false
    if [[ -d "/Volumes/SanDisk" ]]; then
        amir_data="/Volumes/SanDisk/amir_data"
        use_external=true
    fi
    mkdir -p "$amir_data/tmp" "$amir_data/uv_cache" "$amir_data/chrome_profile"
    
    # TMPDIR workaround: exFAT doesn't support flock (error 45)
    export MAGICK_TEMPORARY_PATH="$amir_data/tmp"
    local fs_type=$(diskutil info "$amir_data" 2>/dev/null | grep "File System Personality" | awk '{print $NF}')
    
    if [[ "$fs_type" != "ExFAT" ]]; then
        export TMPDIR="$amir_data/tmp"
        export UV_CACHE_DIR="$amir_data/uv_cache"
    fi
    
    local chrome_profile="$amir_data/chrome_profile"
    local tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/pdf_XXXXXX")
    
    local processed=()
    for i in "${!inputs[@]}"; do
        local file="${inputs[$i]}"
        local abs_file=$(cd "$(dirname "$file")" && pwd)/$(basename "$file")
        local ext=$(echo "${file##*.}" | tr '[:upper:]' '[:lower:]')
        
        if [[ "$ext" == "md" || "$ext" == "txt" ]]; then
            local display_name=$(basename "$file")
            [[ "$display_name" == amir_pdf_stdin_* ]] && display_name="clipboard"
            echo "📝 Rendering $display_name [$engine]..."
            local tmp_out="$tmp_dir/render_$(printf "%03d" $i).pdf"
            local tmp_img="$tmp_dir/render_$(printf "%03d" $i).png"
            local font_fa="/Library/Fonts/B-NAZANIN.TTF"
            [[ ! -f "$font_fa" ]] && font_fa="/Users/su6i/Library/Fonts/B-NAZANIN.TTF"
            
            # Use local venv python directly to bypass uv locking issues on exFAT
            local python_cmd="python3"
            if [[ -f "$LIB_DIR/../.venv/bin/python3" ]]; then
                python_cmd="$LIB_DIR/../.venv/bin/python3"
            elif command -v uv &>/dev/null; then
                python_cmd="uv run python3"
            fi

            local success=false
            if [[ "$engine" == "puppeteer" ]]; then
                node "${LIB_DIR}/nodejs/render_puppeteer.js" "$abs_file" "$tmp_out" "$font_fa" "$chrome_profile" &>/dev/null && success=true
            elif [[ "$engine" == "weasyprint" ]]; then
                $python_cmd "${LIB_DIR}/python/render_weasy.py" "$abs_file" "$tmp_out" "$font_fa" &>/dev/null && success=true
            elif [[ "$engine" == "pandoc" ]]; then
                pandoc "$abs_file" -o "$tmp_out" --pdf-engine=pdfkit &>/dev/null && success=true
            fi

            if [[ "$success" == "true" && -f "$tmp_out" ]]; then
                processed+=("${tmp_out}[0-999]")
            else
                [[ "$engine" != "pil" ]] && echo "⚠️  $engine failed. Using PIL fallback..."
                local en_font="/System/Library/Fonts/Supplemental/Times New Roman.ttf"
                [[ ! -f "$en_font" ]] && en_font="/System/Library/Fonts/Helvetica.ttc"
                
                $python_cmd "${LIB_DIR}/python/render_md.py" "$abs_file" "$tmp_img" "$font_fa" "$en_font" &>/dev/null
                
                if [[ -f "$tmp_img" ]]; then processed+=("$tmp_img"); fi
                
                # Robust collection of PIL pages
                local bname=$(basename "${tmp_img%.*}")
                find "$tmp_dir" -name "${bname}_page_*.png" | sort | while read -r p; do
                    processed+=("$p")
                done
            fi
        else
            processed+=("$file")
        fi
    done

    # Output naming: include engine name
    if [[ -z "$raw_output" ]]; then
        local first_in=$(basename "${inputs[0]%.*}")
        if [[ "$first_in" == amir_pdf_stdin_* ]]; then
            first_in="clipboard"
        fi
        output="${first_in}_${engine}.pdf"
    else
        output="$raw_output"
    fi
    
    local final_ready=()
    for f in "${processed[@]}"; do
        if [[ "$f" == *.pdf* ]]; then
            final_ready+=("$f")
        else
            local clip="$tmp_dir/c_$(basename "$f")"
            $cmd -density 300 "$f" -resize "2232x3260>" -gravity center -extent 2480x3508 -background white -flatten "$clip"
            final_ready+=("$clip")
        fi
    done

    if [[ ${#final_ready[@]} -gt 0 ]]; then
        rm -f "$output" 2>/dev/null
        if $cmd -density 300 "${final_ready[@]}" -compress jpeg -quality 100 "$output"; then
            touch "$output"
            local abs_output=$(python3 -c "import os; print(os.path.abspath('$output'))")
            echo "✅ PDF Created: $abs_output"
        else
            echo "❌ Final assembly failed."
        fi
    else
        echo "❌ No rendered pages found."
    fi

    rm -rf "$tmp_dir"
    for f in "${CLEANUP_FILES[@]}"; do rm -f "$f"; done
}

run_pdf "$@"
