# Apply Tracker — راهنمای کامل (فارسی)

ابزار ردیابی درخواست‌های PhD و شغلی با SQLite، رابط وب FastAPI، TUI ترمینال، و sync خودکار Gmail.

> 🇬🇧 [English version](../APPLY_TRACKER.md)

---

## معماری کلی

```
amir apply <cmd>
  ├─ phd / job              → status.py  (جدول CLI)
  ├─ tui [phd|job]          → tui.py     (Textual TUI)
  ├─ web [port]             → web.py     (FastAPI — localhost:8765)
  └─ stats                  → stats_cli.py (نمودار ترمینال)
```

خودِ کدِ tracker در **ApplyForge** است (`src/apply_tracker/`)، نه amir-cli —
این ریپو فقط wrap می‌کند (`_tracker_py()` در `lib/commands/apply.sh` با
`cd "$APPLYFORGE_DIR" && uv run python -m src.apply_tracker.<module>` صدا
می‌زند، دقیقاً مثل الگوی `amir apply <url>` که به `main.py apply` در
ApplyForge forward می‌شود). در wo-applyforge-0007 (2026-07-06) منتقل شد،
چون tracker به pipeline خودِ ApplyForge وابسته بود.

```
ApplyForge/src/apply_tracker/
  ├─ db.py             SQLite CRUD — schema + migration خودکار
  ├─ service.py        منطق کسب‌وکار — یک entry point برای همه UI‌ها
  ├─ service_cli.py    پل bash ↔ service.py (reject، watch)
  ├─ web.py            رابط وب FastAPI
  ├─ tui.py            TUI با Textual
  ├─ gmail_sync.py     OAuth2 Gmail + پردازش draft های AMIR-SYNC
  ├─ status.py         نمایش جدول CLI
  ├─ tracker.py        CRUD فایل tracking.json + parser فایل‌های .md
  ├─ sync.py           parser فرمت AMIR-SYNC + ساخت موقعیت‌ها
  ├─ generate_html.py  بازسازی خودکار HTML tracker بعد از sync
  └─ stats_cli.py      نمودار bar در ترمینال
```

**جریان داده:** نوشتن → SQLite + JSON (dual-write). خواندن → فقط SQLite از طریق service.py.

---

## دستورات

```bash
# ── کلی ───────────────────────────────────────────────────────────
amir apply                    # هشدار deadline های اضطراری + راهنما

# ── PhD ───────────────────────────────────────────────────────────
amir apply phd                # موارد pending (نفرستاده) به ترتیب اولویت
amir apply phd sent           # لیست ارسال‌شده‌ها
amir apply phd reject         # لیست ریجکت‌شده‌ها
amir apply phd reject <id>    # علامت‌گذاری به عنوان ریجکت
amir apply phd show <id>      # نمایش جزئیات کامل یک موقعیت
amir apply phd draft <id>     # ساخت draft ایمیل با DeepSeek AI
amir apply phd sent <id>      # علامت‌گذاری به عنوان ارسال‌شده

# ── Job ───────────────────────────────────────────────────────────
amir apply job                # مشابه phd برای موقعیت‌های شغلی
amir apply job reject <id>    # ریجکت کردن موقعیت شغلی

# ── رابط‌های کاربری ──────────────────────────────────────────────
amir apply tui [phd|job]      # TUI ترمینال
amir apply web [port]         # رابط وب (پیش‌فرض port 8765)
amir apply stats              # آمار bar chart

# ── داده ──────────────────────────────────────────────────────────
amir apply sync               # پردازش sync_queue.txt → ساخت موقعیت‌ها
```

### فیلتر و مرتب‌سازی (CLI)

```bash
amir apply phd --sort deadline      # نزدیک‌ترین deadline اول (پیش‌فرض)
amir apply phd --sort fit           # بالاترین fit score اول
amir apply phd --sort newest        # جدیدترین اضافه‌شده اول
amir apply phd --sort country       # الفبایی بر اساس کشور
amir apply phd --sort institution   # الفبایی بر اساس موسسه
amir apply phd --country France     # فقط فرانسه
amir apply phd --min-fit 7          # حداقل fit score 7
```

---

## رابط وب (FastAPI)

```bash
amir apply web          # روی port 8765
amir apply web 9000     # port دلخواه
```

آدرس: `http://localhost:8765`

### صفحات

| صفحه | توضیح |
|------|-------|
| `/phd` | موقعیت‌های PhD با toolbar فیلتر + sort دوطرفه روی همه ستون‌ها |
| `/job` | موقعیت‌های شغلی |
| `/replied` | کارت‌های پاسخ‌های دریافتی از استادان/کارفرمایان |
| `/stats` | تحلیل بر اساس status و کشور |

### ویژگی‌های جدول

- **مرتب‌سازی ستون**: کلیک روی هر ستون → مرتب می‌شود؛ کلیک دوباره → برعکس
- **ستون‌های قابل sort**: Institution, Deadline, Days, Fit, **Exp** (سابقه کار), Track, Country, Status, Added
- **فیلتر زنده**: تایپ در search box → ردیف‌ها فیلتر می‌شوند
- **کلیک روی ردیف**: panel جزئیات باز می‌شود با دکمه‌های عملیات

### دکمه‌های عملیات (در panel جزئیات)

| دکمه | کار |
|------|-----|
| **Open** | باز کردن URL آگهی در مرورگر |
| **📂 Open folder** | نمایش پوشه موقعیت در Finder (macOS) |
| **Mark sent** | ثبت به عنوان ارسال‌شده |
| **✗ Reject** | علامت‌گذاری به عنوان ریجکت (حذف از pending) |

### دکمه Sync Gmail

وقتی Gmail متصل باشد، دکمه **🔄 Sync Gmail** در header ظاهر می‌شود. با کلیک:
1. Draft‌های Gmail با محتوای `TRACK:` پیدا می‌شوند
2. فایل‌های `.md` ساخته + SQLite + JSON آپدیت می‌شوند
3. Draft‌های پردازش‌شده به Trash می‌روند
4. HTML tracker بازسازی می‌شود

---

## راه‌اندازی Gmail Sync (یک‌بار، ~۵ دقیقه)

### مرحله ۱ — فعال‌سازی Gmail API

1. به [console.cloud.google.com](https://console.cloud.google.com) برو
2. یک پروژه انتخاب یا بساز
3. منوی چپ: **APIs & Services → Library**
4. جستجو: `Gmail API` → **Enable**

### مرحله ۲ — ساخت OAuth Credentials

1. منوی چپ: **APIs & Services → Credentials**
2. **+ CREATE CREDENTIALS → OAuth client ID**
3. اگر Consent Screen خواست: **External** → اسم و ایمیل → **Save and Continue** × ۳
4. دوباره: **+ CREATE CREDENTIALS → OAuth client ID**
5. "What data will you be accessing?" → **User data** → **Next**
6. Application type: **Desktop app**
7. Name: `amir-apply-tracker` → **CREATE** → **Download JSON**

### مرحله ۳ — ذخیره فایل

```bash
mv ~/Downloads/client_secret_*.json ~/.amir/gmail_credentials.json
```

### مرحله ۴ — اتصال (یک‌بار)

1. `amir apply web` را اجرا کن
2. در header وب: **🔑 Connect Gmail** را کلیک کن
3. صفحه Google باز می‌شود → دسترسی بده
4. برمی‌گردی با دکمه **🔄 Sync Gmail** فعال

### مرحله ۵ — اضافه کردن Test User (اگر خطای access_denied دیدی)

Google Cloud Console → **Google Auth Platform → Audience → Test users** → ایمیل Google خودت را اضافه کن.

---

## فرمت AMIR-SYNC

یک Gmail draft با این ساختار بساز. Claude Code آن را از طریق Gmail MCP می‌خواند، در `sync_queue.txt` می‌نویسد، و `amir apply sync` پردازش می‌کند.

```
TRACK: ai_ml
ID: company_name_role
TITLE: ML Engineer
INSTITUTION: Company Name
LOCATION: Paris, France
DEADLINE: 30/06/2026
LINK: https://...
FIT: 8/10
EXPERIENCE: 3+ ans
CONTACT: recruiter@company.com
SOURCE: linkedin

---

TRACK: phd_ai_general
ID: FR_univ_topic
TITLE: PhD in Machine Learning
...
```

هر موقعیت با `---` جدا می‌شود. Track‌های پشتیبانی‌شده: `ai_ml`, `devops`, `devops_alternance`, `polyvalent`, `phd_ai_general`, `phd_ai_finance`.

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
| `↑` `↓` | navigation |
| `Tab` | جابجایی PhD ↔ Job |
| `s` | چرخش sort |
| `/` | نمایش/پنهان filter bar |
| `Esc` | پاک کردن filter |
| `m` | علامت‌گذاری به عنوان sent |
| `x` | **ریجکت کردن** موقعیت |
| `o` | باز کردن URL در مرورگر |
| `r` | refresh |
| `q` | خروج |

---

## Schema SQLite

```sql
CREATE TABLE positions (
  id           TEXT NOT NULL,
  kind         TEXT NOT NULL,        -- 'phd' یا 'job'
  track        TEXT,
  status       TEXT DEFAULT 'found',
  title        TEXT,
  institution  TEXT,
  country      TEXT,
  location     TEXT,
  deadline     TEXT,                 -- ISO: YYYY-MM-DD
  fit          TEXT,                 -- مثال: "8/10"
  fit_score    REAL,                 -- float برای sort عددی
  experience   TEXT,                 -- مثال: "3+ ans", "Junior", "Master requis"
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

**چرخه status:** `found → draft_ready → sent → replied / bounced / rejected / watching`

ستون‌های جدید به‌صورت خودکار از طریق migration در `get_db()` اضافه می‌شوند.

---

## ساختار دایرکتوری داده

```
$HOME/@-Amir/Apply/2026-2027/
├── PhD-Search/
│   ├── found/
│   │   ├── ai_general/
│   │   │   ├── tracking.json          ← backup JSON (dual-write)
│   │   │   └── <position-id>.md       ← جزئیات موقعیت
│   │   └── ai_finance/
│   ├── applied/
│   │   └── <position-id>/
│   │       ├── email_draft.md
│   │       ├── CV.pdf
│   │       └── LettreMotivation.pdf
│   └── suivi_candidatures_PhD.html    ← HTML tracker (auto-generated)
├── Job-Search/
│   └── ... (مشابه PhD)
├── apply_tracker.db                   ← SQLite (source of truth)
└── sync_queue.txt                     ← ورودی sync (موقت)
```
