---
description: Enhancing scanned documents and low-quality images for official use
---

# Document & Image Enhancement Skill

## Tools
| Tool | Type | Purpose |
|------|------|---------|
| **Upscayl** | Desktop | AI Upscaling (4x) |
| **GIMP** | Desktop | High-Pass + Overlay |
| **ImageMagick** | CLI | Selective darkening |
| **imgupscaler.ai** | Online | AI sharpening (free) |
| **Fotor** | Online | AI enhancement |
| **Topaz Labs** | Online | Pro sharpening (10 free) |

> [!CAUTION]
> **Legal Warning:** For official documents, use ONLY non-generative techniques (contrast, sharpen, levels). AI-generated content modification (like NanoBana, DALL-E, Gemini Imagen) may be considered document forgery.

---

## Techniques

### 1. AI Upscaling (Upscayl)
**Status:** ✅ Works
**Models:** `High Fidelity` or `Ultrasharp`
**Scale Options:**
- `1x` = Quality enhancement only (no size change) - good for online tools
- `4x` = Full upscale + enhancement

### 2. High-Pass + Overlay
**Status:** 🧪 Testing
**GIMP Steps:**
1. `Filters → Enhance → High Pass`
2. `Std. Dev: 8.0`, `Contrast: 1.5`
3. Layer Mode: `Overlay`, Opacity: 50-70%

**ImageMagick (for large files):**
```bash
magick input.png \
    \( +clone -blur 0x10 \) \
    +swap -compose Minus -composite \
    -level 45%,55% \
    input.png +swap \
    -compose SoftLight -composite \
    -quality 95 output.jpg
```

**Online Alternative:** [imgupscaler.ai](https://imgupscaler.ai)
> ⚠️ Max ~5MB. Resize first: `amir img resize big.png 2000`

### 3. Selective Text Darkening (ImageMagick)
**Status:** 🧪 Testing
```bash
magick input.png -black-threshold 40% output.jpg
```

### 4. Morphological Thickening
**Status:** ❌ Ineffective
```bash
magick input.png -negate -morphology Dilate Octagon:1 -negate output.jpg
```

### 5. Frequency Separation (Advanced)
**Status:** 🧪 Testing
**Purpose:** Isolate text layer from background, enhance separately
```bash
# Step 1: Low-freq (background)
magick input.jpg -blur 0x8 /tmp/low.png
# Step 2: High-freq (text details)
magick input.jpg /tmp/low.png -compose Minus -composite -evaluate Add 50% /tmp/high.png
# Step 3: Enhance text layer
magick /tmp/high.png -sigmoidal-contrast 4x40% /tmp/high_enh.png
# Step 4: Recombine
magick /tmp/low.png /tmp/high_enh.png -compose Plus -composite -evaluate Subtract 50% output.jpg
```

## ✅ Best Result Pipeline
**File:** `2-FINAL_text_normalize.jpg`

```
Step 1: ID Guénot.JPG (original 77KB)
    ↓
Step 2: Upscayl 4x (Ultrasharp model) → 285MB PNG
    ↓
Step 3: ImageMagick:
    magick input.png -normalize -level 10%,90% -sharpen 0x1.5 -quality 95 output.jpg
```

---

## Recommended Workflow
```
1. Upscayl 4x (High Fidelity or Ultrasharp)
   ↓
2. Normalize + Level + Sharpen (ImageMagick)
   magick input.png -normalize -level 10%,90% -sharpen 0x1.5 output.jpg
```

---

## Test Log
| Date | Technique | Result |
|------|-----------|--------|
| 2026-02-07 | Upscayl 4x | ✅ |
| 2026-02-07 | **Normalize+Level+Sharpen** | **✅ BEST so far** |
| 2026-02-07 | Normalize + black-threshold | ❌ Ruined image |
| 2026-02-07 | High-Pass + Overlay | ⚠️ OK |
| 2026-02-07 | Morphology Dilate | ❌ |

---

## AI Prompt Method (for selective text fix)
When automated tools fail, use AI image editors (NanoBana, etc.) with targeted prompt - see conversation for full prompt.

---

## Image Stacking (Combine Front/Back)

Combine front/back ID cards or multi-page documents into single image.

**Native ImageMagick:**
```bash
magick front.jpg back.jpg -auto-orient -gravity center -smush 20 -quality 95 output.jpg
```

**Amir CLI (wrapper with extras):**
```bash
amir img stack front.jpg back.jpg [-g 20] [-bg white] [-o output.jpg] [-p a4|b5] [--deskew]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-g` | `20` | Gap between images (pixels) |
| `-bg` | `white` | Background color |
| `-o` | `{first}_stacked.jpg` | Output filename |
| `-p` | - | Paper size preset (`a4` or `b5` at 150dpi) |
| `--deskew` | - | Auto-correct skewed scans |

**Auto-features (both methods):**
- ✅ Auto-orient: Fixes EXIF rotation automatically
- ✅ Quality: 95% JPEG
