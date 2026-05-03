import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict


def _download_yt_source_srt(processor, video_path: str, source_lang: str, dest_srt: str) -> bool:
    """Attempt to download YouTube subtitles for source_lang via yt-dlp.

    Strategy:
    1. Manual (human-curated) subtitles for source_lang
    2. Auto-generated subtitles for source_lang as fallback

    Returns True if dest_srt was written, False otherwise.
    """
    try:
        import shutil as _shutil
        yt_dlp_bin = _shutil.which("yt-dlp")
        if not yt_dlp_bin:
            processor.logger.warning("⚠️  yt-dlp not found in PATH; cannot fetch YouTube subtitles.")
            return False

        # Derive the video URL from the video file's .info.json sidecar if available.
        # The info.json is written by yt-dlp alongside the video file.
        video_path_obj = Path(video_path)
        info_json = video_path_obj.with_suffix("").with_suffix(".mp4.info.json")
        if not info_json.exists():
            # Try common suffixed variants (e.g. _480p.mp4.info.json)
            for candidate in video_path_obj.parent.glob(f"{video_path_obj.stem}*.info.json"):
                info_json = candidate
                break

        url = None
        if info_json.exists():
            try:
                import json
                with open(info_json, "r", encoding="utf-8") as _f:
                    _meta = json.load(_f)
                url = _meta.get("webpage_url") or _meta.get("original_url")
            except Exception:
                pass

        if not url:
            processor.logger.warning(
                "⚠️  Cannot determine YouTube URL from info.json sidecar; skipping yt-dlp subtitle fetch."
            )
            return False

        base_no_ext = str(video_path_obj.with_suffix("").with_suffix(""))
        # Derive the same canonical base used by the rest of the pipeline
        # (strip resolution/quality suffixes like _480p, _720p from the basename)
        import re as _re
        base_no_ext = _re.sub(r'_\d{3,4}p$', '', base_no_ext)

        langs_to_try = [source_lang, f"{source_lang}-orig"]
        langs_csv = ",".join(langs_to_try)

        with tempfile.TemporaryDirectory() as _tmpdir:
            tmp_base = os.path.join(_tmpdir, "sub")

            # Pass 1: manual (human-curated) subtitles
            processor.logger.info(f"📥 Trying YouTube manual subtitles for: {source_lang}")
            _run_yt_dlp_sub_fetch(yt_dlp_bin, url, tmp_base, langs_csv, auto=False)

            found = _find_best_srt(_tmpdir, source_lang)
            if not found:
                # Pass 2: auto-generated subtitles
                processor.logger.info(f"📥 Manual missing; trying auto subtitles for: {source_lang}")
                _run_yt_dlp_sub_fetch(yt_dlp_bin, url, tmp_base, langs_csv, auto=True)
                found = _find_best_srt(_tmpdir, source_lang)

            if found:
                shutil.copy2(found, dest_srt)
                processor.logger.info(
                    f"✅ YouTube subtitle fetched → {Path(dest_srt).name}"
                )
                return True

        processor.logger.warning(f"❌ No YouTube subtitles found for lang: {source_lang}")
        return False

    except Exception as e:
        processor.logger.warning(f"⚠️  yt-dlp subtitle fetch failed: {e}")
        return False


def _run_yt_dlp_sub_fetch(yt_dlp_bin: str, url: str, base_out: str, langs_csv: str, auto: bool) -> None:
    """Run yt-dlp to download subtitles into base_out directory."""
    cmd = [
        yt_dlp_bin,
        "--quiet",
        "--skip-download",
        "--convert-subs", "srt",
        "--sleep-subtitles", "1",
        "-o", f"{base_out}.%(ext)s",
    ]
    if auto:
        cmd += ["--write-auto-subs", "--no-write-subs"]
    else:
        cmd += ["--write-subs", "--no-write-auto-subs"]
    cmd += ["--sub-langs", langs_csv, url]
    try:
        subprocess.run(cmd, check=False, capture_output=True, timeout=60)
    except Exception:
        pass


def _find_best_srt(directory: str, lang: str) -> str:
    """Return the best matching SRT file for lang in directory, or empty string."""
    # Prefer exact match, then accept -orig variant
    for pattern in [f"*.{lang}.srt", f"*.{lang}-orig.srt", f"*.{lang}*.srt"]:
        for path in Path(directory).glob(pattern):
            if path.stat().st_size > 50:
                return str(path)
    return ""


def prepare_source_srt(
    processor,
    result: Dict[str, Any],
    original_base: str,
    source_lang: str,
    force: bool,
    current_video_input: str,
    limit_start: float,
    limit_end,
    correct: bool,
    detect_speakers: bool,
    has_limit: bool,
    is_srt_input: bool,
    migrate_legacy_resolution_srt_fn: Callable[[str, str], bool],
    emit_progress,
    yt_subs: bool = False,
) -> str:
    """Prepare source SRT via reuse or transcription and apply source pre-processing."""
    src_srt = f"{original_base}_{source_lang}.srt"
    migrate_legacy_resolution_srt_fn(source_lang, src_srt)
    processor.logger.info(f"🔎 Source transcription candidate: {src_srt}")

    if os.path.exists(src_srt) and not force:
        try:
            if os.path.getsize(src_srt) < 50:
                processor.logger.warning(
                    "Existing asset verification failed (undersized); initiating regeneration."
                )
                os.remove(src_srt)
            else:
                processor.logger.info(f"Source asset validation successful: {Path(src_srt).name}")
        except Exception:
            pass
    elif os.path.exists(src_srt) and force:
        processor.logger.info(f"🔄 Force mode enabled; overriding existing asset: {Path(src_srt).name}")
        os.remove(src_srt)

    if not os.path.exists(src_srt):
        if yt_subs:
            # The pre-fetcher in video.sh may not have downloaded the source-language SRT
            # (e.g. user ran --yt-subs but the prefetch only covered target langs like 'fa').
            # Try to fetch it directly before falling back to Whisper.
            processor.logger.info(
                f"⬇️  --yt-subs: source SRT not pre-fetched; attempting yt-dlp download for '{source_lang}'..."
            )
            _yt_downloaded = _download_yt_source_srt(
                processor=processor,
                video_path=current_video_input,
                source_lang=source_lang,
                dest_srt=src_srt,
            )
            if not _yt_downloaded:
                processor.logger.warning(
                    f"⚠️  No YouTube subtitles found for '{source_lang}'. Falling back to Whisper transcription."
                )
                yt_subs = False  # allow Whisper branch below

        if not yt_subs and not os.path.exists(src_srt):
            processor.logger.info(
                "🎙️ Reusable source transcription not found after probe; Whisper transcription will run."
            )
            actual_dur = (limit_end - limit_start) if limit_end is not None else 0
            emit_progress(5, "🎙️ Transcription with Whisper...")
            generated_srt = processor.transcribe_video(
                current_video_input,
                source_lang,
                correct,
                detect_speakers,
                dur=actual_dur,
            )

            processor.cleanup()

            generated_is_path = isinstance(generated_srt, (str, os.PathLike)) and os.path.exists(str(generated_srt))
            generated_is_raw_srt = isinstance(generated_srt, str) and "-->" in generated_srt and "\n" in generated_srt

            if generated_is_path:
                generated_srt_path = os.path.abspath(os.fspath(generated_srt))
                if generated_srt_path != os.path.abspath(src_srt):
                    processor.logger.info(f"📦 Moving temp SRT to final path: {Path(src_srt).name}")
                    shutil.move(generated_srt_path, src_srt)
            elif generated_is_raw_srt:
                processor.logger.info(f"📝 Writing transcription content to: {Path(src_srt).name}")
                with open(src_srt, "w", encoding="utf-8-sig") as f:
                    f.write(generated_srt)
            else:
                raise FileNotFoundError(
                    "transcribe_video did not return a valid SRT path or raw SRT content"
                )

        src_is_fresh = True
    else:
        processor.logger.info(f"✅ Reusing source transcription without Whisper: {Path(src_srt).name}")
        src_is_fresh = False

    src_entries = processor.parse_srt(src_srt)
    if not isinstance(src_entries, list):
        src_entries = []

    # Re-segment reused source subtitles only when explicitly requested.
    # Re-applying segmentation on every run can progressively alter cue cadence.
    resegment_reused = str(os.environ.get("AMIR_RESEGMENT_REUSED_SOURCE", "0")).strip().lower() in {
        "1", "true", "yes", "on"
    }

    if not src_is_fresh and src_entries:
        if resegment_reused:
            resegged_src = processor.resegment_existing_entries(src_entries)
            if isinstance(resegged_src, list) and resegged_src:
                src_entries = resegged_src
                processor.logger.info(
                    f"♻️ Re-segmented reused source subtitles: {Path(src_srt).name}"
                )
        else:
            processor.logger.info(
                "ℹ️ Reused source re-segmentation skipped (set AMIR_RESEGMENT_REUSED_SOURCE=1 to enable)."
            )

    if has_limit and is_srt_input:
        def ts_to_sec(ts: str) -> float:
            ts = ts.replace(",", ".")
            parts = ts.split(":")
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

        before = len(src_entries)
        src_entries = [
            e
            for e in src_entries
            if ts_to_sec(e["start"]) >= limit_start
            and (limit_end is None or ts_to_sec(e["start"]) < limit_end)
        ]
        processor.logger.info(
            f"⏱️  Filtered {before} → {len(src_entries)} entries within "
            f"[{limit_start}s, {'end' if limit_end is None else str(limit_end) + 's'}]"
        )

    # Avoid repeated semantic splitting on already-produced source SRT by default.
    extra_sanitize = str(os.environ.get("AMIR_SOURCE_EXTRA_SANITIZE", "0")).strip().lower() in {
        "1", "true", "yes", "on"
    }
    if extra_sanitize:
        sanitized = processor.sanitize_entries(src_entries)
        if isinstance(sanitized, list):
            src_entries = sanitized

    merged = processor._merge_split_numbers(src_entries)
    if isinstance(merged, list):
        src_entries = merged

    avg_words = sum(len((e.get("text") or "").split()) for e in src_entries) / max(1, len(src_entries))
    src_is_fragmented = len(src_entries) >= 60 and avg_words < 2.3

    if src_is_fragmented and not src_is_fresh:
        processor.logger.info(
            f"📐 Detected fragmented source timeline (avg words/entry={avg_words:.2f}); "
            "applying clause merge."
        )
    
    if src_is_fragmented:
        merged_clauses = processor.merge_to_clauses(src_entries)
        if isinstance(merged_clauses, list):
            src_entries = merged_clauses

        re_sanitized = processor.sanitize_entries(src_entries)
        if isinstance(re_sanitized, list):
            src_entries = re_sanitized
            
    # Always commit the sanitized output back to disk to enforce geometry bounds
    with open(src_srt, "w", encoding="utf-8-sig") as f:
        for idx, entry in enumerate(src_entries, 1):
            f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")

    result[source_lang] = src_srt
    return src_srt