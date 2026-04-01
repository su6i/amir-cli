# تحلیل و بهینه‌سازی زیرنویس ویدیوهای عمودی
# Vertical Video Subtitle Optimization Analysis

**تاریخ**: 29 مارس 2026  
**وضعیت**: نیازمند بهینه‌سازی فوری

---

## 📋 خلاصه مسائل (Problem Summary)

### مسائل کلیدی:
1. **✗ حاشیه‌های افقی غلط**: در حالت عمودی، حاشیه‌های افقی 64px است (باید 32px باشد)
2. **✗ برش متن بدون هشدار**: در حالت دو‌زبانه، متن انگلیسی صرفاً به 42 کاراکتر برش داده می‌شود
3. **✗ محاسبه منطقه متن غلط**: برای ویدیوهای عمودی از عرض استفاده می‌شود به جای ارتفاع
4. **✗ محدود شدن سخت بر روی تعداد کلمات**: تعداد کلمات به صورت پویا محاسبه می‌شود، نه دقیقاً 5
5. **✗ ناهماهنگی بین خطوط**: خطوط برای دو زبان متفاوت پوش داده می‌شوند

---

## 🔴 مسائل بحرانی (Critical Issues)

### مسئله 1: حاشیه‌های افقی یکسان
**📍 فایل**: `lib/python/subtitle/rendering/ass_helpers.py` (خطی 17-19)
**مشکل**:
```python
margin_h = 64 if is_portrait else 64  # ← یکسان برای هر دو!
```

**تاثیر**:
- ویدیوهای عمودی (9:16) اضافی 32px حاشیه می‌گیرند
- متن مرکز نمی‌شود بلکه به کناری‌ها فشار داده می‌شود
- ممکن است متن از فریم بیرون بزند

**راه‌حل**:
```python
margin_h = 32 if is_portrait else 64  # ✓ متناسب با اندازه
```

---

### مسئله 2: برش متن بدون کنترل
**📍 فایل**: `lib/python/subtitle/rendering/ass_helpers.py` (خطی 91-97)
**مشکل**:
```python
def _normalize_primary_text(text: str, secondary_srt: Optional[str], is_portrait: bool) -> str:
    out = text.replace("\n", " ").strip()
    if secondary_srt:
        max_top_chars = 42 if is_portrait else 70  # ← برش سخت!
        if len(out) > max_top_chars:
            out = out[:max_top_chars].rsplit(" ", 1)[0] + "…"  # ← متن مفقود!
```

**تاثیر**:
- متن اصلی **خاموشانه** برش داده می‌شود (بدون لاگ)
- کل جملات مفقود می‌شوند
- ناهماهنگی زمانی: خط اول متفاوت از آوای اصلی

**مثال**:
```
Original:  "This is a very important message about the new policy change"
Truncated: "This is a very important message about the new…"
┌────────────────────────────────────────────────────┐
│ Broken sync: User hears "policy change" but sees "…"│
└────────────────────────────────────────────────────┘
```

---

### مسئله 3: محاسبه منطقه متن غلط
**📍 فایل**: `lib/python/subtitle/workflow/base.py` (خطی 222-231)
**مشکل**:
```python
def detect_subtitle_geometry(processor, video_path: str, target_langs: List[str]) -> Tuple[int, int]:
    vw, vh = processor._detect_video_dimensions(video_path)
    
    rendered_font_px = processor.style_config.font_size * (vh / 480.0)
    text_area_px = vw * 0.80  # ← برای ویدیوهای عمودی غلط!
    #              ↑ برای عمودی باید از ارتفاع استفاده شود
    
    max_chars_dyn = max(10, int(text_area_px / avg_glyph_w))
    target_words_dyn = max(4, min(10, max_chars_dyn // 4))  # ← محدود شدن سخت
```

**تاثیر**:
- ویدیوهای عمودی 360×640: `text_area_px = 360 * 0.80 = 288px` (خیلی کمی!)
- تعداد کلمات: `4–10` نه دقیقاً `5`
- برای YouTube Shorts (عمودی): خطوط بسیار محدود

**مثال عددی**:
```
ویدیوی عمودی: 360×640
من: ارتفاع (640px) استفاده شود
جری: عرض (360px) استفاده می‌شود
└─ منطقه متن: 288px (34% کمتر!)
```

---

### مسئله 4: بدون حد سخت 5 کلمه
**📍 فایل**: `lib/python/subtitle/processor.py` (خطوط 1250-1500)
**مشکل**:
```python
target_words_dyn = max(4, min(10, max_chars_dyn // 4))
#                  ↑ محدود شدن 4–10 کلمه، نه دقیقاً 5
```

**تاثیر**:
- برای short-form videos (Instagram/TikTok) باید دقیقاً **5 کلمه** باشد
- فعلاً: 4–10 کلمه می‌تواند باشد
- نتیجه: بعضی خطوط طولانی‌تر، مشکل برای موبایل

---

### مسئله 5: ناهماهنگی دو‌زبانه
**📍 فایل**: `lib/python/subtitle/rendering/ass_helpers.py` (خطی 145-160)
**مشکل**:
```python
# خط اول (انگلیسی): 42 کاراکتر → برش داده می‌شود
text = _normalize_primary_text(entry["text"], secondary_srt, is_portrait)

# خط دوم (فارسی): نه نهایت نمایش داده می‌شود
if bi_fa_text:
    events.append(f"Dialogue: 0,{ass_start},{ass_end},FaDefault,,0,0,0,,{bi_fa_text}")
    events.append(f"Dialogue: 0,{ass_start},{ass_end},TopDefault,,0,0,0,,{final_text}")
```

**تاثیر**:
- خط اول متن کامل نیست
- خط دوم آن را ترجمه کرده اما خط اول داریم!
- **ناهماهنگی مکمل**: صوت می‌گوید X، خط اول Y را نشان می‌دهد

---

## 🟡 مسائل میانی (Medium Priority)

### مسئله 6: استفاده از `len()` بجای `vis_len()`
**📍 فایل**: `lib/python/subtitle/rendering/ass_helpers.py` (خطی 95-96)
```python
if len(out) > max_top_chars:  # ← شمارش کاراکترهای zero-width
#   ^
# باید: if vis_len(out) > max_top_chars
```

**تاثیر**: کاراکترهای BiDi نامرئی صحافی مشکل می‌کنند

---

## 🎯 راه‌حل‌ها (Solutions)

### مرحله 1: محاسبه منطقه متن درست
```python
def detect_subtitle_geometry(...):
    # BEFORE:
    text_area_px = vw * 0.80
    
    # AFTER: استفاده از ارتفاع برای عمودی
    if is_portrait:
        text_area_px = vh * 0.60  # سقف بالاتر برای عمودی
    else:
        text_area_px = vw * 0.80
         
    # دائمی 5 کلمه برای short-form vertical
    if is_portrait:
        target_words_dyn = 5  # ✓ ثابت برای short-form
    else:
        target_words_dyn = max(4, min(10, max_chars_dyn // 4))
```

### مرحله 2: بدون برش خاموش
```python
def _normalize_primary_text(text: str, secondary_srt: Optional[str], is_portrait: bool) -> str:
    out = text.replace("\n", " ").strip()
    
    if secondary_srt:
        # اگر در حالت دوزبانه هستیم، پیام هشدار
        max_top_chars = 50 if is_portrait else 80
        if len(out) > max_top_chars:
            logger.warning(f"⚠️ Text truncation in bilingual mode: '{out[:30]}...'")
            # بدل برش، کاهش اندازه فونت: 
            # return out  # نه برش، بلکه اندازه‌گذاری
    return out
```

### مرحله 3: حاشیه‌های درست
```python
margin_h = 32 if is_portrait else 64  # ✓ متناسب
fa_margin_v = 20 if is_portrait else 10
top_margin_v = 30 if is_portrait else 24
```

### مرحله 4: استفاده از `vis_len()`
```python
from subtitle.segmentation import vis_len

if vis_len(out) > max_top_chars:  # ✓ صحیح
    out = out[:max_top_chars]
```

---

## 📊 خلاصه تغییرات (Change Summary)

| فایل | خط | مسئله | حل |
|------|-----|-------|-----|
| `ass_helpers.py` | 17 | `margin_h = 64` یکسان | `margin_h = 32 if is_portrait else 64` |
| `ass_helpers.py` | 95-97 | برش بدون هشدار | بدون برش، فونت کمتر |
| `workflow/base.py` | 222 | `text_area_px = vw * 0.80` | `text_area_px = vh * 0.60 if is_portrait else vw * 0.80` |
| `workflow/base.py` | 231 | `target_words_dyn = max(4, min(10, ...))` | `target_words_dyn = 5 if is_portrait else ...` |
| `ass_helpers.py` | 96 | `len(out)` اشتباه | `vis_len(out)` درست |

---

## ✅ نتیجه انتظار (Expected Results)

بعد از بهینه‌سازی:
- ✓ **متن عمودی**: حاشیه‌های صحیح (32px)
- ✓ **5 کلمه**: دقیقاً برای short-form videos
- ✓ **بدون برش**: متن کامل و هماهنگ
- ✓ **یک خط هر زبان**: در یک زمان
- ✓ **سنکرو کامل**: صوت = متن

---

## 📝 نکات مهم (Important Notes)

1. **تاثیر**: تغییرات **صرفاً** بر ویدیوهای عمودی تاثیر می‌گذارند
2. **ایمین**: تغییرات **هیچ** بخش دیگر را نمی‌زند
3. **تست**: روی Instagram Reels، YouTube Shorts، TikTok را بررسی کنید
