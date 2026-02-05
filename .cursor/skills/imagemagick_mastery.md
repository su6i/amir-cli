# 🧙‍♂️ ImageMagick Mastery: The Definitive Guide

> [!NOTE]
> This guide documents advanced techniques and "Best Practices" discovered during the development of Amir CLI. It focuses on robust, deterministic image manipulation using ImageMagick v7 (`magick`).

## 1. The Golden Rules

### 🚫 Stop Using `convert`
ImageMagick v7 replaced `convert` with `magick`. Using `convert` is deprecated and may lead to unpredictable behavior or missing features.
- **Bad:** `convert input.jpg ...`
- **Good:** `magick input.jpg ...`

### 📐 Normalize Coordinates First
Images often contain metadata (EXIF Orientation) or Virtual Canvases (offsets) that mess up drawing coordinates.
**ALWAYS** run this sequence first:
```bash
magick input.jpg -auto-orient +repage ...
```
- `-auto-orient`: Rotates image efficiently based on EXIF.
- `+repage`: **Crucial.** Resets the coordinate system (0,0) to the top-left of the actual canvas. Without this, drawing at `0,0` might happen off-screen!

---

## 2. Corner Rounding: The "Clean Canvas" Strategy

We discovered that drawing directly on an image is risky because of existing alpha channels or weird offsets. The **Robust** way is to create a separate mask.

### The Algorithm
1. **Normalize:** Load Image -> Orient -> Repage.
2. **Create Mask:**
    - Clone the image (to get exact dimensions).
    - Make it transparent (`-alpha transparent`).
    - Draw solid WHITE shape on it (the part we want to KEEP).
3. **Composite:**
    - Use `-compose DstIn` (Destination In) to keep only pixels that overlap with the mask.

### The Code
```bash
magick input.jpg \
    -auto-orient +repage \
    -format png -alpha on \
    \( +clone -alpha transparent -fill white -draw "roundrectangle 0,0 %[fx:w-1],%[fx:h-1] $radius,$radius" \) \
    -compose DstIn -composite \
    output.png
```

### Why `%[fx:w-1]`?
ImageMagick coordinates are 0-indexed.
- Width `w` is the count of pixels.
- The last pixel index is `w-1`.
Drawing to `w` would go 1 pixel outside the canvas (sometimes acceptable, but `w-1` is mathematically precise).

---

## 3. Transparency & formats

### 👻 The "White on White" Trap
When you round corners, they become **Transparent**.
- If you view the PNG on a **White Background** (VS Code, GitHub Light Mode, macOS Preview), it looks like *nothing happened*.
- **Fix:** Always verify on a checkerboard or colored background.

### 📄 SVG Handling
Animated SVGs are tricky. ImageMagick might only grab the first frame (often blank or basic).
**Trick:** Use Python/Selenium to "bake" the SVG into a static raster if 100% accuracy is needed, OR assume static.

---

## 4. Useful One-Liners

### Create a Perfect Circle Crop
```bash
magick input.jpg -gravity center -crop 1:1 +repage -alpha set -background none -vignette 0x0 output.png
```

### Check Pixel Color (Debugging)
Check the top-left pixel to see if it's transparent:
```bash
magick image.png[1x1+0+0] -format "%[pixel:p{0,0}]" info:
# Output: srgba(0,0,0,0) -> Transparent
# Output: red -> Not Transparent
```

### Flatten Transparency (For JPG/PDF)
If saving to a format without alpha (JPG), you MUST flatten:
```bash
... -background white -flatten output.jpg
```
Otherwise, transparent areas might turn black.

---

## 5. Performance Tips
- use `mpr:{label}` (Memory Program Register) to store intermediate images in memory instead of temp files for complex chains.
- Process explicitly: Load -> Manipulate -> Write.

---

## 6. Advanced Techniques from the Trenches

### 🎨 Auto-Calculate Average Color
Need to extend an image seamlessly? Calculate the average color of the entire image by scaling it down to a single pixel.

```bash
# Extract the Hex/RGBA color of the average pixel
AUTO_BG=$(magick input.jpg -scale 1x1! -format "%[pixel:p{0,0}]" info:)
# Result: srgb(255,255,255)
```
*Used in `amir img extend`.*

### ✂️ Extending Canvas (Splice vs Extent)
- **`-extent`**: Resizes the canvas. Good for padding to a fixed size (e.g., 1080x1080).
- **`-splice`**: Inserts pixels (rows/columns). Good for adding a generic "border" or extra space at a specific edge.

```bash
# Add 100px red bar to the top
magick input.jpg -background red -gravity North -splice 0x100 output.jpg
```

### 📄 High-Quality PDF Construction
When converting images to PDF, density matters.
- **Critical:** Set `-density 300` **BEFORE** reading the image to tell Magick "treat this as high-res".
- **Sequence:**
    1. `-density 300`
    2. `-size A4` (or pixel equivalent `2480x3508`)
    3. `xc:white` (create canvas)
    4. Input images...

```bash
magick -density 300 -size 2480x3508 xc:white \
    \( input.jpg -resize 2480x3508 \) \
    -disterp none -compose Over -composite \
    output.pdf
```
*Used in `amir pdf`.*

### 🎭 Clone & Complex Chains
The `(` ... `)` parenthesis syntax allows you to create "side-chains" or temporary images in memory.
- `+clone`: Duplicates the last image in the stack.
- `-delete 0`: Removes the original if you only need the processed clone.
- `-swap 0,1`: Re-orders images for composition.

**Pattern:** Load Base -> ( Clone -> Process -> turn into Mask ) -> Apply Mask.
