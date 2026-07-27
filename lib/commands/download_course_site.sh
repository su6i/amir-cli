#!/bin/bash
# amir download — private course-site handler (owner-purchased content only).
# Site hostnames are intentionally NOT hardcoded here; they come from
# AMIR_COURSE_SITE_DOMAINS (.env) or course_site.domains (~/.amir/config.yaml).
# Auth comes exclusively from the owner's own browser cookies — see WO-amir-cli-0007.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="${LIB_DIR:-$(dirname "$SCRIPT_DIR")}"
if ! type log_info &>/dev/null && [[ -f "$LIB_DIR/amir_lib.sh" ]]; then source "$LIB_DIR/amir_lib.sh"; fi
if ! type get_config &>/dev/null; then
    if [[ -f "$LIB_DIR/config.sh" ]]; then source "$LIB_DIR/config.sh"; else get_config() { echo "$3"; }; fi
fi
if ! type sanitize_terminal_filename_stem &>/dev/null && [[ -f "$LIB_DIR/commands/video.sh" ]]; then source "$LIB_DIR/commands/video.sh"; fi

# 1. _course_site_check_drm_in_file FILE
_course_site_check_drm_in_file() {
    local file="$1"
    grep -qiE 'widevine|playready|clearkey|EXT-X-KEY:METHOD=SAMPLE-AES|com\.apple\.fps' "$file"
}

# 2. _course_site_extract_video_url FILE BASE_URL
_course_site_extract_video_url() {
    local file="$1"
    local base_url="$2"
    local hosts
    hosts=$(get_config "course_site" "video_hosts" "youtube.com,youtu.be,vimeo.com")
    python3 - "$file" "$base_url" "$hosts" <<'PY'
import sys, re
from urllib.parse import urlparse, urljoin

file_path = sys.argv[1]
base_url = sys.argv[2]
hosts_csv = sys.argv[3]

with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
    html_content = f.read()

# a. <video>/<source src="..."> ending .mp4 or .m3u8
a_matches = re.findall(r'<(?:video|source)[^>]+src=[\'"]([^\'"]+)[\'"]', html_content, re.IGNORECASE)
for src in a_matches:
    if re.search(r'\.(?:mp4|m3u8)(?:\?|$)', src, re.IGNORECASE):
        print(urljoin(base_url, src))
        sys.exit(0)

# b. <iframe src="..."> host in hosts
host_list = [h.strip().lower() for h in hosts_csv.split(',')]
b_matches = re.findall(r'<iframe[^>]+src=[\'"]([^\'"]+)[\'"]', html_content, re.IGNORECASE)
for src in b_matches:
    full_url = urljoin(base_url, src)
    host = urlparse(full_url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for h in host_list:
        if h.startswith("www."):
            h = h[4:]
        if host == h or host.endswith("." + h):
            print(full_url)
            sys.exit(0)

# c. bare https://...mp4 or https://...m3u8
c_matches = re.search(r'https?://[^\'"<>\s]+\.(?:mp4|m3u8)(?:\?[^\'"<>\s]+)?', html_content, re.IGNORECASE)
if c_matches:
    print(c_matches.group(0))
    sys.exit(0)

# d. data-src=/data-video=/data-url= containing http(s)
d_matches = re.findall(r'data-(?:src|video|url)=[\'"]([^\'"]+)[\'"]', html_content, re.IGNORECASE)
for src in d_matches:
    if src.lower().startswith('http://') or src.lower().startswith('https://'):
        print(urljoin(base_url, src))
        sys.exit(0)

sys.exit(1)
PY
}

# 3. _course_site_extract_lesson_links FILE BASE_URL
_course_site_extract_lesson_links() {
    local file="$1"
    local base_url="$2"
    local pattern
    # /product/ deliberately excluded from the default — see lib/config.sh note
    # (on the site this was validated against it is the course-landing-page scheme,
    # and matched this site's own nav/related-product links in a live smoke test).
    pattern=$(get_config "course_site" "lesson_link_pattern" "/lesson/|/course/|/topic/")
    python3 - "$file" "$base_url" "$pattern" <<'PY'
import sys, re, html
from urllib.parse import urlparse, urljoin

file_path = sys.argv[1]
base_url = sys.argv[2]
pattern = sys.argv[3]

try:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
except Exception:
    sys.exit(1)

base_parsed = urlparse(base_url)
base_host = base_parsed.netloc.lower()
if base_host.startswith("www."):
    base_host = base_host[4:]

seen = set()
for match in re.finditer(r'<a\s+[^>]*href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>', content, re.IGNORECASE | re.DOTALL):
    href = match.group(1)
    text = match.group(2)
    
    full_url = urljoin(base_url, href)
    parsed = urlparse(full_url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
        
    if host != base_host:
        continue
        
    if not re.search(pattern, full_url, re.IGNORECASE):
        continue
        
    if full_url not in seen:
        seen.add(full_url)
        clean_text = re.sub(r'<[^>]+>', '', text)
        clean_text = html.unescape(clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        print(f"{full_url}\t{clean_text}")
PY
}

# 4. _course_site_classify_page FILE BASE_URL
_course_site_classify_page() {
    local file="$1"
    local base_url="$2"
    
    local blocked=0
    if grep -qiE 'single_add_to_cart_button|add_to_cart|digits-login|digits_mobile_no' "$file" || grep -qiE '<form[^>]*login' "$file"; then
        blocked=1
    fi
    
    local links
    links=$(_course_site_extract_lesson_links "$file" "$base_url")
    if [[ -n "$links" ]]; then
        echo "course"
        return 0
    fi
    
    if [[ $blocked -eq 1 ]]; then
        echo "not_purchased"
        return 0
    fi
    
    local video
    video=$(_course_site_extract_video_url "$file" "$base_url")
    if [[ -n "$video" ]]; then
        echo "single"
        return 0
    fi
    
    echo "not_purchased"
}

# 5. _course_site_sanitize_title TITLE
_course_site_sanitize_title() {
    local title="$1"
    local cleaned
    cleaned="$(sanitize_terminal_filename_stem "$title")"
    python3 -c 'import sys; print(sys.argv[1][:120])' "$cleaned"
}

# 6. _course_site_zero_pad_name INDEX TOTAL TITLE
_course_site_zero_pad_name() {
    local index="$1"
    local total="$2"
    local title="$3"
    
    local width=${#total}
    [[ $width -lt 2 ]] && width=2
    
    local padded
    padded=$(printf "%0${width}d" "$index")
    echo "$padded - $title"
}

# 7. _course_site_resolve_cookie_jar COOKIES_FILE BROWSER
_course_site_resolve_cookie_jar() {
    local COOKIES_FILE="$1"
    local BROWSER="$2"
    
    if [[ -n "$COOKIES_FILE" && -f "$COOKIES_FILE" ]]; then
        COURSE_SITE_COOKIE_JAR="$COOKIES_FILE"
        COURSE_SITE_COOKIE_JAR_IS_TEMP=false
        return 0
    elif [[ -f "./cookies.txt" ]]; then
        COURSE_SITE_COOKIE_JAR="./cookies.txt"
        COURSE_SITE_COOKIE_JAR_IS_TEMP=false
        return 0
    elif [[ -f "$HOME/su6i-yar/cookies.txt" ]]; then
        COURSE_SITE_COOKIE_JAR="$HOME/su6i-yar/cookies.txt"
        COURSE_SITE_COOKIE_JAR_IS_TEMP=false
        return 0
    else
        local tmpjar
        tmpjar=$(mktemp)
        if _course_site_export_cookie_jar "$BROWSER" "$tmpjar"; then
            COURSE_SITE_COOKIE_JAR="$tmpjar"
            COURSE_SITE_COOKIE_JAR_IS_TEMP=true
            return 0
        else
            log_error "Could not read browser cookies — pass --cookies cookies.txt"
            rm -f "$tmpjar"
            return 1
        fi
    fi
}

# 8. _course_site_export_cookie_jar BROWSER OUT_JAR
_course_site_export_cookie_jar() {
    local BROWSER="$1"
    local OUT_JAR="$2"
    python3 - "$BROWSER" "$OUT_JAR" <<'PY'
import sys, http.cookiejar
try:
    from yt_dlp.cookies import extract_cookies_from_browser
    browser = sys.argv[1]
    out_jar = sys.argv[2]
    extracted = extract_cookies_from_browser(browser)
    jar = http.cookiejar.MozillaCookieJar(out_jar)
    for c in extracted:
        jar.set_cookie(c)
    jar.save(ignore_discard=True, ignore_expires=True)
except Exception as e:
    print(f"Cookie extraction failed: {e}", file=sys.stderr)
    sys.exit(1)
PY
}

# 9. _course_site_fetch_page URL JAR OUT_FILE
_course_site_fetch_page() {
    local URL="$1"
    local JAR="$2"
    local OUT_FILE="$3"
    curl -sSL --max-time 30 -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36" -b "$JAR" -o "$OUT_FILE" -w '%{http_code}' "$URL"
}

# 10. _course_site_download_one URL DEST_STEM
_course_site_download_one() {
    local URL="$1"
    local DEST_STEM="$2"
    local lower_url
    lower_url=$(echo "$URL" | tr '[:upper:]' '[:lower:]')
    
    if [[ "${lower_url%%\?*}" == *.m3u8 ]]; then
        local manifest_tmp
        manifest_tmp=$(mktemp)
        curl -sSL --max-time 30 -b "$COURSE_SITE_COOKIE_JAR" -o "$manifest_tmp" "$URL"
        if _course_site_check_drm_in_file "$manifest_tmp"; then
            log_error "DRM detected (SAMPLE-AES/widevine/playready/clearkey) — aborting. This tool does not implement DRM key handling."
            rm -f "$manifest_tmp"
            return 3
        fi
        rm -f "$manifest_tmp"
    fi
    
    local pathfile
    pathfile=$(mktemp)
    yt-dlp "${RESOLVED_COOKIE_ARGS[@]}" --newline --continue --no-overwrites --restrict-filenames \
        -o "${DEST_STEM}.%(ext)s" --merge-output-format mp4 \
        --print "after_move:filepath" "$URL" > "$pathfile" 2>&1
    local rc=$?
    
    if [[ $rc -eq 0 ]]; then
        awk 'NF{s=$0} END{print s}' "$pathfile"
        rm -f "$pathfile"
        return 0
    else
        log_error "yt-dlp failed (exit $rc) for $URL"
        rm -f "$pathfile"
        return $rc
    fi
}

# 11. _download_course_site
_download_course_site() {
    local URL=""
    local COOKIES_FILE=""
    local BROWSER="${AMIR_DEFAULT_BROWSER:-chrome}"
    local FORCE=false
    local KEEP_CODEC=false
    local FORCE_NORMALIZE=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --cookies) COOKIES_FILE="$2"; shift 2 ;;
            --browser) BROWSER="$2"; shift 2 ;;
            --force) FORCE=true; shift ;;
            --keep-codec) KEEP_CODEC=true; shift ;;
            --normalize) FORCE_NORMALIZE=true; shift ;;
            *)
                if [[ -z "$URL" && "$1" =~ ^https?:// ]]; then
                    URL="$1"
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$URL" ]]; then
        log_error "A course or lesson URL is required."
        return 1
    fi

    local OUT_DIR
    OUT_DIR="$(pwd)"
    
    _resolve_cookie_args "$COOKIES_FILE" "$BROWSER"
    _course_site_resolve_cookie_jar "$COOKIES_FILE" "$BROWSER" || return 1
    
    local main_page
    main_page=$(mktemp)
    local http_code
    http_code=$(_course_site_fetch_page "$URL" "$COURSE_SITE_COOKIE_JAR" "$main_page")
    if [[ "$http_code" != 2* ]]; then
        log_error "Could not fetch page (HTTP ${http_code:-?})."
        rm -f "$main_page"
        [[ "$COURSE_SITE_COOKIE_JAR_IS_TEMP" == true ]] && rm -f "$COURSE_SITE_COOKIE_JAR"
        return 1
    fi
    
    if _course_site_check_drm_in_file "$main_page"; then
        log_error "DRM detected on this page (SAMPLE-AES/widevine/playready/clearkey) — aborting. This tool does not implement DRM key handling."
        rm -f "$main_page"
        [[ "$COURSE_SITE_COOKIE_JAR_IS_TEMP" == true ]] && rm -f "$COURSE_SITE_COOKIE_JAR"
        return 1
    fi

    local kind
    kind=$(_course_site_classify_page "$main_page" "$URL")
    if [[ "$kind" == "not_purchased" ]]; then
        log_error "Not logged in, or this course is not in your purchases."
        rm -f "$main_page"
        [[ "$COURSE_SITE_COOKIE_JAR_IS_TEMP" == true ]] && rm -f "$COURSE_SITE_COOKIE_JAR"
        return 2
    fi
    
    local PAGE_TITLE
    PAGE_TITLE=$(python3 -c '
import sys, re, html
try:
    with open(sys.argv[1], "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", content, re.IGNORECASE | re.DOTALL)
    if not m:
        m = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    if m:
        text = re.sub(r"<[^>]+>", "", m.group(1))
        print(html.unescape(text).strip())
    else:
        print("")
except Exception:
    print("")
' "$main_page")
    
    PAGE_TITLE=$(_course_site_sanitize_title "$PAGE_TITLE")
    [[ -z "$PAGE_TITLE" ]] && PAGE_TITLE="course"
    
    local -a items=()
    local DEST_DIR=""
    if [[ "$kind" == "course" ]]; then
        while IFS= read -r line; do
            [[ -n "$line" ]] && items+=("$line")
        done < <(_course_site_extract_lesson_links "$main_page" "$URL")
        DEST_DIR="$OUT_DIR/$(_course_site_sanitize_title "$PAGE_TITLE")"
        mkdir -p "$DEST_DIR"
    elif [[ "$kind" == "single" ]]; then
        items+=("$URL"$'\t'"$PAGE_TITLE")
        DEST_DIR="$OUT_DIR"
    fi
    
    local ok=0
    local failed=0
    local total=${#items[@]}
    local i
    
    for (( i=1; i<=total; i++ )); do
        local item="${items[$((i-1))]}"
        local lesson_url="${item%%$'\t'*}"
        local lesson_title="${item#*$'\t'}"
        
        local sanitized_title
        sanitized_title=$(_course_site_sanitize_title "$lesson_title")
        
        local stem
        stem="$DEST_DIR/$(_course_site_zero_pad_name "$i" "$total" "$sanitized_title")"
        
        local existing_file=false
        if [[ "$FORCE" != true ]]; then
            for f in "${stem}".*; do
                if [[ -e "$f" ]]; then
                    existing_file=true
                    break
                fi
            done
        fi
        
        if [[ "$existing_file" == true ]]; then
            log_info "⏭️  [$i/$total] Skipping (exists): $lesson_title"
            ok=$((ok + 1))
            continue
        fi
        
        local video_url=""
        if [[ "$kind" == "course" ]]; then
            local tmp_lesson
            tmp_lesson=$(mktemp)
            _course_site_fetch_page "$lesson_url" "$COURSE_SITE_COOKIE_JAR" "$tmp_lesson" >/dev/null
            if _course_site_check_drm_in_file "$tmp_lesson"; then
                log_error "[$i/$total] DRM detected on lesson page — aborting entire run. This tool does not implement DRM key handling."
                rm -f "$tmp_lesson" "$main_page"
                [[ "$COURSE_SITE_COOKIE_JAR_IS_TEMP" == true ]] && rm -f "$COURSE_SITE_COOKIE_JAR"
                return 1
            fi
            video_url=$(_course_site_extract_video_url "$tmp_lesson" "$lesson_url")
            rm -f "$tmp_lesson"
        elif [[ "$kind" == "single" ]]; then
            video_url=$(_course_site_extract_video_url "$main_page" "$URL")
        fi
        
        if [[ -z "$video_url" ]]; then
            log_error "[$i/$total] No video found for: $lesson_title"
            failed=$((failed + 1))
            continue
        fi
        
        log_info "⬇️  [$i/$total] $lesson_title"
        
        local downloaded_file
        downloaded_file=$(_course_site_download_one "$video_url" "$stem")
        local dl_rc=$?
        
        if [[ $dl_rc -ne 0 ]]; then
            log_error "[$i/$total] Download failed for: $lesson_title"
            failed=$((failed + 1))
            continue
        fi
        
        if [[ "$KEEP_CODEC" != true ]]; then
            ensure_mac_playable_video "$downloaded_file" "$FORCE_NORMALIZE"
        fi
        ok=$((ok + 1))
    done
    
    rm -f "$main_page"
    [[ "$COURSE_SITE_COOKIE_JAR_IS_TEMP" == true ]] && rm -f "$COURSE_SITE_COOKIE_JAR"
    
    if [[ $ok -eq $total && $total -gt 0 ]]; then
        log_info "✅ $ok/$total videos downloaded"
        return 0
    else
        log_error "$ok/$total videos downloaded (${failed:-0} failed)"
        return 1
    fi
}
