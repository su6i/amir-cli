import os
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional


def prepare_runtime_execution(
    processor,
    video_path: str,
    source_lang: str,
    target_langs: List[str],
    original_stem: str,
    original_base: str,
    is_srt_input: bool,
    source_auto_requested: bool,
    post_only: bool,
    platforms: Optional[List[str]],
    prompt_file: Optional[str],
    post_langs: Optional[List[str]],
    limit_start: Optional[float],
    limit_end: Optional[float],
) -> Dict[str, Any]:
    """Prepare runtime inputs and execution mode before stage pipelines."""
    if post_only:
        try:
            processor.generate_posts(
                original_base,
                source_lang,
                {},
                platforms=platforms or ["telegram"],
                prompt_file=prompt_file,
                post_langs=post_langs,
            )
        except Exception as pe:
            processor.logger.warning(f"⚠️ Post generation skipped (post-only mode): {pe}")
        return {"post_only_done": True}

    processor._check_disk_space(min_gb=1)

    current_video_input = video_path
    temp_vid = None
    limit_start_val = limit_start or 0.0
    has_limit = limit_start_val > 0 or limit_end is not None

    if has_limit:
        info = f"{limit_start_val}s → {'end' if limit_end is None else f'{limit_end}s'}"
        processor.logger.info(f"⏱️  Time range restriction: {info}")
        if is_srt_input:
            processor.logger.info(
                "⏱️  SRT input detected — time-range filter will be applied to entries."
            )
        else:
            temp_vid = os.path.join(
                tempfile.gettempdir(), f"temp_{int(time.time())}_{original_stem}.mp4"
            )
            cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
            if limit_start_val > 0:
                cmd += ["-ss", str(limit_start_val)]
            cmd += ["-i", video_path]
            if limit_end is not None:
                cmd += ["-t", str(limit_end - limit_start_val)]
            cmd += ["-c", "copy", temp_vid]
            subprocess.run(cmd, check=True)
            current_video_input = temp_vid

    final_source_lang = source_lang
    if source_auto_requested and not is_srt_input:
        final_source_lang = processor.detect_source_language(current_video_input)

    resolved_targets: List[str] = []
    for t in target_langs:
        resolved = final_source_lang if t in ("auto", "detect", "source") else t
        if resolved and resolved not in resolved_targets:
            resolved_targets.append(resolved)
    final_target_langs = resolved_targets or [final_source_lang, "fa"]

    return {
        "post_only_done": False,
        "current_video_input": current_video_input,
        "temp_vid": temp_vid,
        "limit_start": limit_start_val,
        "has_limit": has_limit,
        "source_lang": final_source_lang,
        "target_langs": final_target_langs,
    }