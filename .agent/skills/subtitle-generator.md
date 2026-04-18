---
name: subtitle-generator
description: Technical protocol for high-fidelity Persian/Bilingual subtitle generation and rendering (2026 Edition).
version: 3.0.0
author: Amir
tags: [ASR, translation, typography, FFmpeg, RTL, SmartMerge, BiDi, Unicode]
---

# Technical Protocol: Subtitle Generation & Multilingual Processing

This document specifies the deterministic pipeline for video transcription, linguistic transformation, and hardcoded subtitle rendering within the `amir-cli` ecosystem.

## 1. Visual Hierarchy & Typographical Standards

Subtitles must adhere to the following layout specifications to optimize cognitive processing:

- **Vertical Constraint**: Exactly one line per language in bilingual mode.
- **Horizontal Constraint**: Maximum of 42 characters per line (Target: 42).
- **Reading Velocity**: Target Characters Per Second (CPS) < 20.
- **Primary Language (Target/FA)**: Color: White (`#FFFFFF`); Weight: Bold; Asset: **Vazirmatn**.
- **Secondary Language (Source/EN)**: Color: Gray (`#808080`); Weight: Regular; Scale: 75% of primary.
- **Rationale**: Chromatic contrast directs focus to the translation while maintaining source context.

## 2. Advanced RTL & BiDi Stability — Unicode Isolates (v3.0, Current)

### 2.1 Background & Why Old Approaches Failed

**The Problem**: libass (used by FFmpeg for subtitle burning) treats each ASS `Dialogue:` event as a standalone BiDi paragraph. The paragraph base direction is determined by Unicode UBA P2/P3 rules — first strong directional character wins. In bilingual mode the English line appears above; its LTR strong characters do NOT affect the Persian event's own paragraph direction (each event = separate paragraph). However, if the Persian line itself starts or contains LTR-strong characters, the paragraph resolves as LTR and punctuation/brackets shift to the wrong visual edge.

**Why RLM anchoring (`\u200F`) was insufficient**: RLM is a weak right-to-left character. It can influence neutral characters adjacent to it, but it does NOT set the paragraph base direction. It also does not isolate sub-runs from surrounding context.

**Why RLE/PDF (`\u202B/\u202C`) failed**: RLE is a "directional embedding", which acts like a strong directional character affecting surrounding text — exactly what TR9 §6.3 warns against for programmatically-generated text.

### 2.2 Correct Solution: Unicode Directional Isolates (TR9 §6.3, Unicode 6.3+)

Unicode TR9 §6.3 explicitly states: **"use directional isolates instead of embeddings in programmatically generated text"**.

| Character | Code | Purpose | HTML equivalent |
|-----------|------|---------|----------------|
| RLI | `\u2067` | Right-to-Left Isolate — forces RTL paragraph, isolated from context | `dir="rtl"` + `unicode-bidi: isolate` |
| LRI | `\u2066` | Left-to-Right Isolate — forces LTR sub-run, isolated from context | `<bdi>` or `unicode-bidi: plaintext` |
| PDI | `\u2069` | Pop Directional Isolate — closes any open RLI/LRI | close tag |

Isolates (unlike embeddings) are **neutral** with respect to the surrounding text — they don't affect bidi resolution outside their scope.

### 2.3 Implementation in `fix_persian_text()` (processor.py)

```python
@staticmethod
def fix_persian_text(text: str) -> str:
    if not text:
        return text

    # Step 0: Remove extra spaces before punctuation (LLM artifact)
    text = re.sub(r'\s+([\.\ !؟،؛])', r'\1', text)

    # Step 1: Informal verb normalization + ZWNJ insertion
    # ZWNJ (\u200C) is safe — Vazirmatn renders it as zero-width invisible glyph
    zwnj_patterns = [
        (r'(\w)(ها)(\s|$)', '\\1\u200c\\2\\3'),
        (r'می(\s)', 'می\u200c\\1'),
    ]
    for pat, repl in zwnj_patterns:
        text = re.sub(pat, repl, text)

    # Step 2: Strip ALL directional control chars including any previously-applied isolates
    # so this function is always idempotent (safe to call multiple times on same text).
    # Kept: ZWNJ (\u200C) — Vazirmatn renders it invisible; needed for word-boundary shaping.
    # Stripped: old embeddings (RLM/LRM/ZWJ/RLE/LRE/PDF/RLO/LRO)
    #         + previously-applied isolates (RLI \u2067, LRI \u2066, PDI \u2069)
    for _cp in ('\u200f', '\u200e', '\u200d',
                '\u202b', '\u202a', '\u202c', '\u202e', '\u202d',
                '\u2067', '\u2066', '\u2069'):  # ← RLI/LRI/PDI stripped for idempotency
        text = text.replace(_cp, '')
    text = text.strip()

    # Step 3: Migration undo — reverse old punct-at-front transform
    # Old versions put punct at logical-START for LTR context. With RLI, paragraph is RTL
    # so punct must be at logical-END. This step runs always; safe on clean text too.
    text = text.strip()
    text = re.sub(r'^([.!:،؛؟]+)(.+)$', r'\2\1', text)

    # Step 4: Wrap English parenthetical terms as LTR isolates (always applied — no guard needed)
    _LRI = '\u2066'
    _PDI = '\u2069'
    _RLI = '\u2067'
    text = re.sub(r'(\([A-Za-z][^)]*\))', _LRI + r'\1' + _PDI, text)

    # Step 5: Wrap entire string as RTL isolate paragraph (always applied — idempotent via step 2)
    text = _RLI + text + _PDI

    return text
```

### 2.4 Critical Rules for Future Changes

> ⚠️ **DO remove the `if not text.startswith(_RLI):` guard.** The function strips RLI/LRI/PDI in step 2, making it idempotent. A guard is NOT needed and will prevent migration from working on cached SRT files that already have `\u2067،text\u2069` format.

> ⚠️ **DO NOT remove the migration regex** `re.sub(r'^([.!:،؛؟]+)(.+)$', r'\2\1', text)` in step 3. It undoes old cached SRT files that had punct at logical-START. It is a no-op on clean text that already has punct at end.

> ⚠️ **DO NOT add a "move trailing punctuation to front" step.** This was the old hack for LTR-context rendering. With RLI wrapping (step 5), the paragraph is RTL. In RTL: logical-END = visual-LEFT = correct position for Persian ending punctuation (period, comma, question mark). Moving punct to logical-FRONT in RTL context puts it at visual-RIGHT (= sentence START) — WRONG.

> ⚠️ **DO NOT use RLM (`\u200F`) anchoring** (the old v2 approach). RLM is a weak hint, not a strong directional control. It fails in mixed-context paragraphs.

> ⚠️ **DO NOT use RLE/PDF (`\u202B/\u202C`)**. These are embeddings, not isolates. TR9 §6.3 explicitly recommends against them for programmatically-generated text.

> ✅ **DO keep ZWNJ (`\u200C`)** in the SRT data. Vazirmatn handles it as zero-width invisible — it's needed for correct word-boundary shaping in some compound words.

> ✅ **DO strip ZWNJ before writing to ASS events** if using B Nazanin font (it renders ZWNJ as a visible box □). Vazirmatn is the recommended font so this is not needed.

### 2.5 Punctuation Rendering Reference

| Position in logical string | Paragraph direction | Visual position | Correct for Persian? |
|---------------------------|--------------------|-----------------|-----------------------|
| Logical-END | RTL (with RLI) | Visual-LEFT (end of line) | ✅ Yes |
| Logical-START | RTL (with RLI) | Visual-RIGHT (start of line) | ❌ No |
| Logical-END | LTR (default, no RLI) | Visual-RIGHT | ❌ No |
| Logical-START | LTR (old hack) | Visual-LEFT | ✅ Yes (old workaround) |

## 3. High-Fidelity Linguistic Processing (Smart Merge)

A common failure in ASR (Whisper/API) is "Token Fragmentation" or "Split Numbers".

- **Smart Merge Algorithm**: The system must Scan transcripts for digits followed by comma-prefixed digits (e.g., "1" + ",500").
- **Protocol**: Automatically merge these entries into a single visual block before translation. This ensures "1,500" stays together and prevents translation engines from confusing single digits with count markers.

## 4. Hardware Encoding & Size Parity (The "Quality Over Bitrate" Law)

To solve the "Size Bloat" problem where hardware encoding produces unpredictable results:

- **The Standard**: For professional-grade results where quality is the "Red Line", **ALWAYS Use libx264 (Software)** with CRF control.
- **Platform-Specific Protocols**:
    - **Pro/Stability (Standard)**: Use `libx264` with `-crf 23` (Archival: 18-20, Distribution: 23-25).
    - **Fast/Draft**: Use `h264_videotoolbox` (Mac) or `h264_nvenc` (Nvidia) with fixed bitrate matching input.
- **Audio Preservation**: Default to `-c:a copy` to preserve 100% of source audio fidelity.

## 5. Automation Algorithms

### 5.1 Semantic Segment Integrity (Python)
Instead of fixed length, use punctuation-based backtracking to ensure natural reading flow. Break at hard points (. ! ?) first, then soft points (, ; :).

### 5.2 Environment Unification
The project uses a **Unified Virtual Environment** located at the root (`.venv`). Submodules (like `subtitle`) MUST NOT have their own `.venv` or `pyproject.toml` to prevent `uv` environment mismatch warnings.

## 6. CLI Interface & Argument Reference

### 6.1 Key Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-s / --source` | `en` | Audio language of the video (used for Whisper transcription) |
| `--sub` (alias `-t`) | `['fa']` | Subtitle languages to display, **in top-to-bottom order** |
| `--limit T1 T2` | — | Time range: `--limit 120 end`, `--limit begin 00:50:38`, `--limit 1800 1:22:00` |
| `--no-render` | — | Generate SRT files only, skip video burn |
| `-f / --force` | — | Re-run Whisper even if SRT cache exists |

### 6.2 `--sub` Behavior

`--sub` defines **what shows up in the video**, in order. The system auto-determines which need translation.

```bash
# Default: en source, fa subtitle only
amir video subtitle video.mp4

# Bilingual: EN on top (source), FA below (translated)
amir video subtitle video.mp4 --sub en fa

# FA only (no English row)
amir video subtitle video.mp4 --sub fa

# French source video, bilingual FR+FA
amir video subtitle video.mp4 -s fr --sub fr fa
```

**Rules:**
- If a `--sub` lang == `-s` source → use transcription as-is (no translation)
- If a `--sub` lang != source → translate from source to that language
- Max 2 languages currently supported (3-language: future)

### 6.3 Rendering Layout Logic (processor.py)

```python
# In run_workflow() — render section:
primary   = target_langs[0]           # top row (first --sub lang)
secondary = target_langs[1] if len(target_langs) >= 2 else None  # bottom row

# In create_ass_with_font():
# Single FA: use FaDefault style for Dialogue events
event_style = "FaDefault" if (lang == 'fa' and not secondary_map) else "Default"
# Bilingual: top row uses Default, bottom row switches inline via {\rFaDefault}
final_text = f"{{\fs{top_fs}}}{{\c&H808080}}{top_text}\N{{\rFaDefault}}{{\fs{bot_fs}}}{{\b1}}{bottom_text}"
```

### 6.4 Font Size — NEVER Dynamic

Font size MUST be constant throughout the video. Dynamic sizing causes jarring jumps.

```python
# CORRECT — fixed sizes:
top_fs = max(16, int(style.font_size * 0.75))  # top row always 75%
bot_fs = style.font_size                         # bottom row always 100%

# WRONG — removed:
# if fa_char_count > 50: fa_fs = style.font_size * 0.72  ← causes jumps
# elif fa_char_count > 35: fa_fs = style.font_size * 0.85
```

## 7. Diagnostic Procedures

### 7.1 disalignment in Mixed text
- **Check**: Ensure `RE_PUNCT_CLEANUP` regex is running to remove spaces before marks.
- **Check**: Verify RLM anchors (`\u200F`) are present at BOTH ends of the string.

### 7.2Centisecond Timing
Ass specs require two digits for centiseconds. Implementation: `cs = int(ms / 10)` formatted with `%02d`.

## 9. `video download --translate` Integration

The `amir video download` command integrates the subtitle pipeline as a downstream step.

### 9.1 Trigger Conditions
The subtitle module is invoked when any of the following flags are set:
- `--yt-subs --translate` — translate downloaded YT subtitles via LLM (no Whisper)
- `--subtitle / -s` — transcribe with Whisper AI then burn
- `--yt-subs --render` — burn existing YT subtitle without translation

### 9.2 Whisper-Skip Protocol
To bypass Whisper transcription when an existing SRT is available, `video download` copies the source SRT to `<base>_<lang>.srt`:
```bash
# Creates: "Title_en.srt"
cp "Title.en.srt" "Title_en.srt"
```
The subtitle processor detects `*_en.srt` alongside the video and skips Whisper, proceeding directly to translation.

### 9.3 DO_RENDER Default Behavior
| Flag | DO_RENDER |
|------|-----------|
| `--translate` | `true` (burn by default) |
| `--translate --no-render` | `false` (SRT-only output) |
| `--subtitle / -s` | `true` |
| `--subtitle --no-render` | `false` |
| `--yt-subs` (alone) | `false` |

### 9.4 Same-Language Guard
Before calling the subtitle module, `video download` validates that `LANG_SRC != LANG`. If they match, it exits with a descriptive error. This prevents the subtitle module from receiving a no-op translation request.

---

## 10. ASS Rendering Gotchas

### 9.1 ZWNJ (U+200C / نیم‌فاصله) renders as □ in B Nazanin
**Problem:** The B Nazanin font does not include a glyph for U+200C (ZWNJ / نیم‌فاصله). libass renders it as a visible white rectangle □ inside the subtitle text.

**Fix:** Strip all U+200C characters from `final_text` **before** writing to the ASS events list. Apply this inside the event-building loop, after all text processing:
```python
# Strip ZWNJ — B Nazanin renders it as a visible box
final_text = final_text.replace('\u200c', '')
events.append(f"Dialogue: 0,{ass_start},{ass_end},Default,,0,0,0,,{final_text}")
```
**Why it is safe:** ffmpeg is compiled with `--enable-libharfbuzz`, which handles Arabic/Persian ligature shaping natively without needing ZWNJ hints. The ZWNJ in SRT source files is kept intact; only the ASS copy is stripped.

---

## 8. Quality Assurance Checklist
- [x] BiDi check: Punctuation is at the visual-LEFT (= end of line in RTL = correct Persian sentence end).
- [x] BiDi check: English terms in parentheses e.g. `(CapEx)` appear in correct position within the Persian sentence (not jumping to start/end of line).
- [x] `fix_persian_text()` does NOT contain a "move trailing punct to front" step.
- [x] `fix_persian_text()` wraps the full string in RLI+PDI and English parens in LRI+PDI.
- [x] Size check: Output file size ≈ Input file size.
- [x] Font check: Parentheses content is visibly smaller (75%).
- [x] Env check: No `.venv` or `uv.lock` in subdirectories.
- [x] Performance check: Using `turbo` model by default.
- [x] ZWNJ check: No U+200C characters in ASS events (B Nazanin box-glyph bug).
