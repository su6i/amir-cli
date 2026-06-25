# `amir pdf build` — Trilingual (FR/EN/FA) LinkedIn posts

Renders a whole post folder to publish-ready PDFs with **WeasyPrint**. This is
generic — it works for **any** post, not a specific one. The engine lives in
`lib/python/render_post.py`; fonts are vendored in `lib/fonts/`.

```bash
amir pdf linkedin-post <folder>                # whole post: guides + trilingue + carousel
amir pdf linkedin-post <folder> carousel       # carousel only
amir pdf linkedin-post <folder> guide fa       # one guide — trilingue auto-rebuilt
amir pdf linkedin-post <folder> guide fa en    # several guides at once (+ trilingue)
amir pdf linkedin-post <folder> guide tri      # rebuild ONLY the trilingue
amir pdf linkedin-post <folder> guide          # all guides + trilingue (no carousel)
```

Targets for `guide`: any of `fr en fa tri`. **`guide.trilingue.pdf` is derived from the
single-language `.md` files, so it is ALWAYS rebuilt alongside any guide** — you never
have to ask for it (and the two can't drift). `tri` on its own rebuilds just the
trilingue. Building only what changed avoids re-rendering the whole post each time.

## Inputs (in the post folder)
| File | Role |
|---|---|
| `guide.{fr,en,fa}.md` | long-form guide sources (the **verified source of truth**) |
| `post.yml` | post-specific render data: trilingual cover + carousel content + footer |

## Outputs (written to the same folder)
`guide.fr.pdf` · `guide.en.pdf` · `guide.fa.pdf` · `guide.trilingue.pdf` · `carrousel.linkedin.pdf`

The guide pipeline: `.md` → autolink bare URLs → `markdown` (tables, sane_lists,
attr_list) → classify `blockquote` (⚠️→warn / 💡→tip / else→note) → strip emoji →
front-matter cover split → A4 theme → WeasyPrint. The Persian guide renders RTL;
the French annex inside it stays LTR (per-block `unicode-bidi:plaintext`).

## `post.yml` schema
```yaml
footer: "Étrangers diplômés en France · 2026"      # page footer (bottom-left)
cover:                                              # guide.trilingue.pdf cover
  title: "..."
  subtitle: "..."
  edition: "Édition trilingue — Français · English · فارسی"
  date: "À jour au 19 juin 2026 · Sources : ..."
  author: "Amir Shirali Pour"
  author_url: "https://amirshirali.com"
  author_handle: "Su6iant"
carousel:                                           # carrousel.linkedin.pdf (1080×1080)
  topbar: "..."
  foot_cover: "..."          # footer on dark cover/cta slides
  foot_slide: "..."          # footer on light content slides
  cover:  {fr, en, lead, tag, sources}
  slides:                    # one entry per content slide
    - {fr, en, bullets: [...], gist, eyebrow?}   # bullets may contain <b>, <span class='num'>
  cta:    {h, sub, pills: [...], link_label, link, link_sub, action, handle, disclaimer}
```

## Fonts & the macOS gotcha (important)
Fonts are **vendored** in `lib/fonts/` (Vazirmatn + DejaVu) and loaded by
`@font-face`. `render_post.py` pins a **restricted `FONTCONFIG_FILE`** (only the
vendored fonts + `~/Library/Fonts`) *before* importing WeasyPrint, otherwise macOS
routes Persian to junk system fonts (Noto-Serif-Yezidi / Hiragino / Microsoft-Sans).
Also: never put `'Liberation Sans'` in a Persian font stack — it breaks Pango
shaping. Full background:
`.agent/constitution/skills/weasyprint-rtl-persian-pdf.md`.

Verify a build is clean (must print `0`):
```bash
pdffonts guide.fa.pdf | grep -icE "microsoft|syriac|yezidi|hiragino"
```

## Persian (Farsi) content rules (apply to every `*.fa.md`)
- Never the literal `<` / `>` in prose — write `کمتر از` / `بیشتر از`.
- No thousands separator in Persian numbers (`۱۸۶۷`, not `۱ ۸۶۷`).
- Author signature line starts with `—` and is auto-rendered LTR/left.
- Bare URLs are auto-placed on their own LTR/left line.
