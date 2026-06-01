# Subtitle Translation & Post Rules (Current Behavior)

Date: 2026-04-17
Scope: Current active rules implemented in subtitle translation, segmentation, timing, and Telegram post generation.

## 1) Core Translation Rules (SRT line translation)

Source of truth:
- lib/python/subtitle/processor.py -> get_translation_prompt()
- lib/python/subtitle/workflow/translation_stage.py

Current rules:
- Output format must be JSON only: line-number keys mapped to translated text values.
- 1:1 line mapping is mandatory: no dropping lines, no merging lines, no shifting content between lines.
- Subtitle fragments are treated as raw segments: translator must not complete the sentence using context.
- No extra explanations/comments are allowed.
- For Persian target (fa): informal Tehrani tone is enforced in the prompt.
- For Persian target (fa): avoid English echo in output (post-processing also strips English artifacts).
- Semantic line-lock mode is ON by default (env: AMIR_SUBTITLE_SEMANTIC_LINE_LOCK=true): source/target alignment is preserved per line.

## 2) Video Geometry Rules (Vertical vs Horizontal)

Source of truth:
- lib/python/subtitle/workflow/base.py -> detect_subtitle_geometry()

### 2.1 Vertical / Portrait videos (vh > vw)
- Text area is width-based (narrow lane): text_area = width * 0.78.
- max_chars is clamped to narrow-safe range: 15..22.
- target_words_per_line is fixed at 4 (strict short-form behavior).

### 2.2 Horizontal / Landscape videos (vw >= vh)
- Text area uses width * 0.80.
- target_words_per_line is dynamic and longer than vertical:
  - target_words_per_line = max(7, min(12, max_chars // 3))
- Goal: keep horizontal cues longer and avoid applying short-form vertical behavior.

## 3) Segmentation Rules (word -> subtitle entry)

Source of truth:
- lib/python/subtitle/processor.py -> segment_words_smart()

Current rules:
- Sentence enders (. ? !) force flush.
- Hard character ceiling and time ceiling are enforced.
- Clause-aware guards avoid bad breaks before dependent clause starters.
- Orphan segments are merged in post-pass.

Low-RAM behavior (important split):
- Portrait only: low-RAM tuning makes segmentation snappier.
- Horizontal: low-RAM tuning DOES NOT apply portrait short-cue clamps.

## 4) Timing Normalization Rules

Source of truth:
- lib/python/subtitle/sanitization/helpers.py -> normalize_and_fix_timing()

Current rules:
- Enforce min_duration for each subtitle entry.
- Tiny positive gap padding is applied conservatively.
- Overlap handling:
  - Small overlap (<= 0.15s): trim previous cue end first.
  - Current cue start is treated as sync anchor and is preserved whenever possible.
  - For previous cue, min-duration is treated as soft during overlap cleanup (kept visually non-zero).
  - Large overlap (> 0.15s): still trim previous cue first; shift current start only in pathological ordering as a final fallback.
- Goal: no persistent overlap across consecutive entries.

## 5) Telegram Post Rules (social output)

Source of truth:
- lib/python/subtitle/social/prompts.py
- lib/python/subtitle/social/post_helpers.py
- lib/python/subtitle/social/generator.py
- lib/python/subtitle/social/discovery.py

### 5.1 Mandatory intro block (top of Telegram post)
Telegram post must begin with these 4 lines in order:
1. 🎙️ Host & Channel
2. 📊 Host followers/background
3. 👤 Main guest
4. 🏅 Guest background/credentials

Metadata used for these lines:
- uploader/channel info
- channel follower count (if available)
- description-derived guest hint

If missing metadata:
- Prompt requires explicit unknown/نامشخص instead of hallucinated facts.

### 5.2 Existing template remains after intro block
- After the 4 intro lines, existing Telegram template continues (short or long variant).
- Required sections are validated; missing sections trigger retry logic.

### 5.3 Telegram file output order
- Telegram saved file now starts directly with post body (no prepended metadata header),
  so the required intro lines are truly the first lines.

## 6) What To Edit If You Want Different Behavior

- Vertical line density:
  - lib/python/subtitle/workflow/base.py
  - portrait target_words_per_line and portrait max_chars clamp

- Horizontal line density:
  - lib/python/subtitle/workflow/base.py
  - landscape target_words_per_line formula

- Segmentation strictness (sentence length/breaking):
  - lib/python/subtitle/processor.py -> segment_words_smart() tunables

- Timing aggressiveness / lag behavior:
  - lib/python/subtitle/sanitization/helpers.py -> normalize_and_fix_timing()

- Telegram intro content and style:
  - lib/python/subtitle/social/prompts.py
  - lib/python/subtitle/social/post_helpers.py (required-section validator)
