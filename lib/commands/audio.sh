#!/bin/bash

# ==============================================================================
# Amir CLI - Audio Module (Smart & Integrated)
# Handles audio extraction, concatenation, and smart video creation.
# ==============================================================================

# Source shared media library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")"
if [[ -f "$LIB_DIR/media_lib.sh" ]]; then
    source "$LIB_DIR/media_lib.sh"
fi

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
        split)
            audio_split "$@"
            ;;
        concat)
            audio_concat "$@"
            ;;
        to-video)
            audio_to_video "$@"
            ;;
        youtube|yt)
            audio_youtube "$@"
            ;;
        *)
            echo "Usage: amir audio {extract|split|concat|to-video|youtube} [options]"
            echo "       amir audio <directory>  (Smart folder-to-video flow)"
            echo ""
            echo "Subcommands:"
            echo "  extract <video_file> [bitrate] [--split mb]  Extract MP3 from video"
            echo "  split <audio_file> <mb>         Split audio into ~N MB chunks"
            echo "  concat [files...] -o output     Join multiple audio files"
            echo "  to-video <audio> -i <image>     Create video from audio and image"
            echo "  youtube <url> [format] [bitrate] [--split mb]  Download audio from YouTube"
            echo "    Formats: mp3 (default), wav, ogg"
            return 1
            ;;
    esac
}

audio_split() {
    local INPUT="$1"
    local split_mb="$2"

    if [[ -z "$INPUT" || ! -f "$INPUT" ]]; then
        log_error "File not found: $INPUT" >&2
        echo "Usage: amir audio split <audio_file> <mb>" >&2
        return 1
    fi
    if [[ -z "$split_mb" || ! "$split_mb" =~ ^[0-9]+$ || "$split_mb" -le 0 ]]; then
        log_error "Split size must be a positive integer in MB." >&2
        echo "Usage: amir audio split <audio_file> <mb>" >&2
        return 1
    fi

    split_media_approx_by_size "$INPUT" "$split_mb"
}

audio_extract() {
    local INPUT="$1"
    shift
    if [[ -z "$INPUT" || ! -f "$INPUT" ]]; then
        log_error "File not found: $INPUT" >&2
        return 1
    fi
    
    # Source Config
    if [[ -f "$LIB_DIR/config.sh" ]]; then source "$LIB_DIR/config.sh"; else get_config() { echo "$3"; }; fi
    local default_kbps=$(get_config "mp3" "bitrate" "320")
    local kbps="$default_kbps"
    local split_mb="0"

    # Backward compatible positional bitrate: amir audio extract file.mp4 192
    if [[ -n "${1:-}" && "${1:-}" =~ ^[0-9]+$ ]]; then
        kbps="$1"
        shift
    fi

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --split)
                split_mb="$2"
                shift 2
                ;;
            *)
                log_error "Unknown option for extract: $1" >&2
                echo "Usage: amir audio extract <video_file> [bitrate] [--split <mb>]" >&2
                return 1
                ;;
        esac
    done

    if [[ "$split_mb" != "0" && ( ! "$split_mb" =~ ^[0-9]+$ || "$split_mb" -le 0 ) ]]; then
        log_error "Split size must be a positive integer in MB." >&2
        echo "Usage: amir audio extract <video_file> [bitrate] [--split <mb>]" >&2
        return 1
    fi
    
    local OUTPUT="${INPUT%.*}.mp3"
    
    log_info "🎧 Extracting Audio at ${kbps}kbps: $(basename "$INPUT") ..." >&2
    local FFMPEG_PATH=$(get_ffmpeg_path)
    local duration_seconds=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null | cut -d. -f1)
    
    run_ffmpeg_with_progress "$duration_seconds" \
        "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y -i "$INPUT" -vn -c:a libmp3lame -b:a "${kbps}k" "$OUTPUT"
    
    if [[ $? -eq 0 ]]; then
        log_success "Created: $OUTPUT" >&2
        echo "$OUTPUT"
        if [[ "$split_mb" =~ ^[0-9]+$ && "$split_mb" -gt 0 ]]; then
            echo ""
            split_media_approx_by_size "$OUTPUT" "$split_mb"
        fi
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

    local LIST_FILE=$(mktemp "$(amir_preferred_temp_dir "$PWD")/audio_concat_XXXXXX.txt")
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
    run_ffmpeg_with_progress "" \
        "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y -f concat -safe 0 -i "$LIST_FILE" -vn -c:a libmp3lame -b:a 192k "$OUTPUT"
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

    local duration_seconds=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AUDIO" 2>/dev/null | cut -d. -f1)
    
    local FFMPEG_PATH=$(get_ffmpeg_path)
    if $WAVEFORM; then
        log_info "Creating video with dynamic waveform: $OUTPUT ..." >&2
        run_ffmpeg_with_progress "$duration_seconds" \
            "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
            -loop 1 -i "$IMAGE" -i "$AUDIO" \
            -filter_complex "[1:a]showwaves=s=1280x200:mode=line:colors=cyan[v_wave];[0:v][v_wave]overlay=0:H-h[outv]" \
            -map "[outv]" -map 1:a -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 192k -shortest "$OUTPUT"
    else
        log_info "Creating static video: $OUTPUT ..." >&2
        run_ffmpeg_with_progress "$duration_seconds" \
            "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
            -loop 1 -i "$IMAGE" -i "$AUDIO" -c:v libx264 -tune stillimage -preset medium -crf 23 -c:a copy -shortest "$OUTPUT"
    fi
    local EXIT_CODE=$?

    if [[ $EXIT_CODE -eq 0 ]]; then
        log_success "Video creation complete." >&2
        echo "$OUTPUT"
    else
        log_error "FFmpeg failed to create video." >&2
        return 1
    fi
}

audio_youtube() {
    local URL="$1"
    shift
    local OUT_FORMAT="mp3"
    local TARGET_BITRATE="128"
    local split_mb="0"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            mp3|wav|ogg)
                OUT_FORMAT="$1"
                shift
                ;;
            --split)
                split_mb="$2"
                shift 2
                ;;
            *)
                if [[ "$1" =~ ^[0-9]+$ ]]; then
                    TARGET_BITRATE="$1"
                    shift
                else
                    log_error "Unknown option for youtube: $1" >&2
                    echo "Usage: amir audio youtube <url> [format] [bitrate] [--split <mb>]" >&2
                    echo "Formats: mp3 (default), wav, ogg" >&2
                    return 1
                fi
                ;;
        esac
    done

    if [[ -z "$URL" ]]; then
        log_error "YouTube URL is required." >&2
        echo "Usage: amir audio youtube <url> [format] [bitrate] [--split <mb>]" >&2
        echo "Formats: mp3 (default), wav, ogg" >&2
        return 1
    fi

    if [[ "$split_mb" != "0" && ( ! "$split_mb" =~ ^[0-9]+$ || "$split_mb" -le 0 ) ]]; then
        log_error "Split size must be a positive integer in MB." >&2
        echo "Usage: amir audio youtube <url> [format] [bitrate] [--split <mb>]" >&2
        return 1
    fi

    if ! command -v yt-dlp &>/dev/null; then
        log_error "yt-dlp is not installed. Install with: brew install yt-dlp" >&2
        return 1
    fi

    local FFMPEG_PATH=$(get_ffmpeg_path)

    # ── Step 1: Fetch metadata only (no download) ─────────────────────────────
    log_info "🔍 Fetching stream list from YouTube (no download yet)..." >&2
    local JSON
    JSON=$(yt-dlp -j "$URL" 2>/dev/null)
    if [[ -z "$JSON" ]]; then
        log_error "Could not fetch video metadata. Check the URL or your connection." >&2
        return 1
    fi

    # ── Step 2: Pick the best audio stream closest to target bitrate ──────────
    # Write selector to a temp file (heredoc + pipe conflict in zsh if using stdin)
    local PY_SEL
    PY_SEL=$(mktemp "$(amir_preferred_temp_dir "$PWD")/amir_ytsel.XXXXXX.py")
    cat > "$PY_SEL" << 'PYEOF'
import json, sys

data   = json.loads(sys.argv[1])
target = int(sys.argv[2])
title  = data.get('title', 'audio').replace('/', '_').replace('\x00', '')

formats = data.get('formats', [])
# audio-only streams with a known bitrate
audio = [
    f for f in formats
    if f.get('vcodec', 'none') == 'none'
    and f.get('acodec', 'none') not in ('none', None)
    and f.get('abr')
]

if not audio:
    # fallback: any stream that has audio
    audio = [f for f in formats if f.get('acodec', 'none') not in ('none', None) and f.get('abr')]

if not audio:
    print("ERROR:no audio streams found")
    sys.exit(1)

# Pick the stream closest to target bitrate.
# Prefer m4a/aac over webm/opus for wider compatibility.
def score(f):
    diff = abs(f['abr'] - target)
    fmt_bonus = 0 if f.get('ext', '') in ('m4a', 'aac') else 1  # prefer m4a
    return (diff, fmt_bonus)

best       = min(audio, key=score)
actual_abr = int(best.get('abr', 0))
# Never upscale: if source abr > target, ffmpeg will re-encode down to target.
# If source abr <= target, keep source abr (don't inflate).
encode_abr = min(actual_abr, target)

print(f"{best['format_id']}|{actual_abr}|{encode_abr}|{best.get('ext','m4a')}|{title}")
PYEOF

    local SELECTION
    SELECTION=$(python3 "$PY_SEL" "$JSON" "$TARGET_BITRATE")
    rm -f "$PY_SEL"

    if [[ "$SELECTION" == ERROR:* ]]; then
        log_error "${SELECTION#ERROR:}" >&2
        return 1
    fi

    local FMT_ID    ; FMT_ID=$(echo    "$SELECTION" | cut -d'|' -f1)
    local SRC_ABR   ; SRC_ABR=$(echo   "$SELECTION" | cut -d'|' -f2)
    local ENC_ABR   ; ENC_ABR=$(echo   "$SELECTION" | cut -d'|' -f3)
    local SRC_EXT   ; SRC_EXT=$(echo   "$SELECTION" | cut -d'|' -f4)
    local TITLE     ; TITLE=$(echo     "$SELECTION" | cut -d'|' -f5)

    log_info "📊 Source stream: format_id=${FMT_ID}  abr=${SRC_ABR}kbps  ext=${SRC_EXT}" >&2
    log_info "🎯 Target: ${TARGET_BITRATE}kbps → will encode at ${ENC_ABR}kbps (no upscale)" >&2

    local RAW_FILE="${TITLE}.${SRC_EXT}"

    # ── Step 3: Download only the selected stream ─────────────────────────────
    log_info "⬇️  Downloading stream ${FMT_ID} (~${SRC_ABR}kbps ${SRC_EXT})..." >&2
    yt-dlp --continue --newline -f "$FMT_ID" -o "$RAW_FILE" "$URL" \
        2> >(grep --line-buffered -E '^\[download\]|^ERROR|^WARNING:' >&2)
    if [[ $? -ne 0 || ! -f "$RAW_FILE" ]]; then
        log_error "Download failed." >&2
        return 1
    fi

    # ── Step 4: Local conversion with ffmpeg ──────────────────────────────────
    local OUTPUT_FILE
    local duration_seconds=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$RAW_FILE" 2>/dev/null | cut -d. -f1)
    
    case "$OUT_FORMAT" in
        mp3)
            OUTPUT_FILE="${TITLE}_${ENC_ABR}kbps.mp3"
            log_info "🔄 Converting to MP3 at ${ENC_ABR}kbps..." >&2
            run_ffmpeg_with_progress "$duration_seconds" \
                "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
                -i "$RAW_FILE" -vn -c:a libmp3lame -b:a "${ENC_ABR}k" "$OUTPUT_FILE"
            ;;
        wav)
            OUTPUT_FILE="${TITLE}_wav.wav"
            log_info "🔄 Converting to WAV..." >&2
            run_ffmpeg_with_progress "$duration_seconds" \
                "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
                -i "$RAW_FILE" -vn "$OUTPUT_FILE"
            ;;
        ogg)
            OUTPUT_FILE="${TITLE}_${ENC_ABR}kbps.ogg"
            log_info "🔄 Converting to OGG at ${ENC_ABR}kbps..." >&2
            run_ffmpeg_with_progress "$duration_seconds" \
                "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
                -i "$RAW_FILE" -vn -c:a libvorbis -b:a "${ENC_ABR}k" "$OUTPUT_FILE"
            ;;
        *)
            log_error "Unsupported format: $OUT_FORMAT. Use: mp3, wav, ogg" >&2
            rm -f "$RAW_FILE"
            return 1
            ;;
    esac
    
    local EXIT_CODE=$?

    rm -f "$RAW_FILE"   # remove the raw downloaded stream

    if [[ $EXIT_CODE -eq 0 ]]; then
        log_success "✅ Done: $OUTPUT_FILE" >&2
        echo "$OUTPUT_FILE"
        if [[ "$split_mb" =~ ^[0-9]+$ && "$split_mb" -gt 0 ]]; then
            echo ""
            split_media_approx_by_size "$OUTPUT_FILE" "$split_mb"
        fi
    else
        log_error "ffmpeg conversion failed." >&2
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
    "${AMIR_ROOT:-$(dirname "$(dirname "$LIB_DIR")")}/amir" subtitle "$FINAL_VIDEO" -t fa -r >&2
    
    log_success "✨ Process complete! Final video: $FINAL_VIDEO" >&2
    echo "$FINAL_VIDEO"
}

# Helper to get absolute path
abspath() {
    python3 -c "import os, sys; print(os.path.abspath(sys.argv[1]))" "$1"
}
