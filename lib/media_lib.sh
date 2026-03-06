#!/bin/bash

# ==============================================================================
# Amir CLI — Shared Media Library
# Reusable functions for all audio/video processing commands.
# Sourced by: video.sh, audio.sh, and any future media module.
# ==============================================================================

# ==============================================================================
# 1. ENCODER DETECTION (GPU / CPU Toggle)
# ==============================================================================

# Detect the best encoder based on mode and platform.
# Usage: detect_encoder [--gpu|--cpu]
# Returns: Sets global variables: MEDIA_ENCODER, MEDIA_TAG_OPT, MEDIA_ENCODER_DISPLAY, MEDIA_PLATFORM
detect_encoder() {
    local mode="${1:---gpu}"  # Default to GPU

    MEDIA_ENCODER="libx265"
    MEDIA_TAG_OPT="-tag:v hvc1"
    MEDIA_ENCODER_DISPLAY="CPU (x265)"
    MEDIA_PLATFORM="cpu"

    if [[ "$mode" == "--cpu" ]]; then
        # Explicit CPU mode — keep defaults
        return 0
    fi

    # GPU mode: auto-detect hardware encoder
    if ffmpeg -encoders 2>/dev/null | grep -q "hevc_videotoolbox"; then
        MEDIA_ENCODER="hevc_videotoolbox"
        MEDIA_TAG_OPT="-tag:v hvc1 -allow_sw 1"
        MEDIA_ENCODER_DISPLAY="Apple Silicon"
        MEDIA_PLATFORM="apple_silicon"
    elif ffmpeg -encoders 2>/dev/null | grep -q "hevc_nvenc"; then
        MEDIA_ENCODER="hevc_nvenc"
        MEDIA_TAG_OPT=""
        MEDIA_ENCODER_DISPLAY="NVIDIA NVENC"
        MEDIA_PLATFORM="nvidia"
    elif ffmpeg -encoders 2>/dev/null | grep -q "hevc_amf"; then
        MEDIA_ENCODER="hevc_amf"
        MEDIA_TAG_OPT=""
        MEDIA_ENCODER_DISPLAY="AMD AMF"
        MEDIA_PLATFORM="amd"
    elif ffmpeg -encoders 2>/dev/null | grep -q "hevc_qsv"; then
        MEDIA_ENCODER="hevc_qsv"
        MEDIA_TAG_OPT=""
        MEDIA_ENCODER_DISPLAY="Intel QSV"
        MEDIA_PLATFORM="intel"
    fi
    # If no HW encoder found, falls back to CPU defaults set above
}

# ==============================================================================
# 2. MEDIA PROBING (Duration, Bitrate, Info)
# ==============================================================================

# Get the total duration of a media file in seconds (integer).
# Usage: get_media_duration "file.mp4"
# Returns: integer seconds (e.g., 5845)
get_media_duration() {
    local file="$1"
    local dur=$(ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$file" 2>/dev/null)
    echo "${dur%.*}"  # Truncate to integer
}

# Get the bitrate of a media file in bits/s (integer).
# Tries container bitrate first, then falls back to stream bitrate.
# Usage: get_media_bitrate "file.mp4"
# Returns: integer bits/s (e.g., 709000)
get_media_bitrate() {
    local file="$1"
    local bitrate=""
    
    # 1. Container bitrate (usually more accurate for file size estimation)
    bitrate=$(ffprobe -v error -show_entries format=bit_rate \
        -of default=noprint_wrappers=1:nokey=1 "$file" 2>/dev/null)
    
    # 2. Fallback to video stream bitrate
    if [[ -z "$bitrate" || ! "$bitrate" =~ ^[0-9]+$ ]]; then
        bitrate=$(ffprobe -v error -select_streams v:0 \
            -show_entries stream=bit_rate \
            -of default=noprint_wrappers=1:nokey=1 "$file" 2>/dev/null)
    fi
    
    # 3. Final fallback
    if [[ -z "$bitrate" || ! "$bitrate" =~ ^[0-9]+$ ]]; then
        echo ""
        return 1
    fi
    
    echo "$bitrate"
}

# Get comprehensive media info.
# Usage: get_media_info "file.mp4"
# Sets globals: MEDIA_WIDTH, MEDIA_HEIGHT, MEDIA_ROTATION, MEDIA_IS_PORTRAIT,
#               MEDIA_CODEC, MEDIA_DURATION, MEDIA_DURATION_FMT, MEDIA_BITRATE
get_media_info() {
    local file="$1"
    
    # Resolution + Rotation
    local ff_output=$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=width,height,codec_name:stream_side_data=rotation \
        -of csv=s=x:p=0 "$file" 2>/dev/null)
    
    MEDIA_WIDTH=$(echo "$ff_output" | cut -d'x' -f1)
    MEDIA_HEIGHT=$(echo "$ff_output" | cut -d'x' -f2)
    MEDIA_CODEC=$(echo "$ff_output" | cut -d'x' -f3)
    MEDIA_ROTATION=$(echo "$ff_output" | cut -d'x' -f4)
    
    # Clean rotation
    MEDIA_ROTATION=${MEDIA_ROTATION#-}
    [[ -z "$MEDIA_ROTATION" ]] && MEDIA_ROTATION=0
    
    # Handle rotated videos (90°/270°: swap W/H)
    if [[ "$MEDIA_ROTATION" == "90" || "$MEDIA_ROTATION" == "270" ]]; then
        local tmp=$MEDIA_WIDTH
        MEDIA_WIDTH=$MEDIA_HEIGHT
        MEDIA_HEIGHT=$tmp
    fi
    
    # Portrait detection
    MEDIA_IS_PORTRAIT=0
    if [[ -n "$MEDIA_HEIGHT" && -n "$MEDIA_WIDTH" && "$MEDIA_HEIGHT" -gt "$MEDIA_WIDTH" ]]; then
        MEDIA_IS_PORTRAIT=1
    fi
    
    # Duration
    MEDIA_DURATION=$(get_media_duration "$file")
    MEDIA_DURATION_FMT=$(format_duration "$MEDIA_DURATION")
    
    # Bitrate
    MEDIA_BITRATE=$(get_media_bitrate "$file")
}

# ==============================================================================
# 3. SMART BITRATE CALCULATION
# ==============================================================================

# Calculate target bitrate ensuring output won't exceed input size.
# Usage: calculate_target_bitrate "$input_bitrate" "$quality" "$encoder"
# Returns: bitrate value (e.g., "350000")
calculate_target_bitrate() {
    local input_bitrate="$1"
    local quality="$2"
    local encoder="$3"
    
    if [[ -z "$input_bitrate" || ! "$input_bitrate" =~ ^[0-9]+$ ]]; then
        echo "2000000"  # 2Mbps fallback
        return
    fi
    
    local target=""
    
    if [[ "$encoder" == "hevc_videotoolbox" || "$encoder" == "h264_videotoolbox" ]]; then
        # VideoToolbox: scale by quality percentage
        target=$(echo "$input_bitrate * $quality / 100" | bc)
    elif [[ "$encoder" == "libx265" ]]; then
        # Software HEVC: ~80% of input (HEVC is more efficient)
        target=$(echo "$input_bitrate * 80 / 100" | bc)
    else
        # Other HW encoders: scale by quality
        target=$(echo "$input_bitrate * $quality / 100" | bc)
    fi
    
    # Safety floor: never go below 100kbps
    if [[ $(echo "$target < 100000" | bc) -eq 1 ]]; then
        target=100000
    fi
    
    echo "$target"
}

# Build encoder quality options array.
# Usage: build_encoder_opts "$encoder" "$quality" "$input_bitrate"
# Sets: MEDIA_Q_OPT (array), MEDIA_BITRATE_FLAGS (array)
build_encoder_opts() {
    local encoder="$1"
    local quality="$2"
    local input_bitrate="$3"
    
    MEDIA_Q_OPT=()
    MEDIA_BITRATE_FLAGS=()
    
    if [[ "$encoder" == "hevc_videotoolbox" || "$encoder" == "h264_videotoolbox" ]]; then
        # VideoToolbox: requires -b:v (does NOT support -q:v)
        local target_br=$(calculate_target_bitrate "$input_bitrate" "$quality" "$encoder")
        MEDIA_Q_OPT=("-b:v" "$target_br")
    elif [[ "$encoder" == "libx265" ]]; then
        # Software: use -q:v + maxrate/bufsize cap
        MEDIA_Q_OPT=("-q:v" "$quality")
        if [[ -n "$input_bitrate" && "$input_bitrate" =~ ^[0-9]+$ ]]; then
            local max_br=$(echo "$input_bitrate * 115 / 100" | bc)
            local buf_sz=$((max_br * 2))
            MEDIA_BITRATE_FLAGS=("-maxrate" "$max_br" "-bufsize" "$buf_sz")
        fi
    else
        # Other HW encoders: try -q:v
        MEDIA_Q_OPT=("-q:v" "$quality")
    fi
}

# ==============================================================================
# 4. OUTPUT SIZE VALIDATION
# ==============================================================================

# Check that output file is not larger than input.
# Usage: validate_output_size "$input_file" "$output_file" "$encoder"
# Returns: 0 if OK, 1 if output is bloated (prints warning)
validate_output_size() {
    local input_file="$1"
    local output_file="$2"
    local encoder="${3:-}"
    
    if [[ ! -f "$output_file" ]]; then
        return 1
    fi
    
    local in_bytes=$(stat -L -f%z "$input_file" 2>/dev/null || stat -L -c%s "$input_file" 2>/dev/null)
    local out_bytes=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null)
    
    if [[ -n "$in_bytes" && -n "$out_bytes" && "$out_bytes" -gt "$in_bytes" ]]; then
        local bloat_pct=$(( (out_bytes - in_bytes) * 100 / in_bytes ))
        echo ""
        echo -e "\033[0;33m⚠️  Output is ${bloat_pct}% LARGER than input!\033[0m"
        echo -e "\033[0;33m    Input:  $(du -hL "$input_file" 2>/dev/null | cut -f1)\033[0m"
        echo -e "\033[0;33m    Output: $(du -h "$output_file" 2>/dev/null | cut -f1)\033[0m"
        
        if [[ "$encoder" == *"videotoolbox"* || "$encoder" == *"nvenc"* ]]; then
            echo -e "\033[0;36m💡 Tip: Try --cpu for better compression ratio (slower but smaller file)\033[0m"
        fi
        return 1
    fi
    
    return 0
}

# ==============================================================================
# 5. DURATION FORMATTING
# ==============================================================================

# Format seconds as HH:MM:SS.
# Usage: format_duration 5845
# Returns: "01:37:25"
format_duration() {
    local secs="${1:-0}"
    [[ -z "$secs" || "$secs" == "N/A" ]] && secs=0
    printf '%02d:%02d:%02d' $((secs/3600)) $((secs%3600/60)) $((secs%60))
}

# ==============================================================================
# 6. HARDWARE DETECTION
# ==============================================================================

# Detect CPU and GPU info for display.
# Usage: detect_hardware
# Sets: HW_CPU_INFO, HW_GPU_INFO
detect_hardware() {
    HW_CPU_INFO="Unknown"
    HW_GPU_INFO="Unknown"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        HW_CPU_INFO=$(sysctl -n machdep.cpu.brand_string 2>/dev/null)
        HW_GPU_INFO="Apple Silicon GPU"
        [[ "$HW_CPU_INFO" == *"Intel"* ]] && HW_GPU_INFO="Intel GPU"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        HW_CPU_INFO=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)
        HW_GPU_INFO=$(lspci | grep -i vga | cut -d: -f3 | xargs 2>/dev/null || echo "Linux GPU")
    fi
}

# ==============================================================================
# 7. UNICODE TABLE RENDERER
# ==============================================================================

# Print a formatted Unicode table with N columns.
# Usage: print_media_table $col_width "Header1|Header2|..." "Row1Col1|Row1Col2|..." ...
#
# Example:
#   print_media_table 20 \
#       "📂 INPUT|🖥️ HARDWARE|🎯 SETTINGS" \
#       "File: in.mp4|CPU: M4|Res: 480p" \
#       "Size: 495M|GPU: Apple|Q: 60"
print_media_table() {
    local col_width="$1"
    shift
    
    # First argument is the header row
    local header_row="$1"
    shift
    
    # Count columns from the header
    local ncols=$(echo "$header_row" | awk -F'|' '{print NF}')
    
    # ── Top border ──
    local border_top="┌"
    local border_mid="├"
    local border_bot="└"
    local separator=$(printf '%0.s─' $(seq 1 $((col_width + 2))))
    
    for ((c=1; c<=ncols; c++)); do
        border_top+="${separator}"
        border_mid+="${separator}"
        border_bot+="${separator}"
        if [[ $c -lt $ncols ]]; then
            border_top+="┬"
            border_mid+="┼"
            border_bot+="┴"
        fi
    done
    border_top+="┐"
    border_mid+="┤"
    border_bot+="┘"
    
    echo "$border_top"
    
    # ── Header row ──
    local header_line="│"
    IFS='|' read -r -a hcols <<< "$header_row"
    for ((c=0; c<ncols; c++)); do
        local padded=$(pad_to_width "${hcols[$c]}" "$col_width")
        header_line+=" ${padded} │"
    done
    echo "$header_line"
    echo "$border_mid"
    
    # ── Data rows ──
    for row in "$@"; do
        local row_line="│"
        IFS='|' read -r -a rcols <<< "$row"
        for ((c=0; c<ncols; c++)); do
            local padded=$(pad_to_width "${rcols[$c]:-}" "$col_width")
            row_line+=" ${padded} │"
        done
        echo "$row_line"
    done
    
    echo "$border_bot"
}

# ==============================================================================
# 8. FFMPEG EXECUTION WITH PROGRESS
# ==============================================================================

# Run an ffmpeg command with automatic progress bar display.
# Usage: run_ffmpeg_with_progress "$duration_seconds" ffmpeg [args...]
# Returns: ffmpeg exit code (via $?)
run_ffmpeg_with_progress() {
    local duration="$1"
    shift
    
    local ffmpeg_error_log=$(mktemp)
    
    "$@" 2> >(tee "$ffmpeg_error_log" >&2) | ffmpeg_progress_bar "$duration"
    local exit_code=${PIPESTATUS[0]:-$?}
    
    printf "\r\033[K"
    
    if [[ $exit_code -ne 0 ]]; then
        echo "❌ FFmpeg failed! (exit code: $exit_code)"
        if [[ -f "$ffmpeg_error_log" ]]; then
            echo "── ffmpeg error ──"
            grep -i 'error\|invalid\|failed\|cannot' "$ffmpeg_error_log" | tail -20
        fi
    fi
    
    rm -f "$ffmpeg_error_log"
    return $exit_code
}
