#!/bin/bash

# We define compress at the top level so other scripts (like batch) can use it when sourced.

# Source Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")"
if [[ -f "$LIB_DIR/config.sh" ]]; then
    source "$LIB_DIR/config.sh"
    if type init_config &> /dev/null; then init_config; fi
else
    get_config() { echo "$3"; }
fi

# Source shared media library (encoder detection, table rendering, etc.)
if [[ -f "$LIB_DIR/media_lib.sh" ]]; then
    source "$LIB_DIR/media_lib.sh"
fi

stats() {
    local config_dir="${AMIR_CONFIG_DIR:-$HOME/.amir-cli}"
    mkdir -p "$config_dir"
    local learning_file="$config_dir/learning_data"
    
    if [[ ! -f "$learning_file" ]]; then
        echo "📊 No learning data found."
        return 1
    fi
    
    # Bash 3.2 Compatible: Use indexed arrays (Global by default in function without local)
    # declare -A quality_factors
    # declare -A speed_factors
    # declare -A sample_counts
    
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" == \#* ]] && continue
        
        if [[ "$key" == quality_factors* ]]; then
            local q="${key#quality_factors[}"
            q="${q%]}"
            quality_factors[$q]="$value"
        elif [[ "$key" == speed_factors* ]]; then
            local q="${key#speed_factors[}"
            q="${q%]}"
            speed_factors[$q]="$value"
        elif [[ "$key" == sample_counts* ]]; then
            local q="${key#sample_counts[}"
            q="${q%]}"
            sample_counts[$q]="$value"
        fi
    done < "$learning_file"
    
    echo "🤖 ADVANCED COMPRESSION AI STATISTICS"
    echo "══════════════════════════════════════"
    echo ""
    
    echo "🎯 QUALITY FACTORS (Compression Efficiency)"
    
    local col_width=$(calculate_column_width 5 12 18)
    
    printf "┌%s┬%s┬%s┬%s┬%s┐\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"

    local h_qual=$(pad_to_width "Qual" $col_width)
    local h_fact=$(pad_to_width "Factor" $col_width)
    local h_est=$(pad_to_width "Est. Ratio" $col_width)
    local h_speed=$(pad_to_width "Speed Factor" $col_width)
    local h_samp=$(pad_to_width "Samples" $col_width)

    printf "│ %s │ %s │ %s │ %s │ %s │\n" \
        "$h_qual" "$h_fact" "$h_est" "$h_speed" "$h_samp"

    printf "├%s┼%s┼%s┼%s┼%s┤\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    for q in 40 50 55 60 65 70 75 80; do
        local factor=${quality_factors[$q]:-1.0}
        local speed=${speed_factors[$q]:-6}
        local samples=${sample_counts[$q]:-0}
        local est_ratio=$(echo "scale=1; $factor * 100" | bc)
        
        # Pad content
        local c_qual=$(pad_to_width "$q" $col_width)
        local c_fact=$(pad_to_width "$factor" $col_width)
        local c_est=$(pad_to_width "${est_ratio}%" $col_width)
        # Fix printf error: speed might be float in bash, ensure integer for display logic simply by string formatting
        local c_speed=$(pad_to_width "${speed%.*}" $col_width)
        local c_samp=$(pad_to_width "$samples" $col_width)
        
        printf "│ %s │ %s │ %s │ %s │ %s │\n" \
            "$c_qual" "$c_fact" "$c_est" "$c_speed" "$c_samp"
    done
    
    printf "└%s┴%s┴%s┴%s┴%s┘\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
}

reset_learning_data() {
    local config_dir="${AMIR_CONFIG_DIR:-$HOME/.amir-cli}"
    local learning_file="$config_dir/learning_data"

    if [[ -f "$learning_file" ]]; then
        rm "$learning_file"
        echo "✅ Advanced learning data reset to defaults."
    else
        echo "ℹ️  No learning data found."
    fi
}

check_hevc_support() {
    echo "🎥 HEVC Encoder Support:"
    local found=0
    for enc in hevc_videotoolbox hevc_nvenc hevc_amf hevc_qsv libx265; do
        if ffmpeg -encoders 2>/dev/null | grep -q "$enc"; then
            echo "  ✅ $enc"
            found=1
        else
            echo "  ❌ $enc"
        fi
    done
    [[ $found -eq 0 ]] && echo "  ⚠️  No hardware HEVC encoders found; falling back to libx265 (CPU)"
}

calculate_column_width() {
    local term_width=$(tput cols 2>/dev/null || echo 120)
    local columns=$1
    local min_width=${2:-25}
    local max_width=${3:-35}
    local padding=12
    
    local available_width=$((term_width - padding * (columns - 1)))
    local col_width=$((available_width / columns))
    
    if [[ $col_width -lt $min_width ]]; then
        col_width=$min_width
    elif [[ $col_width -gt $max_width ]]; then
        col_width=$max_width
    fi
    
    echo $col_width
}

load_learning_data() {
    local config_dir="${AMIR_CONFIG_DIR:-$HOME/.amir-cli}"
    local learning_file="$config_dir/learning_data"
    
    # Bash 3.2 Compatible: Use indexed arrays (Global by default in function without local)
    # quality_factors=()
    # speed_factors=()
    # sample_counts=()
    
    # Set defaults
    quality_factors[40]=0.42
    quality_factors[50]=0.60
    quality_factors[55]=0.75
    quality_factors[60]=1.0
    quality_factors[65]=1.22
    quality_factors[70]=1.3
    quality_factors[75]=1.45
    quality_factors[80]=1.65
    
    speed_factors[40]=9
    speed_factors[50]=8
    speed_factors[55]=7
    speed_factors[60]=6
    speed_factors[65]=5
    speed_factors[70]=4
    speed_factors[75]=4
    speed_factors[80]=3
    
    for q in 40 50 55 60 65 70 75 80; do
        sample_counts[$q]=0
    done
    
    # Load from file if exists
    if [[ -f "$learning_file" ]]; then
        while IFS='=' read -r key value; do
            [[ -z "$key" || "$key" == \#* ]] && continue
            
            if [[ "$key" == quality_factors* ]]; then
                local q="${key#quality_factors[}"
                q="${q%]}"
                quality_factors[$q]="$value"
            elif [[ "$key" == speed_factors* ]]; then
                local q="${key#speed_factors[}"
                q="${q%]}"
                speed_factors[$q]="$value"
            elif [[ "$key" == sample_counts* ]]; then
                local q="${key#sample_counts[}"
                q="${q%]}"
                sample_counts[$q]="$value"
            fi
        done < "$learning_file"
    fi
}

save_learning_data() {
    local config_dir="${AMIR_CONFIG_DIR:-$HOME/.amir-cli}"
    local learning_file="$config_dir/learning_data"
    mkdir -p "$(dirname "$learning_file")"
    
    {
        echo "# Advanced Compression Learning Data"
        echo "# Updated: $(date)"
        echo ""
        for q in 40 50 55 60 65 70 75 80; do
            echo "quality_factors[$q]=${quality_factors[$q]}"
            echo "speed_factors[$q]=${speed_factors[$q]}"
            echo "sample_counts[$q]=${sample_counts[$q]}"
        done
    } > "$learning_file"
}

# Scientific Visual Width Calculation using Python unicodedata (Standard & Portable)
get_visual_width() {
    python3 -c "import unicodedata, sys; s=sys.argv[1]; print(sum(2 if unicodedata.east_asian_width(c) in 'WF' else 0 if unicodedata.category(c) in ('Mn','Me','Cf') else 1 for c in s))" "$1"
}

# Pad text to strictly match visual width
pad_to_width() {
    local text="$1"
    local target_width="$2"
    local vis_len=$(get_visual_width "$text")
    local pad_len=$((target_width - vis_len))
    
    # If text is too long (negative padding), we must truncate
    if [[ $pad_len -lt 0 ]]; then
        # Simple truncation strategy: chop chars until it fits (approximate but safe)
        local truncated="$text"
        while [[ $(get_visual_width "$truncated") -gt $((target_width - 2)) ]]; do
            truncated="${truncated%?}"
        done
        echo -n "${truncated}.."
        # Re-calc padding for truncated string
        vis_len=$(get_visual_width "${truncated}..")
        pad_len=$((target_width - vis_len))
    else
        echo -n "$text"
    fi
    
    # Print spaces
    if [[ $pad_len -gt 0 ]]; then
        printf "%${pad_len}s" ""
    fi
}

# --- Core Processor Function (Extracted for Batch Support) ---
process_video() {
    local input_file="$1"
    local target_h="$2"
    local quality="$3"
    local encoding_mode="${4:---gpu}"  # Default: GPU
    local extreme_mode="${5:-0}"
    local custom_fps="${6:-0}"
    local split_mb="${7:-0}"
    local force_reencode="${8:-0}"

    if [[ ! -f "$input_file" ]]; then
        return
    fi
    
    # Skip already compressed versions to prevent loops
    if [[ "$input_file" == *"_${target_h}p_"* || "$input_file" == *"_compressed"* ]]; then
        return
    fi
    
    # ── Media Info (via shared library) ──
    get_media_info "$input_file"
    local in_w=$MEDIA_WIDTH
    local in_h=$MEDIA_HEIGHT
    local is_portrait=$MEDIA_IS_PORTRAIT
    local duration_seconds=$MEDIA_DURATION
    local duration_formatted=$MEDIA_DURATION_FMT
    
    if [[ -z "$duration_seconds" || "$duration_seconds" -eq 0 ]]; then
        echo "⚠️  Skipping: $(basename "$input_file") (Could not determine duration)"
        return
    fi

    # Calculate target dimensions based on orientation
    local target_w target_h_final
    if [[ $is_portrait -eq 1 ]]; then
        target_h_final=$(( (target_h * 16 / 9 + 1) / 2 * 2 ))
        target_w=$target_h
        [[ $target_h_final -lt $target_w ]] && target_h_final=$((target_w * 16 / 9))
    else
        target_w=$(( (target_h * 16 / 9 + 1) / 2 * 2 ))
        target_h_final=$target_h
    fi

    local fps_suffix=""
    [[ "$custom_fps" -gt 0 ]] && fps_suffix="_${custom_fps}fps"
    local output="${input_file%.*}_${target_h}p_q${quality}${fps_suffix}.mp4"
    
    if [[ -f "$output" && "$force_reencode" -ne 1 ]]; then
        if [[ -n "$split_mb" && "$split_mb" =~ ^[0-9]+$ && "$split_mb" -gt 0 ]]; then
            echo "⏩ Output exists: $(basename "$output")"
            echo "🔁 Reusing existing compressed file and running split only..."
            echo ""
            split_video_by_size_strict "$output" "$split_mb"
            return
        fi
        echo "⏩ Skipping: $(basename "$input_file") (Output exists)"
        return
    fi

    local input_size=$(ls -lh "$input_file" | awk '{print $5}')
    local input_bytes=$(ls -l "$input_file" | awk '{print $5}')
    
    # ── Encoder Detection (via shared library) ──
    detect_encoder "$encoding_mode"
    local encoder="$MEDIA_ENCODER"
    local tag_opt="$MEDIA_TAG_OPT"
    local encoder_display="$MEDIA_ENCODER_DISPLAY"
    
    # ── Hardware Detection (via shared library) ──
    detect_hardware
    
    local quality_factor=${quality_factors[$quality]:-1.0}
    local speed_factor=${speed_factors[$quality]:-6}
    local sample_count=${sample_counts[$quality]:-0}
    
    # ── Input Info Table (via shared library) ──
    local t_orient="Landscape"
    [[ $is_portrait -eq 1 ]] && t_orient="Portrait"
    
    echo ""
    echo "🎬 PROCESSING: $(basename "$input_file")"
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo ""
    
    local col_width=$(calculate_column_width 3 28 35)
    print_media_table "$col_width" \
        "📂 INPUT FILE|🖥️  HARDWARE|🎯 SETTINGS" \
        "File: $(basename "$input_file")|CPU: $HW_CPU_INFO|Resolution: ${target_h}p" \
        "Size: $input_size|GPU: $HW_GPU_INFO|Quality: $quality/100" \
        "Duration: $duration_formatted|Encoder: $encoder_display|Orientation: $t_orient"
    
    echo ""
    echo "⏳ Processing..."
    
    local start_time=$(date +%s)
    
    # ── Encoder Options (via shared library) ──
    local input_bitrate=$(get_media_bitrate "$input_file")
    build_encoder_opts "$encoder" "$quality" "$input_bitrate"
    
    # For VideoToolbox (hardware GPU encoder) the default formula is:
    #   target_bitrate = input_bitrate × quality/100
    # This ignores the resolution change, so a 720p→240p encode still targets the
    # same high bitrate and the file barely shrinks. Fix: scale the target bitrate
    # proportionally to the pixel count change as well.
    if [[ "$encoder" == *"videotoolbox"* && -n "$input_bitrate" && "$input_bitrate" =~ ^[0-9]+$ && "$in_w" -gt 0 && "$in_h" -gt 0 ]]; then
        local corrected_br
        corrected_br=$(awk -v br="$input_bitrate" -v q="$quality" \
            -v iw="$in_w" -v ih="$in_h" -v tw="$target_w" -v th="$target_h_final" \
            'BEGIN {
                pixel_ratio = (tw * th) / (iw * ih);
                if (pixel_ratio > 1) pixel_ratio = 1;
                t = br * (q / 100) * pixel_ratio;
                if (t < 100000) t = 100000;
                printf "%d", t;
            }')
        MEDIA_Q_OPT=("-b:v" "$corrected_br")
    fi

    local audio_filter="aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
    local audio_bitrate_opt=()
    local target_fps=25

    # Extreme mode: mono audio, 56kbps, 24fps, slow CPU preset for maximum compression
    if [[ "$extreme_mode" -eq 1 ]]; then
        audio_filter="aresample=22050,aformat=sample_fmts=fltp:channel_layouts=mono"
        audio_bitrate_opt=("-b:a" "56k")
        target_fps=24
    fi

    # --fps flag overrides everything (including extreme defaults)
    [[ "$custom_fps" -gt 0 ]] && target_fps=$custom_fps

    local filter_cmd="fps=${target_fps},scale='min(${target_w},iw)':-2"

    # ── Execute FFmpeg with Progress Bar ──
    run_ffmpeg_with_progress "$duration_seconds" \
        ffmpeg -hide_banner -loglevel info -stats -nostdin -y -i "$input_file" \
        -vf "$filter_cmd" -sws_flags bilinear \
        -c:v "$encoder" "${MEDIA_Q_OPT[@]}" $tag_opt \
        "${MEDIA_BITRATE_FLAGS[@]}" \
        -af "$audio_filter" \
        -c:a aac "${audio_bitrate_opt[@]}" -pix_fmt yuv420p -movflags +faststart "$output"
    local ffmpeg_exit=$?

    local output_bytes_check=0
    [[ -f "$output" ]] && output_bytes_check=$(ls -l "$output" | awk '{print $5}')
    if [[ ! -f "$output" || "$output_bytes_check" -lt 1000 ]]; then
        echo "❌ Compression failed! (output: ${output_bytes_check} bytes)"
        echo "── ffmpeg error ──"
        cat "$ffmpeg_error_log" | grep -i 'error\|invalid\|failed\|cannot' | tail -20
        rm -f "$ffmpeg_error_log" "$output"
        return 1
    fi
    rm -f "$ffmpeg_error_log"
    
    local end_time=$(date +%s)
    local total_elapsed=$((end_time - start_time))
    local total_elapsed_formatted=$(printf '%02d:%02d' $(($total_elapsed/60)) $(($total_elapsed%60)))
    
    local output_size=$(ls -lh "$output" | awk '{print $5}')
    local output_bytes=$(ls -l "$output" | awk '{print $5}')
    
    # Calculate Ratio & Percent (Correct Logic)
    local ratio=$(echo "scale=2; $input_bytes / $output_bytes" | bc 2>/dev/null || echo "0")
    local percent_calc=$(echo "scale=1; 100 - ($output_bytes * 100 / $input_bytes)" | bc 2>/dev/null || echo "0")
    
    local label_saved="Reduction"
    local val_saved="${percent_calc}%"
    
    # If percent is negative, it means size INCREASED
    if [[ $(echo "$percent_calc < 0" | bc) -eq 1 ]]; then
        label_saved="Increase"
        # Invert sign for display
        val_saved=$(echo "scale=1; $percent_calc * -1" | bc)"%"
    fi

    local actual_speed=$(echo "scale=2; $duration_seconds / $total_elapsed" | bc 2>/dev/null || echo "0")
    
    local actual_ratio=$(echo "scale=4; $output_bytes / $input_bytes" | bc 2>/dev/null || echo "0.05")
    local normalized_ratio=$(echo "scale=4; $actual_ratio * 15" | bc)
    local new_q_factor=$(echo "scale=4; ($quality_factor * 0.7) + ($normalized_ratio * 0.3)" | bc)
    
    [[ $(echo "$new_q_factor < 0.2" | bc) -eq 1 ]] && new_q_factor=0.2
    [[ $(echo "$new_q_factor > 2.0" | bc) -eq 1 ]] && new_q_factor=2.0
    
    quality_factors[$quality]=$new_q_factor
    speed_factors[$quality]=$(echo "scale=0; ($speed_factor * 0.8) + ($actual_speed * 0.2)" | bc)
    sample_counts[$quality]=$((sample_count + 1))
    
    save_learning_data
    
    echo ""
    echo "✅ COMPLETE: $(basename "$output")"
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo ""
    
    local col_width=$(calculate_column_width 4 22 28)
    print_media_table "$col_width" \
        "📥 INPUT|📤 OUTPUT|📊 PERFORMANCE|📈 COMPARISON" \
        "File: $(basename "$input_file")|File: $(basename "$output")|Time: $total_elapsed_formatted|${label_saved}: ${val_saved}" \
        "Size: $input_size|Size: $output_size|Speed: ${actual_speed}x|Ratio: ${ratio}x smaller"
    
    echo ""
    echo "📍 Output: $(realpath "$output")"
    
    # ── Output Size Validation (via shared library) ──
    validate_output_size "$input_file" "$output" "$encoder"

    # ── Split output into chunks if requested (--split N; strict size mode) ──
    if [[ -n "$split_mb" && "$split_mb" -gt 0 && -f "$output" ]]; then
        echo ""
        split_video_by_size_strict "$output" "$split_mb"
    fi
}

run_video_split() {
    local input_file="$1"
    local split_mb="$2"

    if [[ -z "$input_file" || ! -f "$input_file" ]]; then
        echo "❌ Error: No input file specified."
        echo "Usage: amir video split <file> <mb>"
        return 1
    fi
    if [[ -z "$split_mb" || ! "$split_mb" =~ ^[0-9]+$ || "$split_mb" -le 0 ]]; then
        echo "❌ Error: Split size must be a positive integer in MB."
        echo "Usage: amir video split <file> <mb>"
        return 1
    fi

    split_video_by_size_strict "$input_file" "$split_mb"
}

video_abspath() {
    python3 -c "import os, sys; print(os.path.abspath(sys.argv[1]))" "$1"
}

video_concat() {
    local output_file=""
    local input_files=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -o|--output)
                output_file="$2"
                shift 2
                ;;
            *)
                input_files+=("$1")
                shift
                ;;
        esac
    done

    if [[ ${#input_files[@]} -eq 0 ]]; then
        echo "❌ Error: No input files specified."
        echo "Usage: amir video concat <files...> [-o output.mp4]"
        return 1
    fi

    if [[ -z "$output_file" ]]; then
        local first_file
        first_file=$(basename "${input_files[0]%.*}")
        output_file="${first_file}_merged.mp4"
    fi

    local list_file
    list_file=$(mktemp "$(amir_preferred_temp_dir "$PWD")/video_concat_XXXXXX.txt")
    local valid_count=0

    echo "🎬 Preparing to concatenate ${#input_files[@]} files into $(basename "$output_file")"
    for f in "${input_files[@]}"; do
        if [[ -f "$f" ]]; then
            local abs_path
            abs_path=$(video_abspath "$f")
            echo "file '$abs_path'" >> "$list_file"
            echo "   🔗 $(basename "$f")"
            valid_count=$((valid_count + 1))
        else
            echo "   ⚠️  Skipping missing file: $f"
        fi
    done

    if [[ "$valid_count" -eq 0 ]]; then
        rm -f "$list_file"
        echo "❌ Error: No valid input files found."
        return 1
    fi

    if [[ -f "$output_file" && -s "$output_file" ]]; then
        rm -f "$list_file"
        echo "ℹ️  Fast-track: Output already exists: $output_file (skipping merge)"
        echo "$output_file"
        return 0
    fi

    local ffmpeg_path
    ffmpeg_path=$(get_ffmpeg_path)
    # Re-encoding avoids concat failures when source files differ in codecs/timebase.
    run_ffmpeg_with_progress "" \
        "$ffmpeg_path" -hide_banner -loglevel info -stats -y \
        -f concat -safe 0 -i "$list_file" \
        -c:v libx264 -crf 20 -preset medium \
        -c:a aac -b:a 192k -movflags +faststart "$output_file"
    local exit_code=$?
    rm -f "$list_file"

    if [[ $exit_code -eq 0 ]]; then
        echo "✅ Concatenation complete: $output_file"
        echo "$output_file"
    else
        echo "❌ FFmpeg failed to merge video files."
        return 1
    fi
}

video() {
    # Direct shared split subcommand
    if [[ "$1" == "split" ]]; then
        shift
        run_video_split "$@"
        return $?
    fi

    if [[ "$1" == "concat" || "$1" == "merge" ]]; then
        shift
        video_concat "$@"
        return $?
    fi

    # Support explicit 'compress' subcommand by skipping it
    if [[ "$1" == "compress" ]]; then
        shift
    fi

    # If no arguments, show help
    if [[ $# -eq 0 ]]; then
        echo "Usage: amir video compress <files...> [Resolution] [Quality] [--gpu|--cpu]"
        echo "       amir video concat <files...> [-o output.mp4]"
        echo "       amir video cut / trim <file> [options]"
        echo "       amir video split <file> <mb>"
        echo "       amir video batch <dir> [Resolution]"
        echo ""
        echo "Example (Compress): amir video compress movie.mp4 1080 60"
        echo "Example (Compress): amir video compress movie.mp4 --resolution 720 --quality 40"
        echo "Example (Concat):   amir video concat part1.mp4 part2.mp4 -o final.mp4"
        echo "Example (Trim):     amir video trim clip.mp4 -s 00:01:30 -t 00:03:00"
        echo "Example (Delete):   amir video cut clip.mp4 -d 00:01:00 00:02:00"
        echo ""
        echo "Options:"
        echo "  --gpu            Use hardware encoder (default on Apple Silicon)"
        echo "  --cpu            Use software encoder (better compression ratio)"
        echo "  --quality N      Set quality (1-100, higher = better)"
        echo "  --resolution N   Set resolution height (e.g. 720, 1080)"
        echo "  -s, --start      Start time (HH:MM:SS or seconds)"
        echo "  -e, --end        End time on original timeline (HH:MM:SS or seconds)"
        echo "  -t, --to         End time (alias for --end)"
        echo "  --duration       Duration from start"
        echo "  -d, --delete     Delete range: <start> <end> and stitch remaining parts"
        echo "  -x, --extract    Extract only range: <start> <end> into a clip file"
        echo "  -o, --output     Output filename"
        echo "  --subtitle-banner-image  Banner image behind subtitle area (full-width strip)"
        echo "  --subtitle-banner-color  Fallback banner color (used when no image is provided)"
        echo "  --subtitle-banner-height Banner strip height percent (default: 18)"
        echo "  --subtitle-logo          Channel logo image on bottom-right of banner"
        echo "  --subtitle-logo-animated Try animated logo rendering when codec/filter supports it"
        echo "  --subtitle-logo-width    Logo width percent of video width (default: 10)"
        echo "  --guest-tag             Guest lower-third: start,duration,name,title[,pos]"
        echo "  --guest-tag-pos         Default guest position: br|bl|tr|tl|bc|tc"
        return 1
    fi

    # Basic runtime checks
    if ! command -v ffmpeg &> /dev/null || ! command -v bc &> /dev/null; then
        echo "❌ Critical dependencies missing."
        echo "💡 Please run the installer: ./install.sh"
        return 1
    fi
    
    # Smart Argument Parsing
    local inputs=()
    local encoding_mode="--gpu"  # Default: GPU
    local extreme_mode=0
    local custom_fps=0
    local split_mb=0
    local force_reencode=0
    # Load defaults from Config
    local target_h=$(get_config "video" "resolution" "720")
    local quality=$(get_config "video" "quality" "70")
    
    # Validation for config values
    [[ "$target_h" =~ ^[0-9]+$ ]] || target_h=720
    [[ "$quality" =~ ^[0-9]+$ ]] || quality=60

    local args=("$@")
    local i=0
    while [[ $i -lt ${#args[@]} ]]; do
        local arg="${args[$i]}"
        case "$arg" in
            --gpu) encoding_mode="--gpu" ;;
            --cpu) encoding_mode="--cpu" ;;
            extreme|EXTREME)
                extreme_mode=1
                target_h=360
                quality=30
                encoding_mode="--cpu"
                ;;
            --fps)
                i=$(( i + 1 ))
                custom_fps="${args[$i]:-0}"
                ;;
            --quality)
                i=$(( i + 1 ))
                quality="${args[$i]:-70}"
                ;;
            --resolution)
                i=$(( i + 1 ))
                target_h="${args[$i]:-720}"
                ;;
            --split)
                i=$(( i + 1 ))
                split_mb="${args[$i]:-0}"
                ;;
            --force)
                force_reencode=1
                ;;
            *)
                if [[ -f "$arg" || -d "$arg" ]]; then
                    inputs+=("$arg")
                elif [[ "$arg" =~ ^[0-9]+$ ]]; then
                    if [[ "$arg" -le 100 ]]; then
                        quality="$arg"
                    else
                        target_h="$arg"
                    fi
                fi
                ;;
        esac
        i=$(( i + 1 ))
    done

    if [[ ${#inputs[@]} -eq 0 ]]; then
        echo "❌ No valid input files or directories found."
        return 1
    fi

    load_learning_data

    # Process all inputs
    for input in "${inputs[@]}"; do
        if [[ -f "$input" ]]; then
            process_video "$input" "$target_h" "$quality" "$encoding_mode" "$extreme_mode" "$custom_fps" "$split_mb" "$force_reencode"
        elif [[ -d "$input" ]]; then
            echo "📦 Batch processing directory: $input"
            find "$input" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.mov" -o -name "*.mkv" -o -name "*.MP4" -o -name "*.MOV" -o -name "*.MKV" \) | while read -r file; do
                process_video "$file" "$target_h" "$quality" "$encoding_mode" "$extreme_mode" "$custom_fps" "$split_mb" "$force_reencode" < /dev/null
            done
        fi
    done
}

run_video_cut() {
    local input_file=""
    local start_time=""
    local end_time=""
    local duration=""
    local extract_start=""
    local extract_end=""
    local extract_mode=0
    local delete_start=""
    local delete_end=""
    local delete_mode=0
    local output_file=""
    local subtitle_file=""
    local cover_frame_file=""
    local fonts_dir=""
    local encode=0
    local render_resolution=""
    local render_quality=""
    local render_fps=""
    local split_mb=""
    local pad_bottom_pct=0
    local subtitle_banner_image=""
    local subtitle_banner_color=""
    local subtitle_banner_height_pct="18"
    local subtitle_logo_image=""
    local subtitle_logo_animated=0
    local subtitle_logo_width_pct="10"
    local subtitle_logo_margin_right="24"
    local subtitle_logo_margin_bottom="24"
    local guest_tag_default_pos="br"
    local -a guest_tags=()
    
    # UI Display Overrides (for symlinked/temp files)
    local display_in=""
    local display_out=""
    local render_tmp_dir=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -s|--start) start_time="$2"; shift 2 ;;
            -e|--end) end_time="$2"; shift 2 ;;
            -t|--to) end_time="$2"; shift 2 ;;
            --duration) duration="$2"; shift 2 ;;
            -x|--extract)
                extract_mode=1
                extract_start="$2"
                extract_end="$3"
                shift 3
                ;;
            -d|--delete)
                # Backward compatibility: old -d <duration>
                if [[ "$1" == "-d" && ( -z "${3:-}" || "${2:-}" == -* || "${3:-}" == -* ) ]]; then
                    duration="$2"
                    shift 2
                else
                    delete_mode=1
                    delete_start="$2"
                    delete_end="$3"
                    shift 3
                fi
                ;;
            -o|--output) output_file="$2"; shift 2 ;;
            --subtitles) subtitle_file="$2"; shift 2 ;;
            --cover-frame) cover_frame_file="$2"; shift 2 ;;
            --fonts-dir) fonts_dir="$2"; shift 2 ;;
            --display-input) display_in="$2"; shift 2 ;;
            --display-output) display_out="$2"; shift 2 ;;
            --resolution) render_resolution="$2"; shift 2 ;;
            --quality) render_quality="$2"; shift 2 ;;
            --fps) render_fps="$2"; shift 2 ;;
            --split) split_mb="$2"; shift 2 ;;
            --pad-bottom) pad_bottom_pct="$2"; shift 2 ;;
            --subtitle-banner-image) subtitle_banner_image="$2"; shift 2 ;;
            --subtitle-banner-color) subtitle_banner_color="$2"; shift 2 ;;
            --subtitle-banner-height) subtitle_banner_height_pct="$2"; shift 2 ;;
            --subtitle-logo) subtitle_logo_image="$2"; shift 2 ;;
            --subtitle-logo-animated) subtitle_logo_animated=1; shift ;;
            --subtitle-logo-width) subtitle_logo_width_pct="$2"; shift 2 ;;
            --subtitle-logo-margin-right) subtitle_logo_margin_right="$2"; shift 2 ;;
            --subtitle-logo-margin-bottom) subtitle_logo_margin_bottom="$2"; shift 2 ;;
            --guest-tag) guest_tags+=("$2"); shift 2 ;;
            --guest-tag-pos) guest_tag_default_pos="$2"; shift 2 ;;
            --render) encode=1; shift ;;
            *) 
                if [[ -f "$1" && -z "$input_file" ]]; then
                    input_file="$1"
                    shift
                else
                    echo "Unknown argument: $1"
                    return 1
                fi
                ;;
        esac
    done

    if [[ -z "$input_file" ]]; then
        echo "❌ Error: No input file specified."
        echo "Usage: amir video cut <file> [-s start] [-e end] [--duration d] [-d start end] [-x start end] [-o output] [--resolution H] [--quality Q] [--fps N] [--split MB] [--cover-frame IMG] [--subtitle-banner-image IMG|--subtitle-banner-color C] [--subtitle-logo IMG] [--guest-tag 'start,duration,name,title[,pos]']"
        return 1
    fi

    if [[ $extract_mode -eq 1 && $delete_mode -eq 1 ]]; then
        echo "❌ Error: --extract cannot be combined with --delete."
        return 1
    fi

    if [[ $extract_mode -eq 1 && ( -n "$start_time" || -n "$end_time" || -n "$duration" || -n "$delete_start" || -n "$delete_end" ) ]]; then
        echo "❌ Error: --extract cannot be combined with --start/--end/--duration/--delete in the same command."
        return 1
    fi

    if [[ $delete_mode -eq 1 && ( -n "$start_time" || -n "$end_time" || -n "$duration" ) ]]; then
        echo "❌ Error: --delete cannot be combined with --start/--end/--duration in the same command."
        return 1
    fi

    if [[ $extract_mode -eq 1 ]]; then
        start_time="$extract_start"
        end_time="$extract_end"
        if [[ -z "$start_time" || -z "$end_time" ]]; then
            echo "❌ Error: --extract requires both start and end times."
            return 1
        fi
    fi

        # Split-only fast path: if the user asked only for chunking, don't create an
    # unnecessary *_cut file first. Just split the original input directly.
    if [[ -n "$split_mb" && "$split_mb" =~ ^[0-9]+$ && "$split_mb" -gt 0 \
          && -z "$start_time" && -z "$end_time" && -z "$duration" \
            && $delete_mode -eq 0 \
          && -z "$subtitle_file" && -z "$fonts_dir" \
          && -z "$render_resolution" && -z "$render_quality" && -z "$render_fps" \
          && "$encode" -eq 0 && -z "$output_file" ]]; then
        echo "✂️  Split-only mode: reusing source file without creating *_cut output"
        split_video_by_size_strict "$input_file" "$split_mb"
        return $?
    fi

    # Auto-generate output name if not provided
    if [[ -z "$output_file" ]]; then
        local base="${input_file%.*}"
        local ext="${input_file##*.}"
        _time_token() {
            local value="$1"
            value="${value//:/-}"
            value="${value//./-}"
            value="${value// /_}"
            printf '%s' "$value"
        }
        if [[ $extract_mode -eq 1 ]]; then
            output_file="${base}_cut_$(_time_token "$extract_start")_$(_time_token "$extract_end").${ext}"
        else
            output_file="${base}_cut.${ext}"
        fi
    fi

    # Keep render-time temp files off system /tmp when possible.
    # This prevents subtitle rendering from failing on machines with a full local temp volume.
    local tmp_parent
    tmp_parent="$(dirname "$output_file")"
    [[ -d "$tmp_parent" ]] || tmp_parent="$(dirname "$input_file")"
    if [[ -d "$tmp_parent" ]]; then
        if ! tmp_parent="$(cd "$tmp_parent" 2>/dev/null && pwd -P)"; then
            tmp_parent=""
        fi
    fi
    if [[ -n "$tmp_parent" ]]; then
        render_tmp_dir="$tmp_parent/.amir_tmp_$$"
        mkdir -p "$render_tmp_dir" 2>/dev/null || render_tmp_dir=""
    fi

    cleanup_render_tmp() {
        if [[ -n "$render_tmp_dir" && -d "$render_tmp_dir" ]]; then
            rm -rf "$render_tmp_dir"
        fi
    }
    trap cleanup_render_tmp EXIT

    if [[ -n "$render_tmp_dir" ]]; then
        export TMPDIR="$render_tmp_dir"
    fi

    echo "🎬  Processing Video: ${display_in:-$(basename "$input_file")}"
    
    # Allow override of ffmpeg binary via env var (e.g. from static_ffmpeg in python)
    local ffmpeg_cmd="${FFMPEG_EXEC:-ffmpeg}"

    local cmd=("$ffmpeg_cmd" "-hide_banner" "-loglevel" "error" "-stats" "-y")
    local next_filter_input_idx=1
    local cover_input_idx=-1
    local banner_input_idx=-1
    local logo_input_idx=-1

    # Convert time expressions (SS, MM:SS, HH:MM:SS) to seconds.
    # Used to turn absolute end times into a true clip duration when start is set.
    _to_seconds() {
        local ts="$1"
        awk -v t="$ts" 'BEGIN {
            n = split(t, a, ":")
            if (n == 1) {
                printf "%.6f", a[1] + 0
            } else if (n == 2) {
                printf "%.6f", (a[1] * 60) + a[2]
            } else if (n == 3) {
                printf "%.6f", (a[1] * 3600) + (a[2] * 60) + a[3]
            } else {
                print ""
            }
        }'
    }

    if [[ $delete_mode -eq 1 ]]; then
        local delete_start_seconds
        local delete_end_seconds
        local input_duration

        delete_start_seconds="$(_to_seconds "$delete_start")"
        delete_end_seconds="$(_to_seconds "$delete_end")"
        input_duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null)

        if [[ -z "$delete_start_seconds" || -z "$delete_end_seconds" || -z "$input_duration" ]]; then
            echo "❌ Error: Invalid time format for --delete or unreadable input duration."
            return 1
        fi

        if awk -v s="$delete_start_seconds" -v e="$delete_end_seconds" 'BEGIN { exit (e <= s) ? 0 : 1 }'; then
            echo "❌ Error: delete end must be greater than delete start."
            return 1
        fi

        if awk -v s="$delete_start_seconds" -v d="$input_duration" 'BEGIN { exit (s >= d) ? 0 : 1 }'; then
            echo "❌ Error: delete start is beyond video duration."
            return 1
        fi

        if awk -v e="$delete_end_seconds" -v d="$input_duration" 'BEGIN { exit (e > d) ? 0 : 1 }'; then
            delete_end_seconds="$input_duration"
        fi

        echo "✂️  Mode: Delete Range and Stitch"

        local tmp_parent
        tmp_parent="$(dirname "$output_file")"
        [[ -d "$tmp_parent" ]] || tmp_parent="$(dirname "$input_file")"
        if ! tmp_parent="$(cd "$tmp_parent" 2>/dev/null && pwd -P)"; then
            echo "❌ Error: Failed to resolve temp directory path."
            return 1
        fi

        local tmp_dir
        tmp_dir=$(mktemp -d "$tmp_parent/.amir_delete_XXXXXX")
        if [[ -z "$tmp_dir" || ! -d "$tmp_dir" ]]; then
            echo "❌ Error: Failed to create temporary directory."
            return 1
        fi

        local part1="$tmp_dir/part1.${input_file##*.}"
        local part2="$tmp_dir/part2.${input_file##*.}"
        local list_file="$tmp_dir/concat_list.txt"
        local part1_abs=""
        local part2_abs=""
        local has_part=0
        local has_audio_track=0
        if ffprobe -v error -select_streams a:0 -show_entries stream=index -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null | head -n1 | grep -q '^[0-9]'; then
            has_audio_track=1
        fi

        if awk -v s="$delete_start_seconds" 'BEGIN { exit (s > 0.01) ? 0 : 1 }'; then
            "$ffmpeg_cmd" -hide_banner -loglevel error -stats -y \
                -ss 0 -i "$input_file" -t "$delete_start_seconds" \
                -map 0:v:0 -map 0:a? -sn -dn -c copy "$part1"
            if [[ $? -ne 0 ]]; then
                rm -rf "$tmp_dir"
                echo "❌ Error: Failed to build first segment."
                return 1
            fi
            if ! part1_abs="$(cd "$(dirname "$part1")" && pwd -P)/$(basename "$part1")"; then
                rm -rf "$tmp_dir"
                echo "❌ Error: Failed to resolve first segment path."
                return 1
            fi
            echo "file '$part1_abs'" >> "$list_file"
            has_part=1
        fi

        if awk -v e="$delete_end_seconds" -v d="$input_duration" 'BEGIN { exit (e < d - 0.01) ? 0 : 1 }'; then
            "$ffmpeg_cmd" -hide_banner -loglevel error -stats -y \
                -ss "$delete_end_seconds" -i "$input_file" \
                -map 0:v:0 -map 0:a? -sn -dn -c copy "$part2"
            if [[ $? -ne 0 ]]; then
                rm -rf "$tmp_dir"
                echo "❌ Error: Failed to build second segment."
                return 1
            fi
            if ! part2_abs="$(cd "$(dirname "$part2")" && pwd -P)/$(basename "$part2")"; then
                rm -rf "$tmp_dir"
                echo "❌ Error: Failed to resolve second segment path."
                return 1
            fi
            echo "file '$part2_abs'" >> "$list_file"
            has_part=1
        fi

        if [[ $has_part -eq 0 || ! -s "$list_file" ]]; then
            rm -rf "$tmp_dir"
            echo "❌ Error: delete range removed the whole video."
            return 1
        fi

        local stitched_copy="$tmp_dir/stitched_copy.${input_file##*.}"
        local concat_log="$tmp_dir/concat_stitch.log"

        "$ffmpeg_cmd" -hide_banner -loglevel warning -stats -y \
            -f concat -safe 0 -i "$list_file" \
            -fflags +genpts -avoid_negative_ts make_zero \
            -map 0:v:0 -map 0:a? -sn -dn -c copy -map_metadata 0 "$stitched_copy" >"$concat_log" 2>&1
        local delete_exit=$?

        if [[ $delete_exit -ne 0 || ! -f "$stitched_copy" ]]; then
            echo "ℹ️  Auto-fix fallback: concat copy failed, rebuilding with re-encode..."
            if [[ $has_audio_track -eq 1 ]]; then
                "$ffmpeg_cmd" -hide_banner -loglevel error -stats -y \
                    -f concat -safe 0 -i "$list_file" \
                    -map 0:v:0 -map 0:a? -sn -dn \
                    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
                    -c:a aac -b:a 160k -af aresample=async=1:first_pts=0 \
                    -movflags +faststart -map_metadata 0 "$output_file"
            else
                "$ffmpeg_cmd" -hide_banner -loglevel error -stats -y \
                    -f concat -safe 0 -i "$list_file" \
                    -map 0:v:0 -sn -dn \
                    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
                    -an -movflags +faststart -map_metadata 0 "$output_file"
            fi

            if [[ $? -ne 0 || ! -f "$output_file" ]]; then
                rm -rf "$tmp_dir"
                rm -f "$output_file"
                echo "❌ Error: Failed to stitch remaining segments."
                return 1
            fi

            rm -rf "$tmp_dir"

            echo ""
            echo "✅ COMPLETE: $(basename "$output_file")"
            echo "📍 Output: $(realpath "$output_file")"

            if [[ -n "$split_mb" && "$split_mb" =~ ^[0-9]+$ && "$split_mb" -gt 0 ]]; then
                echo ""
                split_video_by_size_strict "$output_file" "$split_mb"
            fi
            return 0
        fi

        local needs_timestamp_fix=0
        if grep -qi "Non-monotonic DTS" "$concat_log"; then
            needs_timestamp_fix=1
        fi

        if [[ $needs_timestamp_fix -eq 1 ]]; then
            echo "ℹ️  Auto-fix: normalizing timestamps for seamless playback..."
        fi

        echo "ℹ️  Auto-fix: ensuring audio/video sync..."
        if [[ $has_audio_track -eq 1 ]]; then
            "$ffmpeg_cmd" -hide_banner -loglevel error -stats -y \
                -fflags +genpts -i "$stitched_copy" \
                -map 0:v:0 -map 0:a? -sn -dn \
                -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
                -c:a aac -b:a 160k -af aresample=async=1:first_pts=0 \
                -movflags +faststart -map_metadata 0 "$output_file"
        else
            "$ffmpeg_cmd" -hide_banner -loglevel error -stats -y \
                -fflags +genpts -i "$stitched_copy" \
                -map 0:v:0 -sn -dn \
                -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
                -an -movflags +faststart -map_metadata 0 "$output_file"
        fi

        if [[ $? -ne 0 || ! -f "$output_file" ]]; then
            rm -rf "$tmp_dir"
            rm -f "$output_file"
            echo "❌ Error: Auto-fix failed while rebuilding stitched output."
            return 1
        fi

        rm -rf "$tmp_dir"

        echo ""
        echo "✅ COMPLETE: $(basename "$output_file")"
        echo "📍 Output: $(realpath "$output_file")"

        if [[ -n "$split_mb" && "$split_mb" =~ ^[0-9]+$ && "$split_mb" -gt 0 ]]; then
            echo ""
            split_video_by_size_strict "$output_file" "$split_mb"
        fi
        return 0
    fi
    
    # Start time (seek)
    if [[ -n "$start_time" ]]; then
        cmd+=("-ss" "$start_time")
    fi

    cmd+=("-i" "$input_file")
    local output_time_opts=()

    if [[ -n "$end_time" ]]; then
        if [[ -n "$start_time" ]]; then
            local start_seconds
            local end_seconds
            start_seconds="$(_to_seconds "$start_time")"
            end_seconds="$(_to_seconds "$end_time")"

            if [[ -z "$start_seconds" || -z "$end_seconds" ]]; then
                echo "❌ Error: Invalid time format for --start/--end."
                return 1
            fi

            local clip_duration
            clip_duration=$(awk -v s="$start_seconds" -v e="$end_seconds" 'BEGIN { printf "%.6f", e - s }')
            if awk -v d="$clip_duration" 'BEGIN { exit (d <= 0) ? 0 : 1 }'; then
                echo "❌ Error: --end must be greater than --start."
                return 1
            fi

            output_time_opts=("-t" "$clip_duration")
        else
            # No explicit start seek: keep native ffmpeg absolute-end behavior.
            output_time_opts=("-to" "$end_time")
        fi
    elif [[ -n "$duration" ]]; then
        output_time_opts=("-t" "$duration")
    fi

    # Optional cover frame image: injected as first frame during render.
    if [[ -n "$cover_frame_file" && -f "$cover_frame_file" ]]; then
        cover_input_idx=$next_filter_input_idx
        cmd+=("-i" "$cover_frame_file")
        ((next_filter_input_idx++))
    fi

    # Subtitle Filter Logic
    local subtitle_filter=""
    local banner_overlay_enabled=0
    local logo_overlay_enabled=0
    local guest_overlay_enabled=0
    local tmp_sub="" 

    # Helper function for FFmpeg filter escaping
    escape_ffmpeg() {
        local s="$1"
        s="${s//\\/\\\\}"  # \ -> \\
        s="${s//:/\\:}"    # : -> \:
        s="${s//\'/\\\'}"  # ' -> \'
        s="${s//,/\\,}"    # , -> \,
        s="${s//\[/\\[}"   # [ -> \[
        s="${s//\]/\\]}"   # ] -> \]
        s="${s// /\\ }"    # Space -> \ Space
        echo "$s"
    }

    # Cleanup trap (will run on exit)
    cleanup_subs() {
        if [[ -n "$tmp_sub" && -f "$tmp_sub" ]]; then
            rm -f "$tmp_sub"
        fi
    }
    trap cleanup_subs EXIT

    if [[ -n "$subtitle_file" ]]; then
        # Create safe temp copy to avoid FFmpeg parsing headaches with spaces/special chars
        tmp_sub="$render_tmp_dir/safe_subs_$$.ass"
        cp "$subtitle_file" "$tmp_sub"

        # Check fonts dir
        local fonts_opt=""
        if [[ -n "$fonts_dir" ]]; then
            local esc_fonts=$(escape_ffmpeg "$fonts_dir")
            fonts_opt=":fontsdir=${esc_fonts}"
        fi
        
        # Use safe temp path (no spaces/special chars guaranteed by /tmp/safe_subs_$$.ass)
        # But escape it just in case /tmp path has weirdness (unlikely)
        local esc_sub=$(escape_ffmpeg "$tmp_sub") 
        
        # Use subtitles filter with explicit filename key
        subtitle_filter="subtitles=filename=${esc_sub}${fonts_opt}"
        
        # If subtitles are present, force render mode
        encode=1
    fi

    if [[ -n "$subtitle_banner_image" ]]; then
        if [[ -f "$subtitle_banner_image" ]]; then
            banner_overlay_enabled=1
        else
            echo "⚠️  Banner image not found, skipping overlay: $subtitle_banner_image"
        fi
    fi
    if [[ -n "$subtitle_banner_color" ]]; then
        banner_overlay_enabled=1
    fi
    if [[ -n "$subtitle_logo_image" ]]; then
        if [[ -f "$subtitle_logo_image" ]]; then
            logo_overlay_enabled=1
        else
            echo "⚠️  Logo image not found, skipping overlay: $subtitle_logo_image"
        fi
    fi

    # Sanitize numeric overlay controls.
    [[ "$subtitle_banner_height_pct" =~ ^[0-9]+$ ]] || subtitle_banner_height_pct="18"
    [[ "$subtitle_logo_width_pct" =~ ^[0-9]+$ ]] || subtitle_logo_width_pct="10"
    [[ "$subtitle_logo_margin_right" =~ ^[0-9]+$ ]] || subtitle_logo_margin_right="24"
    [[ "$subtitle_logo_margin_bottom" =~ ^[0-9]+$ ]] || subtitle_logo_margin_bottom="24"
    (( subtitle_banner_height_pct < 5 || subtitle_banner_height_pct > 80 )) && subtitle_banner_height_pct=18
    (( subtitle_logo_width_pct < 2 || subtitle_logo_width_pct > 40 )) && subtitle_logo_width_pct=10

    if [[ $banner_overlay_enabled -eq 1 || $logo_overlay_enabled -eq 1 ]]; then
        encode=1
    fi
    if [[ ${#guest_tags[@]} -gt 0 ]]; then
        guest_overlay_enabled=1
        encode=1
    fi

    # Provide stable overlay sources via dedicated ffmpeg inputs (instead of movie filter sources).
    if [[ $banner_overlay_enabled -eq 1 && -n "$subtitle_banner_image" && -f "$subtitle_banner_image" ]]; then
        banner_input_idx=$next_filter_input_idx
        cmd+=("-loop" "1" "-i" "$subtitle_banner_image")
        ((next_filter_input_idx++))
    fi
    if [[ $logo_overlay_enabled -eq 1 && -n "$subtitle_logo_image" && -f "$subtitle_logo_image" ]]; then
        logo_input_idx=$next_filter_input_idx
        if [[ $subtitle_logo_animated -eq 1 ]]; then
            cmd+=("-stream_loop" "-1" "-i" "$subtitle_logo_image")
        else
            cmd+=("-loop" "1" "-i" "$subtitle_logo_image")
        fi
        ((next_filter_input_idx++))
    fi

    if [[ ${#output_time_opts[@]} -gt 0 ]]; then
        cmd+=("${output_time_opts[@]}")
    fi

    if [[ $encode -eq 1 ]]; then
        echo "⚙️  Mode: Rendering (High Quality)"
        
        # Hardware Detection & Quality Settings (Reuse logic from process_video is ideal, but here we inline for now)
        # TODO: Refactor process_video to return flags to avoid duplication. 
        # For now, we use the simple "working well" logic + Bitrate Cap.
        
        local target_h=""
        # Default to input video height when no render resolution is provided.
        target_h=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null)
        [[ -z "$target_h" || ! "$target_h" =~ ^[0-9]+$ ]] && target_h=$(get_config "video" "resolution" "720")
        local quality=$(get_config "video" "quality" "70")

        # Per-run render overrides (passed through subtitle/compress pipeline)
        [[ -n "$render_resolution" && "$render_resolution" =~ ^[0-9]+$ ]] && target_h="$render_resolution"
        [[ -n "$render_quality" && "$render_quality" =~ ^[0-9]+$ ]] && quality="$render_quality"
        [[ -n "$render_fps" && "$render_fps" =~ ^[0-9]+$ ]] && render_fps="$render_fps"
        
        # Hardware Detection & Smart Encoder Selection
        # Always use H.264 for maximum compatibility (Telegram, QuickTime, etc.)
        local encoder="libx264"
        
        # Bitrate Logic (Match Input)
        local bitrate_flags=()
        local input_bitrate=""
        local target_bitrate_val=""
        
        # 1. Try Container Bitrate first (usually more accurate for file size)
        input_bitrate=$(ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null)
        
        # 2. Fallback to Stream Bitrate
        if [[ -z "$input_bitrate" || ! "$input_bitrate" =~ ^[0-9]+$ ]]; then
             input_bitrate=$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null)
        fi

        if [[ -n "$input_bitrate" && "$input_bitrate" =~ ^[0-9]+$ ]]; then
             # Heuristic: HEVC is ~50% more efficient than H.264.
             # Target 80% bitrate for HEVC to ensure better quality but smaller size.
             # Target 100% (or slightly more) for H.264 to preserve quality in re-encode.
             local multiplier="1.0"
             if [[ "$encoder" == "hevc_videotoolbox" || "$encoder" == "hevc_nvenc" || "$encoder" == "libx265" ]]; then
                 multiplier="0.8"
             fi
             
             target_bitrate_val=$(echo "$input_bitrate * $multiplier / 1" | bc)
             
             # Maxrate slightly higher for VBR headroom
             local max_rat=$(echo "$target_bitrate_val * 1.5 / 1" | bc)
             local buf=$(echo "$max_rat * 2" | bc)
             
             bitrate_flags=("-maxrate" "${max_rat}" "-bufsize" "${buf}")
        fi

        echo "📊 Settings: $encoder (Q:$quality) | Bitrate Target: ${target_bitrate_val:-Auto}"

        # Build pre-filters (scale/fps) and combine with subtitle filter if present.
        local pre_filter=""
        if [[ -n "$render_fps" && "$render_fps" =~ ^[0-9]+$ && "$render_fps" -gt 0 ]]; then
            pre_filter="fps=${render_fps}"
        fi

        # ── Padding & Scaling ──
        if [[ -n "$pad_bottom_pct" && "$pad_bottom_pct" -gt 0 ]]; then
            # Build the padding filter. We scale down the video content and pad it 
            # so it sits at the top, leaving a black bar at the bottom.
            # Factor is (100 - P) / 100
            local factor_num=$(( 100 - pad_bottom_pct ))
            if [[ -n "$pre_filter" ]]; then pre_filter+=","; fi
            pre_filter+="scale='iw*${factor_num}/100':-2,pad='iw*100/${factor_num}':'ih*100/${factor_num}':(ow-iw)/2:0:black"
        fi

        if [[ -n "$target_h" && "$target_h" =~ ^[0-9]+$ && "$target_h" -gt 0 ]]; then
            if [[ -n "$pre_filter" ]]; then
                pre_filter+=","
            fi
            pre_filter+="scale=-2:${target_h}"
        fi

        local final_filter=""
        if [[ -n "$pre_filter" && -n "$subtitle_filter" ]]; then
            final_filter="${pre_filter},${subtitle_filter}"
        elif [[ -n "$pre_filter" ]]; then
            final_filter="$pre_filter"
        else
            final_filter="$subtitle_filter"
        fi

        local guest_font_file=""
        local -a guest_font_candidates=(
            "$HOME/Library/Fonts/Vazirmatn-Regular.ttf"
            "$HOME/Library/Fonts/Vazirmatn[wght].ttf"
            "/Library/Fonts/Vazirmatn-Regular.ttf"
            "/Library/Fonts/Arial Unicode.ttf"
            "/Library/Fonts/Arial Unicode MS.ttf"
            "/Library/Fonts/Arial.ttf"
        )
        local _fcand
        for _fcand in "${guest_font_candidates[@]}"; do
            if [[ -f "$_fcand" ]]; then
                guest_font_file="$_fcand"
                break
            fi
        done

        local guest_filter=""
        if [[ $guest_overlay_enabled -eq 1 ]]; then
            local guest_font_opt=""
            if [[ -n "$guest_font_file" ]]; then
                guest_font_opt=":fontfile=$(escape_ffmpeg "$guest_font_file")"
            fi

            escape_drawtext_text() {
                local t="$1"
                t="${t//\\/\\\\}"
                t="${t//:/\\:}"
                t="${t//\'/\\\'}"
                t="${t//,/\\,}"
                t="${t//%/\\%}"
                t="${t//\[/\\[}"
                t="${t//\]/\\]}"
                printf '%s' "$t"
            }

            local _tag _g_start _g_dur _g_name _g_role _g_pos _g_start_sec _g_dur_sec _g_end_sec
            for _tag in "${guest_tags[@]}"; do
                IFS=',' read -r _g_start _g_dur _g_name _g_role _g_pos <<< "$_tag"
                [[ -z "$_g_start" || -z "$_g_dur" || -z "$_g_name" || -z "$_g_role" ]] && continue
                _g_start_sec="$(_to_seconds "$_g_start")"
                _g_dur_sec="$(_to_seconds "$_g_dur")"
                [[ -z "$_g_start_sec" || -z "$_g_dur_sec" ]] && continue
                _g_end_sec=$(awk -v s="$_g_start_sec" -v d="$_g_dur_sec" 'BEGIN { printf "%.6f", s + d }')

                if [[ -z "$_g_pos" ]]; then
                    _g_pos="$guest_tag_default_pos"
                fi
                _g_pos="$(printf '%s' "$_g_pos" | tr '[:upper:]' '[:lower:]')"

                local _x_expr="w-tw-34"
                local _y1_expr="h-(h*0.20)"
                case "$_g_pos" in
                    bl) _x_expr="34"; _y1_expr="h-(h*0.20)" ;;
                    tr) _x_expr="w-tw-34"; _y1_expr="34" ;;
                    tl) _x_expr="34"; _y1_expr="34" ;;
                    bc) _x_expr="(w-tw)/2"; _y1_expr="h-(h*0.20)" ;;
                    tc) _x_expr="(w-tw)/2"; _y1_expr="34" ;;
                    *) _x_expr="w-tw-34"; _y1_expr="h-(h*0.20)" ;;
                esac

                local _name_esc _role_esc
                _name_esc="$(escape_drawtext_text "$_g_name")"
                _role_esc="$(escape_drawtext_text "$_g_role")"

                local _dt1="drawtext=text='${_name_esc}'${guest_font_opt}:fontcolor=white:fontsize=h*0.050:box=1:boxcolor=0x2D1588EE@0.88:boxborderw=18:x=${_x_expr}:y=${_y1_expr}:enable='between(t,${_g_start_sec},${_g_end_sec})'"
                local _dt2="drawtext=text='${_role_esc}'${guest_font_opt}:fontcolor=0xFFE066:fontsize=h*0.036:box=1:boxcolor=0x2D1588EE@0.88:boxborderw=14:x=${_x_expr}:y=${_y1_expr}+h*0.065:enable='between(t,${_g_start_sec},${_g_end_sec})'"

                if [[ -z "$guest_filter" ]]; then
                    guest_filter="${_dt1},${_dt2}"
                else
                    guest_filter+=",${_dt1},${_dt2}"
                fi
            done
        fi
        
        # Construct Filter Chain
        local use_cover_frame=false
        if [[ -n "$cover_frame_file" && -f "$cover_frame_file" ]]; then
            use_cover_frame=true
        fi

        local overlay_fc=""
        local overlay_out_label=""
        if [[ $banner_overlay_enabled -eq 1 || $logo_overlay_enabled -eq 1 ]]; then
            local _curr_label="vbase"
            local _overlay_segments=()
            if [[ -n "$pre_filter" ]]; then
                _overlay_segments+=("[0:v]${pre_filter}[${_curr_label}]")
            else
                _overlay_segments+=("[0:v]null[${_curr_label}]")
            fi

            if [[ $banner_overlay_enabled -eq 1 ]]; then
                if [[ -n "$subtitle_banner_image" && -f "$subtitle_banner_image" ]]; then
                    _overlay_segments+=("[${banner_input_idx}:v]setpts=PTS-STARTPTS[banner_src]")
                else
                    local banner_color="${subtitle_banner_color:-0x0A4DFF@1.0}"
                    _overlay_segments+=("color=c=${banner_color}:s=16x16[banner_src]")
                fi
                _overlay_segments+=("[banner_src][${_curr_label}]scale2ref=w=main_w:h=main_h*${subtitle_banner_height_pct}/100[banner][banner_base]")
                _overlay_segments+=("[banner_base][banner]overlay=0:main_h-overlay_h:shortest=1:eof_action=pass[vbanner]")
                _curr_label="vbanner"
            fi

            if [[ $logo_overlay_enabled -eq 1 ]]; then
                _overlay_segments+=("[${logo_input_idx}:v]setpts=PTS-STARTPTS[logo_src]")
                _overlay_segments+=("[logo_src][${_curr_label}]scale2ref=w=main_w*${subtitle_logo_width_pct}/100:h=-1[logo][logo_base]")
                _overlay_segments+=("[logo_base][logo]overlay=main_w-overlay_w-${subtitle_logo_margin_right}:main_h-overlay_h-${subtitle_logo_margin_bottom}:shortest=1:eof_action=pass[vlogo]")
                _curr_label="vlogo"
            fi

            if [[ -n "$subtitle_filter" ]]; then
                _overlay_segments+=("[${_curr_label}]${subtitle_filter}[vsub]")
                _curr_label="vsub"
            fi

            if [[ -n "$guest_filter" ]]; then
                _overlay_segments+=("[${_curr_label}]${guest_filter}[vguest]")
                _curr_label="vguest"
            fi

            local _seg
            for _seg in "${_overlay_segments[@]}"; do
                if [[ -z "$overlay_fc" ]]; then
                    overlay_fc="$_seg"
                else
                    overlay_fc+=";$_seg"
                fi
            done
            overlay_out_label="$_curr_label"
        fi

        if [[ -z "$overlay_fc" && -n "$guest_filter" ]]; then
            if [[ -n "$final_filter" ]]; then
                final_filter+="${final_filter:+,}${guest_filter}"
            else
                final_filter="$guest_filter"
            fi
        fi

        # H.264 with CRF (match input quality, prevent bloat)
        local crf_val=$(( (100 - quality) * 51 / 100 ))
        [[ $crf_val -lt 18 ]] && crf_val=18

        if $use_cover_frame; then
            local _fc=""
            if [[ -n "$overlay_fc" ]]; then
                _fc="${overlay_fc};[${overlay_out_label}]null[vmain];[${cover_input_idx}:v][vmain]scale2ref[cover][vref];[vref][cover]overlay=0:0:enable='lte(t,0.08)':eof_action=pass[vout]"
            else
                local _vprep="null"
                [[ -n "$final_filter" ]] && _vprep="$final_filter"
                _fc="[0:v]${_vprep}[vmain];[${cover_input_idx}:v][vmain]scale2ref[cover][vref];[vref][cover]overlay=0:0:enable='lte(t,0.08)':eof_action=pass[vout]"
            fi
            cmd+=("-filter_complex" "$_fc" "-map" "[vout]" "-map" "0:a?" "-c:v" "libx264" "-crf" "$crf_val" "${bitrate_flags[@]}" "-preset" "medium" "-pix_fmt" "yuv420p" "-c:a" "copy")
        elif [[ -n "$overlay_fc" ]]; then
            cmd+=("-filter_complex" "$overlay_fc" "-map" "[${overlay_out_label}]" "-map" "0:a?" "-c:v" "libx264" "-crf" "$crf_val" "${bitrate_flags[@]}" "-preset" "medium" "-pix_fmt" "yuv420p" "-c:a" "copy")
        elif [[ -n "$final_filter" ]]; then
            cmd+=("-vf" "$final_filter" "-c:v" "libx264" "-crf" "$crf_val" "${bitrate_flags[@]}" "-preset" "medium" "-pix_fmt" "yuv420p" "-c:a" "copy")
        else
            # No filters path
            cmd+=("-c:v" "libx264" "-crf" "23" "${bitrate_flags[@]}" "-preset" "medium" "-c:a" "copy")
        fi
    else
        echo "🚀 Mode: Stream Copy (Instant)"
        cmd+=("-c" "copy")
    fi

    cmd+=("-map_metadata" "0" "$output_file")

# --- Table Helpers (The Scientific Way) ---

# --- Table Helpers (The Scientific Way) ---
# Functions get_visual_width and pad_to_width are now globally available via amir_lib.sh

    # Execute with animated progress bar
    # 1. Get the duration for the progress bar
    local duration_seconds=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null | awk '{print int($1)}')
    
    # If a specific duration (-t) was passed in the cmd array, use that instead
    local extracted_duration=""
    for ((i=0; i<${#cmd[@]}; i++)); do
        if [[ "${cmd[$i]}" == "-t" ]]; then
            extracted_duration="${cmd[$i+1]}"
            break
        fi
    done
    
    if [[ -n "$extracted_duration" ]]; then
        # Check if HH:MM:SS format
        if [[ "$extracted_duration" == *":"* ]]; then
            local h=$(echo "$extracted_duration" | cut -d':' -f1)
            local m=$(echo "$extracted_duration" | cut -d':' -f2)
            local s=$(echo "$extracted_duration" | cut -d':' -f3)
            duration_seconds=$(awk -v h="$h" -v m="$m" -v s="$s" 'BEGIN {print (h*3600) + (m*60) + s}')
        else
            duration_seconds=$(echo "$extracted_duration" | awk '{print int($1)}')
        fi
    fi

    # 2. Run ffmpeg through our universal progress bar
    # Ensure -nostdin and standard logging are set
    local display_cmd=("${cmd[@]}")
    # Inject non-interactive flags if missing
    if [[ ! " ${display_cmd[*]} " =~ " -nostdin " ]]; then
        display_cmd=("-hide_banner" "-loglevel" "info" "-stats" "-nostdin" "${display_cmd[@]:1}")
        display_cmd=("ffmpeg" "${display_cmd[@]}")
    fi
    
    run_ffmpeg_with_progress "$duration_seconds" "${display_cmd[@]}"
    local ffmpeg_exit=$?
    
    # Check result
    if [[ -f "$output_file" && $ffmpeg_exit -eq 0 ]]; then
        # Print Stats Table (Restored Premium Unicode Format)
        local in_size=$(du -hL "$input_file" 2>/dev/null | cut -f1)
        local out_size=$(du -h "$output_file" 2>/dev/null | cut -f1)
        
        # Calculate Ratio (Mac: stat -L -f%z | Linux: stat -L -c%s)
        local in_bytes=$(stat -L -f%z "$input_file" 2>/dev/null || stat -L -c%s "$input_file" 2>/dev/null)
        local out_bytes=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null)
        
        local ratio="N/A"
        local percent_saved="0"
        if [[ -n "$in_bytes" && -n "$out_bytes" && "$in_bytes" -gt 0 ]]; then
             # Simple ratio using awk for floats
             ratio=$(awk "BEGIN {printf \"%.2fx\", $in_bytes/$out_bytes}" 2>/dev/null || echo "N/A")
             # Integer math for percent
             percent_saved=$(( 100 - (out_bytes * 100 / in_bytes) ))
        fi

        echo ""
        echo "✅ COMPLETE: $(basename "$output_file")"
        echo "══════════════════════════════════════════════════════════════════════════"
        echo ""
        
        # Use display overrides or fall back to basenames
        local f_in_label="${display_in:-$(basename "$input_file")}"
        local f_out_label="${display_out:-$(basename "$output_file")}"

        # Truncate labels for table (Max 16 chars)
        local label_in="File: $f_in_label"; [[ $(get_visual_width "$label_in") -gt 16 ]] && label_in="${label_in:0:13}..."
        local label_out="File: $f_out_label"; [[ $(get_visual_width "$label_out") -gt 16 ]] && label_out="${label_out:0:13}..."
        
        local duration_s=$(get_media_duration "$output_file")

        print_media_table 16 \
            "📥 INPUT|📤 OUTPUT|📊 DETAILS|📈 RATIO" \
            "$label_in|$label_out|Codec: $encoder|Saved: ${percent_saved}%" \
            "Size: $in_size|Size: $out_size|Time: ${duration_s}s|Ratio: $ratio"
        
        echo ""
        echo "📍 Output: $(realpath "$output_file")"

        # Optional post-render split (strict size mode; keyframe-bound)
        if [[ -n "$split_mb" && "$split_mb" =~ ^[0-9]+$ && "$split_mb" -gt 0 ]]; then
            echo ""
            split_video_by_size_strict "$output_file" "$split_mb"
        fi
    else
        # run_ffmpeg_with_progress automatically prints the ffmpeg error log if exit code is non-zero
        rm -f "$output_file"
        return 1
    fi
}

# ==============================================================================
# Video Download (web, YouTube, CloudflareStream, 1000+ sites via yt-dlp)
# ==============================================================================
sanitize_terminal_filename_stem() {
    local _input="$1"
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$_input" <<'PY'
import re
import sys

s = sys.argv[1] if len(sys.argv) > 1 else ""
s = (
    s.replace("’", "'")
     .replace("‘", "'")
     .replace("`", "'")
     .replace("´", "'")
)
# Keep Unicode word characters (Persian, Arabic, etc), spaces, dots, underscores, hyphens.
# Python 3 \w matches Unicode word characters by default.
s = re.sub(r'[^\w\s._-]', '_', s)
s = re.sub(r'\s+', '_', s) # Replace spaces with underscores for terminal safety
s = re.sub(r"_+", "_", s).strip("._-")
print(s or "video")
PY
    else
        # Minimal fallback when python3 is unavailable.
        printf "%s" "$_input" | tr -cs 'A-Za-z0-9._-' '_' | sed -E 's/^[_\.-]+|[_\.-]+$//g; s/_+/_/g'
    fi
}

stem_compare_key() {
    local _input="$1"
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$_input" <<'PY'
import re
import sys
import unicodedata

s = sys.argv[1] if len(sys.argv) > 1 else ""
s = (
    s.replace("’", "'")
     .replace("‘", "'")
     .replace("`", "'")
     .replace("´", "'")
)
s = unicodedata.normalize("NFKD", s)
s = s.encode("ascii", "ignore").decode("ascii")
s = s.lower()
print(re.sub(r"[^a-z0-9]+", "", s))
PY
    else
        printf "%s" "$_input" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9'
    fi
}

find_video_thumbnail_file() {
    local _video_file="$1"
    local _base="${_video_file%.*}"
    local _thumb=""
    for _cand in "${_base}.jpg" "${_base}.jpeg" "${_base}.png" "${_base}.webp"; do
        if [[ -f "$_cand" ]]; then
            _thumb="$_cand"
            break
        fi
    done
    [[ -n "$_thumb" ]] && printf "%s" "$_thumb"
}

find_existing_downloaded_video() {
    local _out_dir="$1"
    local _raw_title="$2"
    local _resolution="$3"

    [[ -n "$_out_dir" && -n "$_raw_title" && -n "$_resolution" ]] || return 1

    local _safe_stem
    _safe_stem="$(sanitize_terminal_filename_stem "$_raw_title")"
    [[ -n "$_safe_stem" ]] || return 1
    local _target_key
    _target_key="$(stem_compare_key "$_raw_title")"
    [[ -n "$_target_key" ]] || _target_key="$(stem_compare_key "$_safe_stem")"

    is_reusable_download_video() {
        local _video_path="$1"
        [[ -f "$_video_path" ]] || return 1

        local _lower_name
        _lower_name="$(basename "$_video_path" | tr '[:upper:]' '[:lower:]')"

        # Never reuse rendered subtitle outputs as download sources.
        if [[ "$_lower_name" == *_subbed*.mp4 ]]; then
            return 1
        fi

        local _ffprobe_cmd="${FFPROBE_EXEC:-ffprobe}"
        local _frame_count _duration
        _frame_count="$("$_ffprobe_cmd" -v error -select_streams v:0 -show_entries stream=nb_frames -of default=noprint_wrappers=1:nokey=1 "$_video_path" 2>/dev/null | tr -d '\r')"
        _duration="$("$_ffprobe_cmd" -v error -select_streams v:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 "$_video_path" 2>/dev/null | tr -d '\r')"

        if [[ "$_frame_count" =~ ^[0-9]+$ && "$_frame_count" -gt 1 ]]; then
            return 0
        fi

        if [[ -n "$_duration" ]] && awk -v d="$_duration" 'BEGIN { exit (d > 1.0) ? 0 : 1 }'; then
            return 0
        fi

        return 1
    }

    local _exact="${_out_dir}/${_safe_stem}_${_resolution}p.mp4"
    if [[ -f "$_exact" ]] && is_reusable_download_video "$_exact"; then
        printf "%s" "$_exact"
        return 0
    fi

    local _candidate
    for _candidate in "${_out_dir}"/${_safe_stem}_${_resolution}p*.mp4; do
        [[ -f "$_candidate" ]] || continue
        is_reusable_download_video "$_candidate" || continue
        printf "%s" "$_candidate"
        return 0
    done

    # Fallback: robust semantic match among all files with same resolution suffix.
    # Handles legacy naming drift like: Bibi's -> Bibi_s / Bibis.
    if [[ -n "$_target_key" ]]; then
        local _cand_name _cand_stem _cand_base _cand_key
        for _candidate in "${_out_dir}"/*_${_resolution}p*.mp4; do
            [[ -f "$_candidate" ]] || continue
            is_reusable_download_video "$_candidate" || continue
            _cand_name="$(basename "$_candidate")"
            _cand_stem="${_cand_name%.*}"
            _cand_base="$(printf '%s' "$_cand_stem" | sed -E "s/_${_resolution}p(_[0-9]+)?$//")"
            _cand_key="$(stem_compare_key "$_cand_base")"
            if [[ -n "$_cand_key" && "$_cand_key" == "$_target_key" ]]; then
                printf "%s" "$_candidate"
                return 0
            fi
        done
    fi

    return 1
}

extract_video_thumbnail_fallback() {
    local _video_file="$1"
    local _thumb_out="$2"
    local _ffmpeg_cmd="${FFMPEG_EXEC:-ffmpeg}"
    "$_ffmpeg_cmd" -hide_banner -loglevel error -y \
        -ss 1 -i "$_video_file" -frames:v 1 -q:v 2 "$_thumb_out" >/dev/null 2>&1
}

embed_video_cover_art() {
    local _video_file="$1"
    local _thumb_file="$2"

    [[ -f "$_video_file" && -f "$_thumb_file" ]] || return 0

    local _ext="${_video_file##*.}"
    _ext="$(printf '%s' "$_ext" | tr '[:upper:]' '[:lower:]')"
    case "$_ext" in
        mp4|m4v|mov) ;;
        *) return 0 ;;
    esac

    local _ffmpeg_cmd="${FFMPEG_EXEC:-ffmpeg}"
    local _tmp_out="${_video_file%.*}.cover_tmp.${_ext}"

    if "$_ffmpeg_cmd" -hide_banner -loglevel error -y \
        -i "$_video_file" -i "$_thumb_file" \
        -map 0 -map 1 \
        -c copy -c:v:1 mjpeg \
        -disposition:v:1 attached_pic \
        -metadata:s:v:1 title="Cover" \
        -metadata:s:v:1 comment="Cover (front)" \
        "$_tmp_out"; then
        mv -f "$_tmp_out" "$_video_file"
        log_info "🖼️  Embedded cover art: $(basename "$_video_file")" >&2
    else
        rm -f "$_tmp_out"
        log_info "⚠️  Could not embed cover art into: $(basename "$_video_file")" >&2
    fi
}

ensure_mac_playable_video() {
    local _video_file="$1"
    [[ -f "$_video_file" ]] || return 1

    local _vcodec _acodec
    _vcodec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$_video_file" 2>/dev/null | head -n1)
    _acodec=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$_video_file" 2>/dev/null | head -n1)

    [[ -z "$_vcodec" ]] && return 1

    # QuickTime/macOS compatibility: vp9/av1 in mp4 is unreliable in many setups.
    # Keep native file when already compatible, otherwise normalize to H.264/AAC.
    local _video_ok=false
    case "$_vcodec" in
        h264|hevc|h265|mpeg4|prores) _video_ok=true ;;
    esac

    local _audio_ok=false
    if [[ -z "$_acodec" ]]; then
        _audio_ok=true  # no audio stream
    else
        case "$_acodec" in
            aac|alac|mp3|ac3|eac3) _audio_ok=true ;;
        esac
    fi

    if $_video_ok && $_audio_ok; then
        return 0
    fi

    local _tmp_out="${_video_file%.*}.mac_compat_tmp.mp4"
    log_info "🛠️  Normalizing for macOS playback (v=${_vcodec:-?}, a=${_acodec:-none})..." >&2

    if ffmpeg -hide_banner -loglevel error -y \
        -i "$_video_file" \
        -map "0:v:0" -map "0:a?" \
        -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
        -c:a aac -b:a 160k \
        -movflags +faststart \
        "$_tmp_out"; then
        mv -f "$_tmp_out" "$_video_file"
        log_info "✅ macOS-compatible video generated: $(basename "$_video_file")" >&2
        return 0
    fi

    rm -f "$_tmp_out"
    log_info "⚠️  Could not normalize video for macOS playback." >&2
    return 1
}

# Internal state for subtitle prefetch (Bash 3.2 compatible)
YT_PREFETCH_LANGS=()
YT_PREFETCH_FILES=()
YT_PREFETCH_KINDS=()
YT_PREFETCH_SOURCE_LANG=""
YT_PREFETCH_SOURCE_FILE=""

_reset_yt_prefetch_state() {
    YT_PREFETCH_LANGS=()
    YT_PREFETCH_FILES=()
    YT_PREFETCH_KINDS=()
    YT_PREFETCH_SOURCE_LANG=""
    YT_PREFETCH_SOURCE_FILE=""
}

_pick_best_sub_file_for_lang() {
    local _base="$1"
    local _lang="$2"
    local _mode="${3:-any}"   # any | manual

    local _had_nullglob=0
    shopt -q nullglob && _had_nullglob=1
    shopt -s nullglob

    local -a _cands=()
    local _f _seen _e
    for _f in \
        "${_base}.${_lang}.srt" \
        "${_base}.${_lang}"*.srt \
        "${_base}"*".${_lang}.srt" \
        "${_base}"*".${_lang}"*.srt; do
        [[ -f "$_f" ]] || continue
        _seen=false
        for _e in "${_cands[@]}"; do
            [[ "$_e" == "$_f" ]] && _seen=true && break
        done
        [[ "$_seen" == false ]] && _cands+=("$_f")
    done

    [[ $_had_nullglob -eq 0 ]] && shopt -u nullglob

    local _manual=""
    for _f in "${_cands[@]}"; do
        if [[ "$_f" != *"-orig.srt" && "$_f" != *".orig.srt" ]]; then
            _manual="$_f"
            break
        fi
    done

    if [[ -n "$_manual" ]]; then
        printf "%s" "$_manual"
        return 0
    fi

    [[ "$_mode" == "manual" ]] && return 1

    if [[ ${#_cands[@]} -gt 0 ]]; then
        printf "%s" "${_cands[0]}"
        return 0
    fi

    return 1
}

prefetch_youtube_subtitles_with_fallback() {
    local _url="$1"
    local _base="$2"
    local _source_pref="$3"
    shift 3

    _reset_yt_prefetch_state

    local -a _langs=()
    local _tok _norm _seen _e
    for _tok in "$@"; do
        _norm="$(printf '%s' "$_tok" | tr '[:upper:]' '[:lower:]')"
        [[ -z "$_norm" || "$_norm" == "auto" ]] && continue
        [[ "$_norm" =~ ^[a-z]{2,3}$ ]] || continue
        _seen=false
        for _e in "${_langs[@]}"; do
            [[ "$_e" == "$_norm" ]] && _seen=true && break
        done
        [[ "$_seen" == false ]] && _langs+=("$_norm")
    done

    [[ ${#_langs[@]} -eq 0 ]] && return 0

    local _langs_csv
    _langs_csv="$(IFS=,; echo "${_langs[*]}")"

    log_info "📥 Trying YouTube manual subtitles for: ${_langs_csv}" >&2
    yt-dlp \
        "${COOKIE_ARGS[@]}" \
        "${IMPERSONATE_ARGS[@]}" \
        --remote-components "ejs:github" \
        --quiet \
        --skip-download \
        --write-subs \
        --no-write-auto-subs \
        --sub-langs "${_langs_csv}" \
        --convert-subs srt \
        --sleep-subtitles 2 \
        -o "${_base}.%(ext)s" \
        "$_url" >/dev/null 2>&1 || true

    local -a _missing=()
    local _lang _best
    for _lang in "${_langs[@]}"; do
        _best="$(_pick_best_sub_file_for_lang "$_base" "$_lang" "manual")"
        if [[ -n "$_best" ]]; then
            YT_PREFETCH_LANGS+=("$_lang")
            YT_PREFETCH_FILES+=("$_best")
            YT_PREFETCH_KINDS+=("manual")
        else
            _missing+=("$_lang")
        fi
    done

    if [[ ${#_missing[@]} -gt 0 ]]; then
        local _missing_csv
        _missing_csv="$(IFS=,; echo "${_missing[*]}")"
        log_info "📥 Manual missing; trying auto subtitles for: ${_missing_csv}" >&2
        yt-dlp \
            "${COOKIE_ARGS[@]}" \
            "${IMPERSONATE_ARGS[@]}" \
            --remote-components "ejs:github" \
            --quiet \
            --skip-download \
            --write-auto-subs \
            --no-write-subs \
            --sub-langs "${_missing_csv}" \
            --convert-subs srt \
            --sleep-subtitles 2 \
            -o "${_base}.%(ext)s" \
            "$_url" >/dev/null 2>&1 || true

        for _lang in "${_missing[@]}"; do
            _best="$(_pick_best_sub_file_for_lang "$_base" "$_lang" "any")"
            if [[ -n "$_best" ]]; then
                YT_PREFETCH_LANGS+=("$_lang")
                YT_PREFETCH_FILES+=("$_best")
                YT_PREFETCH_KINDS+=("auto")
            fi
        done
    fi

    # Canonicalize selected tracks to <base>_<lang>.srt for deterministic reuse.
    local -a _canon_langs=()
    local -a _canon_files=()
    local -a _canon_kinds=()
    local _i _raw _canon _kind
    for (( _i=0; _i<${#YT_PREFETCH_FILES[@]}; _i++ )); do
        _lang="${YT_PREFETCH_LANGS[_i]}"
        _raw="${YT_PREFETCH_FILES[_i]}"
        _kind="${YT_PREFETCH_KINDS[_i]}"
        _canon="${_base}_${_lang}.srt"
        if [[ "$_raw" != "$_canon" ]]; then
            cp -f "$_raw" "$_canon" >/dev/null 2>&1 || continue
        else
            [[ -f "$_canon" ]] || continue
        fi
        _canon_langs+=("$_lang")
        _canon_files+=("$_canon")
        _canon_kinds+=("$_kind")
    done
    YT_PREFETCH_LANGS=("${_canon_langs[@]}")
    YT_PREFETCH_FILES=("${_canon_files[@]}")
    YT_PREFETCH_KINDS=("${_canon_kinds[@]}")

    local _src_norm
    _src_norm="$(printf '%s' "$_source_pref" | tr '[:upper:]' '[:lower:]')"

    if [[ "$_src_norm" != "auto" && "$_src_norm" =~ ^[a-z]{2,3}$ ]]; then
        for (( _i=0; _i<${#YT_PREFETCH_LANGS[@]}; _i++ )); do
            if [[ "${YT_PREFETCH_LANGS[_i]}" == "$_src_norm" ]]; then
                YT_PREFETCH_SOURCE_LANG="$_src_norm"
                YT_PREFETCH_SOURCE_FILE="${YT_PREFETCH_FILES[_i]}"
                break
            fi
        done
    fi

    if [[ -z "$YT_PREFETCH_SOURCE_FILE" && ${#YT_PREFETCH_FILES[@]} -gt 0 ]]; then
        YT_PREFETCH_SOURCE_LANG="${YT_PREFETCH_LANGS[0]}"
        YT_PREFETCH_SOURCE_FILE="${YT_PREFETCH_FILES[0]}"
    fi

    # If source is auto, expose selected source as <base>_auto.srt so subtitle
    # workflow reuses it and skips Whisper unless no downloaded subtitles exist.
    if [[ "$_src_norm" == "auto" && -n "$YT_PREFETCH_SOURCE_FILE" && -f "$YT_PREFETCH_SOURCE_FILE" ]]; then
        local _auto_alias="${_base}_auto.srt"
        cp -f "$YT_PREFETCH_SOURCE_FILE" "$_auto_alias" >/dev/null 2>&1 || true
        if [[ -f "$_auto_alias" ]]; then
            YT_PREFETCH_SOURCE_LANG="auto"
            YT_PREFETCH_SOURCE_FILE="$_auto_alias"
        fi
    fi

    for (( _i=0; _i<${#YT_PREFETCH_FILES[@]}; _i++ )); do
        log_success "📄 ${YT_PREFETCH_KINDS[_i]} subtitle: $(basename "${YT_PREFETCH_FILES[_i]}")" >&2
    done
}

video_download() {
    local URL=""
    local LANG="fa"
    local LANG_SRC="auto"
    local DO_SUBTITLE=false
    local YT_SUBS=false           # download YouTube's own subtitles instead of Whisper
    local DO_RENDER=false         # burn subtitles into video
    local ONLY_SUBS=false
    local SUB_FORMAT="srt"        # srt | ass | all
    local AUTO_YES=false
    local GET_LINK=false
    local YT_TRANSLATE=false       # translate downloaded YT subs via amir subtitle (skips Whisper)
    local PREFETCH_YT_SUBS=false   # internal: prefetch yt subtitles before subtitle pipeline
    local BROWSER="${AMIR_DEFAULT_BROWSER:-chrome}"
    local COOKIES_FILE=""
    local BROWSER_EXPLICIT=false
    local COOKIES_EXPLICIT=false
    local DL_RESOLUTION=$(get_config "video" "resolution" "480")
    local DL_QUALITY=$(get_config "video" "quality" "40")
    local DL_RESOLUTION_EXPLICIT=false
    local DL_QUALITY_EXPLICIT=false
    local KEEP_THUMB_FILE=true
    local LIST_FORMATS=false
    local EXTREME_DL=false
    local -a _LANG_POSITIONALS=()
    local -a SUB_LANG_TOKENS=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --subtitle|-s)   DO_SUBTITLE=true; DO_RENDER=true; shift ;;  # whisper+burn
            --yt-subs)       YT_SUBS=true; shift ;;              # youtube built-in subs
            --translate)     YT_TRANSLATE=true; YT_SUBS=true; shift ;; # download YT subs + translate
            --prefetch-yt-subs) PREFETCH_YT_SUBS=true; shift ;;
            --render|-r)     DO_RENDER=true; shift ;;
            --sub-only|--no-render) DO_RENDER=false; shift ;;
            --only-subs)     ONLY_SUBS=true; shift ;;
            --sub-format)    SUB_FORMAT="$2"; shift 2 ;;
            --target|-t)
                # accept: -t <target>  OR  -t <src> <target>
                if [[ -n "${3:-}" && "${3:-}" != -* && ! "${3:-}" =~ ^https?:// && ${#3} -le 10 ]]; then
                    LANG_SRC="$2"; LANG="$3"; shift 3
                else
                    LANG="$2"; shift 2
                fi ;;
            --browser|-b)    BROWSER="$2"; BROWSER_EXPLICIT=true; shift 2 ;;
            --cookies)       COOKIES_FILE="$2"; COOKIES_EXPLICIT=true; shift 2 ;;
            --keep-thumb)    KEEP_THUMB_FILE=true; shift ;;
            -y|--yes)        AUTO_YES=true; shift ;;
            --get-link|-l)   GET_LINK=true; shift ;;
            --formats|-F|--list-formats|--list-format|--lists-format) LIST_FORMATS=true; shift ;;
            --extreme)       EXTREME_DL=true; shift ;;
            --resolution|-R)
                DL_RESOLUTION="$2"
                DL_RESOLUTION_EXPLICIT=true
                shift 2
                # Optional quality value immediately after resolution: --resolution 360 60
                if [[ -n "${1:-}" && "${1:-}" =~ ^[0-9]+$ && ${1} -le 100 ]]; then
                    DL_QUALITY="$1"
                    DL_QUALITY_EXPLICIT=true
                    shift
                fi
                ;;
            --quality)
                DL_QUALITY="$2"
                DL_QUALITY_EXPLICIT=true
                shift 2
                ;;
            -*)
                log_error "Unknown option: $1" >&2
                echo "Usage: amir video download <url> [options]" >&2
                return 1
                ;;
            *)
                # First bare argument is URL. Extra bare args (e.g. --subtitle en fa)
                # are treated as language hints, not as URL overwrite.
                if [[ -z "$URL" ]]; then
                    URL="$1"
                elif [[ "$1" =~ ^[0-9]+p?$ && "$DO_SUBTITLE" == false && "$YT_SUBS" == false && "$YT_TRANSLATE" == false && "$DL_RESOLUTION_EXPLICIT" == false ]]; then
                    # Convenience: allow `amir video download <url> 360` or `... 360p`.
                    DL_RESOLUTION="$1"
                    DL_RESOLUTION_EXPLICIT=true
                elif [[ "$1" != -* && ! "$1" =~ ^https?:// && ${#1} -le 10 && ( "$DO_SUBTITLE" == true || "$YT_SUBS" == true || "$YT_TRANSLATE" == true || "$PREFETCH_YT_SUBS" == true ) ]]; then
                    _LANG_POSITIONALS+=("$1")
                fi
                shift
                ;;
        esac
    done

    # Support compact syntax with optional inline sizes:
    #   --subtitle fa
    #   --subtitle en fa
    #   --subtitle en 18 fa 20
    if [[ ${#_LANG_POSITIONALS[@]} -gt 0 ]]; then
        SUB_LANG_TOKENS=("${_LANG_POSITIONALS[@]}")

        local -a _lang_only=()
        local _tok
        for _tok in "${_LANG_POSITIONALS[@]}"; do
            if [[ "$_tok" =~ ^[A-Za-z]{2,3}$ ]]; then
                _lang_only+=("$_tok")
            fi
        done

        if [[ ${#_lang_only[@]} -eq 1 ]]; then
            # One language means target only; keep default source.
            LANG="${_lang_only[0]}"
        elif [[ ${#_lang_only[@]} -ge 2 ]]; then
            # Two+ languages: first is source, last is primary target.
            LANG_SRC="${_lang_only[0]}"
            LANG="${_lang_only[${#_lang_only[@]}-1]}"
        fi
    fi

    # Strip shell-escaped backslashes (e.g. \? \= that zsh adds when URL is unquoted)
    # Handles both: unquoted URLs where shell strips escapes, and quoted URLs with literal backslashes
    URL="${URL//\\/}"  # Remove all backslashes, treating them as escape characters
    
    # Additional cleanup: ensure URL is a valid https?:// format
    if [[ ! "$URL" =~ ^https?:// ]]; then
        log_error "Invalid URL format: '$URL'. Must start with http:// or https://" >&2
        return 1
    fi

    # Normalize resolution forms like `180p` -> `180` and validate numeric value.
    if [[ "$DL_RESOLUTION" =~ ^([0-9]+)[pP]$ ]]; then
        DL_RESOLUTION="${BASH_REMATCH[1]}"
    fi
    if [[ ! "$DL_RESOLUTION" =~ ^[0-9]+$ || "$DL_RESOLUTION" -le 0 ]]; then
        log_error "Invalid resolution: '$DL_RESOLUTION' (use a positive number like 360 or 480)." >&2
        return 1
    fi

    # Common shell mistake: passing a variable name literal instead of its value.
    # Example: amir video download URL   (literal token)
    # We auto-resolve from exported env var when available.
    if [[ "$URL" =~ ^[A-Za-z_][A-Za-z0-9_]*$ && ! "$URL" =~ ^https?:// ]]; then
        local _url_var_name="$URL"
        local _url_from_env=""
        _url_from_env="$(printenv "$_url_var_name" 2>/dev/null)"
        if [[ "$_url_from_env" =~ ^https?:// ]]; then
            URL="$_url_from_env"
            log_info "ℹ️  Resolved URL from env var: ${_url_var_name}" >&2
        else
            log_error "URL looks like a variable name literal: '$URL'" >&2
            echo "💡 Correct usage: amir video download \"\$$URL\"" >&2
            echo "💡 If you want literal-name auto-resolution, export first: export $URL='https://...'; then run: amir video download $URL" >&2
            return 1
        fi
    fi

    # When --translate is set, source and target must differ
    if $YT_TRANSLATE && [[ "$LANG_SRC" == "auto" ]]; then
        # YT built-in subtitle selection needs an explicit track code.
        LANG_SRC="en"
    fi

    if $YT_TRANSLATE && [[ "$LANG" == "$LANG_SRC" ]]; then
        log_error "Source and target language are the same (${LANG})." >&2
        echo "" >&2
        echo "  Translate TO a language: --translate -t fa" >&2
        echo "  Specify src AND target:  --translate -t en fa" >&2
        echo "  (default source: auto, default target: fa; --translate fallback source: en)" >&2
        return 1
    fi

    if [[ -z "$URL" ]]; then
        log_error "URL is required." >&2
        echo "" >&2
        echo "Usage: amir video download <url> [options]" >&2
        echo "" >&2
        echo "Options:" >&2
        echo "  --subtitle, -s        Subtitle pipeline: YouTube manual -> YouTube auto -> Whisper large-v3 (e.g. --subtitle fa | --subtitle en fa | --subtitle en 18 fa 20)" >&2
        echo "  --yt-subs             Download YouTube subtitles only (manual first, auto fallback)" >&2
        echo "  --target, -t [src] <target>  Subtitle language; optionally specify source then target (e.g. -t en fa)" >&2
        echo "  --render, -r          Burn subtitle into video (use with --yt-subs)" >&2
        echo "  --sub-only            Generate subtitle files only, no burning (use with --subtitle)" >&2
        echo "  --only-subs           Keep subtitle files; prompt to delete raw video" >&2
        echo "  --sub-format <fmt>    Subtitle format: srt | ass | all (default: srt)" >&2
        echo "  -y, --yes             Auto-confirm deletion prompt (use with --only-subs)" >&2
        echo "  -l, --get-link        Print direct stream URL(s) — for use in a download manager" >&2
        echo "  --browser <name>      Browser for cookies (default: chrome)" >&2
        echo "  --cookies <file>      Path to Netscape cookies.txt file" >&2
        echo "  --keep-thumb          Keep the downloaded thumbnail sidecar file" >&2
        echo "  --formats, -F, --list-formats, --list-format  Show available resolutions and sizes before downloading" >&2
        echo "  --lists-format        Compatibility alias (same as --list-formats)" >&2
        echo "  --resolution, -R <h> [q]  Download max height (e.g. 240/360/480/720/1080); optional quality after it" >&2
        echo "  --quality <q>         Download quality factor (1-100). Same as optional [q] after --resolution" >&2
        echo "  --extreme             Fast defaults for subtitle pipeline: 360p + q30" >&2
        return 1
    fi

    if ! command -v yt-dlp &>/dev/null; then
        log_error "yt-dlp is not installed. Install with: brew install yt-dlp" >&2
        return 1
    fi

    # Build cookie arguments
    # YouTube can return HTTP 403 when browser cookies are auto-injected.
    # Keep explicit user choice, but avoid implicit browser cookies for YouTube links.
    local -a COOKIE_ARGS=()
    local IS_YOUTUBE_URL=false
    if [[ "$URL" =~ ^https?://([^/]+\.)?(youtube\.com|youtu\.be|youtube-nocookie\.com)(/|$) ]]; then
        IS_YOUTUBE_URL=true
    fi

    if [[ -n "$COOKIES_FILE" ]]; then
        COOKIE_ARGS=(--cookies "$COOKIES_FILE")
    elif [[ -f "cookies.txt" ]]; then
        COOKIE_ARGS=(--cookies "cookies.txt")
    elif [[ -f "$HOME/su6i-yar/cookies.txt" ]]; then
        COOKIE_ARGS=(--cookies "$HOME/su6i-yar/cookies.txt")
    elif $BROWSER_EXPLICIT && [[ -n "$BROWSER" && "$BROWSER" != "none" ]]; then
        COOKIE_ARGS=(--cookies-from-browser "$BROWSER")
    elif $IS_YOUTUBE_URL; then
        COOKIE_ARGS=()
    elif [[ -n "$BROWSER" && "$BROWSER" != "none" ]]; then
        COOKIE_ARGS=(--cookies-from-browser "$BROWSER")
    fi

    # Cloudflare / anti-bot compatibility:
    # Default to Chrome impersonation, but allow disabling/override via env.
    # Examples:
    #   AMIR_YTDLP_IMPERSONATE=none   -> disable
    #   AMIR_YTDLP_IMPERSONATE=safari -> custom target
    local -a IMPERSONATE_ARGS=()
    local IMPERSONATE_TARGET="${AMIR_YTDLP_IMPERSONATE:-chrome}"
    if [[ -n "$IMPERSONATE_TARGET" && "$IMPERSONATE_TARGET" != "none" ]]; then
        IMPERSONATE_ARGS=(--impersonate "$IMPERSONATE_TARGET" --extractor-args "generic:impersonate=$IMPERSONATE_TARGET")
    else
        # Keep generic extractor behavior available even when explicit impersonation is disabled.
        IMPERSONATE_ARGS=(--extractor-args "generic:impersonate")
    fi

    # ── Extreme download defaults ─────────────────────────────────────────
    if $EXTREME_DL; then
        # New default profile for fast turnaround + acceptable subtitle readability.
        if ! $DL_RESOLUTION_EXPLICIT; then
            DL_RESOLUTION="360"
        fi
        if ! $DL_QUALITY_EXPLICIT; then
            DL_QUALITY="30"
        fi
        log_info "⚡ Extreme mode defaults: ${DL_RESOLUTION}p, q${DL_QUALITY}" >&2
    fi

    # ── Substack / Zeteo Video Interception ───────────────────────────────
    # yt-dlp's Substack extractor defaults to downloading the audio podcast
    # and misses the hidden Mux video streams. We manually extract the Mux URL.
    local SUBSTACK_ORIG_URL=""
    if [[ "$URL" =~ ^https?://([^/]+\.)?(substack\.com|zeteo\.com)(/|$) ]]; then
        log_info "🔍 Inspecting Substack/Zeteo page for hidden native video streams..." >&2
        local _mux_id=""
        _mux_id=$(curl -sL "$URL" | python3 -c 'import re,json,sys; m=re.search(r"window._preloads\s*=\s*JSON\.parse\(\"(.*?)\"\)", sys.stdin.read()); print(json.loads(m.group(1).encode().decode("unicode_escape")).get("post",{}).get("videoUpload",{}).get("id","")) if m else ""' 2>/dev/null)
        if [[ -n "$_mux_id" ]]; then
            local _mux_url=""
            _mux_url=$(curl -sI "https://api.substack.com/api/v1/video/upload/${_mux_id}/src" | awk -F' ' '/^[Ll]ocation:/ {print $2}' | tr -d '\r' 2>/dev/null)
            if [[ -n "$_mux_url" && "$_mux_url" == http* ]]; then
                # The Substack API redirects to the hardcoded /high.mp4
                # We need the HLS playlist (.m3u8) so yt-dlp can see and select all resolutions!
                _mux_url="${_mux_url/\/high.mp4?/.m3u8?}"
                
                log_info "✅ Found hidden Mux video stream! Redirecting yt-dlp..." >&2
                SUBSTACK_ORIG_URL="$URL"
                URL="$_mux_url"
            fi
        fi
    fi

    # ── List-formats mode ──────────────────────────────────────────────────
    if $LIST_FORMATS; then
        log_info "📊 Fetching available formats for: $URL" >&2
        echo "" >&2
        local _fmt_json
        _fmt_json=$(mktemp "$OUT_DIR/.amir_formats.XXXXXX")
        if ! yt-dlp \
            "${COOKIE_ARGS[@]}" \
            "${IMPERSONATE_ARGS[@]}" \
            --no-playlist \
            -j \
            "$URL" > "$_fmt_json" 2>/dev/null; then
            rm -f "$_fmt_json"
            log_error "Could not fetch format list from source (URL blocked/invalid/cookie required)." >&2
            return 1
        fi

        if [[ ! -s "$_fmt_json" ]]; then
            rm -f "$_fmt_json"
            log_error "No format metadata returned by extractor." >&2
            return 1
        fi

        python3 - "$_fmt_json" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    print("❌ ERROR: Failed to parse source metadata.", file=sys.stderr)
    raise SystemExit(1)

title = data.get("title", "?")
fmts = data.get("formats", [])
print(f"  📹 {title}")
print()
print(f"  {'Res':<8} {'Codec':<8} {'VBR kbps':<12} {'Size (est.)':<14} {'Note'}")
print("  " + "-" * 60)

seen = {}
for f in fmts:
    h = f.get("height") or 0
    vb = f.get("vbr") or f.get("tbr") or 0
    fs = f.get("filesize") or f.get("filesize_approx") or 0
    vc = (f.get("vcodec") or "").split(".")[0]
    fid = f.get("format_id") or ""
    note = f.get("format_note", "") or ""
    if h < 144:
        continue
    if not vc or vc in ("none", ""):
        vc = "hls" if fid.startswith("hls-") else "unknown"
    cur = seen.get(h)
    if cur is None or vb > (cur[1] or 0):
        seen[h] = (vc, vb, fs, note)

dur = data.get("duration") or 0
for h in sorted(seen.keys(), reverse=True):
    vc, vb, fs, note = seen[h]
    if fs:
        size_s = f"{fs/1024/1024:.1f} MB"
    elif vb and dur:
        size_s = f"~{vb * 1000 * dur / 8 / 1024 / 1024:.0f} MB"
    else:
        size_s = "?"
    vbr_s = f"{int(vb)} kbps" if vb else "?"
    print(f"  {str(h)+'p':<8} {vc:<8} {vbr_s:<12} {size_s:<14} {note}")

print()
print("  💡 Tip: smaller kbps = smaller file. Run with --resolution <N> to download.")
PY
        local _fmt_exit=$?
        rm -f "$_fmt_json"
        return $_fmt_exit
    fi

    # ── Get-link mode ──────────────────────────────────────────────────────
    if $GET_LINK; then
        log_info "🔗 Fetching direct download URL(s) from: $URL" >&2
        log_info "   Auth via: ${COOKIES_FILE:-browser:$BROWSER}" >&2
        yt-dlp \
            "${COOKIE_ARGS[@]}" \
            "${IMPERSONATE_ARGS[@]}" \
            --remote-components "ejs:github" \
            --newline \
            -g \
            "$URL"
        return $?
    fi

    # Use absolute output path so --print returns absolute path regardless of cwd changes
    local OUT_DIR
    OUT_DIR="$(pwd)"
    local OUT_TEMPLATE="${OUT_DIR}/%(title)s.%(ext)s"

    local VIDEO_FILE
    local THUMB_FILE=""
    local THUMB_TMP=false
    local INFO_JSON_FILE=""
    local _VID_TITLE
    
    local _title_url="$URL"
    [[ -n "$SUBSTACK_ORIG_URL" ]] && _title_url="$SUBSTACK_ORIG_URL"
    
    _VID_TITLE=$(yt-dlp \
        "${COOKIE_ARGS[@]}" \
        "${IMPERSONATE_ARGS[@]}" \
        --no-playlist \
        --print "%(title)s" \
        --skip-download \
        "$_title_url" 2>/dev/null | head -n1 | tr -d '\r')

    if [[ -n "$_VID_TITLE" ]]; then
        local _existing_video
        _existing_video="$(find_existing_downloaded_video "$OUT_DIR" "$_VID_TITLE" "$DL_RESOLUTION")"
        if [[ -n "$_existing_video" && -f "$_existing_video" ]]; then
            VIDEO_FILE="$_existing_video"
            log_info "⏩ Reusing existing downloaded video: $(basename "$VIDEO_FILE")" >&2
        fi
        
        # Override the output template to use the pre-fetched title (sanitized for safe filenames)
        local _safe_vid_title="${_VID_TITLE//\//_}"
        OUT_TEMPLATE="${OUT_DIR}/${_safe_vid_title}.%(ext)s"
    fi

    if [[ -z "$VIDEO_FILE" ]]; then
        log_info "⬇️  Starting download..." >&2

        # Download:
        #   stdout  → temp file  (line1 = title via before_dl, line2 = final filepath via after_move)
        #   stderr  → filtered:  only [download] progress lines + ERROR/WARNING lines reach the terminal
        #             everything else ([youtube], [info], [generic], …) is hidden
        local _PATHFILE
        _PATHFILE=$(mktemp "$OUT_DIR/.amir_dl_path.XXXXXX")
        # Some titles contain unicode slash-like characters that break fragmented
        # merge/rename on certain yt-dlp + fs combinations. Force safe filenames.
        yt-dlp \
            "${COOKIE_ARGS[@]}" \
            "${IMPERSONATE_ARGS[@]}" \
            --remote-components "ejs:github" \
            --newline \
            --continue \
            --no-overwrites \
            --restrict-filenames \
            --windows-filenames \
            --keep-video \
            --write-info-json \
            --write-thumbnail \
            --convert-thumbnails jpg \
            -f "bestvideo[height<=${DL_RESOLUTION}][format_id!*=timeline]+bestaudio/best[height<=${DL_RESOLUTION}][format_id!*=timeline]/best[height<=${DL_RESOLUTION}][vcodec!=none]/best[vcodec!=none]/best" \
            --merge-output-format mp4 \
            --print "before_dl:${_VID_TITLE:-%(title)s}" \
            --print "after_move:filepath" \
            -o "$OUT_TEMPLATE" \
            "$URL" > "$_PATHFILE" \
            2> >(awk '/\[download\]|^ERROR|^WARNING:/{print; fflush()}' >&2)
        local _DL_EXIT=$?

        # Resilient YouTube fallback:
        # In some environments, auth/browser/session flags can trigger transient 403.
        # If user did not explicitly request cookies/browser, retry once with bare yt-dlp args.
        if [[ $_DL_EXIT -ne 0 && "$IS_YOUTUBE_URL" == true && "$BROWSER_EXPLICIT" == false && "$COOKIES_EXPLICIT" == false ]]; then
            log_info "↻ Retry without browser auth/session hints for YouTube..." >&2
            : > "$_PATHFILE"
            yt-dlp \
                --remote-components "ejs:github" \
                --newline \
                --continue \
                --no-overwrites \
                --restrict-filenames \
                --windows-filenames \
                --keep-video \
                --write-info-json \
                --write-thumbnail \
                --convert-thumbnails jpg \
                -f "bestvideo[height<=${DL_RESOLUTION}][format_id!*=timeline]+bestaudio/best[height<=${DL_RESOLUTION}][format_id!*=timeline]/best[height<=${DL_RESOLUTION}][vcodec!=none]/best[vcodec!=none]/best" \
                --merge-output-format mp4 \
                --print "before_dl:${_VID_TITLE:-%(title)s}" \
                --print "after_move:filepath" \
                -o "$OUT_TEMPLATE" \
                "$URL" > "$_PATHFILE" \
                2> >(awk '/\[download\]|^ERROR|^WARNING:/{print; fflush()}' >&2)
            _DL_EXIT=$?
        fi

        _VID_TITLE=$(sed -n '1p' "$_PATHFILE" 2>/dev/null | tr -d '\r')
        VIDEO_FILE=$(sed -n '2p' "$_PATHFILE" 2>/dev/null | tr -d '\r')
        rm -f "$_PATHFILE"

        if [[ $_DL_EXIT -ne 0 && -z "$VIDEO_FILE" ]]; then
            log_error "Download failed (yt-dlp exit $_DL_EXIT)." >&2
            return 1
        fi

        # Show title after the progress bar
        [[ -n "$_VID_TITLE" ]] && log_info "📹 $_VID_TITLE" >&2

        # Resolve relative path (some yt-dlp versions omit leading dir)
        if [[ -n "$VIDEO_FILE" && ! "$VIDEO_FILE" = /* ]]; then
            VIDEO_FILE="${OUT_DIR}/${VIDEO_FILE}"
        fi

        # Verify the file actually exists
        if [[ -z "$VIDEO_FILE" || ! -f "$VIDEO_FILE" ]]; then
            log_error "Download failed or output path could not be determined." >&2
            return 1
        fi
    fi

    THUMB_FILE="$(find_video_thumbnail_file "$VIDEO_FILE")"
    if [[ -f "${VIDEO_FILE}.info.json" ]]; then
        INFO_JSON_FILE="${VIDEO_FILE}.info.json"
    elif [[ -f "${VIDEO_FILE%.*}.info.json" ]]; then
        INFO_JSON_FILE="${VIDEO_FILE%.*}.info.json"
    fi

    # Enforce terminal-safe filename in-place before entering subtitle pipeline.
    local _dl_dir _dl_name _dl_stem _dl_ext _safe_stem _safe_path _n
    _dl_dir="$(dirname "$VIDEO_FILE")"
    _dl_name="$(basename "$VIDEO_FILE")"
    _dl_stem="${_dl_name%.*}"
    _dl_ext="${_dl_name##*.}"
    _safe_stem="$(sanitize_terminal_filename_stem "$_dl_stem")"
    if [[ -n "$_safe_stem" && "$_safe_stem" != "$_dl_stem" ]]; then
        _safe_path="${_dl_dir}/${_safe_stem}.${_dl_ext}"
        _n=2
        while [[ -e "$_safe_path" ]]; do
            _safe_path="${_dl_dir}/${_safe_stem}_${_n}.${_dl_ext}"
            ((_n++))
        done
        mv "$VIDEO_FILE" "$_safe_path"
        VIDEO_FILE="$_safe_path"
        log_info "🧹 Normalized filename: ${_dl_name} -> $(basename "$VIDEO_FILE")" >&2
        if [[ -n "$THUMB_FILE" && -f "$THUMB_FILE" ]]; then
            local _thumb_ext="${THUMB_FILE##*.}"
            local _safe_thumb="${VIDEO_FILE%.*}.${_thumb_ext}"
            mv "$THUMB_FILE" "$_safe_thumb"
            THUMB_FILE="$_safe_thumb"
        fi
        if [[ -n "$INFO_JSON_FILE" && -f "$INFO_JSON_FILE" ]]; then
            local _safe_info="${VIDEO_FILE}.info.json"
            mv "$INFO_JSON_FILE" "$_safe_info"
            INFO_JSON_FILE="$_safe_info"
        fi
    fi

    # ── Add/normalize resolution suffix from ACTUAL downloaded height ───────
    local ACTUAL_HEIGHT
    ACTUAL_HEIGHT=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null | head -n1)
    [[ "$ACTUAL_HEIGHT" =~ ^[0-9]+$ ]] || ACTUAL_HEIGHT="$DL_RESOLUTION"

    if [[ "$DL_RESOLUTION" =~ ^[0-9]+$ && "$ACTUAL_HEIGHT" =~ ^[0-9]+$ && "$ACTUAL_HEIGHT" -lt "$DL_RESOLUTION" ]]; then
        log_info "ℹ️  Requested ${DL_RESOLUTION}p but source provided ${ACTUAL_HEIGHT}p (best available)." >&2
    fi

    if [[ "$ACTUAL_HEIGHT" =~ ^[0-9]+$ ]]; then
        local _res_dir _res_name _res_stem _res_ext _res_base _res_new _res_n
        _res_dir="$(dirname "$VIDEO_FILE")"
        _res_name="$(basename "$VIDEO_FILE")"
        _res_stem="${_res_name%.*}"
        _res_ext="${_res_name##*.}"
        _res_base="$(printf '%s' "$_res_stem" | sed -E 's/_[0-9]+p(_[0-9]+)?$//')"
        _res_new="${_res_dir}/${_res_base}_${ACTUAL_HEIGHT}p.${_res_ext}"
        _res_n=2
        while [[ -e "$_res_new" && "$_res_new" != "$VIDEO_FILE" ]]; do
            _res_new="${_res_dir}/${_res_base}_${ACTUAL_HEIGHT}p_${_res_n}.${_res_ext}"
            ((_res_n++))
        done
        if [[ "$_res_new" != "$VIDEO_FILE" ]]; then
            mv "$VIDEO_FILE" "$_res_new"
            if [[ -n "$THUMB_FILE" && -f "$THUMB_FILE" ]]; then
                local _res_thumb="${_res_new%.*}.${THUMB_FILE##*.}"
                mv "$THUMB_FILE" "$_res_thumb"
                THUMB_FILE="$_res_thumb"
            fi
            if [[ -n "$INFO_JSON_FILE" && -f "$INFO_JSON_FILE" ]]; then
                mv "$INFO_JSON_FILE" "${_res_new}.info.json"
                INFO_JSON_FILE="${_res_new}.info.json"
            fi
            VIDEO_FILE="$_res_new"
        fi
    fi

    # Keep every artifact in the current working directory.
    # Do not create per-video folders; subtitle reuse and all follow-up checks
    # should operate against the directory the user explicitly chose.
    OUT_DIR="$PWD"

    if [[ -z "$THUMB_FILE" || ! -f "$THUMB_FILE" ]]; then
        THUMB_FILE="${VIDEO_FILE%.*}.cover.jpg"
        if extract_video_thumbnail_fallback "$VIDEO_FILE" "$THUMB_FILE"; then
            THUMB_TMP=true
            log_info "🖼️  Generated fallback cover from video frame" >&2
        else
            THUMB_FILE=""
        fi
    fi

    # Normalize codec/container profile for QuickTime/macOS if needed.
    ensure_mac_playable_video "$VIDEO_FILE"

    if [[ "$ACTUAL_HEIGHT" =~ ^[0-9]+$ ]]; then
        log_success "Saved → $(basename "$VIDEO_FILE") (${ACTUAL_HEIGHT}p actual)" >&2
    else
        log_success "Saved → $(basename "$VIDEO_FILE")" >&2
    fi

    local BASE_YT="${VIDEO_FILE%.*}"
    if [[ "$IS_YOUTUBE_URL" == true && ( "$DO_SUBTITLE" == true || "$YT_SUBS" == true || "$PREFETCH_YT_SUBS" == true ) ]]; then
        local -a _prefetch_tokens=("${SUB_LANG_TOKENS[@]}")
        _prefetch_tokens+=("$LANG_SRC" "$LANG")
        prefetch_youtube_subtitles_with_fallback "$URL" "$BASE_YT" "$LANG_SRC" "${_prefetch_tokens[@]}"
    else
        _reset_yt_prefetch_state
    fi

    # ── YouTube built-in subtitles ──────────────────────────────────────────
    if $YT_SUBS; then
        # Collect downloaded SRT files
        local -a YT_SUB_FILES=()
        if [[ ${#YT_PREFETCH_FILES[@]} -gt 0 ]]; then
            YT_SUB_FILES=("${YT_PREFETCH_FILES[@]}")
        else
            log_info "📥 Fetching subtitles  ${LANG_SRC} → ${LANG}..." >&2
            yt-dlp \
                "${COOKIE_ARGS[@]}" \
                "${IMPERSONATE_ARGS[@]}" \
                --remote-components "ejs:github" \
                --quiet \
                --skip-download \
                --write-subs \
                --write-auto-subs \
                --sub-langs "${LANG_SRC},${LANG_SRC}-orig,${LANG},${LANG}-orig" \
                --convert-subs srt \
                --sleep-subtitles 3 \
                -o "${BASE_YT}.%(ext)s" \
                "$URL" >&2

            for f in "${BASE_YT}"*.srt; do
                [[ -f "$f" ]] && YT_SUB_FILES+=("$f")
            done
        fi

        if [[ ${#YT_SUB_FILES[@]} -eq 0 ]]; then
            log_error "No subtitles found on YouTube for lang: $LANG" >&2
        else
            for f in "${YT_SUB_FILES[@]}"; do
                log_success "📄 $(basename "$f")" >&2
            done
        fi

        # ── --translate: use downloaded EN srt → amir subtitle (skips Whisper) ──
        if $YT_TRANSLATE && [[ ${#YT_SUB_FILES[@]} -gt 0 ]]; then
            # Pick human-curated source SRT (e.g. title.en.srt) over auto-generated (-orig)
            local SRC_SRT=""
            if [[ -n "$YT_PREFETCH_SOURCE_FILE" && -f "$YT_PREFETCH_SOURCE_FILE" ]]; then
                SRC_SRT="$YT_PREFETCH_SOURCE_FILE"
            fi
            if [[ -z "$SRC_SRT" ]]; then
                for f in "${YT_SUB_FILES[@]}"; do
                    [[ "$f" == *".${LANG_SRC}.srt" && "$f" != *"-orig.srt" ]] && SRC_SRT="$f" && break
                done
            fi
            # fallback: any -orig variant of source lang
            if [[ -z "$SRC_SRT" ]]; then
                for f in "${YT_SUB_FILES[@]}"; do
                    [[ "$f" == *"${LANG_SRC}"* ]] && SRC_SRT="$f" && break
                done
            fi
            # final fallback: first available SRT
            [[ -z "$SRC_SRT" ]] && SRC_SRT="${YT_SUB_FILES[0]}"

            # Rename to _<src>.srt so amir subtitle detects it and skips transcription
            local SRC_SRT_RENAMED="${BASE_YT}_${LANG_SRC}.srt"
            cp "$SRC_SRT" "$SRC_SRT_RENAMED"
            log_info "📋 Using $(basename "$SRC_SRT") → $(basename "$SRC_SRT_RENAMED") (Whisper skipped)" >&2

            local AMIR_BIN
            AMIR_BIN="$(dirname "$LIB_DIR")/amir"
            local -a SUB_FLAGS=("-s" "$LANG_SRC" "-t" "$LANG" "--max-lines" "1")
            [[ "$DL_RESOLUTION" =~ ^[0-9]+$ ]] && SUB_FLAGS+=("--resolution" "$DL_RESOLUTION")
            [[ "$DL_QUALITY" =~ ^[0-9]+$ ]] && SUB_FLAGS+=("--quality" "$DL_QUALITY")
            $ONLY_SUBS && SUB_FLAGS+=("--no-render")
            ! $DO_RENDER && SUB_FLAGS+=("--no-render")

            log_info "🌐 Translating ${LANG_SRC}→${LANG} via LLM (no Whisper)..." >&2
            "$AMIR_BIN" subtitle "$VIDEO_FILE" "${SUB_FLAGS[@]}"
            local _sub_exit=$?
            if [[ $_sub_exit -eq 0 && $DO_RENDER == true && $ONLY_SUBS == false ]]; then
                local _rendered_translate="${VIDEO_FILE%.*}_${LANG}.mp4"
                [[ -f "$_rendered_translate" ]] && VIDEO_FILE="$_rendered_translate"
            fi
            if [[ $_sub_exit -eq 0 && -n "$THUMB_FILE" && -f "$THUMB_FILE" && -f "$VIDEO_FILE" ]]; then
                embed_video_cover_art "$VIDEO_FILE" "$THUMB_FILE"
            fi
            if [[ -n "$THUMB_FILE" && -f "$THUMB_FILE" ]] && { $THUMB_TMP || ! $KEEP_THUMB_FILE; }; then
                rm -f "$THUMB_FILE"
            fi
            # Create a text file with the video URL before returning
            if [[ $_sub_exit -eq 0 && -f "$VIDEO_FILE" ]]; then
                local URL_FILE="${VIDEO_FILE%.*}_link.txt"
                echo "$URL" > "$URL_FILE"
                log_info "📝 URL saved: $(basename "$URL_FILE")" >&2
            fi
            return $_sub_exit
        fi

        # ── --render without --translate: burn existing LANG or EN srt directly ──
        if $DO_RENDER && [[ ${#YT_SUB_FILES[@]} -gt 0 ]]; then
            # Prefer target-lang SRT, fallback to first available
            local SRT_TO_BURN=""
            for f in "${YT_SUB_FILES[@]}"; do
                [[ "$f" == *"${LANG}"* ]] && SRT_TO_BURN="$f" && break
            done
            [[ -z "$SRT_TO_BURN" && ${#YT_SUB_FILES[@]} -gt 0 ]] && SRT_TO_BURN="${YT_SUB_FILES[0]}"

            log_info "🎬 Burning subtitle: $(basename "$SRT_TO_BURN")" >&2
            local AMIR_BIN
            AMIR_BIN="$(dirname "$LIB_DIR")/amir"
            "$AMIR_BIN" video cut "$VIDEO_FILE" \
                --subtitles "$SRT_TO_BURN" \
                --output "${VIDEO_FILE%.*}_subbed.mp4" \
                --render >&2
            local _rendered_ytsubs="${VIDEO_FILE%.*}_subbed.mp4"
            [[ -f "$_rendered_ytsubs" ]] && VIDEO_FILE="$_rendered_ytsubs"
        fi

        # --only-subs: prompt to delete raw video
        if $ONLY_SUBS; then
            local DELETE_VIDEO=false
            if $AUTO_YES; then
                DELETE_VIDEO=true
            else
                printf "\n❓ Delete raw video file '%s'? [y/N] " "$(basename "$VIDEO_FILE")" >&2
                read -r REPLY </dev/tty
                [[ "$REPLY" =~ ^[Yy]$ ]] && DELETE_VIDEO=true
            fi
            if $DELETE_VIDEO; then
                rm -f "$VIDEO_FILE"
                log_info "🗑️  Deleted: $VIDEO_FILE" >&2
            else
                # Create a text file with the video URL if video was kept
                local URL_FILE="${VIDEO_FILE%.*}_link.txt"
                echo "$URL" > "$URL_FILE"
                log_info "📝 URL saved: $(basename "$URL_FILE")" >&2
            fi
            if [[ -n "$THUMB_FILE" && -f "$THUMB_FILE" ]] && { $THUMB_TMP || ! $KEEP_THUMB_FILE; }; then
                rm -f "$THUMB_FILE"
            fi

            return 0
        fi

        if [[ -n "$THUMB_FILE" && -f "$THUMB_FILE" ]]; then
            embed_video_cover_art "$VIDEO_FILE" "$THUMB_FILE"
            if $THUMB_TMP || ! $KEEP_THUMB_FILE; then
                rm -f "$THUMB_FILE"
            fi
        fi


        log_success "✅ Final file: $VIDEO_FILE" >&2
        echo "$VIDEO_FILE"
        return 0
    fi

    # ── Subtitle generation ─────────────────────────────────────────────────
    if $DO_SUBTITLE; then
        local AMIR_BIN
        AMIR_BIN="$(dirname "$LIB_DIR")/amir"
        if [[ "$IS_YOUTUBE_URL" == true && ${#YT_PREFETCH_FILES[@]} -eq 0 ]]; then
            log_info "ℹ️  No YouTube subtitle track matched requested languages; falling back to Whisper large-v3." >&2
        fi
        local -a SUB_FLAGS=("-s" "$LANG_SRC" "--max-lines" "1")
        if [[ ${#SUB_LANG_TOKENS[@]} -gt 0 ]]; then
            SUB_FLAGS+=("-t" "${SUB_LANG_TOKENS[@]}")
        else
            SUB_FLAGS+=("-t" "$LANG")
        fi
        SUB_FLAGS+=("--whisper-model" "large-v3")
        [[ "$DL_RESOLUTION" =~ ^[0-9]+$ ]] && SUB_FLAGS+=("--resolution" "$DL_RESOLUTION")
        [[ "$DL_QUALITY" =~ ^[0-9]+$ ]] && SUB_FLAGS+=("--quality" "$DL_QUALITY")
        # Never burn when --only-subs is set (no point burning a video we're about to delete)
        ($DO_RENDER && ! $ONLY_SUBS) || SUB_FLAGS+=("--no-render")

        log_info "🎙️  Generating subtitles (lang: $LANG, render: $DO_RENDER)..." >&2
        "$AMIR_BIN" subtitle "$VIDEO_FILE" "${SUB_FLAGS[@]}" >&2

        local BASE="${VIDEO_FILE%.*}"

        if $ONLY_SUBS; then
            # Collect generated subtitle files filtered by requested format
            local -a SUB_FILES=()
            case "$SUB_FORMAT" in
                srt)
                    for f in "${BASE}"*_${LANG}.srt "${BASE}"*.srt; do
                        [[ -f "$f" ]] && SUB_FILES+=("$f")
                    done ;;
                ass)
                    for f in "${BASE}"*_${LANG}.ass "${BASE}"*.ass; do
                        [[ -f "$f" ]] && SUB_FILES+=("$f")
                    done ;;
                all|*)
                    for f in "${BASE}"*.srt "${BASE}"*.ass; do
                        [[ -f "$f" ]] && SUB_FILES+=("$f")
                    done ;;
            esac

            if [[ ${#SUB_FILES[@]} -eq 0 ]]; then
                log_error "No subtitle files found after generation." >&2
            else
                log_success "Subtitle files (format: $SUB_FORMAT):" >&2
                for f in "${SUB_FILES[@]}"; do
                    log_info "   📄 $f" >&2
                    echo "$f"
                done
            fi

            # Ask whether to delete the raw video
            local DELETE_VIDEO=false
            if $AUTO_YES; then
                DELETE_VIDEO=true
            else
                printf "\n❓ Delete raw video file '%s'? [y/N] " "$(basename "$VIDEO_FILE")" >&2
                read -r REPLY </dev/tty
                [[ "$REPLY" =~ ^[Yy]$ ]] && DELETE_VIDEO=true
            fi

            if $DELETE_VIDEO; then
                rm -f "$VIDEO_FILE"
                log_info "🗑️  Deleted: $VIDEO_FILE" >&2
            else
                log_info "📁 Kept: $VIDEO_FILE" >&2
                # Create a text file with the video URL if video was kept
                local URL_FILE="${VIDEO_FILE%.*}_link.txt"
                echo "$URL" > "$URL_FILE"
                log_info "📝 URL saved: $(basename "$URL_FILE")" >&2
            fi
            if [[ -n "$THUMB_FILE" && -f "$THUMB_FILE" ]] && { $THUMB_TMP || ! $KEEP_THUMB_FILE; }; then
                rm -f "$THUMB_FILE"
            fi

            return 0
        fi

        # If rendered, subtitle command produces a new file with lang suffix
        if $DO_RENDER; then
            local RENDERED="${BASE}_${LANG}.mp4"
            [[ -f "$RENDERED" ]] && VIDEO_FILE="$RENDERED"
        fi
    fi

    if [[ -n "$THUMB_FILE" && -f "$THUMB_FILE" ]]; then
        embed_video_cover_art "$VIDEO_FILE" "$THUMB_FILE"
        if $THUMB_TMP || ! $KEEP_THUMB_FILE; then
            rm -f "$THUMB_FILE"
        fi
    fi


    log_success "✅ Final file: $VIDEO_FILE" >&2
    
    # Create a text file with the video URL
    local URL_FILE="${VIDEO_FILE%.*}_link.txt"
    echo "$URL" > "$URL_FILE"
    log_info "📝 URL saved: $(basename "$URL_FILE")" >&2
    
    echo "$VIDEO_FILE"
}

# ==============================================================================
# TikTok Download — thin wrapper around video_download with TikTok-optimised
# defaults: no browser cookie (public videos work without login), and the
# standard best-quality format selector already avoids the watermarked
# 'download' format_id (yt-dlp assigns it preference=-2).
# Supports: vt.tiktok.com, vm.tiktok.com, www.tiktok.com & any tiktok URL.
# Usage: amir video tiktok <url> [same options as 'video download']
# ==============================================================================
video_tiktok() {
    if [[ -z "$1" || ( "$1" == --* && "$1" != "--subtitle" && "$1" != "-s" ) ]]; then
        log_error "TikTok URL is required." >&2
        echo "" >&2
        echo "Usage: amir video tiktok <url> [options]" >&2
        echo "       amir video tt     <url> [options]" >&2
        echo "" >&2
        echo "Examples:" >&2
        echo "  amir video tiktok 'https://vt.tiktok.com/ZSu8LxsHC'" >&2
        echo "  amir video tiktok 'https://vt.tiktok.com/ZSu8LxsHC' --subtitle -t fa" >&2
        echo "  amir video tiktok 'https://vt.tiktok.com/ZSu8LxsHC' --translate -t en fa" >&2
        echo "  amir video tiktok 'https://vt.tiktok.com/ZSu8LxsHC' --sub-only" >&2
        echo "" >&2
        echo "Options (same as 'amir video download'):" >&2
        echo "  --subtitle, -s         Subtitle pipeline: YouTube manual -> YouTube auto -> Whisper large-v3" >&2
        echo "  --translate            Download YT-style subs + translate via LLM" >&2
        echo "  --target, -t [s] <t>   Subtitle language (e.g. -t fa  or  -t en fa)" >&2
        echo "  --sub-only             Generate SRT only, do not burn into video" >&2
        echo "  --only-subs            Keep subtitle files, prompt to delete raw video" >&2
        echo "  -l, --get-link         Print direct stream URL without downloading" >&2
        return 1
    fi

    # Public TikTok videos need no browser login — pass --browser none so
    # video_download skips the default '--cookies-from-browser chrome' flag.
    # All other flags are forwarded as-is.
    video_download --browser none "$@"
}

run_video() {
    if [[ "$1" == "stats" ]]; then
        load_learning_data
        stats
    elif [[ "$1" == "reset" ]]; then
        reset_learning_data
    elif [[ "$1" == "codecs" ]]; then
        check_hevc_support
    elif [[ "$1" == "batch" ]]; then
        shift
        video "$@"          # video() already handles directories natively
    elif [[ "$1" == "cut" || "$1" == "trim" ]]; then
        shift
        run_video_cut "$@"
    elif [[ "$1" == "compress" ]]; then
        shift
        video "$@"
    elif [[ "$1" == "subtitle" ]]; then
        shift
        source "$LIB_DIR/commands/subtitle.sh"
        run_subtitle "$@"
    elif [[ "$1" == "download" || "$1" == "dl" ]]; then
        shift
        video_download "$@"
    elif [[ "$1" == "tiktok" || "$1" == "tt" ]]; then
        shift
        video_tiktok "$@"
    else
        video "$@"
    fi
}
