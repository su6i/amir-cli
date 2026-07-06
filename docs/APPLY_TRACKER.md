# Apply Tracker — Complete Guide

Track PhD and job applications with a SQLite backend, FastAPI web UI, Textual TUI, and Gmail sync.

> 🇮🇷 [نسخه فارسی](fa/APPLY_TRACKER_FA.md)

---

## Architecture

```
amir apply <cmd>
  ├─ phd / job              → status.py  (CLI table)
  ├─ tui [phd|job]          → tui.py     (Textual TUI)
  ├─ web [port]             → web.py     (FastAPI — localhost:8765)
  └─ stats                  → stats_cli.py (terminal bar charts)
```

The tracker code itself lives in **ApplyForge** (`src/apply_tracker/`), not
amir-cli — this repo only wraps it (`_tracker_py()` in `lib/commands/apply.sh`
shells out via `cd "$APPLYFORGE_DIR" && uv run python -m src.apply_tracker.<module>`,
same pattern as `amir apply <url>` forwarding to ApplyForge's `main.py apply`).
Moved in wo-applyforge-0007 (2026-07-06) because the tracker depends on
ApplyForge's own pipeline; keeping it in amir-cli duplicated that dependency.

```
ApplyForge/src/apply_tracker/
  ├─ db.py             SQLite CRUD — schema + migrations
  ├─ service.py        Business logic — single entry point for all UIs
  ├─ service_cli.py    Bash → service.py bridge (reject, watch)
  ├─ web.py            FastAPI web interface
  ├─ tui.py            Textual TUI
  ├─ gmail_sync.py     Gmail OAuth2 + AMIR-SYNC draft processing
  ├─ status.py         CLI table renderer
  ├─ tracker.py        tracking.json CRUD + .md file parser
  ├─ sync.py           AMIR-SYNC format parser + position creator
  ├─ generate_html.py  HTML tracker auto-generation (post-sync)
  └─ stats_cli.py      Terminal bar charts
```

**Data flow:** All writes go to SQLite **and** JSON (dual-write). All reads come from SQLite via `service.py` only — `db.py` is never called directly by UI layers.

---

## Commands

```bash
# ── Overview ──────────────────────────────────────────────────────
amir apply                    # urgent deadline alerts + help

# ── PhD ───────────────────────────────────────────────────────────
amir apply phd                # list pending positions (not sent), sorted by urgency
amir apply phd sent           # list sent applications
amir apply phd reject         # list rejected positions
amir apply phd reject <id>    # mark a position as rejected
amir apply phd show <id>      # show full details of one position
amir apply phd draft <id>     # generate email draft with DeepSeek AI
amir apply phd sent <id>      # mark as sent

# ── Job ───────────────────────────────────────────────────────────
amir apply job                # same as phd but for jobs
amir apply job reject <id>    # reject a job position

# ── UIs ───────────────────────────────────────────────────────────
amir apply tui [phd|job]      # Textual TUI
amir apply web [port]         # FastAPI web UI (default port 8765)
amir apply stats              # bar chart statistics

# ── Data ──────────────────────────────────────────────────────────
amir apply sync               # fetch AMIR-SYNC drafts from Gmail (direct OAuth)
```

### CLI Filters & Sort

```bash
amir apply phd --sort deadline      # nearest deadline first (default)
amir apply phd --sort fit           # highest fit score first
amir apply phd --sort newest        # most recently added first
amir apply phd --sort country       # alphabetical by country
amir apply phd --sort institution   # alphabetical by institution
amir apply phd --sort status        # grouped by status
amir apply phd --country France     # filter by country
amir apply phd --min-fit 7          # minimum fit score
```

---

## Web UI (FastAPI)

```bash
amir apply web          # start on port 8765
amir apply web 9000     # custom port
```

Open: `http://localhost:8765`

### Pages

| Page | Description |
|------|-------------|
| `/phd` | PhD positions with filter toolbar, bidirectional sort on all columns |
| `/job` | Job positions |
| `/replied` | Cards showing each supervisor/employer's reply |
| `/stats` | Status and country breakdown |

### Table Features

- **Column sort**: click any header to sort; click again to reverse direction
- **Sort options**: Institution, Deadline, Days left, Fit, Experience, Track, Country, Status, Added
- **Live filter**: type in the search box to filter rows instantly
- **Row click**: expands a detail panel with title, contact, notes, and action buttons
- **Action buttons** (in detail panel):
  - **Open** — open the job/PhD posting URL
  - **📂 Open folder** — reveal position folder in Finder (macOS)
  - **Mark sent** — record as submitted
  - **✗ Reject** — mark as rejected (removes from pending list)

### Sync Gmail Button

When Gmail is connected, the **🔄 Sync Gmail** button appears in the header. Clicking it:
1. Fetches Gmail drafts containing `TRACK:` content
2. Creates `.md` files + updates SQLite + JSON
3. Moves processed drafts to Trash
4. Regenerates HTML trackers

---

## Gmail Sync — Setup (one-time, ~5 minutes)

### Step 1 — Enable Gmail API

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Select or create a project
3. Left menu: **APIs & Services → Library**
4. Search `Gmail API` → **Enable**

### Step 2 — Create OAuth Credentials

1. Left menu: **APIs & Services → Credentials**
2. **+ CREATE CREDENTIALS → OAuth client ID**
3. If prompted for consent screen: choose **External**, fill app name + email, click **Save and Continue** × 3
4. Back to Credentials → **+ CREATE CREDENTIALS → OAuth client ID**
5. "What data will you be accessing?" → **User data** → **Next**
6. Application type: **Desktop app**
7. Name: `amir-apply-tracker` → **CREATE** → **Download JSON**

### Step 3 — Save the File

```bash
mv ~/Downloads/client_secret_*.json ~/.amir/gmail_credentials.json
```

### Step 4 — Connect (one-time browser auth)

1. Run `amir apply web`
2. Click **🔑 Connect Gmail** in the header
3. Google OAuth screen appears → grant access
4. Redirected back — **🔄 Sync Gmail** button is now active

### Step 5 — Add Test User (if you see "access_denied")

In Google Cloud Console → **Google Auth Platform → Audience → Test users** → add your Google account email.

### OAuth Files

| File | Contents |
|------|----------|
| `~/.amir/gmail_credentials.json` | OAuth client ID/secret (from Google Cloud) |
| `~/.amir/gmail_token.json` | Access/refresh token (auto-created after first auth) |

Both files are local only and never committed.

---

## AMIR-SYNC Draft Format

Create a Gmail draft with this structure. `amir apply sync` fetches it directly via Gmail OAuth, processes it, and trashes the draft automatically.

```
TRACK: ai_ml
ID: company_name_role
TITLE: ML Engineer
INSTITUTION: Company Name
LOCATION: Paris, France
DEADLINE: 30/06/2026
LINK: https://...
FIT: 8/10
EXPERIENCE: 3+ years
CONTACT: recruiter@company.com
SOURCE: linkedin

---

TRACK: phd_ai_general
ID: FR_univ_topic
TITLE: PhD in Machine Learning
...
```

Separate each position with `---`. Supported tracks: `ai_ml`, `devops`, `devops_alternance`, `polyvalent`, `phd_ai_general`, `phd_ai_finance`.

**Experience field** is automatically parsed and stored. Supported keywords in `.md` files: `Expérience`, `Experience`, `Années`, `Years`.

---

## TUI (Textual)

```bash
amir apply tui          # both PhD and Job
amir apply tui phd      # PhD only
amir apply tui job      # Job only
```

### Key Bindings

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate rows |
| `Tab` | Switch PhD ↔ Job |
| `s` | Cycle sort (deadline/fit/country/status/institution) |
| `/` | Show/hide filter bar |
| `Esc` | Clear filter |
| `m` | Mark current row as sent |
| `x` | Reject current row |
| `o` | Open URL in browser |
| `r` | Refresh data |
| `q` | Quit |

---

## SQLite Schema

```sql
CREATE TABLE positions (
  id           TEXT NOT NULL,
  kind         TEXT NOT NULL,        -- 'phd' or 'job'
  track        TEXT,
  status       TEXT DEFAULT 'found',
  title        TEXT,
  institution  TEXT,
  country      TEXT,
  location     TEXT,
  deadline     TEXT,                 -- ISO: YYYY-MM-DD
  fit          TEXT,                 -- e.g. "8/10"
  fit_score    REAL,                 -- parsed float for numeric sort
  experience   TEXT,                 -- e.g. "3+ ans", "Junior", "Master requis"
  link         TEXT,
  contact      TEXT,
  lang         TEXT,
  source       TEXT,
  notes        TEXT,
  sent_date    TEXT,
  reply_date   TEXT,
  reply_type   TEXT,                 -- positive/negative/bounce/info
  added_date   TEXT,
  updated_date TEXT,
  PRIMARY KEY (id, kind)
);
```

**Status lifecycle:** `found → draft_ready → sent → replied / bounced / rejected / watching`

New columns are added automatically via migration in `get_db()` — no manual SQL needed.

---

## service.py API (for developers)

```python
# from ApplyForge's repo root:
from src.apply_tracker.service import (
    get_positions,   # list[dict] — main query with enriched days_left
    get_stats,       # {"phd": {...}, "job": {...}}
    get_countries,   # sorted list of countries in DB
    mark_sent,       # dual-write: SQLite + JSON
    mark_status,     # dual-write any status change
    SORT_CHOICES,    # ["deadline","fit","country","status","institution","newest"]
)

rows = get_positions(
    base_dir,
    kind="phd",           # "phd" or "job"
    track="ai_general",   # optional
    status="found",       # optional filter
    pending_only=True,    # exclude sent/replied/rejected
    country="France",     # optional
    min_fit=7.0,          # optional
    sort_by="deadline",   # see SORT_CHOICES
    asc=True,             # True = ascending, False = descending
)
# each row has a computed "days_left" field added by _enrich()
```

---

## Data Directory Structure

```
$HOME/@-Amir/Apply/2026-2027/
├── PhD-Search/
│   ├── found/
│   │   ├── ai_general/
│   │   │   ├── tracking.json          ← JSON backup (dual-write)
│   │   │   └── <position-id>.md       ← position details
│   │   └── ai_finance/
│   ├── applied/
│   │   └── <position-id>/
│   │       ├── email_draft.md
│   │       ├── CV.pdf
│   │       └── LettreMotivation.pdf
│   └── suivi_candidatures_PhD.html    ← auto-generated HTML tracker
├── Job-Search/
│   └── ... (same structure)
└── apply_tracker.db                   ← SQLite (source of truth)
```

---

## Initial Setup

```bash
# build tracking.json from existing .md files
amir apply phd init ai_general
amir apply phd init ai_finance
amir apply job init ai_ml

# or it's built automatically on first sync
amir apply sync
```
