#!/usr/bin/env bash
# amir download — universal media downloader
# Videos (YouTube, TikTok, Twitter/X, Vimeo, 1000+ sites): yt-dlp
# Instagram photo/carousel posts: gallery-dl (auto-installed if missing)

# Browser cookies are served from a small on-disk cache; see lib/cookie_cache.sh.
# Located via BASH_SOURCE rather than LIB_DIR so this file also works when it is
# sourced on its own (tests do exactly that).
if [[ -z "${_AMIR_COOKIE_CACHE_LOADED:-}" ]]; then
    _amir_cookie_cache_sh="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)/cookie_cache.sh"
    [[ -f "$_amir_cookie_cache_sh" ]] && source "$_amir_cookie_cache_sh"
    unset _amir_cookie_cache_sh
fi

# Sentinel exit code from _gallery_dl_download(): the Instagram cookie jar has
# no sessionid, so any further retry (with cookies, or falling back to
# yt-dlp) would hit the exact same login wall. _download_instagram() checks
# for this specific code to stop after the one explicit message instead of
# also trying yt-dlp and adding more noise.
_AMIR_IG_AUTH_REQUIRED=2

run_download() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _download_help
        return 0
    fi
    if [[ $# -eq 0 ]]; then
        _download_help
        return 0
    fi

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
            --refresh-cookies)
                # Consumed here only — yt-dlp/gallery-dl do not understand this
                # flag, so it must never reach PASSTHROUGH. video.sh's own
                # parser (line ~2984) does the same for the `amir video
                # download` entry point; this file has no direct dependency on
                # that one and must keep working standalone.
                export AMIR_REFRESH_COOKIES=1
                shift ;;
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
# Bash 3.2 has no namerefs, so the result is returned via two global arrays —
# read them immediately after calling this function:
#   RESOLVED_COOKIE_ARGS  — cookies to use on the FIRST attempt (explicit only)
#   FALLBACK_COOKIE_ARGS  — cookies to retry with if the anonymous attempt fails
#
# Anonymous-first policy: a download that needs no login always wins. A cookie
# jar without a valid session (e.g. Instagram mid/datr with no sessionid) still
# identifies the device to the site, which earns a login wall and a rate-limit
# on that device id — strictly worse than sending nothing. So only cookies the
# user asked for explicitly (--cookies / --browser) go on the first attempt;
# implicitly discovered ones (./cookies.txt, config cookies.file, default
# browser) are held back as the retry.
#
# Cookies read from a browser go through the cache in lib/cookie_cache.sh, so a
# repeat download of the same site reuses the jar on disk instead of unlocking
# the keychain and decrypting the profile again. Pass the URL to enable it; with
# no URL there is no site to scope the cache to and the browser is read directly.
_resolve_cookie_args() {
    local _cookies_file="$1"
    local _browser="${2:-${AMIR_DEFAULT_BROWSER:-chrome}}"
    local _browser_explicit="${3:-false}"
    local _url="${4:-}"

    local _global_cookies
    _global_cookies="${AMIR_COOKIES_FILE:-$(get_config "cookies" "file" "")}"

    RESOLVED_COOKIE_ARGS=()
    FALLBACK_COOKIE_ARGS=()

    if [[ "${AMIR_NO_COOKIES:-}" == "1" ]]; then
        return 0   # hard anonymous — no first attempt with cookies, no retry
    elif [[ -n "$_cookies_file" ]]; then
        RESOLVED_COOKIE_ARGS=(--cookies "$_cookies_file")
    elif [[ "$_browser_explicit" == "true" && "$_browser" == "none" ]]; then
        return 0   # explicit opt-out
    elif [[ "$_browser_explicit" == "true" && -n "$_browser" ]]; then
        _cookie_args_from_browser "$_browser" "$_url"
        RESOLVED_COOKIE_ARGS=("${BROWSER_COOKIE_ARGS[@]}")
    elif [[ -f "cookies.txt" ]]; then
        FALLBACK_COOKIE_ARGS=(--cookies "cookies.txt")
    elif [[ -n "$_global_cookies" && -f "$_global_cookies" ]]; then
        FALLBACK_COOKIE_ARGS=(--cookies "$_global_cookies")
    elif [[ -n "$_browser" && "$_browser" != "none" ]]; then
        # cached-only: this jar is for a retry that may never happen.
        _cookie_args_from_browser "$_browser" "$_url" cached-only
        FALLBACK_COOKIE_ARGS=("${BROWSER_COOKIE_ARGS[@]}")
    fi
}

# Thin wrapper so this file keeps working when cookie_cache.sh is absent: the
# cache is an optimisation, never a requirement.
_cookie_args_from_browser() {
    if type _browser_cookie_args &>/dev/null; then
        _browser_cookie_args "$1" "${2:-}" "${3:-refresh}"
    else
        BROWSER_COOKIE_ARGS=(--cookies-from-browser "$1")
    fi
}

# ── Instagram: probe for video formats, fall back to gallery-dl for photos ────

_classify_instagram_url() {
    local url="$1"; shift
    local -a cookie_args=("$@")

    local url_lower
    url_lower=$(printf '%s' "$url" | tr '[:upper:]' '[:lower:]')

    if [[ "$url_lower" =~ /(reel|reels|tv)(/|\?|$) ]]; then
        echo "video 1"
        return 0
    fi

    local probe_json
    probe_json=$(yt-dlp --no-playlist "${cookie_args[@]}" -J "$url" 2>/dev/null)

    local has_video="no"
    local item_count=1
    if [[ -n "$probe_json" ]]; then
        local probe_result
        probe_result=$(echo "$probe_json" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    entries=d.get('entries')
    count=len(entries) if isinstance(entries, list) else 1
    fmts=d.get('formats',[])
    has_video='yes' if any(f.get('vcodec','none') not in ('none','') and f.get('height') for f in fmts) else 'no'
    print(f'{has_video} {count}')
except Exception:
    print('unknown 1')
" 2>/dev/null)
        if [[ -n "$probe_result" ]]; then
            has_video="${probe_result%% *}"
            item_count="${probe_result##* }"
        fi
    fi
    [[ "$item_count" =~ ^[0-9]+$ ]] || item_count=1

    if [[ "$has_video" == "yes" ]]; then
        echo "video $item_count"
    else
        echo "photo $item_count"
    fi
}

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
    local BROWSER_EXPLICIT="false"
    local i=0
    while [[ $i -lt ${#ARGS[@]} ]]; do
        case "${ARGS[$i]}" in
            --browser|-b) BROWSER="${ARGS[$((i+1))]}"; BROWSER_EXPLICIT="true"; i=$((i+2)) ;;
            --cookies)    COOKIES_FILE="${ARGS[$((i+1))]}"; i=$((i+2)) ;;
            *) i=$((i+1)) ;;
        esac
    done

    # Anonymous-first: the probe classifies a public post fine without cookies,
    # and sending a session-less Instagram jar here is what triggers the login
    # wall in the first place. video_download() and _gallery_dl_download() each
    # retry with the implicit cookie jar on their own if the anonymous try fails.
    _resolve_cookie_args "$COOKIES_FILE" "$BROWSER" "$BROWSER_EXPLICIT" "$URL"
    local -a PROBE_COOKIE_ARGS=("${RESOLVED_COOKIE_ARGS[@]}")

    log_info "🔍 Probing Instagram URL..." >&2

    local target_type item_count
    read -r target_type item_count <<< "$(_classify_instagram_url "$URL" "${PROBE_COOKIE_ARGS[@]}")"
    [[ "$item_count" =~ ^[0-9]+$ ]] || item_count=1

    # Snapshot the output directory so a post's completeness can be judged by
    # what actually landed on disk, not by any single tool's own exit code —
    # yt-dlp fetches only the video item(s) of a multi-item carousel and still
    # reports success, silently dropping the rest.
    # Resolve the destination once, the same way _gallery_dl_download() does
    # (cd + pwd -P), and reuse this single value for the before/after
    # snapshots AND as the OUT_DIR handed to _gallery_dl_download(). Two
    # independent `pwd`-based resolutions (one here, one inside the callee)
    # is what let a stale/differently-resolved cwd snapshot the wrong
    # directory and make a fully successful download look like "0 of N".
    local _ig_out_dir _ig_before
    _ig_out_dir=$(cd "$(pwd)" 2>/dev/null && pwd -P 2>/dev/null || pwd)
    _ig_before=$(mktemp)
    find "$_ig_out_dir" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.mp4" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.webm" \) 2>/dev/null > "$_ig_before"

    local _ig_rc=0
    local _ig_auth_only=false

    if [[ "$target_type" == "video" ]]; then
        log_info "🎬 Reel/video detected — using yt-dlp..." >&2
        if ! video_download "${ARGS[@]}"; then
            log_warning "yt-dlp failed — falling back to gallery-dl..." >&2
            _gallery_dl_download "$URL" "$_ig_out_dir" "$BROWSER" "$COOKIES_FILE" "$IMG_FORMAT" "$KEEP_SOURCE_CODEC" "$BROWSER_EXPLICIT"
            _ig_rc=$?
            [[ $_ig_rc -eq $_AMIR_IG_AUTH_REQUIRED ]] && _ig_auth_only=true
        fi
    else
        log_info "📸 Photo/carousel post detected — using gallery-dl..." >&2
        _gallery_dl_download "$URL" "$_ig_out_dir" "$BROWSER" "$COOKIES_FILE" "$IMG_FORMAT" "$KEEP_SOURCE_CODEC" "$BROWSER_EXPLICIT"
        _ig_rc=$?
        if [[ $_ig_rc -eq $_AMIR_IG_AUTH_REQUIRED ]]; then
            _ig_auth_only=true
        elif [[ $_ig_rc -ne 0 && "$item_count" -le 1 ]]; then
            # yt-dlp cannot fetch photos at all, so a fallback is only worth
            # trying when this post is a single video/reel gallery-dl missed —
            # never for a multi-item carousel, which yt-dlp would just as
            # surely leave incomplete (video items only) while still exiting 0.
            log_warning "gallery-dl failed — falling back to yt-dlp..." >&2
            video_download "${ARGS[@]}"
            _ig_rc=$?
        fi
    fi

    if [[ "$_ig_auth_only" == true ]]; then
        # _gallery_dl_download already printed the one explicit login message —
        # a completeness warning on top of it would only add noise.
        rm -f "$_ig_before"
        return 1
    fi

    # `grep -vxFf` is not reliable across grep implementations when the
    # pattern file ($_ig_before) is empty (a fresh/empty destination dir,
    # i.e. nothing existed before this download): BSD grep (macOS) treats an
    # empty -f file as matching every line, which -v then excludes entirely
    # — a fully successful download into an empty directory would count as
    # 0 new files. `comm -13` on two sorted lists has no such edge case: an
    # empty "before" list simply means every "after" entry is new.
    local _ig_after _ig_before_sorted _ig_after_sorted _ig_new_count
    _ig_after=$(mktemp)
    find "$_ig_out_dir" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.mp4" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.webm" \) 2>/dev/null > "$_ig_after"
    _ig_before_sorted=$(mktemp)
    _ig_after_sorted=$(mktemp)
    sort "$_ig_before" > "$_ig_before_sorted"
    sort "$_ig_after" > "$_ig_after_sorted"
    _ig_new_count=$(comm -13 "$_ig_before_sorted" "$_ig_after_sorted" | wc -l | tr -d ' ')
    rm -f "$_ig_before" "$_ig_after" "$_ig_before_sorted" "$_ig_after_sorted"

    if [[ "$item_count" -gt 1 && "$_ig_new_count" -lt "$item_count" ]]; then
        log_error "⚠️  $_ig_new_count of $item_count items downloaded — the rest need a logged-in session (try --refresh-cookies)." >&2
        return 1
    fi

    return "$_ig_rc"
}

# ── gallery-dl wrapper ─────────────────────────────────────────────────────────

_gallery_dl_download() {
    local URL="$1"
    local OUT_DIR="${2:-.}"
    local BROWSER="${3:-chrome}"
    local COOKIES_FILE="${4:-}"
    local IMG_FORMAT="${5:-jpg}"   # jpg | png | webp (webp = no conversion)
    local KEEP_SOURCE_CODEC="${6:-false}"
    local BROWSER_EXPLICIT="${7:-false}"

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

    _resolve_cookie_args "$COOKIES_FILE" "$BROWSER" "$BROWSER_EXPLICIT" "$URL"
    local -a COOKIE_ARGS=("${RESOLVED_COOKIE_ARGS[@]}")
    local -a RETRY_COOKIE_ARGS=("${FALLBACK_COOKIE_ARGS[@]}")

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
        --filename "{username}_{post_shortcode}_{num}.{extension}" \
        -o 'postprocessors=[{"name":"metadata","mode":"custom","content-format":"{description}"}]' \
        "$URL"
    local rc=$?

    # Anonymous-first: the attempt above ran without cookies unless the user
    # asked for them. Only on failure do we spend the implicit cookie jar.
    if [[ $rc -ne 0 && "${RETRY_COOKIE_ARGS[0]:-}" == "--cookies-from-browser" ]]; then
        # The retry is actually happening, so reading the browser now pays for
        # itself: cache the jar and reuse it on the next download of this site.
        _cookie_args_from_browser "$BROWSER" "$URL"
        RETRY_COOKIE_ARGS=("${BROWSER_COOKIE_ARGS[@]}")
    fi

    if [[ $rc -ne 0 && ${#RETRY_COOKIE_ARGS[@]} -gt 0 ]]; then
        # A retry with a cookie jar that carries no `sessionid` is not really a
        # retry: it identifies the same anonymous device and fails the exact
        # same way, just louder (gallery-dl's own multi-line error output on
        # top of ours). Skip it and say the one thing that actually helps.
        local _retry_jar="" _has_session=true
        if [[ "${RETRY_COOKIE_ARGS[0]:-}" == "--cookies" ]]; then
            _retry_jar="${RETRY_COOKIE_ARGS[1]:-}"
            _cookie_jar_has_cookie "$_retry_jar" sessionid || _has_session=false
        elif [[ "${RETRY_COOKIE_ARGS[0]:-}" == "--cookies-from-browser" ]]; then
            # Extraction above found no usable jar at all — no cookies means
            # no session either.
            _has_session=false
        fi

        if [[ "$_has_session" == false ]]; then
            log_error "❌ Instagram: not logged in — sign into Chrome (Default profile), then:" >&2
            log_error "   amir download --refresh-cookies '$URL'" >&2
            rm -f "$_snapshot" "$_video_snapshot"
            return "$_AMIR_IG_AUTH_REQUIRED"
        fi

        log_info "↻ Anonymous attempt failed — retrying with cookies (${RETRY_COOKIE_ARGS[1]})..." >&2
        gallery-dl \
            "${RETRY_COOKIE_ARGS[@]}" \
            --directory "$real_out_dir" \
            --filename "{username}_{post_shortcode}_{num}.{extension}" \
            -o 'postprocessors=[{"name":"metadata","mode":"custom","content-format":"{description}"}]' \
            "$URL"
        rc=$?
    fi

    if [[ $rc -ne 0 ]]; then
        log_error "gallery-dl failed (exit $rc)." >&2
        log_error "Auth errors: this post likely needs a real login. Pass --cookies cookies.txt (exported while logged in), or --browser chrome with an Instagram session in that profile." >&2
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
                "$_ffmpeg_bin" -nostdin -y -i "$webp_file" "$out_file" -loglevel quiet 2>/dev/null && rm -f "$webp_file"
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
    usage_block >&2 <<'EOF'
Usage: amir download <url> [options]

Description:
  Download videos, reels, photos and carousels from YouTube, Instagram,
  TikTok, Twitter/X, Vimeo, and 1000+ other sites.

Options:
  Video options (YouTube, TikTok, Twitter, Vimeo, ...):
    -R, --resolution <N>   Max height in pixels (default: 480)
    -F, --formats          List available resolutions before downloading
    -l, --get-link         Print direct stream URL (for download managers)
    --subtitle, -s         Generate subtitles with Whisper after download
    --yt-subs              Download YouTube's built-in subtitles
    --browser <name>       Browser for cookie auth ('none' = never use cookies)
    --cookies <file>       Netscape cookies.txt file
    --refresh-cookies      Re-read the browser instead of the cached cookie jar
    --extreme              Fast mode: 360p, lower quality
    --normalize            Force transcoding to H.264/AAC/MP4 even if already compliant
    --keep-codec           Skip codec normalization; keep whatever the site served
    --po-token <token>     Pass GVS PO Token (e.g. web+XXX) for YouTube 720p+
    --yt-dlp-args <args>   Pass extra arguments directly to yt-dlp

  Auth policy — anonymous first (owner ruling 2026-09-05): a download that needs
  no login always wins, so cookies found implicitly (./cookies.txt, config
  cookies.file, default browser) are NOT sent on the first attempt; they are only
  used to retry after it fails. A session-less jar (e.g. Instagram mid/datr with
  no sessionid) still identifies the device to the site, which earns the login
  wall and a rate-limit on that id — strictly worse than sending nothing.
  Cookies you ask for explicitly (--cookies / --browser <name>) are used on the
  first attempt. --browser none, or AMIR_NO_COOKIES=1, forces full anonymity.
  For Instagram specifically: if the cached jar has no `sessionid`, amir prints
  one explicit "not logged in" message and stops — it will not retry with the
  same useless cookies or fall back to yt-dlp and add more noise.

  Cookie cache: reading cookies out of a browser decrypts the whole profile
  through the system keychain, so the jar for the site being downloaded is kept
  in ~/.amir/cookies (0600, one file per browser+site) and reused until it goes
  stale. The browser is opened again only when that jar is missing, older than
  the TTL, or holds nothing but expired cookies. Only the site's own cookies are
  cached, never the whole browser jar. Knobs: --refresh-cookies (re-read now),
  AMIR_COOKIE_CACHE_TTL (seconds, default 43200), AMIR_NO_COOKIE_CACHE=1 (off),
  AMIR_COOKIE_CACHE_DIR (elsewhere).

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
