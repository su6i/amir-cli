import unicodedata
from typing import Dict, List, Tuple


def group_entries_into_paragraphs(entries: List[Dict]) -> List[List[int]]:
    """Group consecutive subtitle entries into sentence-level paragraphs."""
    sentence_enders = {".", "!", "?", "…", "。", "？", "！"}
    groups = []
    current_group = []
    group_start_sec = 0.0
    max_group_seconds = 15.0

    def _ts_to_sec(ts: str) -> float:
        ts = ts.replace(",", ".")
        h, m, s = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    for i, entry in enumerate(entries):
        if not current_group:
            group_start_sec = _ts_to_sec(entry.get("start", "00:00:00,000"))

        current_group.append(i)
        text = entry.get("text", "").strip()

        ends_sentence = False
        if text:
            last_char = text.rstrip()[-1] if text.rstrip() else ""
            if last_char in sentence_enders:
                ends_sentence = True
            if text.rstrip().endswith("...") or text.rstrip().endswith("…"):
                ends_sentence = True

        group_end_sec = _ts_to_sec(entry.get("end", entry.get("start", "00:00:00,000")))
        group_duration = group_end_sec - group_start_sec

        if ends_sentence or len(current_group) >= 8 or group_duration >= max_group_seconds:
            groups.append(current_group)
            current_group = []

    if current_group:
        groups.append(current_group)

    return groups


def take_words_up_to(words: List[str], target_chars: int) -> Tuple[str, List[str]]:
    """Take words up to target chars with punctuation/lexical snapping."""
    if not words:
        return ("", [])

    punctuations = {".", "!", "?", "…", "。", "？", "！", ",", ";", ":", "،", "؛", "»", ")", "}", "]"}
    bad_enders = {
        "و", "در", "به", "که", "از", "با", "برای", "تا", "چون", "اگر",
        "یا", "پس", "اما", "ولی", "هم", "نیز", "را",
        "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "of", "that",
    }

    best_index = 0
    chars_so_far = 0
    best_punctuated_index = -1

    for i, word in enumerate(words):
        word_len = len(word) + (1 if i > 0 else 0)
        chars_so_far += word_len

        ends_in_punct = word.rstrip() and word.rstrip()[-1] in punctuations

        if 0.8 * target_chars <= chars_so_far <= 1.3 * target_chars and ends_in_punct:
            best_punctuated_index = i

        if chars_so_far > 1.3 * target_chars and i > 0:
            break

        if chars_so_far <= target_chars:
            best_index = i
        elif best_index == 0:
            best_index = i

    if best_punctuated_index != -1:
        final_idx = best_punctuated_index
    else:
        final_idx = best_index
        clean_end_word = words[final_idx].rstrip("".join(punctuations)).strip().lower()
        if clean_end_word in bad_enders and final_idx > 0:
            final_idx -= 1

    taken = words[: final_idx + 1]
    remaining = words[final_idx + 1 :]
    return (" ".join(taken).strip(), remaining)


def take_n_words_with_punct_snap(
    words: List[str], target_n: int, min_n: int, max_n: int = None
) -> Tuple[List[str], List[str]]:
    """Take ~target_n words while preferring punctuation boundaries."""
    if not words:
        return ([], [])

    punctuations = {".", "!", "?", "…", "،", "؟", "؛", ",", ";", ":", "。", "？", "！"}
    bad_enders = {
        "و", "در", "به", "که", "از", "با", "برای", "تا", "چون", "اگر",
        "یا", "پس", "اما", "ولی", "هم", "نیز", "را",
        "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "of", "that",
    }

    available = len(words)
    hard_max = min(max_n if max_n is not None else target_n + 1, available)
    final_n = max(min_n, min(target_n, hard_max))

    search_low = min_n - 1
    search_high = min(hard_max - 1, target_n + 1)

    best_punct_idx = -1
    for i in range(search_low, search_high + 1):
        w = words[i].rstrip()
        if w and w[-1] in punctuations:
            best_punct_idx = i

    if best_punct_idx >= 0:
        final_n = best_punct_idx + 1
    else:
        punct_chars = "".join(punctuations)
        while final_n > min_n:
            w = words[final_n - 1].rstrip(punct_chars).strip().lower()
            if w in bad_enders:
                final_n -= 1
            else:
                break

    final_n = max(min_n, min(final_n, hard_max))
    return (words[:final_n], words[final_n:])


def vis_len(s: str) -> int:
    """Visual character length excluding zero-width Unicode format chars."""
    return sum(1 for c in s if unicodedata.category(c) != "Cf")


def is_abbrev_dot(word_text: str, next_word: str, abbreviations: set) -> bool:
    """Detect whether a trailing dot likely belongs to an abbreviation."""
    stripped = word_text.rstrip(".")
    if len(stripped) <= 2:
        return True
    if stripped.lower() in abbreviations:
        return True
    if next_word and next_word[0].islower():
        return True
    return False


def peek_next_clause_words(words: List, idx: int, max_lookahead: int = 20) -> int:
    """Count words in next clause until punctuation boundary."""
    count = 0
    for k in range(idx + 1, min(idx + max_lookahead, len(words))):
        w = words[k].word.strip()
        if not w:
            continue
        count += 1
        if w.endswith(("?", "!", "...", ".", ",", ";", ":")):
            break
    return count


def merge_orphan_segments(entries: List[Dict], hard_limit: int, min_words: int = 4, max_allowance: int = 20, parse_to_sec_fn=None) -> List[Dict]:
    """Merge tiny tail segments into previous when safe for readability, enforcing sync."""
    merged: List[Dict] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        word_count = len(entry["text"].split())

        if word_count < max(2, int(min_words)):
            # Prefer merge to previous when possible.
            if merged:
                prev = merged[-1]
                gap_safe = True
                if parse_to_sec_fn:
                    gap = parse_to_sec_fn(entry["start"]) - parse_to_sec_fn(prev["end"])
                    if gap > 0.25: gap_safe = False
                
                if gap_safe:
                    combined_prev = (prev["text"] + " " + entry["text"]).strip()
                    if len(combined_prev) <= hard_limit + max_allowance:
                        prev["end"] = entry["end"]
                        prev["text"] = " ".join(combined_prev.split())
                        i += 1
                        continue

            # If there is no previous (or previous merge is unsafe), merge into next.
            if i + 1 < len(entries):
                nxt = entries[i + 1]
                gap_safe = True
                if parse_to_sec_fn:
                    gap = parse_to_sec_fn(nxt["start"]) - parse_to_sec_fn(entry["end"])
                    if gap > 0.25: gap_safe = False

                if gap_safe:
                    combined_next = (entry["text"] + " " + nxt["text"]).strip()
                    if len(combined_next) <= hard_limit + max_allowance:
                        nxt["start"] = entry["start"]
                        nxt["text"] = " ".join(combined_next.split())
                        i += 1
                        continue

        merged.append(entry)
        i += 1
    return merged
