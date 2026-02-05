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

## 4. ✂️ Canvas Extension Patterns

### A. Extent (Padding to Fixed Size)
**Use Case:** Fit an image into a 1080x1080 square with white background.
```bash
magick "$input" \
    -auto-orient +repage \
    -resize "1080x1080" \
    -background white -gravity center -extent "1080x1080" \
    "$output"
```

### B. Splice (Adding Borders)
**Use Case:** Add a 100px bar to the Top or Bottom.
```bash
# Top Border
magick "$input" -background white -gravity North -splice 0x100 "$output"

# Right Border
magick "$input" -background white -gravity East -splice 100x0 "$output"
```

---

## 5. 📄 High-Fidelity PDF Generation
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
