"""Tests for lib/cookie_cache.sh — the on-disk browser cookie cache.

None of these tests may read a real browser: the extraction step is stubbed out
so the suite stays hermetic (and does not ask for a keychain unlock in CI).
"""

import os
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_SCRIPT = os.path.join(SCRIPT_DIR, "cookie_cache.sh")
DOWNLOAD_SCRIPT = os.path.join(SCRIPT_DIR, "commands", "download.sh")

# A stub standing in for the browser: writes a jar that mixes the site's own
# cookies with unrelated ones, so scoping can be asserted on the result.
STUB_EXPORT = """
_amir_export_browser_cookie_jar() {
    local out="$2"
    {
        printf '# Netscape HTTP Cookie File\\n'
        printf '.youtube.com\\tTRUE\\t/\\tTRUE\\t%s\\tSID\\tyt\\n' "$FUTURE"
        printf '#HttpOnly_.youtube.com\\tTRUE\\t/\\tTRUE\\t%s\\tHSID\\tyt2\\n' "$FUTURE"
        printf '.google.com\\tTRUE\\t/\\tTRUE\\t%s\\tSAPISID\\tgoog\\n' "$FUTURE"
        printf 'mail.google.com\\tFALSE\\t/\\tTRUE\\t%s\\tGMAIL_AT\\tsecret\\n' "$FUTURE"
        printf '.paypal.com\\tTRUE\\t/\\tTRUE\\t%s\\tPAYPAL\\tsecret\\n' "$FUTURE"
    } > "$out"
}
""".strip()


def run_bash(snippet, env=None, cwd=None):
    if env is None:
        env = os.environ.copy()
    res = subprocess.run(
        ["bash", "-c", snippet],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=cwd,
    )
    return res.stdout.strip()


def cache_env(tmp_path, **extra):
    env = os.environ.copy()
    env["AMIR_COOKIE_CACHE_DIR"] = str(tmp_path / "cookies")
    env["FUTURE"] = str(int(time.time()) + 86400)
    env.pop("AMIR_NO_COOKIE_CACHE", None)
    env.pop("AMIR_REFRESH_COOKIES", None)
    env.update(extra)
    return env


def write_jar(path, expiry_offset=86400, domain=".youtube.com"):
    expiry = int(time.time()) + expiry_offset
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Netscape HTTP Cookie File\n"
        f"{domain}\tTRUE\t/\tTRUE\t{expiry}\tSID\tvalue\n"
    )
    return path


# ── Scope ─────────────────────────────────────────────────────────────────────

def test_scope_lists_site_first_then_siblings():
    out = run_bash(f'source "{CACHE_SCRIPT}" && _cookie_scope_domains "https://www.youtube.com/watch?v=x"')
    assert out.split()[0] == "youtube.com"
    assert "google.com" in out.split()


def test_scope_falls_back_to_registrable_domain():
    out = run_bash(f'source "{CACHE_SCRIPT}" && _cookie_scope_domains "https://vimeo.com/12345"')
    assert out == "vimeo.com"


def test_scope_rejects_a_url_without_a_host():
    out = run_bash(f'source "{CACHE_SCRIPT}" && _cookie_scope_domains "notaurl" || echo NONE')
    assert out == "NONE"


# ── Jar validity ──────────────────────────────────────────────────────────────

def test_expired_only_jar_is_not_live(tmp_path):
    jar = write_jar(tmp_path / "expired.txt", expiry_offset=-86400)
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && '
        f'if _cookie_jar_has_live_cookie "{jar}"; then echo LIVE; else echo STALE; fi'
    )
    assert out == "STALE"


def test_session_cookie_counts_as_live(tmp_path):
    jar = tmp_path / "session.txt"
    jar.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tv\n")
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && '
        f'if _cookie_jar_has_live_cookie "{jar}"; then echo LIVE; else echo STALE; fi'
    )
    assert out == "LIVE"


def test_ttl_zero_disables_the_cache(tmp_path):
    jar = write_jar(tmp_path / "jar.txt")
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && '
        f'if _cookie_jar_is_fresh "{jar}" 0; then echo FRESH; else echo STALE; fi'
    )
    assert out == "STALE"


def test_jar_older_than_ttl_is_stale(tmp_path):
    jar = write_jar(tmp_path / "jar.txt")
    old = time.time() - 7200
    os.utime(jar, (old, old))
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && '
        f'if _cookie_jar_is_fresh "{jar}" 3600; then echo FRESH; else echo STALE; fi'
    )
    assert out == "STALE"


# ── Cache behaviour ───────────────────────────────────────────────────────────

def test_fresh_cache_is_used_without_touching_the_browser(tmp_path):
    env = cache_env(tmp_path)
    jar = write_jar(tmp_path / "cookies" / "chrome__youtube.com.txt")
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && '
        '_amir_export_browser_cookie_jar() { echo BROWSER_WAS_READ >&2; return 1; } && '
        '_browser_cookie_args chrome "https://www.youtube.com/watch?v=x" && '
        'echo "${BROWSER_COOKIE_ARGS[@]}"',
        env=env,
    )
    assert out == f"--cookies {jar}"


def test_stale_cache_is_refreshed_from_the_browser(tmp_path):
    env = cache_env(tmp_path)
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && {STUB_EXPORT} && '
        '_browser_cookie_args chrome "https://www.youtube.com/watch?v=x" && '
        'echo "${BROWSER_COOKIE_ARGS[@]}"',
        env=env,
    )
    jar = tmp_path / "cookies" / "chrome__youtube.com.txt"
    assert out == f"--cookies {jar}"
    assert jar.exists()


def test_refreshed_jar_holds_only_the_sites_own_cookies(tmp_path):
    """The whole point of scoping: a YouTube download must not park the
    browser's Gmail or PayPal session on disk in plaintext."""
    env = cache_env(tmp_path)
    run_bash(
        f'source "{CACHE_SCRIPT}" && {STUB_EXPORT} && '
        '_browser_cookie_args chrome "https://www.youtube.com/watch?v=x"',
        env=env,
    )
    body = (tmp_path / "cookies" / "chrome__youtube.com.txt").read_text()
    assert "SID\tyt" in body            # the site's own cookie
    assert "HSID\tyt2" in body          # ... including #HttpOnly_ ones
    assert "SAPISID\tgoog" in body      # the sibling domain's account cookie
    assert "GMAIL_AT" not in body       # but not a sibling *subdomain*
    assert "PAYPAL" not in body         # and nothing unrelated


def test_cached_jar_is_not_world_readable(tmp_path):
    env = cache_env(tmp_path)
    run_bash(
        f'source "{CACHE_SCRIPT}" && {STUB_EXPORT} && '
        '_browser_cookie_args chrome "https://www.youtube.com/watch?v=x"',
        env=env,
    )
    jar = tmp_path / "cookies" / "chrome__youtube.com.txt"
    assert oct(jar.stat().st_mode)[-3:] == "600"
    assert oct(jar.parent.stat().st_mode)[-3:] == "700"


def test_cached_only_mode_never_reads_the_browser(tmp_path):
    env = cache_env(tmp_path)
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && {STUB_EXPORT} && '
        '_browser_cookie_args chrome "https://www.youtube.com/watch?v=x" cached-only && '
        'echo "${BROWSER_COOKIE_ARGS[@]}"',
        env=env,
    )
    assert out == "--cookies-from-browser chrome"
    assert not (tmp_path / "cookies" / "chrome__youtube.com.txt").exists()


def test_no_cookie_cache_env_bypasses_the_cache(tmp_path):
    env = cache_env(tmp_path, AMIR_NO_COOKIE_CACHE="1")
    write_jar(tmp_path / "cookies" / "chrome__youtube.com.txt")
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && '
        '_browser_cookie_args chrome "https://www.youtube.com/watch?v=x" && '
        'echo "${BROWSER_COOKIE_ARGS[@]}"',
        env=env,
    )
    assert out == "--cookies-from-browser chrome"


def test_refresh_flag_ignores_a_fresh_cache(tmp_path):
    env = cache_env(tmp_path, AMIR_REFRESH_COOKIES="1")
    jar = write_jar(tmp_path / "cookies" / "chrome__youtube.com.txt", domain=".stale.example")
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && {STUB_EXPORT} && '
        '_browser_cookie_args chrome "https://www.youtube.com/watch?v=x" && '
        'echo "${BROWSER_COOKIE_ARGS[@]}"',
        env=env,
    )
    assert out == f"--cookies {jar}"
    assert "SID\tyt" in jar.read_text()   # rewritten from the browser


def test_a_url_less_call_reads_the_browser_directly(tmp_path):
    env = cache_env(tmp_path)
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && {STUB_EXPORT} && '
        '_browser_cookie_args chrome && echo "${BROWSER_COOKIE_ARGS[@]}"',
        env=env,
    )
    assert out == "--cookies-from-browser chrome"


def test_browser_none_yields_no_cookie_flags(tmp_path):
    env = cache_env(tmp_path)
    out = run_bash(
        f'source "{CACHE_SCRIPT}" && '
        '_browser_cookie_args none "https://www.youtube.com/watch?v=x" && '
        'echo "count=${#BROWSER_COOKIE_ARGS[@]}"',
        env=env,
    )
    assert out == "count=0"


# ── Integration with _resolve_cookie_args ─────────────────────────────────────

def test_explicit_browser_resolves_to_the_cached_jar(tmp_path):
    env = cache_env(tmp_path)
    jar = write_jar(tmp_path / "cookies" / "chrome__youtube.com.txt")
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && '
        '_resolve_cookie_args "" "chrome" "true" "https://www.youtube.com/watch?v=x" && '
        'echo "${RESOLVED_COOKIE_ARGS[@]}"',
        env=env,
        cwd=str(tmp_path),
    )
    assert out == f"--cookies {jar}"


def test_implicit_browser_retry_jar_does_not_trigger_an_extraction(tmp_path):
    """Anonymous-first: the retry jar may never be used, so resolving it must
    not pay for a browser read up front."""
    env = cache_env(tmp_path)
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && '
        '_amir_export_browser_cookie_jar() { echo BROWSER_WAS_READ >&2; return 1; } && '
        '_resolve_cookie_args "" "chrome" "false" "https://www.youtube.com/watch?v=x" && '
        'echo "${FALLBACK_COOKIE_ARGS[@]}"',
        env=env,
        cwd=str(tmp_path),
    )
    assert out == "--cookies-from-browser chrome"


def _stub_lib_dir(tmp_path):
    """A minimal LIB_DIR so run_download() can be exercised without pulling in
    the real video.sh/download_course_site.sh (heavy, and would perform a real
    network download)."""
    lib_dir = tmp_path / "lib"
    commands = lib_dir / "commands"
    commands.mkdir(parents=True)
    (commands / "video.sh").write_text(
        'video_download() { echo "REFRESH=${AMIR_REFRESH_COOKIES:-unset}"; }\n'
    )
    (commands / "download_course_site.sh").write_text(
        '_url_is_course_site() { return 1; }\n'
    )
    return str(lib_dir)


def test_refresh_cookies_flag_is_parsed_by_run_download(tmp_path):
    """--refresh-cookies must be recognized by run_download() itself (not just
    by video.sh's separate parser) so the Instagram/gallery-dl path also gets
    a forced cache refresh instead of silently ignoring the flag."""
    env = os.environ.copy()
    env["LIB_DIR"] = _stub_lib_dir(tmp_path)
    env.pop("AMIR_REFRESH_COOKIES", None)
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && run_download --refresh-cookies "https://example.com/video"',
        env=env,
    )
    assert out == "REFRESH=1"


def test_without_refresh_cookies_flag_env_stays_unset(tmp_path):
    env = os.environ.copy()
    env["LIB_DIR"] = _stub_lib_dir(tmp_path)
    env.pop("AMIR_REFRESH_COOKIES", None)
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && run_download "https://example.com/video"',
        env=env,
    )
    assert out == "REFRESH=unset"


def test_gallery_dl_skips_useless_retry_without_sessionid(tmp_path):
    """A cookie jar with no sessionid identifies the device but not a logged-in
    account; retrying gallery-dl with it fails the same way, just louder.
    _gallery_dl_download must skip that retry, print one explicit message, and
    return the AUTH_REQUIRED sentinel (2) instead of falling through to the
    generic multi-line error."""
    env = cache_env(tmp_path)
    cache_dir = tmp_path / "cookies"
    cache_dir.mkdir(parents=True, exist_ok=True)
    jar = cache_dir / "chrome__instagram.com.txt"
    jar.write_text(
        "# Netscape HTTP Cookie File\n"
        ".instagram.com\tTRUE\t/\tTRUE\t0\tmid\tX\n"
    )
    calls_file = tmp_path / "gallery_dl_calls"
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && '
        f'gallery-dl() {{ echo call >> "{calls_file}"; return 1; }}; '
        'log_info() { :; }; log_warning() { :; }; log_error() { echo "$1"; }; '
        f'_gallery_dl_download "https://www.instagram.com/p/ABC/" "{tmp_path}" chrome "" jpg false false 2>&1; '
        'echo "rc=$?"',
        env=env,
    )
    assert "not logged in" in out
    assert "rc=2" in out
    assert calls_file.read_text().count("call") == 1


def test_gallery_dl_retries_with_cookies_when_jar_has_sessionid(tmp_path):
    """Unchanged behavior: a jar that DOES carry a live sessionid still gets
    the normal anonymous -> cookies retry."""
    env = cache_env(tmp_path)
    cache_dir = tmp_path / "cookies"
    cache_dir.mkdir(parents=True, exist_ok=True)
    jar = cache_dir / "chrome__instagram.com.txt"
    jar.write_text(
        "# Netscape HTTP Cookie File\n"
        ".instagram.com\tTRUE\t/\tTRUE\t0\tmid\tX\n"
        ".instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\tY\n"
    )
    calls_file = tmp_path / "gallery_dl_calls"
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && '
        f'gallery-dl() {{ echo call >> "{calls_file}"; return 1; }}; '
        'log_info() { echo "$1"; }; log_warning() { :; }; log_error() { echo "$1"; }; '
        f'_gallery_dl_download "https://www.instagram.com/p/ABC/" "{tmp_path}" chrome "" jpg false false 2>&1; '
        'echo "rc=$?"',
        env=env,
    )
    assert calls_file.read_text().count("call") == 2
    assert "retrying with cookies" in out
    assert "rc=2" not in out


_IG_CAROUSEL_JSON = (
    '{"_type": "playlist", "id": "Dc6MT41mcAe", '
    '"entries": [{"id": "A"}, {"id": "B"}, {"id": "C"}]}'
)


def test_classify_instagram_url_counts_carousel_entries_in_one_probe():
    """The real yt-dlp -J shape for an Instagram carousel is a playlist dict
    with an 'entries' array and NO top-level 'formats' key — classification
    must count len(entries) from that same JSON, never probe a second time."""
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && '
        f"yt-dlp() {{ printf '%s' '{_IG_CAROUSEL_JSON}'; }}; "
        '_classify_instagram_url "https://www.instagram.com/p/Dc6MT41mcAe/?img_index=3"'
    )
    assert out == "photo 3"


def test_classify_instagram_url_reel_shortcut_skips_the_probe():
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && '
        'yt-dlp() { echo SHOULD_NOT_BE_CALLED >&2; exit 1; }; '
        '_classify_instagram_url "https://www.instagram.com/reel/XYZ456/"'
    )
    assert out == "video 1"


def test_download_instagram_reports_incomplete_carousel_and_skips_yt_dlp_fallback(tmp_path):
    """gallery-dl reports success (rc=0) after fetching only 1 of a 3-item
    carousel. The completeness check must catch this, print an explicit
    item-count message, exit nonzero, and never fall back to yt-dlp (which
    cannot fetch photos anyway)."""
    env = os.environ.copy()
    env["AMIR_COOKIE_CACHE_DIR"] = str(tmp_path / "cookies")
    calls_file = tmp_path / "video_download_calls"
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && '
        f"yt-dlp() {{ printf '%s' '{_IG_CAROUSEL_JSON}'; }}; "
        f'gallery-dl() {{ touch "{tmp_path}/item1.jpg"; return 0; }}; '
        f'video_download() {{ echo call >> "{calls_file}"; return 1; }}; '
        'ensure_mac_playable_video() { return 0; }; '
        'log_info() { :; }; log_warning() { :; }; log_error() { echo "$1"; }; '
        f'cd "{tmp_path}" && '
        '_download_instagram jpg false "https://www.instagram.com/p/Dc6MT41mcAe/?img_index=3" 2>&1; '
        'echo "rc=$?"',
        env=env,
    )
    assert "1 of 3 items downloaded" in out
    assert "rc=1" in out
    assert not calls_file.exists()


def test_download_instagram_returns_success_when_carousel_is_complete(tmp_path):
    env = os.environ.copy()
    env["AMIR_COOKIE_CACHE_DIR"] = str(tmp_path / "cookies")
    out = run_bash(
        f'source "{DOWNLOAD_SCRIPT}" && '
        f"yt-dlp() {{ printf '%s' '{_IG_CAROUSEL_JSON}'; }}; "
        f'gallery-dl() {{ touch "{tmp_path}/a.jpg" "{tmp_path}/b.jpg" "{tmp_path}/c.mp4"; return 0; }}; '
        'ensure_mac_playable_video() { return 0; }; '
        'log_info() { :; }; log_warning() { :; }; log_error() { echo "$1"; }; '
        f'cd "{tmp_path}" && '
        '_download_instagram jpg false "https://www.instagram.com/p/Dc6MT41mcAe/?img_index=3" 2>&1; '
        'echo "rc=$?"',
        env=env,
    )
    assert "items downloaded" not in out
    assert "rc=0" in out
