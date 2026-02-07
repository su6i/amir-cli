# ImageMagick Technical Reference

> [!IMPORTANT]
> This document serves as a technical reference for ImageMagick v7 operations used within the Amir CLI.
> **Standard Protocol:** Normalize input using `-auto-orient +repage` before processing.

## 1. Input Normalization
**Purpose:** Correct EXIF rotation and reset virtual canvas offsets to ensure deterministic coordinate systems.
**Command Sequence:**
```bash
magick input.jpg -auto-orient +repage ...
```

---

## 2. Corner Rounding Strategy
**Method:** Masking (Clean Canvas)
**Issue:** Direct drawing operations fail on files with existing offsets or alpha channels.
**Implementation:**
1. Clone image.
2. Create transparent mask.
3. Draw white rounded rectangle.
4. Composite using `DstIn`.

```bash
# Variables: $input, $radius, $output (PNG)
magick "$input" \
    -auto-orient +repage \
    -format png -alpha on \
    \( +clone -alpha transparent -fill white -draw "roundrectangle 0,0 %[fx:w-1],%[fx:h-1] $radius,$radius" \) \
    -compose DstIn -composite \
    "$output"
```
*Note:* `%[fx:w-1]` ensures drawing occurs within 0-indexed bounds.

> [!TIP]
> **Robust Alternative (CopyOpacity):** If `DstIn` causes color loss (white output), use:
> ```bash
> magick "$input" -alpha set \
>     \( +clone -fill black -colorize 100 -fill white -draw "roundrectangle 0,0 %[fx:w-1],%[fx:h-1] $radius,$radius" \) \
>     -alpha off -compose CopyOpacity -composite \
>     "$output"
> ```
> This strictly isolates alpha manipulation from color channels.

---

## 3. Average Color Extraction
**Purpose:** Determine dominant background color for seamless extension.
**Method:** Scale to 1x1 pixel.

```bash
# Output: Hex or RGBA string
AVERAGE_COLOR=$(magick "$input" -scale 1x1! -format "%[pixel:p{0,0}]" info:)
```

---

## 4. CLI Command Implementations
Mappings for `amir img` subcommands.

### A. Resize
**Operation:** Scale preserving aspect ratio.
```bash
magick "$input" -auto-orient +repage -resize "${width}x${height}" "$output"
```

### B. Crop (Fill)
**Operation:** Resize to fill dimensions, then crop excess.
```bash
# Variables: $width, $height, $gravity
magick "$input" -auto-orient +repage \
    -resize "${width}x${height}^" \
    -gravity "$gravity" -extent "${width}x${height}" \
    "$output"
```

### C. Pad (Fit)
**Operation:** Scale to fit dimensions, fill background.
```bash
# Variables: $bg_color
magick "$input" -auto-orient +repage \
    -resize "${width}x${height}" \
    -background "$bg_color" -gravity center -extent "${width}x${height}" \
    "$output"
```

### D. Convert
**Operation:** Format conversion.
**Requirement:** Flatten alpha channel if target format (e.g., JPEG) does not support transparency.

```bash
# To PNG
magick "$input" -auto-orient +repage "$output.png"

# To JPEG
magick "$input" -auto-orient +repage -background white -flatten "$output.jpg"
```

### E. Extend
**Operation:** Add border/padding to specific edges.
**Method:** `splice`.

```bash
# Example: Add 100px to Top
magick "$input" -auto-orient +repage -background "$color" -gravity North -splice 0x100 "$output"
```

---

## 5. PDF Generation
**Requirement:** High-resolution output (300 DPI).

```bash
magick -density 300 -size 2480x3508 xc:white \
    \( "$input_image" -resize 2480x3508 \) \
    -gravity center -compose Over -composite \
    "$output"
```

---

## 6. Troubleshooting

### Transparency Visualization
**Issue:** Transparent pixels appear white in some viewers.
**Verification:** Check alpha channel of top-left pixel.
```bash
# Expected output: srgba(0,0,0,0)
magick "$output_file[1x1+0+0]" -format "%[pixel:p{0,0}]" info:
```

### Alpha Flattening
**Issue:** Black artifacts in JPEG output.
**Cause:** Missing background layer when converting transparent source.
**Fix:** Apply `-background white -flatten`.

---

## 7. PDF Optimization Strategy (The "Sweet Spot")
**Goal:** <1MB file size for A4 documents without blurry text.

**1. Density is King:**
Never read a PDF without `-density`. ImageMagick defaults to 72 DPI, killing text quality before processing begins.
```bash
# BAD
magick input.pdf -resize 50% out.jpg

# GOOD
magick -density 300 input.pdf -resize 50% out.jpg
```

**2. The 75/75 Rule:**
- **Resize 75%:** (225 DPI valid for screen/ebook).
- **Quality 75:** (JPEG standard).
- **Chroma:** `-define jpeg:sampling-factor=4:4:4` (Prevents red/blue text blur).
- **Strip:** `-strip` (Removes huge EXIF blobs).

**3. Compression Command:**
```bash
magick -density 300 "$source" \
    -strip \
    -resize 75% \
    -define jpeg:sampling-factor=1x1 \
    -compress jpeg \
    -quality 75 \
    "$output"
```

---

## 8. Troubleshooting & Best Practices (Lessons Learned)

### 🔴 The "White Page" / Blank Output Issue
**Symptoms:** PDF output has correct file size (e.g., 7MB) but pages appear completely white or blank.
**Common Causes:**
1.  **Masking Complexity:** Using `-draw roundrectangle` with complex alpha compositing (`DstIn`) can sometimes mask the entire image if not handled perfectly.
2.  **Extent vs. Flatten:** Using `-extent` on an image with an active alpha channel (from masking) *before* correctly flattening it can lead to the background covering the content.
3.  **Over-Engineering:** Nesting multiple parentheses `( ( ... ) )` inside loops creates fragile command strings that are prone to "Unbalanced Parenthesis" errors.

**✅ Solution (The "Safe" Path):**
**Keep It Simple.** Avoid complex nesting for multi-page documents.
```bash
# BAD: Complex nesting, masking, and manual flattening per page
magick \( input.jpg -resize ... \( +clone -draw ... \) -compose ... \) -extent ... output.pdf

# GOOD: Simple Resize Pipeline
magick input.jpg -resize "2480x3508>" -density 300 output.pdf
```

### 🔴 Unbalanced Parentheses
**Symptoms:** `magick: unbalanced parenthesis` error.
**Cause:** 
-   Opening a parenthesis `(` inside a loop but failing to close it correctly in all logic branches.
-   Duplicating `final_cmd+=("(")` lines during refactoring.
**Fix:** 
-   Count your parentheses. 
-   Use linear command structures where possible.
-   Avoid excessive nesting `( ( ) )` if a single simple chain works.

### 🔴 Flattening Transparency
**Legacy Method:** `-flatten` (Older, sometimes buggy with specific compose methods).
**Modern Method:** `-alpha remove -alpha off`.
**Why?** `-alpha remove` blends the image onto the current background color (white) and removes the alpha channel entirely, ensuring a solid opaque image.
```bash
# Robust Flattening
magick input.png -background white -alpha remove -alpha off output.jpg
```
