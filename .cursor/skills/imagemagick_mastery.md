# 🧙‍♂️ ImageMagick Mastery: The Definitive Recipe Book

> [!IMPORTANT]
> This is a **Strict Technical Reference**. Do not guess. Use these proven recipes exactly as written.
> **Core Principle:** Always normalize input using `-auto-orient +repage` before any operation.

## 1. 📐 The "Clean Canvas" Normalization Protocol
**Why:** Fixes EXIF rotation and "Virtual Canvas" offsets.
**When:** THE FIRST STEP OF EVERY COMMAND.

```bash
magick input.jpg -auto-orient +repage ...
```

---

## 2. 🎨 Corner Rounding (The "Robust Mask" Method)
**Problem:** Rounding directly fails on images with offsets or existing alpha.
**Solution:** Create a separate, pristine white mask on a transparent background.

```bash
# Variables: $input, $radius, $output (must be png)
magick "$input" \
    -auto-orient +repage \
    -format png -alpha on \
    \( +clone -alpha transparent -fill white -draw "roundrectangle 0,0 %[fx:w-1],%[fx:h-1] $radius,$radius" \) \
    -compose DstIn -composite \
    "$output"
```
*Key Detail:* `%[fx:w-1]` ensures we draw exactly within bounds (0-indexed).

---

## 3. 🔍 Smart Color Extraction
**Problem:** Need the average color of an image to extend borders seamlessly.
**Solution:** Scale to 1x1 pixel and read its color.

```bash
# Returns hex or rgba string (e.g., #FF0000 or srgba(255,0,0,1))
AVERAGE_COLOR=$(magick "$input" -scale 1x1! -format "%[pixel:p{0,0}]" info:)
```

---

## 4. 🛠️ Amir CLI Operation Recipes
These recipes map directly to `amir img` subcommands.

### A. `resize` (Simple Scale)
**Goal:** Resize image to fit within dimensions, preserving aspect ratio.
```bash
magick "$input" -auto-orient +repage -resize "${width}x${height}" "$output"
```

### B. `crop` (Fill & Cut)
**Goal:** Fill the dimensions completely (zoom) and crop the excess (center or gravity).
**Technique:** Resize to *Fill* (`^`) then Extent.
```bash
# Variables: $width, $height, $gravity (e.g., Center, NorthWest)
magick "$input" -auto-orient +repage \
    -resize "${width}x${height}^" \
    -gravity "$gravity" -extent "${width}x${height}" \
    "$output"
```

### C. `pad` (Fit & Box)
**Goal:** Fit image inside dimensions and fill the rest with a background color.
**Technique:** Resize to *Fit* then Extent.
```bash
# Variables: $bg_color (default: white)
magick "$input" -auto-orient +repage \
    -resize "${width}x${height}" \
    -background "$bg_color" -gravity center -extent "${width}x${height}" \
    "$output"
```

### D. `convert` (Format Change)
**Goal:** Change file format (e.g., SVG/WEBP to PNG/JPG).
**Critical:** Flatten transparency if saving to JPG.
```bash
# To PNG (Supports Transparency)
magick "$input" -auto-orient +repage "$output.png"

# To JPG (Needs Flattening)
magick "$input" -auto-orient +repage -background white -flatten "$output.jpg"
```

---

## 5. ✂️ Advanced Canvas Operations

### E. `extend` (Add Borders)
**Goal:** Add pixels to specific sides (Top/Bottom/Left/Right).
**Technique:** Use `-splice` (inserts pixels).
```bash
# Add 100px bar to Top
magick "$input" -auto-orient +repage -background "$color" -gravity North -splice 0x100 "$output"
```

---

## 6. 📄 High-Fidelity PDF Generation
**Problem:** Default conversions are low-res or wrong page size.
**Solution:** Set density *before* reading, define page size, and composite over white.

```bash
# Variables: $inputs (array), $output
magick -density 300 -size 2480x3508 xc:white \
    \( "$input_image" -resize 2480x3508 \) \
    -gravity center -compose Over -composite \
    "$output"
```
*Note:* For multiple images, iterate and composite them onto the canvas or use `convert` sequence if simple Append is needed.

---

## 6. 🛠 Troubleshooting & Transparency

### The "White on White" Illusion
**Symptom:** Corners look white, not rounded.
**Cause:** Viewing a transparent PNG on a white background.
**Verify:**
```bash
# Check Top-Left Pixel Transparency. Returns 'srgba(0,0,0,0)' if transparent.
magick "$output_file[1x1+0+0]" -format "%[pixel:p{0,0}]" info:
```

### Flattening for JPG
**Symptom:** Black corners when saving as JPG.
**Cause:** JPG has no alpha channel; transparency defaults to black.
**Fix:** Explicit flatten.
```bash
magick "$input_png" -background white -flatten output.jpg
```
