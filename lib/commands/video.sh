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
    local config_dir="${AMIR_CONFIG_DIR:-$HOME/.amir}"
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

reset() {
    local config_dir="${AMIR_CONFIG_DIR:-$HOME/.amir}"
    local learning_file="$config_dir/learning_data"
    
    if [[ -f "$learning_file" ]]; then
        rm "$learning_file"
        echo "✅ Advanced learning data reset to defaults."
    else
        echo "ℹ️  No learning data found."
    fi
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
    local config_dir="${AMIR_CONFIG_DIR:-$HOME/.amir}"
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
    local config_dir="${AMIR_CONFIG_DIR:-$HOME/.amir}"
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
    
    local input_bitrate=$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null)
    local bitrate_flags=()
    if [[ -n "$input_bitrate" && "$input_bitrate" =~ ^[0-9]+$ ]]; then
        # Apply 15% safety overhead to the ceiling
        local max_bitrate=$(echo "$input_bitrate * 1.15 / 1" | bc)
        # Standard bufsize is usually 2x maxrate for VBR stability
        local buf_size=$((max_bitrate * 2))
        bitrate_flags=("-maxrate" "${max_bitrate}" "-bufsize" "${buf_size}")
    fi

    # Execute ffmpeg with a single-line progress filter
    local filter_cmd="fps=25,scale=${target_w}:${target_h_final}:force_original_aspect_ratio=decrease,pad=${target_w}:${target_h_final}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    
    ffmpeg -hide_banner -loglevel info -stats -nostdin -y -i "$input_file" \
    -vf "$filter_cmd" -sws_flags bilinear \
    -c:v "$encoder" -q:v $quality $tag_opt \
    "${bitrate_flags[@]}" \
    -af "$audio_filter" \
    -c:a aac -pix_fmt yuv420p -movflags +faststart "$output" 2>&1 | while read -d $'\r' -r line; do
        printf "\r⏳ Processing... %s" "$line"
    done
    printf "\r⏳ Processing... Done!                                        \n"
    
    if [[ ! -f "$output" ]]; then
        echo "❌ Compression failed!"
        return
    fi
    
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
    # If no arguments, show help
    if [[ $# -eq 0 ]]; then
        echo "Usage: amir video <files|dirs...> [Resolution] [Quality]"
        echo "       amir video cut <file> [options]"
        echo "Example: amir video Video1.mp4 720 60"
        echo "Cut:     amir video cut input.mp4 -s 00:01:00 -e 00:02:00"
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
            --render) encode=1; shift ;;
            *) 
                if [[ -f "$1" && -z "$input_file" ]]; then
                    input_file="$1"
                fi
                shift 
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

    echo "✂️  Cutting Video: $(basename "$input_file")"
    
    # Allow override of ffmpeg binary via env var (e.g. from static_ffmpeg in python)
    local ffmpeg_cmd="${FFMPEG_EXEC:-ffmpeg}"

    local cmd=("$ffmpeg_cmd" "-hide_banner" "-loglevel" "info" "-y")
    
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
        local quality=$(get_config "video" "quality" "60")
        
        # Hardware Detection
        local encoder="libx265"
        local tag_opts=("-tag:v" "hvc1")
        if [[ "$OSTYPE" == "darwin"* ]]; then
             if "$ffmpeg_cmd" -encoders 2>/dev/null | grep -q "hevc_videotoolbox"; then
                encoder="hevc_videotoolbox"
            fi
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if lspci 2>/dev/null | grep -iq nvidia && "$ffmpeg_cmd" -encoders 2>/dev/null | grep -q "hevc_nvenc"; then
                 encoder="hevc_nvenc"; tag_opts=()
            fi
        fi
        
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
             # Target slightly higher (105%) to preserve quality during re-encode without bloat
             target_bitrate_val=$(echo "$input_bitrate * 1.05 / 1" | bc)
             
             # Maxrate slightly higher for VBR headroom
             local max_rat=$(echo "$target_bitrate_val * 1.2 / 1" | bc)
             local buf=$(echo "$max_rat * 2" | bc)
             
             bitrate_flags=("-maxrate" "${max_rat}" "-bufsize" "${buf}")
        fi

        echo "📊 Settings: $encoder (Q:$quality) | Bitrate Cap: ${max_bitrate:-Auto}"
        
        # Construct Filter Chain
        if [[ -n "$filter_complex" ]]; then
             if [[ "$encoder" == "hevc_videotoolbox" ]]; then
                 if [[ -n "$target_bitrate_val" ]]; then
                     # Use Average Bitrate mode to match input specs (as requested by user)
                     cmd+=("-vf" "$filter_complex" "-c:v" "$encoder" "-b:v" "${target_bitrate_val}" "${tag_opts[@]}")
                 else
                     # Fallback to Quality mode
                     cmd+=("-vf" "$filter_complex" "-c:v" "$encoder" "-q:v" "$quality" "${tag_opts[@]}")
                 fi
             else
                 # CPU/Other needs flags (simplified for now)
                  local crf_val=$(( (100 - quality) * 51 / 100 ))
                  [[ $crf_val -lt 15 ]] && crf_val=15
                  cmd+=("-vf" "$filter_complex" "-c:v" "libx264" "-crf" "$crf_val" "-preset" "medium")
             fi
             cmd+=("${bitrate_flags[@]}" "-c:a" "aac")
        else
            # No filters, just re-encode (cut with re-encode)
             cmd+=("-c:v" "libx264" "-crf" "23" "-preset" "medium" "-c:a" "aac")
        fi
    else
        echo "🚀 Mode: Stream Copy (Instant)"
        cmd+=("-c" "copy")
    fi

    cmd+=("-map_metadata" "0" "$output_file")

    # Execute
    # Direct execution without pipe to avoid subshell/signal issues
    "${cmd[@]}"
    
    # Check result
    if [[ -f "$output_file" ]]; then
        echo "✅ Output saved to: $(realpath "$output_file")"
    else
        echo "❌ Operation failed."
        return 1
    fi
}

run_video() {
    if [[ "$1" == "stats" ]]; then
        stats
    elif [[ "$1" == "reset" ]]; then
        reset
    elif [[ "$1" == "codecs" ]]; then
        codecs_check
    elif [[ "$1" == "batch" ]]; then
        shift
        # If the first arg after 'batch' is a directory, use it, otherwise use "."
        if [[ -d "$1" ]]; then
            local target_dir="$1"
            shift
            video "$target_dir" "$@"
        else
            video "." "$@"
        fi
    elif [[ "$1" == "cut" || "$1" == "trim" ]]; then
        shift
        run_video_cut "$@"
    else
        video "$@"
    fi
}
