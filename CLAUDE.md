# amir-cli — CLAUDE.md

## قانون طلایی: مستندسازی اتوماتیک

**بعد از هر تغییر در کد، دستورات، یا ساختار پروژه:**

1. این فایل (`CLAUDE.md`) — اگر فایل کلیدی، دستور جدید، یا تصمیم معماری تغییر کرد، ثبت کن
2. `README.md` (اگر وجود دارد) — دستور جدید یا option جدید را مستند کن
3. بخش **تصمیمات** این فایل را با تاریخ و توضیح کامل به‌روز کن

اگر ابزار AI این پروژه را باز می‌کند، باید بتواند فقط با خواندن همین فایل شروع به کار کند.

---

## چیه این پروژه

ابزار CLI شخصی برای تبدیل Markdown/HTML به PDF با موتور Puppeteer (headless Chrome). دستور اصلی: `amir pdf [options] file.md`.

## فایل‌های کلیدی

| فایل | نقش |
|---|---|
| `lib/commands/pdf.sh` | entry point دستور `amir pdf` |
| `lib/nodejs/render_puppeteer.js` | موتور رندر اصلی (Puppeteer) |
| `lib/themes/carousel.css` | تم LinkedIn carousel |
| `lib/commands/audio.sh`, `video.sh` | دستورات صوتی/تصویری |
| `lib/python/subtitle/processor.py` | پردازش زیرنویس |

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

## دستور ساخت PDF carousel

```bash
cd /Users/su6i/@-github/CV/docs
amir pdf --theme carousel FILE.md -o OUTPUT.pdf
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
