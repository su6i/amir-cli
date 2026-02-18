---
name: subtitle-generator
description: Technical protocol for high-fidelity Persian/Bilingual subtitle generation and rendering (2026 Edition).
version: 2.3.0
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

## 2. Advanced RTL & BiDi Stability (The "RLM Anchor" Solution)

To solve the "Right-to-Left Disalignment" where punctuation (periods, question marks) flips to the wrong side in mixed-language strings:

- **The Problem**: Common libraries like `arabic-reshaper` or simple RLE/PDF wrappers often fail in ASS renderers when Latin terms are present at the beginning or end of a Persian sentence.
- **The Solution (RLM Anchoring)**: Every Persian string **MUST** be encapsulated with a leading and trailing `\u200F` (RLM - Right-to-Left Mark). This forces the renderer to treat the entire segment as RTL, regardless of its contents.
- **Sub-segment Isolation**: Technical terms (English) inside Persian sentences MUST be wrapped in parentheses and isolated with RLM anchors: `\u200F(TERM)\u200F`.
- **Implementation**: Enforce native HarfBuzz shaping by injecting explicit font paths via the `fontsdir` parameter in the filter graph.

## 3. Typographical Refinement: Proportional Scaling

- **Font Scaling (Parentheses Fix)**: To maintain professional visual density, English content inside parentheses is scaled to **75%** of the primary font size using ASS tags (`{\fscx75\fscy75}(English Content){\fscx100\fscy100}`).
- **Resolution Scaling**: Base font size is dynamically calculated as `font_size = (vertical_resolution / 1080) * 25`.
- **NBSP Logic**: Use `\u00A0` (Non-Breaking Space) for the final word-pair to prevent "orphaned" single words on new lines.

## 4. Hardware Encoding & Size Parity (The "Quality Over Bitrate" Law)

To solve the "Size Bloat" problem where hardware encoding produces files 3x larger than the source:

- **The Problem**: Fixed bitrates (`-b:v 5M`) are dangerous. They ignore the source's actual complexity. High-motion videos might look bad, while static videos become unnecessarily massive.
- **The Technique**: ALWAYS prioritize **Constant Quality** parameters over explicit bitrates. This allows the encoder to spend bits only where needed, matching the source file's density.
- **Platform-Specific "Magic Numbers"**:
    - **Mac (Apple Silicon)**: Use `h264_videotoolbox` with `-q:v 45`. This specific value provides the optimal balance where the output size almost perfectly matches a high-quality input.
    - **Ubuntu (NVIDIA)**: Use `h264_nvenc` with `-rc vbr -cq 23 -preset p4`. The combination of `vbr` (Variable Bitrate) and `cq` (Constant Quality) is the key to parity.
    - **Intel (QSV)**: Use `h264_qsv` with `-global_quality 23`.
    - **Software (Fallback)**: Use `libx264` with `-crf 23`.
- **Audio Preservation**: Default to `-c:a copy`. Re-encoding audio is a primary cause of subtle size increases and metadata loss.

## 5. Automation Algorithms

### 5.1 Semantic Segment Integrity (Python)
Instead of fixed length, use punctuation-based backtracking to ensure natural reading flow. Break at hard points (. ! ?) first, then soft points (, ; :).

### 5.2 Environment Unification
The project uses a **Unified Virtual Environment** located at the root (`.venv`). Submodules (like `subtitle`) MUST NOT have their own `.venv` or `pyproject.toml` to prevent `uv` environment mismatch warnings.

## 6. Pro Feature Specifications (2026 Expansion)

- **Whisper Turbo**: Default model is `turbo` (fine-tuned v3). Requires ~6GB RAM on Linux and provides 2x speedup over large-v3 with near-identical accuracy.
- **Temperature Control**: Default `0.0` for factual accuracy. 
- **LLM Selection**: Supports `deepseek` (Default), `gemini`, or `litellm`.

## 7. Diagnostic Procedures

### 7.1 disalignment in Mixed text
- **Check**: Ensure `RE_PUNCT_CLEANUP` regex is running to remove spaces before marks.
- **Check**: Verify RLM anchors (`\u200F`) are present at BOTH ends of the string.

### 7.2Centisecond Timing
Ass specs require two digits for centiseconds. Implementation: `cs = int(ms / 10)` formatted with `%02d`.

## 8. Quality Assurance Checklist
- [x] BiDi check: Punctuation is on the left for Persian sentences.
- [x] Size check: Output file size ≈ Input file size.
- [x] Font check: Parentheses content is visibly smaller (75%).
- [x] Env check: No `.venv` or `uv.lock` in subdirectories.
- [x] Performance check: Using `turbo` model by default.
