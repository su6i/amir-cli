#!/bin/bash

# ==============================================================================
# Amir CLI - Audio Module (Smart & Integrated)
# Handles audio extraction, concatenation, and smart video creation.
# ==============================================================================

run_audio() {
    local SUBCOMMAND="$1"
    
    # Smart Mode Detection: If first arg is a directory
    if [[ -d "$SUBCOMMAND" ]]; then
        smart_audio_flow "$@"
        return $?
    fi

    shift

    case "$SUBCOMMAND" in
        extract|mp3)
            audio_extract "$@"
            ;;
        concat)
            audio_concat "$@"
            ;;
        to-video)
            audio_to_video "$@"
            ;;
        *)
            echo "Usage: amir audio {extract|concat|to-video} [options]"
            echo "       amir audio <directory>  (Smart folder-to-video flow)"
            echo ""
            echo "Subcommands:"
            echo "  extract <video_file> [bitrate]  Extract MP3 from video"
            echo "  extract <video_file> [bitrate]  Extract MP3 from video"
            echo "  concat [files...] -o output     Join multiple audio files"
            echo "  to-video <audio> -i <image>     Create video from audio and image"
            return 1
            ;;
    esac
}

audio_extract() {
    local INPUT="$1"
    if [[ -z "$INPUT" || ! -f "$INPUT" ]]; then
        log_error "File not found: $INPUT" >&2
        return 1
    fi
    
    # Source Config
    if [[ -f "$LIB_DIR/config.sh" ]]; then source "$LIB_DIR/config.sh"; else get_config() { echo "$3"; }; fi
    local default_kbps=$(get_config "mp3" "bitrate" "320")
    local kbps=${2:-$default_kbps}
    
    local OUTPUT="${INPUT%.*}.mp3"
    
    log_info "🎧 Extracting Audio at ${kbps}kbps: $(basename "$INPUT") ..." >&2
    local FFMPEG_PATH=$(get_ffmpeg_path)
    "$FFMPEG_PATH" -hide_banner -loglevel error -stats -y -i "$INPUT" -vn -c:a libmp3lame -b:a "${kbps}k" "$OUTPUT"
    
    if [[ $? -eq 0 ]]; then
        log_success "Created: $OUTPUT" >&2
        echo "$OUTPUT"
    else
        log_error "Extraction failed." >&2
        return 1
    fi
}

audio_concat() {
    local OUTPUT=""
    local INPUT_FILES=()
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -o|--output) OUTPUT="$2"; shift 2 ;;
            *) INPUT_FILES+=("$1"); shift ;;
        esac
    done

    if [[ ${#INPUT_FILES[@]} -eq 0 ]]; then
        log_error "No input files specified." >&2
        return 1
    fi

    if [[ -z "$OUTPUT" ]]; then
        local first_file=$(basename "${INPUT_FILES[0]%.*}")
        OUTPUT="${first_file}_merged.mp3"
    fi

    local LIST_FILE=$(mktemp)
    log_info "Preparing to concatenate ${#INPUT_FILES[@]} files into $OUTPUT:" >&2
    
    for f in "${INPUT_FILES[@]}"; do
        if [[ -f "$f" ]]; then
            echo "   🔗 $(basename "$f")" >&2
            local abs_path=$(abspath "$f")
            echo "file '$abs_path'" >> "$LIST_FILE"
        fi
    done

    if [[ -f "$OUTPUT" && -s "$OUTPUT" ]]; then
        log_info "Fast-track: Output already exists: $OUTPUT (skipping merge)" >&2
        echo "$OUTPUT"
        return 0
    fi

    local FFMPEG_PATH=$(get_ffmpeg_path)
    # Re-encoding (vn) is safer than copy because input files might have images/metadata streams 
    # that cause "Exactly one MP3 audio stream is required" error.
    "$FFMPEG_PATH" -hide_banner -loglevel error -stats -y -f concat -safe 0 -i "$LIST_FILE" -vn -c:a libmp3lame -b:a 192k "$OUTPUT"
    local EXIT_CODE=$?
    rm "$LIST_FILE"

    if [[ $EXIT_CODE -eq 0 ]]; then
        log_success "Concatenation complete." >&2
        echo "$OUTPUT"
    else
        log_error "FFmpeg failed to merge audio files." >&2
        return 1
    fi
}

audio_to_video() {
    local AUDIO=""
    local IMAGE=""
    local OUTPUT=""
    local WAVEFORM=false
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -i|--image) IMAGE="$2"; shift 2 ;;
            -o|--output) OUTPUT="$2"; shift 2 ;;
            --waveform) WAVEFORM=true; shift ;;
            *) if [[ -z "$AUDIO" ]]; then AUDIO="$1"; fi; shift ;;
        esac
    done

    if [[ -z "$AUDIO" || ! -f "$AUDIO" ]]; then
        log_error "Audio file not found: '$AUDIO'" >&2
        return 1
    fi

    if [[ -z "$IMAGE" || ! -f "$IMAGE" ]]; then
        log_info "Generating/Fetching background image..." >&2
        IMAGE="${AUDIO%.*}_bg.jpg"
        local audio_name=$(basename "${AUDIO%.*}")
        uv run --with requests --with Pillow "$LIB_DIR/python/generate_image.py" "$audio_name" "$IMAGE" >&2
        
        if [[ ! -f "$IMAGE" ]]; then
            log_error "Failed to obtain an image. Creating a simple color one..." >&2
            magick -size 1280x720 xc:navy "$IMAGE" >&2
        fi
    fi

    if [[ -z "$OUTPUT" ]]; then
        OUTPUT="${AUDIO%.*}.mp4"
    fi

    if [[ -f "$OUTPUT" && -s "$OUTPUT" ]]; then
        log_info "Fast-track: Video already exists: $OUTPUT (skipping creation)" >&2
        echo "$OUTPUT"
        return 0
    fi

    local FFMPEG_PATH=$(get_ffmpeg_path)
    if $WAVEFORM; then
        log_info "Creating video with dynamic waveform: $OUTPUT ..." >&2
        "$FFMPEG_PATH" -hide_banner -loglevel error -stats -y \
            -loop 1 -i "$IMAGE" -i "$AUDIO" \
            -filter_complex "[1:a]showwaves=s=1280x200:mode=line:colors=cyan[v_wave];[0:v][v_wave]overlay=0:H-h[outv]" \
            -map "[outv]" -map 1:a -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 192k -shortest "$OUTPUT"
    else
        log_info "Creating static video: $OUTPUT ..." >&2
        "$FFMPEG_PATH" -hide_banner -loglevel error -stats -y \
            -loop 1 -i "$IMAGE" -i "$AUDIO" -c:v libx264 -tune stillimage -preset medium -crf 23 -c:a copy -shortest "$OUTPUT"
    fi

    if [[ $? -eq 0 ]]; then
        log_success "Video creation complete." >&2
        echo "$OUTPUT"
    else
        log_error "FFmpeg failed to create video." >&2
        return 1
    fi
}

smart_audio_flow() {
    local DIR="$1"
    log_info "🚀 Starting Smart Audio Flow for directory: $DIR" >&2
    
    local FILES=($(find "$DIR" -maxdepth 1 \( -name "*.mp3" -o -name "*.wav" \) | sort -V))
    if [[ ${#FILES[@]} -eq 0 ]]; then
        log_error "No audio files found in $DIR" >&2
        return 1
    fi
    
    local MERGED_AUDIO=$(audio_concat "${FILES[@]}")
    [[ -z "$MERGED_AUDIO" ]] && return 1
    
    local FINAL_VIDEO=$(audio_to_video "$MERGED_AUDIO" --waveform)
    [[ -z "$FINAL_VIDEO" ]] && return 1
    
    log_info "🤖 Automatically calling subtitle module (with rendering)..." >&2
    # Added -r to render/burn subtitles into the video
    "$SCRIPT_DIR/amir" subtitle "$FINAL_VIDEO" -t fa -r >&2
    
    log_success "✨ Process complete! Final video: $FINAL_VIDEO" >&2
    echo "$FINAL_VIDEO"
}

# Helper to get absolute path
abspath() {
    python3 -c "import os, sys; print(os.path.abspath(sys.argv[1]))" "$1"
}
