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
    """Enforce minimum duration, pad silent gaps, and resolve overlaps.

    Overlap policy (critical for sync accuracy):
    - Minor overlap (<= 0.15s): trim the PREVIOUS entry's end backward to the
      current entry's start. Never shift current start forward unless timing
      order is pathological.
    - Large overlap (> 0.15s): still prefer trimming previous end first to keep
      current cue start anchored to speech; shift current start only as a last
      resort when overlap cannot be removed by trimming previous end.
    """
    small_overlap_sec = 0.15
    min_prev_visible_duration = 0.06
    sync_epsilon = 0.01

    cleaned: List[Dict] = []

    for i, entry in enumerate(entries):
        start = parse_to_sec_fn(entry["start"])
        end = parse_to_sec_fn(entry["end"])

        if end - start < min_duration:
            end = start + min_duration

        next_start_time = parse_to_sec_fn(entries[i + 1]["start"]) if i + 1 < len(entries) else 1e9
        gap = next_start_time - end

        # Tiny gap padding: only a 50ms nudge to prevent subtitle flicker,
        # capped so we never overshoot the next entry's start.
        if 0.1 < gap <= 2.0:
            end = min(end + 0.05, next_start_time - 0.03)

        # Overlap resolution: prefer trimming previous end rather than
        # advancing this start (advancing start causes audio/subtitle drift).
        if cleaned:
            prev = cleaned[-1]
            prev_start = parse_to_sec_fn(prev["start"])
            prev_end = parse_to_sec_fn(prev["end"])
            if start < prev_end:
                overlap = prev_end - start
                if overlap <= small_overlap_sec:
                    # Small overlap: preserve CURRENT start sync and trim previous
                    # cue end aggressively (min-duration on previous cue is soft).
                    desired_prev_end = start - sync_epsilon
                    min_prev_end = prev_start + min_prev_visible_duration
                    new_prev_end = max(min_prev_end, desired_prev_end)
                    prev["end"] = format_time_fn(new_prev_end)

                    # Pathological ordering fallback: previous starts at/after
                    # current start, so trimming cannot fully remove overlap.
                    if start < new_prev_end:
                        start = new_prev_end + sync_epsilon
                        if end - start < min_duration:
                            end = start + min_duration
                else:
                    # Large overlap: still prioritize current-start sync by
                    # trimming previous end first.
                    desired_prev_end = start - sync_epsilon
                    min_prev_end = prev_start + min_prev_visible_duration
                    new_prev_end = max(min_prev_end, desired_prev_end)
                    prev["end"] = format_time_fn(new_prev_end)

                    # Last resort when overlap cannot be resolved by trimming
                    # previous end (pathological timestamp order).
                    if start < new_prev_end:
                        start = new_prev_end + sync_epsilon
                        if end - start < min_duration:
                            end = start + min_duration

        entry["start"] = format_time_fn(start)
        entry["end"] = format_time_fn(end)
        cleaned.append(entry)

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
    preserve_timing: bool = False,
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
                # In whisper-timing passthrough mode, avoid consuming an entire
                # next cue because it would require timing merge.
                if not (preserve_timing and len(nxt_parts) == 1):
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
                        if not preserve_timing:
                            cur["end"] = nxt["end"]
                            i += 1
                        ctext = clean_bidi_fn(cur["text"])
                        words = ctext.split()

        if not preserve_timing and (len(words) <= 2 or len(ctext) < 12):
            prev = final[-1] if final else None
            merged_with_next = False
            # Adaptive orphan limit:
            # - For landscape (max_chars >= 30): use standard 60 chars to preserve segmentation parity.
            # - For portrait (max_chars < 30): use strict geometric bounds to prevent overflow.
            if max_chars >= 30:
                orphan_max = 60
            else:
                orphan_max = int(max(max_chars * 1.2, max_chars + 4))

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

        cur_text = cur.get("text", "").strip()
        if cur_text:
            words_only = [w for w in re.findall(r"[\w\u0600-\u06FF'-]+", cur_text)]
            if words_only:
                rebuilt = cur_text
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
