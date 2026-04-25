import os
import re
import json
from pathlib import Path
from typing import Any, Callable, Dict, List

from subtitle.config import has_target_language_chars


def _env_flag(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        parsed = int(val.strip())
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        parsed = float(val.strip())
        if parsed <= 0:
            return default
        return min(parsed, 1.0)
    except Exception:
        return default


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", (text or "").strip()) if w])


def _is_probable_mismatch(src_text: str, tgt_text: str, target_lang: str) -> bool:
    src = (src_text or "").strip()
    tgt = (tgt_text or "").strip()

    if not tgt:
        return True

    src_words = _word_count(src)
    tgt_words = _word_count(tgt)

    if src_words >= 6 and tgt_words <= 1:
        return True

    src_chars = len(src)
    tgt_chars = len(tgt)
    if src_chars >= 35 and tgt_chars <= 4:
        return True

    if target_lang == "fa":
        if not has_target_language_chars(tgt, "fa"):
            return True

    # If a long source line is nearly copied as-is, it is likely untranslated.
    if src_chars >= 20 and tgt.lower() == src.lower():
        return True

    return False


def _save_qc_report(report_path: str, report: Dict[str, Any]) -> None:
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception:
        # Non-fatal by design: QC reporting must never break translation pipeline.
        pass


def _run_semantic_quality_gate(
    processor,
    source_texts: List[str],
    translated: List[str],
    target_lang: str,
    source_lang: str,
) -> tuple[List[str], Dict[str, Any]]:
    if not isinstance(translated, list):
        translated = []

    qc_enabled = _env_flag("AMIR_SUBTITLE_SEMANTIC_QC", True)
    base_report: Dict[str, Any] = {
        "enabled": qc_enabled,
        "target_lang": target_lang,
        "source_lang": source_lang,
        "total_lines": len(translated or []),
        "risky_lines_found": 0,
        "selected_for_retry": 0,
        "max_ratio": None,
        "max_lines": None,
        "retried_indices": [],
        "sample": [],
    }
    if not qc_enabled:
        return translated, base_report

    if not translated:
        return translated, base_report

    max_ratio = _env_float("AMIR_SUBTITLE_SEMANTIC_QC_MAX_RATIO", 0.25)
    max_lines = _env_int("AMIR_SUBTITLE_SEMANTIC_QC_MAX_LINES", 80)
    base_report["max_ratio"] = max_ratio
    base_report["max_lines"] = max_lines
    hard_cap = min(max_lines, max(1, int(len(translated) * max_ratio)))

    risky_indices: List[int] = []
    total = min(len(source_texts), len(translated))
    for i in range(total):
        if _is_probable_mismatch(source_texts[i], translated[i], target_lang):
            risky_indices.append(i)

    base_report["risky_lines_found"] = len(risky_indices)

    if not risky_indices:
        return translated, base_report

    selected = risky_indices[:hard_cap]
    base_report["selected_for_retry"] = len(selected)
    base_report["retried_indices"] = [idx + 1 for idx in selected]
    processor.logger.info(
        f"🛡️ Semantic QC: found {len(risky_indices)} risky lines, re-translating {len(selected)} with context"
    )

    fixed = list(translated)
    for idx in selected:
        prev_lines = source_texts[max(0, idx - 2):idx]
        next_lines = source_texts[idx + 1:min(len(source_texts), idx + 3)]
        new_text = processor.translate_single_with_context(
            source_texts[idx],
            prev_lines,
            next_lines,
            target_lang,
            source_lang,
        )
        if new_text and new_text.strip():
            fixed[idx] = new_text

    for idx in selected[:15]:
        base_report["sample"].append(
            {
                "line": idx + 1,
                "source": source_texts[idx],
                "before": translated[idx],
                "after": fixed[idx],
            }
        )

    return fixed, base_report


def _translate_with_selected_provider(
    processor,
    texts: List[str],
    tgt: str,
    source_lang: str,
    original_entries: List[Dict[str, str]],
    output_srt: str,
    existing_translations: Dict[int, str],
) -> List[str]:
    if processor.llm_choice == "gemini":
        return processor.translate_with_gemini(
            texts,
            tgt,
            source_lang,
            original_entries=original_entries,
            output_srt=output_srt,
            existing_translations=existing_translations,
        )
    if processor.llm_choice == "litellm":
        return processor.translate_with_litellm(
            texts,
            tgt,
            source_lang,
            original_entries=original_entries,
            output_srt=output_srt,
            existing_translations=existing_translations,
        )
    if processor.llm_choice == "minimax":
        return processor.translate_with_minimax(
            texts,
            tgt,
            source_lang,
            original_entries=original_entries,
            output_srt=output_srt,
            existing_translations=existing_translations,
        )
    if processor.llm_choice == "grok":
        return processor.translate_with_grok(
            texts,
            tgt,
            source_lang,
            original_entries=original_entries,
            output_srt=output_srt,
            existing_translations=existing_translations,
        )
    return processor.translate_with_batch_fallback_chain(
        texts,
        tgt,
        source_lang,
        original_entries=original_entries,
        output_srt=output_srt,
        existing_translations=existing_translations,
    )


def run_translation_stage(
    processor,
    result: Dict[str, Any],
    source_lang: str,
    target_langs: List[str],
    src_srt: str,
    original_base: str,
    force: bool,
    emit_progress,
    migrate_legacy_resolution_srt_fn: Callable[[str, str], bool],
) -> None:
    """Translate source SRT into target languages with resume and resegmentation."""
    semantic_line_lock = _env_flag("AMIR_SUBTITLE_SEMANTIC_LINE_LOCK", True)

    tgt_langs_to_translate = [t for t in target_langs if t != source_lang]
    tgt_count = len(tgt_langs_to_translate)
    emit_progress(
        55,
        f"🌐 Starting translation to {', '.join(t.upper() for t in tgt_langs_to_translate)}...",
    )

    for tgt in target_langs:
        if tgt == source_lang:
            continue

        tgt_srt = f"{original_base}_{tgt}.srt"
        migrate_legacy_resolution_srt_fn(tgt, tgt_srt)

        if os.path.exists(tgt_srt) and not force:
            src_entries_count = len(processor.parse_srt(src_srt))
            if processor.validate_srt(tgt_srt, src_entries_count, tgt):
                resegment_existing_target = _env_flag("AMIR_RESEGMENT_EXISTING_TARGET", False)
                if resegment_existing_target:
                    try:
                        processor.resegment_existing_srt_file(tgt_srt)
                    except Exception as reseg_err:
                        processor.logger.warning(
                            f"⚠️ Existing target re-segmentation skipped for {Path(tgt_srt).name}: {reseg_err}"
                        )
                else:
                    processor.logger.info(
                        "ℹ️ Existing target re-segmentation skipped (set AMIR_RESEGMENT_EXISTING_TARGET=1 to enable)."
                    )
                processor.logger.info(f"✓ Target asset verification successful: {Path(tgt_srt).name}")
                result[tgt] = tgt_srt
                continue
            processor.logger.info(
                f"� Smart Resume: Target asset {Path(tgt_srt).name} "
                "is incomplete or untranslated. Recovering good segments..."
            )

        processor.logger.info(f"--- Translation Sequence initiated (Target ISO: {tgt.upper()}) ---")
        tgt_idx = tgt_langs_to_translate.index(tgt) if tgt in tgt_langs_to_translate else 0
        start_pct = 55 + int(tgt_idx / max(1, tgt_count) * 20)
        emit_progress(start_pct, f"🌐 Translating to {tgt.upper()}...")

        try:
            entries = processor.parse_srt(src_srt)
            if not isinstance(entries, list):
                entries = result.get("entries", []) if isinstance(result.get("entries"), list) else []

            recovered_map = {}
            if not force:
                recovered_partial = processor._ingest_partial_srt(
                    entries, tgt_srt.replace(".srt", "_partial.srt"), tgt
                )
                if isinstance(recovered_partial, dict):
                    recovered_map.update(recovered_partial)

                recovered_full = processor._ingest_partial_srt(entries, tgt_srt, tgt)
                if isinstance(recovered_full, dict):
                    recovered_map.update(recovered_full)

            if semantic_line_lock:
                processor.logger.info(
                    "🧠 Semantic line-lock mode ON: preserving 1:1 source/target subtitle alignment"
                )

                source_texts = [str(entry.get("text", "")) for entry in entries if isinstance(entry, dict)]
                translated = _translate_with_selected_provider(
                    processor,
                    source_texts,
                    tgt,
                    source_lang,
                    entries,
                    tgt_srt,
                    recovered_map,
                )
                if not isinstance(translated, list):
                    translated = list(source_texts)

                translated, qc_report = _run_semantic_quality_gate(
                    processor,
                    source_texts,
                    translated,
                    tgt,
                    source_lang,
                )

                qc_report_path = f"{original_base}_{tgt}_semantic_qc.json"
                _save_qc_report(qc_report_path, qc_report)
                processor.logger.info(f"🧾 Semantic QC report: {Path(qc_report_path).name}")

                if tgt == "fa":
                    translated = [
                        processor.fix_persian_text(processor.strip_english_echo(t)) if t and t.strip() else t
                        for t in translated
                    ]

                with open(tgt_srt, "w", encoding="utf-8-sig") as f:
                    for idx_srt, entry in enumerate(entries, 1):
                        if not isinstance(entry, dict):
                            continue
                        start = str(entry.get("start", "00:00:00,000"))
                        end = str(entry.get("end", "00:00:00,000"))
                        src_text = str(entry.get("text", ""))
                        t_text = translated[idx_srt - 1] if idx_srt - 1 < len(translated) else src_text
                        f.write(f"{idx_srt}\n{start} --> {end}\n{t_text}\n\n")

                if tgt == "fa" and translated:
                    lang_specific_count = sum(
                        1 for t in translated if has_target_language_chars(str(t), tgt)
                    )
                    if lang_specific_count < len(translated) // 2:
                        processor.logger.warning(
                            "⚠️ Translation audit failed: "
                            f"Only {lang_specific_count}/{len(translated)} lines are Persian. "
                            "LLM may have hallucinated or failed."
                        )

                result[tgt] = tgt_srt
                processor.logger.info(f"✓ Final save completed: {Path(tgt_srt).name}")
                continue

            paragraph_groups = processor._group_entries_into_paragraphs(entries)
            if not isinstance(paragraph_groups, list):
                paragraph_groups = []
            paragraph_texts = []
            for group in paragraph_groups:
                paragraph_texts.append(" ".join(entries[idx]["text"] for idx in group))

            processor.logger.info(
                f"📐 Paragraph grouping: {len(entries)} fragments → {len(paragraph_texts)} paragraphs"
            )

            para_entries = []
            for group in paragraph_groups:
                para_entries.append(
                    {
                        "start": entries[group[0]]["start"],
                        "end": entries[group[-1]]["end"],
                        "text": " ".join(entries[idx]["text"] for idx in group),
                    }
                )

            translated_paragraphs = _translate_with_selected_provider(
                processor,
                paragraph_texts,
                tgt,
                source_lang,
                para_entries,
                tgt_srt,
                recovered_map,
            )
            if not isinstance(translated_paragraphs, list):
                translated_paragraphs = list(paragraph_texts)

            translated = processor._resegment_translation(entries, paragraph_groups, translated_paragraphs)

            if tgt == "fa":
                translated = [
                    processor.fix_persian_text(processor.strip_english_echo(t)) if t and t.strip() else t
                    for t in translated
                ]

            with open(tgt_srt, "w", encoding="utf-8-sig") as f:
                for idx_srt, entry in enumerate(entries, 1):
                        if not isinstance(entry, dict):
                            continue
                        start = str(entry.get("start", "00:00:00,000"))
                        end = str(entry.get("end", "00:00:00,000"))
                        src_text = str(entry.get("text", ""))
                        t_text = translated[idx_srt - 1] if idx_srt - 1 < len(translated) else src_text
                        f.write(f"{idx_srt}\n{start} --> {end}\n{t_text}\n\n")

            if tgt == "fa" and translated:
                lang_specific_count = sum(
                    1 for t in translated if has_target_language_chars(str(t), tgt)
                )
                if lang_specific_count < len(translated) // 2:
                    processor.logger.warning(
                        "⚠️ Translation audit failed: "
                        f"Only {lang_specific_count}/{len(translated)} lines are Persian. "
                        "LLM may have hallucinated or failed."
                    )

            result[tgt] = tgt_srt
            processor.logger.info(f"✓ Final save completed: {Path(tgt_srt).name}")

        except Exception as e:
            processor.logger.error(f"❌ Translation to {tgt} failed: {e}")
            if processor.fail_on_translation_error:
                raise
            continue