#!/bin/bash

# ──────────────────────────────────────────────────────────────────
# amir pdf linkedin-post <folder> [carousel | guide [fr|en|fa]]
#
# Renders a trilingual (FR/EN/FA) LinkedIn post with WeasyPrint via
# lib/python/render_post.py. Reads <folder>/guide.{fr,en,fa}.md +
# <folder>/post.yml (cover + carousel data). Subcommands:
#   (none)            whole post: guides + guide.trilingue.pdf + carrousel.linkedin.pdf
#   carousel              only carrousel.linkedin.pdf
#   guide <fr en fa tri>  rebuild the listed guides; guide.trilingue.pdf is ALWAYS
#                         rebuilt alongside any guide (it is derived from the .md
#                         files, so it can't drift). 'tri' = only the trilingue.
#   guide                 all guides + guide.trilingue.pdf (no carousel)
# Fonts are vendored in lib/fonts/ and the renderer pins a restricted
# fontconfig (macOS RTL/Persian fix — see the weasyprint-rtl-persian-pdf skill).
# ──────────────────────────────────────────────────────────────────
run_pdf_linkedin_post() {
    local folder="$1"

    if [[ -z "$folder" || ! -d "$folder" ]]; then
        echo "❌ Usage: amir pdf linkedin-post <folder> [carousel | guide [fr en fa tri]]"
        echo "   amir pdf linkedin-post <folder>               → whole post (guides + trilingue + carousel)"
        echo "   amir pdf linkedin-post <folder> carousel      → carousel only"
        echo "   amir pdf linkedin-post <folder> guide fa      → a single guide (trilingue auto-rebuilt)"
        echo "   amir pdf linkedin-post <folder> guide fa en   → several guides at once (+ trilingue)"
        echo "   amir pdf linkedin-post <folder> guide tri     → rebuild ONLY the trilingue"
        echo "   amir pdf linkedin-post <folder> guide         → all guides + trilingue"
        return 1
    fi
    if [[ ! -f "$folder/post.yml" ]]; then
        echo "❌ Missing $folder/post.yml (cover + carousel data)."
        return 1
    fi
    shift                          # drop <folder>
    local sub="$1"
    [[ $# -ge 1 ]] && shift        # drop the subcommand (if present)
    local targets=("$@")           # remaining = guide targets: fr en fa tri

    local mode
    case "$sub" in
        "")        mode="all" ;;
        carousel)  mode="carousel" ;;
        guide)     mode="guide" ;;
        *)         echo "❌ Unknown subcommand: $sub  (use: carousel | guide [fr en fa tri])"; return 1 ;;
    esac
    if [[ "$mode" == "guide" ]]; then
        local t
        for t in "${targets[@]}"; do
            [[ "$t" =~ ^(fr|en|fa|tri)$ ]] || { echo "❌ Unknown guide target: $t  (use any of: fr en fa tri)"; return 1; }
        done
    fi

    local SCRIPT_DIR; SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local LIB_DIR; LIB_DIR="$(dirname "$SCRIPT_DIR")"

    echo ""
    case "$mode" in
        all)      echo "🔨  Building LinkedIn post (WeasyPrint, FR/EN/FA): $folder" ;;
        carousel) echo "🎠  Building carousel: $folder" ;;
        guide)    if [[ ${#targets[@]} -gt 0 ]]; then echo "📄  Building: ${targets[*]} — $folder"; else echo "📄  Building all guides + trilingue: $folder"; fi ;;
    esac
    echo ""

    # WeasyPrint needs the Homebrew native libs (pango/cairo/gobject); the
    # renderer pins its own restricted fontconfig. The `markdown` package isn't
    # in the venv, so run isolated via uv (no permanent dep added).
    export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:/usr/local/lib:${DYLD_FALLBACK_LIBRARY_PATH:-}"
    if uv run --no-project --python 3.12 --with weasyprint --with markdown --with pyyaml \
        python "$LIB_DIR/python/render_post.py" "$folder" "$LIB_DIR/fonts" "$mode" "${targets[@]}"; then
        echo ""
        echo "✅  Done"
    else
        echo "⚠️   Build failed"
        return 1
    fi
}

# Multi-engine PDF Rendering - Final Robust Version
run_pdf() {
    local cmd="magick"
    ! command -v magick &>/dev/null && cmd="convert"
    if ! command -v "$cmd" &>/dev/null; then echo "❌ ImageMagick not found."; return 1; fi

    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local LIB_DIR="$(dirname "$SCRIPT_DIR")"
    
    local inputs=() output="" engine="puppeteer" theme=""
    local raw_output="" free_size=false
    local page_width="" page_height=""
    local multi_page=false
    local do_deskew=true
    local force_rtl=false
    local CLEANUP_FILES=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -o|--output) raw_output="$2"; shift; shift ;;
            --engine) engine="$2"; shift; shift ;;
            --weasyprint) engine="weasyprint"; shift ;;
            --pil) engine="pil"; shift ;;
            --pandoc) engine="pandoc"; shift ;;
            --free-size|-f) free_size=true; shift ;;
            --page-width) page_width="$2"; shift; shift ;;
            --page-height) page_height="$2"; shift; shift ;;
            --pages|--merge) multi_page=true; shift ;;
            --deskew|--straighten) do_deskew=true; shift ;;
            --no-deskew|--no-straighten) do_deskew=false; shift ;;
            --theme) theme="$2"; shift; shift ;;
            --force-rtl|--rtl) force_rtl=true; shift ;;
            *) [[ -f "$1" ]] && inputs+=("$1"); shift ;;
        esac
    done
    
    # If no files provided, check for piped input
    if [[ ${#inputs[@]} -eq 0 ]]; then
        if [[ ! -t 0 ]]; then
            local stdin_tmp
            stdin_tmp=$(mktemp "${amir_data}/tmp/amir_pdf_stdin_XXXXXX.txt")
            cat > "$stdin_tmp"
            if [[ -s "$stdin_tmp" ]]; then
                inputs+=("$stdin_tmp")
                CLEANUP_FILES+=("$stdin_tmp")
            else
                rm -f "$stdin_tmp"
            fi
        fi
    fi

    if [[ ${#inputs[@]} -eq 0 ]]; then
        echo "❌ Error: No valid input files provided or files do not exist."
        return 1
    fi

    local amir_data=""
    local use_external=false
    if [[ -d "/Volumes/SanDisk" ]]; then
        amir_data="/Volumes/SanDisk/amir_data"
        use_external=true
    else
        amir_data="$(amir_preferred_temp_dir "$PWD")/pdf_data"
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
    local tmp_dir=$(mktemp -d "${amir_data}/tmp/pdf_XXXXXX")
    
    local processed=()
    for i in "${!inputs[@]}"; do
        local file="${inputs[$i]}"
        local abs_file=$(cd "$(dirname "$file")" && pwd)/$(basename "$file")
        local ext=$(echo "${file##*.}" | tr '[:upper:]' '[:lower:]')
        
        if [[ "$ext" == "tex" ]]; then
            local display_name=$(basename "$file")
            [[ "$display_name" == amir_pdf_stdin_* ]] && display_name="clipboard"
            echo "📝 Rendering $display_name [xelatex]..."
            
            if ! command -v xelatex &>/dev/null; then
                echo "❌ Error: xelatex is not installed. Please install MacTeX or BasicTeX."
                continue
            fi

            local jobname="render_$(printf "%03d" $i)"
            local tmp_out="$tmp_dir/${jobname}.pdf"
            
            # Add amir's latex styles directory to TEXINPUTS (with trailing colon for default paths)
            export TEXINPUTS="$LIB_DIR/latex//:${TEXINPUTS:-:}"
            
            # Run twice for TOC/references
            xelatex -interaction=nonstopmode -output-directory="$tmp_dir" -jobname="$jobname" "$abs_file" &>/dev/null
            xelatex -interaction=nonstopmode -output-directory="$tmp_dir" -jobname="$jobname" "$abs_file" &>/dev/null
            
            if [[ -f "$tmp_out" ]]; then
                processed+=("${tmp_out}[0-999]")
            else
                echo "❌ Failed to render $display_name with xelatex. You might be missing some fonts or packages."
            fi
            
        elif [[ "$ext" == "md" || "$ext" == "txt" ]]; then
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
                node "${LIB_DIR}/nodejs/render_puppeteer.js" "$abs_file" "$tmp_out" "$font_fa" "$chrome_profile" "$free_size" "$page_width" "$page_height" "$theme" "$force_rtl" &>/dev/null && success=true
            elif [[ "$engine" == "weasyprint" ]]; then
                if [[ "$free_size" == "true" ]]; then echo "⚠️  --free-size is only fully supported on Puppeteer. Output may vary."; fi
                if [[ -n "$page_width" || -n "$page_height" ]]; then echo "⚠️  --page-width/--page-height are only supported on Puppeteer. Output may vary."; fi
                $python_cmd "${LIB_DIR}/python/render_weasy.py" "$abs_file" "$tmp_out" "$font_fa" &>/dev/null && success=true
            elif [[ "$engine" == "pandoc" ]]; then
                if [[ "$free_size" == "true" ]]; then echo "⚠️  --free-size is only fully supported on Puppeteer. Output may vary."; fi
                if [[ -n "$page_width" || -n "$page_height" ]]; then echo "⚠️  --page-width/--page-height are only supported on Puppeteer. Output may vary."; fi
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
    local image_batch=()

    for f in "${processed[@]}"; do
        if [[ "$f" == *.pdf* ]]; then
            final_ready+=("$f")
        elif [[ "$free_size" == "true" ]]; then
            final_ready+=("$f")
        elif [[ "$multi_page" == "true" ]]; then
            local clip="$tmp_dir/c_$(basename "$f")"
            $cmd -density 300 "$f" -resize "2232x3260>" -gravity center -extent 2480x3508 -background white -flatten "$clip"
            final_ready+=("$clip")
        else
            # Collect images for collage
            image_batch+=("$f")
        fi
    done

    if [[ ${#image_batch[@]} -gt 0 ]]; then
        local collaged="$tmp_dir/c_collage.jpg"
        local collage_cmd=("$cmd" "-size" "2480x3508" "xc:white" "(")
        for img in "${image_batch[@]}"; do
            collage_cmd+=("(")
            collage_cmd+=("$img" "-auto-orient" "+repage")
            
            # Auto-crop borders (like dark tables or scanner backgrounds)
            collage_cmd+=("-fuzz" "10%" "-trim" "+repage")
            
            # Smart Rotate: Force portrait images to landscape
            # Use -90 to ensure text orientation is upright for standard phone captures
            collage_cmd+=("-set" "option:rot" "%[fx:(w<h)?-90:0]" "-rotate" "%[rot]" "+repage")
            
            if [[ "$do_deskew" == "true" ]]; then
                collage_cmd+=("-deskew" "40%" "+repage")
            fi
            
            # Elegant Presentation:
            # 1. Resize to ~70% of A4 width (1800px out of 2480px) so it doesn't cover the full width
            collage_cmd+=("-resize" "1800x")
            
            # 2. Add subtle rounded corners (radius 40)
            collage_cmd+=("-alpha" "set" "(" "+clone" "-alpha" "transparent" "-background" "none" "-fill" "white" "-stroke" "none" "-draw" "roundrectangle 0,0 %[fx:w-1],%[fx:h-1] 40,40" ")" "-compose" "DstIn" "-composite" "-compose" "Over")
            collage_cmd+=("-background" "white" "-alpha" "remove" "-alpha" "off")
            
            # 3. Add vertical padding
            collage_cmd+=("-bordercolor" "white" "-border" "0x60")
            
            collage_cmd+=(")")
        done
        collage_cmd+=("-background" "white" "-append" "+repage")
        collage_cmd+=("-resize" "2480x3508>" "+repage")
        collage_cmd+=(")")
        collage_cmd+=("-gravity" "center" "-composite" "-units" "PixelsPerInch" "-density" "300" "$collaged")
        
        "${collage_cmd[@]}"
        
        if [[ -f "$collaged" ]]; then
            final_ready+=("$collaged")
        fi
    fi

    if [[ ${#final_ready[@]} -gt 0 ]]; then
        rm -f "$output" 2>/dev/null
        
        # Optimization: if there's exactly one PDF, copy it directly to preserve vector text/fonts and prevent massive file bloat
        if [[ ${#final_ready[@]} -eq 1 && "${final_ready[0]}" == *.pdf* ]]; then
            local src_pdf="${final_ready[0]}"
            # Strip ImageMagick page range syntax if present (e.g. file.pdf[0-999] -> file.pdf)
            src_pdf="${src_pdf%\[*\]}"
            cp "$src_pdf" "$output"
            local abs_output=$(python3 -c "import os; print(os.path.abspath('$output'))")
            echo "✅ PDF Created: $abs_output"
        else
            # Smart Merge: Use Ghostscript if all inputs are PDFs to avoid rasterization bloat
            local all_pdfs=true
            local gs_inputs=()
            for f in "${final_ready[@]}"; do
                if [[ "$f" == *.pdf* ]]; then
                    gs_inputs+=("${f%\[*\]}")
                else
                    all_pdfs=false
                    break
                fi
            done

            if [[ "$all_pdfs" == "true" ]] && command -v gs &>/dev/null; then
                if gs -dNOPAUSE -sDEVICE=pdfwrite -sOUTPUTFILE="$output" -dBATCH "${gs_inputs[@]}" &>/dev/null; then
                    touch "$output"
                    local abs_output=$(python3 -c "import os; print(os.path.abspath('$output'))")
                    echo "✅ PDF Created (Vector Merge): $abs_output"
                else
                    all_pdfs=false # Fallback to ImageMagick if GS fails
                fi
            else
                all_pdfs=false
            fi

            if [[ "$all_pdfs" == "false" ]]; then
                if $cmd -density 300 "${final_ready[@]}" -compress jpeg -quality 100 "$output"; then
                    touch "$output"
                    local abs_output=$(python3 -c "import os; print(os.path.abspath('$output'))")
                    echo "✅ PDF Created (Rasterized): $abs_output"
                else
                    echo "❌ Final assembly failed."
                fi
            fi
        fi
    else
        echo "❌ No rendered pages found."
    fi

    rm -rf "$tmp_dir"
    for f in "${CLEANUP_FILES[@]}"; do rm -f "$f"; done
}

# ──────────────────────────────────────────────────────────────────
# amir pdf split <file.pdf> --pages <spec> [--combined] [-o output]
#
# --pages is a comma-separated list of page numbers/ranges, e.g.:
#   --pages 1,3,4          → three files, each a single page
#   --pages 1,2-3,4-8      → three files: [1], [2,3], [4,5,6,7,8]
#   --pages 1,2-3,4-8 --combined  → one file with pages 1,2,3,4,5,6,7,8
#
# Implemented via qpdf's native --pages page-range syntax (qpdf itself
# accepts "1,3,5-9"-style ranges), so no manual page-range parsing needed.
# ──────────────────────────────────────────────────────────────────
run_pdf_split() {
    local input="" pages_spec="" combined=false output=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --pages) pages_spec="$2"; shift 2 ;;
            --combined) combined=true; shift ;;
            -o|--output) output="$2"; shift 2 ;;
            -*) echo "❌ Unknown option: $1"; return 1 ;;
            *) input="$1"; shift ;;
        esac
    done

    if [[ -z "$input" || ! -f "$input" ]]; then
        echo "❌ Usage: amir pdf split <file.pdf> --pages <spec> [--combined] [-o output]"
        echo "   --pages 1,3,4          → 3 separate PDFs, one page each"
        echo "   --pages 1,2-3,4-8      → 3 separate PDFs: [1] [2-3] [4-8]"
        echo "   --pages 1,2-3,4-8 --combined  → 1 PDF with all those pages merged"
        return 1
    fi
    if [[ -z "$pages_spec" ]]; then
        echo "❌ --pages is required (e.g. --pages 1,3,4 or --pages 1,2-3,4-8)"
        return 1
    fi
    if ! command -v qpdf &>/dev/null; then
        echo "❌ qpdf not found. Install with: brew install qpdf"
        return 1
    fi

    pages_spec="${pages_spec// /}"
    local stem="${input%.pdf}"
    [[ -n "$output" ]] && stem="${output%.pdf}"

    if [[ "$combined" == "true" ]]; then
        local out="${stem}_combined.pdf"
        [[ -n "$output" ]] && out="${output%.pdf}.pdf"
        if qpdf "$input" --pages . "$pages_spec" -- "$out"; then
            echo "✅ Combined PDF saved: $(realpath "$out")"
        else
            echo "❌ qpdf failed to build combined PDF."
            return 1
        fi
        return 0
    fi

    local -a tokens
    IFS=',' read -ra tokens <<< "$pages_spec"
    local i=1
    for token in "${tokens[@]}"; do
        local out="${stem}_p${token}.pdf"
        if qpdf "$input" --pages . "$token" -- "$out"; then
            echo "✅ Part $i saved: $(realpath "$out")  (pages $token)"
        else
            echo "❌ qpdf failed on range: $token"
        fi
        ((i++))
    done
}

if [[ "$1" == "linkedin-post" ]]; then
    run_pdf_linkedin_post "${@:2}"
elif [[ "$1" == "split" ]]; then
    run_pdf_split "${@:2}"
else
    run_pdf "$@"
fi
