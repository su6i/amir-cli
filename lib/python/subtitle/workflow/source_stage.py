import os
import shutil
from pathlib import Path
from typing import Any, Callable, Dict


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

        if os.path.abspath(generated_srt) != os.path.abspath(src_srt):
            processor.logger.info(f"📦 Moving temp SRT to final path: {Path(src_srt).name}")
            shutil.move(generated_srt, src_srt)

        src_is_fresh = True
    else:
        processor.logger.info(f"✅ Reusing source transcription without Whisper: {Path(src_srt).name}")
        src_is_fresh = False

    src_entries = processor.parse_srt(src_srt)

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

    src_entries = processor.sanitize_entries(src_entries)
    src_entries = processor._merge_split_numbers(src_entries)

    avg_words = sum(len((e.get("text") or "").split()) for e in src_entries) / max(1, len(src_entries))
    src_is_fragmented = len(src_entries) >= 60 and avg_words < 2.3

    if src_is_fresh or src_is_fragmented:
        if src_is_fragmented and not src_is_fresh:
            processor.logger.info(
                f"📐 Detected fragmented source timeline (avg words/entry={avg_words:.2f}); "
                "applying clause merge."
            )
        src_entries = processor.merge_to_clauses(src_entries)
        src_entries = processor.sanitize_entries(src_entries)
        with open(src_srt, "w", encoding="utf-8-sig") as f:
            for idx, entry in enumerate(src_entries, 1):
                f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")

    result[source_lang] = src_srt
    return src_srt