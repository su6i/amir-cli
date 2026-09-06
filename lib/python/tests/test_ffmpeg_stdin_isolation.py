"""Regression tests: ffmpeg must not consume the caller's stdin.

`ensure_mac_playable_video()` and the webp conversion loop both run inside
`while IFS= read -r f; do ...; done < <(find ...)`. Without `-nostdin`, ffmpeg
inherits that pipe and swallows the filenames the loop has not read yet, so
files are silently skipped and ffmpeg reports a parse error on the truncated
name it stole.
"""

import os
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
VIDEO_SH = os.path.join(SCRIPT_DIR, "commands", "video.sh")

# Faithful stand-in for the real binary: it reads stdin unless told not to.
FFMPEG_STUB = """#!/bin/bash
for arg in "$@"; do
    [[ "$arg" == "-nostdin" ]] && exec > /dev/null 2>&1 && break
done
case " $* " in
    *" -nostdin "*) : ;;
    *) cat > /dev/null ;;   # real ffmpeg drains stdin when it is not disabled
esac
out="${@: -1}"
: > "$out"
exit 0
"""

FFPROBE_STUB = """#!/bin/bash
case " $* " in
    *"stream=codec_name"*)
        case " $* " in
            *" a:0 "*) echo "opus" ;;
            *) echo "vp9" ;;
        esac
        ;;
esac
exit 0
"""


def _make_stub_bin(tmpdir):
    bin_dir = os.path.join(tmpdir, "bin")
    os.makedirs(bin_dir)
    for name, body in (("ffmpeg", FFMPEG_STUB), ("ffprobe", FFPROBE_STUB)):
        path = os.path.join(bin_dir, name)
        with open(path, "w") as fh:
            fh.write(body)
        os.chmod(path, 0o755)
    return bin_dir


def _run_normalize_loop(tmpdir, names):
    """Normalize `names` through a read loop fed by a pipe, as callers do."""
    for name in names:
        with open(os.path.join(tmpdir, name), "w") as fh:
            fh.write("x")
    bin_dir = _make_stub_bin(tmpdir)
    script = f'''
export PATH="{bin_dir}:$PATH"
source "{VIDEO_SH}" 2>/dev/null || true
log_info() {{ :; }}
log_error() {{ :; }}
get_config() {{ echo "${{3:-}}"; }}
cd "{tmpdir}"
while IFS= read -r f; do
    ensure_mac_playable_video "$f" >/dev/null 2>&1 && echo "OK:$f"
done < <(printf '%s\\n' {" ".join(names)})
'''
    proc = subprocess.run(
        ["bash", "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [line[3:] for line in proc.stdout.splitlines() if line.startswith("OK:")]


def test_every_file_in_the_loop_is_reached():
    """No filename may be eaten by the ffmpeg subprocess."""
    names = [f"airesearches_Dc6MT41mcAe_{i}.mp4" for i in range(1, 20)]
    with tempfile.TemporaryDirectory() as tmpdir:
        assert _run_normalize_loop(tmpdir, names) == names


def test_normalize_leaves_stdin_untouched():
    """A read after normalizing must still see the next queued line."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "clip.mp4"), "w") as fh:
            fh.write("x")
        bin_dir = _make_stub_bin(tmpdir)
        script = f'''
export PATH="{bin_dir}:$PATH"
source "{VIDEO_SH}" 2>/dev/null || true
log_info() {{ :; }}
log_error() {{ :; }}
get_config() {{ echo "${{3:-}}"; }}
cd "{tmpdir}"
{{
    read -r _first
    ensure_mac_playable_video "clip.mp4" >/dev/null 2>&1
    read -r second
    echo "SECOND:$second"
}} < <(printf 'first\\nsecond-line-survived\\n')
'''
        proc = subprocess.run(
            ["bash", "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert "SECOND:second-line-survived" in proc.stdout
