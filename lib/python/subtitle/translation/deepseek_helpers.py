from typing import Dict, List, Optional


def build_contextual_batch_text(texts: List[str], target_indices: List[int]) -> str:
    """Build numbered translation payload with nearby non-translated context lines."""
    first_abs = target_indices[0]
    last_abs = target_indices[-1]
    ctx_before = texts[max(0, first_abs - 3): first_abs]
    ctx_after = texts[last_abs + 1: last_abs + 4]

    ctx_section = ""
    if ctx_before or ctx_after:
        parts = []
        if ctx_before:
            parts.append(
                "Previous lines (context only, do NOT translate):\n"
                + "\n".join(f"  • {t}" for t in ctx_before)
            )
        if ctx_after:
            parts.append(
                "Following lines (context only, do NOT translate):\n"
                + "\n".join(f"  • {t}" for t in ctx_after)
            )
        ctx_section = "\n".join(parts) + "\n\nLines to translate:\n"

    current_batch_texts = [texts[idx] for idx in target_indices]
    numbered_lines = "\n".join(f"{idx + 1}. {text}" for idx, text in enumerate(current_batch_texts))
    return ctx_section + numbered_lines


def write_partial_translation_srt(
    output_srt: Optional[str],
    original_entries: Optional[List[Dict]],
    final_result: List[Optional[str]],
) -> None:
    """Persist current translation state to output SRT as checkpoint."""
    if not output_srt or not original_entries:
        return

    with open(output_srt, "w", encoding="utf-8-sig") as f:
        for idx_srt, entry in enumerate(original_entries, 1):
            trans = final_result[idx_srt - 1]
            t_text = trans if trans is not None else entry["text"]
            f.write(f"{idx_srt}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")
