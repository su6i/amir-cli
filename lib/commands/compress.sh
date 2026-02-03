#!/bin/bash

# We define compress at the top level so other scripts (like batch) can use it when sourced.

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
    echo "┌───────┬──────────────┬─────────────┬──────────────┬──────────┐"
    echo "│ Qual  │ Factor       │ Est. Ratio  │ Speed Factor │ Samples  │"
    echo "├───────┼──────────────┼─────────────┼──────────────┼──────────┤"
    
    for q in 40 50 55 60 65 70 75 80; do
        local factor=${quality_factors[$q]:-1.0}
        local speed=${speed_factors[$q]:-6}
        local samples=${sample_counts[$q]:-0}
        local est_ratio=$(echo "scale=1; $factor * 100" | bc)
        
        printf "│ %5d │ %12.4f │ %11s%% │ %12d │ %8d │\n" \
            "$q" "$factor" "$est_ratio" "$speed" "$samples"
    done
    
    echo "└───────┴──────────────┴─────────────┴──────────────┴──────────┘"
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

compress() {
    if [[ -z "$1" || ! -f "$1" ]]; then
        echo "❌ Error: File not found."
        return 1
    fi
    
    # Basic runtime checks
    if ! command -v ffmpeg &> /dev/null || ! command -v bc &> /dev/null; then
        echo "❌ Critical dependencies missing."
        echo "💡 Please run the installer: ./install.sh"
        return 1
    fi
    
    local target_h=${2:-720}
    local quality=${3:-60}
    # Ensure width is even (essential for some codecs/filters)
    # 480p -> 853.33 -> 853 (Odd!) -> Fix to 854
    local target_w=$(( (target_h * 16 / 9 + 1) / 2 * 2 ))
    local output="${1%.*}_${target_h}p_q${quality}.mp4"
    
    local input_size=$(ls -lh "$1" | awk '{print $5}')
    local input_bytes=$(ls -l "$1" | awk '{print $5}')
    local duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$1" 2>/dev/null)
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
    else 
        # Windows (Git Bash/WSL)
        cpu_info="Windows CPU" 
        gpu_info="Windows GPU"
    fi
    
    load_learning_data
    
    local base_ratio=0.06
    if [[ $input_bytes -gt 8589934592 ]]; then
        base_ratio=0.047
    elif [[ $input_bytes -gt 4294967296 ]]; then
        base_ratio=0.052
    elif [[ $input_bytes -gt 2147483648 ]]; then
        base_ratio=0.062
    else
        base_ratio=0.072
    fi
    
    local quality_factor=${quality_factors[$quality]:-1.0}
    local speed_factor=${speed_factors[$quality]:-6}
    local sample_count=${sample_counts[$quality]:-0}
    
    echo ""
    echo "🎬 VIDEO COMPRESSION TOOL"
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo ""
    
truncate_text() {
    local text="$1"
    local max_len="$2"
    if [[ ${#text} -gt $max_len ]]; then
        echo "${text:0:$((max_len-2))}.."
    else
        echo "$text"
    fi
}

    local col_width=$(calculate_column_width 3 28 35)
    
    printf "┌%s┬%s┬%s┐\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    # Print emojis explicitly to avoid printf width miscalculation
    # 📂 (2) + Space (1) = 3 chars prefix
    # 🖥️ (2) + Space (2) = 4 chars prefix
    # 🎯 (2) + Space (1) = 3 chars prefix
    printf "│ 📂 %-$((col_width-3))s │ 🖥️  %-$((col_width-4))s │ 🎯 %-$((col_width-3))s │\n" \
        "INPUT FILE" "HARDWARE" "SETTINGS"
    
    printf "├%s┼%s┼%s┤\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    # Pre-truncate fields to ensure table alignment
    local t_file=$(truncate_text "File: $(basename "$1")" $col_width)
    local t_cpu=$(truncate_text "CPU: $cpu_info" $col_width)
    local t_res=$(truncate_text "Resolution: ${target_h}p" $col_width)
    
    local t_size=$(truncate_text "Size: $input_size" $col_width)
    local t_gpu=$(truncate_text "GPU: $gpu_info" $col_width)
    local t_qual=$(truncate_text "Quality: $quality/100" $col_width)
    
    local t_dur=$(truncate_text "Duration: $duration_formatted" $col_width)
    local t_enc=$(truncate_text "Encoder: VideoToolbox" $col_width)
    local t_audio=$(truncate_text "Audio: AAC 44.1kHz" $col_width)

    printf "│ %-${col_width}s │ %-${col_width}s │ %-${col_width}s │\n" \
        "$t_file" "$t_cpu" "$t_res"
    printf "│ %-${col_width}s │ %-${col_width}s │ %-${col_width}s │\n" \
        "$t_size" "$t_gpu" "$t_qual"
    printf "│ %-${col_width}s │ %-${col_width}s │ %-${col_width}s │\n" \
        "$t_dur" "$t_enc" "$t_audio"
    
    printf "└%s┴%s┴%s┘\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    echo ""
    echo "⏳ Processing..."
    
    local start_time=$(date +%s)
    
    # Encoder selection
    local encoder="libx265"
    local tag_opt="-tag:v hvc1"
    
    # Check available encoders
    if ffmpeg -encoders 2>/dev/null | grep -q "hevc_videotoolbox"; then
        encoder="hevc_videotoolbox"
    elif ffmpeg -encoders 2>/dev/null | grep -q "hevc_nvenc"; then
        encoder="hevc_nvenc"
        tag_opt="" # NVENC handles tags differently often
    elif ffmpeg -encoders 2>/dev/null | grep -q "hevc_amf"; then
        encoder="hevc_amf"
        tag_opt=""
    elif ffmpeg -encoders 2>/dev/null | grep -q "hevc_qsv"; then
        encoder="hevc_qsv"
        tag_opt=""
    fi
    
    # Windows/Linux fix for audio filters
    local audio_filter="aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
    
    # Run ffmpeg with 'script' to force TTY behavior (prevents scrolling, fixes buffering)
    # macOS 'script -q /dev/null' keeps logs single-line (\r) vs newline (\n)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        script -q /dev/null ffmpeg -hide_banner -loglevel error -stats -nostdin -y -i "$1" \
        -vf "fps=25,scale=${target_w}:${target_h}:force_original_aspect_ratio=decrease,pad=${target_w}:${target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1" \
        -c:v "$encoder" -q:v $quality $tag_opt \
        -af "$audio_filter" \
        -c:a aac -pix_fmt yuv420p -movflags +faststart "$output"
    else
        # Linux/Windows fallback (standard execution)
        ffmpeg -hide_banner -loglevel error -stats -nostdin -y -i "$1" \
        -vf "fps=25,scale=${target_w}:${target_h}:force_original_aspect_ratio=decrease,pad=${target_w}:${target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1" \
        -c:v "$encoder" -q:v $quality $tag_opt \
        -af "$audio_filter" \
        -c:a aac -pix_fmt yuv420p -movflags +faststart "$output"
    fi
    
    if [[ ! -f "$output" ]]; then
        echo "❌ Compression failed!"
        return 1
    fi
    
    local end_time=$(date +%s)
    local total_elapsed=$((end_time - start_time))
    local total_elapsed_formatted=$(printf '%02d:%02d' $(($total_elapsed/60)) $(($total_elapsed%60)))
    
    local output_size=$(ls -lh "$output" | awk '{print $5}')
    local output_bytes=$(ls -l "$output" | awk '{print $5}')
    local ratio=$(echo "scale=2; $input_bytes / $output_bytes" | bc 2>/dev/null || echo "0")
    local percent_saved=$(echo "scale=1; 100 - ($output_bytes * 100 / $input_bytes)" | bc 2>/dev/null || echo "0")
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
    echo "✅ COMPRESSION COMPLETE"
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo ""
    
    local col_width=$(calculate_column_width 4 22 28)
    
    printf "┌%s┬%s┬%s┬%s┐\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    # Print emojis explicitly to avoid printf width miscalculation (All have 1 space = 3 chars prefix)
    printf "│ 📥 %-$((col_width-3))s │ 📤 %-$((col_width-3))s │ 📊 %-$((col_width-3))s │ 📈 %-$((col_width-3))s │\n" \
        "INPUT" "OUTPUT" "PERFORMANCE" "COMPARISON"
    
    printf "├%s┼%s┼%s┼%s┤\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    # Pre-truncate validation table
    local t_in_file=$(truncate_text "File: $(basename "$1")" $col_width)
    local t_out_file=$(truncate_text "File: $(basename "$output")" $col_width)
    local t_time=$(truncate_text "Time: $total_elapsed_formatted" $col_width)
    local t_saved=$(truncate_text "Reduction: ${percent_saved}%" $col_width)
    
    local t_in_size=$(truncate_text "Size: $input_size" $col_width)
    local t_out_size=$(truncate_text "Size: $output_size" $col_width)
    local t_speed=$(truncate_text "Speed: ${actual_speed}x" $col_width)
    local t_ratio=$(truncate_text "Ratio: ${ratio}x smaller" $col_width)

    printf "│ %-${col_width}s │ %-${col_width}s │ %-${col_width}s │ %-${col_width}s │\n" \
        "$t_in_file" "$t_out_file" "$t_time" "$t_saved"
    printf "│ %-${col_width}s │ %-${col_width}s │ %-${col_width}s │ %-${col_width}s │\n" \
        "$t_in_size" "$t_out_size" "$t_speed" "$t_ratio"
    
    printf "└%s┴%s┴%s┴%s┘\n" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))" \
        "$(printf '%0.s─' $(seq 1 $((col_width+2))))"
    
    echo ""
    echo "📍 Output: $(realpath "$output")"
}

# --- Helper for Codec Info ---
test_codec_support() {
    local codec="$1"
    if ffmpeg -encoders 2>/dev/null | grep -q "V..... $codec"; then
        return 0
    else
        return 1
    fi
}

codecs_check() {
    echo "🔍 HEVC Codec Availability:"
    echo "═════════════════════════"
    
    local codecs=("libx265" "hevc_videotoolbox" "hevc_vaapi" "hevc_nvenc" "hevc_qsv")
    
    for codec in "${codecs[@]}"; do
        if test_codec_support "$codec"; then
            echo "✅ $codec: Available"
        else
            echo "❌ $codec: Not available"
        fi
    done
    return 0
}

run_compress() {
    if [[ "$1" == "stats" ]]; then
        stats
    elif [[ "$1" == "reset" ]]; then
        reset
    elif [[ "$1" == "codecs" ]]; then
        codecs_check
    else
        compress "$@"
    fi
}
