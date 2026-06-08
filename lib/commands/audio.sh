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
        convert)
            audio_convert "$@"
            ;;
        cut)
            audio_cut "$@"
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
        normalize)
            audio_normalize "$@"
            ;;
        fade)
            audio_fade "$@"
            ;;
        trim-silence)
            audio_trim_silence "$@"
            ;;
        transcribe)
            audio_transcribe "$@"
            ;;
        *)
            echo "Usage: amir audio {extract|convert|cut|normalize|fade|trim-silence|split|concat|to-video|youtube|transcribe} [options]"
            echo "       amir audio <directory>  (Smart folder-to-video flow)"
            echo ""
            echo "Subcommands:"
            echo "  extract <video_file> [bitrate] [--split mb]  Extract MP3 from video"
            echo "  convert <audio_file> [format]   Convert audio format (wav, mp3, ogg, m4a)"
            echo "  cut <audio_file> [-s start] [-e end]         Trim or delete segments"
            echo "         -s 00:01:00 -e 00:03:00               Keep 1m–3m"
            echo "         -d 00:01:00 00:03:00                  Delete 1m–3m, keep rest"
            echo "         -d 00:01:00 00:02:00 -d 00:05:00 00:06:00  Multi-delete"
            echo "         -x 00:01:00 00:03:00                  Extract named clip"
            echo "  normalize <audio_file> [--target -16] [--peak -1]  Loudness normalize (EBU R128)"
            echo "  fade <audio_file> [--in 2] [--out 3]         Fade in/out (seconds)"
            echo "  trim-silence <audio_file> [--threshold -40] [--pad 0.3]  Remove leading/trailing silence"
            echo "  split <audio_file> <mb>         Split audio into ~N MB chunks"
            echo "  concat [files...] -o output     Join multiple audio files"
            echo "  to-video <audio> -i <image>     Create video from audio and image"
            echo "  youtube <url> [format] [bitrate] [--split mb]  Download audio from YouTube"
            echo "    Formats: mp3 (default), wav, ogg"
            echo "  transcribe <audio_file> [--source fa|en|...] [subtitle-options]"
            echo "    Transcribe audio via Whisper — saves both .srt and .txt"
            return 1
            ;;
    esac
}

audio_transcribe() {
    local input="$1"
    shift

    if [[ -z "$input" ]]; then
        echo "Usage: amir audio transcribe <audio_file> [--source fa|en|...] [subtitle-options]"
        echo "  Transcribes audio via Whisper and saves both .srt and .txt"
        return 1
    fi

    if [[ ! -f "$input" ]]; then
        echo "❌ File not found: $input" >&2
        return 1
    fi

    # Run subtitle pipeline (generates SRT)
    amir subtitle "$input" "$@"
    local exit_code=$?
    [[ $exit_code -ne 0 ]] && return $exit_code

    # Find the most recently generated SRT for this file
    local base="${input%.*}"
    local srt_file
    srt_file=$(ls -t "${base}"_*.srt 2>/dev/null | head -1)

    if [[ -z "$srt_file" ]]; then
        echo "⚠️  SRT not found — skipping TXT generation"
        return 0
    fi

    # Strip sequence numbers, timestamps, HTML tags and blank lines → plain text
    local txt_file="${srt_file%.srt}.txt"
    grep -v '^[0-9][0-9]*$' "$srt_file" \
        | grep -v '^[0-9][0-9]:.*-->.*[0-9]$' \
        | grep -v '^$' \
        | sed 's/<[^>]*>//g' \
        > "$txt_file"
    echo "✅ TXT saved: $txt_file"
}

audio_cut() {
    local start_time=""
    local end_time=""
    local extract_mode=0
    local extract_start=""
    local extract_end=""
    local -a delete_starts=()
    local -a delete_ends=()
    local delete_mode=0
    local output_file=""
    local -a input_files=()
    local -a _opts=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -s|--start)   start_time="$2";  _opts+=("$1" "$2"); shift 2 ;;
            -e|--end|-t|--to) end_time="$2"; _opts+=("$1" "$2"); shift 2 ;;
            -x|--extract)
                extract_mode=1; extract_start="$2"; extract_end="$3"
                _opts+=("$1" "$2" "$3"); shift 3
                ;;
            -d|--delete)
                if [[ -n "${2:-}" && "${2:-}" != -* && -n "${3:-}" && "${3:-}" != -* ]]; then
                    delete_mode=1; delete_starts+=("$2"); delete_ends+=("$3")
                    _opts+=("$1" "$2" "$3"); shift 3
                else
                    delete_mode=1; _opts+=("$1"); shift 1
                fi
                ;;
            -o|--output) output_file="$2"; shift 2 ;;
            *)
                if [[ -f "$1" ]]; then
                    input_files+=("$1"); shift
                else
                    echo "❌ Unknown argument: $1" >&2
                    echo "Usage: amir audio cut <file(s)> [-s start] [-e end] [-d start end ...] [-x start end] [-o output]" >&2
                    return 1
                fi
                ;;
        esac
    done

    if [[ ${#input_files[@]} -eq 0 ]]; then
        echo "❌ Error: No input file specified." >&2
        echo "" >&2
        echo "Usage: amir audio cut <file(s)> [options]" >&2
        echo "  -s 00:01:00 -e 00:03:00                    Keep 1m–3m (stream copy, fast)" >&2
        echo "  -d 00:01:00 00:03:00                       Delete 1m–3m, keep rest" >&2
        echo "  -d 00:01:00 00:02:00 -d 00:05:00 00:06:00  Multi-delete in one pass" >&2
        echo "  -x 00:01:00 00:03:00                       Extract named clip" >&2
        echo "  -o output.mp3                              Custom output filename" >&2
        return 1
    fi

    # ── Batch dispatch ─────────────────────────────────────────────────────────
    if [[ ${#input_files[@]} -gt 1 ]]; then
        [[ -n "$output_file" ]] && echo "⚠️  Batch mode: -o ignored, outputs auto-named." >&2
        local _ok=0 _fail=0 _total=${#input_files[@]}
        for _f in "${input_files[@]}"; do
            echo ""; echo "── [$(( _ok + _fail + 1 ))/${_total}] $(basename "$_f") ──"
            if audio_cut "$_f" "${_opts[@]}"; then (( _ok += 1 )); else (( _fail += 1 )); fi
        done
        echo ""; echo "Batch cut: ${_ok}✅  ${_fail}❌  (${_total} files)"
        return $(( _fail > 0 ? 1 : 0 ))
    fi

    local input_file="${input_files[0]}"

    # -s/-e --delete shorthand: treat start/end as the delete range
    if [[ $delete_mode -eq 1 && ${#delete_starts[@]} -eq 0 ]]; then
        if [[ -n "$start_time" && -n "$end_time" ]]; then
            delete_starts+=("$start_time")
            delete_ends+=("$end_time")
            start_time=""; end_time=""
        else
            echo "❌ --delete requires a range: use -d START END  or  -s START -e END --delete" >&2
            return 1
        fi
    fi

    if [[ $extract_mode -eq 1 ]]; then
        if [[ -z "$extract_start" || -z "$extract_end" ]]; then
            echo "❌ --extract requires both start and end times." >&2
            return 1
        fi
        start_time="$extract_start"
        end_time="$extract_end"
    fi

    # Auto-generate output filename
    local ext="${input_file##*.}"
    if [[ -z "$output_file" ]]; then
        local base="${input_file%.*}"
        _act() { local v="$1"; v="${v//:/-}"; v="${v//./-}"; v="${v// /_}"; printf '%s' "$v"; }
        if [[ $extract_mode -eq 1 ]]; then
            output_file="${base}_cut_$(_act "$extract_start")_$(_act "$extract_end").${ext}"
        else
            output_file="${base}_cut.${ext}"
        fi
    fi

    local FFMPEG_PATH
    FFMPEG_PATH=$(get_ffmpeg_path)

    # Convert HH:MM:SS or MM:SS or SS to fractional seconds
    _acut_to_sec() {
        awk -v t="$1" 'BEGIN {
            n = split(t, a, ":")
            if (n == 1) { printf "%.6f", a[1]+0 }
            else if (n == 2) { printf "%.6f", a[1]*60+a[2] }
            else { printf "%.6f", a[1]*3600+a[2]*60+a[3] }
        }'
    }

    # Return ffmpeg audio encoder args for a given output extension
    _acut_enc() {
        case "${1##*.}" in
            mp3)  echo "-c:a libmp3lame -b:a 192k" ;;
            m4a|aac) echo "-c:a aac -b:a 192k" ;;
            wav)  echo "-c:a pcm_s16le" ;;
            ogg)  echo "-c:a libvorbis -q:a 4" ;;
            flac) echo "-c:a flac" ;;
            *)    echo "-c:a libmp3lame -b:a 192k" ;;
        esac
    }

    local input_duration
    input_duration=$(ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null)
    if [[ -z "$input_duration" ]]; then
        echo "❌ Could not read audio duration from: $input_file" >&2
        return 1
    fi
    local dur_secs="${input_duration%%.*}"

    # ── Simple trim (no delete): stream copy, fast ─────────────────────────────
    if [[ $delete_mode -eq 0 ]]; then
        echo "✂️  Trimming: ${start_time:-(start)} → ${end_time:-(end)}"
        local trim_args=()
        [[ -n "$start_time" ]] && trim_args+=(-ss "$start_time")
        [[ -n "$end_time" ]] && trim_args+=(-to "$end_time")

        run_ffmpeg_with_progress "$dur_secs" \
            "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
            "${trim_args[@]}" -i "$input_file" -c copy "$output_file"

        if [[ $? -eq 0 ]]; then
            echo ""
            echo "✅ COMPLETE: $(basename "$output_file")"
            echo "📍 Output: $(realpath "$output_file")"
        else
            echo "❌ Trim failed." >&2
            return 1
        fi
        return 0
    fi

    # ── Delete mode: sort and validate ranges ──────────────────────────────────
    local -a ds=() de=()
    local i
    for (( i=0; i<${#delete_starts[@]}; i++ )); do
        ds+=("$(_acut_to_sec "${delete_starts[$i]}")")
        de+=("$(_acut_to_sec "${delete_ends[$i]}")")
    done

    # Sort ranges by start time
    local sorted_pairs
    sorted_pairs=$(for (( i=0; i<${#ds[@]}; i++ )); do
        printf '%s %s\n' "${ds[$i]}" "${de[$i]}"
    done | awk '{printf "%.6f %.6f\n", $1, $2}' | sort -n)
    ds=(); de=()
    while IFS=' ' read -r s e; do
        ds+=("$s"); de+=("$e")
    done <<< "$sorted_pairs"

    for (( i=0; i<${#ds[@]}; i++ )); do
        if awk -v s="${ds[$i]}" -v e="${de[$i]}" 'BEGIN{exit (e<=s)?0:1}'; then
            echo "❌ Delete range $((i+1)): end must be greater than start (${delete_starts[$i]} → ${delete_ends[$i]})" >&2
            return 1
        fi
        if [[ $i -gt 0 ]]; then
            if awk -v prev="${de[$((i-1))]}" -v cur="${ds[$i]}" 'BEGIN{exit (cur<prev)?0:1}'; then
                echo "❌ Delete ranges overlap between range $i and $((i+1))." >&2
                return 1
            fi
        fi
    done

    # Build keep segments (inverse of delete ranges)
    local -a keep_starts=(0) keep_ends=()
    for (( i=0; i<${#ds[@]}; i++ )); do
        keep_ends+=("${ds[$i]}")
        keep_starts+=("${de[$i]}")
    done
    keep_ends+=("$input_duration")

    echo "✂️  Mode: Delete ($((${#ds[@]})) range(s)) — audio re-encode"
    for (( i=0; i<${#ds[@]}; i++ )); do
        printf '   🗑️  Delete %d: %s → %s\n' "$((i+1))" "${delete_starts[$i]}" "${delete_ends[$i]}"
    done

    # Build filter_complex (audio-only: atrim + asetpts + concat)
    local filter="" seg=0
    for (( i=0; i<${#keep_starts[@]}; i++ )); do
        local ks="${keep_starts[$i]}" ke="${keep_ends[$i]}"
        if awk -v s="$ks" -v e="$ke" 'BEGIN{exit (e-s > 0.05)?0:1}'; then
            filter+="[0:a]atrim=start=${ks}:end=${ke},asetpts=PTS-STARTPTS[a${seg}];"
            seg=$(( seg+1 ))
        fi
    done

    if [[ $seg -eq 0 ]]; then
        echo "❌ Delete ranges remove the entire audio." >&2
        return 1
    fi

    local concat_in=""
    for (( i=0; i<seg; i++ )); do concat_in+="[a${i}]"; done
    filter+="${concat_in}concat=n=${seg}:v=0:a=1[outa]"

    local filter_file
    filter_file=$(mktemp /tmp/amir_audiocut_XXXXXX.txt)
    printf '%s' "$filter" > "$filter_file"

    local enc_args
    read -r -a enc_args <<< "$(_acut_enc "$output_file")"

    run_ffmpeg_with_progress "$dur_secs" \
        "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
        -i "$input_file" \
        -filter_complex_script "$filter_file" \
        -map '[outa]' \
        "${enc_args[@]}" \
        "$output_file"
    local exit_code=$?
    rm -f "$filter_file"

    if [[ $exit_code -eq 0 ]]; then
        echo ""
        echo "✅ COMPLETE: $(basename "$output_file")"
        echo "📍 Output: $(realpath "$output_file")"
    else
        echo "❌ Audio cut failed." >&2
        return 1
    fi
}

audio_normalize() {
    local target_lufs="-16"
    local true_peak="-1"
    local output_file=""
    local -a input_files=()
    local -a _opts=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --target|-l) target_lufs="$2"; _opts+=("$1" "$2"); shift 2 ;;
            --peak|-p)   true_peak="$2";   _opts+=("$1" "$2"); shift 2 ;;
            -o|--output) output_file="$2"; shift 2 ;;
            *)
                if [[ -f "$1" ]]; then
                    input_files+=("$1"); shift
                else
                    echo "❌ Unknown argument: $1" >&2
                    echo "Usage: amir audio normalize <file(s)> [--target -16] [--peak -1] [-o output]" >&2
                    return 1
                fi ;;
        esac
    done

    if [[ ${#input_files[@]} -eq 0 ]]; then
        echo "❌ No input file." >&2
        echo "Usage: amir audio normalize <file(s)> [--target -16] [--peak -1] [-o output]" >&2
        echo "  --target  Target integrated loudness in LUFS (default: -16, YouTube standard)" >&2
        echo "  --peak    Max true peak in dBTP (default: -1)" >&2
        return 1
    fi

    # ── Batch dispatch ─────────────────────────────────────────────────────────
    if [[ ${#input_files[@]} -gt 1 ]]; then
        [[ -n "$output_file" ]] && echo "⚠️  Batch mode: -o ignored, outputs auto-named." >&2
        local _ok=0 _fail=0 _total=${#input_files[@]}
        for _f in "${input_files[@]}"; do
            echo ""; echo "── [$(( _ok + _fail + 1 ))/${_total}] $(basename "$_f") ──"
            if audio_normalize "$_f" "${_opts[@]}"; then (( _ok += 1 )); else (( _fail += 1 )); fi
        done
        echo ""; echo "Batch normalize: ${_ok}✅  ${_fail}❌  (${_total} files)"
        return $(( _fail > 0 ? 1 : 0 ))
    fi

    local input_file="${input_files[0]}"
    local ext="${input_file##*.}"
    [[ -z "$output_file" ]] && output_file="${input_file%.*}_normalized.${ext}"

    local FFMPEG_PATH; FFMPEG_PATH=$(get_ffmpeg_path)

    # Pass 1: measure loudness
    echo "📊 Measuring loudness (pass 1)..."
    local measured
    measured=$("$FFMPEG_PATH" -hide_banner -i "$input_file" \
        -af "loudnorm=I=${target_lufs}:TP=${true_peak}:LRA=11:print_format=json" \
        -f null /dev/null 2>&1 | grep -A 20 '"input_i"')

    if [[ -z "$measured" ]]; then
        echo "❌ loudnorm measurement failed." >&2
        return 1
    fi

    local input_i input_tp input_lra input_thresh
    input_i=$(echo "$measured"    | grep '"input_i"'          | grep -o '"-\?[0-9.]*"' | tr -d '"')
    input_tp=$(echo "$measured"   | grep '"input_tp"'         | grep -o '"-\?[0-9.]*"' | tr -d '"')
    input_lra=$(echo "$measured"  | grep '"input_lra"'        | grep -o '"-\?[0-9.]*"' | tr -d '"')
    input_thresh=$(echo "$measured" | grep '"input_thresh"'   | grep -o '"-\?[0-9.]*"' | tr -d '"')

    echo "   Input:  ${input_i} LUFS  |  Peak: ${input_tp} dBTP  |  LRA: ${input_lra} LU"
    echo "   Target: ${target_lufs} LUFS  |  Peak: ${true_peak} dBTP"

    # Pass 2: apply normalization
    echo "🔊 Applying normalization (pass 2)..."
    local duration_seconds
    duration_seconds=$(ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null | cut -d. -f1)

    local filter="loudnorm=I=${target_lufs}:TP=${true_peak}:LRA=11"
    filter+=":measured_I=${input_i}:measured_TP=${input_tp}"
    filter+=":measured_LRA=${input_lra}:measured_thresh=${input_thresh}"
    filter+=":offset=0:linear=true:print_format=none"

    local enc_args=()
    case "$ext" in
        mp3)  enc_args=(-c:a libmp3lame -b:a 192k) ;;
        m4a|aac) enc_args=(-c:a aac -b:a 192k) ;;
        wav)  enc_args=(-c:a pcm_s16le) ;;
        ogg)  enc_args=(-c:a libvorbis -q:a 4) ;;
        flac) enc_args=(-c:a flac) ;;
        *)    enc_args=(-c:a libmp3lame -b:a 192k) ;;
    esac

    run_ffmpeg_with_progress "$duration_seconds" \
        "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
        -i "$input_file" -af "$filter" "${enc_args[@]}" "$output_file"

    if [[ $? -eq 0 ]]; then
        echo ""
        echo "✅ COMPLETE: $(basename "$output_file")"
        echo "📍 Output: $(realpath "$output_file")"
    else
        echo "❌ Normalization failed." >&2
        return 1
    fi
}

audio_fade() {
    local fade_in=0
    local fade_out=0
    local output_file=""
    local -a input_files=()
    local -a _opts=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --in|-i)  fade_in="$2";  _opts+=("$1" "$2"); shift 2 ;;
            --out|-O) fade_out="$2"; _opts+=("$1" "$2"); shift 2 ;;
            -o|--output) output_file="$2"; shift 2 ;;
            *)
                if [[ -f "$1" ]]; then
                    input_files+=("$1"); shift
                else
                    echo "❌ Unknown argument: $1" >&2
                    echo "Usage: amir audio fade <file(s)> [--in 2] [--out 3] [-o output]" >&2
                    return 1
                fi ;;
        esac
    done

    if [[ ${#input_files[@]} -eq 0 ]]; then
        echo "❌ No input file." >&2
        echo "Usage: amir audio fade <file(s)> [--in 2] [--out 3] [-o output]" >&2
        echo "  --in   Fade-in duration in seconds (default: 0)" >&2
        echo "  --out  Fade-out duration in seconds (default: 0)" >&2
        return 1
    fi

    if [[ "$fade_in" == "0" && "$fade_out" == "0" ]]; then
        echo "❌ Specify at least --in or --out." >&2
        return 1
    fi

    # ── Batch dispatch ─────────────────────────────────────────────────────────
    if [[ ${#input_files[@]} -gt 1 ]]; then
        [[ -n "$output_file" ]] && echo "⚠️  Batch mode: -o ignored, outputs auto-named." >&2
        local _ok=0 _fail=0 _total=${#input_files[@]}
        for _f in "${input_files[@]}"; do
            echo ""; echo "── [$(( _ok + _fail + 1 ))/${_total}] $(basename "$_f") ──"
            if audio_fade "$_f" "${_opts[@]}"; then (( _ok += 1 )); else (( _fail += 1 )); fi
        done
        echo ""; echo "Batch fade: ${_ok}✅  ${_fail}❌  (${_total} files)"
        return $(( _fail > 0 ? 1 : 0 ))
    fi

    local input_file="${input_files[0]}"

    local duration
    duration=$(ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null)
    if [[ -z "$duration" ]]; then
        echo "❌ Could not read duration from: $input_file" >&2
        return 1
    fi

    local ext="${input_file##*.}"
    [[ -z "$output_file" ]] && output_file="${input_file%.*}_fade.${ext}"

    # Build afade filter chain
    local filters=()
    if awk -v v="$fade_in" 'BEGIN{exit (v>0)?0:1}'; then
        filters+=("afade=t=in:st=0:d=${fade_in}")
    fi
    if awk -v v="$fade_out" 'BEGIN{exit (v>0)?0:1}'; then
        local fade_out_start
        fade_out_start=$(awk -v d="$duration" -v fo="$fade_out" 'BEGIN{printf "%.6f", d-fo}')
        filters+=("afade=t=out:st=${fade_out_start}:d=${fade_out}")
    fi

    local filter_str
    printf -v filter_str '%s,' "${filters[@]}"
    filter_str="${filter_str%,}"

    local FFMPEG_PATH; FFMPEG_PATH=$(get_ffmpeg_path)
    local dur_secs="${duration%%.*}"

    echo "🎚️  Fade: in=${fade_in}s  out=${fade_out}s"

    local enc_args=()
    case "$ext" in
        mp3)  enc_args=(-c:a libmp3lame -b:a 192k) ;;
        m4a|aac) enc_args=(-c:a aac -b:a 192k) ;;
        wav)  enc_args=(-c:a pcm_s16le) ;;
        ogg)  enc_args=(-c:a libvorbis -q:a 4) ;;
        flac) enc_args=(-c:a flac) ;;
        *)    enc_args=(-c:a libmp3lame -b:a 192k) ;;
    esac

    run_ffmpeg_with_progress "$dur_secs" \
        "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
        -i "$input_file" -af "$filter_str" "${enc_args[@]}" "$output_file"

    if [[ $? -eq 0 ]]; then
        echo ""
        echo "✅ COMPLETE: $(basename "$output_file")"
        echo "📍 Output: $(realpath "$output_file")"
    else
        echo "❌ Fade failed." >&2
        return 1
    fi
}

audio_trim_silence() {
    local threshold="-40"
    local pad="0.3"
    local output_file=""
    local -a input_files=()
    local -a _opts=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --threshold|-t) threshold="$2"; _opts+=("$1" "$2"); shift 2 ;;
            --pad|-p)       pad="$2";       _opts+=("$1" "$2"); shift 2 ;;
            -o|--output)    output_file="$2"; shift 2 ;;
            *)
                if [[ -f "$1" ]]; then
                    input_files+=("$1"); shift
                else
                    echo "❌ Unknown argument: $1" >&2
                    echo "Usage: amir audio trim-silence <file(s)> [--threshold -40] [--pad 0.3] [-o output]" >&2
                    return 1
                fi ;;
        esac
    done

    if [[ ${#input_files[@]} -eq 0 ]]; then
        echo "❌ No input file." >&2
        echo "Usage: amir audio trim-silence <file(s)> [--threshold -40] [--pad 0.3] [-o output]" >&2
        echo "  --threshold  Silence level in dB (default: -40). Louder = more aggressive." >&2
        echo "  --pad        Seconds of silence to keep at edges (default: 0.3)" >&2
        return 1
    fi

    # ── Batch dispatch ─────────────────────────────────────────────────────────
    if [[ ${#input_files[@]} -gt 1 ]]; then
        [[ -n "$output_file" ]] && echo "⚠️  Batch mode: -o ignored, outputs auto-named." >&2
        local _ok=0 _fail=0 _total=${#input_files[@]}
        for _f in "${input_files[@]}"; do
            echo ""; echo "── [$(( _ok + _fail + 1 ))/${_total}] $(basename "$_f") ──"
            if audio_trim_silence "$_f" "${_opts[@]}"; then (( _ok += 1 )); else (( _fail += 1 )); fi
        done
        echo ""; echo "Batch trim-silence: ${_ok}✅  ${_fail}❌  (${_total} files)"
        return $(( _fail > 0 ? 1 : 0 ))
    fi

    local input_file="${input_files[0]}"
    local ext="${input_file##*.}"
    [[ -z "$output_file" ]] && output_file="${input_file%.*}_trimmed.${ext}"

    local FFMPEG_PATH; FFMPEG_PATH=$(get_ffmpeg_path)
    local duration_seconds
    duration_seconds=$(ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$input_file" 2>/dev/null | cut -d. -f1)

    echo "✂️  Trimming silence (threshold: ${threshold}dB, pad: ${pad}s)..."

    # silenceremove: remove leading silence (start_periods=1) and trailing silence (stop_periods=1)
    # areverse trick: apply twice to handle both ends, since silenceremove only removes leading silence
    local filter="silenceremove=start_periods=1:start_silence=${pad}:start_threshold=${threshold}dB"
    filter+=",areverse"
    filter+=",silenceremove=start_periods=1:start_silence=${pad}:start_threshold=${threshold}dB"
    filter+=",areverse"

    local enc_args=()
    case "$ext" in
        mp3)  enc_args=(-c:a libmp3lame -b:a 192k) ;;
        m4a|aac) enc_args=(-c:a aac -b:a 192k) ;;
        wav)  enc_args=(-c:a pcm_s16le) ;;
        ogg)  enc_args=(-c:a libvorbis -q:a 4) ;;
        flac) enc_args=(-c:a flac) ;;
        *)    enc_args=(-c:a libmp3lame -b:a 192k) ;;
    esac

    run_ffmpeg_with_progress "$duration_seconds" \
        "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
        -i "$input_file" -af "$filter" "${enc_args[@]}" "$output_file"

    if [[ $? -eq 0 ]]; then
        local new_dur
        new_dur=$(ffprobe -v error -show_entries format=duration \
            -of default=noprint_wrappers=1:nokey=1 "$output_file" 2>/dev/null)
        echo ""
        echo "✅ COMPLETE: $(basename "$output_file")"
        echo "📍 Output: $(realpath "$output_file")"
        if [[ -n "$new_dur" && -n "$duration_seconds" ]]; then
            local removed
            removed=$(awk -v orig="$duration_seconds" -v new="$new_dur" 'BEGIN{printf "%.1f", orig-new}')
            echo "   Removed ${removed}s of silence"
        fi
    else
        echo "❌ trim-silence failed." >&2
        return 1
    fi
}

audio_split() {
    # Usage: amir audio split <file(s)> <mb>
    # Last numeric arg is always the chunk size in MB
    local -a input_files=()
    local split_mb=""

    for arg in "$@"; do
        if [[ -f "$arg" ]]; then
            input_files+=("$arg")
        elif [[ "$arg" =~ ^[0-9]+$ ]]; then
            split_mb="$arg"
        else
            log_error "Unknown argument: $arg" >&2
            echo "Usage: amir audio split <file(s)> <mb>" >&2
            return 1
        fi
    done

    if [[ ${#input_files[@]} -eq 0 ]]; then
        log_error "No input files specified." >&2
        echo "Usage: amir audio split <file(s)> <mb>" >&2
        return 1
    fi
    if [[ -z "$split_mb" || "$split_mb" -le 0 ]]; then
        log_error "Split size must be a positive integer in MB." >&2
        echo "Usage: amir audio split <file(s)> <mb>" >&2
        return 1
    fi

    local _ok=0 _fail=0 _total=${#input_files[@]}
    for _f in "${input_files[@]}"; do
        [[ $_total -gt 1 ]] && echo "── [$(( _ok + _fail + 1 ))/${_total}] $(basename "$_f") ──"
        if split_media_approx_by_size "$_f" "$split_mb"; then (( _ok += 1 )); else (( _fail += 1 )); fi
    done
    [[ $_total -gt 1 ]] && { echo ""; echo "Batch split: ${_ok}✅  ${_fail}❌  (${_total} files)"; }
    return $(( _fail > 0 ? 1 : 0 ))
}

audio_convert() {
    # Usage: amir audio convert <file(s)> [mp3|wav|ogg|m4a]
    # Last non-file arg is the target format (default: mp3)
    local -a input_files=()
    local FORMAT="mp3"

    for arg in "$@"; do
        if [[ -f "$arg" ]]; then
            input_files+=("$arg")
        elif [[ "$arg" =~ ^(mp3|wav|ogg|m4a|aac|flac)$ ]]; then
            FORMAT="$arg"
        else
            log_error "Unknown argument: $arg" >&2
            echo "Usage: amir audio convert <file(s)> [mp3|wav|ogg|m4a|flac]" >&2
            return 1
        fi
    done

    if [[ ${#input_files[@]} -eq 0 ]]; then
        log_error "No input files specified." >&2
        echo "Usage: amir audio convert <file(s)> [mp3|wav|ogg|m4a|flac]" >&2
        return 1
    fi

    local ENCODER_ARGS=()
    case "$FORMAT" in
        mp3)  ENCODER_ARGS=(-c:a libmp3lame -b:a 192k) ;;
        wav)  ENCODER_ARGS=(-c:a pcm_s16le) ;;
        ogg)  ENCODER_ARGS=(-c:a libvorbis -q:a 4) ;;
        m4a|aac) ENCODER_ARGS=(-c:a aac -b:a 192k) ;;
        flac) ENCODER_ARGS=(-c:a flac) ;;
        *)
            log_error "Unsupported target format: $FORMAT" >&2
            echo "Try: mp3, wav, ogg, m4a, or flac" >&2
            return 1 ;;
    esac

    local FFMPEG_PATH; FFMPEG_PATH=$(get_ffmpeg_path)
    local UPPER_FORMAT; UPPER_FORMAT=$(echo "$FORMAT" | tr '[:lower:]' '[:upper:]')
    local _ok=0 _fail=0 _total=${#input_files[@]}

    for INPUT in "${input_files[@]}"; do
        [[ $_total -gt 1 ]] && echo "── [$(( _ok + _fail + 1 ))/${_total}] $(basename "$INPUT") ──"
        local OUTPUT="${INPUT%.*}.${FORMAT}"
        if [[ "$INPUT" == "$OUTPUT" ]]; then
            log_error "Input and target format are the same: $INPUT" >&2
            (( _fail++ )); continue
        fi
        log_info "🔄 Converting $(basename "$INPUT") to ${UPPER_FORMAT}..." >&2
        local duration_seconds
        duration_seconds=$(ffprobe -v error -show_entries format=duration \
            -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null | cut -d. -f1)
        run_ffmpeg_with_progress "$duration_seconds" \
            "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
            -i "$INPUT" -vn "${ENCODER_ARGS[@]}" "$OUTPUT"
        if [[ $? -eq 0 ]]; then
            log_success "Converted: $OUTPUT" >&2
            echo "$OUTPUT"
            (( _ok++ ))
        else
            log_error "Conversion failed: $INPUT" >&2
            (( _fail++ ))
        fi
    done

    [[ $_total -gt 1 ]] && { echo ""; echo "Batch convert: ${_ok}✅  ${_fail}❌  (${_total} files)"; }
    return $(( _fail > 0 ? 1 : 0 ))
}

audio_extract() {
    # Source Config
    if [[ -f "$LIB_DIR/config.sh" ]]; then source "$LIB_DIR/config.sh"; else get_config() { echo "$3"; }; fi
    local default_kbps; default_kbps=$(get_config "mp3" "bitrate" "320")
    local kbps="$default_kbps"
    local split_mb="0"
    local -a input_files=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --split) split_mb="$2"; shift 2 ;;
            *)
                if [[ -f "$1" ]]; then
                    input_files+=("$1"); shift
                elif [[ "$1" =~ ^[0-9]+$ ]]; then
                    kbps="$1"; shift
                else
                    log_error "Unknown option for extract: $1" >&2
                    echo "Usage: amir audio extract <video_file(s)> [bitrate] [--split <mb>]" >&2
                    return 1
                fi ;;
        esac
    done

    if [[ ${#input_files[@]} -eq 0 ]]; then
        log_error "No input files specified." >&2
        echo "Usage: amir audio extract <video_file(s)> [bitrate] [--split <mb>]" >&2
        return 1
    fi

    if [[ "$split_mb" != "0" && ( ! "$split_mb" =~ ^[0-9]+$ || "$split_mb" -le 0 ) ]]; then
        log_error "Split size must be a positive integer in MB." >&2
        return 1
    fi

    local FFMPEG_PATH; FFMPEG_PATH=$(get_ffmpeg_path)
    local _ok=0 _fail=0 _total=${#input_files[@]}

    for INPUT in "${input_files[@]}"; do
        [[ $_total -gt 1 ]] && echo "── [$(( _ok + _fail + 1 ))/${_total}] $(basename "$INPUT") ──"
        local OUTPUT="${INPUT%.*}.mp3"
        log_info "🎧 Extracting at ${kbps}kbps: $(basename "$INPUT") ..." >&2
        local duration_seconds
        duration_seconds=$(ffprobe -v error -show_entries format=duration \
            -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null | cut -d. -f1)
        run_ffmpeg_with_progress "$duration_seconds" \
            "$FFMPEG_PATH" -hide_banner -loglevel info -stats -y \
            -i "$INPUT" -vn -c:a libmp3lame -b:a "${kbps}k" "$OUTPUT"
        if [[ $? -eq 0 ]]; then
            log_success "Created: $OUTPUT" >&2
            echo "$OUTPUT"
            if [[ "$split_mb" =~ ^[0-9]+$ && "$split_mb" -gt 0 ]]; then
                split_media_approx_by_size "$OUTPUT" "$split_mb"
            fi
            (( _ok++ ))
        else
            log_error "Extraction failed: $INPUT" >&2
            (( _fail++ ))
        fi
    done

    [[ $_total -gt 1 ]] && { echo ""; echo "Batch extract: ${_ok}✅  ${_fail}❌  (${_total} files)"; }
    return $(( _fail > 0 ? 1 : 0 ))
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
