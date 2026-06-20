# 🏗 Technical Documentation & Architecture

[← Back to README](../README.md)

This document provides a deep dive into the internal structure, logic, and design patterns of **Amir CLI**. It is intended for advanced users, contributors, and those who want to extend the tool.

---

## 📂 Project Structure

```bash
amir-cli/
├── amir                  # The main executable (Bash script entry point)
├── install.sh            # Automated installer (symlinks & dependencies)
├── completions/
│   └── _amir             # Zsh autocompletion definitions
├── lib/
│   ├── amir_lib.sh       # Core libraries (colors, helpers, progress bar)
│   ├── media_lib.sh      # Shared media functions (encoder, tables, probing)
│   ├── python/           # Python helper scripts (standard library ONLY)
│   └── commands/         # Individual subcommand scripts
│       ├── video.sh      # Video processing (compress, cut, download)
│       ├── audio.sh      # Audio extraction, concat, youtube
│       ├── img.sh        # Image processing logic
│       └── ...
└── docs/
    └── TECHNICAL.md      # This file
```

---

## 🧠 Core Logic & Design

### 1. Entry Point (`amir`)
The `amir` script is the brain of the operation. It performs the following steps on every run:
1.  **Symlink Resolution:** It robustly resolves its own physical location, even if invoked via a symlink (e.g., from `/usr/local/bin/amir`). This ensures relative paths to `lib/` always work.
2.  **Environment Setup:** Sources `lib/amir_lib.sh` to load global variables (like `LIB_DIR`, `py_script`) and helper functions.
3.  **Command Routing:**
    - It checks the first argument (`$1`) to determine the requested command.
    - It looks for a corresponding script in `lib/commands/$1.sh`.
    - If found, it sources that script and calls the `run_$1` function (dashing naming convention: `run_img`, `run_qr`).

### 2. Dependency Management
To ensure maximum portability and zero setup friction:
- **No Pip/Venv:** We deliberately avoid using `pip` or virtual environments.
- **Python Standard Library:** Any Python logic (in `lib/python/`) uses **only** the standard library (`json`, `os`, `sys`, `urllib`, etc.). This guarantees the CLI runs on any machine with Python 3 installed.
- **External Tools:** We rely on robust system binaries like `ffmpeg` (media), `magick` (images), and `bc` (math), which the installer checks for.

### 3. Zsh Autocompletion
The completion script (`completions/_amir`) is a sophisticated Zsh function that:
- Dynamically handles subcommands.
- Provides context-aware suggestions (e.g., listing image sizes for `img resize` or gravity options for `img crop`).
- Is properly registered to `fpath` by the installer.

---

## 🛠 Extending Amir CLI

Adding a new command is designed to be trivial.

### Step 1: Create the Script
Create a new file in `lib/commands/mycmd.sh`.

### Step 2: Define the Function
Inside the file, define a function named `run_mycmd`.

```bash
run_mycmd() {
    echo "This is my new custom command!"
    echo "Arguments passed: $@"
}
```

### Step 3: Usage
No registration needed! Just run:
```bash
amir mycmd "hello world"
```
The router automatically detects the file `mycmd.sh` and executes `run_mycmd`.

### Step 4: Autocompletion (Optional)
To get tab-completion for your new command:
1. Open `completions/_amir`.
2. Add your command to the logic (look for the `_arguments` or `case` block).
3. Restart your shell.

### Real-World Example: `qr` Command

Here is a simplified look at how the `amir qr` command is implemented in `lib/commands/qr.sh`:

```bash
run_qr() {
    local input="$1"
    
    # 1. Validation
    if [[ -z "$input" ]]; then 
        echo "❌ Error: Input required."
        return 1
    fi

    # 2. Logic (Detect protocol)
    if [[ "$input" =~ ^[0-9+]+$ ]]; then
        input="tel:$input"
    elif [[ "$input" == *@*.* ]]; then
        input="mailto:$input"
    fi

    # 3. Execution (Use external tool)
    echo "📌 Generating QR for: $input"
    qrencode -t ANSIUTF8 "$input"
}
```
This shows how you can mix shell logic, argument parsing (`$1`), and external tools (`qrencode`) seamlessly.

### 4. Autocompletion (Zsh)
To give users helpful hints, we need to update `completions/_amir` in **two places**.

#### A. Register the Command
First, add your command to the main list (around line 20):

```zsh
    if (( CURRENT == 2 )); then
        local -a commands
        commands=(
            # ... existing commands ...
            'qr:Create smart QR Code'  # <--- Add this line
        )
        _describe -t commands 'commands' commands
```

#### B. Define Logic
Then, add the argument handling logic to the main `case` statement:

```zsh
    case "$words[2]" in
        qr)
            case $((CURRENT)) in
                3) _message "Enter URL, phone number, email or text" ;;
                4) _message "Output filename (optional)" ;;
            esac
            ;;
```

### 5. Usage
Now you can run:
```bash
# Generate in terminal
amir qr "https://google.com"

# Save as image
amir qr "+989123456789" contact.png
```

---

## 🔍 Specific Command Logics

### `clip` (Smart Clipboard)
- **Functionality**: Replaces single-purpose `pbcopy`/`pbpaste`. Handles text strings, file contents, and binary transfers.
- **Piping Architecture**:
    - **Input Pipe**: If `stdin` is not a TTY, it reads the stream. If a filename is provided, it saves to that file; otherwise, it copies to the system clipboard.
    - **Output Pipe**: If `stdout` is not a TTY and no arguments are provided, it outputs the current clipboard content. This enables workflows like `amir clip | amir pdf`.
- **System Commands**: Wraps `pbcopy`/`pbpaste` (macOS), `xclip`/`xsel` (Linux).

### `img` (Image Processing)
- **Architecture:** Split into sub-functions `do_resize`, `do_crop`, and `do_pad`.
- **Tool Abstraction:** It attempts to use `magick` (ImageMagick v7) first. If not found, it falls back to `convert` (IM v6). On macOS, it has a limited fallback to `sips` (Apple's native image tool) for basic operations. For SVG files specifically, it uses `rsvg-convert` (from `librsvg`) to ensure perfect geometry and font rendering, falling back to `magick` only if unavailable or for intermediate format conversion.
- **Smart Legacy Mode:** If no subcommand (`resize`/`crop`) is given, it inspects arguments to guess the user's intent (e.g., presence of gravity code = crop).
- **Extend Subcommand:** Uses `magick` -splice capabilities to add borders. Supports auto-average background color calculating and independent per-side coloring.
- **Smart File Naming**: Output filenames automatically append used options (e.g., `_bg-blue_circle`) to prevent accidental overwrites. Includes interactive overwrite protection if a collision occurs.

#### 🎨 Image Corner Rounding (`round`)
- **Format Support**: `amir img round` now supports both PNG (for transparency) and JPG (flattened against a white background).
- **macOS Compatibility**: Uses shell-safe `tr` translations instead of Bash 4+ `${var^^}` syntax to maintain full compatibility with macOS default Bash 3.2.
- **Robust Masking (CopyOpacity Strategy)**: Uses `-compose CopyOpacity` to strictly separate alpha channel manipulation from color channels. This prevents the "white page" bug where DstIn composition could replace image color with mask color on certain ImageMagick versions.

#### 🧠 Smart Crop (Content-Aware)
- **Algorithm:** Uses `lib/python/smart_crop.py` with OpenCV.
- **Pipeline:**
  1. **Preprocessing:** Gaussian Blur + Canny Edge Detection.
  2. **Morphology:** Dilates edges to connect disjoint parts (e.g., text lines in a receipt) into a single "blob".
  3. **Detection:** Finds the largest external contour and computes its bounding box.
  4. **Fallback:** If no distinct subject is found, it returns the original image to prevent accidental data loss.
- **Integration:** Available in `amir img crop --smart` and `amir pdf --smart` (auto-crops before merging).

#### 🎥 Static SVG Baking (Animated SVGs)
When converting a `.svg` file that contains CSS animations (`@keyframes`), Amir CLI uses a custom Python script (`lib/python/svg_bake.py`) instead of a headless browser.
- **Mechanism:** It parses the SVG text, identifies keyframe animations, calculates the final state properties, and injects them as inline `style` overrides with `!important`.
- **Why?** Eliminates the heavy dependency on Puppeteer/Chromium, making the CLI faster and more portable (no installation of Node.js required).
- **Whitespace Handling:** Uses literal `\u00A0` (Non-Breaking Space) and `xml:space="preserve"` to ensure `rsvg-convert` renders text spacing correctly.

#### 📦 Image Compression (`compress`)
- **Algorithm:** Two-phase pipeline per file:
  1. **Phase 1** — binary-search JPEG quality (default 85→50) at full dimensions until target size is met.
  2. **Phase 2** — if quality floor is insufficient, reduces dimensions in 10% steps (80%→70%→…→20%) at `min_quality` until target is met.
- **`--uniform` mode:** Pre-pass probes every file to find the most restrictive scale needed, then applies that common scale to all files. Ensures all outputs share the same physical dimensions — useful for document front/back pairs.
- **`--grayscale` mode:** Adds `-colorspace Gray -normalize` before JPEG encoding. Typically halves file size vs. color mode with no loss of text legibility — recommended for official documents.
- **Output:** Always JPEG (`.jpg`) for maximum compression. Uses `JPG:` format prefix so ImageMagick writes JPEG regardless of temp-file extension (required on macOS BSD `mktemp` which does not support extensions in templates).
- **Batch:** Accepts multiple files or globs; reports per-file result and a summary line.

### `img scan` (Document Scanning)
- **Purpose:** Converts photos of documents into "Official Administrative" scans (Pure white background, sharp black text).
- **Architecture:** Hybrid Shell/Python pipeline.
- **Modes:**
  1.  **Fast (Shell/IM):** Simple histogram stretch.
  2.  **Pro (Shell/IM):** Uses "Global Illumination Normalization" (Divide by large version of self) + Histogram Crushing.
  3.  **OCR (Shell/IM):** Aggressive binary-like grayscale for machine reading.
  4.  **Python (OpenCV):** Uses `uv run` to execute `lib/python/doc_scan.py`. Implements adaptive Gaussian thresholding and median blurring for "Official Letter" quality.
- **Dependencies:** The Python mode automatically manages `opencv-python` via `uv`, requiring no manual user installation.


### `video` (Advanced Video Processing)
- **Unified Entry:** Single command handles compression, trimming, and batch processing.
- **Encoding Toggle:** `--gpu` (default on Apple Silicon) uses hardware encoder for speed. `--cpu` forces `libx265` for maximum compression efficiency.
- **Compression Profiles:**
  - Numeric mode: `<resolution> <quality>` (legacy-compatible).
  - `extreme`: tuned for minimum size (`360p`, CPU mode, low audio footprint).
  - `--fps <N>`: explicit output frame rate (can be lower than 24, e.g. 10fps).
  - `--split <MB>`: post-encode split into approximate chunk sizes using FFmpeg segment muxer.
- **Subcommands:**
    - `cut` (or `trim`): Fast video slicing. Uses `-c copy` (stream copy) by default for near-instant cutting without quality loss. Supports `-s` (start), `-e` (absolute end on original timeline), `--duration`, `-d/--delete <start> <end>` to remove a middle range and stitch the rest, and `-x/--extract <start> <end>` to keep only that range (default output: `_cut_<start>_<end>`).
    - `convert`: Container format conversion (MOV→MP4, MKV, WEBM, AVI). Default: stream-copy (instant, no quality loss). `--cpu` forces re-encode via libx264 CRF 23 — better for text/slides; auto-appends `_converted` suffix if input and output format match. Output without extension auto-appended with target format.
  - `split`: Split an existing media file into approximate MB chunks without re-encoding.
    - `batch`: Optimized for directories.
    - `stats`: View AI learning statistics.
    - `download <url> [opts]`: Download from YouTube & 1000+ sites (see below).
  - `tiktok <url> [opts]`: Thin wrapper around `download` with TikTok-oriented defaults.
- **Orientation Awareness:** Automatically detects Portrait vs. Landscape orientation.
- **Hardware Acceleration:** Auto-detects macOS Silicon (`videotoolbox`), NVIDIA (`nvenc`), or Intel (`qsv`). Toggle with `--gpu`/`--cpu` flags.
- **Smart Encoding:** Output size is validated post-encoding. If output > input, user is warned with a suggestion to try `--cpu` mode.
- **Split Semantics:** `--split` is size-targeted but keyframe-bound, so each chunk is approximate (not exact byte-perfect cuts).
- **Real-Time Progress:** Universal `ffmpeg_progress_bar` displays percentage, ETA, speed, and bitrate for all media operations.
- **Local ML Estimation:** Features an intelligent, localized tracking system that evaluates past performance specific to the user's CPU/GPU and typical video sources. Variables `quality_factor` and `speed_factor` are persistently saved to `~/.amir-cli/learning_data` and automatically read to accurately predict final output size (`Est Size: ~X MB`) and processing time (`Est Time: XhYmZs`).
- **Batch Processing:** Processes directories by looping over standard video formats (`.mp4`, `.mov`, etc.), intentionally bypassing OS resource forks (like `._` hidden files on ExFAT drives). Also skips already processed outputs (`_720p_q60` or pre-existing files) seamlessly to prevent loops.
- **Table Alignment:** Uses Python's `unicodedata` library to strictly calculate visual string width (East Asian Width). All tables rendered via shared `print_media_table()` function.

### `media_lib.sh` (Shared Media Functions)
**Purpose:** Centralized library sourced by `video.sh` and `audio.sh` to eliminate code duplication.

| Function | Purpose |
|---|---|
| `detect_encoder(mode)` | Auto-detect GPU/CPU encoder. `--gpu` selects hardware, `--cpu` selects `libx265`. |
| `get_media_duration(file)` | Extract duration in seconds via `ffprobe`. |
| `get_media_bitrate(file)` | Extract bitrate with container → stream fallback. |
| `get_media_info(file)` | Full probe: width, height, rotation, duration, portrait detection. Sets `MEDIA_*` globals. |
| `build_encoder_opts(enc, quality, bitrate)` | Build encoder-specific quality options (`-b:v` for VideoToolbox, `-q:v` for libx265). |
| `calculate_target_bitrate(bitrate, quality, enc)` | Smart bitrate scaling to prevent output bloat. |
| `validate_output_size(input, output, enc)` | Post-encode guard: warns if output > input. |
| `detect_hardware()` | CPU/GPU info for display tables. Sets `HW_CPU_INFO`, `HW_GPU_INFO`. |
| `print_media_table(width, header, rows...)` | Universal Unicode table renderer (N columns, auto-width). |
| `format_duration(seconds)` | `HH:MM:SS` formatter. |
| `run_ffmpeg_with_progress(duration, cmd...)` | Execute FFmpeg with automatic progress bar and error capture. |

Notes:
- In software HEVC mode (`libx265`), quality values `<= 51` are treated as CRF mode (`-crf`) to support aggressive profiles cleanly.
- Subtitle burn path (`amir video cut --render`, used by `amir subtitle`) is a separate re-encode pipeline from `amir video compress`.
- Subtitle render defaults to the input video height when `--resolution` is not provided.
- If a sidecar thumbnail (`.jpg/.jpeg/.png`) exists near the source, subtitle render can inject it as startup frame content (first ~80ms) in the same render pass to improve client previews.
- Branded subtitle overlays are supported in the same render pass: `--subtitle-banner-image` or `--subtitle-banner-color`, optional `--subtitle-logo` (with `--subtitle-logo-animated`), and timed guest lower-thirds via repeatable `--guest-tag`.
- Overlay chains use `shortest=1`/`eof_action=pass` on compositing stages to prevent frozen-video outputs when static/auxiliary overlay sources are present.
- When any banner option (`--subtitle-banner-color` or `--subtitle-banner-image`) is provided, the ASS subtitle background is forced to fully transparent (`&H00000000`) regardless of style — this ensures the banner colour is visible and not covered by the subtitle box. Implemented in `cli.py`.

#### `video download` — Download + Subtitle Pipeline

```bash
amir video download <url> [options]
```

| Flag | Behavior |
|------|----------|
| `--yt-subs` | Download and use YouTube's built-in subtitles (human-curated first, auto-gen fallback). Bypasses Whisper transcription. |
| `--subtitle / -s` | Run Whisper AI transcription on the downloaded video, then burn. Sets `DO_RENDER=true`. |
| `--translate` | Download YT subs + translate via DeepSeek → **burn into video by default** (`DO_RENDER=true`). Skip Whisper. |
| `--sub-only` | Public flag for subtitle-only output (no burn). `--no-render` is still accepted as alias. |
| `--target / -t [src] lang` | Subtitle language. Two-value form: `-t en fa` (source=en, target=fa). Single: `-t fa` (source stays default `en`). |
| `--only-subs` | After subtitle generation, prompt to delete the raw downloaded video. |
| `--get-link / -l` | Print the direct stream URL(s) without downloading (for external download managers). |
| `--formats / -F` | List available resolutions and estimated sizes before downloading. |
| `--resolution / -R <h>` | Explicit download max height (e.g. `240/360/480/720/1080`). For auto-min selection, use `--extreme`. |
| `--extreme` | Auto-pick smallest practical available resolution (floor: 240p) for minimum size. |
| `--browser <name>` | Browser for cookie extraction (default: `chrome`). |
| `--cookies <file>` | Path to a Netscape `cookies.txt` file (for paywalled or geo-restricted content). |
| `--keep-thumb` | Keep downloaded thumbnail sidecar file (otherwise temporary thumbs may be cleaned). |

**Key design rules:**
- `--translate` implies `DO_RENDER=true` — the translated subtitle is burned into the video automatically.
- Use `--sub-only` (or `--no-render`) to get SRT-only output: `amir video download <url> --translate -t en fa --sub-only`.
- The `-t` parser guards against consuming the URL as a language: values matching `^https?://` or longer than 10 chars are never parsed as language codes.
- Shell-escaped backslashes are stripped from the URL automatically (`URL="${URL//\\/}"`) — users can paste unquoted zsh-escaped URLs without errors.
- Same-source/target validation: `-t en` with default source `en` produces a clear error instead of a silent no-op.
- Existing downloads in the current working directory are matched and reused before re-downloading (exact, prefix, then semantic normalized-title fallback).
- Download outputs use `--no-overwrites` and are normalized to terminal-safe stems with an explicit `_<resolution>p` suffix.
- Runtime artifacts are kept in the user's current working directory to maximize reuse across subtitle/translate/render reruns.

**Translation workflow (`--translate`):**
1. Probe title and attempt local reuse by normalized stem + resolution; only run yt-dlp when no reusable file is found.
2. Download video with yt-dlp (`--print after_move:filepath`, `--no-overwrites`, filtered streaming progress) and normalize filename to terminal-safe ASCII.
3. Apply resolution suffix (`_<resolution>p`) for deterministic reuse keys.
4. Fetch YT built-in subtitles (`--skip-download --write-subs --write-auto-subs`, prefer `*.en.srt` over `*.en-orig.srt`)
5. Copy chosen source SRT to `_en.srt` (triggers Whisper-skip in `amir subtitle`)
6. Call `amir subtitle <video> -s en -t fa` with or without `--sub-only`
7. `amir subtitle` pre-processes the source SRT: **Clause Merging**. Automatically merges fragmented YouTube subtitle lines into semantically complete clauses (breaking only on `. , ? ! : ;`).
8. `amir subtitle` does LLM translation → validates 100% → optionally burns with ffmpeg (Always forces **H.264 (`-pix_fmt yuv420p`)** for maximum cross-platform compatibility like Telegram/QuickTime, safely ignoring AV1 triggers).

**Robust `yt-dlp` Configuration & URL Parsing (Lessons Learned):**
- **Strict URL Extraction (UTF-16 vs Unicode):** Never pass raw user input directly to `yt-dlp`. Always extract the URL using `extract_link_from_text` first. **CRITICAL WARNING:** Do not rely on Telegram's `entity.offset` and `entity.length` for raw `url` entities if mixing emojis or Persian characters. Telegram provides these offsets in **UTF-16 code units**, whereas Python 3 strings are Unicode characters. An emoji counts as 2 units in UTF-16 but 1 in Python, causing severe string slicing misalignments:
  ```python
  # INCORRECT: Will break if the message contains emojis before the URL
  url = text_content[entity.offset : entity.offset+entity.length]
  
  # CORRECT: Encode to UTF-16 first, slice the bytes, then decode
  encoded = text_content.encode('utf-16-le')
  url = encoded[entity.offset*2 : (entity.offset+entity.length)*2].decode('utf-16-le')
  ```
- **Systemd Logging:** If a server's `.service` file uses `StandardOutput=append:/home/user/bot.log`, the `journalctl -u bot -f` command will **NOT** show any Python application output or Exception tracebacks. Always check the physical `bot.log` file when debugging silent failures on production.
  import re
  match = re.search(r'(https?://\S+)', user_text)
  target_url = match.group(1) if match else user_text
  ```
  Failing to do so results in `yt-dlp` interpreting the entire block of text as a single invalid URL or mistaking newlines/text for unsupported command-line options.

### `pdf` (Multi-Engine High-Fidelity Rendering)
- **Architecture:** Hybrid system utilizing specialized rendering engines with a robust fallback pipeline.
- **Engines:**
    - **Puppeteer (Default):** Chromium-based rendering for highest fidelity. Supports CSS3, complex layouts, and modern typography.
    - **WeasyPrint:** Python-based CSS/HTML renderer (optimized for print).
    - **Pandoc:** Vector-based conversion for document formats.
    - **PIL (Fallback):** Ultra-robust image-based renderer. Used automatically if advanced engines fail to ensure no content loss. Supports infinite vertical pagination.
- **Key Technical Features:**
    - **Continuous / Free-Size Rendering:** The `--free-size` (`-f`) flag bypasses A4 constraints. `render_puppeteer.js` measures the rendered body size and can also honor `--page-width` / `--page-height` for manual sizing, so tables and blocks can stay on a single page when you give the layout enough width.
    - **Piping Support:** Accepts `stdin` if no file arguments are provided. Integrated with `mktemp` to handle content safely and provides descriptive "clipboard" logging/naming.
    - **ExFAT Robustness:** Automatically detects ExFAT filesystems (e.g., SanDisk drives) and bypasses `uv run` in favor of direct `.venv/bin/python3` execution to avoid "Operation not supported" errors caused by ExFAT's lack of file locking.
    - **Base64 Font Embedding:** To bypass browser security restrictions (`file://`), the **B Nazanin** Persian font is injected directly as a Base64 Data URI into the Puppeteer HTML stream.
    - **Themes (`--theme <name>` → `lib/themes/<name>.css`):** appended after the base style so they can override it.
        - `carousel` — square **1080px** LinkedIn slides; each `##` heading starts a new `.slide` (1080×1080, content vertically centred, `overflow:hidden`). Tables use `table-layout:fixed` with column ratios (col 1 = 5%), so prefer bold-label lists over wide label tables. Render: `amir pdf carousel.fr.md -o carousel.fr.pdf --theme carousel` (add `--force-rtl` for Persian).
        - `guide` — clean professional **A4** long-form document (guides, reports, legal texts): coloured headings with accent bars, boxed blockquotes, clickable links; LTR + RTL via CSS logical properties (`border-inline-start`). Render: `amir pdf guide.fr.md -o guide.fr.pdf --theme guide` (add `--force-rtl` for Persian).
    - **Persian number formatting (authoring rule):** When preparing Persian/Arabic Markdown for `amir pdf`, do **not** put a thousands separator (space or `٬`) inside numbers — write `۱۸۶۷` not `۱ ۸۶۷`. A space between digit groups is rendered literally and breaks Persian number reading in the PDF. Decimal separators (`٬`/`٫`) are fine. (This is an authoring convention; the renderer does not auto-strip separators.)
    - **Direction Detection & `--force-rtl`:** By default `render_puppeteer.js` auto-detects document direction (Persian vs Latin character count) and, as a per-element fallback, flips any block that *starts* with a Latin character to LTR. This heuristic breaks RTL documents whose lines legitimately begin with a Latin token (URLs, code, legal references like `CESEDA L421-1`, `€2,800.53`): such lines get left-aligned, scrambling a Persian/Arabic page. The **`--force-rtl`** flag (alias `--rtl`; passed as the 9th positional arg to `render_puppeteer.js` and forwarded by `pdf.sh`) pins `docDir = rtl` and disables the per-element LTR flip, forcing every block (`p, li, ul, ol, h1–h6, th, td, blockquote`) to `dir="rtl"` / `text-align:right`. **Rule of thumb: always pass `--force-rtl` when rendering a Persian/Arabic file that mixes in Latin tokens.**
    - **Smart Pagination:** Uses CSS `page-break-inside: avoid` to prevent element splitting. The assembly loop in `pdf.sh` uses explicit page selection (`[0-999]`) to ensure ImageMagick captures every page from multi-page PDFs.
    - **Finder Optimization:** On macOS, the script executes `touch` on the final output to force Finder to refresh "Date Added" and "Date Modified" metadata.
    - **Disk Space Overflow:** If the internal disk is full (100% capacity), the script automatically redirects `TMPDIR`, `UV_CACHE_DIR`, and Chrome profiles to `/Volumes/SanDisk/amir_data`.

### `img` (Image Manipulation) - AI & Laboratory
- **Upscaling Architecture:** Uses the `realesrgan-ncnn-vulkan` binary. 
  - **Tiling Fix:** ESRGAN models are native 4x. To prevent tiling artifacts at other scales, the CLI always upscales to 4x internally and then downsamples via ImageMagick to the target scale (1x, 2x, 3x).
  - **Hardware Support:** Utilizes Vulkan for acceleration (Metal on macOS).
- **Enhancement Lab (`lab`):** 
  - **Logic:** Automates the testing of 20 unique ImageMagick filter chains per model.
  - **Single Mode (Default):** Runs on 1 selected model (default: ultrasharp) → **20 images**.
  - **Multi Mode (`-m all`):** Iterates through all 7 AI models → **140 images** (7 models × 20 filters).
  - **Hierarchical Storage:** Organizes results into `lab_{base}/{model}/{filter}.jpg` for easy comparison.
- **Stacking:** Combines images with auto-orient and deskew. Uses paper-size presets (A4/B5 at 150DPI) for standardized document preparation.

### `subtitle` (AI-Powered Multilingual Subtitle System)
**Architecture:** Hybrid Python/FFmpeg pipeline with intelligent caching, validation, and rendering.

#### Branded Render Presets
- `channel_brand_blue`: Blue lower-third branding baseline for horizontal videos.
- `shorts_brand_blue`: Shorts-optimized version with tighter banner/logo defaults.
- `news_guest_blue`: News lower-third preset tuned for guest name/title overlays.
- `--brand-kit <logo>`: One-shot brand setup (auto wires logo + blue banner defaults).
- `--brand-kit-shorts`: Pair with `--brand-kit` to apply Shorts-oriented defaults.

#### Component Stack
1. **Transcription Engine:**
   - **Primary:** `faster-whisper` (CPU-optimized Whisper)
   - **Apple Silicon:** `mlx-whisper` (Metal acceleration via MLX framework)
   - **Model:** Default `large-v3` (highest accuracy)
   - **Optimization:** Smart caching with SHA-256 hash keying (`~/.amir_cache/transcriptions/`)

2. **Translation System:**
    - **Primary Provider:** DeepSeek API (GPT-4 class quality, cost-effective).
    - **Smart Model Selector:** Dynamically selects `deepseek-v4-pro` (thinking mode) before June 2026 to leverage the 75% discount, automatically reverting to `deepseek-v4-flash` (non-thinking mode) post-expiry to prevent overcharging.
    - **Fallback Chain:** LiteLLM → Gemini
    - **Batch Processing:** 25 lines per API call (DeepSeek), 40 lines (Gemini), 20 lines (LiteLLM)
    - **Cache:** SHA-256 keyed translations (`~/.amir_cache/translations/`)

3. **Language Support (32 Languages):**
   - **Centralized Registry:** `LANGUAGE_REGISTRY` dataclass-based configuration
   - **Components:** Language code, display name, Unicode char range, RTL flag
   - **Top 25 (YouTube Priority 2026):**
     ```
     zh (Chinese), en (English), es (Spanish), hi (Hindi), ar (Arabic),
     bn (Bengali), pt (Portuguese), ru (Russian), ja (Japanese), fr (French),
     ur (Urdu), pa (Punjabi), vi (Vietnamese), tr (Turkish), ko (Korean),
     id (Indonesian), de (German), fa (Persian), gu (Gujarati), it (Italian),
     mr (Marathi), te (Telugu), ta (Tamil), th (Thai), ha (Hausa)
     ```
   - **Additional:** Greek, Hebrew, Malagasy, Dutch, Polish, Ukrainian

4. **Quality Assurance:**
   - **Multi-Stage Parser:**
     - Numbered format (`1. text\n2. text`)
     - JSON format (`[{"index": 1, "text": "..."}]`)
     - Plain text (line-by-line)
     - Persian/Arabic digit normalization (`۱۲۳` → `123`)
     - 80% valid line threshold
   - **Post-Translation Validation:**
     - Character range check for non-Latin scripts
     - Source comparison for Latin scripts
     - Technical term pattern detection (parenthetical English)
    - Automatic retry for incomplete batches (max 3 retries, no interactive blocking prompt)
     - **Guarantee:** No rendering until 100% translation or user decline

5. **Resume Capability:**
   - **Mechanism:** Ingests partial SRT files to recover existing translations
   - **Smart Mapping:** Time-based alignment (prevents line count desync)
   - **Use Case:** Continue interrupted translation jobs with `-c/--continue` flag
   - **Cost Savings:** Avoids re-translating already completed batch segments

6. **Technical Term Preservation:**
   - **Pattern:** Maintains English terms in parentheses (e.g., "هوش مصنوعی عمومی (AGI)")
   - **Scope:** All 32 languages (configurable per language)
   - **Mechanism:** Prompt engineering + validation regex

7. **Video Rendering (Smart Bitrate System):**
   - **Resolution Detection:** ffprobe extracts width × height
   - **Adaptive Mapping:**
     ```
     ≤480p  (≤500K pixels):  1.5 Mbps
     ≤720p  (≤1M pixels):    2.5 Mbps
     ≤1080p (≤2.5M pixels):  4.0 Mbps
     4K+    (>2.5M pixels):  8.0 Mbps
     ```
   - **Hardware Acceleration:**
     - **Apple Silicon:** `h264_videotoolbox` with bitrate targeting
     - **Fallback:** `libx264 -crf 23 -preset medium` (quality-based)
   - **Audio:** `-c:a copy` (lossless passthrough)
   - **Font Injection:** Explicit `fontsdir` for sandboxed FFmpeg environments
   - **File Size:** Optimized for minimal increase (typically 1.5-2x original)

8. **ASS Styling (Advanced SubStation Alpha):**
   - **Bilingual Layout:**
     - **Primary:** Bottom, white, bold, 24px
     - **Secondary:** Top, gray, 18px (e.g., English commentary over Persian)
    - **RTL Support:** Proper alignment and punctuation fixing for Arabic/Persian/Urdu/Hebrew via `fix_persian_text_fn` (applied even to manual SRT imports).
    - **Font Selection:** `Vazirmatn` (Persian), `Noto Sans` (Fallback).
   - **Resolution Scaling:** `font_size = (height / 1080) * 25`

9. **Document Export (`--save` flag):**
   - **Module:** `lib/python/subtitle/exporter.py`
   - **Formats:** `txt` (plain text), `md` (Markdown), `html` (styled, RTL/LTR, dark mode), `pdf` (via `amir pdf` Puppeteer engine)
   - **Usage:** `--save txt pdf` → generates `video_en.txt`, `video_fa.txt`, `video_en.pdf`, `video_fa.pdf`
   - **Overwrite Protection:** Interactive confirmation before overwriting existing files
   - **Output Location:** Same directory as input file

#### Workflow Example
```bash
# Full pipeline: Transcribe + Translate + Render
amir subtitle video.mp4 --sub en fa

# Export as document (no video rendering)
amir subtitle video.mp4 --sub en fa --save txt md --no-render

# Export multiple formats
amir subtitle video.mp4 --sub en fa --save txt pdf html

# Resume interrupted translation
amir subtitle video.mp4 --sub en fa -rc

# Multiple languages
amir subtitle video.mp4 --sub en fa ar es
```

#### Technical Implementation Details
- **File:** `lib/python/subtitle/processor.py` (~4400 lines)
- **Class:** `SubtitleProcessor`
- **Key Methods:**
  - `run_workflow(post_langs=None)`: Orchestrates full pipeline; `post_langs` limits which language posts are generated
  - `generate_posts(original_base, source_lang, result, platforms, post_langs=None)`: Generates social media posts; default `post_langs=None` → FA only
  - `_get_post_prompt(platform, title, srt_lang_name, full_text, ..., source_lang='')`: Builds analytical/factual LLM prompt per platform + language
  - `_telegram_sections_complete(text) -> (bool, list)`: Validates 8 required post sections (📽️ 🔴 🚨 ✨ 📌 ⏱️ 5×🔹 #)
  - `_sanitize_post(text, platform)`: Strips markdown, enforces 1024-char Telegram hard cap
  - `_srt_duration_str(entries, lang='fa')`: Returns video duration formatted as Persian-Indic numerals+words for `fa`, Latin numerals+English for all other langs
  - `_to_persian_digits(value)`: Converts `0-9` → `۰-۹`
  - `_parse_translated_batch_output()`: Robust multi-format parser
  - `translate_with_deepseek()`: Batch translation with retry logic
  - `create_ass_with_font()`: ASS generation with bilingual support
  - `_ingest_partial_srt()`: Resume translation recovery

### `trend` / `research` (Research Toolkit Bridge)

**Purpose:** Surface trending content and drive idea generation from 6 platforms — YouTube, GitHub, arXiv, Reddit, ProductHunt, Indie Hackers — without leaving the terminal.

#### Architecture

`trend.sh` is a thin bridge that delegates all work to the [Research Toolkit](https://github.com/su6i/research-toolkit), a separate Python project with a full Multi-Agent RAG pipeline.

```
amir trend [keyword] [--options]
  │
  └─ lib/commands/trend.sh → run_trend()
       │
       ├─ finds $RESEARCH_TOOLKIT_DIR/.venv/bin/python
       └─ calls: python main.py query [args]
                   │
                   └─ research_toolkit pipeline:
                       ├─ SQLite (metadata, sort by metric)
                       ├─ ChromaDB + BM25 (hybrid search)
                       ├─ RRF fusion (Reciprocal Rank Fusion)
                       └─ cross-encoder reranker
```

**Why direct `.venv/bin/python` instead of `uv run`:**  
The `amir` entry script activates its own `.venv`. If `uv run` is called in a subprocess, it may inherit the wrong `VIRTUAL_ENV` environment variable and pick up amir-cli's packages instead of research_toolkit's. Calling the toolkit's Python binary directly avoids this conflict entirely.

#### Usage

```bash
# No keyword → global trending (most-viewed YouTube videos)
amir trend

# Search YouTube for a topic, sort by views (default)
amir trend "AI tools"

# Show 20 results
amir trend "machine learning" --limit 20

# Filter by language — Persian-language results only
amir trend "music" --lang fa

# Filter by region — trending in Iran
amir trend --region IR

# Combine: Persian-language music videos
amir trend "آهنگ" --lang fa --limit 15

# Sort by likes instead of views
amir trend "devops" --metric likes

# GitHub repos sorted by stars
amir trend "LLM agents" --source github --metric stars --limit 10

# Academic papers (arXiv), sorted by publication date
amir trend "transformer architecture" --source arxiv --metric published_at

# Reddit posts sorted by comments
amir trend "startup ideas" --source reddit --metric comments

# Semantic vector search (multilingual — works across languages)
amir trend "climate agriculture" --semantic

# Generate AI-powered ideas from collected data (calls the idea pipeline)
amir trend "fintech" --ideas --count 15

# amir research = alias for amir trend
amir research "open source AI"
```

#### All Options

| Option | Short | Values | Default | Description |
|--------|-------|--------|---------|-------------|
| `--source` | `-s` | `youtube` `github` `arxiv` `reddit` `producthunt` `indiehackers` | `youtube` | Platform to search |
| `--lang` | `-l` | `fa` `en` `de` `ar` `zh` `es` `fr` `ru` `ja` `ko` `tr` `pt` `hi` | any | Language filter (YouTube only) |
| `--region` | `-r` | `IR` `US` `GB` `DE` `FR` `JP` `KR` `AU` `CA` `IN` `TR` `SA` `AE` `BR` | global | Region for trending (YouTube only) |
| `--metric` | `-m` | `views` `likes` `stars` `citations` `comments` `published_at` | `views` | Sort results by this metric |
| `--limit` | `-n` | number | `10` | Number of results to show |
| `--semantic` | | flag | keyword | Use semantic vector search |
| `--ideas` | | flag | — | Generate AI ideas from collected data |
| `--count` | `-c` | number | `10` | Number of ideas (with `--ideas`) |

#### Autocomplete

All options and their values are registered in `completions/_amir`. Press Tab at any point:

```zsh
amir trend --source <Tab>   →  youtube   github   arxiv   reddit   producthunt   indiehackers
amir trend --lang   <Tab>   →  fa (فارسی)   en   de   ar   zh   es   ...
amir trend --region <Tab>   →  IR (Iran)   US   GB   DE   FR   ...
amir trend --metric <Tab>   →  views   likes   stars   citations   comments   published_at
amir trend --limit  <Tab>   →  5   10   20   50
```

#### Configuration

Set `RESEARCH_TOOLKIT_DIR` in your shell or `.env` if the toolkit lives elsewhere:

```bash
# In ~/.zshrc or ~/.bashrc
export RESEARCH_TOOLKIT_DIR=/path/to/research_toolkit

# Or in amir-cli/.env
RESEARCH_TOOLKIT_DIR=/path/to/research_toolkit
```

Default path: `$HOME/@-github/research_toolkit`

#### Data Flow

1. **No keyword given** → `--trending` flag is set automatically → calls YouTube's `chart=mostPopular` endpoint with optional `regionCode`
2. **Keyword given** → queries the local SQLite database first
3. **No data in DB** → auto-collects from the source API (no confirmation needed in non-interactive mode)
4. **`--semantic` flag** → bypasses SQLite, queries ChromaDB + BM25 hybrid pipeline with cross-encoder reranker
5. **`--ideas` flag** → calls `python main.py idea --keywords [keyword]` (Multi-Agent RAG synthesis pipeline)

### `llm-lists` (LLM Model Discovery)
**Purpose:** Fetch and export available models from AI providers for quick reference.

#### Supported Providers
1. **Gemini:** Google's latest models via `google-genai` SDK
2. **OpenAI:** GPT models via official SDK
3. **DeepSeek:** Chat/Coder models (OpenAI-compatible endpoint)
4. **Groq:** Ultra-fast inference models
5. **Anthropic:** Claude models (manually curated list)

#### Architecture
- **Implementation:** Hybrid Bash/Python (`lib/commands/llm-lists.sh`)
- **Python Script:** Dynamically generated with embedded code
- **Environment:** Uses `.env` for API keys
- **Execution:** Prefers virtual environment Python if available

#### Usage
```bash
# List models
amir llm-lists gemini
amir llm-lists deepseek

# Export formats
amir llm-lists openai -e md        # Markdown
amir llm-lists groq --export pdf   # PDF (requires pandoc)
```

#### Export Features
- **Markdown:** Timestamped code block format
- **PDF:** Converted via Pandoc with metadata
- **Naming:** `{provider}_models_YYYYMMDD.{ext}`

## ⚙️ Configuration & Storage

### Centralized Configuration System

Amir CLI implements a **global configuration system** via `~/.amir/config.yaml`. This allows users to customize default behaviors without modifying code.

#### Architecture

**`lib/config.sh`:**
- Provides `get_config <section> <key> <default>` function
- Uses `awk` for YAML parsing (no external dependencies)
- Auto-creates `config.yaml` with sensible defaults on first run
- Handles `~` expansion in file paths

**Integration Pattern:**
Each command sources `lib/config.sh` and reads defaults:
```bash
# Source Config
local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
local LIB_DIR="$(dirname "$SCRIPT_DIR")"
if [[ -f "$LIB_DIR/config.sh" ]]; then
    source "$LIB_DIR/config.sh"
else
    get_config() { echo "$3"; }  # Fallback
fi

# Read defaults
local quality=$(get_config "compress" "quality" "60")
```

**Supported Commands:**
- `pdf`: `radius`, `rotate`
- `compress`: `resolution`, `quality`
- `mp3`: `bitrate`
- `img`: `default_size`
- `qr`: `size`
- `pass`: `length`
- `weather`: `default_city`
- `todo`: `file`
- `short`: `provider`

### Storage Location
By default, Amir CLI stores all its data (logs, stats, config, temp files) in:
- **`~/.amir/`** (Hidden directory in your User Home)

This prevents home directory pollution. The structure is:
```text
~/.amir/
├── config.yaml        # User configuration
├── learning_data      # AI stats for video compression
├── todo_list.txt      # Todo items
├── chat_history.md    # AI chat logs
└── code_history.md    # Code generation logs
```

### Customizing the Location
You can change this location (e.g., if you want to rename the project or store data elsewhere) by setting the `AMIR_CONFIG_DIR` environment variable.

**Example (.bashrc / .zshrc):**
```bash
export AMIR_CONFIG_DIR="$HOME/.my_custom_tool_data"
```

The CLI automatically detects this variable and uses it instead of the default.

---

## Apply Tracker Architecture

> Full usage docs: [APPLY_TRACKER.md](APPLY_TRACKER.md) | [فارسی](fa/APPLY_TRACKER_FA.md)

### Design Principles

**Single entry, multi interfaces.** All three UIs (CLI, TUI, Web) read and write exclusively through `service.py`. The database layer (`db.py`) is never called directly from UI code. This means:
- Adding a new UI requires zero changes to business logic
- A bug fix in `service.py` fixes it for all three interfaces simultaneously

**Dual-write, SQLite-read.** Every status change writes to both SQLite and the JSON `tracking.json` files. JSON acts as a human-readable backup. All queries go to SQLite for speed and filtering power.

**Column migrations without downtime.** New schema columns are added via `ALTER TABLE ... ADD COLUMN` inside `get_db()` wrapped in try/except — the database upgrades itself on first open after a code update.

### Key Files

| File | Role |
|------|------|
| `db.py` | Schema, upsert with conflict resolution, country inference |
| `service.py` | `get_positions()`, `mark_sent()`, `mark_status()`, `get_stats()` |
| `service_cli.py` | Thin bash→service bridge: `reject`, `watch` |
| `web.py` | FastAPI routes + inline HTML/CSS/JS (no template engine) |
| `tui.py` | Textual `App` with `DataTable`, key bindings, filter bar |
| `gmail_sync.py` | OAuth2 flow, token persistence, Gmail API draft fetch + trash |
| `sync.py` | AMIR-SYNC format parser → `.md` + `tracking.json` + SQLite upsert |
| `generate_html.py` | HTML tracker regeneration after every sync |

### SQLite Upsert Logic

On conflict (re-sync of existing position), the `ON CONFLICT DO UPDATE` clause preserves manually-set fields:
- `status` is only overwritten if the incoming value is not `'found'` — a re-sync never reverts a sent/replied position to found
- `sent_date`, `reply_date`, `reply_type` use `COALESCE(existing, incoming)` — once set manually, never overwritten

### Gmail OAuth2 Flow (Web UI)

```
User clicks "Connect Gmail"
  → GET /auth/gmail
  → gmail_sync.start_auth_flow(callback_url) → stores Flow in module var
  → redirect to Google OAuth consent screen
  → User grants permission
  → Google redirects to GET /auth/gmail/callback?code=...
  → gmail_sync.complete_auth_flow(code) → saves token to ~/.amir/gmail_token.json
  → redirect to /phd with success flash message

User clicks "Sync Gmail"
  → POST /api/sync-gmail
  → gmail_sync.fetch_and_process(BASE_DIR)
     ├─ load token, refresh if expired
     ├─ Gmail API: list drafts with query "AMIR-SYNC"
     ├─ fetch each draft body (base64url decode)
     ├─ sync.parse_sync_content() + sync.apply_positions()
     ├─ Gmail API: delete processed drafts
     └─ generate_html.regenerate_all() for both PhD and Job
  → redirect to /phd?msg=...
```

### Sort System

`service.py` defines `_ORDER` as a dict of `(asc_sql, desc_sql)` tuples per sort key. The `_order(sort_by, asc)` function selects the correct SQL fragment. This is passed directly to `db.query(order_by=...)` — no Python-side sorting occurs.

```python
_ORDER = {
    "deadline":  ("... deadline ASC", "... deadline DESC"),
    "fit":       ("fit_score ASC NULLS LAST", "fit_score DESC NULLS LAST"),
    "newest":    ("added_date DESC, id ASC", "added_date ASC, id DESC"),
    ...
}
```

The `id` tiebreaker in `newest` ensures consistent ordering even when multiple positions share the same `added_date`.
