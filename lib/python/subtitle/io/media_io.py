import os
import re
import subprocess
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def sanitize_stem_for_fs(stem: str) -> str:
    """Build a terminal-safe ASCII filename stem."""
    if not stem:
        return "video"

    stem = (
        stem.replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("´", "'")
    )
    normalized = unicodedata.normalize("NFKD", stem)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_only = ascii_only.replace("'", "_")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_only)
    safe = re.sub(r"_+", "_", safe).strip("._-")
    return safe or "video"


def ensure_safe_input_filename(file_path: str, logger=None) -> str:
    """Rename input file in-place before processing starts."""
    if not file_path:
        return file_path

    src = os.path.abspath(file_path)
    if not os.path.exists(src):
        return src

    parent = os.path.dirname(src)
    name = os.path.basename(src)
    stem, ext = os.path.splitext(name)
    safe_stem = sanitize_stem_for_fs(stem)

    if safe_stem == stem:
        return src

    candidate = os.path.join(parent, f"{safe_stem}{ext}")
    if os.path.abspath(candidate) == src:
        return src

    idx = 2
    while os.path.exists(candidate):
        candidate = os.path.join(parent, f"{safe_stem}_{idx}{ext}")
        idx += 1

    os.replace(src, candidate)
    if logger is not None:
        logger.info(f"🧹 Input filename normalized: {name} → {os.path.basename(candidate)}")
    return candidate


def collect_existing_output_files(result: Dict[str, Any]) -> List[str]:
    files: List[str] = []

    def _collect(value: Any):
        if isinstance(value, str) and os.path.exists(value):
            files.append(os.path.abspath(value))
        elif isinstance(value, dict):
            for v in value.values():
                _collect(v)
        elif isinstance(value, list):
            for v in value:
                _collect(v)

    _collect(result)

    seen = set()
    unique: List[str] = []
    for path in files:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def bundle_outputs_zip(base_path: str, files: List[str], logger=None) -> Optional[str]:
    zip_path = f"{base_path}.zip"
    base_abs = os.path.abspath(base_path)
    base_dir = os.path.dirname(base_abs)
    base_name = os.path.basename(base_abs)

    merged_files = [os.path.abspath(f) for f in files if isinstance(f, str)]

    try:
        for p in Path(base_dir).glob(f"{base_name}_*"):
            if p.is_file():
                merged_files.append(str(p.resolve()))
    except Exception:
        pass

    include_ext = {".srt", ".ass", ".txt", ".pdf", ".vtt", ".md"}
    video_ext = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

    filtered: List[str] = []
    seen = set()
    zip_abs = os.path.abspath(zip_path)
    for f in merged_files:
        abs_f = os.path.abspath(f)
        if abs_f == zip_abs or not os.path.exists(abs_f):
            continue
        ext = Path(abs_f).suffix.lower()
        if ext in video_ext or ext == ".zip":
            continue
        if ext not in include_ext:
            continue

        base_name_only = os.path.basename(abs_f)
        if re.search(r"_\d{3,4}p_([a-z]{2,3})(_|\.)", base_name_only, flags=re.IGNORECASE):
            canonical_name = re.sub(
                r"_\d{3,4}p(?:_q\d+)?_", "_", base_name_only, count=1, flags=re.IGNORECASE
            )
            canonical_path = os.path.join(base_dir, canonical_name)
            if os.path.exists(canonical_path):
                continue

        if abs_f in seen:
            continue
        seen.add(abs_f)
        filtered.append(abs_f)

    if not filtered:
        return None

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in filtered:
            if os.path.exists(f):
                zf.write(f, arcname=os.path.basename(f))

    return zip_path


def detect_video_dimensions(video_path: str) -> Tuple[Optional[int], Optional[int]]:
    """Detect video width and height using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0:s=x",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        dims = result.stdout.strip()
        if dims and "x" in dims:
            w, h = dims.split("x")
            return int(w), int(h)
    except Exception:
        pass
    return None, None


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        dur = result.stdout.strip()
        if dur:
            return float(dur)
    except Exception:
        pass
    return 0.0
