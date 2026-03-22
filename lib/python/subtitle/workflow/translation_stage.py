import os
from pathlib import Path
from typing import Any, Callable, Dict, List

from subtitle.config import has_target_language_chars


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

            recovered_map = {}
            if not force:
                recovered_map.update(
                    processor._ingest_partial_srt(entries, tgt_srt.replace(".srt", "_partial.srt"), tgt)
                    or {}
                )
                recovered_map.update(processor._ingest_partial_srt(entries, tgt_srt, tgt) or {})

            paragraph_groups = processor._group_entries_into_paragraphs(entries)
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

            if processor.llm_choice == "gemini":
                translated_paragraphs = processor.translate_with_gemini(
                    paragraph_texts,
                    tgt,
                    source_lang,
                    original_entries=para_entries,
                    output_srt=tgt_srt,
                    existing_translations=recovered_map,
                )
            elif processor.llm_choice == "litellm":
                translated_paragraphs = processor.translate_with_litellm(
                    paragraph_texts,
                    tgt,
                    source_lang,
                    original_entries=para_entries,
                    output_srt=tgt_srt,
                    existing_translations=recovered_map,
                )
            elif processor.llm_choice == "minimax":
                translated_paragraphs = processor.translate_with_minimax(
                    paragraph_texts,
                    tgt,
                    source_lang,
                    original_entries=para_entries,
                    output_srt=tgt_srt,
                    existing_translations=recovered_map,
                )
            elif processor.llm_choice == "grok":
                translated_paragraphs = processor.translate_with_grok(
                    paragraph_texts,
                    tgt,
                    source_lang,
                    original_entries=para_entries,
                    output_srt=tgt_srt,
                    existing_translations=recovered_map,
                )
            else:
                translated_paragraphs = processor.translate_with_batch_fallback_chain(
                    paragraph_texts,
                    tgt,
                    source_lang,
                    original_entries=para_entries,
                    output_srt=tgt_srt,
                    existing_translations=recovered_map,
                )

            translated = processor._resegment_translation(entries, paragraph_groups, translated_paragraphs)

            if tgt == "fa":
                translated = [
                    processor.fix_persian_text(processor.strip_english_echo(t)) if t and t.strip() else t
                    for t in translated
                ]

            with open(tgt_srt, "w", encoding="utf-8-sig") as f:
                for idx_srt, entry in enumerate(entries, 1):
                    t_text = translated[idx_srt - 1] if idx_srt - 1 < len(translated) else entry["text"]
                    f.write(f"{idx_srt}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")

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