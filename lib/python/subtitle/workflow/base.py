import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def resolve_workflow_base(
    processor,
    video_path: str,
    source_lang: str,
    target_langs: List[str],
    post_only: bool,
    render_resolution: Optional[int],
) -> Dict[str, object]:
    """Resolve canonical base paths and normalized input context for workflow."""
    if not isinstance(video_path, (str, os.PathLike)):
        video_path = str(video_path)
    video_path = os.path.abspath(os.fspath(video_path))
    source_lang = (source_lang or "auto").strip().lower()
    target_langs = [str(l).strip().lower() for l in (target_langs or ["auto", "fa"]) if str(l).strip()]

    source_auto_requested = source_lang in ("auto", "detect", "")
    if os.path.exists(video_path) and not post_only:
        safe_path = processor._ensure_safe_input_filename(video_path)
        if isinstance(safe_path, (str, os.PathLike)):
            video_path = os.path.abspath(os.fspath(safe_path))

    original_dir = os.path.dirname(video_path)
    original_stem = Path(video_path).stem

    if "safe_input" in original_stem or "temp_" in original_stem:
        original_stem = re.sub(r"^(temp_\d+_|safe_)", "", original_stem)

    original_stem = re.sub(r"_\d{3,4}p(?:_q\d+)?(?:_\d+)?$", "", original_stem)

    is_srt_input = video_path.lower().endswith(".srt")
    if is_srt_input:
        stem_lang_match = re.search(r"_([a-z]{2,3})$", original_stem)
        if stem_lang_match:
            detected_srt_lang = stem_lang_match.group(1)
            source_lang = detected_srt_lang
            source_auto_requested = False
            original_stem = original_stem[: -len(f"_{detected_srt_lang}")]
        elif original_stem.endswith(f"_{source_lang}"):
            original_stem = original_stem[: -len(f"_{source_lang}")]

    parent_dir = os.path.dirname(original_dir)
    cwd = os.getcwd()
    processor.logger.info(f"📁 Subtitle base resolution cwd: {cwd}")
    normalized_target_stem = processor._sanitize_stem_for_fs(original_stem)
    if not isinstance(normalized_target_stem, str):
        normalized_target_stem = str(original_stem or "")

    def stem_match_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

    target_stem_key = stem_match_key(normalized_target_stem)

    def normalize_candidate_stem(value: str) -> str:
        value = re.sub(r"_\d{3,4}p(?:_q\d+)?(?:_\d+)?$", "", value or "")
        normalized = processor._sanitize_stem_for_fs(value)
        return normalized if isinstance(normalized, str) else str(value or "")

    candidate_bases = [
        os.path.join(cwd, original_stem),
        os.path.join(cwd, normalized_target_stem),
        os.path.join(cwd, original_stem, original_stem),
        os.path.join(cwd, normalized_target_stem, normalized_target_stem),
        os.path.join(original_dir, original_stem),
        os.path.join(parent_dir, original_stem),
        os.path.join(parent_dir, original_stem, original_stem),
    ]

    probe_langs = [
        l
        for l in ([source_lang] + [t for t in (target_langs or []) if t != source_lang])
        if re.fullmatch(r"[a-z]{2,3}", str(l or "").lower())
    ]

    if source_lang in ("auto", "detect", ""):
        for fallback_lang in (
            "en",
            "fa",
            "ar",
            "fr",
            "de",
            "es",
            "tr",
            "it",
            "ru",
            "pt",
            "zh",
            "ja",
            "ko",
        ):
            if fallback_lang not in probe_langs:
                probe_langs.append(fallback_lang)

        scan_dirs = []
        for d in (
            cwd,
            os.path.join(cwd, original_stem),
            original_dir,
            parent_dir,
            os.path.join(parent_dir, original_stem),
        ):
            if d and os.path.isdir(d) and d not in scan_dirs:
                scan_dirs.append(d)
        for scan_dir in scan_dirs:
            try:
                for p in Path(scan_dir).glob("*_*.srt"):
                    m = re.search(r"_([a-z]{2,3})\.srt$", p.name.lower())
                    if m:
                        lang = m.group(1)
                        if lang not in probe_langs:
                            probe_langs.append(lang)
            except Exception:
                continue

    existing_base = None
    for b in candidate_bases:
        for l in probe_langs:
            if os.path.exists(f"{b}_{l}.srt"):
                existing_base = b
                break
        if existing_base:
            break

    if not existing_base:
        search_dirs = []
        for d in (
            cwd,
            os.path.join(cwd, original_stem),
            original_dir,
            parent_dir,
            os.path.join(parent_dir, original_stem),
        ):
            if d and os.path.isdir(d) and d not in search_dirs:
                search_dirs.append(d)

        for search_dir in search_dirs:
            for l in probe_langs:
                try:
                    for p in Path(search_dir).glob(f"*_{l}.srt"):
                        if not p.is_file():
                            continue
                        cand_base = str(p)[: -len(f"_{l}.srt")]
                        cand_stem = os.path.basename(cand_base)
                        cand_norm = normalize_candidate_stem(cand_stem)
                        if cand_norm == normalized_target_stem or stem_match_key(cand_norm) == target_stem_key:
                            existing_base = cand_base
                            break
                except Exception:
                    continue
                if existing_base:
                    break
            if existing_base:
                break

    original_base = existing_base or os.path.join(original_dir, original_stem)
    original_dir = os.path.dirname(original_base)
    original_stem = os.path.basename(original_base)
    lock_key = os.path.abspath(original_base).lower()
    if render_resolution:
        lock_key += f"_{render_resolution}"

    if existing_base:
        processor.logger.info(f"♻️ Canonical base resolved to existing assets: {original_base}")
    else:
        processor.logger.info(f"🆕 Canonical base resolved to new assets: {original_base}")

    return {
        "video_path": video_path,
        "source_lang": source_lang,
        "target_langs": target_langs,
        "source_auto_requested": source_auto_requested,
        "is_srt_input": is_srt_input,
        "original_base": original_base,
        "original_dir": original_dir,
        "original_stem": original_stem,
        "lock_key": lock_key,
    }


def migrate_legacy_resolution_srt(
    processor,
    original_base: str,
    original_dir: str,
    lang_code: str,
    expected_path: str,
) -> bool:
    """Promote legacy *_<res>p_<lang>.srt to shared base name if missing."""
    if os.path.exists(expected_path):
        return True
    try:
        base_name = Path(original_base).name
        parent_dir = Path(original_dir)
        pattern = f"{base_name}_*p_{lang_code}.srt"
        candidates = [p for p in parent_dir.glob(pattern) if p.is_file()]
        if not candidates:
            return False
        candidates.sort(key=lambda p: (p.stat().st_size, p.stat().st_mtime), reverse=True)
        best = candidates[0]
        if best.stat().st_size < 50:
            return False
        shutil.move(str(best), expected_path)
        processor.logger.info(f"📦 Reusing legacy SRT: {best.name} -> {Path(expected_path).name}")
        return True
    except Exception as e:
        processor.logger.warning(f"⚠️ Legacy SRT migration skipped for {lang_code}: {e}")
        return os.path.exists(expected_path)


def detect_subtitle_geometry(processor, video_path: str, target_langs: List[str]) -> Tuple[int, int]:
    """Detect video dimensions and update dynamic subtitle geometry settings.
    
    CRITICAL FIX FOR VERTICAL VIDEOS:
    - Portrait videos (9:16): use HEIGHT for text area calculation (was: width)
    - Ensures sufficient character budget for short-form video subtitles
    - Enforces 4-word-per-line default for mobile-optimized short-form content
    """
    vw, vh = 0, 0
    if video_path.lower().endswith(".srt"):
        return vw, vh

    vw, vh = processor._detect_video_dimensions(video_path)
    if not (vw and vh):
        return vw, vh

    try:
        font_size = float(getattr(getattr(processor, "style_config", None), "font_size", 16) or 16)
    except Exception:
        font_size = 16.0
    rendered_font_px = font_size * (vh / 480.0)
    
    # FIX: For vertical (portrait) videos, use HEIGHT for text area, not WIDTH
    # This gives vertical videos more character budget and prevents aggressive truncation
    if vh > vw:  # Portrait mode
        text_area_px = vh * 0.60  # Use HEIGHT for vertical videos: more generous
    else:
        text_area_px = vw * 0.80  # Keep WIDTH for horizontal videos
    
    rtl_langs = {"fa", "ar", "ur", "he"}
    is_rtl = target_langs and any(l in rtl_langs for l in target_langs)
    avg_glyph_w = rendered_font_px * (0.64 if is_rtl else 0.55)
    max_chars_dyn = max(10, int(text_area_px / avg_glyph_w))
    
    # FIX: For vertical short-form videos, enforce exactly 4 words per line
    # was: max(4, min(10, max_chars_dyn // 4)) → variable 4-10 words (inconsistent)
    # now: 4 words for portrait (short-form), flexible for landscape
    if vh > vw:  # Portrait mode: short-form videos need consistent 4-word lines
        target_words_dyn = 4
    else:
        target_words_dyn = max(4, min(10, max_chars_dyn // 4))  # Keep flexible for desktop
    
    if getattr(processor, "style_config", None) is not None:
        processor.style_config.max_chars = max_chars_dyn
    processor.target_words_per_line = target_words_dyn
    orientation = "📱 Vertical" if vh > vw else "🖥️  Horizontal"
    processor.logger.info(
        f"{orientation} video ({vw}×{vh}): "
        f"font≈{rendered_font_px:.0f}px text_area={text_area_px:.0f}px "
        f"max_chars={max_chars_dyn} target_words={target_words_dyn}"
    )
    return vw, vh