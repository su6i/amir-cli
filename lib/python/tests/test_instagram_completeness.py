"""Tests for Instagram carousel download completeness counting."""

import os
import shutil
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
BASH_SCRIPT = os.path.join(SCRIPT_DIR, "commands", "download.sh")


def run_download_instagram(item_count, create_count, cwd, preexisting_files=()):
    """Run _download_instagram() with bash stubs to test its counting behavior."""
    for name in preexisting_files:
        with open(os.path.join(cwd, name), "w"):
            pass
    script = f'''
source "{BASH_SCRIPT}"
log_info() {{ :; }}
log_warning() {{ :; }}
log_error() {{ echo "$@" >&2; }}
_resolve_cookie_args() {{ RESOLVED_COOKIE_ARGS=(); FALLBACK_COOKIE_ARGS=(); return 0; }}
video_download() {{ return 1; }}
_classify_instagram_url() {{ echo "photo {item_count}"; return 0; }}
_gallery_dl_download() {{
    local url="$1" out_dir="$2"
    local i=1
    while [[ $i -le {create_count} ]]; do
        touch "$out_dir/stub_new_${{i}}.jpg"
        i=$((i+1))
    done
    return 0
}}
_download_instagram "jpg" "false" "https://www.instagram.com/p/FAKE123/"
'''
    return subprocess.run(
        ["bash", "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
    )


def test_carousel_complete_download_dest_not_cwd():
    """Complete download when the destination dir already has a pre-existing file."""
    tmp_dir = tempfile.mkdtemp()
    try:
        res = run_download_instagram(
            item_count=3,
            create_count=3,
            cwd=tmp_dir,
            preexisting_files=("old.jpg",),
        )
        assert res.returncode == 0
        assert "items downloaded" not in res.stderr
        assert "ERROR" not in res.stderr
        assert "⚠" not in res.stderr
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_carousel_partial_download_dest_not_cwd():
    """Partial download when the destination dir already has a pre-existing file."""
    tmp_dir = tempfile.mkdtemp()
    try:
        res = run_download_instagram(
            item_count=3,
            create_count=2,
            cwd=tmp_dir,
            preexisting_files=("old.jpg",),
        )
        assert res.returncode != 0
        assert "2 of 3" in res.stderr
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_carousel_complete_download_empty_dest_dir():
    """Regression test: complete download when the destination dir starts out empty."""
    tmp_dir = tempfile.mkdtemp()
    try:
        res = run_download_instagram(
            item_count=2,
            create_count=2,
            cwd=tmp_dir,
            preexisting_files=(),
        )
        assert res.returncode == 0
        assert "items downloaded" not in res.stderr
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
