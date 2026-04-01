import json
import os
import re
from pathlib import Path
from typing import Dict, Optional


def discover_video_metadata(processor, original_base: str, srt_path: Optional[str] = None) -> Dict[str, str]:
    """Best-effort metadata lookup from yt-dlp sidecars near the current video/SRT."""
    def stem_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

    def normalize_candidate_stem(value: str) -> str:
        stem = value or ""
        # Strip common sidecar suffixes and generated tails to compare base video identity.
        stem = re.sub(r"\.info$", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"_[a-z]{2,3}(?:_[a-z]{2,3})?$", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"_[0-9]{3,4}p(?:_q[0-9]+)?(?:_[0-9]+)?$", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"_(subbed|rendered)$", "", stem, flags=re.IGNORECASE)
        return stem

    candidates = []
    if srt_path:
        srt_path = os.path.abspath(srt_path)
        candidates.extend([
            f"{srt_path}.info.json",
            f"{os.path.splitext(srt_path)[0]}.info.json",
        ])

    original_base_abs = os.path.abspath(original_base)
    base_dir = os.path.dirname(original_base_abs)
    base_name = os.path.basename(original_base_abs)

    target_keys = {stem_key(normalize_candidate_stem(base_name))}
    if srt_path:
        srt_stem = os.path.splitext(os.path.basename(srt_path))[0]
        target_keys.add(stem_key(normalize_candidate_stem(srt_stem)))
    target_keys = {k for k in target_keys if k}

    def is_related_meta(meta_path: str) -> bool:
        stem = Path(meta_path).stem
        candidate_key = stem_key(normalize_candidate_stem(stem))
        if not candidate_key or not target_keys:
            return False
        return any(candidate_key in tk or tk in candidate_key for tk in target_keys)

    candidates.extend([
        f"{original_base_abs}.info.json",
        f"{original_base_abs}.mp4.info.json",
        f"{original_base_abs}.mov.info.json",
        f"{original_base_abs}.m4v.info.json",
    ])

    cwd = os.getcwd()
    try:
        dynamic_candidates = []
        for d in set([base_dir, cwd]):
            for pattern in (f"{base_name}_*.info.json", f"{base_name}*.info.json", "*.info.json"):
                for p in Path(d).glob(pattern):
                    if p.is_file() and is_related_meta(str(p.resolve())):
                        dynamic_candidates.append(str(p.resolve()))

        dynamic_candidates = sorted(set(dynamic_candidates), key=lambda p: os.path.getmtime(p), reverse=True)
        candidates.extend(dynamic_candidates)
    except Exception:
        pass

    seen = set()
    title = ""
    publish_date = ""
    webpage_url = ""
    uploader = ""
    duration_sec = 0.0

    for meta_path in candidates:
        if not meta_path or meta_path in seen or not os.path.exists(meta_path):
            continue
        seen.add(meta_path)
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            title = str(data.get("title") or data.get("fulltitle") or "").strip()
            publish_date = processor._format_publish_date(
                data.get("upload_date") or data.get("release_date") or data.get("timestamp") or ""
            )
            webpage_url = str(data.get("webpage_url") or data.get("original_url") or "").strip()
            uploader = str(data.get("uploader") or data.get("channel") or "").strip()
            if title or publish_date or webpage_url or uploader:
                duration_sec = data.get("duration") or 0.0
                if not duration_sec:
                    for ext in (".mp4", ".mkv", ".mov", ".m4v", ".webm", ".ts"):
                        v_p = original_base + ext
                        if os.path.exists(v_p):
                            duration_sec = processor._get_video_duration(v_p)
                            if duration_sec > 0:
                                break

                return {
                    "title": title,
                    "publish_date": publish_date,
                    "webpage_url": webpage_url,
                    "uploader": uploader,
                    "duration_sec": duration_sec,
                }
        except Exception:
            continue

    if duration_sec <= 0:
        exts = (".mp4", ".mkv", ".mov", ".m4v", ".webm", ".ts")

        for ext in exts:
            v_p = original_base_abs + ext
            if os.path.exists(v_p):
                duration_sec = processor._get_video_duration(v_p)
                if duration_sec > 0:
                    break

        if duration_sec <= 0:
            try:
                for ext in exts:
                    for p in Path(base_dir).glob(f"{base_name}*{ext}"):
                        duration_sec = processor._get_video_duration(str(p))
                        if duration_sec > 0:
                            break
                    if duration_sec > 0:
                        break
            except Exception:
                pass

    return {
        "title": title,
        "publish_date": publish_date,
        "webpage_url": webpage_url,
        "uploader": uploader,
        "duration_sec": duration_sec,
    }