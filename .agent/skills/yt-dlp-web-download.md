---
name: yt-dlp-web-download
description: yt-dlp Web Video Download Technical Encyclopedia: Cloudflare bypass, smart stream selection, bitrate-aware audio extraction, and subtitle pipeline integration.
---

# Skill: yt-dlp Web Video Download (Technical Encyclopedia)

[Back to README](../../README.md)

Comprehensive technical protocols for downloading video and audio from 1000+ websites using `yt-dlp`, bypassing Cloudflare bot detection, selecting optimal streams, and integrating with a local ffmpeg conversion pipeline.

---

## 1. Cloudflare Bot Detection Bypass

### 1.1 Problem Context
Sites like `tuckercarlson.com` serve video through **CloudflareStream** and protect HTML pages with **Cloudflare's anti-bot challenge (HTTP 403)**. A plain `yt-dlp` invocation fails with:
```
ERROR: [generic] Got HTTP Error 403 caused by Cloudflare anti-bot challenge
```

### 1.2 Solution: TLS Impersonation via `curl_cffi`
yt-dlp supports TLS fingerprint impersonation (mimicking a real browser's TLS handshake) via the `curl_cffi` dependency.

**Installation:**
```bash
# Must install in the SAME Python environment that yt-dlp uses
/opt/homebrew/bin/python3.14 -m pip install curl_cffi --break-system-packages
```

**Usage:**
```bash
yt-dlp --extractor-args "generic:impersonate" <url>
```

### 1.3 Paywall Bypass via Browser Cookies
For authenticated content (subscriptions, paywalled videos), pass the logged-in browser's cookies:
```bash
# From Chrome (recommended — most reliable on macOS)
yt-dlp --cookies-from-browser chrome --extractor-args "generic:impersonate" <url>

# From a Netscape-format cookies.txt file (server/CI use)
yt-dlp --cookies /path/to/cookies.txt --extractor-args "generic:impersonate" <url>
```

**Gotchas:**
- Safari cookies require Full Disk Access permission; use Chrome instead.
- `curl_cffi` must be installed in yt-dlp's Python env, not the project's venv.

---

## 2. Smart Stream Selection (Bitrate-Aware)

### 2.1 Problem Context
YouTube and similar platforms expose multiple audio-only streams at different bitrates. Downloading a high-bitrate stream and then re-encoding to a lower one wastes bandwidth. The goal is to download the stream **closest to the target bitrate** and never re-encode upward (upscale = quality loss without benefit).

### 2.2 Solution: Metadata-First Download Pattern
```bash
# Step 1: Fetch metadata only (no download, no bandwidth waste)
JSON=$(yt-dlp -j "$URL" 2>/dev/null)

# Step 2: Select stream with Python (write to temp file — avoid heredoc+pipe conflict in zsh)
cat > /tmp/amir_ytsel.py << 'PYEOF'
import json, sys

data   = json.loads(sys.argv[1])
target = int(sys.argv[2])
title  = data.get('title', 'audio').replace('/', '_')

formats = data.get('formats', [])
audio = [f for f in formats
         if f.get('vcodec', 'none') == 'none'
         and f.get('acodec', 'none') not in ('none', None)
         and f.get('abr')]

def score(f):
    diff = abs(f['abr'] - target)
    fmt_bonus = 0 if f.get('ext', '') in ('m4a', 'aac') else 1  # prefer m4a
    return (diff, fmt_bonus)

best       = min(audio, key=score)
actual_abr = int(best.get('abr', 0))
encode_abr = min(actual_abr, target)   # NEVER upscale

print(f"{best['format_id']}|{actual_abr}|{encode_abr}|{best.get('ext','m4a')}|{title}")
PYEOF

SELECTION=$(python3 /tmp/amir_ytsel.py "$JSON" 128)
FMT_ID=$(echo "$SELECTION" | cut -d'|' -f1)

# Step 3: Download only the selected stream
yt-dlp -f "$FMT_ID" -o "%(title)s.%(ext)s" "$URL"

# Step 4: Local conversion with ffmpeg (full control over output)
ffmpeg -hide_banner -loglevel error -y -i "source.m4a" -vn -c:a libmp3lame -b:a 128k "output_128kbps.mp3"
```

### 2.3 Scoring Logic
- **Primary key:** `abs(abr - target)` — closest bitrate wins
- **Secondary key:** `ext in ('m4a', 'aac')` gets priority (wider device compatibility vs. opus/webm)
- **Anti-upscale rule:** `encode_abr = min(actual_abr, target)` — if selected stream is 48kbps and target is 128kbps, encode at 48kbps

### 2.4 Gotcha: heredoc + pipe conflict in Zsh
In zsh, a heredoc assigned via `$(... << 'EOF')` redirects stdin to the heredoc, **not** to the piped command. This causes Python to receive `null` (from yt-dlp JSON) instead of a string, producing:
```
NameError: name 'null' is not defined
```
**Fix:** Write Python code to a temp file and pass the JSON as `sys.argv[1]`:
```bash
# WRONG (zsh conflict):
result=$(echo "$JSON" | python3 - arg << 'EOF' ... EOF)

# CORRECT (pass as argument):
cat > /tmp/script.py << 'EOF' ... EOF
result=$(python3 /tmp/script.py "$JSON" "$TARGET")
rm /tmp/script.py
```

---

## 3. YouTube JS Challenge (EJS / deno Solver)

### 3.1 Problem Context
YouTube uses JS-based "n parameter" challenges to throttle bots. Since early 2026, yt-dlp requires an external JS runtime (deno) + a remote solver script (EJS) to pass these challenges:
```
WARNING: n challenge solving failed: Some formats may be missing.
```

### 3.2 Solution: `--remote-components`
```bash
# Recommended: download EJS solver from GitHub at runtime (requires internet access)
yt-dlp --remote-components "ejs:github" <youtube-url>

# Alternative: NPM (slower, needs npm installed)
yt-dlp --remote-components "ejs:npm" <youtube-url>
```
**Prerequisite:** deno must be installed (`brew install deno`).  
**Effect:** yt-dlp downloads the EJS solver script from yt-dlp's GitHub releases and uses deno to solve the challenge.  
**For non-YouTube sites** (CloudflareStream, Vimeo, etc.): this flag is ignored safely — no harm in always including it.

---

## 4. Capturing the Final Output Filepath (Without Swallowing Progress Bar)

### 4.1 Problem Context
After `yt-dlp` downloads and merges streams, the final filename may differ from the input template. Capturing the exact path is needed for downstream processing (subtitle, compress, etc.).

**The trap:** `VIDEO_FILE=$(yt-dlp ... 2>/dev/null)` captures stdout but silences stderr — this hides the progress bar, ETA, speed, and all error messages from the user.

### 4.2 Solution: Redirect stdout to a temp file
yt-dlp's `--print` output goes to **stdout** while the progress bar goes to **stderr**. Redirect stdout to a temp file so stderr (progress) still flows to the terminal:
```bash
local _PATHFILE
_PATHFILE=$(mktemp /tmp/amir_dl_path.XXXXXX)

yt-dlp \
    --print "after_move:filepath" \
    -o "$(pwd)/%(title)s.%(ext)s" \
    "$URL" > "$_PATHFILE"   # stdout → file; stderr → terminal (progress visible)

VIDEO_FILE=$(head -1 "$_PATHFILE" | tr -d '\r')
rm -f "$_PATHFILE"

# Resolve relative path (some yt-dlp versions omit leading dir)
if [[ -n "$VIDEO_FILE" && ! "$VIDEO_FILE" = /* ]]; then
    VIDEO_FILE="$(pwd)/${VIDEO_FILE}"
fi
```

### 4.3 Why absolute output template matters
With `-o "%(title)s.%(ext)s"` (relative), yt-dlp may print just the filename without path. `[[ -f "filename" ]]` then fails if the shell's working directory is not where the file landed.  
**Fix:** Always use `-o "$(pwd)/%(title)s.%(ext)s"` to force an absolute path in `--print` output.

---

## 5. Downloading Built-in Platform Subtitles

### 5.1 Pattern: Human subs preferred, auto-generated as fallback
```bash
yt-dlp \
    --skip-download \
    --write-subs \
    --write-auto-subs \
    --sub-langs "fa,fa-orig,en" \
    --convert-subs srt \
    -o "%(title)s.%(ext)s" \
    "$URL"
```
- `--write-subs`: downloads human-made subtitles (preferred)
- `--write-auto-subs`: downloads auto-generated subtitles **only if human subs are absent for that language**
- `--convert-subs srt`: converts vtt/ttml/etc. to SRT automatically
- `fa-orig`: sometimes YouTube uses this code for the original Persian track

### 5.3 HTTP 429 (Too Many Requests) on subtitle download
When downloading video + subtitles in sequence, YouTube may rate-limit the second request:
```
ERROR: Unable to download video subtitles for 'fa': HTTP Error 429: Too Many Requests
```
**Fix:** Add `--sleep-requests 2` (2 second delay between subtitle API calls):
```bash
yt-dlp --skip-download --write-subs --write-auto-subs \
    --sleep-requests 2 \
    --sub-langs "fa,fa-orig,en" --convert-subs srt "$URL"
```
**Note:** HTTP 429 on the *target language* subtitle (e.g., `fa`) does NOT block the pipeline. `amir video download --translate` will use the English SRT and translate it locally via LLM. The 429 error is expected and non-fatal when using `--translate`.

### 5.4 `en-orig` vs `en` subtitle files
- **`title.en-orig.srt`** — Auto-generated captions from YouTube's ASR on the original audio. Has word-level timestamps → large file size (700KB+). Useful as a base for translation.
- **`title.en.srt`** — Human-curated subtitles. Sentence-level timing, smaller file (150–200KB), better quality.

yt-dlp downloads both when `--write-subs` + `--write-auto-subs` are used together.

**Source SRT preference order in `amir video download --translate`:**
1. `title.en.srt` (human-curated, exact `en` match, not `-orig`) ← **preferred**
2. `title.en.srt` (any human-curated)
3. `title.en-orig.srt` (auto-generated)
4. First available `.srt` file (fallback)

### 5.5 `--translate` flag: Full Download + Translate + Burn Pipeline

`amir video download <url> --yt-subs --translate -t [src] <lang>` does the following in sequence:

```
1. yt-dlp download video → stdout redirected to temp file for filepath capture
2. yt-dlp --skip-download --write-subs --write-auto-subs → download platform subs
3. Select source SRT (prefer human-curated en.srt)
4. cp source.srt → title_en.srt  (triggers Whisper-skip in amir subtitle)
5. amir subtitle <video> -s en -t fa  →  LLM translation → 100% validation → burn
```

**Flag semantics:**
| Flag | Effect |
|------|--------|
| `--translate` | Sets `YT_TRANSLATE=true; YT_SUBS=true; DO_RENDER=true` |
| `--translate --no-render` | SRT output only, no burn |
| `--yt-subs` (alone) | Downloads platform SRT without any translation |
| `--yt-subs --render` | Downloads platform SRT and burns directly (no translation) |

**`-t` / `--target` parsing rules:**
```bash
# Two-value form: sets LANG_SRC + LANG
amir video download URL --translate -t en fa

# Single-value form: keeps default LANG_SRC=en, sets LANG only
amir video download URL --translate -t fa

# Guards against URL being consumed as language:
# If $3 matches ^https?:// OR length > 10 → treated as next arg, not language
```
**Same-lang guard:** If `LANG_SRC == LANG` after parsing, the command exits with:
```
ERROR: Source and target language are the same (en).
  Translate TO a language: --translate -t fa
  Specify src AND target:  --translate -t en fa
```

### 5.6 Shell URL escaping gotcha
t-dlp with an unquoted or incorrectly escaped YouTube URL causes the generic extractor to mis-parse it:
```bash
# WRONG — zsh interprets \? and \= producing a mangled URL
amir video download "https://www.youtube.com/watch\?v\=abc123"

# CORRECT — just put the URL in double quotes
amir video download "https://www.youtube.com/watch?v=abc123"
```
With the correct URL, yt-dlp uses the `[youtube]` extractor directly instead of falling back to `[generic]`.

---

## 6. Supported Sites

yt-dlp supports 1800+ extractors. Key sites tested:
| Site | Notes |
|------|-------|
| YouTube | Needs `--remote-components ejs:github` + deno for JS challenges |
| Aparat (آپارات) | Native extractor, no cookies needed |
| tuckercarlson.com | Requires `curl_cffi` + Chrome cookies; no built-in subtitles |
| CloudflareStream | Detected automatically via embed URL; manifests are m3u8/mpd only |
| Twitter/X | Cookies required for age-restricted content |
| Vimeo, Dailymotion | Native extractors |

---

## 7. Output Filename Standards
Per project rules, output filenames must include selected options as suffixes:
```bash
# Audio extraction with bitrate suffix
yt-dlp ... -o "%(title)s_${ENCODE_ABR}kbps.%(ext)s"

# Video download — keep original title, mp4 container
yt-dlp ... --merge-output-format mp4 -o "%(title)s.%(ext)s"
```

---

## 8. References
- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
- [yt-dlp Impersonation docs](https://github.com/yt-dlp/yt-dlp#impersonation)
- [curl_cffi PyPI](https://pypi.org/project/curl-cffi/)
- [yt-dlp output template variables](https://github.com/yt-dlp/yt-dlp#output-template)

---
*Created: 2026-02-24 — Last updated: 2026-02-25 — Added §5.5 translate+burn pipeline, §5.6 URL escaping, -t parsing rules, DO_RENDER=true default for --translate.*
