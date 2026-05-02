# Vertical Video Subtitle Issues - Comprehensive Analysis

## Executive Summary
The subtitle module has **mixed support for vertical video subtitles** with several potential issues:
1. **Text wrapping logic is reasonably intelligent** but has fixed width thresholds
2. **Margin/positioning adjustments exist** but may be insufficient for some vertical formats
3. **Truncation without safety checks** in bilingual mode could cause text loss
4. **Text synchronization uses safe index-based mapping** but resegmentation has edge cases
5. **Word limits are dynamic but based on static glyph width assumptions**

---

## 1. TEXT WRAPPING LOGIC

### A. Word-Count Logic in `processor.py`

**File**: [lib/python/subtitle/processor.py](lib/python/subtitle/processor.py)

#### Key Functions:

1. **Dynamic Target Words (Lines 388, 224-226)**
   ```
   Line 388: self.target_words_per_line = 7  # Default baseline
   Line 224: target_words_dyn = max(4, min(10, max_chars_dyn // 4))
   Line 226: processor.target_words_per_line = target_words_dyn
   ```
   - **Issue**: Uses fixed formula `max_chars_dyn // 4` which assumes 4 chars per word
   - **Problem**: Asian languages (CJK) have ~2 chars per word visually, but this formula doesn't account for that
   - **For vertical**: Range 4-10 words may be too many for narrow portrait videos

2. **Max Character Limit (Lines 225)**
   ```
   Line 225: processor.style_config.max_chars = max_chars_dyn
   ```
   - Calculated from video geometry but not validated for preview

3. **Semantic Split at Best Point (Lines 1491-1564)**
   ```
   Line 1491-1564: _find_best_split_point() and _split_at_best_point()
   ```
   - Uses **collocation database** to avoid breaking word pairs
   - **Issue**: Collocations are language-specific; non-English languages may not break optimally
   - Fallback: `text.rfind(' ', 0, max_chars)` then mid-word split
   - **Doesn't account for vertical orientation** when selecting best split point

### B. Rendering Layout in `rendering/ass_helpers.py`

**File**: [lib/python/subtitle/rendering/ass_helpers.py](lib/python/subtitle/rendering/ass_helpers.py)

#### Key Components:

1. **Portrait Detection (Line 16)**
   ```python
   is_portrait = bool(video_width and video_height and video_height > video_width)
   ```
   - Simple boolean: true if height > width
   - **No intermediate portrait modes** (e.g., 16:9-like narrow formats where height is moderately > width)

2. **Margin Calculations (Lines 17-19)**
   ```python
   Line 17: margin_h = 64 if is_portrait else 64                    # ALWAYS 64
   Line 18: fa_margin_v = 26 if is_portrait else 10
   Line 19: top_margin_v = 44 if is_portrait else 24
   ```
   - **Critical Issue**: `margin_h` is **identical** (64 pixels) for both portrait and horizontal
   - **Problem**: Portrait videos need SMALLER horizontal margins (not larger)
   - **Vertical spacing**: `fa_margin_v` only adjusts to 26 for portrait
   - **Top margin**: Increases from 24 to 44 for portrait (good for dual-line bilingual)

3. **Font Scaling for Bilingual (Lines 151-158)**
   ```python
   Line 153: top_scale = 0.90 if is_portrait else 0.82
   Line 154: top_fs = max(13, int(style.font_size * top_scale))
   Line 155: bot_fs = style.font_size
   ```
   - **Portrait**: Top text is 90% of bottom (less scaling)
   - **Horizontal**: Top text is 82% of bottom (more scaling)
   - **Issue**: Minimum 13px font might be too small for portrait; no maximum safety

### C. Text Normalization & Truncation (Lines 91-97)**

**File**: [lib/python/subtitle/rendering/ass_helpers.py](lib/python/subtitle/rendering/ass_helpers.py#L91-L97)

```python
Line 91-97: _normalize_primary_text()
    def _normalize_primary_text(text: str, secondary_srt: Optional[str], is_portrait: bool) -> str:
        out = text.replace("\n", " ").replace("\\N", " ").replace("\\n", " ").strip()
        out = " ".join(out.split())  # Collapse whitespace
        if secondary_srt:
            max_top_chars = 42 if is_portrait else 70
            if len(out) > max_top_chars:
                out = out[:max_top_chars].rsplit(" ", 1)[0] + "…"
        return out
```

**Issues**:
1. **Truncation without warning** — text is silently cut at 42 chars (portrait) or 70 chars (horizontal)
2. **Naive character-based truncation** — using `len(out)` ignores zero-width Unicode chars
3. **Not visual-length aware** — Persian and Arabic combine-marks count as characters but may not render visibly
4. **The `rsplit(" ", 1)` hack** — tries to remove last word but fails if last piece is a single letter
5. **NO escape to full text** — if truncation happens, English speaker text is lost permanently

---

## 2. MARGINS & POSITIONING FOR VERTICAL VIDEOS

### A. Margin Settings

**File**: [lib/python/subtitle/rendering/ass_helpers.py](lib/python/subtitle/rendering/ass_helpers.py#L14-L34)

```python
Lines 14-34:
def compute_ass_layout(...) -> Dict[str, object]:
    is_portrait = bool(video_width and video_height and video_height > video_width)
    margin_h = 64 if is_portrait else 64                           # ❌ NO DIFFERENCE
    fa_margin_v = 26 if is_portrait else 10
    top_margin_v = 44 if is_portrait else 24

    # Build ASS style string using margin_h, fa_margin_v
    # Format: alignment,marginL,marginR,marginV,encoding
```

**ASS Style Format** (Line 28):
```
f"{style.alignment},{margin_h},{margin_h},{fa_margin_v},1"
```

**Problems**:
- **MarginL and MarginR both set to 64** — This is correct for 16:9 but wrong for 9:16
- **For 9:16 portrait videos**, margins should be SMALLER horizontally (e.g., 32-48px) not identical
- **MarginV (vertical margin)** is set more conservatively (26 for portrait), which is good
- **Alignment is never overridden** based on orientation — Always uses default from style config

### B. Font Size Scaling

**File**: [lib/python/subtitle/processor.py](lib/python/subtitle/processor.py#L218-231)

```python
Lines 218-231:
    rendered_font_px = processor.style_config.font_size * (vh / 480.0)
    text_area_px = vw * 0.80
    is_rtl = target_langs and any(l in rtl_langs for l in target_langs)
    avg_glyph_w = rendered_font_px * (0.64 if is_rtl else 0.55)
    max_chars_dyn = max(10, int(text_area_px / avg_glyph_w))
```

**Issues**:
1. **`text_area_px = vw * 0.80`** — Uses video WIDTH for text area calculation
   - For portrait (9:16), vw is SMALL, so text_area_px is tiny
   - This artificially constrains max_chars for vertical videos
   
2. **`avg_glyph_w` is a hardcoded multiplier**:
   - RTL: 0.64x font_size, LTR: 0.55x font_size
   - **No consideration for CJK or other scripts**
   - These are empirical guesses, not scientifically validated
   
3. **No preview/fallback** if max_chars becomes too small (floor is 10)

### C. Wrap Style in ASS Header

**File**: [lib/python/subtitle/rendering/ass_helpers.py](lib/python/subtitle/rendering/ass_helpers.py#L62-75)

```python
Lines 62-75:
def build_ass_header(styles_block: str, secondary_srt: Optional[str]) -> str:
    wrap_style = "2" if secondary_srt else "0"
    return f"""[Script Info]
    ScriptType: v4.00+
    WrapStyle: {wrap_style}
    ...
```

**ASS WrapStyle settings**:
- `WrapStyle: 0` — No smart word wrap (mono subtitle)
- `WrapStyle: 2` — Smart bilingual wrap (encourages 2-line subtitles)

**Issue**: No consideration for video resolution or aspect ratio

---

## 3. TRUNCATION LOGIC FOR BILINGUAL SUBTITLES

### A. Primary Text Truncation

**File**: [lib/python/subtitle/rendering/ass_helpers.py](lib/python/subtitle/rendering/ass_helpers.py#L91-97)

```python
Lines 91-97:
    if secondary_srt:
        max_top_chars = 42 if is_portrait else 70
        if len(out) > max_top_chars:
            out = out[:max_top_chars].rsplit(" ", 1)[0] + "…"
```

**Critical Problems**:
1. **Silent truncation** — No warning to user
2. **Character-count based** — Doesn't use visual length (`vis_len()`)
3. **Naive word boundary attempt** — `rsplit(" ", 1)` fails for:
   - Single-letter last words (e.g., "word a" → "word…" instead of "word a")
   - Multi-space scenarios
   - Lines ending with punctuation + space
4. **No fallback for untranslatable text** — If truncation creates nonsense, no recovery

### B. Resegmented Translation Trimming

**File**: [lib/python/subtitle/translation/resegment.py](lib/python/subtitle/translation/resegment.py#L56-68)

```python
Lines 56-68:
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
```

**Issues**:
1. **Better than assertion version** — Uses `vis_len()` (excludes zero-width chars)
2. **Fallback to hard truncation** — `text[:slot_max_chars]` if no words fit
   - This is a last-resort safety; prevents complete loss
3. **No smart breaking** — Doesn't try to preserve complete thoughts
4. **Silent truncation** — No warning emitted

### C. Bilingual Event Assembly

**File**: [lib/python/subtitle/rendering/ass_helpers.py](lib/python/subtitle/rendering/ass_helpers.py#L140-172)

```python
Lines 140-172:
def build_ass_events(...) -> List[str]:
    for entry in entries:
        text = _normalize_primary_text(entry["text"], secondary_srt, is_portrait)
        ...
        if secondary_map:
            sec_text = secondary_map.get(entry["index"])
            if sec_text:
                ...
                bi_fa_text = f"{...}{sec_text_formatted}"
        ...
        if bi_fa_text:
            events.append(f"Dialogue: 0,{ass_start},{ass_end},FaDefault,,0,0,0,,{bi_fa_text}")
            events.append(f"Dialogue: 0,{ass_start},{ass_end},TopDefault,,0,0,0,,{final_text}")
```

**Issue**: Two dialogue events are emitted for the PRIMARY text:
1. **Secondary text event** (lines 168)
2. **Primary (English) text event** (line 169)
3. **Primary text has ALREADY been truncated** (in `_normalize_primary_text`)

---

## 4. TEXT SYNCHRONIZATION (Original/Translated)

### A. Index-Based Secondary Mapping

**File**: [lib/python/subtitle/rendering/ass_helpers.py](lib/python/subtitle/rendering/ass_helpers.py#L77-82)

```python
Lines 77-82:
def build_secondary_map(sec_entries: List[Dict]) -> Dict[str, str]:
    """Build index-based secondary subtitle map for deterministic pairing."""
    secondary_map: Dict[str, str] = {}
    for entry in sec_entries:
        secondary_map[entry["index"]] = entry["text"]
    return secondary_map
```

**Approach**: Dictionary keyed by entry index
- Safe for exact 1:1 matching
- **Doesn't handle partial matches** if entry indices drift

### B. Translation Resegmentation

**File**: [lib/python/subtitle/translation/resegment.py](lib/python/subtitle/translation/resegment.py#L5-150)

```python
Lines 5-150:
def resegment_translation(...):
    result = [""] * len(entries)
    
    for group_indices, translated_text in zip(paragraph_groups, translated_paragraphs):
        n_slots = len(group_indices)
        if n_slots == 1:
            result[group_indices[0]] = trim_to_fit(translated_text.strip())
        else:
            # Smart distribution across multiple slots
```

**How it works**:
1. **Paragraph grouping** — Groups consecutive subtitle entries until sentence end
2. **Translation as whole** — Translates the entire paragraph at once
3. **Re-segmentation** — Splits translated text back onto ORIGINAL timecodes
4. **Index awareness** — Maps translated content to original entry positions

**Issues**:
1. **Assumes sorted indices** — If entry["index"] is not monotonically increasing, mapping could fail
2. **Edge case: Empty translation** — Falls back to original text (lines 82-85)
3. **Edge case: Translation shorter than slots** — Some slots get empty text
4. **Bad enders list** (lines 30-45) — Only works for Persian/English; doesn't scale

### C. Synchronization Maintenance

**File**: [lib/python/subtitle/translation/resegment.py](lib/python/subtitle/translation/resegment.py#L79-150)

```python
The function maintains sync by:
1. Iterating through (paragraph_groups, translated_paragraphs) in lockstep
2. Using group_indices to directly map back to result array positions
3. Never skipping or reordering entries
```

**Strength**: Original timing information is **completely preserved**
- No audio-visual sync issues from translation
- Each entry retains its start/end timestamp

**Weakness**: If paragraph grouping is wrong, cascading errors happen

---

## 5. MAXIMUM WORD/CHARACTER LIMITS

### A. Style Configuration

**File**: [lib/python/subtitle/models/types.py](lib/python/subtitle/models/types.py#L25-39)

```python
Lines 25-39:
@dataclass
class StyleConfig:
    max_chars: int
    max_lines: int
    ...

Lines 61-87:
STYLE_PRESETS = {
    SubtitleStyle.LECTURE: StyleConfig(
        max_chars=42,
        max_lines=1,
        ...
    ),
    SubtitleStyle.VLOG: StyleConfig(
        max_chars=35,
        max_lines=2,
        ...
    ),
}
```

**Default Limits**:
- LECTURE: 42 chars, 1 line
- VLOG: 35 chars, 2 lines

**Issue**: No portrait-specific presets

### B. Dynamic Calculation

**File**: [lib/python/subtitle/processor.py](lib/python/subtitle/processor.py#L218-231)

```python
Lines 218-231: detect_subtitle_geometry()
    rendered_font_px = processor.style_config.font_size * (vh / 480.0)
    text_area_px = vw * 0.80
    max_chars_dyn = max(10, int(text_area_px / avg_glyph_w))
    target_words_dyn = max(4, min(10, max_chars_dyn // 4))
```

**Calculation**:
1. Scale base font size based on video height
2. Calculate available text width as 80% of video width
3. Estimate average glyph width (0.55-0.64x font_size)
4. Derive max_chars from: `text_area_px / avg_glyph_w`
5. Target words: `max_chars // 4` (capped 4-10)

**Issues**:
- **For portrait video (9:16)**:
  - vw is small → text_area_px is TINY
  - avg_glyph_w unchanged → max_chars becomes very small
  - Example: 360px width → text_area_px = 288px → max_chars ≈ 15
- **Hardcoded glyph multiplier** — 0.55/0.64 are empirical guesses
- **No visual validation** — No check if 10px font is even readable

### C. Word Limits in Translation Sanitization

**File**: [lib/python/subtitle/sanitization/helpers.py](lib/python/subtitle/sanitization/helpers.py#L5-13)

```python
Lines 5-13:
def apply_semantic_splitting(
    entries: List[Dict],
    max_chars: int,
    split_at_best_point_fn: Callable[[Dict, int], List[Dict]],
) -> List[Dict]:
    """Split each entry to keep lines within width constraints."""
```

**Point**: Uses `max_chars` as the limit for semantic splitting
- Feeds the configured limit directly to split function
- No adaptive adjustment for orientation

### D. Character Limits in Batch Translation

**File**: [lib/python/subtitle/cache/helpers.py](lib/python/subtitle/cache/helpers.py#L11-22)

```python
Lines 11-22:
def create_balanced_batches(..., max_chars: int = 5000):
    """Group texts into batches without exceeding max_chars."""
    current_batch = []
    current_chars = 0
    for text in texts:
        text_len = len(text)
        if current_batch and current_chars + text_len > max_chars:
            # Start new batch
```

**Purpose**: Ensures translation API batches don't exceed token limits
- Default: 5000 characters per batch
- **Not related to subtitle display width**

---

## 6. ADDITIONAL ISSUES FOUND

### A. Wrap Style Handling

**File**: [lib/python/subtitle/rendering/ass_helpers.py](lib/python/subtitle/rendering/ass_helpers.py#L62-75)

```python
Line 64: wrap_style = "2" if secondary_srt else "0"
```

- WrapStyle=2 uses smart wrapping but might be overly aggressive for narrow content

### B. No Resolution-Based Text Area Adjustment

**File**: [lib/python/subtitle/workflow/base.py](lib/python/subtitle/workflow/base.py#L222)

```python
text_area_px = vw * 0.80
```

- Always uses 80% of video width
- No adjustment for actual resolution (360p vs 4K vertical)

### C. Zero-Width Character Handling Inconsistency

- **`_normalize_primary_text()`** (line 96): Uses raw `len(out)` → counts zero-width chars
- **`trim_to_fit()`** (line 58 of resegment.py): Uses `vis_len()` → IGNORES zero-width chars

**Issue**: Different truncation behavior creates inconsistency

### D. RTL Language-Specific Limits

**File**: [lib/python/subtitle/workflow/base.py](lib/python/subtitle/workflow/base.py#L221-222)

```python
is_rtl = target_langs and any(l in rtl_langs for l in target_langs)
avg_glyph_w = rendered_font_px * (0.64 if is_rtl else 0.55)
```

- Persian (0.64) is wider than English (0.55)
- CJK not considered
- Characters combine differently (Persian diacritics, Arabic ligatures)

---

## 7. CRITICAL VERTICAL VIDEO ISSUES SUMMARY

| Issue | File | Line(s) | Severity | Impact |
|-------|------|---------|----------|--------|
| Horizontal margins identical for portrait/horizontal | ass_helpers.py | 17 | **CRITICAL** | Width constraint wrong for vertical |
| Primary text truncation not visual-aware | ass_helpers.py | 91-97 | **HIGH** | Text loss in Persian/Arabic bilingual |
| No portrait-specific style presets | types.py | 61-87 | **HIGH** | Manual config required |
| Text area calculation ignores portrait aspect | base.py | 222 | **HIGH** | Graphics too constrained vertically |
| Glyph width hardcoded, not script-aware | base.py | 222 | **MEDIUM** | CJK subtitles misaligned |
| No minimum font size enforcement | ass_helpers.py | 154 | **MEDIUM** | Can become unreadable |
| Truncation without logging | ass_helpers.py, resegment.py | 97, 68 | **MEDIUM** | Silent data loss |
| Orphan segment merging hard-limited | segmentation/helpers.py | 169 | **LOW** | May not merge in vertical context |

---

## 8. RECOMMENDATIONS

1. **Fix horizontal margins for portrait**:
   - Reduce to 32-48px for vw < 480px
   
2. **Add visual-length aware truncation**:
   - Use `vis_len()` everywhere, not `len()`
   - Add truncation warnings to logs

3. **Create portrait-specific StyleConfig presets**:
   - Add `SubtitleStyle.VERTICAL_VLOG`, etc.

4. **Adjust text_area_px for orientation**:
   - Use `vh * 0.80` for portrait instead of `vw * 0.80`

5. **Add script-aware glyph metrics**:
   - Table-driven glyph width for known scripts

6. **Add validation** before rendering:
   - Warn if max_chars < 20 or font_size < 14px
