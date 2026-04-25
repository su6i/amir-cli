import os
from typing import Any, Dict, List

from subtitle.config import get_language_config


_HIDDEN_NATIVE_CUE_MARKER = "\u061c"


def _is_native_source_line_for_target(text: str, target_lang: str) -> bool:
    """Heuristic: detect source lines that are already in target script."""
    t = str(text or "").strip()
    if not t:
        return False

    lang_cfg = get_language_config(target_lang)
    if not lang_cfg.char_range:
        return False

    char_start, char_end = lang_cfg.char_range
    target_chars = sum(1 for ch in t if char_start <= ch <= char_end)
    latin_chars = sum(1 for ch in t if ("a" <= ch <= "z") or ("A" <= ch <= "Z"))

    if target_chars < 2:
        return False
    if latin_chars == 0:
        return True
    return target_chars >= (latin_chars * 2)


def apply_final_target_text_fixes(
    processor,
    source_lang: str,
    target_langs: List[str],
    result: Dict[str, Any],
) -> None:
    """Apply final target-side text cleanup and native-line visibility policy."""
    native_policy = str(getattr(processor, "native_target_lines", "keep") or "keep").strip().lower()
    if native_policy == "on":
        native_policy = "keep"
    elif native_policy == "off":
        native_policy = "hide"
    if native_policy not in {"keep", "hide"}:
        native_policy = "keep"

    should_fix_persian = source_lang == "en"
    should_process_native_policy = native_policy in {"keep", "hide"}

    if not should_fix_persian and not should_process_native_policy:
        return

    src_entries: List[Dict[str, Any]] = []
    if should_process_native_policy:
        src_path = result.get(source_lang)
        if src_path and os.path.exists(src_path):
            parsed_src = processor.parse_srt(src_path)
            if isinstance(parsed_src, list):
                src_entries = parsed_src

    for tgt in target_langs:
        if tgt == source_lang:
            continue
        tgt_path = result.get(tgt)
        if tgt_path and os.path.exists(tgt_path):
            tgt_entries = processor.parse_srt(tgt_path)
            if not isinstance(tgt_entries, list):
                continue

            changed = False
            if should_fix_persian:
                for e in tgt_entries:
                    old_text = e.get("text", "")
                    new_text = processor.fix_persian_text(old_text)
                    if new_text != old_text:
                        e["text"] = new_text
                        changed = True

            if src_entries:
                changed_count = 0
                pair_count = min(len(src_entries), len(tgt_entries))
                for idx in range(pair_count):
                    src_text = str(src_entries[idx].get("text", ""))
                    if not _is_native_source_line_for_target(src_text, tgt):
                        continue

                    cur_text = str(tgt_entries[idx].get("text", ""))
                    if native_policy == "hide":
                        if cur_text != _HIDDEN_NATIVE_CUE_MARKER:
                            tgt_entries[idx]["text"] = _HIDDEN_NATIVE_CUE_MARKER
                            changed = True
                            changed_count += 1
                    else:
                        if cur_text == _HIDDEN_NATIVE_CUE_MARKER or not cur_text.strip():
                            tgt_entries[idx]["text"] = src_text
                            changed = True
                            changed_count += 1

                if changed_count > 0:
                    mode_label = "hidden" if native_policy == "hide" else "restored"
                    processor.logger.info(
                        f"🧩 Native {tgt.upper()} source lines {mode_label}: {changed_count}"
                    )

            if changed:
                with open(tgt_path, "w", encoding="utf-8-sig") as f:
                    for idx, entry in enumerate(tgt_entries, 1):
                        f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")