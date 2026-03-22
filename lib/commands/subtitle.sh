#!/bin/bash

# _subtitle_run <file> [subtitle-flags...]
# Private helper: runs the Python subtitle module.
# Defined once here so run_subtitle and the URL-download path both call it
# without duplicating the PYTHONPATH / python3 invocation.
_subtitle_run() {
    local SUBTITLE_DIR="$LIB_DIR/python/subtitle"
    if [[ ! -d "$SUBTITLE_DIR" ]]; then
        echo "❌ Error: Subtitle module not found at $SUBTITLE_DIR" >&2
        return 1
    fi
    # Prefer the project venv Python (has mlx-whisper, faster-whisper, etc.)
    local _VENV_PY="$LIB_DIR/../.venv/bin/python"
    local _PYTHON
    if [[ -x "$_VENV_PY" ]]; then
        _PYTHON="$_VENV_PY"
    elif command -v python3 &>/dev/null; then
        _PYTHON="python3"
    else
        echo "❌ Error: python3 not found." >&2
        return 1
    fi

    # macOS allocator noise suppression (harmless warning spam):
    # "MallocStackLogging: can't turn off malloc stack logging..."
    # Unset these variables for this subprocess only.
    #
    # Adaptive RAM profile (no queueing/serialization):
    # If another subtitle process is already running, force a lighter runtime
    # profile for THIS process only to reduce peak memory under parallel load.
    # Users can disable this behavior with: AMIR_SUBTITLE_ADAPTIVE_RAM=0
    local _ADAPTIVE_RAM="${AMIR_SUBTITLE_ADAPTIVE_RAM:-1}"
    local _LOW_RAM_MODE=0
    if [[ "$_ADAPTIVE_RAM" != "0" ]]; then
        local _active_subtitle_jobs
        _active_subtitle_jobs=$(pgrep -f "[p]ython(3(\\.[0-9]+)?)? .* -m subtitle" 2>/dev/null | wc -l | tr -d ' ')
        if [[ -n "$_active_subtitle_jobs" && "$_active_subtitle_jobs" =~ ^[0-9]+$ && "$_active_subtitle_jobs" -ge 1 ]]; then
            _LOW_RAM_MODE=1
            echo "ℹ️  Parallel subtitle run detected ($_active_subtitle_jobs active). Using low-RAM profile for this job." >&2
        fi
    fi

    local -a _ENV_ARGS=(
        -u MallocStackLogging
        -u MallocStackLoggingNoCompact
        -u MallocScribble
        -u MallocGuardEdges
        "PYTHONPATH=$LIB_DIR/python:$PYTHONPATH"
    )

    # IMPORTANT: Do NOT force AMIR_SUBTITLE_MAX_CONCURRENT by default.
    # If user sets it explicitly, pass through. Otherwise leave unlimited.
    if [[ -n "${AMIR_SUBTITLE_MAX_CONCURRENT:-}" ]]; then
        _ENV_ARGS+=("AMIR_SUBTITLE_MAX_CONCURRENT=${AMIR_SUBTITLE_MAX_CONCURRENT}")
    fi

    if [[ "$_LOW_RAM_MODE" -eq 1 ]]; then
        _ENV_ARGS+=(
            "AMIR_FORCE_FASTER_WHISPER=1"
            "OMP_NUM_THREADS=1"
            "OPENBLAS_NUM_THREADS=1"
            "MKL_NUM_THREADS=1"
            "NUMEXPR_NUM_THREADS=1"
            "VECLIB_MAXIMUM_THREADS=1"
        )
    fi

    env \
        "${_ENV_ARGS[@]}" \
        "$_PYTHON" -m subtitle "$@"
}

run_subtitle() {
    # Translate --sub-only (public flag) to --no-render (internal Python flag)
    local -a _args_tr=()
    for _a in "$@"; do
        local _norm="$_a"
        # Normalize common Unicode dash characters from copy/paste to ASCII '-'
        _norm="${_norm//$'\u2013'/-}"  # en dash
        _norm="${_norm//$'\u2014'/-}"  # em dash
        _norm="${_norm//$'\u2212'/-}"  # minus sign

        [[ "$_norm" == "--sub-only" ]] && _args_tr+=("--no-render") || _args_tr+=("$_norm")
    done
    set -- "${_args_tr[@]}"

    # ── URL auto-detect ────────────────────────────────────────────────────
    # If the first positional argument is a URL, download it first via
    # video_download (the single source of truth for all yt-dlp logic),
    # then replace the URL with the local file path and call _subtitle_run.
    # This way every subtitle flag (-s, -t, --llm, --model, --no-render …)
    # passes through unchanged — no duplication, no flag translation needed.
    local _url=""
    for _a in "$@"; do
        [[ "$_a" =~ ^https?:// ]] && _url="$_a" && break
    done

    if [[ -n "$_url" ]]; then
        # Load video_download (reuse, don't duplicate)
        source "$LIB_DIR/commands/video.sh"

        # Separate download-only flags from subtitle flags.
        # Download flags accepted here: --resolution/-R, --quality, --extreme, --browser/-b, --cookies, -y/--yes
        # Everything else (-s, -t, --llm, --model, --no-render …) goes to _subtitle_run.
        local -a _orig=("$@")
        local -a _dl_flags=()
        local -a _sub_flags=()
        local _has_extreme=false
        local _has_resolution=false
        local _has_quality=false
        local _i=0
        while (( _i < ${#_orig[@]} )); do
            local _cur="${_orig[_i]}"
            if [[ "$_cur" == "$_url" ]]; then (( _i++ )); continue; fi
            case "$_cur" in
                --resolution|-R)
                    _has_resolution=true
                    _dl_flags+=("$_cur" "${_orig[_i+1]}"); (( _i += 2 ))
                    _sub_flags+=("--resolution" "${_orig[_i-1]}")
                    # Optional quality value immediately after height (must be 1-100)
                    if [[ -n "${_orig[_i]:-}" && "${_orig[_i]:-}" =~ ^[0-9]+$ && ${_orig[_i]} -le 100 ]]; then
                        _dl_flags+=("${_orig[_i]}")
                        _sub_flags+=("--quality" "${_orig[_i]}")
                        _has_quality=true
                        (( _i++ ))
                    fi ;;
                --quality)
                    _has_quality=true
                    _dl_flags+=("$_cur" "${_orig[_i+1]}")
                    _sub_flags+=("$_cur" "${_orig[_i+1]}")
                    (( _i += 2 )) ;;
                --browser|-b|--cookies)
                    _dl_flags+=("$_cur" "${_orig[_i+1]}"); (( _i += 2 )) ;;
                --keep-thumb)
                    _dl_flags+=("$_cur"); (( _i++ )) ;;
                --extreme)
                    _has_extreme=true
                    _dl_flags+=("$_cur"); (( _i++ )) ;;
                -y|--yes)
                    _dl_flags+=("$_cur"); (( _i++ )) ;;
                *)
                    _sub_flags+=("$_cur"); (( _i++ )) ;;
            esac
        done

        # Default to extreme download profile for `amir video subtitle <URL>`.
        if ! $_has_extreme; then
            _has_extreme=true
            _dl_flags+=("--extreme")
        fi

        # Keep subtitle render profile aligned with video_download extreme defaults.
        if $_has_extreme; then
            $_has_resolution || _sub_flags+=("--resolution" "360")
            $_has_quality || _sub_flags+=("--quality" "30")
        fi

        # Download only (no --subtitle: all subtitle processing happens below via _subtitle_run)
        # stdout = final file path; stderr (progress bars, info) goes straight to terminal
        local _VIDEO_FILE
        _VIDEO_FILE=$(video_download "$_url" "${_dl_flags[@]}")
        if [[ -z "$_VIDEO_FILE" || ! -f "$_VIDEO_FILE" ]]; then
            echo "❌ Download failed or file not found." >&2
            return 1
        fi

        # Run subtitle on the downloaded file with all original subtitle flags
        _subtitle_run "$_VIDEO_FILE" "${_sub_flags[@]}"
        return $?
    fi

    # ── Normal file path ───────────────────────────────────────────────────
    _subtitle_run "$@"
}
