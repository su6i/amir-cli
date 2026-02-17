---
name: subtitle-generator
description: Technical protocol for high-fidelity Persian/Bilingual subtitle generation and rendering (2026 Edition).
version: 2.2.0
author: Amir
tags: [ASR, translation, typography, FFmpeg, RTL]
---

# Technical Protocol: Subtitle Generation & Multilingual Processing

This document specifies the deterministic pipeline for video transcription, linguistic transformation, and hardcoded subtitle rendering within the `amir-cli` ecosystem.

## 1. Visual Hierarchy & Typographical Standards

Subtitles must adhere to the following layout specifications to optimize cognitive processing:

- **Vertical Constraint**: Exactly one line per language in bilingual mode.
- **Horizontal Constraint**: Maximum of 42 characters per line (Target: 42).
- **Reading Velocity**: Target Characters Per Second (CPS) < 20.
- **Primary Language (Target/FA)**: Color: White (`#FFFFFF`); Weight: Bold; Asset: **B Nazanin (MANDATORY LAW)**.
- **Secondary Language (Source/EN)**: Color: Gray (`#808080`); Weight: Regular; Scale: 75% of primary.
- **Rationale**: Chromatic contrast directs focus to the translation while maintaining source context.

## 2. The "Nuclear Option" (Persian Shaping Logic)

To ensure perfect character joining and directionality:

- **Constraint**: **NEVER** utilize `arabic-reshaper` or `python-bidi` in the processing layer if the target renderer (FFmpeg) supports `libharfbuzz`.
- **Implementation**: Enforce native HarfBuzz shaping by injecting explicit font paths via the `fontsdir` parameter in the filter graph.
- **Implementation**: Enforce native HarfBuzz shaping by injecting explicit font paths via the `fontsdir` parameter in the filter graph.
- **Directionality Protocol**: 
    - **Anchor Lines**: Encapsulate Persian string with leading and trailing `\u200F` (RLM).
    - **Technical Terms**: Wrap English terms in parentheses with `\u200F` on both sides: `\u200F(TERM)\u200F`.
    - **Avoid RLE**: Do not use `\u202B` (RLE) as it causes unpredictable mirroring in modern ASS renderers.
- **Line Constraint**: Bilingual subtitles (EN+FA) **MUST** occupy exactly one line per language. Replace `\n` in the source layer with spaces.

## 3. Structural Segmentation & Semantic Logic

- **Line Balancing**: Long segments require a 50-50 length distribution.
- **Orphan Prevention**: Minimum of three words required per line suffix. Use `\u00A0` (NBSP) for the last word-pair.
- **Semantic Integrity**: Avoid breaks within Noun-Adjective pairs or Genitive constructs.

## 4. Automation Algorithms

### 4.1 Semantic Segment Integrity (Python)
Instead of fixed length, use punctuation-based backtracking to ensure natural reading flow.

```python
def resegment_to_sentences(segments, max_length=42):
    # BACKTRACKING LOGIC:
    # 1. Break at HARD points (. ! ?) with priority.
    # 2. Break at SOFT points (, ; :) with lookahead (max 12 chars).
    # 3. Use whitespace as a last resort.
    # This prevents splitting noun-adjective pairs and maintains Bidi context.
```

### 4.2 Non-Breaking Space Logic (Orphan Mitigation)
```python
def apply_nbsp(text):
    words = text.split()
    if len(words) >= 3:
        return " ".join(words[:-2]) + " " + words[-2] + "\u00A0" + words[-1]
    return text
```

## 5. Pro Feature Specifications (2026 Expansion)

### 5.1 AI Inference Tuning
- **Temperature Control**: Default `0.0` for maximum factual accuracy in technical content. Adjustable via `--temperature` (e.g., `0.8` for creative works).
- **Prompt Engineering**: Dynamic injection via `--initial-prompt` to seed context (e.g., "Medical jargon glossary").

### 5.2 Visual Override Heirarchy
- **Primary Color**: Defaults to White (`&H00FFFFFF`). Overridable via `--primary-color`.
- **Background**: Defaults to Transparent. Lecture Mode uses `&H80000000` (Semi-Opaque). Overridable via `--back-color`.

## 6. Hardware & Software Dependencies

- **Acoustic Inference**: Faster-Whisper (Large-v3 / MLX) utilizing Apple Silicon Neural Engine.
- **Linguistic Interface**: DeepSeek Chat API utilizing 20-line batching for throughput optimization.
- **Asset Rendering**: FFmpeg 8.0+ incorporating `libass` and `libharfbuzz`.

## 6. Implementation Workflow (Step-by-Step)

1.  **Signal Extraction**: Audio separation and transcription via neural model.
2.  **Linguistic Transformation**: Batch-processed mapping with structural verification.
3.  **Persistence serialization**: Output to UTF-8 with BOM (SRT/ASS).
4.  **Spatial Normalization**: Proportional scaling based on source vertical resolution ($h$):
    - `font_size = (h / 1080) * 25`
5.  **FFmpeg Synthesis**: Hardcoded embedding utilizing explicit `fontsdir` injection.

## 7. Diagnostic Procedures & Troubleshooting

### RTL Punctuation Disalignment
- **Symptom**: Punctuation metrics positioned at start-of-line (Right side instead of Left).
- **Remedy**: Verification of RLE/PDF wrapper injection in the `processor.py` logic.

### Centisecond Timing Overflow
- **Symptom**: Overlapping subtitle segments in ASS format.
- **Constraint**: ASS specifications require precisely two digits for centiseconds (`.cc`).
- **Correction**: `cs = int(ms / 10)` formatted with `%02d`.

### Ghosting / Duplicate Rendering
- **Prevention**: Utilization of the `-sn` flag in FFmpeg and verification that only one `.ass` layer is injected per render.

## 8. Quality Assurance Checklist
- [ ] CPS audit (Threshold: 20/s).
- [ ] Orphan audit (Threshold: 3 words).
- [ ] RTL Directionality verification (Punctuation check).
- [ ] Asset encoding verification (UTF-8 w/ BOM).
- [ ] B Nazanin Font Law compliance check.
