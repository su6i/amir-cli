import re
from pathlib import Path
from typing import Any, Dict, List

from subtitle.config import get_language_config


def validate_and_retry_translations(
    processor,
    source_lang: str,
    target_langs: List[str],
    result: Dict[str, Any],
    src_srt: str,
) -> None:
    """Ensure translated targets are complete; retry untranslated lines with context."""
    for tgt in target_langs:
        if tgt == source_lang:
            continue

        tgt_srt = result.get(tgt) or src_srt.replace(f"_{source_lang}.srt", f"_{tgt}.srt")
        if not os_path_exists(tgt_srt):
            continue

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                tgt_entries = processor.parse_srt(tgt_srt)
                for e in tgt_entries:
                    e["text"] = processor.fix_persian_text(e["text"])

                with open(tgt_srt, "w", encoding="utf-8-sig") as f:
                    for idx, entry in enumerate(tgt_entries, 1):
                        f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")

                src_entries = processor.parse_srt(src_srt)
                untranslated_indices = []
                lang_config = get_language_config(tgt)

                for i, entry in enumerate(tgt_entries):
                    text = entry["text"].strip()
                    if not text:
                        untranslated_indices.append(i)
                        continue

                    if lang_config.char_range:
                        char_start, char_end = lang_config.char_range
                        has_target_chars = any(char_start <= c <= char_end for c in text)
                        if not has_target_chars:
                            has_parenthetical_english = bool(re.search(r"\([A-Za-z0-9\s\-]+\)", text))
                            if not has_parenthetical_english:
                                untranslated_indices.append(i)
                    else:
                        if i < len(src_entries) and text == src_entries[i]["text"].strip():
                            untranslated_indices.append(i)

                if not untranslated_indices:
                    processor.logger.info(
                        f"✅ Translation validation: 100% of lines translated to {tgt.upper()}"
                    )
                    break

                untranslated_count = len(untranslated_indices)
                total_count = len(tgt_entries)
                percentage = (total_count - untranslated_count) / total_count * 100

                processor.logger.warning(
                    f"⚠️ Incomplete translation: {untranslated_count}/{total_count} lines "
                    f"({100-percentage:.1f}%) not translated to {tgt.upper()}"
                )

                try:
                    rows = []
                    for idx in untranslated_indices:
                        line_no = idx + 1
                        text = tgt_entries[idx]["text"].replace("\n", " ").strip()
                        if not text and idx < len(src_entries):
                            text = src_entries[idx]["text"].replace("\n", " ").strip()
                        if len(text) > 240:
                            text = text[:237] + "..."
                        rows.append((line_no, text))

                    idx_width = max((len(str(r[0])) for r in rows), default=4)
                    print("\n📋 Untranslated lines:\n")
                    print(f"{'Line'.rjust(idx_width)}  | Text")
                    print("-" * (idx_width + 3 + 80))
                    for ln, txt in rows:
                        print(f"{str(ln).rjust(idx_width)}  | {txt}")
                    print(f"\nTotal untranslated: {untranslated_count}/{total_count}\n")
                except Exception as e:
                    processor.logger.warning(f"⚠️ Error printing table: {e}")
                    processor.logger.info(
                        f"📋 Untranslated line indices: {untranslated_indices[:10]}"
                        f"{'...' if len(untranslated_indices) > 10 else ''}"
                    )

                processor.logger.warning(
                    f"⚠️ Incomplete translation (attempt {retry_count + 1}/{max_retries}): "
                    f"{untranslated_count}/{total_count} lines ({100-percentage:.1f}%) "
                    f"not translated to {tgt.upper()}"
                )

                retry_count += 1
                processor.logger.info(
                    f"🔄 Retrying translation for {untranslated_count} lines "
                    f"(Attempt {retry_count}/{max_retries})..."
                )

                retried_translations = []
                for idx in untranslated_indices:
                    text_to_retry = src_entries[idx]["text"] if idx < len(src_entries) else ""
                    prev_lines = [src_entries[i]["text"] for i in range(max(0, idx - 3), idx)]
                    next_lines = [
                        src_entries[i]["text"]
                        for i in range(idx + 1, min(len(src_entries), idx + 4))
                    ]

                    try:
                        translation = processor.translate_single_with_context(
                            text_to_retry,
                            prev_lines,
                            next_lines,
                            tgt,
                            source_lang,
                        )
                        retried_translations.append(translation)
                    except Exception as e:
                        processor.logger.error(f"Failed to retry line {idx+1}: {e}")
                        retried_translations.append(None)

                for idx, new_translation in zip(untranslated_indices, retried_translations):
                    if new_translation and new_translation.strip() and idx < len(tgt_entries):
                        tgt_entries[idx]["text"] = new_translation

                with open(tgt_srt, "w", encoding="utf-8-sig") as f:
                    for idx, entry in enumerate(tgt_entries, 1):
                        f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")

                print("\n✅ Retried translations results:\n")
                success_rows = []
                for idx, new_translation in zip(untranslated_indices, retried_translations):
                    if new_translation and new_translation.strip() and idx < len(src_entries):
                        line_no = idx + 1
                        source_text = src_entries[idx]["text"].replace("\n", " ").strip()
                        trans_text = new_translation.replace("\n", " ").strip()

                        if len(source_text) > 40:
                            source_text = source_text[:37] + "..."
                        if len(trans_text) > 40:
                            trans_text = trans_text[:37] + "..."

                        success_rows.append((line_no, source_text, trans_text))

                if success_rows:
                    idx_w = max(len(str(r[0])) for r in success_rows)
                    src_w = max(len(r[1]) for r in success_rows)

                    print(f"{'Line'.rjust(idx_w)} | {'Source'.ljust(src_w)} | Translation")
                    print("-" * (idx_w + 3 + src_w + 3 + 40))
                    for ln, src, tr in success_rows:
                        print(f"{str(ln).rjust(idx_w)} | {src.ljust(src_w)} | {tr}")
                    print(
                        f"\nSuccessfully retried: {len(success_rows)}/{len(untranslated_indices)}\n"
                    )
                else:
                    print("No lines were successfully retried.\n")

                processor.logger.info(f"💾 Updated {Path(tgt_srt).name} with retried translations")

            except Exception as e:
                processor.logger.error(f"❌ Validation/retry failed: {e}")
                break

        if retry_count >= max_retries:
            processor.logger.warning(
                f"⚠️ Maximum retries ({max_retries}) reached. "
                "Some lines may remain untranslated."
            )


def os_path_exists(path: str) -> bool:
    try:
        import os

        return bool(path) and os.path.exists(path)
    except Exception:
        return False