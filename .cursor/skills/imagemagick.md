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
