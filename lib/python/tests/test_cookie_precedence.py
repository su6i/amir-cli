import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASH_SCRIPT = os.path.join(SCRIPT_DIR, "commands", "download.sh")
COURSE_SITE_SCRIPT = os.path.join(SCRIPT_DIR, "commands", "download_course_site.sh")

def run_resolve(cookies_arg, browser_arg, explicit_browser, cwd, env=None, array="RESOLVED_COOKIE_ARGS"):
    cmd = f'source "{BASH_SCRIPT}" && _resolve_cookie_args "{cookies_arg}" "{browser_arg}" "{explicit_browser}" && echo "${{{array}[@]}}"'
    if env is None:
        env = os.environ.copy()
    res = subprocess.run(
        ["bash", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=env
    )
    return res.stdout.strip()

def run_course_site_resolve(cookies_arg, browser_arg, explicit_browser, cwd, env=None):
    cmd = (
        f'source "{COURSE_SITE_SCRIPT}" && '
        '_course_site_export_cookie_jar() { echo "BROWSER:$1" > "$2"; return 0; } && '
        'log_error() { :; } && '
        f'_course_site_resolve_cookie_jar "{cookies_arg}" "{browser_arg}" "{explicit_browser}" && '
        'if [[ "$COURSE_SITE_COOKIE_JAR_IS_TEMP" == "true" ]]; then cat "$COURSE_SITE_COOKIE_JAR"; else echo "$COURSE_SITE_COOKIE_JAR"; fi'
    )
    if env is None:
        env = os.environ.copy()
    res = subprocess.run(
        ["bash", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=env
    )
    return res.stdout.strip()

def test_explicit_cookies_wins(tmp_path):
    out = run_resolve("/explicit/cookies.txt", "chrome", "true", cwd=str(tmp_path))
    assert out == "--cookies /explicit/cookies.txt"

def test_explicit_browser_wins_over_local(tmp_path):
    (tmp_path / "cookies.txt").write_text("local")
    out = run_resolve("", "safari", "true", cwd=str(tmp_path))
    assert out == "--cookies-from-browser safari"

# ── Anonymous-first policy ────────────────────────────────────────────────────
# Implicitly discovered cookies (./cookies.txt, config cookies.file, default
# browser) must NOT be spent on the first attempt: a session-less jar hands the
# site a device id with no login behind it, which earns a login wall and a
# rate-limit on that id. They land in FALLBACK_COOKIE_ARGS for the retry instead.

def test_local_cookies_held_back_for_retry(tmp_path):
    (tmp_path / "cookies.txt").write_text("local")
    env = os.environ.copy()
    env["AMIR_COOKIES_FILE"] = "/global/cookies.txt"
    assert run_resolve("", "chrome", "false", cwd=str(tmp_path), env=env) == ""
    fallback = run_resolve("", "chrome", "false", cwd=str(tmp_path), env=env,
                           array="FALLBACK_COOKIE_ARGS")
    assert fallback == "--cookies cookies.txt"

def test_global_cookies_held_back_and_beat_default_browser(tmp_path):
    # Create the global file so the check `-f "$_global_cookies"` passes
    global_file = tmp_path / "global_cookies.txt"
    global_file.write_text("global")
    env = os.environ.copy()
    env["AMIR_COOKIES_FILE"] = str(global_file)

    assert run_resolve("", "chrome", "false", cwd=str(tmp_path), env=env) == ""
    fallback = run_resolve("", "chrome", "false", cwd=str(tmp_path), env=env,
                           array="FALLBACK_COOKIE_ARGS")
    assert fallback == f"--cookies {str(global_file)}"

def test_default_browser_held_back_for_retry(tmp_path):
    assert run_resolve("", "firefox", "false", cwd=str(tmp_path)) == ""
    fallback = run_resolve("", "firefox", "false", cwd=str(tmp_path),
                           array="FALLBACK_COOKIE_ARGS")
    assert fallback == "--cookies-from-browser firefox"

def test_explicit_browser_none_disables_cookies_entirely(tmp_path):
    # A discovered ./cookies.txt must not sneak back in past an explicit opt-out.
    (tmp_path / "cookies.txt").write_text("local")
    assert run_resolve("", "none", "true", cwd=str(tmp_path)) == ""
    assert run_resolve("", "none", "true", cwd=str(tmp_path),
                       array="FALLBACK_COOKIE_ARGS") == ""

def test_amir_no_cookies_beats_explicit_flags(tmp_path):
    env = os.environ.copy()
    env["AMIR_NO_COOKIES"] = "1"
    assert run_resolve("/explicit/cookies.txt", "chrome", "true", cwd=str(tmp_path), env=env) == ""
    assert run_resolve("/explicit/cookies.txt", "chrome", "true", cwd=str(tmp_path), env=env,
                       array="FALLBACK_COOKIE_ARGS") == ""

def test_course_site_explicit_cookies_wins(tmp_path):
    explicit_file = tmp_path / "explicit_cookies.txt"
    explicit_file.write_text("explicit")
    (tmp_path / "cookies.txt").write_text("local")
    out = run_course_site_resolve(str(explicit_file), "chrome", "false", cwd=str(tmp_path))
    assert out == str(explicit_file)

def test_course_site_explicit_browser_beats_discovered_file(tmp_path):
    (tmp_path / "cookies.txt").write_text("local")
    # this is the regression guard — a discovered jar used to silently outrank an explicitly typed --browser, handing yt-dlp stale cookies with no warning.
    out = run_course_site_resolve("", "safari", "true", cwd=str(tmp_path))
    assert out == "BROWSER:safari"

def test_course_site_local_cookies_beats_config(tmp_path):
    (tmp_path / "cookies.txt").write_text("local")
    config_file = tmp_path / "global_cookies.txt"
    config_file.write_text("global")
    env = os.environ.copy()
    env["AMIR_COOKIES_FILE"] = str(config_file)
    out = run_course_site_resolve("", "chrome", "false", cwd=str(tmp_path), env=env)
    assert out == "./cookies.txt"

def test_course_site_config_beats_default_browser(tmp_path):
    config_file = tmp_path / "global_cookies.txt"
    config_file.write_text("global")
    env = os.environ.copy()
    env["AMIR_COOKIES_FILE"] = str(config_file)
    out = run_course_site_resolve("", "chrome", "false", cwd=str(tmp_path), env=env)
    assert out == str(config_file)

def test_course_site_unset_config_rung_is_skipped(tmp_path):
    env = os.environ.copy()
    env.pop("AMIR_COOKIES_FILE", None)
    # unset config must leave the rung inert, not resolve to an empty path.
    out = run_course_site_resolve("", "firefox", "false", cwd=str(tmp_path), env=env)
    assert out == "BROWSER:firefox"
