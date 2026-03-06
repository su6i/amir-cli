#!/bin/bash

# We define compress at the top level so other scripts (like batch) can use it when sourced.

# Source Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")"
if [[ -f "$LIB_DIR/config.sh" ]]; then
    source "$LIB_DIR/config.sh"
    # We don't verify init_config here, we just use get_config if needed.
    # Actually, we should ensure config exists if we are going to read it.
    if type init_config &>/dev/null; then init_config; fi
else
    # Fallback
    get_config() { echo "$3"; }
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

    if [[ ! -f "$input_file" ]]; then
        # Silent ignore for directories if they get here (shouldn't happen)
        return
    fi
    
    # Skip already compressed versions to prevent loops
    if [[ "$input_file" == *"_${target_h}p_"* || "$input_file" == *"_compressed"* ]]; then
        return
    fi
    
    # Detect input dimensions (Width, Height, and Rotation from side data or tags)
    local ff_output=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height:stream_side_data=rotation -of csv=s=x:p=0 "$input_file" 2>/dev/null)
    local in_w=$(echo "$ff_output" | cut -d'x' -f1)
    local in_h=$(echo "$ff_output" | cut -d'x' -f2)
    local rotation=$(echo "$ff_output" | cut -d'x' -f3)

    # Clean rotation (remove minus sign if any, handle empty)
    rotation=${rotation#-}
    [[ -z "$rotation" ]] && rotation=0

    # Handle rotation (some videos are stored sideways but flagged with rotation)
    if [[ "$rotation" == "90" || "$rotation" == "-90" || "$rotation" == "270" ]]; then
        local temp_w=$in_w
        in_w=$in_h
        in_h=$temp_w
    fi

    local is_portrait=0
    if [[ "$in_h" -gt "$in_w" ]]; then
        is_portrait=1
    fi

    # Calculate target dimensions base on orientation
    local target_w target_h_final
    if [[ $is_portrait -eq 1 ]]; then
        target_h_final=$(( (target_h * 16 / 9 + 1) / 2 * 2 ))
        target_w=$target_h
        # Ensure target_h_final is the larger dimension
        [[ $target_h_final -lt $target_w ]] && target_h_final=$((target_w * 16 / 9))
    else
        target_w=$(( (target_h * 16 / 9 + 1) / 2 * 2 ))
        target_h_final=$target_h
    fi

    local output="${input_file%.*}_${target_h}p_q${quality}.mp4"
    
    if [[ -f "$output" ]]; then
       echo "⏩ Skipping: $(basename "$input_file") (Output exists)"
       return
    fi

    local input_size=$(ls -lh "$input_file" | awk '{print $5}')
    local input_bytes=$(ls -l "$input_file" | awk '{print $5}')
    local duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null)
    
    if [[ -z "$duration" ]]; then
        echo "⚠️  Skipping: $(basename "$input_file") (Could not determine duration)"
        return
    fi

    local duration_seconds=${duration%.*}
    local duration_formatted=$(printf '%02d:%02d:%02d' $(($duration_seconds/3600)) $(($duration_seconds%3600/60)) $(($duration_seconds%60)))
    
    # Hardware Detection
    local cpu_info="Unknown"
    local gpu_info="Unknown"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        cpu_info=$(sysctl -n machdep.cpu.brand_string 2>/dev/null)
        gpu_info="Apple Silicon GPU"
        [[ "$cpu_info" == *"Intel"* ]] && gpu_info="Intel GPU"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        cpu_info=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)
        gpu_info=$(lspci | grep -i vga | cut -d: -f3 | xargs 2>/dev/null || echo "Linux GPU")
    fi
    
    local quality_factor=${quality_factors[$quality]:-1.0}
    local speed_factor=${speed_factors[$quality]:-6}
    local sample_count=${sample_counts[$quality]:-0}
    
    # Encoder selection
    local encoder="libx265"
    local tag_opt="-tag:v hvc1"
    
    # Check available encoders
    if ffmpeg -encoders 2>/dev/null | grep -q "hevc_videotoolbox"; then
        encoder="hevc_videotoolbox"
    elif ffmpeg -encoders 2>/dev/null | grep -q "hevc_nvenc"; then
        encoder="hevc_nvenc"
        tag_opt=""
    elif ffmpeg -encoders 2>/dev/null | grep -q "hevc_amf"; then
        encoder="hevc_amf"
        tag_opt=""
    elif ffmpeg -encoders 2>/dev/null | grep -q "hevc_qsv"; then
        encoder="hevc_qsv"
        tag_opt=""
    fi
    
    # Pre-calculate display name
    local encoder_display="CPU (x265)"
    [[ "$encoder" == "hevc_videotoolbox" ]] && encoder_display="Apple Silicon"
    [[ "$encoder" == "hevc_nvenc" ]] && encoder_display="NVIDIA NVENC"
    [[ "$encoder" == "hevc_qsv" ]] && encoder_display="Intel QSV"
    
    echo ""
    echo "🎬 PROCESSING: $(basename "$input_file")"
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo ""
    
    local col_width=$(calculate_column_width 3 28 35)
    
    printf "┌%s┬%s┬%s┐\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    # Standard Header Padding (Unicode Aware)
    local h_input=$(pad_to_width "📂 INPUT FILE" $col_width)
    local h_hard=$(pad_to_width "🖥️  HARDWARE" $col_width)
    local h_set=$(pad_to_width "🎯 SETTINGS" $col_width)
    
    printf "│ %s │ %s │ %s │\n" "$h_input" "$h_hard" "$h_set"
    
    printf "├%s┼%s┼%s┤\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    # Content Padding using standard unicode width
    local t_file=$(pad_to_width "File: $(basename "$input_file")" $col_width)
    local t_cpu=$(pad_to_width "CPU: $cpu_info" $col_width)
    local t_res=$(pad_to_width "Resolution: ${target_h}p" $col_width)
    
    local t_size=$(pad_to_width "Size: $input_size" $col_width)
    local t_gpu=$(pad_to_width "GPU: $gpu_info" $col_width)
    local t_qual=$(pad_to_width "Quality: $quality/100" $col_width)
    
    local t_dur=$(pad_to_width "Duration: $duration_formatted" $col_width)
    local t_enc=$(pad_to_width "Encoder: ${encoder_display}" $col_width)
    local t_orient="Landscape"
    [[ $is_portrait -eq 1 ]] && t_orient="Portrait"
    local t_audio=$(pad_to_width "Orientation: $t_orient" $col_width)

    printf "│ %s │ %s │ %s │\n" \
        "$t_file" "$t_cpu" "$t_res"
    printf "│ %s │ %s │ %s │\n" \
        "$t_size" "$t_gpu" "$t_qual"
    printf "│ %s │ %s │ %s │\n" \
        "$t_dur" "$t_enc" "$t_audio"
    
    printf "└%s┴%s┴%s┘\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    echo ""
    echo "⏳ Processing..."
    
    local start_time=$(date +%s)
    

    
    # Windows/Linux fix for audio filters
    local audio_filter="aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
    
    # bitrate_flags only for software encoder (hevc_videotoolbox/nvenc/etc don't support
    # -maxrate/-bufsize combined with -q:v quality mode — causes immediate failure)
    local bitrate_flags=()
    if [[ "$encoder" == "libx265" ]]; then
        local input_bitrate=$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null)
        if [[ -n "$input_bitrate" && "$input_bitrate" =~ ^[0-9]+$ ]]; then
            local max_bitrate=$(echo "$input_bitrate * 1.15 / 1" | bc)
            local buf_size=$((max_bitrate * 2))
            bitrate_flags=("-maxrate" "${max_bitrate}" "-bufsize" "${buf_size}")
        fi
    fi

    # Execute ffmpeg with a single-line progress filter
    local filter_cmd="fps=25,scale=${target_w}:${target_h_final}:force_original_aspect_ratio=decrease,pad=${target_w}:${target_h_final}:(ow-iw)/2:(oh-ih)/2,setsar=1"

    local ffmpeg_error_log=$(mktemp)
    ffmpeg -hide_banner -loglevel info -stats -nostdin -y -i "$input_file" \
    -vf "$filter_cmd" -sws_flags bilinear \
    -c:v "$encoder" -q:v $quality $tag_opt \
    "${bitrate_flags[@]}" \
    -af "$audio_filter" \
    -c:a aac -pix_fmt yuv420p -movflags +faststart "$output" 2> >(tee "$ffmpeg_error_log" >&2) | while read -d $'\r' -r line; do
        printf "\r⏳ Processing... %s" "$line"
    done
    local ffmpeg_exit=${PIPESTATUS[0]:-$?}
    printf "\r⏳ Processing... Done!                                        \n"

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
    
    printf "┌%s┬%s┬%s┬%s┐\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    # Scientific Header Padding
    local h_in=$(pad_to_width "📥 INPUT" $col_width)
    local h_out=$(pad_to_width "📤 OUTPUT" $col_width)
    local h_perf=$(pad_to_width "📊 PERFORMANCE" $col_width)
    local h_comp=$(pad_to_width "📈 COMPARISON" $col_width)
    
    printf "│ %s │ %s │ %s │ %s │\n" \
        "$h_in" "$h_out" "$h_perf" "$h_comp"
    
    printf "├%s┼%s┼%s┼%s┤\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    # Content Padding using standard unicode width
    local t_in_file=$(pad_to_width "File: $(basename "$input_file")" $col_width)
    local t_out_file=$(pad_to_width "File: $(basename "$output")" $col_width)
    local t_time=$(pad_to_width "Time: $total_elapsed_formatted" $col_width)
    local t_saved=$(pad_to_width "${label_saved}: ${val_saved}" $col_width)
    
    local t_in_size=$(pad_to_width "Size: $input_size" $col_width)
    local t_out_size=$(pad_to_width "Size: $output_size" $col_width)
    local t_speed=$(pad_to_width "Speed: ${actual_speed}x" $col_width)
    local t_ratio=$(pad_to_width "Ratio: ${ratio}x smaller" $col_width)

    printf "│ %s │ %s │ %s │ %s │\n" \
        "$t_in_file" "$t_out_file" "$t_time" "$t_saved"
    printf "│ %s │ %s │ %s │ %s │\n" \
        "$t_in_size" "$t_out_size" "$t_speed" "$t_ratio"
    
    printf "└%s┴%s┴%s┴%s┘\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    echo ""
    echo "📍 Output: $(realpath "$output")"
}

video() {
    # Support explicit 'compress' subcommand by skipping it
    if [[ "$1" == "compress" ]]; then
        shift
    fi

    # If no arguments, show help
    if [[ $# -eq 0 ]]; then
        echo "Usage: amir video compress <files...> [Resolution] [Quality]"
        echo "       amir video cut / trim <file> [options]"
        echo "       amir video batch <dir> [Resolution]"
        echo ""
        echo "Example (Compress): amir video compress movie.mp4 1080 60"
        echo "Example (Trim):     amir video trim clip.mp4 -s 00:01:30 -t 00:03:00"
        echo ""
        echo "Options for cut/trim:"
        echo "  -s, --start      Start time (HH:MM:SS or seconds)"
        echo "  -e, --end        End time (HH:MM:SS or seconds)"
        echo "  -t, --to         End time (alias for --end)"
        echo "  -d, --duration   Duration from start"
        echo "  -o, --output     Output filename"
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
    # Load defaults from Config
    local target_h=$(get_config "video" "resolution" "720")
    local quality=$(get_config "video" "quality" "70")
    
    # Validation for config values
    [[ "$target_h" =~ ^[0-9]+$ ]] || target_h=720
    [[ "$quality" =~ ^[0-9]+$ ]] || quality=60
    
    for arg in "$@"; do
        if [[ -f "$arg" || -d "$arg" ]]; then
            inputs+=("$arg")
        elif [[ "$arg" =~ ^[0-9]+$ ]]; then
            if [[ "$arg" -le 100 ]]; then
                quality="$arg"
            else
                target_h="$arg"
            fi
        else
            # Try to treat unknown arg as input (might be a file pattern that didn't expand)
             if [[ -f "$arg" || -d "$arg" ]]; then
                 inputs+=("$arg")
             fi
        fi
    done

    if [[ ${#inputs[@]} -eq 0 ]]; then
        echo "❌ No valid input files or directories found."
        return 1
    fi

    load_learning_data

    # Process all inputs
    for input in "${inputs[@]}"; do
        if [[ -f "$input" ]]; then
            # Single File
            process_video "$input" "$target_h" "$quality"
        elif [[ -d "$input" ]]; then
            # Directory (Batch)
            echo "📦 Batch processing directory: $input"
            find "$input" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.mov" -o -name "*.mkv" -o -name "*.MP4" -o -name "*.MOV" -o -name "*.MKV" \) | while read -r file; do
                process_video "$file" "$target_h" "$quality" < /dev/null
            done
        fi
    done
}

run_video_cut() {
    local input_file=""
    local start_time=""
    local end_time=""
    local duration=""
    local output_file=""
    local subtitle_file=""
    local fonts_dir=""
    local encode=0
    
    # UI Display Overrides (for symlinked/temp files)
    local display_in=""
    local display_out=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -s|--start) start_time="$2"; shift 2 ;;
            -e|--end) end_time="$2"; shift 2 ;;
            -t|--to) end_time="$2"; shift 2 ;;
            -d|--duration) duration="$2"; shift 2 ;;
            -o|--output) output_file="$2"; shift 2 ;;
            --subtitles) subtitle_file="$2"; shift 2 ;;
            --fonts-dir) fonts_dir="$2"; shift 2 ;;
            --display-input) display_in="$2"; shift 2 ;;
            --display-output) display_out="$2"; shift 2 ;;
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
        echo "Usage: amir video cut <file> [-s start] [-e end] [-o output]"
        return 1
    fi

    # Auto-generate output name if not provided
    if [[ -z "$output_file" ]]; then
        local base="${input_file%.*}"
        local ext="${input_file##*.}"
        output_file="${base}_cut.${ext}"
    fi

    echo "🎬  Processing Video: ${display_in:-$(basename "$input_file")}"
    
    # Allow override of ffmpeg binary via env var (e.g. from static_ffmpeg in python)
    local ffmpeg_cmd="${FFMPEG_EXEC:-ffmpeg}"

    local cmd=("$ffmpeg_cmd" "-hide_banner" "-loglevel" "error" "-stats" "-y")
    
    # Start time (seek)
    if [[ -n "$start_time" ]]; then
        cmd+=("-ss" "$start_time")
    fi

    cmd+=("-i" "$input_file")

    if [[ -n "$end_time" ]]; then
        cmd+=("-to" "$end_time")
    elif [[ -n "$duration" ]]; then
        cmd+=("-t" "$duration")
    fi

    # Subtitle Filter Logic
    local filter_complex=""
    local tmp_sub="" 

    # Cleanup trap (will run on exit)
    cleanup_subs() {
        if [[ -n "$tmp_sub" && -f "$tmp_sub" ]]; then
            rm -f "$tmp_sub"
        fi
    }
    trap cleanup_subs EXIT

    if [[ -n "$subtitle_file" ]]; then
        # Create safe temp copy to avoid FFmpeg parsing headaches with spaces/special chars
        tmp_sub="/tmp/safe_subs_$$.ass"
        cp "$subtitle_file" "$tmp_sub"

        # Helper function for basic escaping (mainly for fonts_dir if needed)
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
        filter_complex="subtitles=filename=${esc_sub}${fonts_opt}"
        
        # If subtitles are present, force render mode
        encode=1
    fi

    if [[ $encode -eq 1 ]]; then
        echo "⚙️  Mode: Rendering (High Quality)"
        
        # Hardware Detection & Quality Settings (Reuse logic from process_video is ideal, but here we inline for now)
        # TODO: Refactor process_video to return flags to avoid duplication. 
        # For now, we use the simple "working well" logic + Bitrate Cap.
        
        local target_h=$(get_config "video" "resolution" "720")
        local quality=$(get_config "video" "quality" "70")
        
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
        
        # Construct Filter Chain
        if [[ -n "$filter_complex" ]]; then
            # H.264 with CRF (match input quality, prevent bloat)
            local crf_val=$(( (100 - quality) * 51 / 100 ))
            [[ $crf_val -lt 18 ]] && crf_val=18
            cmd+=("-vf" "$filter_complex" "-c:v" "libx264" "-crf" "$crf_val" "${bitrate_flags[@]}" "-preset" "medium" "-pix_fmt" "yuv420p")
            # Audio Copy (preserve original quality)
            cmd+=("-c:a" "copy")
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

# Calculate visual width (2 for wide/emoji, 1 for normal) using Python unicodedata
get_visual_width() {
    python3 -c "import unicodedata, sys; s=sys.argv[1]; print(sum(2 if unicodedata.east_asian_width(c) in 'WF' else 0 if unicodedata.category(c) in ('Mn','Me','Cf') else 1 for c in s))" "$1" 2>/dev/null || echo ${#1}
}

# Pad to target visual width
pad_to_width() {
    local text="$1"
    local target="$2"
    local current=$(get_visual_width "$text")
    local diff=$((target - current))
    echo -n "$text"
    if [[ $diff -gt 0 ]]; then
        printf "%${diff}s" ""
    fi
}

    # Execute
    # Direct execution without pipe to avoid subshell/signal issues
    "${cmd[@]}"
    
    # Check result
    if [[ -f "$output_file" ]]; then
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
        
        # Premium Unicode Table (Width Optimized: 16 per col)
        # Total width ~ 77 chars (fits in standard 80-col terminal)
        local t_line="┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐"
        local h_line="├──────────────────┼──────────────────┼──────────────────┼──────────────────┤"
        local b_line="└──────────────────┴──────────────────┴──────────────────┴──────────────────┘"

        echo "$t_line"
        printf "│ %s │ %s │ %s │ %s │\n" "$(pad_to_width "📥 INPUT" 16)" "$(pad_to_width "📤 OUTPUT" 16)" "$(pad_to_width "📊 DETAILS" 16)" "$(pad_to_width "📈 RATIO" 16)"
        echo "$h_line"
        
        # Use display overrides or fall back to basenames
        local f_in_label="${display_in:-$(basename "$input_file")}"
        local f_out_label="${display_out:-$(basename "$output_file")}"

        # Truncate labels for table (Max 16 chars)
        local label_in="File: $f_in_label"; [[ $(get_visual_width "$label_in") -gt 16 ]] && label_in="${label_in:0:13}..."
        local label_out="File: $f_out_label"; [[ $(get_visual_width "$label_out") -gt 16 ]] && label_out="${label_out:0:13}..."
        
        local duration_s=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$output_file" 2>/dev/null | cut -d. -f1)

        printf "│ %s │ %s │ %s │ %s │\n" "$(pad_to_width "$label_in" 16)" "$(pad_to_width "$label_out" 16)" "$(pad_to_width "Codec: $encoder" 16)" "$(pad_to_width "Saved: ${percent_saved}%" 16)"
        printf "│ %s │ %s │ %s │ %s │\n" "$(pad_to_width "Size: $in_size" 16)" "$(pad_to_width "Size: $out_size" 16)" "$(pad_to_width "Time: ${duration_s}s" 16)" "$(pad_to_width "Ratio: $ratio" 16)"
        echo "$b_line"
        
        echo ""
        echo "📍 Output: $(realpath "$output_file")"
    else
        echo "❌ Operation failed."
        return 1
    fi
}

# ==============================================================================
# Video Download (web, YouTube, CloudflareStream, 1000+ sites via yt-dlp)
# ==============================================================================
video_download() {
    local URL=""
    local LANG="fa"
    local LANG_SRC="en"
    local DO_SUBTITLE=false
    local YT_SUBS=false           # download YouTube's own subtitles instead of Whisper
    local DO_RENDER=false         # burn subtitles into video
    local ONLY_SUBS=false
    local SUB_FORMAT="srt"        # srt | ass | all
    local AUTO_YES=false
    local GET_LINK=false
    local YT_TRANSLATE=false       # translate downloaded YT subs via amir subtitle (skips Whisper)
    local BROWSER="chrome"
    local COOKIES_FILE=""
    local DL_RESOLUTION=$(get_config "video" "resolution" "720")
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --subtitle|-s)   DO_SUBTITLE=true; DO_RENDER=true; shift ;;  # whisper+burn
            --yt-subs)       YT_SUBS=true; shift ;;              # youtube built-in subs
            --translate)     YT_TRANSLATE=true; YT_SUBS=true; shift ;; # download YT subs + translate
            --render|-r)     DO_RENDER=true; shift ;;
            --no-render)     DO_RENDER=false; shift ;;
            --only-subs)     ONLY_SUBS=true; shift ;;
            --sub-format)    SUB_FORMAT="$2"; shift 2 ;;
            --target|-t)
                # accept: -t <target>  OR  -t <src> <target>
                if [[ -n "${3:-}" && "${3:-}" != -* && ! "${3:-}" =~ ^https?:// && ${#3} -le 10 ]]; then
                    LANG_SRC="$2"; LANG="$3"; shift 3
                else
                    LANG="$2"; shift 2
                fi ;;
            --browser|-b)    BROWSER="$2"; shift 2 ;;
            --cookies)       COOKIES_FILE="$2"; shift 2 ;;
            -y|--yes)        AUTO_YES=true; shift ;;
            --get-link|-l)   GET_LINK=true; shift ;;
            --resolution|-r) DL_RESOLUTION="$2"; shift 2 ;;
            -*)
                log_error "Unknown option: $1" >&2
                echo "Usage: amir video download <url> [options]" >&2
                return 1
                ;;
            *)  URL="$1"; shift ;;
        esac
    done

    # Strip shell-escaped backslashes (e.g. \? \= that zsh adds when URL is unquoted)
    URL="${URL//\\/}"

    # When --translate is set, source and target must differ
    if $YT_TRANSLATE && [[ "$LANG" == "$LANG_SRC" ]]; then
        log_error "Source and target language are the same (${LANG})." >&2
        echo "" >&2
        echo "  Translate TO a language: --translate -t fa" >&2
        echo "  Specify src AND target:  --translate -t en fa" >&2
        echo "  (default source: en, default target: fa)" >&2
        return 1
    fi

    if [[ -z "$URL" ]]; then
        log_error "URL is required." >&2
        echo "" >&2
        echo "Usage: amir video download <url> [options]" >&2
        echo "" >&2
        echo "Options:" >&2
        echo "  --subtitle, -s        Transcribe + burn subtitles via Whisper AI (default lang: fa)" >&2
        echo "  --yt-subs             Download YouTube's own subtitles (human first, auto-gen fallback)" >&2
        echo "  --target, -t [src] <target>  Subtitle language; optionally specify source then target (e.g. -t en fa)" >&2
        echo "  --render, -r          Burn subtitle into video (use with --yt-subs)" >&2
        echo "  --no-render           Generate subtitle files only, no burning (use with --subtitle)" >&2
        echo "  --only-subs           Keep subtitle files; prompt to delete raw video" >&2
        echo "  --sub-format <fmt>    Subtitle format: srt | ass | all (default: srt)" >&2
        echo "  -y, --yes             Auto-confirm deletion prompt (use with --only-subs)" >&2
        echo "  -l, --get-link        Print direct stream URL(s) — for use in a download manager" >&2
        echo "  --browser <name>      Browser for cookies (default: chrome)" >&2
        echo "  --cookies <file>      Path to Netscape cookies.txt file" >&2
        return 1
    fi

    if ! command -v yt-dlp &>/dev/null; then
        log_error "yt-dlp is not installed. Install with: brew install yt-dlp" >&2
        return 1
    fi

    # Build cookie arguments
    local -a COOKIE_ARGS=()
    if [[ -n "$COOKIES_FILE" ]]; then
        COOKIE_ARGS=(--cookies "$COOKIES_FILE")
    elif [[ -n "$BROWSER" && "$BROWSER" != "none" ]]; then
        COOKIE_ARGS=(--cookies-from-browser "$BROWSER")
    fi

    # ── Get-link mode ──────────────────────────────────────────────────────
    if $GET_LINK; then
        log_info "🔗 Fetching direct download URL(s) from: $URL" >&2
        log_info "   Auth via: ${COOKIES_FILE:-browser:$BROWSER}" >&2
        yt-dlp \
            "${COOKIE_ARGS[@]}" \
            --extractor-args "generic:impersonate" \
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

    log_info "⬇️  Starting download..." >&2

    # Download:
    #   stdout  → temp file  (line1 = title via before_dl, line2 = final filepath via after_move)
    #   stderr  → filtered:  only [download] progress lines + ERROR/WARNING lines reach the terminal
    #             everything else ([youtube], [info], [generic], …) is hidden
    local _PATHFILE
    _PATHFILE=$(mktemp /tmp/amir_dl_path.XXXXXX)
    local VIDEO_FILE
    yt-dlp \
        "${COOKIE_ARGS[@]}" \
        --extractor-args "generic:impersonate" \
        --remote-components "ejs:github" \
        --newline \
        --continue \
        -f "bestvideo[height<=${DL_RESOLUTION}]+bestaudio/best[height<=${DL_RESOLUTION}]/best" \
        --merge-output-format mp4 \
        --print "before_dl:%(title)s" \
        --print "after_move:filepath" \
        -o "$OUT_TEMPLATE" \
        "$URL" > "$_PATHFILE" \
        2> >(grep --line-buffered -E '^\[download\]|^ERROR|^WARNING:' >&2)
    local _DL_EXIT=$?

    local _VID_TITLE
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

    log_success "Saved → $(basename "$VIDEO_FILE")" >&2

    # ── YouTube built-in subtitles ──────────────────────────────────────────
    if $YT_SUBS; then
        local BASE_YT="${VIDEO_FILE%.*}"
        log_info "📥 Fetching subtitles  ${LANG_SRC} → ${LANG}..." >&2
        # --write-subs      : human-curated subs (preferred)
        # --write-auto-subs : auto-generated, only downloaded when human subs absent for the lang
        yt-dlp \
            "${COOKIE_ARGS[@]}" \
            --extractor-args "generic:impersonate" \
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

        # Collect downloaded SRT files
        local -a YT_SUB_FILES=()
        for f in "${BASE_YT}"*.srt; do
            [[ -f "$f" ]] && YT_SUB_FILES+=("$f")
        done

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
            for f in "${YT_SUB_FILES[@]}"; do
                [[ "$f" == *".${LANG_SRC}.srt" && "$f" != *"-orig.srt" ]] && SRC_SRT="$f" && break
            done
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
            local -a SUB_FLAGS=("-s" "$LANG_SRC" "-t" "$LANG")
            $ONLY_SUBS && SUB_FLAGS+=("--no-render")
            ! $DO_RENDER && SUB_FLAGS+=("--no-render")

            log_info "🌐 Translating ${LANG_SRC}→${LANG} via LLM (no Whisper)..." >&2
            "$AMIR_BIN" subtitle "$VIDEO_FILE" "${SUB_FLAGS[@]}"
            return $?
        fi

        # ── --render without --translate: burn existing LANG or EN srt directly ──
        if $DO_RENDER && [[ ${#YT_SUB_FILES[@]} -gt 0 ]]; then
            # Prefer target-lang SRT, fallback to first available
            local SRT_TO_BURN=""
            for f in "${YT_SUB_FILES[@]}"; do
                [[ "$f" == *"${LANG}"* ]] && SRT_TO_BURN="$f" && break
            done
            [[ -z "$SRT_TO_BURN" ]] && SRT_TO_BURN="${YT_SUB_FILES[1]}"

            log_info "🎬 Burning subtitle: $(basename "$SRT_TO_BURN")" >&2
            local AMIR_BIN
            AMIR_BIN="$(dirname "$LIB_DIR")/amir"
            "$AMIR_BIN" video cut "$VIDEO_FILE" \
                --subtitles "$SRT_TO_BURN" \
                --output "${VIDEO_FILE%.*}_subbed.mp4" \
                --render >&2
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
            fi
            return 0
        fi

        log_success "✅ Final file: $VIDEO_FILE" >&2
        echo "$VIDEO_FILE"
        return 0
    fi

    # ── Subtitle generation ─────────────────────────────────────────────────
    if $DO_SUBTITLE; then
        local AMIR_BIN
        AMIR_BIN="$(dirname "$LIB_DIR")/amir"
        local -a SUB_FLAGS=("-t" "$LANG")
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
            fi
            return 0
        fi

        # If rendered, subtitle command produces a new file with lang suffix
        if $DO_RENDER; then
            local RENDERED="${BASE}_${LANG}.mp4"
            [[ -f "$RENDERED" ]] && VIDEO_FILE="$RENDERED"
        fi
    fi

    log_success "✅ Final file: $VIDEO_FILE" >&2
    echo "$VIDEO_FILE"
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
    else
        video "$@"
    fi
}
