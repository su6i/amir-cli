#!/usr/bin/env python3
"""
amir-cli — Trilingual post renderer (WeasyPrint).

Generic engine for FR/EN/FA LinkedIn posts. Reads a folder's content + a
`post.yml` (post-specific cover/carousel data) and produces:
  guide.{fr,en,fa}.pdf  ·  guide.trilingue.pdf  ·  carrousel.linkedin.pdf

Usage:  render_post.py <folder> <fonts_dir>

The macOS RTL/Persian font handling here is non-obvious — see
.agent/constitution/skills/weasyprint-rtl-persian-pdf.md before changing it.
"""
import os, re, sys, tempfile
from pathlib import Path

FOLDER = Path(sys.argv[1]).resolve()
FONTS  = str(Path(sys.argv[2]).resolve())

# ── Controlled font environment (MUST be set before importing weasyprint) ─────
# Point fontconfig ONLY at the vendored fonts + the user's Liberation fonts, so
# macOS cannot reach junk fallbacks (Noto-Serif-Yezidi / Hiragino / Microsoft).
_fc = Path(tempfile.gettempdir()) / "amir-post-fonts.conf"
_fc.write_text(f'''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{FONTS}</dir>
  <dir>{Path.home() / "Library" / "Fonts"}</dir>
  <cachedir>{tempfile.gettempdir()}/amir-post-fc-cache</cachedir>
</fontconfig>''')
os.environ["FONTCONFIG_FILE"] = str(_fc)

import markdown
import yaml
from weasyprint import HTML

META = yaml.safe_load((FOLDER / "post.yml").read_text(encoding="utf-8"))
COVER    = META.get("cover", {})
CAROUSEL = META.get("carousel", {})
FOOTER   = META.get("footer", "")

# ════════════════════════════════════════════════════════════════════════════
# GUIDE THEME (A4 long-form) — proven CSS + macOS fixes + LTR links/signature
# ════════════════════════════════════════════════════════════════════════════
GUIDE_CSS = f"""
@font-face {{ font-family:'Vazir'; src:url(file://{FONTS}/Vazirmatn-Regular.ttf); font-weight:normal; }}
@font-face {{ font-family:'Vazir'; src:url(file://{FONTS}/Vazirmatn-Bold.ttf); font-weight:bold; }}
@font-face {{ font-family:'DejaVu Serif'; src:url(file://{FONTS}/DejaVuSerif.ttf); font-weight:normal; }}
@font-face {{ font-family:'DejaVu Serif'; src:url(file://{FONTS}/DejaVuSerif-Bold.ttf); font-weight:bold; }}
@font-face {{ font-family:'DejaVu Sans'; src:url(file://{FONTS}/DejaVuSans.ttf); font-weight:normal; }}
@font-face {{ font-family:'DejaVu Sans'; src:url(file://{FONTS}/DejaVuSans-Bold.ttf); font-weight:bold; }}

:root {{ --navy:#1b3a6b; --navy2:#2e5596; --line:#cbd6e6; }}

@page {{
  size: A4; margin: 20mm 18mm 22mm 18mm;
  @bottom-center {{ content: counter(page); color:#7a869a; font-family:'Liberation Sans'; font-size:9pt; }}
  @bottom-left  {{ content: "{FOOTER}"; color:#9aa7b8; font-family:'Liberation Sans'; font-size:7.5pt; }}
}}

html {{ font-size: 11pt; }}
body {{ font-family:'Liberation Serif','DejaVu Serif',serif; color:#1f2733; line-height:1.58; }}

/* each text block follows its own dominant script (FR annex LTR, Persian RTL) */
.rtl p, .rtl li, .rtl td, .rtl th, .rtl blockquote, .rtl h1, .rtl h2, .rtl h3, .rtl dt, .rtl dd {{ unicode-bidi: plaintext; }}
.rtl {{ direction: rtl; text-align: right; }}
/* Persian body: 'Liberation Serif' FIRST so embedded Latin (CESEDA, SMIC…) is
   serif like the FR/EN guides; Persian has no Liberation glyphs so it falls to
   'Vazir'. Safe because the restricted fontconfig has no junk Arabic fonts. */
.rtl body, .rtl p, .rtl li {{ font-family:'Liberation Serif','Vazir','DejaVu Serif',serif; }}

h1, h2, h3 {{ font-family:'Liberation Sans','DejaVu Sans',sans-serif; color:var(--navy); page-break-after: avoid; }}
/* Persian headings: fallback MUST be 'DejaVu Serif', NEVER 'Liberation Sans'
   (the latter makes macOS Pango drop the whole bold Persian title to junk). */
.rtl h1, .rtl h2, .rtl h3 {{ font-family:'Vazir','DejaVu Serif',serif; }}

h2 {{ font-size:15pt; border-left:5px solid var(--navy); padding:1px 0 1px 14px; margin:1.6em 0 .7em; }}
.rtl h2 {{ border-left:none; border-right:5px solid var(--navy); padding:1px 14px 1px 0; }}
h3 {{ font-size:11.8pt; color:var(--navy2); border-left:3px solid var(--navy2); padding-left:8px; margin:1.2em 0 .5em; }}
.rtl h3 {{ border-left:none; border-right:3px solid var(--navy2); padding-left:0; padding-right:8px; }}

p {{ margin:.5em 0; text-align:justify; }}
.rtl p, .rtl li {{ text-align:justify; }}
strong {{ color:#16243a; font-weight:bold; }}
a {{ color:#1d4ed8; text-decoration:underline; word-break:break-all; }}
/* Bare URLs (autolinked, class .urllink): own line, left-to-right, left-aligned
   even inside the RTL document. Named links (e.g. the signature) are untouched. */
.rtl a.urllink {{ display:block; direction:ltr; unicode-bidi:isolate; text-align:left; }}
/* Author signature line (starts with em dash): force LTR + left even in RTL. */
.rtl p.sig {{ direction:ltr; unicode-bidi:isolate; text-align:left; }}
/* « … » around a Latin phrase: isolate as an LTR run so the guillemets sit on
   the correct side inside RTL text (e.g. «pièce manquante»). */
.ltrq {{ direction:ltr; unicode-bidi:isolate; }}
/* Pure-Latin/French blocks inside the RTL doc (e.g. the French annex): align LTR/left,
   and flip the coloured heading bar to the left edge. */
.rtl .ltrblock {{ direction:ltr; text-align:left; }}
.rtl p.ltrblock, .rtl li.ltrblock {{ text-align:justify; }}   /* justify the French annex body */
.rtl h2.ltrblock {{ border-right:none; border-left:5px solid var(--navy); padding:1px 0 1px 14px; }}
.rtl h3.ltrblock {{ border-right:none; border-left:3px solid var(--navy2); padding-right:0; padding-left:8px; }}
ul, ol {{ margin:.4em 0 .7em; padding-left:1.4em; }}
.rtl ul, .rtl ol {{ padding-left:0; padding-right:1.4em; }}
li {{ margin:.25em 0; }}
hr {{ border:none; border-top:1px solid var(--line); margin:1.4em 0; }}

table {{ border-collapse:collapse; width:100%; margin:.8em 0; font-size:9.6pt; page-break-inside:avoid; break-before:avoid; }}
th {{ background:var(--navy); color:#fff; padding:6px 8px; text-align:left; font-family:'Vazir','DejaVu Sans',sans-serif; }}
.rtl th {{ text-align:right; }}
td {{ border:1px solid var(--line); padding:5px 8px; vertical-align:top; }}
tr:nth-child(even) td {{ background:#f4f7fb; }}

blockquote {{ margin:.9em 0; padding:9px 13px; border-radius:5px; border-left:4px solid #94a3b8; background:#f1f5f9; page-break-inside:avoid; }}
.rtl blockquote {{ border-left:none; border-right:4px solid #94a3b8; }}
blockquote p {{ margin:.25em 0; }}
blockquote.warn {{ border-color:#d97706; background:#fff7ed; }}
.rtl blockquote.warn {{ border-color:#d97706; }}
blockquote.tip  {{ border-color:#2563eb; background:#eff6ff; }}
blockquote.note {{ border-color:#64748b; background:#f1f5f9; font-style:italic; color:#3b4757; }}

.front {{ page-break-after: always; border-top:6px solid var(--navy); padding-top:14px; }}
.front h1 {{ font-size:25pt; line-height:1.2; margin:.1em 0 .15em; border-bottom:none; }}
.front h3 {{ font-size:13pt; color:#334155; border:none; padding:0; font-weight:normal; margin:.2em 0 1em; }}

.divider {{ page-break-before: always; text-align:center; padding-top:38%; }}
.divider .lang {{ font-family:'Vazir','DejaVu Serif',serif; font-weight:bold; font-size:30pt; color:var(--navy); }}
.divider .sub {{ color:#64748b; font-size:12pt; margin-top:8px; }}
.combined-cover {{ page-break-after: always; border-top:6px solid var(--navy); padding-top:20px; }}
.combined-cover h1 {{ font-size:24pt; color:var(--navy); }}
.combined-cover .sub {{ font-size:12.5pt; color:#334155; margin:.3em 0; }}
"""

URL_RE = re.compile(r'(?<![\(\[])(https?://[^\s)\]]+)')
EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF\U0000FE0F\U00002049\U0000203C]")

def preprocess(md):
    # autolink bare URLs and tag them so CSS can put them on their own LTR line
    return URL_RE.sub(r'[\1](\1){.urllink}', md)

def classify_blockquotes(html):
    def repl(m):
        inner = m.group(1)
        cls = 'warn' if '⚠️' in inner else 'tip' if '💡' in inner else 'note'
        return f'<blockquote class="{cls}">{inner}</blockquote>'
    return re.sub(r'<blockquote>(.*?)</blockquote>', repl, html, flags=re.S)

def mark_signature(html):
    # paragraphs that start with an em dash and contain a link = author signature
    def repl(m):
        body = m.group(1)
        plain = re.sub(r'<[^>]+>', '', body).lstrip()
        if plain.startswith('—') and '<a ' in body:
            return f'<p class="sig">{body}</p>'
        return m.group(0)
    return re.sub(r'<p>(.*?)</p>', repl, html, flags=re.S)

def strip_emoji(html):
    html = EMOJI.sub('', html)
    html = re.sub(r'  +', ' ', html)
    html = re.sub(r'(<(?:p|li|h[1-3]|strong|em|td|th)[^>]*>) +', r'\1', html)
    return html

def isolate_latin_guillemets(html):
    # « » around a *purely Latin* phrase get mis-placed in RTL; wrap it in an
    # isolated LTR run so the guillemets hug the phrase. Skip quotes that contain
    # any Persian/Arabic letter — those are RTL quotes and MUST stay RTL (wrapping
    # them would flip the whole Persian sentence to LTR and scramble it).
    def repl(m):
        inner = m.group(1)
        if re.search(r'[A-Za-zÀ-ÿ]', inner) and not re.search(r'[؀-ۿ]', inner):
            return f'<span class="ltrq">«{inner}»</span>'
        return m.group(0)
    return re.sub(r'«([^«»]*)»', repl, html)

def ltr_latin_blocks(html):
    # In an RTL doc, a block element whose text has NO Persian/Arabic letter is a
    # Latin/French block (e.g. the verbatim French annex, French article headings):
    # render it LTR + left-aligned. CSS scopes `.ltrblock` to `.rtl`, so LTR guides
    # are unaffected. Persian/mixed blocks keep their content (and stay RTL).
    def repl(m):
        tag, attrs, inner = m.group(1), m.group(2) or '', m.group(3)
        text = re.sub(r'<[^>]+>', '', inner)
        if not text.strip() or re.search(r'[؀-ۿ]', text):
            return m.group(0)
        if 'class="' in attrs:
            attrs = attrs.replace('class="', 'class="ltrblock ', 1)
        else:
            attrs += ' class="ltrblock"'
        return f'<{tag}{attrs}>{inner}</{tag}>'
    return re.sub(r'<(p|h1|h2|h3|li|blockquote)((?:\s[^>]*)?)>(.*?)</\1>', repl, html, flags=re.S)

def to_html(s):
    h = markdown.markdown(s, extensions=['tables', 'sane_lists', 'attr_list'])
    h = isolate_latin_guillemets(mark_signature(classify_blockquotes(h)))
    return strip_emoji(ltr_latin_blocks(h))

def md_to_parts(path):
    raw = preprocess(Path(path).read_text(encoding='utf-8'))
    parts = raw.split('\n---\n', 1)
    front = parts[0]
    body = parts[1] if len(parts) > 1 else ''
    return to_html(front), to_html(body)

def doc(lang_class, inner):
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<style>{GUIDE_CSS}</style></head><body class="{lang_class}">{inner}</body></html>')

def build_single(src, out, rtl=False):
    front, body = md_to_parts(src)
    inner = f'<div class="front">{front}</div><div class="body">{body}</div>'
    HTML(string=doc('rtl' if rtl else 'ltr', inner)).write_pdf(out)
    print("built", out)

# language order (rtl flag per language)
LANGS = [("fr", "Français", "Version française", False),
         ("en", "English",  "English version",   False),
         ("fa", "فارسی",    "نسخهٔ فارسی",        True)]

def build_trilingue():
    # combined trilingual PDF (reads the .md files directly — independent of the
    # individual guide PDFs, so it can be rebuilt on its own).
    present = [(code, name, sub, rtl) for code, name, sub, rtl in LANGS
               if (FOLDER / f"guide.{code}.md").exists()]
    if len(present) < 2:
        return
    c = COVER
    author = (f'— {c.get("author","")} '
              f'(<a href="{c.get("author_url","#")}" style="color:#64748b">{c.get("author_handle","")}</a>)')
    cover = (f'<div class="combined-cover"><h1>{c.get("title","")}</h1>'
             f'<div class="sub">{c.get("subtitle","")}</div>'
             f'<div class="sub"><strong>{c.get("edition","")}</strong></div>'
             f'<div class="sub">{c.get("date","")}</div>'
             f'<div class="sub" style="margin-top:1.5em;color:#64748b;">{author}</div></div>')
    sections = [cover]
    for code, name, sub, rtl in present:
        front, body = md_to_parts(str(FOLDER / f"guide.{code}.md"))
        cls = 'rtl' if rtl else 'ltr'
        sections.append(
            f'<div class="{cls}"><div class="divider"><div class="lang">{name}</div>'
            f'<div class="sub">{sub}</div></div>'
            f'<div class="front">{front}</div><div class="body">{body}</div></div>')
    out = FOLDER / "guide.trilingue.pdf"
    HTML(string=doc('ltr', ''.join(sections))).write_pdf(str(out))
    print("built", out)

def build_guides(targets=None):
    # targets: any of 'fr','en','fa','tri'. None → all guides + trilingue.
    want = set(targets) if targets else {"fr", "en", "fa", "tri"}
    built_guide = False
    for code, name, sub, rtl in LANGS:
        if code in want and (FOLDER / f"guide.{code}.md").exists():
            build_single(str(FOLDER / f"guide.{code}.md"),
                         str(FOLDER / f"guide.{code}.pdf"), rtl=rtl)
            built_guide = True
    # guide.trilingue.pdf is derived from the single-language .md files, so it must
    # never drift: rebuild it whenever ANY guide was rendered (or when asked via 'tri').
    if built_guide or "tri" in want:
        build_trilingue()

# ════════════════════════════════════════════════════════════════════════════
# CAROUSEL THEME (1080×1080 LinkedIn) — content from post.yml['carousel']
# ════════════════════════════════════════════════════════════════════════════
CAROUSEL_CSS = """
@page { size: 1080px 1080px; margin: 0; }
* { box-sizing: border-box; margin:0; padding:0; }
body { font-family:'Liberation Sans','DejaVu Sans',sans-serif; }
.slide { width:1080px; height:1080px; page-break-after:always; padding:84px 90px;
         display:flex; flex-direction:column; position:relative; }
.light { background:#ffffff; color:#1f2733; }
.dark  { background:#1b3a6b; color:#ffffff; }
.topbar { display:flex; justify-content:space-between; align-items:center;
          font-size:21px; color:#7c8aa0; letter-spacing:.3px; }
.dark .topbar { color:#9db4d6; }
.accent { width:64px; height:8px; background:#1b3a6b; border-radius:4px; margin:30px 0 26px; }
.eyebrow { font-size:23px; font-weight:bold; color:#2e5596; letter-spacing:1px; text-transform:uppercase; }
.title-fr { font-size:50px; line-height:1.12; font-weight:bold; color:#1b3a6b; margin-top:14px; }
.title-en { font-size:27px; line-height:1.25; color:#5b6b82; font-style:italic; margin-top:12px; }
ul { list-style:none; margin-top:34px; }
li { font-size:30px; line-height:1.36; color:#1f2733; margin:18px 0; padding-left:46px; position:relative; }
li:before { content:"\\2192"; position:absolute; left:0; color:#2e5596; font-weight:bold; }
.num { color:#b45309; font-weight:bold; }
.gist { margin-top:auto; font-size:23px; line-height:1.4; color:#5b6b82; border-top:2px solid #e2e8f0; padding-top:20px; }
.gist b { color:#2e5596; font-style:normal; }
.foot { position:absolute; bottom:40px; left:90px; right:90px; font-size:18px; color:#aeb9c8;
        display:flex; justify-content:space-between; }
.dark .foot { color:#7f99c4; }
.big { font-size:70px; line-height:1.1; font-weight:bold; }
.big-en { font-size:33px; color:#cfe0f7; margin-top:18px; font-style:italic; }
.lead { font-size:30px; color:#e8eefa; margin-top:40px; line-height:1.4; }
.swipe { margin-top:auto; font-size:26px; color:#cfe0f7; }
.center { justify-content:center; }
.cta-h { font-size:60px; font-weight:bold; line-height:1.12; }
.cta-sub { font-size:30px; color:#cfe0f7; margin-top:26px; line-height:1.45; }
.pill { display:inline-block; background:#ffffff; color:#1b3a6b; font-weight:bold;
        font-size:25px; padding:10px 22px; border-radius:40px; margin:8px 10px 0 0; }
"""

def build_carousel():
    if not CAROUSEL:
        return
    cov   = CAROUSEL["cover"]
    items = CAROUSEL["slides"]
    cta   = CAROUSEL["cta"]
    topbar_txt = CAROUSEL["topbar"]
    foot_cover = CAROUSEL.get("foot_cover", "")
    foot_slide = CAROUSEL.get("foot_slide", "")
    n_total = len(items) + 2

    def topbar(i):
        return (f"<div class='topbar'><span>{topbar_txt}</span>"
                f"<span>{i} / {n_total}</span></div>")

    cover = (f"<div class='slide dark'>{topbar(1)}"
             f"<div style='margin-top:120px'><div class='big'>{cov['fr']}</div>"
             f"<div class='big-en'>{cov['en']}</div><div class='lead'>{cov['lead']}</div></div>"
             f"<div class='swipe'>{cov['tag']}&nbsp;&nbsp;→</div>"
             f"<div class='foot'><span>{foot_cover}</span><span>{cov.get('sources','')}</span></div></div>")

    body = ""
    for i, s in enumerate(items):
        bullets = "".join(f"<li>{b}</li>" for b in s["bullets"])
        # content slides carry only the doc footer (no repeated author handle —
        # the cover and CTA slides already credit "Amir Shirali Pour · Su6iant")
        body += (f"<div class='slide light'>{topbar(i+2)}<div class='accent'></div>"
                 f"<div class='eyebrow'>{s.get('eyebrow', f'Étape {i+1} / Step {i+1}')}</div>"
                 f"<div class='title-fr'>{s['fr']}</div><div class='title-en'>{s['en']}</div>"
                 f"<ul>{bullets}</ul><div class='gist'>{s['gist']}</div>"
                 f"<div class='foot'><span>{foot_slide}</span></div></div>")

    pills = "".join(f"<span class='pill'>{p}</span>" for p in cta["pills"])
    sub_html = f"<div class='cta-sub'>{cta['sub']}</div>" if cta.get("sub") else ""
    cta_html = (f"<div class='slide dark center'><div class='cta-h'>{cta['h']}</div>"
                f"{sub_html}<div style='margin-top:36px'>{pills}</div>"
                f"<div class='cta-sub' style='margin-top:40px'>{cta['link_label']}<br>"
                f"<b style='color:#ffffff'>{cta['link']}</b><br>"
                f"<span style='font-size:24px;color:#9db4d6'>{cta['link_sub']}</span></div>"
                f"<div class='cta-sub' style='margin-top:30px;font-size:26px'>{cta['action']}</div>"
                f"<div class='foot'><span>{foot_cover}</span><span>{cta.get('disclaimer','')}</span></div></div>")

    html = (f"<html><head><meta charset='utf-8'><style>{CAROUSEL_CSS}</style></head>"
            f"<body>{cover}{body}{cta_html}</body></html>")
    out = FOLDER / "carrousel.linkedin.pdf"
    HTML(string=html).write_pdf(str(out))
    print("built", out, "slides:", n_total)

if __name__ == "__main__":
    mode = sys.argv[3] if len(sys.argv) > 3 else "all"   # all | carousel | guide
    targets = [t for t in sys.argv[4:] if t]              # fr en fa tri (for mode "guide")
    if mode == "all":
        build_guides()
        build_carousel()
    elif mode == "carousel":
        build_carousel()
    elif mode in ("guide", "guides"):
        build_guides(targets or None)
    else:
        sys.exit(f"unknown mode: {mode}")
