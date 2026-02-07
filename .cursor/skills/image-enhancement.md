---
description: Complete pipeline for enhancing scanned official documents (ID cards, passports, etc.)
---

# Document Quality Enhancement Skill

> [!CAUTION]
> **Legal Warning:** For official documents, use ONLY non-generative techniques (contrast, sharpen, levels). AI-generated content modification (like NanoBana, DALL-E, Gemini Imagen) may be considered document forgery.

---

## Tools Required

| Tool | Type | Purpose |
|------|------|---------|
| **Upscayl** | Desktop | AI Upscaling (4x) |
| **ImageMagick** | CLI | Contrast, sharpening, levels |
| **amir CLI** | CLI | Image stacking, PDF conversion |

---

## Complete Pipeline (Step-by-Step)

### Step 1: AI Upscaling
**Tool:** Upscayl (Desktop App)

| Setting | Value |
|---------|-------|
| Model | `Ultrasharp` |
| Scale | `4x` |
| Output Format | `PNG` |

**Output:** `{filename}_upscaled_4x.png` (~300MB)

---

### Step 2: Contrast & Sharpening
**Tool:** ImageMagick

**Native Command:**
```bash
magick "input_upscaled_4x.png" \
    -normalize \
    -level 10%,90% \
    -sharpen 0x1.5 \
    -quality 95 \
    "output_enhanced.jpg"
```

| Parameter | Effect |
|-----------|--------|
| `-normalize` | Auto contrast adjustment |
| `-level 10%,90%` | Darken text, whiten background |
| `-sharpen 0x1.5` | Sharpen edges |
| `-quality 95` | High quality JPEG |

---

### Step 3: Combine Front/Back (Optional)
**Tool:** ImageMagick / amir CLI

**Native ImageMagick:**
```bash
magick front.jpg back.jpg -auto-orient -gravity center -smush 20 -quality 95 output.jpg
```

**amir CLI (with extras):**
```bash
amir img stack front.jpg back.jpg --deskew -p a4 -o combined.jpg
```

| Option | Default | Description |
|--------|---------|-------------|
| `-g` | `20` | Gap between images (pixels) |
| `-bg` | `white` | Background color |
| `-o` | `{first}_stacked.jpg` | Output filename |
| `-p` | - | Paper size: `a4` or `b5` (150dpi) |
| `--deskew` | - | Auto-correct skewed scans |

**Auto-features:**
- ✅ Auto-orient: Fixes EXIF rotation
- ✅ Filename includes options (e.g., `_stacked_deskew_a4`)

---

### Step 4: Convert to PDF (Optional)
**Tool:** amir CLI

```bash
amir pdf "combined.jpg" -o "Document.pdf"
```

---

## Pipeline Summary

```
Original (77KB JPG)
     ↓
Step 1: Upscayl 4x (Ultrasharp) → PNG 300MB
     ↓
Step 2: normalize + level + sharpen → JPG 45MB
     ↓
Step 3: amir img stack --deskew -p a4 → A4 JPG
     ↓
Step 4: amir pdf → A4 PDF
```

---

## Processing Order Rule
> **Always:** Enhancement BEFORE Resize
> 
> 1. AI Upscale (more pixels = more data to work with)
> 2. Enhancement (normalize, sharpen, levels)
> 3. Resize to final size (shrinking preserves quality)

---

## Alternative Techniques (Testing)

### High-Pass + Overlay
```bash
magick input.png \
    \( +clone -blur 0x10 \) \
    +swap -compose Minus -composite \
    -level 45%,55% \
    input.png +swap \
    -compose SoftLight -composite \
    -quality 95 output.jpg
```

### Selective Text Darkening
```bash
magick input.png -black-threshold 40% output.jpg
```
**Status:** ❌ Not recommended (affects entire image)

---

## Test Log

| Date | Technique | Result |
|------|-----------|--------|
| 2026-02-07 | Upscayl 4x + Normalize + Level + Sharpen | ✅ BEST |
| 2026-02-07 | Normalize + black-threshold | ❌ Ruined image |
| 2026-02-07 | High-Pass + Overlay | ⚠️ OK but complex |
| 2026-02-07 | Morphology Dilate | ❌ Ineffective |
