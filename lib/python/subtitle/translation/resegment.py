import re
from typing import Callable, Dict, List


def resegment_translation(
    entries: List[Dict],
    paragraph_groups: List[List[int]],
    translated_paragraphs: List[str],
    slot_max_chars: int,
    vis_len: Callable[[str], int],
) -> List[str]:
    """Re-segment translated paragraphs back onto original subtitle slots."""

    # Sentence-ending punctuation; exclude comma-like separators.
    sent_end = re.compile(r"(?<=[.!?؟…])\s+")
    bad_enders = frozenset(
        {
            "و",
            "در",
            "به",
            "که",
            "از",
            "با",
            "برای",
            "تا",
            "چون",
            "اگر",
            "یا",
            "پس",
            "اما",
            "ولی",
            "هم",
            "نیز",
            "را",
            "این",
            "آن",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
            "of",
            "that",
            "the",
            "a",
            "an",
        }
    )

    result = [""] * len(entries)

    def trim_to_fit(text: str) -> str:
        if vis_len(text) <= slot_max_chars:
            return text
        words_tmp = text.split()
        fitted, budget = [], 0
        for w in words_tmp:
            needed = vis_len(w) + (1 if fitted else 0)
            if budget + needed > slot_max_chars:
                break
            budget += needed
            fitted.append(w)
        return " ".join(fitted) if fitted else text[:slot_max_chars]

    def split_at_punct(text: str) -> List[str]:
        parts = sent_end.split(text.strip())
        out = []
        for part in parts:
            part = part.strip()
            if part:
                out.append(part)
        return out if out else [text.strip()]

    for group_indices, translated_text in zip(paragraph_groups, translated_paragraphs):
        if not translated_text or not translated_text.strip():
            for idx in group_indices:
                result[idx] = entries[idx].get("text", "")
            continue

        n_slots = len(group_indices)
        if n_slots == 1:
            result[group_indices[0]] = trim_to_fit(translated_text.strip())
            continue

        sentences = split_at_punct(translated_text)
        if len(sentences) >= n_slots:
            for i, idx in enumerate(group_indices):
                if i < n_slots - 1:
                    result[idx] = trim_to_fit(sentences[i])
                else:
                    result[idx] = trim_to_fit(" ".join(sentences[i:]))
            continue

        slot_cursor = 0
        for sentence_idx, sentence in enumerate(sentences):
            if slot_cursor >= n_slots:
                break

            sentences_left = len(sentences) - sentence_idx
            slots_left = n_slots - slot_cursor

            if sentences_left == 1 and slots_left > 1:
                sentence_vis = trim_to_fit(sentence)
                if sentence_vis == sentence.strip():
                    for idx in group_indices[slot_cursor:-1]:
                        result[idx] = ""
                    result[group_indices[-1]] = sentence_vis
                else:
                    remaining_slots = group_indices[slot_cursor:]
                    n_remaining = len(remaining_slots)
                    words_fa = sentence.split()
                    chunks = []
                    target_per_chunk = max(1, len(words_fa) // n_remaining)

                    buf_w = []
                    buf_c = 0
                    for wi, w in enumerate(words_fa):
                        buf_w.append(w)
                        buf_c += len(w) + (1 if len(buf_w) > 1 else 0)
                        is_last_word = wi == len(words_fa) - 1
                        chunks_needed = n_remaining - len(chunks)
                        words_left = len(words_fa) - wi - 1

                        should_chunk = False
                        if is_last_word:
                            should_chunk = True
                        elif len(chunks) < n_remaining - 1:
                            ends_punct = (
                                w.rstrip()[-1] in (".", "!", "?", "،", "؛", ",") if w.rstrip() else False
                            )
                            if buf_c >= slot_max_chars * 0.7 and ends_punct:
                                should_chunk = True
                            elif buf_c >= slot_max_chars:
                                while (
                                    len(buf_w) > 1
                                    and buf_w[-1].lower().rstrip(".,!?؟،") in bad_enders
                                ):
                                    words_fa.insert(wi + 1 - (len(buf_w) - len(buf_w)), buf_w.pop())
                                should_chunk = True
                            elif len(buf_w) >= target_per_chunk and words_left >= chunks_needed - 1:
                                should_chunk = True

                        if should_chunk and buf_w:
                            chunks.append(trim_to_fit(" ".join(buf_w).strip()))
                            buf_w = []
                            buf_c = 0

                    while len(chunks) < n_remaining:
                        chunks.append(chunks[-1] if chunks else "")
                    chunks = chunks[:n_remaining]

                    for k, idx in enumerate(remaining_slots):
                        result[idx] = chunks[k]
                slot_cursor = n_slots
            else:
                result[group_indices[slot_cursor]] = trim_to_fit(sentence)
                slot_cursor += 1

        for k in range(slot_cursor, n_slots):
            result[group_indices[k]] = result[group_indices[max(0, slot_cursor - 1)]]

    return result