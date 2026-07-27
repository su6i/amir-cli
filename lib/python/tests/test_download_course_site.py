"""تست‌های مربوط به توابع بش برای دانلود از سایت رمضانی."""

import os
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
BASH_SCRIPT = os.path.join(SCRIPT_DIR, "commands", "download_course_site.sh")


def run_bash_function(func_name, *args):
    """بارگذاری اسکریپت بش و اجرای یک تابع خاص با آرگومان‌ها."""
    args_str = " ".join(f'"{a}"' for a in args)
    cmd = f'source "{BASH_SCRIPT}" && {func_name} {args_str}'
    result = subprocess.run(
        ["bash", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result


def test_course_site_check_drm_in_file_found():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("Some content with widevine embedded.")
        temp_name = f.name

    try:
        res = run_bash_function("_course_site_check_drm_in_file", temp_name)
        assert res.returncode == 0
    finally:
        os.remove(temp_name)


def test_course_site_check_drm_in_file_not_found():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("Clean HTML file without any DRM markers.")
        temp_name = f.name

    try:
        res = run_bash_function("_course_site_check_drm_in_file", temp_name)
        assert res.returncode == 1
    finally:
        os.remove(temp_name)


def test_course_site_extract_video_url_video_tag():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write('<html><body><video src="/videos/test.mp4"></video></body></html>')
        temp_name = f.name

    try:
        res = run_bash_function(
            "_course_site_extract_video_url", temp_name, "https://example-course-site.test"
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "https://example-course-site.test/videos/test.mp4"
    finally:
        os.remove(temp_name)


def test_course_site_extract_video_url_iframe():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(
            '<html><body><iframe src="https://vimeo.com/video/123"></iframe></body></html>'
        )
        temp_name = f.name

    try:
        res = run_bash_function(
            "_course_site_extract_video_url", temp_name, "https://example-course-site.test"
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "https://vimeo.com/video/123"
    finally:
        os.remove(temp_name)


def test_course_site_extract_video_url_bare_link():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write('Some JS config: {"url": "https://cdn.example-course-site.test/stream.m3u8"}')
        temp_name = f.name

    try:
        res = run_bash_function(
            "_course_site_extract_video_url", temp_name, "https://example-course-site.test"
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "https://cdn.example-course-site.test/stream.m3u8"
    finally:
        os.remove(temp_name)


def test_course_site_extract_video_url_data_src():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(
            '<html><body><div data-src="https://cdn.example-course-site.test/video.mp4"></div></body></html>'
        )
        temp_name = f.name

    try:
        res = run_bash_function(
            "_course_site_extract_video_url", temp_name, "https://example-course-site.test"
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "https://cdn.example-course-site.test/video.mp4"
    finally:
        os.remove(temp_name)


def test_course_site_extract_lesson_links():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write('<html><body><a href="/lesson/123">Lesson 1</a></body></html>')
        temp_name = f.name

    try:
        res = run_bash_function(
            "_course_site_extract_lesson_links", temp_name, "https://example-course-site.test"
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "https://example-course-site.test/lesson/123\tLesson 1"
    finally:
        os.remove(temp_name)


def test_course_site_classify_page_course():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write('<html><body><a href="/lesson/123">Lesson 1</a></body></html>')
        temp_name = f.name

    try:
        res = run_bash_function(
            "_course_site_classify_page", temp_name, "https://example-course-site.test"
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "course"
    finally:
        os.remove(temp_name)


def test_course_site_classify_page_single():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write('<html><body><video src="https://example-course-site.test/v.mp4"></video></body></html>')
        temp_name = f.name

    try:
        res = run_bash_function(
            "_course_site_classify_page", temp_name, "https://example-course-site.test"
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "single"
    finally:
        os.remove(temp_name)


def test_course_site_classify_page_not_purchased_blocked():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(
            '<html><body><button class="single_add_to_cart_button">Buy</button></body></html>'
        )
        temp_name = f.name

    try:
        res = run_bash_function(
            "_course_site_classify_page", temp_name, "https://example-course-site.test"
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "not_purchased"
    finally:
        os.remove(temp_name)


def test_course_site_classify_page_not_purchased_empty():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("<html><body><p>Hello</p></body></html>")
        temp_name = f.name

    try:
        res = run_bash_function(
            "_course_site_classify_page", temp_name, "https://example-course-site.test"
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "not_purchased"
    finally:
        os.remove(temp_name)


def test_course_site_sanitize_title():
    res = run_bash_function("_course_site_sanitize_title", "Hello World! @#$")
    assert res.returncode == 0
    assert res.stdout.strip() == "Hello_World"

    res = run_bash_function("_course_site_sanitize_title", "آزمون فارسی 123")
    assert res.returncode == 0
    assert res.stdout.strip() == "آزمون_فارسی_123"


def test_course_site_zero_pad_name():
    res = run_bash_function("_course_site_zero_pad_name", "5", "12", "My Lesson")
    assert res.returncode == 0
    assert res.stdout.strip() == "05 - My Lesson"

    res = run_bash_function("_course_site_zero_pad_name", "1", "5", "Intro")
    assert res.returncode == 0
    assert res.stdout.strip() == "01 - Intro"

    res = run_bash_function("_course_site_zero_pad_name", "100", "150", "End")
    assert res.returncode == 0
    assert res.stdout.strip() == "100 - End"


def test_course_page_preserves_document_order_and_naming():
    fixture_file = os.path.join(
        os.path.dirname(__file__), "fixtures", "course_site", "course_page.html"
    )
    base_url = "https://example-course-site.test/product/investment-2026/"
    res = run_bash_function("_course_site_extract_lesson_links", fixture_file, base_url)
    assert res.returncode == 0
    lines = [line for line in res.stdout.strip().split("\n") if line.strip()]
    assert len(lines) == 3, f"Expected 3 lesson links, got {len(lines)}: {lines}"
    expected_urls = [
        "https://example-course-site.test/lesson/زبان-بدن-بازار/",
        "https://example-course-site.test/lesson/آموزش-پرتفوی/",
        "https://example-course-site.test/lesson/استراتژی-نهایی/",
    ]
    for i, expected_url in enumerate(expected_urls):
        line = lines[i]
        parts = line.split("\t")
        assert len(parts) == 2, f"Expected tab-separated line, got: {line}"
        assert (
            parts[0] == expected_url
        ), f"URL mismatch at position {i}: expected {expected_url}, got {parts[0]}"
        sanitized = run_bash_function("_course_site_sanitize_title", parts[1])
        assert sanitized.returncode == 0
        sanitized_title = sanitized.stdout.strip()
        padded = run_bash_function(
            "_course_site_zero_pad_name", str(i + 1), "3", sanitized_title
        )
        assert padded.returncode == 0
        result_str = padded.stdout.strip()
        expected_prefix = f"{str(i + 1).zfill(2)} - "
        assert result_str.startswith(
            expected_prefix
        ), f"Position {i}: expected to start with '{expected_prefix}', got '{result_str}'"


def test_drm_manifest_aborts_download_without_invoking_ytdlp(tmp_path):
    import stat

    fixture = os.path.join(
        os.path.dirname(__file__), "fixtures", "course_site", "drm_manifest.m3u8"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    def write_fake(name, body):
        p = bin_dir / name
        p.write_text(f"#!/bin/bash\n{body}\n")
        p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    write_fake(
        "curl",
        f'''
args=("$@")
for i in "${{!args[@]}}"; do
  if [[ "${{args[$i]}}" == "-o" ]]; then
    out="${{args[$((i+1))]}}"
    cp "{fixture}" "$out"
  fi
done
exit 0
''',
    )
    write_fake("yt-dlp", 'touch "$MARKER_DIR/ytdlp_was_called"\nexit 0')
    write_fake("ffmpeg", 'touch "$MARKER_DIR/ffmpeg_was_called"\nexit 0')
    write_fake("ffprobe", 'touch "$MARKER_DIR/ffprobe_was_called"\nexit 0')

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "MARKER_DIR": str(tmp_path),
    }
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    script = f'''
source "{BASH_SCRIPT}"
RESOLVED_COOKIE_ARGS=()
COURSE_SITE_COOKIE_JAR=/dev/null
_course_site_download_one "https://cdn.example.com/stream.m3u8" "{out_dir}/lesson"
'''
    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, env=env
    )

    assert (
        result.returncode == 3
    ), f"expected exit 3, got {result.returncode}: stdout={result.stdout} stderr={result.stderr}"
    combined = (result.stdout + result.stderr).lower()
    assert "drm" in combined, f"expected a DRM message, got: {combined}"
    assert not (
        tmp_path / "ytdlp_was_called"
    ).exists(), "yt-dlp must NOT be invoked when DRM is detected"
    assert not (tmp_path / "ffmpeg_was_called").exists()
    assert not (tmp_path / "ffprobe_was_called").exists()


def test_sanitize_title_persian_survives_slash_colon():
    res = run_bash_function("_course_site_sanitize_title", "دوره:   مقدمه/پیشرفته   ")
    assert res.returncode == 0
    result = res.stdout.strip()
    assert "/" not in result, f"Slash found in sanitized title: {result}"
    assert ":" not in result, f"Colon found in sanitized title: {result}"
    assert "دوره" in result, f"'دوره' not found in sanitized title: {result}"
    assert "مقدمه" in result, f"'مقدمه' not found in sanitized title: {result}"
    assert "پیشرفته" in result, f"'پیشرفته' not found in sanitized title: {result}"
    assert len(result) > 0
