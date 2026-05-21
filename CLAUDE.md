# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## قانون کامیت: فرمت پیام

**هیچ‌گاه خط `Co-Authored-By:` به پیام کامیت اضافه نکن.** این پروژه شخصی است و نسبت دادن کامیت به AI غیرحرفه‌ای به نظر می‌رسد.

```bash
# فرمت صحیح:
git commit -m "type(scope): description"

# ممنوع:
# Co-Authored-By: Claude ... <noreply@anthropic.com>
```

---

## قانون امنیتی: بررسی اجباری قبل از هر کامیت

**قبل از هر `git commit`، با دقت و وسواس بررسی کن که هیچ‌کدام از موارد زیر در staged files وجود ندارد:**

| چه چیزی | نمونه |
|---|---|
| نام و نام خانوادگی واقعی | Amir Shirali-Pour، هر اسم شخصی |
| آدرس ایمیل | هر ایمیل واقعی |
| شماره تلفن | هر شماره واقعی |
| token و API key | هر رشته‌ای که شبیه secret باشد |
| مسیر فایل‌های شخصی | مسیرهایی که به فایل‌های خصوصی اشاره می‌کنند |
| داده hardcode شده از پروژه CV | محتوای `master_cv.json`، اطلاعات شغلی |

**روش بررسی:**
```bash
git diff --cached          # همه staged changes را بخوان
git diff --cached --stat   # لیست فایل‌های staged
```

اگر حتی یک مورد مشکوک دیدی → `git restore --staged <file>` و از کاربر بپرس.
در صورت شک، کامیت نکن.

---

## سیستم Agent: قوانین، Workflow‌ها، و Skill‌ها

پروژه یک سیستم دانش در `.agent/` دارد. **قبل از هر پیاده‌سازی** باید از آن استفاده کنی:

### قانون ۱: Workflow First
هر تسک یه workflow مشخص داره — قبل از نوشتن کد بخوانش:

| تسک | Workflow |
|---|---|
| پروژه جدید | `.agent/workflows/init-project.md` |
| پیاده‌سازی AI/ML | `.agent/workflows/ai-optimization.md` |
| تست و commit | `.agent/workflows/quality-assurance.md` |
| مستندسازی | `.agent/workflows/documentation.md` |

### قانون ۲: Skill First (No Reinventing the Wheel)
قبل از هر پیاده‌سازی، skill مربوطه را بخوان:

| حوزه | Skill |
|---|---|
| FFmpeg | `.agent/skills/ffmpeg.md`, `.agent/skills/ffmpeg-recipes.md` |
| زیرنویس و Whisper | `.agent/skills/subtitle-generator.md`, `.agent/skills/mlx-whisper.md` |
| دانلود ویدیو | `.agent/skills/yt-dlp-web-download.md` |
| Python | `.agent/skills/python-core-standards.md` |
| Bash/Zsh پیشرفته | `.agent/skills/zsh-scripting-advanced.md` |
| PDF رندر | `.agent/skills/pdf-rendering-engines.md` |
| Claude Code | `.agent/skills/claude-code-integration.md` |
| کیفیت کد | `.agent/skills/github-code-quality.md` |

قوانین کلی: `.agent/rules/global.mdc` — بخوان و رعایت کن.

### قانون ۳: Plan Before Code
برای هر تسکی که بیش از ۳ فایل را لمس می‌کند، ابتدا Plan Mode را فعال کن (`/plan`) یا از `Plan` subagent استفاده کن.

---

## قانون طلایی: مستندسازی اتوماتیک

**بعد از هر تغییر در کد، دستورات، یا ساختار پروژه:**

1. این فایل (`CLAUDE.md`) — اگر فایل کلیدی، دستور جدید، یا تصمیم معماری تغییر کرد، ثبت کن
2. `README.md` (اگر وجود دارد) — دستور جدید یا option جدید را مستند کن
3. بخش **تصمیمات** این فایل را با تاریخ و توضیح کامل به‌روز کن

اگر ابزار AI این پروژه را باز می‌کند، باید بتواند فقط با خواندن همین فایل شروع به کار کند.

---

## معماری و ساختار پروژه

`amir` یک CLI ابزار شخصی چندمنظوره است: ویدیو/صوت، زیرنویس AI، PDF/carousel، مدیریت سیستم.

### لایه‌های اجرا

```
amir (bash entry point)
├── sources lib/commands/*.sh     ← ~28 command modules
├── activates .venv automatically
├── exports AMIR_ROOT, LIB_DIR, SCRIPT_DIR
└── config from ~/.amir/config.yaml
```

### ماژول‌های کلیدی

| دستور | فایل | توضیح |
|-------|------|-------|
| `amir trend` / `amir research` | `lib/commands/trend.sh` | Bridge به research_toolkit (YouTube, GitHub, arXiv, Reddit, ProductHunt, IndieHackers) |
| `amir video` | `lib/commands/video.sh` | پردازش ویدیو + دانلود |
| `amir subtitle` | `lib/commands/subtitle.sh` | زیرنویس AI چندزبانه |
| `amir pdf` | `lib/commands/pdf.sh` | PDF با Puppeteer |
| `amir chat` | `lib/commands/chat.sh` | چت با Gemini/Gemma |

### ماژول trend — وابستگی خارجی

`amir trend` یک wrapper است که research_toolkit را فراخوانی می‌کند:

```
amir trend [keyword] [--options]
  │
  └─ lib/commands/trend.sh → run_trend()
       │
       └─ $toolkit_dir/.venv/bin/python main.py query [args]
            │
            └─ research_toolkit: synthesizer → connector → YouTube API / GitHub / ...
```

مسیر پیش‌فرض: `$HOME/@-github/research_toolkit`  
سفارشی‌سازی: `export RESEARCH_TOOLKIT_DIR=/path/to/toolkit`

**چرا از python مستقیم به جای `uv run` استفاده می‌کنیم:**  
`amir` اول `.venv` خودش را activate می‌کند. اگر `uv run` درون زیرپروسه فراخوانی شود، ممکن است venv اشتباه را انتخاب کند. فراخوانی مستقیم `.venv/bin/python` از مسیر toolkit این تداخل را حل می‌کند.

**اجرای دستورات Python:** از طریق `uv run` یا `.venv` که توسط installer ساخته می‌شه.

**اجرای PDF:** Node.js + Puppeteer (`lib/nodejs/render_puppeteer.js`) — مستقل از venv.

### سیستم زیرنویس (پیچیده‌ترین بخش)

```
lib/python/subtitle/
├── cli.py               ← argparse entry point (amir subtitle)
├── processor.py         ← orchestrator اصلی (Whisper + translate + render)
├── transcription/       ← Whisper (mlx-whisper / faster-whisper)
├── translation/         ← deepseek_pipeline.py + gemini fallback
├── social/              ← Telegram/LinkedIn post generation
├── rendering/           ← ASS subtitle + FFmpeg burn-in
├── segmentation/        ← speaker diarization
├── concurrency/         ← slot management (cap=1 default)
└── workflow/            ← pipeline orchestration
```

### API Keys (در `~/.amir/config.yaml` یا env vars)

| متغیر | کاربرد |
|---|---|
| `DEEPSEEK_API_KEY` | ترجمه زیرنویس (deepseek-v4-flash) — اصلی |
| `GEMINI_API_KEY` | fallback ترجمه + `amir chat` |
| `GOOGLE_API_KEY` | Gemini TTS |
| `OPENAI_API_KEY` | فقط برای `amir llm-lists openai` |

---

## دستورات توسعه

```bash
# نصب اولیه
./install.sh

# اجرای مستقیم (بدون install)
bash amir <command>

# اجرای Python subtitle مستقیماً
uv run python -m subtitle <args>
# یا با venv فعال:
source .venv/bin/activate
python lib/python/subtitle/cli.py <args>

# تست subtitle (pytest)
cd lib/python/subtitle && pytest tests/ -v

# ساخت PDF carousel
amir pdf --theme carousel FILE.md -o OUTPUT.pdf

# git add برای lib/commands/ (به دلیل gitignore باید -f بزنی)
git add -f lib/commands/specific_file.sh
```

---

## فایل‌های کلیدی

| فایل | نقش |
|---|---|
| `amir` | bash entry point — sources commands, activates venv |
| `lib/commands/pdf.sh` | دستور `amir pdf` |
| `lib/commands/video.sh` | دانلود + پردازش ویدیو + SIGINT trap |
| `lib/commands/subtitle.sh` | pipeline زیرنویس، exit code 130 propagation |
| `lib/nodejs/render_puppeteer.js` | موتور رندر PDF (Puppeteer) |
| `lib/themes/carousel.css` | تم LinkedIn carousel (1080×1080) |
| `lib/python/subtitle/processor.py` | orchestrator زیرنویس |
| `lib/python/subtitle/cli.py` | argparse + banner back_color fix |
| `lib/python/subtitle/quality.py` | کیفیت‌سنج SRT + ساخت language timeline چندزبانه |
| `lib/python/subtitle/workflow/source_stage.py` | تهیه SRT منبع + YouTube auto-pipeline |
| `lib/python/subtitle/translation/deepseek_pipeline.py` | DeepSeek V4-Flash translation |
| `lib/commands/init-project.sh` | `amir init-project` — کپی `.agent/` به پروژه جدید |
| `lib/commands/trend.sh` | `amir trend` / `amir research` — bridge به research_toolkit |
| `completions/_amir` | Zsh autocompletion — شامل `trend` و تمام آپشن‌هایش |

---

## تصمیمات این session (21 مه 2026)

### مشکل ۶: ویدیوهای چندزبانه — هذیان Whisper هنگام تغییر زبان
**علت:** Whisper زبان را فقط یک‌بار از ۳۰ ثانیه اول detect می‌کند و برای کل ویدیو قفل می‌کند. وقتی `language='he'` ست بود و صدا به انگلیسی تغییر می‌کرد، Whisper هذیان عبری تولید می‌کرد (مثل "על קריטיקה" loop در Tucker Carlson).

**راه‌حل — سه لایه:**

1. **`quality.py` (جدید):** کیفیت‌سنج SRT با ۵ metric: coverage، WPM، exact-repetition، **near-duplicate loop** (Jaccard similarity > 0.6 بین خطوط متوالی — این hallucination رو با score=0.50 گرفت)، و gap analysis. آستانه پیش‌فرض: 0.65.

2. **YouTube auto-pipeline در `source_stage.py`:** قبل از هر Whisper، اگر `info.json` کنار ویدیو باشد، track‌های `iw`/`he` و `en` رو دانلود و quality-check می‌کند:
   - یه track با quality≥0.65 و coverage≥72% → مستقیم استفاده (بدون Whisper)
   - دو track مکمل (مثل he=5% + en=95%) → `build_language_timeline()` → `transcribe_by_language_timeline()`
   - هیچ‌کدام → Whisper معمولی
   - با `--no-yt-auto` غیرفعال می‌شود

3. **`transcribe_by_language_timeline()` در `processor.py`:** هر segment ویدیو را با FFmpeg جدا می‌کند و Whisper را با زبان درست آن segment فراخوانی می‌کند. timestamps مطلق را نگه می‌دارد.

4. **`--multilingual` flag:** برای ویدیوهای **غیر YouTube** (بدون info.json) — chunk را از 420-600s به **90s** کاهش می‌دهد تا هر chunk مستقلاً زبانش را detect کند. برای YouTube ها نیازی نیست.

**فایل‌های تغییریافته:** `quality.py` (جدید)، `processor.py`، `workflow/source_stage.py`، `cli.py`

### نکته مهم — رفتار `--force` با YouTube auto-pipeline

`--force` یعنی «SRT قدیمی را پاک کن و از صفر پردازش کن». **نباید** YouTube auto-pipeline را skip کند.
در `source_stage.py`، شرط `not force` از condition اجرای `_auto_yt_check` حذف شد — حالا `--force` همچنان YouTube را چک می‌کند و فقط `--no-yt-auto` آن را skip می‌کند.

### سه باگ در YouTube auto-pipeline (کشف‌شده در تست Tucker Carlson)

1. **`iw` → `he` filename normalization:** yt-dlp کد `iw` (عبری قدیمی) را در نام فایل به `he` نرمال می‌کند. `_find_best_srt("iw")` فایل را پیدا نمی‌کرد. **راه‌حل:** تابع حالا هم `iw` و هم `he` را جستجو می‌کند.

2. **Decision 2 threshold:** برای language map (نه استفاده مستقیم بدون Whisper)، threshold از `score >= 0.35` به `coverage >= 0.10` تغییر کرد — چون WPM یا near-dup در track یوتیوب مهم نیست، فقط پوشش زمانی مهم است.

3. **Fallback برای en-only:** وقتی فقط track انگلیسی موجود است (مثل `en-orig` با 96% coverage)، gap قبل از اولین entry انگلیسی به عنوان بخش `source_lang` استنتاج می‌شود (مثل Tucker Carlson: فاصله 0 تا 38 ثانیه = عبری).

4. **Whisper hallucination در segment بلند:** segment 17 دقیقه‌ای انگلیسی Tucker Carlson در دقیقه ۸ هذیان می‌زد («It's not a good thing» loop). علت واقعی: گوینده اسرائیلی در طول مصاحبه به عبری سوال می‌پرسد — وقتی Whisper با `language='en'` force می‌شود و عبری می‌شنود، hallucinate می‌کند. **راه‌حل:** segmentهای بلند‌تر از ۳۰۰ ثانیه با `force_chunked=True, language=''` (auto-detect per 90s chunk) پردازش می‌شوند تا زبان‌بندی مخلوط درست handle شود.

---

## تصمیمات این session (20 مه 2026)

### مشکل ۴: Ctrl+C در pipeline دانلود+زیرنویس کار نمی‌کرد
**علت:** تابع `video_download` در `video.sh` هیچ trap‌ای برای `SIGINT` نداشت. وقتی Ctrl+C زده می‌شد، `yt-dlp` می‌مرد ولی bash ادامه می‌داد: retry دانلود، ساخت زیرنویس، ایجاد `_link.txt` و ...  
**راه‌حل:** در ابتدای `video_download` یک trap تنظیم شد: `trap '_DL_ABORTED=1' INT`. بعد از هر مرحله کلیدی (دانلود اول، retry، شروع subtitle) مقدار `_DL_ABORTED` و exit code 130 چک می‌شه. در `subtitle.sh` هم exit code 130 از `video_download` تشخیص داده و propagate می‌شه.

### مشکل ۵: `--subtitle-banner-color` بی‌اثر بود
**علت:** در `cli.py` کد مربوط به transparent کردن پس‌زمینه subtitle فقط برای ۴ style خاص اجرا می‌شد (`channel_brand_blue` و ...). برای `lecture` (default style) که `back_color="&H80000000"` داشت، این اتفاق نمی‌افتاد. نتیجه: پس‌زمینه‌ی نیمه‌شفاف subtitle روی banner می‌نشست و رنگ banner دیده نمی‌شد.  
**راه‌حل:** شرط style‌های خاص حذف شد. حالا برای **هر style‌ای** که `--subtitle-banner-color` یا `--subtitle-banner-image` ست باشه، `back_color` به `&H00000000` (کاملاً transparent) تغییر می‌کنه (`cli.py` خط ۳۶۱).

---

## تصمیمات این session (18 مه 2026)

### مشکل ۱: سرریز جدول در تم carousel
**علت:** `render_puppeteer.js` در base CSS مقدار `min-width: 100%` روی `table` تنظیم کرده بود. تم carousel عرض را 976px می‌خواست اما `min-width: 100% = 1080px` override می‌شد → overflow 104px.  
**راه‌حل:** اضافه کردن `min-width: 0 !important` به carousel `addStyleTag` در `render_puppeteer.js`.

### مشکل ۲: محتوا بالای صفحه می‌چسبید (no vertical centering)
**علت:** محتوای هر اسلاید به صورت block عادی flow می‌شد، هیچ centering نداشت.  
**راه‌حل دو مرحله‌ای:**
1. **DOM wrapping (JS):** بعد از emoji fix، یک `page.evaluate()` اضافه شد که هر `H2` و sibling‌هایش تا H2 بعدی را در یک `<div class="slide">` wrap می‌کند. محتوای قبل از اولین H2 (cover) در `<div class="slide slide-cover">` می‌رود.
2. **CSS:** در `carousel.css`، `page-break-before` از `h2` حذف شد و به `.slide` منتقل شد. هر slide با `display:flex; justify-content:center; height:1080px` عمودی center می‌شود.

### مشکل ۳: کاور پایین صفحه بود
**علت:** `h1` داشت `padding-top: 80px` که داخل flex container محاسبه می‌شد و متن را پایین‌تر از center می‌برد.  
**راه‌حل:** `padding: 80px 52px 0` → `padding: 0 52px`.

## وضعیت فعلی carousel theme

```css
/* carousel.css تغییرات کلیدی */
h1 { padding: 0 52px; }           /* was: 80px 52px 0 */
h2 { padding: 0 52px 0; }         /* was: 60px 52px 0 + page-break */
/* .slide و .slide-cover اضافه شد */
.slide { height:1080px; display:flex; flex-direction:column; justify-content:center; }
```

```javascript
// render_puppeteer.js — carousel addStyleTag (کلیدی)
// min-width: 0 !important  ← fix overflow
// .slide / .slide-cover    ← vertical centering
// DOM wrapping via page.evaluate() بعد از emoji fix
```

## پروژه وابسته: CV / LinkedIn Content

مسیر: `/Users/su6i/@-github/CV/` — مستندات کامل در `CV/CLAUDE.md`

### دستور ساخت carousel از CV project

```bash
# از ریشه CV project:
amir pdf --theme carousel linkedin/02_data_science/carousel.md \
         -o linkedin/02_data_science/carousel.pdf
```

### فایل‌های اصلی در CV project

| فایل | محتوا |
|---|---|
| `linkedin/01_IT_job_market/carousel.md` | بازار IT فرانسه (15 شهر) — منتشر شده |
| `linkedin/02_data_science/carousel.md` | مشاغل Data در فرانسه — منتشر شده |
| `scripts/data_jobs_scraper.mjs` | اسکرپر France Travail MétierScope |
| `docs/it_rome_codes.json` | کدهای ROME برای مشاغل IT/Data |
| `scripts/linkedin_post.py` | انتشار PDF carousel روی LinkedIn |
