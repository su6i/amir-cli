# رودمپ: تولید پست شبکه‌های اجتماعی از زیرنویس

این سند نقشه راه پیاده‌سازی پست‌خودکار برای شبکه‌های اجتماعی مختلف از روی زیرنویس‌های تولیدشده را شرح می‌دهد.

---

## معماری فعلی (فروردین ۱۴۰۴)

سه متد اصلی در `processor.py`:

| متد | مسئولیت |
|---|---|
| `generate_posts(original_base, source_lang, result, platforms, prompt_file)` | حلقه اصلی — برای هر زبان SRT × هر پلتفرم یک فایل `.txt` می‌سازد |
| `_get_post_prompt(platform, title, srt_lang_name, full_text, prompt_file)` | پرامپت‌های مخصوص هر پلتفرم — اینجا پلتفرم جدید اضافه کن |
| `_call_llm_for_post(system, user)` | فراخوانی LLM با DeepSeek → Gemini fallback |

**قرارداد نام‌گذاری خروجی:** `{original_base}_{srt_lang}_{platform}.txt`  
مثال: `KI_video_fa_telegram.txt` ، `KI_video_de_telegram.txt`

**CLI flags (به‌روزشده):**
- `--post [PLATFORM ...]` — بعد از workflow پست بساز (پیش‌فرض: telegram)
- `--post-only [PLATFORM ...]` — فقط از SRT های موجود پست بساز
- `--prompt-file FILE` — فایل پرامپت سفارشی (یک‌بار مصرف)
- فایل پرامپت دائمی: `~/.amir/prompts/{platform}.txt` با متغیرهای `{title}`, `{srt_lang_name}`, `{full_text}`

---

## چطور پلتفرم جدید اضافه کنیم

فقط یک `elif` در `_get_post_prompt()` اضافه کن:

```python
elif platform == 'youtube':
    system = "You write SEO-optimized YouTube video descriptions..."
    user   = f"Write a YouTube description for: {title}\n\n{full_text}"
    return system, user
```

سپس فراخوانی:
```bash
amir video subtitle video.mp4 --post  # فعلاً فقط telegram
# آینده:
# processor.generate_posts(base, lang, result, platforms=['telegram', 'youtube', 'linkedin'])
```

---

## نقشه راه پلتفرم‌ها

### ✅ پیاده‌سازی‌شده
- [x] **Telegram** — پست فارسی کوتاه (۸۰–۲۰۰ کلمه) + هشتگ  
  کلید: `'telegram'`
- [x] **YouTube** — توضیحات ویدیو SEO-optimized (۲۰۰–۴۰۰ کلمه)  
  کلید: `'youtube'`
- [x] **LinkedIn** — پست حرفه‌ای دوزبانه FA+EN (۱۵۰–۲۵۰ کلمه)  
  کلید: `'linkedin'`

---

### 🔲 در صف پیاده‌سازی

- [ ] **Instagram** — کپشن + هشتگ‌های زیاد
  - زبان: فارسی
  - طول: ۵۰–۱۲۰ کلمه + ۱۵–۳۰ هشتگ
  - لحن: پرانرژی، emoji-heavy
  - کلید پیشنهادی: `'instagram'`

- [ ] **X (Twitter)** — رشته توییت (Thread)
  - زبان: فارسی یا انگلیسی
  - ساختار: توییت اول = hook، ۳–۵ توییت بعدی = نکات کلیدی، آخری = CTA
  - محدودیت: هر توییت ≤ ۲۸۰ کاراکتر
  - خروجی: لیست JSON از توییت‌ها
  - کلید پیشنهادی: `'twitter'`

- [ ] **Aparat** — توضیحات فارسی برای آپارات
  - زبان: فارسی
  - طول: ۸۰–۲۰۰ کلمه
  - شامل: تگ‌های فارسی مناسب موتور جستجوی آپارات
  - کلید پیشنهادی: `'aparat'`

---

## نکات فنی

- هر SRT زبانی که تولید شده باشد پست جداگانه می‌گیرد (مثلاً هم `_fa_telegram.txt` هم `_de_telegram.txt`)
- `_SOCIAL_LANG_NAMES` در کلاس، نگاشت کد زبان به نام فارسی است — در صورت نیاز گسترش بده
- پرامپت‌ها همیشه از SRT زبانی که در اختیار است می‌خوانند (نه لزوماً FA)
- LLM fallback chain: DeepSeek → Gemini (در `_call_llm_for_post`)
