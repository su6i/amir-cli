---
name: audio-processing
description: Audio Processing Technical Encyclopedia: LUFS Standards, Spectral Editing, Dynamic Range, and Professional Mastering Protocols.
---

# Skill: Audio Processing (Technical Encyclopedia)

[Back to README](../../README.md)

Comprehensive technical protocols for the acquisition, processing, and mastering of audio in the 2025 ecosystem. This document defines the standards for loudness normalization (LUFS), spectral signal repair, and high-fidelity signal orchestration.

---

## 1. Loudness Normalization Standards (LUFS / LKFS)
The industrial standard for consistent perceived volume across diverse platforms (YouTube, Spotify, Netflix).

### 1.1 BS.1770-4 Protocols
*   **Integrated Loudness:** Target for the entire track (Standard: -14 LUFS for YouTube, -16 LUFS for Podcast).
*   **True Peak (dBTP):** Maximum peak measured through inter-sample interpolation. Standard: < -1.0 dBTP to prevent clipping during lossy conversion (AAC/MP3).
*   **Loudness Range (LRA):** Measurement of the dynamic variety within a program.

### 1.2 Implementation Protocol (FFmpeg / Python)
```python
# 1.2.1 LUFS Analysis Logic
# Utilizing the 'loudnorm' filter for automatic matching to target.
ffmpeg -i input.wav -filter:a loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null -
```

---

## 2. Spectral Analysis & Signal Repair
Identifying and eliminating spectral artifacts using Short-Time Fourier Transform (STFT).

### 2.1 Spectral Repair Protocols
*   **De-Noising:** Utilizing spectral subtraction or AI-based models (e.g., Clear, iZotope RX) to separate signal from environmental noise.
*   **Mouth De-Clicking:** Visual identification of high-frequency transients unrelated to phonemes.
*   **Harmonic Reconstruction:** Synthesizing missing frequency bands when processing low-bitrate source material.

---

## 3. Dynamic Range Management
Controlling the bridge between the quietest and loudest parts of the signal.

### 3.1 Compression Logic & Parameters
*   **Threshold:** The level above which the signal is attenuated.
*   **Ratio:** The amount of attenuation applied (Standard: 3:1 for voice, 4:1 for aggressive control).
*   **Attack & Release:** 
    *   **Attack:** Velocity of response (Fast for transients, slow for transparency).
    *   **Release:** Velocity of recovery (Must be timed to prevent "pumping" artifacts).

### 3.2 Multiband Compression Standard
Processing specific frequency ranges (Low, Mid, High) independently to fix tonal imbalances without affecting the entire signal.

---

## 4. Technical Appendix: Comprehensive Audio Metric Reference
| Metric | Full Name | Standard |
| :--- | :--- | :--- |
| **LUFS** | Loudness Units relative to Full Scale | -14 to -16 |
| **dBTP** | Decibels True Peak | < -1.0 |
| **RMS** | Root Mean Square (Avg Power) | Variable |
| **THD** | Total Harmonic Distortion | < 0.1% |
| **Crest Factor** | Ratio of Peak to RMS | > 12dB (Good) |

---

## 5. Industrial Case Study: AI Dubbing Signal Path
**Objective:** Processing a raw multilingual recording for high-resolution distribution.
1.  **De-Verb:** Removing room reflections to simulate a dry studio environment.
2.  **Spectral Matching:** Aligning the EQ curve of the AI-generated voice to match the human original.
3.  **Phase Alignment:** Correcting micro-delays between multiple microphones to prevent comb filtering.
4.  **Brickwall Limiting:** Ensuring strict compliance with the -1.0 dBTP ceiling while maintaining constant -14 LUFS.

---

## 6. Glossary of Audio Processing Terms
*   **Sample Rate:** Number of snapshots taken per second (Standard: 48kHz for video, 44.1kHz for music).
*   **Bit Depth:** Number of bits used to represent each sample (Standard: 24-bit for recording, 32-bit float for processing).
*   **Dithering:** Adding low-level noise to mask quantization errors when reducing bit depth (e.g., 24 to 16-bit).
*   **Phase Inversion:** Flipping the polarity of a signal; used extensively for noise cancellation and phase checking.

---

## 7. Mathematical Foundations: The Fourier Transform
*   **Discrete Fourier Transform (DFT):** The mathematical process of converting a signal from the Time Domain (waveform) to the Frequency Domain (spectrum).
*   **Zero-Crossing:** The point where a waveform crosses the zero-amplitude line; the ideal point for splicing audio to avoid "clicks."

---

## 8. Troubleshooting & Quality Verification (The "Red Book")
*   **Aliasing:** High-frequency artifacts occurring when the signal exceeds the Nyquist frequency. *Fix: Use steep anti-aliasing filters.*
*   **DC Offset:** An electrical or digital displacement of the zero-axis. *Fix: Apply a high-pass filter at 20Hz.*
*   **Jitter:** Timing variations in the sample clock during A/D conversion.

---

## 9. Appendix: Surround and Object-Based Audio
*   **5.1 / 7.1 Mapping:** Traditional multi-channel standards.
*   **Dolby Atmos / ADM:** Metadata-driven spatial audio where sounds are "objects" placed in 3D space rather than assigned to specific speakers.

---

## 10. Benchmarks & Scaling Standards (2025)
*   **Processing Latency:** Target < 10ms for real-time monitoring.
*   **Signal-to-Noise Ratio (SNR):** Target > 90dB for studio-grade recordings.
*   **THD+N:** Targeted to remain below 0.005% throughout the signal chain.

---

## 11. MP3 Bitrate Standards & Practical File-Size Reference

### 11.1 Bitrate Selection Protocol
For audio extraction from video, bitrate selection depends on use case:

| Bitrate | Use Case | Size/hour | Size/2.5h |
|---------|----------|-----------|-----------|
| 320 kbps | Studio music master | ~144 MB | ~360 MB |
| 256 kbps | High-fidelity music | ~112 MB | ~280 MB |
| 192 kbps | Balanced music/podcast | ~84 MB | ~210 MB |
| **128 kbps** | **Conversation / podcast (recommended default)** | **~56 MB** | **~140 MB** |
| 96 kbps | Voice-only, low-bandwidth | ~42 MB | ~105 MB |

**Rule:** For spoken-word content, 128 kbps is perceptually indistinguishable from 320 kbps. Reserve 320 kbps for music.

### 11.2 Anti-Upscale Rule (Critical)
Never re-encode audio **above** the source bitrate. If the YouTube source stream is 48 kbps, encoding to 128 kbps produces a larger file with **no quality gain**:
```bash
# Correct: cap encode_abr at the source bitrate
encode_abr=$(( actual_abr < target ? actual_abr : target ))
ffmpeg -i source.m4a -c:a libmp3lame -b:a "${encode_abr}k" output.mp3
```

### 11.3 YouTube Audio Stream Reference (2026)
YouTube exposes 4 audio-only streams per video:
| format_id | abr | ext | codec | Best for target |
|-----------|-----|-----|-------|-----------------|
| 249 | ~46 kbps | webm | opus | target ≤ 48k |
| 139 | ~49 kbps | m4a | aac-lc | target ≤ 48k (m4a preferred) |
| 251 | ~129 kbps | webm | opus | target 128k (webm) |
| **140** | **~130 kbps** | **m4a** | **aac-lc** | **target ≥ 128k (recommended)** |

> See `.cursor/skills/yt-dlp-web-download.md` for the complete smart stream selection implementation.

---
[Back to README](../../README.md)

*Updated: 2026-02-24 — Added Section 11: MP3 bitrate standards, anti-upscale rule, and YouTube stream reference.*
