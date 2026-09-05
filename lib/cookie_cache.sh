#!/usr/bin/env bash
# ==============================================================================
# Browser cookie cache
# ==============================================================================
# Pulling cookies straight out of Chrome is not free: every call decrypts the
# whole profile through the system keychain, and on a locked keychain it puts a
# GUI prompt in front of a command that was supposed to be unattended. The jar
# barely changes between two downloads of the same site, so paying that cost per
# invocation is waste.
#
# This module keeps the last extraction in a small per-site jar under
# ~/.amir/cookies and goes back to the browser only when that jar is missing,
# older than the TTL, or holds nothing but expired cookies.
#
# The cache is scoped to the site being downloaded: a YouTube download caches
# YouTube's (and Google's) cookies, nothing else. A full jar on disk would mean
# plaintext session cookies for every site the browser has ever logged into —
# the browser keeps those encrypted, and this cache has no business undoing
# that. Cache files are 0600 inside a 0700 directory.
#
# Knobs:
#   AMIR_COOKIE_CACHE_DIR    where jars live      (default ~/.amir/cookies)
#   AMIR_COOKIE_CACHE_TTL    seconds             (default 43200 = 12h, 0 = off)
#   AMIR_NO_COOKIE_CACHE=1   bypass entirely, read the browser every time
#   AMIR_REFRESH_COOKIES=1   ignore the cached jar once and re-extract
# ==============================================================================

_AMIR_COOKIE_CACHE_LOADED=1

_cookie_cache_dir() {
    local dir="${AMIR_COOKIE_CACHE_DIR:-${AMIR_CONFIG_DIR:-$HOME/.amir}/cookies}"
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir" 2>/dev/null || return 1
    fi
    chmod 700 "$dir" 2>/dev/null
    printf '%s' "$dir"
}

_cookie_cache_ttl() {
    local ttl="${AMIR_COOKIE_CACHE_TTL:-}"
    if [[ -z "$ttl" ]] && type get_config &>/dev/null; then
        ttl=$(get_config "cookies" "cache_ttl" "")
    fi
    [[ "$ttl" =~ ^[0-9]+$ ]] || ttl=43200
    printf '%s' "$ttl"
}

# _cookie_scope_domains URL — the domains worth caching for this URL.
# Prints a space-separated list whose FIRST entry is the site itself (matched
# with its subdomains) and whose remaining entries are sibling domains matched
# exactly. The distinction matters: YouTube's auth needs the account cookie on
# `.google.com`, but nothing needs mail.google.com's session — and a jar on disk
# should hold the least it can get away with.
# Returns 1 when the URL yields no host, in which case the caller must fall back
# to reading the browser directly rather than guess a scope.
_cookie_scope_domains() {
    local url="$1"
    local host="${url#*://}"
    host="${host%%/*}"
    host="${host%%\?*}"
    host="${host%%#*}"
    host="${host%%:*}"
    host=$(printf '%s' "$host" | tr '[:upper:]' '[:lower:]')
    host="${host#www.}"
    [[ -n "$host" && "$host" == *.* ]] || return 1

    # Registrable domain: the last two labels. Good enough for the sites this
    # CLI downloads from; a miss only widens or narrows the cache scope, it
    # never sends a cookie anywhere it would not already have gone.
    local reg
    reg=$(printf '%s' "$host" | awk -F. '{ print $(NF-1)"."$NF }')

    # A site's login often lives on a sibling domain, and yt-dlp still only
    # sends each cookie to its own domain — listing a sibling here widens what
    # gets cached, not what gets transmitted.
    case "$reg" in
        youtube.com|youtu.be) printf 'youtube.com youtu.be google.com googlevideo.com' ;;
        instagram.com)        printf 'instagram.com cdninstagram.com facebook.com' ;;
        x.com|twitter.com)    printf 'x.com twitter.com twimg.com' ;;
        *)                    printf '%s' "$reg" ;;
    esac
}

# _cookie_jar_has_live_cookie FILE — true when at least one cookie is still
# valid. Expiry 0 means a session cookie, which never goes stale on disk.
_cookie_jar_has_live_cookie() {
    local file="$1"
    [[ -s "$file" ]] || return 1
    awk -v now="$(date +%s)" -F'\t' '
        /^#[[:space:]]/ { next }
        NF >= 7 { if ($5 + 0 == 0 || $5 + 0 > now) { found = 1; exit } }
        END { exit(found ? 0 : 1) }
    ' "$file"
}

# _cookie_jar_is_fresh FILE TTL — true when FILE was written less than TTL
# seconds ago. A TTL of 0 disables the cache.
_cookie_jar_is_fresh() {
    local file="$1" ttl="$2"
    [[ -s "$file" ]] || return 1
    [[ "$ttl" -gt 0 ]] || return 1

    local mtime
    mtime=$(stat -f %m "$file" 2>/dev/null || stat -c %Y "$file" 2>/dev/null) || return 1
    [[ "$mtime" =~ ^[0-9]+$ ]] || return 1

    local age=$(( $(date +%s) - mtime ))
    [[ $age -ge 0 && $age -lt $ttl ]]
}

# _amir_export_browser_cookie_jar BROWSER OUT_JAR — full jar, Netscape format.
_amir_export_browser_cookie_jar() {
    local browser="$1"
    local out_jar="$2"
    python3 - "$browser" "$out_jar" <<'PY'
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

# _cookie_cache_refresh BROWSER OUT_FILE DOMAIN... — extract from the browser
# and write the scoped jar. Returns 1 (leaving OUT_FILE untouched) when the
# browser cannot be read or holds no live cookie for these domains.
_cookie_cache_refresh() {
    local browser="$1"
    local out="$2"
    shift 2
    local domains="$*"
    [[ -n "$domains" ]] || return 1

    local full scoped
    full=$(mktemp "${TMPDIR:-/tmp}/amir-cookies-full.XXXXXX") || return 1
    chmod 600 "$full" 2>/dev/null
    if ! _amir_export_browser_cookie_jar "$browser" "$full" >/dev/null 2>&1; then
        rm -f "$full"
        return 1
    fi

    scoped=$(mktemp "${TMPDIR:-/tmp}/amir-cookies-scoped.XXXXXX") || { rm -f "$full"; return 1; }
    chmod 600 "$scoped" 2>/dev/null
    {
        printf '# Netscape HTTP Cookie File\n'
        printf '# Written by amir — %s cookies for: %s\n' "$browser" "$domains"
        printf '# Refreshed from the browser when stale; delete this file to force a refresh.\n'
    } > "$scoped"

    # Match the cookie's own domain field, honouring the #HttpOnly_ prefix
    # yt-dlp writes and the leading dot of a domain cookie. The first domain is
    # the site itself and takes its subdomains with it; the siblings after it
    # match exactly, so a YouTube jar picks up the `.google.com` account cookie
    # without dragging mail.google.com's session onto disk with it.
    awk -v doms="$domains" -F'\t' '
        BEGIN { n = split(doms, d, " ") }
        /^#[[:space:]]/ { next }
        NF >= 7 {
            dom = $1
            sub(/^#HttpOnly_/, "", dom)
            sub(/^\./, "", dom)
            dom = tolower(dom)
            for (i = 1; i <= n; i++) {
                if (dom == d[i]) { print; next }
                if (i == 1 && substr(dom, length(dom) - length(d[i])) == "." d[i]) { print; next }
            }
        }
    ' "$full" >> "$scoped"
    rm -f "$full"

    if ! _cookie_jar_has_live_cookie "$scoped"; then
        rm -f "$scoped"
        return 1
    fi

    mv "$scoped" "$out" 2>/dev/null || { rm -f "$scoped"; return 1; }
    chmod 600 "$out" 2>/dev/null
    return 0
}

# _browser_cookie_args BROWSER [URL] [MODE] — the yt-dlp flags that read
# BROWSER's cookies, served from cache when possible. Bash 3.2 has no namerefs,
# so the result comes back in a global array:
#
#   BROWSER_COOKIE_ARGS  — (--cookies <jar>) or (--cookies-from-browser <b>)
#
# MODE is 'refresh' (default) — read the browser when the cache is stale — or
# 'cached-only', which never touches the browser and leaves the caller with
# --cookies-from-browser. Anonymous-first callers use 'cached-only' while
# resolving, because a cookie jar prepared for a retry that never happens is a
# keychain unlock spent on nothing.
#
# Every failure path falls back to --cookies-from-browser, so the caller's
# behaviour is unchanged when the cache cannot help.
_browser_cookie_args() {
    local browser="$1"
    local url="${2:-}"
    local mode="${3:-refresh}"

    BROWSER_COOKIE_ARGS=(--cookies-from-browser "$browser")
    [[ -n "$browser" && "$browser" != "none" ]] || { BROWSER_COOKIE_ARGS=(); return 0; }
    [[ "${AMIR_NO_COOKIE_CACHE:-}" == "1" ]] && return 0
    [[ -n "$url" ]] || return 0

    local domains
    domains=$(_cookie_scope_domains "$url") || return 0

    local dir
    dir=$(_cookie_cache_dir) || return 0

    local primary="${domains%% *}"
    local jar="$dir/${browser}__${primary}.txt"
    local ttl
    ttl=$(_cookie_cache_ttl)

    if [[ "${AMIR_REFRESH_COOKIES:-}" != "1" ]] \
        && _cookie_jar_is_fresh "$jar" "$ttl" \
        && _cookie_jar_has_live_cookie "$jar"; then
        BROWSER_COOKIE_ARGS=(--cookies "$jar")
        return 0
    fi

    [[ "$mode" == "cached-only" ]] && return 0

    if _cookie_cache_refresh "$browser" "$jar" $domains; then
        BROWSER_COOKIE_ARGS=(--cookies "$jar")
    fi
    return 0
}
