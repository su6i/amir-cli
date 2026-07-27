#!/usr/bin/env bash
# amir download — universal media downloader
# Videos (YouTube, TikTok, Twitter/X, Vimeo, 1000+ sites): yt-dlp
# Instagram photo/carousel posts: gallery-dl (auto-installed if missing)

run_download() {
    source "$LIB_DIR/commands/video.sh"
    source "$LIB_DIR/commands/download_course_site.sh"

    # Extract URL and --format flag before delegating
    local URL=""
    local IMG_FORMAT="jpg"
    local KEEP_SOURCE_CODEC=false
    local -a PASSTHROUGH=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --format|-f)
                IMG_FORMAT="$2"; shift 2 ;;
            --keep-codec)
                # video_download() (yt-dlp path) parses --keep-codec itself from
                # PASSTHROUGH, so it must stay in the array; we also capture it
                # here to gate the gallery-dl (Instagram photo/carousel) path,
                # which does not forward arbitrary args to the gallery-dl binary.
                KEEP_SOURCE_CODEC=true
                PASSTHROUGH+=("$1"); shift ;;
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
        _download_instagram "$IMG_FORMAT" "$KEEP_SOURCE_CODEC" "${PASSTHROUGH[@]}"
    elif _url_is_course_site "$URL"; then
        _download_course_site "${PASSTHROUGH[@]}"
    else
        video_download "${PASSTHROUGH[@]}"
    fi
}

# ── Private course-site routing ───────────────────────────────────────────────
# The sites handled by the course-site path are NOT named in this repository.
# Configure them locally, outside version control, in either:
#   .env                  → AMIR_COURSE_SITE_DOMAINS="host1.tld,host2.tld"
#   ~/.amir/config.yaml   → course_site: { domains: host1.tld,host2.tld }
# Unset means the path stays inert and every URL goes to the normal yt-dlp flow.
_url_is_course_site() {
    local _url="$1"
    local _domains _d
    _domains="${AMIR_COURSE_SITE_DOMAINS:-$(get_config "course_site" "domains" "")}"
    [[ -z "$_domains" ]] && return 1

    local _oldifs="$IFS"
    IFS=','
    for _d in $_domains; do
        _d=$(printf '%s' "$_d" | tr -d '[:space:]')
        [[ -z "$_d" ]] && continue
        # Escape dots so a configured host matches literally, not as a wildcard.
        local _re
        _re=$(printf '%s' "$_d" | sed 's/\./\\./g')
        if [[ "$_url" =~ (^|https?://|\.)${_re}(/|$|:) ]]; then
            IFS="$_oldifs"
            return 0
        fi
    done
    IFS="$_oldifs"
    return 1
}

# ── Shared cookie resolution (yt-dlp-style) ────────────────────────────────────
# Bash 3.2 has no namerefs, so the result is returned via the global array
# RESOLVED_COOKIE_ARGS — read it immediately after calling this function.
# Order: --cookies <file> → ./cookies.txt → $HOME/su6i-yar/cookies.txt →
#        --cookies-from-browser $BROWSER (default: $AMIR_DEFAULT_BROWSER, else chrome).
_resolve_cookie_args() {
    local _cookies_file="$1"
    local _browser="${2:-${AMIR_DEFAULT_BROWSER:-chrome}}"
    RESOLVED_COOKIE_ARGS=()
    if [[ -n "$_cookies_file" ]]; then
        RESOLVED_COOKIE_ARGS=(--cookies "$_cookies_file")
    elif [[ -f "cookies.txt" ]]; then
        RESOLVED_COOKIE_ARGS=(--cookies "cookies.txt")
    elif [[ -f "$HOME/su6i-yar/cookies.txt" ]]; then
        RESOLVED_COOKIE_ARGS=(--cookies "$HOME/su6i-yar/cookies.txt")
    elif [[ -n "$_browser" && "$_browser" != "none" ]]; then
        RESOLVED_COOKIE_ARGS=(--cookies-from-browser "$_browser")
    fi
}

# ── Instagram: probe for video formats, fall back to gallery-dl for photos ────

_download_instagram() {
    local IMG_FORMAT="$1"; shift
    local KEEP_SOURCE_CODEC="$1"; shift
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

    _resolve_cookie_args "$COOKIES_FILE" "$BROWSER"
    local -a PROBE_COOKIE_ARGS=("${RESOLVED_COOKIE_ARGS[@]}")

    log_info "🔍 Probing Instagram URL..." >&2

    local probe_json
    probe_json=$(yt-dlp --no-playlist "${PROBE_COOKIE_ARGS[@]}" -J "$URL" 2>/dev/null)

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
        _gallery_dl_download "$URL" "$(pwd)" "$BROWSER" "$COOKIES_FILE" "$IMG_FORMAT" "$KEEP_SOURCE_CODEC"
    fi
}

# ── gallery-dl wrapper ─────────────────────────────────────────────────────────

_gallery_dl_download() {
    local URL="$1"
    local OUT_DIR="${2:-.}"
    local BROWSER="${3:-chrome}"
    local COOKIES_FILE="${4:-}"
    local IMG_FORMAT="${5:-jpg}"   # jpg | png | webp (webp = no conversion)
    local KEEP_SOURCE_CODEC="${6:-false}"

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

    _resolve_cookie_args "$COOKIES_FILE" "$BROWSER"
    local -a COOKIE_ARGS=("${RESOLVED_COOKIE_ARGS[@]}")

    # Resolve real path (handles macOS /tmp → /private/tmp symlink and Linux equivalents)
    local real_out_dir
    real_out_dir=$(cd "$OUT_DIR" && pwd -P 2>/dev/null || echo "$OUT_DIR")

    log_info "⬇️  Downloading with gallery-dl → $real_out_dir" >&2

    # Snapshot of pre-existing webp/video files so we only touch newly downloaded ones
    local _snapshot _video_snapshot
    _snapshot=$(mktemp)
    _video_snapshot=$(mktemp)
    find "$real_out_dir" -maxdepth 1 -name "*.webp" 2>/dev/null > "$_snapshot"
    find "$real_out_dir" -maxdepth 1 \( -name "*.mp4" -o -name "*.mov" -o -name "*.mkv" -o -name "*.webm" \) 2>/dev/null > "$_video_snapshot"

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

    # Normalize newly downloaded video items (carousel posts can mix photos + reels;
    # gallery-dl saves those raw — often vp9/av1 in mp4, unplayable in QuickTime).
    if [[ "$KEEP_SOURCE_CODEC" == true ]]; then
        log_info "⏭️  --keep-codec: skipping macOS-playback normalization for downloaded videos." >&2
    else
        local normalized=0
        while IFS= read -r video_file; do
            grep -qxF "$video_file" "$_video_snapshot" && continue  # skip pre-existing
            ensure_mac_playable_video "$video_file" && normalized=$((normalized + 1))
        done < <(find "$real_out_dir" -maxdepth 1 \( -name "*.mp4" -o -name "*.mov" -o -name "*.mkv" -o -name "*.webm" \) 2>/dev/null)
        [[ $normalized -gt 0 ]] && log_info "✅ $normalized video(s) verified/normalized for macOS playback" >&2
    fi

    rm -f "$_video_snapshot"
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
    --normalize            Force transcoding to H.264/AAC/MP4 even if already compliant
    --keep-codec           Skip codec normalization; keep whatever the site served
    --po-token <token>     Pass GVS PO Token (e.g. web+XXX) for YouTube 720p+
    --yt-dlp-args <args>   Pass extra arguments directly to yt-dlp

  Output codec policy (default: H.264/AAC/MP4 for every download, owner ruling
  2026-07-27): configurable via ~/.amir/config.yaml under the `codec:` section
  (keep_video / keep_audio accept comma lists of source codecs to leave as-is).

  Instagram photo/carousel options:
    --format <fmt>         Image format: jpg (default), png, webp

  Private course sites (courses YOU purchased — needs your logged-in session):
    Enable by listing your hostnames in AMIR_COURSE_SITE_DOMAINS (.env) or
    course_site.domains (~/.amir/config.yaml). Unset = disabled.
    Accepts a single lesson URL or a whole course page (all lessons, in order).
    Never bypasses a login or paywall; aborts outright if DRM is detected.
    --force                 Re-download lessons even if the target file already exists
    (also honors --browser, --cookies, --keep-codec, --normalize above)

Examples:
  amir download https://youtu.be/dQw4w9WgXcQ
  amir download https://www.instagram.com/p/ABC123/
  amir download https://www.instagram.com/p/ABC123/ --format png
  amir download https://www.instagram.com/reel/XYZ456/ -R 1080
  amir download https://twitter.com/user/status/123456
EOF
}
