#!/usr/bin/env bash
# amir download — universal media downloader
# Videos (YouTube, TikTok, Twitter/X, Vimeo, 1000+ sites): yt-dlp
# Instagram photo/carousel posts: gallery-dl (auto-installed if missing)

run_download() {
    source "$LIB_DIR/commands/video.sh"

    # Extract URL from args (first https:// token)
    local URL=""
    for arg in "$@"; do
        [[ "$arg" =~ ^https?:// ]] && URL="$arg" && break
    done

    if [[ -z "$URL" ]]; then
        _download_help
        return 1
    fi

    if [[ "$URL" =~ (instagram\.com|instagr\.am) ]]; then
        _download_instagram "$@"
    else
        video_download "$@"
    fi
}

# ── Instagram: probe for video formats, fall back to gallery-dl for photos ────

_download_instagram() {
    local URL=""
    local -a EXTRA_ARGS=("$@")

    for arg in "$@"; do
        [[ "$arg" =~ ^https?:// ]] && URL="$arg" && break
    done

    # Parse --browser / --cookies from caller args (forwarded to gallery-dl if needed)
    local BROWSER="${AMIR_DEFAULT_BROWSER:-chrome}"
    local COOKIES_FILE=""
    local i=0
    while [[ $i -lt ${#EXTRA_ARGS[@]} ]]; do
        case "${EXTRA_ARGS[$i]}" in
            --browser|-b) BROWSER="${EXTRA_ARGS[$((i+1))]}"; i=$((i+2)) ;;
            --cookies)    COOKIES_FILE="${EXTRA_ARGS[$((i+1))]}"; i=$((i+2)) ;;
            *) i=$((i+1)) ;;
        esac
    done

    log_info "🔍 Probing Instagram URL..." >&2

    # Quick probe: check if yt-dlp finds any video formats
    local probe_json
    probe_json=$(yt-dlp --no-playlist -J "$URL" 2>/dev/null)

    local has_video="no"
    if [[ -n "$probe_json" ]]; then
        has_video=$(echo "$probe_json" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    fmts=d.get('formats',[])
    has=(any(f.get('vcodec','none') not in ('none','') and f.get('height') for f in fmts))
    print('yes' if has else 'no')
except:
    print('unknown')
" 2>/dev/null)
    fi

    if [[ "$has_video" == "yes" ]]; then
        log_info "🎬 Reel/video detected — using yt-dlp..." >&2
        video_download "$@"
    else
        log_info "📸 Photo/carousel post detected — using gallery-dl..." >&2
        _gallery_dl_download "$URL" "$(pwd)" "$BROWSER" "$COOKIES_FILE"
    fi
}

# ── gallery-dl wrapper ─────────────────────────────────────────────────────────

_gallery_dl_download() {
    local URL="$1"
    local OUT_DIR="${2:-.}"
    local BROWSER="${3:-chrome}"
    local COOKIES_FILE="${4:-}"

    # Auto-install gallery-dl if missing
    if ! command -v gallery-dl &>/dev/null; then
        log_info "📦 gallery-dl not found — installing via uv tool..." >&2
        if ! uv tool install gallery-dl 2>&1; then
            log_error "Failed to install gallery-dl." >&2
            log_error "Install manually: uv tool install gallery-dl" >&2
            return 1
        fi
        log_info "✅ gallery-dl installed." >&2
    fi

    local -a COOKIE_ARGS=()

    # Cookie resolution (same priority as yt-dlp in video.sh)
    if [[ -n "$COOKIES_FILE" ]]; then
        COOKIE_ARGS=(--cookies "$COOKIES_FILE")
    elif [[ -f "cookies.txt" ]]; then
        COOKIE_ARGS=(--cookies "cookies.txt")
    elif [[ -f "$HOME/su6i-yar/cookies.txt" ]]; then
        COOKIE_ARGS=(--cookies "$HOME/su6i-yar/cookies.txt")
    elif [[ -n "$BROWSER" && "$BROWSER" != "none" ]]; then
        COOKIE_ARGS=(--cookies-from-browser "$BROWSER")
    fi

    log_info "⬇️  Downloading with gallery-dl → $OUT_DIR" >&2

    gallery-dl \
        "${COOKIE_ARGS[@]}" \
        --directory "$OUT_DIR" \
        --filename "{filename}.{extension}" \
        "$URL"
    local rc=$?
    if [[ $rc -eq 0 ]]; then
        log_info "✅ Download complete." >&2
    else
        log_error "gallery-dl failed (exit $rc)." >&2
        log_error "If you get auth errors, make sure Chrome is open and try again, or use --cookies cookies.txt" >&2
    fi
    return $rc
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

  Instagram:
    Photo/carousel posts   → gallery-dl (auto-installed if missing)
    Reels / videos         → yt-dlp (same options as above)

Examples:
  amir download https://youtu.be/dQw4w9WgXcQ
  amir download https://www.instagram.com/p/ABC123/
  amir download https://www.instagram.com/reel/XYZ456/ -R 1080
  amir download https://twitter.com/user/status/123456
EOF
}
