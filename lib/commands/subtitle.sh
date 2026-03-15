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
    PYTHONPATH="$LIB_DIR/python:$PYTHONPATH" "$_PYTHON" -m subtitle "$@"
}

run_subtitle() {
    # Translate --sub-only (public flag) to --no-render (internal Python flag)
    local -a _args_tr=()
    for _a in "$@"; do
        [[ "$_a" == "--sub-only" ]] && _args_tr+=("--no-render") || _args_tr+=("$_a")
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
        # Download flags accepted here: --resolution/-R, --extreme, --browser/-b, --cookies, -y/--yes
        # Everything else (-s, -t, --llm, --model, --no-render …) goes to _subtitle_run.
        local -a _orig=("$@")
        local -a _dl_flags=()
        local -a _sub_flags=()
        local _i=0
        while (( _i < ${#_orig[@]} )); do
            local _cur="${_orig[_i]}"
            if [[ "$_cur" == "$_url" ]]; then (( _i++ )); continue; fi
            case "$_cur" in
                --resolution|-R)
                    _dl_flags+=("$_cur" "${_orig[_i+1]}"); (( _i += 2 ))
                    _sub_flags+=("--resolution" "${_orig[_i-1]}")
                    # Optional quality value immediately after height (must be 1-100)
                    if [[ -n "${_orig[_i]:-}" && "${_orig[_i]:-}" =~ ^[0-9]+$ && ${_orig[_i]} -le 100 ]]; then
                        _dl_flags+=("${_orig[_i]}")
                        _sub_flags+=("--quality" "${_orig[_i]}")
                        (( _i++ ))
                    fi ;;
                --browser|-b|--cookies)
                    _dl_flags+=("$_cur" "${_orig[_i+1]}"); (( _i += 2 )) ;;
                --extreme)
                    _dl_flags+=("$_cur"); (( _i++ )) ;;
                -y|--yes)
                    _dl_flags+=("$_cur"); (( _i++ )) ;;
                *)
                    _sub_flags+=("$_cur"); (( _i++ )) ;;
            esac
        done

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
