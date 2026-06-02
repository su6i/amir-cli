# Apply Tracker — راهنمای کامل

ابزار ردیابی درخواست‌های PhD و Job با رابط وب، TUI، و CLI.

---

## معماری کلی

```
amir apply <cmd>
  ├─ phd / job                → status.py (CLI table)
  ├─ tui                      → tui.py (Textual TUI)
  ├─ web [port]               → web.py (FastAPI at localhost:8765)
  └─ stats                    → stats_cli.py (bar charts)

lib/python/apply_tracker/
  ├─ db.py          SQLite CRUD — source of truth
  ├─ service.py     Business logic — یک entry point برای همه UI‌ها
  ├─ web.py         FastAPI web interface
  ├─ tui.py         Textual TUI
  ├─ gmail_sync.py  Gmail OAuth2 + AMIR-SYNC processing
  ├─ status.py      CLI table output
  ├─ tracker.py     tracking.json CRUD + parser
  ├─ sync.py        AMIR-SYNC draft parser + position creator
  ├─ generate_html.py  HTML tracker auto-generation
  └─ stats_cli.py   Terminal bar charts
```

**Data flow:** Write → SQLite + JSON (dual-write). Read → SQLite only (service.py).

---

## دستورات

```bash
amir apply                  # sync + help
amir apply phd              # لیست موارد pending (not sent)
amir apply phd sent         # لیست ارسال‌شده‌ها
amir apply phd show <id>    # جزئیات یک موقعیت
amir apply phd draft <id>   # ساخت draft ایمیل با DeepSeek
amir apply phd sent <id>    # علامت‌گذاری به عنوان ارسال‌شده
amir apply job              # همانند phd برای کار
amir apply tui              # رابط ترمینال (arrow keys)
amir apply web [port]       # رابط وب (پیش‌فرض 8765)
amir apply stats            # آمار بار chart ترمینال
amir apply sync             # sync از sync_queue.txt
```

### فیلتر و مرتب‌سازی (CLI)

```bash
amir apply phd --sort fit           # بر اساس fit score
amir apply phd --sort deadline      # بر اساس deadline
amir apply phd --country France     # فقط فرانسه
amir apply phd --min-fit 7          # حداقل fit 7
amir apply phd sent                 # فقط sent
```

---

## ساختار دایرکتوری داده

```
$HOME/@-Amir/Apply/2026-2027/
├── PhD-Search/
│   ├── found/
│   │   ├── ai_general/
│   │   │   ├── tracking.json       ← source of truth (JSON backup)
│   │   │   └── <position-id>.md    ← جزئیات موقعیت
│   │   └── ai_finance/
│   ├── applied/
│   │   └── <position-id>/
│   │       ├── email_draft.md
│   │       ├── CV.pdf
│   │       └── LettreMotivation.pdf
│   └── suivi_candidatures_PhD.html ← HTML tracker (auto-generated)
├── Job-Search/
│   └── ... (همانند PhD)
├── apply_tracker.db            ← SQLite database
└── sync_queue.txt              ← ورودی sync (موقت)
```

---

## رابط وب (FastAPI)

```bash
amir apply web          # شروع روی port 8765
amir apply web 9000     # port دلخواه
```

باز می‌شود: `http://localhost:8765`

### صفحات

| صفحه | توضیح |
|------|-------|
| `/phd` | لیست موقعیت‌های PhD با فیلتر/مرتب‌سازی |
| `/job` | لیست موقعیت‌های Job |
| `/replied` | کارت‌های پاسخ‌های دریافتی |
| `/stats` | آمار بر اساس status و country |

### دکمه‌های جدول

- **Open** — باز کردن لینک آگهی
- **Mark sent** — علامت‌گذاری به عنوان ارسال‌شده
- **🔄 Sync Gmail** — دریافت موقعیت‌های جدید از Gmail (نیاز به setup زیر)

---

## Gmail Sync — راه‌اندازی

### پیش‌نیاز: یک‌بار setup (۵ دقیقه)

#### مرحله ۱ — فعال‌سازی Gmail API

1. برو به [console.cloud.google.com](https://console.cloud.google.com)
2. پروژه مناسب را انتخاب کن (یا New Project بساز)
3. منوی چپ: **APIs & Services → Library**
4. جستجو: `Gmail API` → کلیک → **Enable**

#### مرحله ۲ — ساخت OAuth Credentials

1. منوی چپ: **APIs & Services → Credentials**
2. بالای صفحه: **+ CREATE CREDENTIALS → OAuth client ID**
3. اگر "Configure consent screen" خواست:
   - **External** انتخاب کن
   - App name: هر چیزی (مثلاً `amir-tracker`)
   - User support email: ایمیل خودت
   - **Save and Continue** × 3 بار تا برگردی به Dashboard
4. دوباره: **+ CREATE CREDENTIALS → OAuth client ID**
5. گزینه **"Which API are you using?"** نمایش می‌دهد:
   - What data will you be accessing? → **User data** انتخاب کن → **Next**
6. در صفحه بعد:
   - Application type: **Desktop app**
   - Name: `amir-apply-tracker`
7. **CREATE** → **Download JSON**

#### مرحله ۳ — ذخیره فایل

```bash
mv ~/Downloads/client_secret_*.json ~/.amir/gmail_credentials.json
```

#### مرحله ۴ — اتصال (یک‌بار)

```bash
amir apply web
```

در مرورگر:
1. دکمه **🔑 Connect Gmail** در header کلیک کن
2. به Google هدایت می‌شوی → حساب Google خود را انتخاب کن
3. مجوز دسترسی به Gmail بده
4. به Apply Tracker برمی‌گردی با پیام تأیید
5. از این به بعد دکمه **🔄 Sync Gmail** فعال است

### نحوه کار Sync

1. در Gmail یک draft با محتوای `[AMIR-SYNC]` بساز (با Claude Code)
2. در web UI روی **🔄 Sync Gmail** کلیک کن
3. سیستم:
   - Draft‌های AMIR-SYNC را پیدا می‌کند
   - موقعیت‌های جدید را parse می‌کند
   - فایل‌های `.md` و `tracking.json` می‌سازد
   - SQLite را به‌روز می‌کند
   - Draft‌ها را به Trash منتقل می‌کند
   - HTML tracker را regenerate می‌کند
4. نتیجه در header صفحه نمایش داده می‌شود

### فرمت AMIR-SYNC draft

```
TRACK: ai_general
ID: univ_paris_ml_2026
TITLE: PhD in Machine Learning
INSTITUTION: Université Paris-Saclay
LOCATION: Orsay, France
DEADLINE: 30/06/2026
LINK: https://...
FIT: 9/10
CONTACT: prof.name@univ.fr
SOURCE: adum

---

TRACK: ai_ml
ID: company_ml_engineer
TITLE: ML Engineer
...
```

هر موقعیت با `---` جدا می‌شود.

### فایل‌های ذخیره‌شده OAuth

| فایل | محتوا |
|------|-------|
| `~/.amir/gmail_credentials.json` | OAuth client ID/secret (از Google Cloud) |
| `~/.amir/gmail_token.json` | Access/refresh token (auto-created بعد از اتصال) |

**امنیت:** هر دو فایل فقط در دستگاه محلی هستند و هرگز commit نمی‌شوند.

---

## TUI (Textual)

```bash
amir apply tui          # هر دو PhD و Job
amir apply tui phd      # فقط PhD
amir apply tui job      # فقط Job
```

### کلیدها

| کلید | عملکرد |
|------|--------|
| `↑ ↓` | navigation |
| `Tab` | جابجایی PhD ↔ Job |
| `s` | چرخش sort (deadline/fit/country/status/institution) |
| `/` | نمایش/پنهان‌کردن filter bar |
| `m` | علامت‌گذاری به عنوان ارسال‌شده |
| `o` | باز کردن URL در مرورگر |
| `r` | refresh |
| `q` | خروج |

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
  fit_score    REAL,                 -- parsed float for sorting
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

**Statuses:** `found → draft_ready → sent → replied / bounced / rejected / watching`

---

## service.py API (برای توسعه‌دهندگان)

```python
from apply_tracker.service import (
    get_positions,   # list[dict] — main query
    get_stats,       # {"phd": {...}, "job": {...}}
    get_countries,   # sorted list of countries
    mark_sent,       # dual-write sent status
    mark_status,     # dual-write any status
    SORT_CHOICES,    # ["deadline","fit","country","status","institution"]
)

# مثال
rows = get_positions(
    base_dir,
    kind="phd",
    track="ai_general",      # optional filter
    status="found",          # optional filter
    pending_only=True,       # exclude sent/replied/rejected
    country="France",        # optional filter
    min_fit=7.0,             # optional filter
    sort_by="deadline",      # see SORT_CHOICES
)
# هر row شامل days_left محاسبه‌شده است
```

---

## راه‌اندازی اولیه

```bash
# ساخت tracking.json از .md files موجود
amir apply phd init ai_general
amir apply phd init ai_finance
amir apply job init ai_ml

# یا پس از اولین sync خودکار ساخته می‌شود
amir apply sync
```
