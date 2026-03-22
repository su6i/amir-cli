import os
import re
from pathlib import Path
from typing import Callable, Dict, List


def parse_srt_file(srt_path: str) -> List[Dict]:
    with open(srt_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    pattern = re.compile(
        r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:(?!\n\n).)*)",
        re.DOTALL,
    )

    entries: List[Dict] = []
    for m in pattern.finditer(content):
        entries.append(
            {
                "index": m.group(1),
                "start": m.group(2),
                "end": m.group(3),
                "text": m.group(4).strip().replace("\n", " "),
            }
        )
    return entries


def validate_srt_file(
    srt_path: str,
    expected_count: int,
    target_lang: str,
    has_target_language_chars_fn: Callable[[str, str], bool],
    logger=None,
) -> bool:
    """Validate SRT file against entry count, language integrity and repetition patterns."""
    if not os.path.exists(srt_path):
        return False

    try:
        if os.path.getsize(srt_path) < 50:
            return False

        entries = parse_srt_file(srt_path)
        actual_count = len(entries)

        if actual_count != expected_count:
            if logger is not None:
                logger.warning(
                    f"⚠️ Parity mismatch for {Path(srt_path).name}: expected {expected_count}, found {actual_count}."
                )
            return False

        texts = [e["text"].strip() for e in entries if e["text"].strip()]
        if not texts:
            return False

        if target_lang == "fa":
            persian_lines = sum(1 for t in texts if has_target_language_chars_fn(t, target_lang))
            ratio = persian_lines / actual_count
            if ratio < 0.98:
                if logger is not None:
                    logger.warning(
                        f"⚠️ Content audit failed for {Path(srt_path).name}: Only {persian_lines}/{actual_count} ({ratio:.1%}) lines are Persian."
                    )
                return False

        if len(texts) > 50:
            counts = {}
            for t in texts:
                counts[t] = counts.get(t, 0) + 1

            most_common_text = max(counts, key=counts.get)
            max_repeat = counts[most_common_text]

            if max_repeat > len(texts) * 0.05:
                if logger is not None:
                    logger.warning(
                        f"⚠️ Hallucination detected: Sentence '{most_common_text[:40]}...' repeats {max_repeat} times."
                    )
                return False

        return True
    except Exception as e:
        if logger is not None:
            logger.debug(f"Validation error: {e}")
        return False
