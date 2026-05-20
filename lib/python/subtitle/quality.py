"""Subtitle quality assessment and language timeline building for multilingual content."""
from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QualityResult:
    score: float                  # 0.0 = unusable, 1.0 = perfect
    coverage: float               # fraction of video_duration covered by subtitles
    wpm: float                    # words per minute of covered speech
    max_consecutive_repeat: int   # longest run of identical consecutive lines
    max_gap_sec: float            # longest silence gap between subtitle entries
    reason: str = ""              # human-readable reason for score deductions
    _near_dup_ratio: float = 0.0  # fraction of consecutive-entry pairs that are near-duplicates


@dataclass
class LangSegment:
    start: float   # seconds
    end: float     # seconds
    lang: str      # normalized ISO language code (e.g. "he", "en")


# ---------------------------------------------------------------------------
# YouTube language code normalization
# YouTube uses legacy/non-standard codes for some languages.
# ---------------------------------------------------------------------------

_YT_NORMALIZE: Dict[str, str] = {
    "iw": "he",        # Hebrew (old code)
    "ji": "yi",        # Yiddish (old code)
    "jw": "jv",        # Javanese (old code)
    "mo": "ro",        # Moldovan → Romanian
    "in": "id",        # Indonesian (old code)
    "zh-Hans": "zh",
    "zh-Hant": "zh-TW",
    "pt-PT": "pt",
    "en-orig": "en",   # YouTube's "original" English track
}


def normalize_yt_lang(code: str) -> str:
    """Map a YouTube language code to its canonical ISO form."""
    return _YT_NORMALIZE.get(code, code)


def yt_codes_for_lang(lang: str) -> List[str]:
    """Return all YouTube track codes that map to *lang* (including lang itself)."""
    codes = [lang]
    for yt_code, canonical in _YT_NORMALIZE.items():
        if canonical == lang and yt_code not in codes:
            codes.append(yt_code)
    return codes


# ---------------------------------------------------------------------------
# SRT helpers (self-contained; no dependency on rest of subtitle package)
# ---------------------------------------------------------------------------

def _ts_to_sec(ts: str) -> float:
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def _parse_srt(srt_path: str) -> List[Dict]:
    """Parse SRT → list of {start, end, text} (seconds)."""
    entries: List[Dict] = []
    try:
        text = Path(srt_path).read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return entries

    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        for i, line in enumerate(lines):
            m = re.match(
                r"(\d+:\d+:\d+[,\.]\d+)\s*-->\s*(\d+:\d+:\d+[,\.]\d+)", line
            )
            if m:
                try:
                    start = _ts_to_sec(m.group(1))
                    end = _ts_to_sec(m.group(2))
                    body = " ".join(l.strip() for l in lines[i + 1 :] if l.strip())
                    if body:
                        entries.append({"start": start, "end": end, "text": body})
                except Exception:
                    pass
                break
    return entries


# ---------------------------------------------------------------------------
# Quality assessment
# ---------------------------------------------------------------------------

def assess_subtitle_quality(srt_path: str, video_duration: float) -> QualityResult:
    """Score subtitle quality on [0.0, 1.0].

    Checks coverage, speech rate, hallucination loops, and large gaps.
    A score >= 0.65 is generally considered usable as-is for translation.
    """
    entries = _parse_srt(srt_path)
    n = len(entries)

    if n == 0 or video_duration <= 0:
        return QualityResult(0.0, 0.0, 0.0, 0, 0.0, "empty_or_zero_duration")

    # 1. Coverage
    total_sub_sec = sum(max(0.0, e["end"] - e["start"]) for e in entries)
    coverage = min(1.0, total_sub_sec / video_duration)

    # 2. WPM (words per minute of covered speech)
    total_words = sum(len(e["text"].split()) for e in entries)
    wpm = (total_words / total_sub_sec * 60.0) if total_sub_sec > 0 else 0.0

    # 3a. Consecutive-line exact repetition
    texts = [re.sub(r"\s+", " ", e["text"].strip().lower()) for e in entries]
    max_run = max(sum(1 for _ in g) for _, g in groupby(texts)) if texts else 0

    # 3b. Near-duplicate consecutive entries (Jaccard similarity > 0.6)
    # Catches the pattern where Whisper hallucinates slightly varying versions
    # of the same phrase ("על קריטיקה, ...") across many consecutive entries.
    near_dup_pairs = 0
    for i in range(n - 1):
        t1 = set(texts[i].split())
        t2 = set(texts[i + 1].split())
        union = len(t1 | t2)
        if union > 0 and len(t1 & t2) / union > 0.60:
            near_dup_pairs += 1
    near_dup_ratio = near_dup_pairs / max(1, n - 1)  # fraction of pairs that are near-dups

    # 4. Largest gap between entries
    max_gap = 0.0
    for i in range(n - 1):
        gap = entries[i + 1]["start"] - entries[i]["end"]
        if gap > max_gap:
            max_gap = gap

    # ---- Score calculation ------------------------------------------------
    score = 1.0
    reasons: List[str] = []

    # Coverage penalty
    if coverage < 0.35:
        score -= 0.45
        reasons.append(f"very_low_coverage({coverage:.0%})")
    elif coverage < 0.55:
        score -= 0.25
        reasons.append(f"low_coverage({coverage:.0%})")
    elif coverage < 0.72:
        score -= 0.10
        reasons.append(f"partial_coverage({coverage:.0%})")

    # WPM penalty
    if wpm < 40 or wpm > 420:
        score -= 0.35
        reasons.append(f"abnormal_wpm({wpm:.0f})")
    elif wpm < 70 or wpm > 320:
        score -= 0.10
        reasons.append(f"unusual_wpm({wpm:.0f})")

    # Repetition / hallucination penalty (exact repetition)
    if max_run >= 5:
        score -= 0.50
        reasons.append(f"hallucination(run={max_run})")
    elif max_run >= 3:
        score -= 0.22
        reasons.append(f"repetition(run={max_run})")

    # Near-duplicate pairs penalty (e.g. "על קריטיקה" loop variants)
    if near_dup_ratio >= 0.30:
        score -= 0.50
        reasons.append(f"near_dup_loop({near_dup_ratio:.0%})")
    elif near_dup_ratio >= 0.15:
        score -= 0.25
        reasons.append(f"near_dup_high({near_dup_ratio:.0%})")

    # Large-gap penalty (> 3 minutes of silence)
    if max_gap > 180:
        score -= 0.12
        reasons.append(f"large_gap({max_gap:.0f}s)")

    return QualityResult(
        score=max(0.0, min(1.0, score)),
        coverage=coverage,
        wpm=wpm,
        max_consecutive_repeat=max_run,
        max_gap_sec=max_gap,
        reason="; ".join(reasons) if reasons else "ok",
        # extra field for callers that want the raw near-dup ratio
        _near_dup_ratio=near_dup_ratio,
    )


# ---------------------------------------------------------------------------
# Language timeline building
# ---------------------------------------------------------------------------

def build_language_timeline(
    tracks: Dict[str, str],    # {normalized_lang: local_srt_path}
    video_duration: float,
    slot_sec: float = 10.0,    # time resolution for voting
    min_segment_sec: float = 8.0,
) -> List[LangSegment]:
    """Build a non-overlapping language timeline from multiple subtitle tracks.

    Each 10-second slot is assigned to the language with the most words in that
    window.  Adjacent same-language slots are merged into segments.

    Returns a sorted list of LangSegment covering [0, video_duration].
    """
    if not tracks:
        return []

    # Parse all tracks
    parsed: Dict[str, List[Dict]] = {}
    for lang, path in tracks.items():
        try:
            entries = _parse_srt(path)
            if entries:
                parsed[lang] = entries
        except Exception:
            pass

    if not parsed:
        return []

    if len(parsed) == 1:
        only_lang = next(iter(parsed))
        return [LangSegment(0.0, video_duration, only_lang)]

    # Word-density grid: slot_words[lang][slot_idx] = word_count
    n_slots = max(1, int(video_duration / slot_sec) + 2)
    slot_words: Dict[str, List[int]] = {lang: [0] * n_slots for lang in parsed}

    for lang, entries in parsed.items():
        for e in entries:
            s0 = max(0, int(e["start"] / slot_sec))
            s1 = min(n_slots - 1, int(e["end"] / slot_sec))
            w = len(e["text"].split())
            for s in range(s0, s1 + 1):
                slot_words[lang][s] += w

    # Assign each slot to best-covered language (empty = "")
    slot_lang: List[str] = []
    for i in range(n_slots):
        best_lang, best_w = "", 0
        for lang in parsed:
            if slot_words[lang][i] > best_w:
                best_w = slot_words[lang][i]
                best_lang = lang
        slot_lang.append(best_lang if best_w > 0 else "")

    # Forward-fill empty slots from nearest neighbour
    # Pass 1: forward
    last = ""
    for i in range(len(slot_lang)):
        if slot_lang[i]:
            last = slot_lang[i]
        elif last:
            slot_lang[i] = last
    # Pass 2: backward (for leading silence)
    last = ""
    for i in range(len(slot_lang) - 1, -1, -1):
        if slot_lang[i]:
            last = slot_lang[i]
        elif last:
            slot_lang[i] = last

    if not any(slot_lang):
        fallback = next(iter(parsed))
        return [LangSegment(0.0, video_duration, fallback)]

    # Merge consecutive slots with same language into segments
    raw_segments: List[LangSegment] = []
    cur_lang = slot_lang[0]
    cur_start = 0.0
    for i in range(1, n_slots):
        if slot_lang[i] != cur_lang:
            raw_segments.append(LangSegment(cur_start, i * slot_sec, cur_lang))
            cur_lang = slot_lang[i]
            cur_start = i * slot_sec
    raw_segments.append(LangSegment(cur_start, video_duration, cur_lang))

    # Absorb short (<min_segment_sec) segments into their longer neighbour
    merged: List[LangSegment] = []
    for seg in raw_segments:
        dur = seg.end - seg.start
        if merged and dur < min_segment_sec:
            # extend previous segment to absorb this one
            prev = merged[-1]
            merged[-1] = LangSegment(prev.start, seg.end, prev.lang)
        else:
            merged.append(seg)

    # Clamp final segment end to video_duration
    if merged:
        last_seg = merged[-1]
        merged[-1] = LangSegment(last_seg.start, video_duration, last_seg.lang)

    return merged


def timeline_is_multilingual(timeline: List[LangSegment]) -> bool:
    """Return True if timeline contains more than one distinct language."""
    return len({seg.lang for seg in timeline}) > 1
