import re
from typing import Callable, Dict, List, Set


def apply_semantic_splitting(
    entries: List[Dict],
    max_chars: int,
    split_at_best_point_fn: Callable[[Dict, int], List[Dict]],
) -> List[Dict]:
    """Split each entry to keep lines within width constraints."""
    split_entries: List[Dict] = []
    for entry in entries:
        split_entries.extend(split_at_best_point_fn(entry, max_chars))
    return split_entries


def normalize_and_fix_timing(
    entries: List[Dict],
    min_duration: float,
    parse_to_sec_fn: Callable[[str], float],
    format_time_fn: Callable[[float], str],
) -> List[Dict]:
    """Enforce minimum duration, pad silent gaps, and resolve overlaps."""
    cleaned: List[Dict] = []
    last_end = 0.0

    for i, entry in enumerate(entries):
        start = parse_to_sec_fn(entry["start"])
        end = parse_to_sec_fn(entry["end"])

        if end - start < min_duration:
            end = start + min_duration

        next_start_time = parse_to_sec_fn(entries[i + 1]["start"]) if i + 1 < len(entries) else 1e9
        gap = next_start_time - end
        if gap > 0.3:
            padding = min(0.5, gap - 0.05)
            end += padding

        if start < last_end:
            overlap = last_end - start
            if overlap > 0:
                start = last_end
                if end - start < min_duration:
                    end = start + min_duration

        entry["start"] = format_time_fn(start)
        entry["end"] = format_time_fn(end)
        cleaned.append(entry)
        last_end = end

    return cleaned


def deduplicate_consecutive_entries(cleaned: List[Dict]) -> List[Dict]:
    """Merge consecutive identical subtitle texts into a single entry."""
    deduped: List[Dict] = []
    for entry in cleaned:
        if deduped and entry["text"].strip() == deduped[-1]["text"].strip():
            deduped[-1]["end"] = entry["end"]
            continue
        deduped.append(entry)
    return deduped


def postprocess_orphans_and_collocations(
    cleaned: List[Dict],
    max_chars: int,
    load_collocations_fn: Callable[[], Set[str]],
    remove_whisper_artifacts_fn: Callable[[str], str],
    clean_bidi_fn: Callable[[str], str],
    fix_persian_text_fn: Callable[[str], str],
) -> List[Dict]:
    """Apply orphan merge policy and NBSP insertion for known collocations."""
    collocations = load_collocations_fn()

    final: List[Dict] = []
    i = 0
    while i < len(cleaned):
        cur = cleaned[i]
        text = cur.get("text", "").strip()
        text = remove_whisper_artifacts_fn(text)
        cur["text"] = text

        ctext = clean_bidi_fn(text)
        words = ctext.split()

        # Persian verb-prefix repair across subtitle boundaries:
        # if current ends with standalone "می"/"نمی" and next starts with a word,
        # move next first token to current as a joined verb (e.g., "می" + "بره" -> "می\u200cبره").
        nxt = cleaned[i + 1] if i + 1 < len(cleaned) else None
        if nxt:
            ccur = clean_bidi_fn(cur.get("text", "")).strip()
            cnxt = clean_bidi_fn(nxt.get("text", "")).strip()

            parts = ccur.split()
            nxt_parts = cnxt.split()
            if parts and nxt_parts and parts[-1] in ("می", "نمی"):
                prefix = parts[-1]
                first_next = nxt_parts[0]
                joined = f"{prefix}\u200c{first_next}"

                new_cur_parts = parts[:-1] + [joined]
                cur["text"] = " ".join(new_cur_parts).strip()

                remaining_next = " ".join(nxt_parts[1:]).strip()
                if remaining_next:
                    nxt["text"] = remaining_next
                    ctext = clean_bidi_fn(cur["text"])
                    words = ctext.split()
                else:
                    cur["end"] = nxt["end"]
                    i += 1
                    ctext = clean_bidi_fn(cur["text"])
                    words = ctext.split()

        if len(words) <= 2 or len(ctext) < 12:
            prev = final[-1] if final else None
            merged_with_next = False
            orphan_max = 60

            if nxt:
                cnxt_text = clean_bidi_fn(nxt["text"])
                right_first = re.findall(r"[\w\u0600-\u06FF'-]+", cnxt_text)
                if right_first:
                    pair = f"{words[0].lower()} {right_first[0].lower()}"
                    if pair in collocations:
                        combined_clean = ctext + " " + cnxt_text
                        if len(combined_clean) <= orphan_max:
                            nxt["start"] = cur["start"]
                            nxt["text"] = combined_clean
                            i += 1
                            merged_with_next = True
                            continue

            if prev and not merged_with_next:
                cprev = clean_bidi_fn(prev["text"])
                combined_clean = cprev + " " + ctext
                if len(combined_clean) <= orphan_max:
                    prev["end"] = cur["end"]
                    prev["text"] = combined_clean
                    i += 1
                    continue

        if text:
            words_only = [w for w in re.findall(r"[\w\u0600-\u06FF'-]+", text)]
            if words_only:
                rebuilt = text
                for left, right in zip(words_only, words_only[1:]):
                    pair = f"{left.lower()} {right.lower()}"
                    if pair in collocations:
                        rebuilt = re.sub(
                            re.escape(left) + r"\s+" + re.escape(right),
                            left + "\u00A0" + right,
                            rebuilt,
                            flags=re.IGNORECASE,
                        )
                cur["text"] = rebuilt

        # Final Persian normalization pass for ZWNJ compounds.
        # Applies only when Persian/Arabic script is present.
        if re.search(r"[\u0600-\u06FF]", cur.get("text", "")):
            cur["text"] = fix_persian_text_fn(cur["text"])

        final.append(cur)
        i += 1

    for idx, entry in enumerate(final, 1):
        entry["index"] = str(idx)

    return final
