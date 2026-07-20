#!/usr/bin/env bash
# amir download — universal media downloader
# Videos (YouTube, TikTok, Twitter/X, Vimeo, 1000+ sites): yt-dlp
# Instagram photo/carousel posts: gallery-dl (auto-installed if missing)

run_download() {
    source "$LIB_DIR/commands/video.sh"

    # Extract URL and --format flag before delegating
    local URL=""
    local IMG_FORMAT="jpg"
    local -a PASSTHROUGH=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --format|-f)
                IMG_FORMAT="$2"; shift 2 ;;
            *)
                [[ "$1" =~ ^https?:// && -z "$URL" ]] && URL="$1"
                PASSTHROUGH+=("$1"); shift ;;
        esac
    done

    if [[ -z "$URL" ]]; then
        _download_help
        return 1
    fi

    if [[ "$URL" =~ (instagram\.com|instagr\.am) ]]; then
        _download_instagram "$IMG_FORMAT" "${PASSTHROUGH[@]}"
    else
        video_download "${PASSTHROUGH[@]}"
    fi
}

# ── Instagram: probe for video formats, fall back to gallery-dl for photos ────

_download_instagram() {
    local IMG_FORMAT="$1"; shift
    local URL=""
    local -a ARGS=("$@")

    for arg in "$@"; do
        [[ "$arg" =~ ^https?:// ]] && URL="$arg" && break
    done

    local BROWSER="${AMIR_DEFAULT_BROWSER:-chrome}"
    local COOKIES_FILE=""
    local i=0
    while [[ $i -lt ${#ARGS[@]} ]]; do
        case "${ARGS[$i]}" in
            --browser|-b) BROWSER="${ARGS[$((i+1))]}"; i=$((i+2)) ;;
            --cookies)    COOKIES_FILE="${ARGS[$((i+1))]}"; i=$((i+2)) ;;
            *) i=$((i+1)) ;;
        esac
    done

    log_info "🔍 Probing Instagram URL..." >&2

    local probe_json
    probe_json=$(yt-dlp --no-playlist -J "$URL" 2>/dev/null)

    local has_video="no"
    if [[ -n "$probe_json" ]]; then
        has_video=$(echo "$probe_json" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    fmts=d.get('formats',[])
    print('yes' if any(f.get('vcodec','none') not in ('none','') and f.get('height') for f in fmts) else 'no')
except:
    print('unknown')
" 2>/dev/null)
    fi

    if [[ "$has_video" == "yes" ]]; then
        log_info "🎬 Reel/video detected — using yt-dlp..." >&2
        video_download "$@"
    else
        log_info "📸 Photo/carousel post detected — using gallery-dl..." >&2
        _gallery_dl_download "$URL" "$(pwd)" "$BROWSER" "$COOKIES_FILE" "$IMG_FORMAT"
    fi
}

# ── gallery-dl wrapper ─────────────────────────────────────────────────────────

_gallery_dl_download() {
    local URL="$1"
    local OUT_DIR="${2:-.}"
    local BROWSER="${3:-chrome}"
    local COOKIES_FILE="${4:-}"
    local IMG_FORMAT="${5:-jpg}"   # jpg | png | webp (webp = no conversion)

    # Normalise: jpg → jpeg for sips
    local SIPS_FORMAT="$IMG_FORMAT"
    [[ "$SIPS_FORMAT" == "jpg" ]] && SIPS_FORMAT="jpeg"

    if ! command -v gallery-dl &>/dev/null; then
        log_info "📦 gallery-dl not found — installing via uv tool..." >&2
        if ! uv tool install gallery-dl --with yt-dlp 2>&1; then
            log_error "Failed to install gallery-dl. Install manually: uv tool install gallery-dl --with yt-dlp" >&2
            return 1
        fi
        log_info "✅ gallery-dl installed." >&2
    fi

    local -a COOKIE_ARGS=()
    if [[ -n "$COOKIES_FILE" ]]; then
        COOKIE_ARGS=(--cookies "$COOKIES_FILE")
    elif [[ -f "cookies.txt" ]]; then
        COOKIE_ARGS=(--cookies "cookies.txt")
    elif [[ -f "$HOME/su6i-yar/cookies.txt" ]]; then
        COOKIE_ARGS=(--cookies "$HOME/su6i-yar/cookies.txt")
    elif [[ -n "$BROWSER" && "$BROWSER" != "none" ]]; then
        COOKIE_ARGS=(--cookies-from-browser "$BROWSER")
    fi

    # Resolve real path (handles macOS /tmp → /private/tmp symlink and Linux equivalents)
    local real_out_dir
    real_out_dir=$(cd "$OUT_DIR" && pwd -P 2>/dev/null || echo "$OUT_DIR")

    log_info "⬇️  Downloading with gallery-dl → $real_out_dir" >&2

    # Snapshot of pre-existing webp files so we only convert newly downloaded ones
    local _snapshot
    _snapshot=$(mktemp)
    find "$real_out_dir" -maxdepth 1 -name "*.webp" 2>/dev/null > "$_snapshot"

    gallery-dl \
        "${COOKIE_ARGS[@]}" \
        --directory "$real_out_dir" \
        --filename "{filename}.{extension}" \
        -o 'postprocessors=[{"name":"metadata","mode":"custom","content-format":"{description}"}]' \
        "$URL"
    local rc=$?

    if [[ $rc -ne 0 ]]; then
        log_error "gallery-dl failed (exit $rc)." >&2
        log_error "If you get auth errors, make sure Chrome is open and try again, or use --cookies cookies.txt" >&2
        return $rc
    fi

    # Convert newly downloaded webp → jpg/png using ffmpeg (cross-platform)
    if [[ "$IMG_FORMAT" != "webp" ]]; then
        local _ffmpeg_bin
        _ffmpeg_bin=$(command -v ffmpeg 2>/dev/null)
        local converted=0
        while IFS= read -r webp_file; do
            grep -qxF "$webp_file" "$_snapshot" && continue  # skip pre-existing
            local out_file="${webp_file%.webp}.$IMG_FORMAT"
            if [[ -n "$_ffmpeg_bin" ]]; then
                "$_ffmpeg_bin" -y -i "$webp_file" "$out_file" -loglevel quiet 2>/dev/null && rm -f "$webp_file"
            else
                # fallback: sips on macOS
                sips --setProperty format "$SIPS_FORMAT" "$webp_file" --out "$out_file" &>/dev/null && rm -f "$webp_file"
            fi
            log_info "🖼️  $(basename "$out_file")" >&2
            converted=$((converted + 1))
        done < <(find "$real_out_dir" -maxdepth 1 -name "*.webp" 2>/dev/null)
        [[ $converted -gt 0 ]] && log_info "✅ $converted image(s) saved as .$IMG_FORMAT" >&2
    fi

    rm -f "$_snapshot"
    log_info "✅ Download complete." >&2
    return 0
}

# ── Help ──────────────────────────────────────────────────────────────────────

_download_help() {
    cat >&2 <<'EOF'
Usage: amir download <url> [options]

Download videos, reels, photos and carousels from YouTube, Instagram,
TikTok, Twitter/X, Vimeo, and 1000+ other sites.

  Video options (YouTube, TikTok, Twitter, Vimeo, ...):
    -R, --resolution <N>   Max height in pixels (default: 480)
    -F, --formats          List available resolutions before downloading
    -l, --get-link         Print direct stream URL (for download managers)
    --subtitle, -s         Generate subtitles with Whisper after download
    --yt-subs              Download YouTube's built-in subtitles
    --browser <name>       Browser for cookie auth (default: chrome)
    --cookies <file>       Netscape cookies.txt file
    --extreme              Fast mode: 360p, lower quality
    --normalize            Force transcoding to H.264/AAC for older macOS compatibility
    --po-token <token>     Pass GVS PO Token (e.g. web+XXX) for YouTube 720p+
    --yt-dlp-args <args>   Pass extra arguments directly to yt-dlp

  Instagram photo/carousel options:
    --format <fmt>         Image format: jpg (default), png, webp

Examples:
  amir download https://youtu.be/dQw4w9WgXcQ
  amir download https://www.instagram.com/p/ABC123/
  amir download https://www.instagram.com/p/ABC123/ --format png
  amir download https://www.instagram.com/reel/XYZ456/ -R 1080
  amir download https://twitter.com/user/status/123456
EOF
}
