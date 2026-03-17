"""
Subtitle Exporter — Convert SRT files to clean document formats.
Strips timestamps and outputs:  TXT, MD, HTML, PDF.
PDF rendering delegates to `amir pdf` (Puppeteer engine).
"""

import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

# Language metadata for document headers and RTL detection
LANG_META = {
    "en": {"name": "English", "native": "English", "rtl": False, "font": "Inter"},
    "fa": {"name": "Persian", "native": "فارسی", "rtl": True, "font": "Vazirmatn"},
    "ar": {"name": "Arabic", "native": "العربية", "rtl": True, "font": "Vazirmatn"},
    "fr": {"name": "French", "native": "Français", "rtl": False, "font": "Inter"},
    "de": {"name": "German", "native": "Deutsch", "rtl": False, "font": "Inter"},
    "es": {"name": "Spanish", "native": "Español", "rtl": False, "font": "Inter"},
    "tr": {"name": "Turkish", "native": "Türkçe", "rtl": False, "font": "Inter"},
    "ru": {"name": "Russian", "native": "Русский", "rtl": False, "font": "Inter"},
    "zh": {"name": "Chinese", "native": "中文", "rtl": False, "font": "Inter"},
    "ja": {"name": "Japanese", "native": "日本語", "rtl": False, "font": "Inter"},
    "ko": {"name": "Korean", "native": "한국어", "rtl": False, "font": "Inter"},
    "hi": {"name": "Hindi", "native": "हिन्दी", "rtl": False, "font": "Inter"},
    "pt": {"name": "Portuguese", "native": "Português", "rtl": False, "font": "Inter"},
    "it": {"name": "Italian", "native": "Italiano", "rtl": False, "font": "Inter"},
    "nl": {"name": "Dutch", "native": "Nederlands", "rtl": False, "font": "Inter"},
    "uk": {"name": "Ukrainian", "native": "Українська", "rtl": False, "font": "Inter"},
}


def _get_lang_meta(lang: str) -> dict:
    """Return language metadata with safe defaults."""
    return LANG_META.get(lang, {"name": lang.upper(), "native": lang, "rtl": False, "font": "Inter"})


def _clean_subtitle_text(text: str) -> str:
    """Remove BiDi control marks and normalize subtitle text spacing."""
    # Remove invisible directional controls commonly injected in RTL pipelines.
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_srt_entries(srt_path: str) -> List[dict]:
    """Parse SRT blocks into timed text entries."""
    entries: List[dict] = []
    if not os.path.exists(srt_path):
        return entries

    with open(srt_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    content = content.lstrip('\ufeff')

    def _to_sec(ts: str) -> float:
        h, m, s_ms = ts.strip().split(':')
        s, ms = s_ms.split(',')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        start_sec = 0.0
        end_sec = 0.0
        text_lines = []
        for i, line in enumerate(lines):
            if i == 0 and re.match(r'^\d+$', line.strip()):
                continue
            if '-->' in line:
                m = re.match(
                    r'^(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})$',
                    line.strip(),
                )
                if m:
                    start_sec = _to_sec(m.group(1))
                    end_sec = _to_sec(m.group(2))
                continue
            text_lines.append(line.strip().replace('\\N', ' '))

        text = _clean_subtitle_text(' '.join(text_lines))
        if text:
            entries.append({'start': start_sec, 'end': end_sec, 'text': text})

    return entries


def srt_to_plain_text(srt_path: str) -> str:
    """Parse an SRT file and reconstruct readable sentence/paragraph text.

    This is intentionally different from subtitle timing granularity: we merge
    short fragments into full sentences for document readability.  Paragraphs
    are formed by grouping sentences until a word-count threshold is reached.
    """
    entries = _parse_srt_entries(srt_path)
    if not entries:
        return ""

    # Common abbreviations whose trailing '.' is NOT a sentence end.
    _ABBREVS = frozenset({
        'dr', 'mr', 'mrs', 'ms', 'prof', 'sr', 'jr', 'st', 'vs',
        'etc', 'approx', 'dept', 'gov', 'lt', 'gen', 'col',
    })
    sentence_end_re = re.compile(r'[.!?\u061f\u3002\uff01\uff1f]+["\'\u00bb\u201d)]*$')

    def _is_real_end(text: str) -> bool:
        """Check if text ends with a real sentence terminator (not an abbreviation)."""
        if not sentence_end_re.search(text):
            return False
        # Check if the last word is an abbreviation
        last_word = text.rstrip('.!?\u061f\u3002\uff01\uff1f"\'\u00bb\u201d) ').split()[-1] if text.split() else ''
        stripped = last_word.rstrip('.')
        if stripped.lower() in _ABBREVS:
            return False
        if len(stripped) <= 2 and '.' in last_word:
            return False  # e.g. "U.S."
        return True

    clauses: List[str] = []
    buf: List[str] = []
    buf_words = 0
    buf_start = entries[0]['start']
    prev_end = entries[0]['start']

    for e in entries:
        t = e['text']
        if not t:
            continue

        # Large timing gap likely indicates a sentence/idea boundary.
        gap = max(0.0, e['start'] - prev_end)
        if gap >= 1.5 and buf:
            clauses.append(' '.join(buf).strip())
            buf = []
            buf_words = 0
            buf_start = e['start']

        buf.append(t)
        buf_words += len(t.split())

        elapsed = max(0.0, e['end'] - buf_start)
        ends_sentence = _is_real_end(t)

        # Flush conditions tuned for subtitle-derived fragments.
        if (ends_sentence and buf_words >= 5) or buf_words >= 30 or elapsed >= 12.0:
            clauses.append(' '.join(buf).strip())
            buf = []
            buf_words = 0

        prev_end = e['end']

    if buf:
        clauses.append(' '.join(buf).strip())

    # Build paragraphs from clauses to avoid one giant text wall.
    paragraphs: List[str] = []
    pbuf: List[str] = []
    p_words = 0
    for c in clauses:
        if not c:
            continue
        pbuf.append(c)
        p_words += len(c.split())
        if p_words >= 150:
            paragraphs.append(' '.join(pbuf).strip())
            pbuf = []
            p_words = 0
    if pbuf:
        paragraphs.append(' '.join(pbuf).strip())

    return '\n\n'.join(paragraphs)


def export_txt(text: str, output_path: str, lang: str) -> bool:
    """Export as plain text file."""
    meta = _get_lang_meta(lang)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    return os.path.exists(output_path)


def export_md(text: str, output_path: str, title: str, lang: str) -> bool:
    """Export as Markdown document with title and language header."""
    meta = _get_lang_meta(lang)
    
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    
    # Build Markdown
    md_lines = [
        f"# {title}",
        "",
        f"**Language:** {meta['name']} ({meta['native']})",
        "",
        "---",
        "",
    ]
    
    for p in paragraphs:
        md_lines.append(p)
        md_lines.append("")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    
    return os.path.exists(output_path)


def export_html(text: str, output_path: str, title: str, lang: str) -> bool:
    """Export as a beautifully styled HTML document with RTL/LTR auto-detection."""
    meta = _get_lang_meta(lang)
    direction = "rtl" if meta["rtl"] else "ltr"
    text_align = "right" if meta["rtl"] else "left"
    font = meta["font"]
    
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    
    body_html = '\n'.join(f'    <p>{p}</p>' for p in paragraphs if p.strip())
    
    html = f"""<!DOCTYPE html>
<html lang="{lang}" dir="{direction}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — {meta['name']}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Vazirmatn:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #fafafa;
            --text: #1a1a2e;
            --accent: #6366f1;
            --muted: #64748b;
            --border: #e2e8f0;
            --card: #ffffff;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #0f172a;
                --text: #e2e8f0;
                --accent: #818cf8;
                --muted: #94a3b8;
                --border: #334155;
                --card: #1e293b;
            }}
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: '{font}', 'Inter', 'Vazirmatn', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            direction: {direction};
            text-align: {text_align};
            line-height: 1.8;
            padding: 0;
        }}
        .container {{
            max-width: 720px;
            margin: 0 auto;
            padding: 3rem 2rem;
        }}
        header {{
            margin-bottom: 2.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 2px solid var(--accent);
        }}
        header h1 {{
            font-size: 1.75rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 0.5rem;
        }}
        header .meta {{
            font-size: 0.9rem;
            color: var(--muted);
        }}
        header .lang-badge {{
            display: inline-block;
            background: var(--accent);
            color: white;
            padding: 0.2rem 0.75rem;
            border-radius: 1rem;
            font-size: 0.8rem;
            font-weight: 600;
            margin-{text_align}: 0.5rem;
        }}
        article {{
            background: var(--card);
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        article p {{
            margin-bottom: 1.2rem;
            font-size: 1.05rem;
            line-height: 1.9;
        }}
        article p:last-child {{
            margin-bottom: 0;
        }}
        footer {{
            margin-top: 2rem;
            text-align: center;
            font-size: 0.8rem;
            color: var(--muted);
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>{title}</h1>
        <div class="meta">
            <span class="lang-badge">{meta['native']}</span>
            Transcript — {meta['name']}
        </div>
    </header>
    <article>
{body_html}
    </article>
    <footer>
        Generated by Amir CLI &mdash; Subtitle Export
    </footer>
</div>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return os.path.exists(output_path)


def export_pdf(md_path: str, output_path: str) -> tuple[bool, str]:
    """Export as PDF by delegating to `amir pdf` (Puppeteer engine).
    
    Creates a temporary MD file, calls `amir pdf`, then renames the output.
    """
    try:
        result = subprocess.run(
            ["amir", "pdf", md_path, "-o", output_path],
            capture_output=True, text=True, timeout=60
        )
        ok = result.returncode == 0 and os.path.exists(output_path)
        if ok:
            return True, ""
        reason = (result.stderr or result.stdout or "Unknown exporter error").strip()
        return False, reason
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)


def _confirm_overwrite(path: str) -> bool:
    """Ask user for overwrite confirmation. Returns True if OK to write."""
    if not os.path.exists(path):
        return True
    
    try:
        answer = input(f"⚠️  File exists: {os.path.basename(path)} — Overwrite? [y/N] ").strip().lower()
        return answer in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        return False


def export_subtitles(
    srt_paths: Dict[str, str],
    base_name: str,
    formats: List[str],
    output_dir: str,
    title: Optional[str] = None,
    logger=None
) -> List[str]:
    """Main export entry point.
    
    Args:
        srt_paths: Dict mapping lang code → SRT file path (e.g., {"en": "video_en.srt", "fa": "video_fa.srt"})
        base_name: Base filename without extension (e.g., "video")
        formats: List of output formats (e.g., ["txt", "pdf", "md", "html"])
        output_dir: Directory to save output files
        title: Optional document title (defaults to base_name)
        logger: Optional logger instance
    
    Returns:
        List of successfully created file paths.
    """
    if not title:
        title = base_name.replace('_', ' ').replace('-', ' ').title()
    
    created_files = []
    valid_formats = {'txt', 'md', 'html', 'pdf'}
    formats = [f.lower().strip('.') for f in formats]
    
    invalid = set(formats) - valid_formats
    if invalid:
        msg = f"⚠️  Unsupported format(s): {', '.join(invalid)}. Valid: {', '.join(sorted(valid_formats))}"
        if logger:
            logger.warning(msg)
        else:
            print(msg)
    
    formats = [f for f in formats if f in valid_formats]
    if not formats:
        return []
    
    for lang, srt_path in srt_paths.items():
        if not os.path.exists(srt_path):
            if logger:
                logger.warning(f"⚠️  SRT file not found for {lang}: {srt_path}")
            continue
        
        # Parse SRT to plain text
        text = srt_to_plain_text(srt_path)
        if not text.strip():
            if logger:
                logger.warning(f"⚠️  Empty transcript for {lang}")
            continue
        
        for fmt in formats:
            output_path = os.path.join(output_dir, f"{base_name}_{lang}.{fmt}")
            pdf_error = ""
            
            # Overwrite confirmation
            if not _confirm_overwrite(output_path):
                if logger:
                    logger.info(f"⏩ Skipped: {os.path.basename(output_path)}")
                continue
            
            success = False
            
            if fmt == 'txt':
                success = export_txt(text, output_path, lang)
            
            elif fmt == 'md':
                success = export_md(text, output_path, title, lang)
            
            elif fmt == 'html':
                success = export_html(text, output_path, title, lang)
            
            elif fmt == 'pdf':
                # PDF path: generate MD first → amir pdf
                tmp_md = os.path.join(output_dir, f".{base_name}_{lang}_tmp.md")
                export_md(text, tmp_md, title, lang)
                success, pdf_error = export_pdf(tmp_md, output_path)
                # Cleanup temp MD
                try:
                    os.remove(tmp_md)
                except OSError:
                    pass
            
            if success:
                created_files.append(output_path)
                if logger:
                    logger.info(f"✅ Exported: {os.path.basename(output_path)}")
                else:
                    print(f"✅ Exported: {output_path}")
            else:
                if logger:
                    details = f" ({pdf_error})" if pdf_error else ""
                    logger.warning(f"❌ Failed to export: {os.path.basename(output_path)}{details}")
                else:
                    print(f"❌ Failed: {output_path}")
    
    return created_files
