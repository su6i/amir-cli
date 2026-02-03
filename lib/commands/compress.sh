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
    
    # Calculate target dimensions
    local target_w=$(( (target_h * 16 / 9 + 1) / 2 * 2 ))
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
    else 
        # Windows (Git Bash/WSL)
        cpu_info="Windows CPU" 
        gpu_info="Windows GPU"
    fi
    
    local quality_factor=${quality_factors[$quality]:-1.0}
    local speed_factor=${speed_factors[$quality]:-6}
    local sample_count=${sample_counts[$quality]:-0}
    
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
    local t_enc=$(pad_to_width "Encoder: VideoToolbox" $col_width)
    local t_audio=$(pad_to_width "Audio: AAC 44.1kHz" $col_width)

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
    
    # Windows/Linux fix for audio filters
    local audio_filter="aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
    
    # Execute ffmpeg
    if [[ "$OSTYPE" == "darwin"* ]]; then
        script -q /dev/null ffmpeg -hide_banner -loglevel error -stats -nostdin -y -i "$input_file" \
        -vf "fps=25,scale=${target_w}:${target_h}:force_original_aspect_ratio=decrease,pad=${target_w}:${target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1" \
        -c:v "$encoder" -q:v $quality $tag_opt \
        -af "$audio_filter" \
        -c:a aac -pix_fmt yuv420p -movflags +faststart "$output"
    else
        ffmpeg -hide_banner -loglevel error -stats -nostdin -y -i "$input_file" \
        -vf "fps=25,scale=${target_w}:${target_h}:force_original_aspect_ratio=decrease,pad=${target_w}:${target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1" \
        -c:v "$encoder" -q:v $quality $tag_opt \
        -af "$audio_filter" \
        -c:a aac -pix_fmt yuv420p -movflags +faststart "$output"
    fi
    
    if [[ ! -f "$output" ]]; then
        echo "❌ Compression failed!"
        return
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
    local t_saved=$(pad_to_width "Reduction: ${percent_saved}%" $col_width)
    
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

compress() {
    # If no arguments, show help
    if [[ $# -eq 0 ]]; then
        echo "Usage: amir compress <files|dirs...> [Resolution] [Quality]"
        echo "Example: amir compress Video1.mp4 Video2.mp4 720 60"
        echo "Batch:   amir compress ./Videos"
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
    local target_h=720
    local quality=60
    
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
                process_video "$file" "$target_h" "$quality"
            done
        fi
    done
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
