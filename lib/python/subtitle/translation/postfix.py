import os
from typing import Any, Dict, List


def apply_final_target_text_fixes(
    processor,
    source_lang: str,
    target_langs: List[str],
    result: Dict[str, Any],
) -> None:
    """Apply final target-side text cleanup before rendering."""
    if source_lang != "en":
        return

    for tgt in target_langs:
        if tgt == source_lang:
            continue
        tgt_path = result.get(tgt)
        if tgt_path and os.path.exists(tgt_path):
            tgt_entries = processor.parse_srt(tgt_path)
            for e in tgt_entries:
                e["text"] = processor.fix_persian_text(e["text"])
            with open(tgt_path, "w", encoding="utf-8-sig") as f:
                for idx, entry in enumerate(tgt_entries, 1):
                    f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")