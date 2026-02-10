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
| **amir CLI** | CLI | All-in-one: AI Upscale, Filter Lab, Stacking, PDF |
| **Real-ESRGAN** | Engine | Underlying AI engine (integrated in amir CLI) |
| **ImageMagick** | Engine | Underlying filter engine (integrated in amir CLI) |
| **Upscayl** | Desktop | GUI alternative for AI Upscaling |

---

## 🚀 Recommended CLI Pipeline

### Step 1: Quality Exploration (The Lab)
Before processing everything, find the "Golden Formula" for your specific scanner/document.
```bash
# Generate 140 variations (7 AI models x 20 filters)
# Logic: AI at 4x native -> Downsample to 1x -> Apply 20 filters
amir img lab input.jpg -s 1 -m all
```
**Results:** Check the `lab_input/` folder. Each subfolder corresponds to an AI model.

### Step 2: AI Upscaling & Enhancement
Once you find a model (e.g., `ultrasharp`), apply it.
```bash
# AI-Upscale (4x default)
amir img upscale input.jpg

# OR: AI-Enhance at 1x (No size change, just better quality)
amir img upscale input.jpg 1
```

### Step 3: Manual Filter (Optional)
If you don't want the full lab, apply the "Best" filter manually:
```bash
magick "input.jpg" -normalize -level 10%,90% -sharpen 0x1.5 "output.jpg"
```

### Step 4: Stacking & PDF
```bash
# Stack front/back with A4 preset and Auto-Straighten
amir img stack front.jpg back.jpg -p a4 --deskew -o id_card.jpg

# Convert to final PDF
amir pdf id_card.jpg -o id_card.pdf
```

---

## 📄 Professional Document Scanning (New)

For administrative documents (letters, forms) that need a **pure white background** and **crisp black text**, use the `scan` command.

```bash
# Comparison Mode: Generates 4 variations (Fast, Pro, OCR, Python)
amir img scan letter.jpg

# Single Mode: "Official Letter" grade (Global Illumination Normalization)
amir img scan letter.jpg --pro

# OCR Mode: Best for text extraction (Grayscale, High Contrast)
amir img scan letter.jpg --ocr

# Python Mode: OpenCV Adaptive Thresholding (High Fidelity)
amir img scan letter.jpg --py
```

### Techniques Used:
- **Global Illumination Normalization (Pro/OCR):** Uses a massive kernel (1/10th image size) to flatten lighting across the whole page, eliminating local halos.
- **Histogram Compression:** Crushes light grey noise into pure white.
- **Adaptive Thresholding (Python):** Uses OpenCV's Gaussian-weighted thresholding for precise text isolation.


## 🔬 AI Model Guide

| Model | Recommendation | Key Feature |
|-------|----------------|-------------|
| **`ultrasharp`** | **Official Documents** | Sharpens text edges, best for reading |
| **`upscayl-lite`** | **Speed** | 3x faster, good for quick previews |
| **`remacri`** | High Detail | Recovers fine textures |
| **`digital-art`** | Logos/Graphics | Smooths surfaces, removes JPG noise |

---

## 📏 Processing Rules
1. **Always use 4x internally:** ESRGAN models are native 4x. Using them at 1x/2x directly causes "Tiling" corruption.
   * *The amir CLI handles this automatically by upscaling to 4x and then downsampling.*
2. **Enhance BEFORE Resize:** AI-Upscale first to give ImageMagick more pixels to work with.
3. **Deskew after Stacking:** High-resolution stacks allow for more precise rotation math.

---

## Technical Log (milestones)
- ✅ **Real-ESRGAN CLI Integration:** Fixed tiling artifact by standardizing 4x native upscale + downsample.
- ✅ **Lab Integration:** Automated 420-variation generation (60 filters x 7 models).
- ✅ **Forensic Series:** Added specialized channel isolation and frequency filtering for ID cards.
- ✅ **Knowledge Integration:** Integrated "State of the Art" restoration pipeline (TextSR, OCR-aware, Restoration-first).

---

## 🕵️‍♂️ Forensic Document Restoration (Advanced)

When dealing with extremely poor quality documents (Motion Blur, Low-Res, Heavy JSON Noise), follow this industry-grade logic:

### 1. Restoration FIRST, AI-Upscale SECOND
*   **The Problem:** Most people jump directly to Super-Resolution (ESRGAN).
*   **The Professional Fix:** Restore the signal first.
    *   **Deblurring:** Use Wiener Deconvolution (or GAN-based deblurring).
    *   **Denoising:** Use BM3D or Deep Denoising (DnCNN) before upscaling.
    *   *Logic: Garbage in, Upscaled Garbage out. Fix the garbage first.*

### 2. Document-Specific Models
Do not use "Face" or "Anime" models for text.
*   **TextSR / TSRGAN:** Specialized for stroke recovery.
*   **DocSR:** Optimized for paper texture and ink contrast.
*   **Real-ESRGAN (Text/Contrast Models):** Our `ultrasharp` model is the closest general-purpose match.

### 3. OCR-Aware Enhancement
*   The goal isn't "pretty," it's "readable by machines."
*   **CLAHE (Local Contrast):** Essential for removing uneven lighting.
*   **Adaptive Binarization (LAT):** Best for converting low-res scans to clean BW for OCR.

### 4. Multi-Frame Reconstruction (Pro Tip)
If the user provides multiple poor photos of the same card:
1.  **Frame Alignment:** Sub-pixel alignment of all frames.
2.  **Statistical SR:** Reconstruct one high-res frame from the redundant information in multiple low-res frames.
