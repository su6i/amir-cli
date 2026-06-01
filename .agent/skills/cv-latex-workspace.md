# CV Workspace — Agent Knowledge Base

## 1. Repo Layout (post-reorganization)

```
CV/
├── .agents/
│   ├── instructions/quality_guard.md   ← Persian char rules
│   └── skills/knowledge.md             ← THIS FILE
├── templates/
│   ├── lato/                           ← ACTIVE — compile from here
│   │   ├── lato_macros.tex             ← shared packages + macros
│   │   ├── personal_data.tex           ← name, email, phone, location
│   │   ├── personal_data.json          ← same data for job-applier (Python)
│   │   ├── CV_AI_Data_Lato.tex         ← EN · AI Engineer / Data Scientist
│   │   ├── CV_IT_Infra_Lato.tex        ← FR · Ingénieur Support IT & Réseaux
│   │   ├── CV_PhD_Lato.tex             ← EN · PhD applications
│   │   └── output/                     ← compiled PDFs (committed to git)
│   ├── classic/                        ← older standalone templates
│   └── experimental/                   ← AI-generated experiments (deepseek, gpt, gemini)
├── Applied/                            ← one subfolder per job application
├── cover_letters/                      ← LM templates (FR + EN)
└── recommendation_letter/
```

---

## 2. LaTeX Compile Workflow

**MUST compile from inside `templates/lato/`** so `\input{lato_macros}` and
`\input{personal_data}` resolve correctly.

**Easiest — use the root script:**
```bash
cd .../CV          # repo root
./compile.sh       # all 3 CVs
./compile.sh ai    # only CV_AI_Data_Lato
./compile.sh it    # only CV_IT_Infra_Lato
./compile.sh phd   # only CV_PhD_Lato
```

**Manual (if script unavailable):**
```bash
cd templates/lato
pdflatex -output-directory=/tmp -interaction=nonstopmode CV_AI_Data_Lato.tex
cp /tmp/CV_AI_Data_Lato.pdf ../../output/
```

---

## 3. Modular Template Architecture

### personal_data.tex  
Single source of truth — edit once, applies to all CVs:
- `\cvname`, `\cvemail`, `\cvphone`, `\cvlinkedin`, `\cvgithub`
- `\cvlocation` = your city/country, `\cvmobility` = mobility statement (EN)
- `\cvmobilityFR` = "Mobile en France" (FR override)

### lato_macros.tex  
All packages + macros. Defines:
- `\cvsection{Title}` — colored rule + firstsection logic (no \vfill before Profil)
- `\headerrow{Left}{Right}` — flush date to right
- `\cvheader{Job Title}` — full contact block using personal_data vars
- `\sectionspace` = `\vfill` — distributes whitespace evenly between sections
- `\itemspace` = `\vspace{0.2em}` — between items inside a section (override per CV)

### Adding a new template:
```latex
\documentclass[11pt,a4paper]{article}
\input{lato_macros}
\input{personal_data}
% Optional overrides:
\renewcommand{\itemspace}{\vspace{0.15em}}
\begin{document}
\cvheader{Job Title Here}
% ... sections ...
\end{document}
```

---

## 4. Spacing Tuning

| Variable | Default | IT_Infra | AI_Data |
|---|---|---|---|
| `\itemspace` | 0.2em | 0.15em | 0.25em |
| geometry margins | top/bot 0.3in, lr 0.4in | same | same |
| font size | 11pt | 11pt | 11pt |

**\vfill trick:** `\sectionspace = \vfill` distributes leftover vertical space equally
between all section boundaries → no big white gap at the bottom.

**First section gap fix:** `\iffirstsection` flag in `\cvsection` gives Profil only
`\vspace{0.25em}` instead of `\vfill`, so header↔profile gap is small.

**Overfull \hbox:** Add `\setlength{\emergencystretch}{3em}` in preamble.

**List top padding:** `\setlist{topsep=0pt, partopsep=0pt}` zeroes all list gaps.

**Hyphenation:** Avoid `Word\&` at end of tabular cell. If a French word like
"Déploiement" gets hyphenated badly → split into separate bullet or use `\mbox{...}`.

---

## 5. Content Facts

### Amir's Profile
- **Degrees:** Master Informatique Bac+5 (Montpellier 2025) + DU Big Data (2025-2026)
- **Master grades:** Réseaux Avancés 16.33/20 (1ᵉʳ/13) · Web Avancé 17.15/20 (2ᵉ/17) · Système 16.5/20
- **Languages:** French (Advanced) · English (Professional) · Persian (Native)
- **Location:** Grenoble · Mobile in France

### Key Experience
- **toHero (Stage Jan–Jun 2025):** +500% speed, -99% costs · 18K Excel rows + 1772 PDF pages · 476 multi-agent test scenarios
- **NIOC (2021–2024):** Python/SNMP automation · -70% manual interventions · Power BI dashboards 1500+ users
- **NIOC (2017–2019):** VOIP support · SolarWinds · -30% downtime
- **NIOC (2010–2013):** QA inspection TETRA network 78 sites

### Active Projects (2025)
- **Multi-Agent Financial Markets Analyser:** AutoML + DL + RL portfolio optimization · BGE-M3 embeddings + ChromaDB RAG
- **Su6i-Yar Telegram Bot:** Hetzner VPS · 8-layer LLM fallback (Gemini/DeepSeek/Grok) · fal.ai Flux Schnell · MiniMax 2.5 · Faster-Whisper · Fish Speech · GPT-SoVITS · amir-cli
- **Cisco Switch & IP Phone Manager:** v1 NIOC (70 switches, SNMP, -70% site visits) → v2 full-stack (FastAPI, Next.js, PostgreSQL/PostGIS, Docker, Telegram alerts)

### Certifications (2025)
- MCP: Build Rich-Context AI Apps with Anthropic
- Multi-Agent Systems — CrewAI
- Prompt Engineering

---

## 6. Quality Rules (from quality_guard.md)

- **NO Persian/Arabic characters** in FR/EN CVs (except Languages section mention)
- Run `src/utils/cv_verify.py` before final PDF
- Grep check: `perl -ne 'print if /[^\x00-\x7f]/' file.tex`

---

## 7. personal_data.json → Job Applier

`personal_data.json` mirrors `personal_data.tex`. Python job-applier should read this
file to auto-fill application forms. Do NOT duplicate values — always read from JSON.

---

## 8. latexmk Cache Bug

If pdflatex gives a cached error that won't go away:
```bash
latexmk -C CV_IT_Infra_Lato.tex  # clears .fdb_latexmk cache
```
