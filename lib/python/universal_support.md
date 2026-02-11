# 🌍 پشتیبانی جهانی از کارت‌های شناسایی

## ✅ کشورها و زبان‌های پشتیبانی شده

### 🇪🇺 اروپا

| کشور | زبان | فیلدهای Name | مثال شماره شناسایی |
|------|------|-------------|-------------------|
| 🇫🇷 فرانسه | French | NOM, PRÉNOM | 9927063493 (10 رقم) |
| 🇩🇪 آلمان | German | NACHNAME, VORNAME | 123456789 (9 رقم) |
| 🇪🇸 اسپانیا | Spanish | APELLIDO, NOMBRE | 12345678A (8 رقم + حرف) |
| 🇮🇹 ایتالیا | Italian | COGNOME, NOME | ABCDEF12G34H567I |
| 🇵🇹 پرتغال | Portuguese | APELIDO, NOME | 12345678 |
| 🇳🇱 هلند | Dutch | ACHTERNAAM, VOORNAAM | 123456789 |
| 🇵🇱 لهستان | Polish | NAZWISKO, IMIĘ | ABC123456 |
| 🇬🇧 انگلیس | English | SURNAME, GIVEN NAME | AB123456C |

### 🇷🇺 شرق اروپا و روسیه

| کشور | الفبا | فیلدهای Name | نمونه |
|------|------|-------------|------|
| 🇷🇺 روسیه | Cyrillic | ФАМИЛИЯ, ИМЯ, ОТЧЕСТВО | 1234 567890 |
| 🇺🇦 اوکراین | Cyrillic | ПРІЗВИЩЕ, ІМ'Я | 12345678 |
| 🇧🇬 بلغارستان | Cyrillic | ПРЕЗИМЕ, ИМЕ | 123456789 |

### 🌏 آسیا

| کشور | اسکریپت | فیلدها | شماره |
|------|---------|--------|-------|
| 🇨🇳 چین | Chinese (简体) | 姓名, 姓, 名 | 110101199001011234 |
| 🇯🇵 ژاپن | Japanese (漢字/仮名) | 氏名, 姓, 名 | 1234567890123 |
| 🇰🇷 کره | Korean (한글) | 이름, 성명 | 123456-1234567 |
| 🇹🇭 تایلند | Thai | ชื่อ, นามสกุล | 1234567890123 |
| 🇻🇳 ویتنام | Vietnamese | TÊN, HỌ | 123456789012 |
| 🇮🇳 هند | Multi | NAME, SURNAME | 1234 5678 9012 |

### 🌍 خاورمیانه و شمال آفریقا

| کشور | اسکریپت | فیلدها | نمونه |
|------|---------|--------|------|
| 🇮🇷 ایران | Persian/Arabic | نام, نام خانوادگی | 1234567890 |
| 🇸🇦 عربستان | Arabic | الاسم, اللقب | 1234567890 |
| 🇦🇪 امارات | Arabic/English | NAME, اسم | 784-1234-1234567-1 |
| 🇹🇷 ترکیه | Turkish (Latin) | SOYAD, ADI | 12345678901 |
| 🇪🇬 مصر | Arabic | الاسم, اللقب | 12345678901234 |
| 🇮🇱 اسرائیل | Hebrew/Arabic | שם משפחה, שם פרטי | 123456789 |

### 🌎 آمریکا

| کشور | زبان | فیلدها | شماره |
|------|------|--------|-------|
| 🇺🇸 آمریکا | English | NAME, SURNAME | 123-45-6789 (SSN) |
| 🇨🇦 کانادا | English/French | NOM, NAME | 123 456 789 |
| 🇲🇽 مکزیک | Spanish | APELLIDOS, NOMBRE | ABCD123456HDFRRL00 |
| 🇧🇷 برزیل | Portuguese | NOME, SOBRENOME | 123.456.789-00 |
| 🇦🇷 آرژانتین | Spanish | APELLIDO, NOMBRE | 12.345.678 |

## 🔧 تنظیمات Tesseract برای هر منطقه

### اروپا و آمریکای لاتین:
```python
lang='eng+fra+spa+deu+ita+por'
```

### شرق اروپا:
```python
lang='eng+rus+ukr+bul'
```

### خاورمیانه:
```python
lang='eng+ara+fas+tur+heb'
```

### آسیا:
```python
lang='eng+chi_sim+chi_tra+jpn+kor+tha+vie'
```

### همه موارد (پیشنهادی):
```python
lang='eng+fra+spa+deu+ita+por+rus+ara+chi_sim+jpn+kor'
```

## 📋 فرمت‌های مختلف شماره شناسایی

| نوع | طول | فرمت | مثال |
|-----|------|------|------|
| SSN (USA) | 9 | ###-##-#### | 123-45-6789 |
| NIE (Spain) | 9 | X#######L | X1234567A |
| CPF (Brazil) | 11 | ###.###.###-## | 123.456.789-00 |
| Aadhaar (India) | 12 | #### #### #### | 1234 5678 9012 |
| NRIC (Singapore) | 9 | S#######L | S1234567D |
| MyKad (Malaysia) | 12 | ######-##-#### | 123456-12-3456 |
| ID Card (China) | 18 | ################## | 110101199001011234 |
| Passport (Universal) | 8-9 | A######## | AB1234567 |

## 🎯 الگوریتم تشخیص هوشمند

```
1. Multi-language OCR
   ├─ Latin (eng+fra+spa+deu+ita+por)
   ├─ Cyrillic (rus+ukr+bul)
   ├─ Arabic (ara+fas)
   └─ CJK (chi_sim+jpn+kor)

2. Pattern Detection
   ├─ Find name labels (100+ variations)
   ├─ Extract text after label
   ├─ Clean prefix (Mr., Mrs., M., etc.)
   └─ Normalize (remove special chars)

3. Number Extraction
   ├─ Look for 6-20 digit sequences
   ├─ Normalize (O→0, I→1, S→5)
   ├─ Vote for most common
   └─ Prefer longer numbers

4. Combine & Validate
   ├─ Priority: Position-based
   ├─ Fallback: Pattern matching
   ├─ Verify: Not a noise word
   └─ Output: NAME_NUMBER.png
```

## ⚙️ نصب زبان‌های Tesseract

### Ubuntu/Debian:
```bash
# European languages
sudo apt-get install tesseract-ocr-eng tesseract-ocr-fra tesseract-ocr-spa \
                     tesseract-ocr-deu tesseract-ocr-ita tesseract-ocr-por

# Cyrillic
sudo apt-get install tesseract-ocr-rus tesseract-ocr-ukr tesseract-ocr-bul

# Arabic/Persian
sudo apt-get install tesseract-ocr-ara tesseract-ocr-fas

# Asian
sudo apt-get install tesseract-ocr-chi-sim tesseract-ocr-jpn tesseract-ocr-kor
```

### macOS:
```bash
brew install tesseract
brew install tesseract-lang  # All languages
```

### Windows:
```powershell
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# Install with "Additional Language Data" selected
```

## 🧪 تست با کارت‌های مختلف

```bash
# French ID
python3 smart_crop_v2_ADVANCED_OCR.py french_id.png output/

# German Ausweis
python3 smart_crop_v2_ADVANCED_OCR.py german_ausweis.png output/

# Japanese 運転免許証
python3 smart_crop_v2_ADVANCED_OCR.py japanese_license.png output/

# Arabic بطاقة
python3 smart_crop_v2_ADVANCED_OCR.py arabic_id.png output/

# US Driver License
python3 smart_crop_v2_ADVANCED_OCR.py us_dl.png output/
```

## 💡 نکات مهم

1. **کیفیت عکس**: حداقل 300 DPI
2. **نور**: یکنواخت و بدون سایه
3. **زاویه**: مستقیم (کد auto-rotate داره)
4. **زبان**: Tesseract باید نصب باشه
5. **فرمت**: هر فرمتی (PNG, JPG, TIFF, ...)

## 🚨 محدودیت‌ها

- ❌ دست‌نویس (handwritten) را نمی‌خواند
- ❌ عکس‌های خیلی blur
- ❌ زبان‌هایی که Tesseract ندارد (برخی زبان‌های آفریقایی)
- ⚠️  دقت برای عربی و فارسی: ~70% (چپ به راست مشکل ایجاد می‌کند)

## 🎉 موارد استفاده موفق

✅ Passport (همه کشورها)
✅ National ID Card
✅ Driver License
✅ Residence Permit
✅ Work Permit
✅ Student ID
✅ Health Insurance Card
✅ Social Security Card




# 📛 Smart Filename نام‌گذاری هوشمند - راهنمای کامل

## 🎯 چطور کار می‌کنه؟

### حالت 1: Output یک **دایرکتوری** هست
```bash
python smart_crop.py input.png output_dir/
                                       ↑ 
                               slash یعنی directory
```

**رفتار:** 
- ✅ Smart naming **خودکار** فعال میشه
- ✅ OCR اجرا میشه و اسم + شماره رو می‌خونه
- ✅ فایل با اسم هوشمند ذخیره میشه

**خروجی:**
```
output_dir/SHIRALT_POUR_9927063493.png
```

---

### حالت 2: Output یک **فایل** هست
```bash
python smart_crop.py input.png my_exact_name.png
                                ↑
                          اسم دقیق فایل
```

**رفتار:**
- ❌ Smart naming **غیرفعال** 
- ✅ دقیقاً همون اسمی که دادی استفاده میشه

**خروجی:**
```
my_exact_name.png
```

---

### حالت 3: Force کردن Smart Naming برای فایل
```bash
python smart_crop.py input.png output.png 20 smart
                                               ↑
                                          mode = smart
```

**رفتار:**
- ✅ Smart naming **اجباری** فعال میشه
- ⚠️  اسم `output.png` نادیده گرفته میشه
- ✅ اسم هوشمند جایگزین میشه

**خروجی:**
```
SHIRALT_POUR_9927063493.png  (اسم output.png نادیده گرفته شد)
```

---

## 📊 جدول تصمیم‌گیری

| شرایط | Smart Naming | نام نهایی |
|-------|--------------|-----------|
| `output/` (dir) + mode=crop | ✅ خودکار | `LASTNAME_ID.png` |
| `output/` (dir) + mode=scan | ✅ خودکار | `LASTNAME_ID.png` |
| `file.png` + mode=crop | ❌ خاموش | `file.png` |
| `file.png` + mode=smart | ✅ اجباری | `LASTNAME_ID.png` |
| `file.png` + mode=scan | ❌ خاموش | `file.png` |

---

## 💡 مثال‌های کاربردی

### ✅ مثال 1: Batch Processing (پردازش دسته‌ای)
```bash
# می‌خوای 100 تا کارت رو اسکن کنی:
for img in *.png; do
    python smart_crop.py "$img" output_dir/
done

# خروجی:
# output_dir/SMITH_JOHN_123456.png
# output_dir/DOE_JANE_789012.png
# output_dir/WANG_LI_345678.png
# ...
```

### ✅ مثال 2: اسم دقیق می‌خوای
```bash
# برای یه کارت خاص:
python smart_crop.py passport.png my_passport_scan.png

# خروجی:
# my_passport_scan.png  (عین همین اسم)
```

### ✅ مثال 3: Professional Scan با اسم هوشمند
```bash
# کیفیت بالا + OCR:
python smart_crop.py id_card.png scans/ 30 scan

# خروجی:
# scans/MUELLER_HANS_987654321.png  (enhanced quality)
```

### ✅ مثال 4: Force Smart Naming
```bash
# حتی اگه اسم فایل دادی، OCR رو می‌خوای:
python smart_crop.py card.png ignored_name.png 20 smart

# خروجی:
# LASTNAME_FIRSTNAME_ID.png  (اسم ignored_name نادیده گرفته شد)
```

---

## 🔧 کد داخلی (برای توسعه‌دهندگان)

```python
# خط 538-548 از smart_crop_fixed.py:

use_smart_name = os.path.isdir(output_path) or 'smart' in mode.lower()

if use_smart_name and os.path.isdir(output_path):
    smart_name = get_smart_filename(warped, input_path)
    output_path = os.path.join(output_path, smart_name)
    print(f"💡 Smart Name: {smart_name}")
elif os.path.isdir(output_path):
    # Directory اما smart خاموش
    base = os.path.basename(input_path)
    output_path = os.path.join(output_path, f"{os.path.splitext(base)[0]}_cropped.png")
```

---

## 🐛 عیب‌یابی

### مشکل: هر بار اسم متفاوت می‌ده
**علت:** OCR noise دارد

**راه‌حل:**
1. کیفیت عکس رو بهتر کن (نور، فوکوس)
2. از mode `scan` استفاده کن برای بهتر شدن OCR
3. اگه خیلی مهمه، اسم دقیق بده (حالت 2)

### مشکل: اسم رو نادیده میگیره
**علت:** Output یک directory هست یا mode=smart

**راه‌حل:**
```bash
# اگه می‌خوای اسم دقیق:
python smart_crop.py input.png exact_name.png  # بدون slash، بدون smart
```

### مشکل: فارسی/عربی رو درست نمی‌خونه
**علت:** RTL زبان‌ها سخت‌تر هستند

**راه‌حل:**
1. Tesseract language pack نصب کن: `ara`, `fas`
2. دقت: ~75% (کامل نیست)
3. Fallback: از شماره استفاده میشه (`ID_123456.png`)

---

## 📖 خلاصه

✅ **Directory output** → Smart naming خودکار
✅ **File output** → اسم دقیق
✅ **mode=smart** → اجباری smart naming
✅ **OCR fail** → fallback به اسم اصلی + `_smart.png`



╔═══════════════════════════════════════════════════════════════════════╗
║                    📋 COMMAND CHEAT SHEET                             ║
╠═══════════════════════════════════════════════════════════════════════╣

🎯 BASIC SYNTAX (Original):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
python smart_crop.py <INPUT> <OUTPUT> [MARGIN] [MODE] [KERNEL]
                     ↑       ↑        ↑        ↑      ↑
                     arg1    arg2     arg3     arg4   arg5


✅ CORRECT EXAMPLES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ Smart naming (output = directory):
   python smart_crop.py input.png output/
   → output/LASTNAME_FIRSTNAME_ID.png

2️⃣ Exact filename:
   python smart_crop.py input.png exact.png
   → exact.png

3️⃣ Force smart naming:
   python smart_crop.py input.png output.png 20 smart
   → LASTNAME_FIRSTNAME_ID.png

4️⃣ Professional scan:
   python smart_crop.py input.png scans/ 30 scan
   → scans/LASTNAME_ID.png (enhanced)

5️⃣ Preview only:
   python smart_crop.py input.png preview.png 20 preview
   → preview.png (with overlay)

6️⃣ Current directory:
   python smart_crop.py input.png .
   → ./LASTNAME_ID.png


❌ WRONG EXAMPLES (Don't Do This!):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ python smart_crop.py input.png --smart
   Problem: --smart is treated as OUTPUT filename!
   Creates: --smart.png (wrong!)
   
✅ Fix: python smart_crop.py input.png . 20 smart
   Or:   python smart_crop.py input.png output/ 20 smart

❌ python smart_crop.py input.png
   Problem: Missing OUTPUT argument!
   Error: "Usage: ..."
   
✅ Fix: python smart_crop.py input.png .

❌ python smart_crop.py input.png output --smart
   Problem: --smart is in wrong position!
   Creates: output/ directory, ignores --smart
   
✅ Fix: python smart_crop.py input.png output/ 20 smart


🎨 EASY MODE (Using scan.py wrapper):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ python scan.py input.png
   → scans/LASTNAME_ID.png (auto)

✅ python scan.py input.png --output=docs/
   → docs/LASTNAME_ID.png

✅ python scan.py input.png --output=exact.png
   → exact.png

✅ python scan.py input.png --smart --margin=30
   → scans/LASTNAME_ID.png (with margin)

✅ python scan.py input.png --scan
   → scans/LASTNAME_ID.png (enhanced quality)


📊 ARGUMENT POSITIONS (Important!):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Position 1 (sys.argv[1]): INPUT file (required)
Position 2 (sys.argv[2]): OUTPUT file/dir (required)
Position 3 (sys.argv[3]): MARGIN pixels (optional, default: 20)
Position 4 (sys.argv[4]): MODE (optional, default: crop)
                         Values: crop, smart, scan, preview, tuning
Position 5 (sys.argv[5]): KERNEL size (optional, default: 9)


🔧 MODE VALUES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

crop    = Standard crop + perspective correction
smart   = Force OCR smart naming (even for file output)
scan    = Enhanced quality + auto-rotate + smart naming
preview = Show detection overlay only
tuning  = Generate debug samples (for developers)


💡 QUICK TIPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Want smart naming? Use directory: python smart_crop.py in.png out/
• Want exact name? Use filename: python smart_crop.py in.png exact.png
• Current dir shortcut: Use dot: python smart_crop.py in.png .
• Batch processing: for f in *.png; do python smart_crop.py "$f" scans/; done
• Need help? Run: python smart_crop.py (without args)


🐛 COMMON MISTAKES → SOLUTIONS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mistake: amir img crop file.png --smart
Fix:     python smart_crop.py file.png . 20 smart

Mistake: python smart_crop.py file.png
Fix:     python smart_crop.py file.png .

Mistake: python smart_crop.py file.png dir --smart
Fix:     python smart_crop.py file.png dir/ 20 smart

Mistake: Creates --smart.png file
Fix:     You put --smart in OUTPUT position! Use position 4 (mode)


╚═══════════════════════════════════════════════════════════════════════╝