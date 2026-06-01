# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## قانون Merge: فقط بعد از تأیید کاربر

**هیچ‌گاه قبل از تأیید صریح کاربر merge نکن.**

روند اجباری:
1. کد را روی feature branch بنویس و commit کن
2. به کاربر بگو: **«آماده تست است — بعد از تأیید merge می‌کنم»**
3. صبر کن کاربر برنامه را تست کند و به‌صراحت تأیید کند
4. فقط بعد از تأیید: `git merge` + `git branch -d`

```bash
# ممنوع — بدون تأیید:
git checkout main && git merge feature/xyz && git branch -d feature/xyz

# درست — صبر برای تأیید، سپس merge
```

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
| `amir apply` | `lib/commands/apply.sh` | CV/CL از URL شغلی + PhD/Job tracker |
| `amir apply phd` | `lib/commands/phd.sh` | مدیریت کامل درخواست‌های دکترا |
| `amir apply job` | `lib/commands/job.sh` | مدیریت کامل درخواست‌های شغلی |
| `amir trend` / `amir research` | `lib/commands/trend.sh` | Bridge به research_toolkit |
| `amir video` | `lib/commands/video.sh` | پردازش ویدیو + دانلود |
| `amir video record` | `lib/commands/video.sh` → `video_record()` | ضبط صفحه با AVFoundation — `--list`, `--screen N`, `--audio N`, `--fps N` |
| `amir video convert` | `lib/commands/video.sh` → `video_convert()` | تبدیل container فرمت — stream-copy هوشمند، HEVC hvc1 درست handle می‌شود |
| `amir video pip` | `lib/commands/video.sh` → `video_pip()` | PiP overlay چند ویدیو با time window و مختصات |
| `amir video cut -d -d` | `lib/commands/video.sh` → `run_video_cut()` | چند برش همزمان با filter_complex یک‌پاسه |
| `amir audio` | `lib/commands/audio.sh` | پردازش صوتی — subcommandها زیر |
| `amir audio cut` | `lib/commands/audio.sh` → `audio_cut()` | برش و حذف بخش — stream copy برای trim، atrim+concat برای delete. batch: چند فایل همزمان |
| `amir audio normalize` | `lib/commands/audio.sh` → `audio_normalize()` | two-pass EBU R128 loudnorm — `--target -16` (YouTube)، `-14` (Spotify). batch |
| `amir audio fade` | `lib/commands/audio.sh` → `audio_fade()` | `--in N --out N` با afade — زمان fade-out از طول فایل محاسبه می‌شود. batch |
| `amir audio trim-silence` | `lib/commands/audio.sh` → `audio_trim_silence()` | حذف سکوت ابتدا و انتها با silenceremove+areverse. batch |
| `amir audio convert` | `lib/commands/audio.sh` → `audio_convert()` | تبدیل فرمت صوتی — `*.wav mp3` batch-friendly |
| `amir audio extract` | `lib/commands/audio.sh` → `audio_extract()` | استخراج MP3 از ویدیو. batch: `*.mp4 192` |
| `amir audio split` | `lib/commands/audio.sh` → `audio_split()` | تقسیم فایل صوتی به chunks. batch |
| `amir subtitle` | `lib/commands/subtitle.sh` | زیرنویس AI چندزبانه |
| `amir pdf` | `lib/commands/pdf.sh` | PDF با Puppeteer |
| `amir chat` | `lib/commands/chat.sh` | چت با Gemini/Gemma |
| `amir keyboard` / `amir kb` | `lib/commands/keyboard.sh` → `lib/python/keyboard_layout.py` | layout کیبرد Apple Compact — FR/EN/FA + لایه‌های `--opt`/`--shift`/`--find` |
| `amir skill` | `lib/commands/skill.sh` | مدیریت skill — `search`, `harvest`, `list`, `show` |

### ماژول apply — معماری یکپارچه

```
amir apply <cmd>
  │
  ├─ [هر اجرا] → _apply_urgent_check() → PhD/Job alert اگر deadline ≤14 روز
  │
  ├─ phd <subcmd>  → lib/commands/phd.sh → lib/python/apply_tracker/
  │                   PHD_SEARCH_DIR = $HOME/@-Amir/Apply/2026-2027/PhD-Search
  │
  ├─ job <subcmd>  → lib/commands/job.sh → lib/python/apply_tracker/
  │                   JOB_SEARCH_DIR = $HOME/@-Amir/Apply/2026-2027/Job-Search
  │
  └─ <url>/preview → ApplyForge ($APPLYFORGE_DIR, default: $HOME/@-github/ApplyForge)
```

**Subcommands مشترک PhD/Job:** `status | show | draft | sent | reply | open | init`
**فقط job:** `new | sync`

### تقسیم‌وظیفه AI در apply tracker

| کار | مدل | نحوه اجرا |
|-----|-----|-----------|
| تولید draft ایمیل | DeepSeek v4-flash | `amir apply phd draft <id>` از ترمینال |
| بهبود/بازبینی draft | Claude Sonnet | در این Claude Code session |
| ایجاد Gmail draft | Gmail MCP | در این Claude Code session |
| sync ایمیل کاری | Gmail MCP | در این Claude Code session |
| جستجو استاد/شرکت | Web search MCP | در این Claude Code session |

**قانون sync — اجباری:** وقتی کاربر گفت "sync new positions":
1. Gmail MCP → `list_drafts` با query `AMIR-SYNC`
2. محتوای draft را بخوان (`get_thread` یا از `plaintextBody`)
3. محتوا را در `$HOME/@-Amir/Apply/2026-2027/sync_queue.txt` ذخیره کن
4. `amir apply sync` را اجرا کن (فایل‌های .md + tracking.json ساخته می‌شوند)
5. **Draft را به TRASH بفرست** با `label_message(messageId, ["TRASH"])` ← این مرحله اجباری است
6. نتیجه را گزارش بده (X موقعیت اضافه شد)

**نکته معماری:** `sync.py` به Gmail MCP دسترسی ندارد — مرحله ۵ (حذف draft) همیشه باید در Claude Code session انجام شود.

**قانون apply — اجباری:** وقتی کاربر گفت "برای X اپلای کن" یا "این draft رو بازبینی کن" → Claude Sonnet مستقیماً:
1. `amir apply phd show <id>` را اجرا می‌کند یا فایل را می‌خواند
2. **قانون supervisor research (اجباری برای PhD):** قبل از نوشتن هر ایمیل PhD:
   - `tracking.json` را بخوان → آیا `supervisor.gender` و `supervisor.key_papers` موجود است؟
   - اگر نه: web search کن (نام + institution)، جنسیت/عنوان/مقالات اخیر را پیدا کن
   - نتیجه را در `tracking.json` زیر کلید `supervisor` ذخیره کن
   - هرگز "Madame, Monsieur" عمومی ننویس — همیشه "Monsieur X" یا "Madame X" دقیق
   - حداقل یک مقاله‌ی اخیر supervisor را در ایمیل نام ببر
3. draft با کیفیت بالا می‌نویسد یا بهبود می‌دهد (با CLIL/project angle اگر مرتبط است)
4. با Gmail MCP یک Gmail draft می‌سازد (با ضمیمه‌های درست)

**schema supervisor در tracking.json:**
```json
"supervisor": {
  "name": "Tiago de Lima",
  "gender": "M",
  "title": "Maître de conférences HDR",
  "salutation": "Monsieur de Lima",
  "email": "delima@cril-lab.fr",
  "research_areas": ["Dynamic Epistemic Logic", "belief revision", "multi-agent"],
  "key_papers": ["Checking Agent Intentions in Games (ICTAI 2021)", "..."],
  "workshops": ["MAFTEC + IA & Jeux (Arras, juillet 2026)"],
  "researched_date": "YYYY-MM-DD"
}
```

### قانون One-Folder (اجباری)
هر اپلای PhD باید **یک پوشه** داشته باشد که همه چیز در آن باشد:
```
$HOME/@-Amir/Apply/2026-2027/PhD-Search/applied/<pos_id>/
├── Amir_SHIRALI-POUR-CV_PhD_<lang>.pdf              ← رزومه از pipeline
├── Amir_SHIRALI-POUR-LettreMotivation_<pos>_fr.pdf  ← انگیزه‌نامه
├── JobPosting_<pos_id>.md                           ← توضیحات آگهی
├── email_draft.md                                   ← متن ایمیل draft
└── Recommandation_*.pdf                             ← توصیه‌نامه‌ها
```
دستور ساخت این پوشه: `amir apply phd lettre <id>`

### ساختار دایرکتوری Apply tracker

```
$HOME/@-Amir/Apply/2026-2027/
├── PhD-Search/found/ai_general/tracking.json   ← source of truth
├── PhD-Search/found/ai_finance/tracking.json
├── PhD-Search/applied/<position-id>/email_draft.md
├── Job-Search/found/<track>/tracking.json
└── Job-Search/applied/<position-id>/email_draft.md
```

**tracking.json statuses:** `found → draft_ready → sent → replied/bounced/rejected/watching`

- **`APPLYFORGE_DIR`** — می‌توان override کرد: `export APPLYFORGE_DIR=/path/to/ApplyForge`
- **`--color blue`** — پیش‌فرض برای sidebar آبی کم‌رنگ altacv (`E6F0FA`)؛ با `--color <other>` قابل override است
- **subcommand preview:** `amir apply preview [--role ai|it|phd] [--lang fr|en] [--color ...]`

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
| `lib/commands/skill.sh` | `amir skill` — search/harvest/list/show برای skill management از GitHub |
| `completions/_amir` | Zsh autocompletion — شامل `trend`، `video record`، `skill` و تمام آپشن‌هایشان |

---

## تصمیمات این session (30 مه 2026) — بخش دوم

### amir skill — مدیریت skill از GitHub

دستور جدید `amir skill` با چهار subcommand:

```bash
amir skill search "persian tts" --min-stars 500   # جستجوی GitHub
amir skill harvest "fish speech tts" --pick 5      # fetch + ساخت skill file
amir skill list --grep video                        # لیست skill های موجود
amir skill show opensource-tts                      # نمایش محتوا
```

**قانون harvest:** فقط از repo‌هایی که واقعاً fetch شده‌اند skill بساز — نه از دانش خودت. وقتی `claude --print` در دسترس نیست، محتوای raw README ذخیره می‌شود.

**SKILL_DIR resolution:** از `AMIR_ROOT` → `BASH_SOURCE` → fallback hardcoded. اگر در background خراب شد، از Agent مستقیم استفاده کن.

### skill های جدید این session (از GitHub fetch شده)

| فایل | منبع | کاربرد در pipeline |
|---|---|---|
| `obs-studio.md` | upgradeQ/OBS + obsproject/websocket | ضبط و اتوماسیون |
| `davinci-resolve-scripting.md` | X-Raym gist + mhadifilms gist | ویرایش Python API |
| `youtube-data-api.md` | Google Developers + googleapis | آپلود + schedule |
| `auto-editor.md` | WyattBlue/auto-editor | حذف سکوت خودکار |
| `heygen-api.md` | docs.heygen.com | AI avatar |
| `youtube-automation-pipeline.md` | 4 GitHub repo | pipeline کامل |
| `ai-video-generation.md` | SDK های رسمی | RunwayML/Kling/Luma/Pika |
| `opensource-tts.md` | 5 GitHub repo | TTS رایگان |
| `fish-speech.md` | fishaudio/fish-speech | TTS با fa/fr/en |
| `gpt-sovits.md` | RVC-Boss/GPT-SoVITS | voice cloning |
| `video-effects-transitions.md` | xfade-easing + remotion | transition/intro/outro |
| `xtts-v2.md` | coqui-ai/TTS | TTS چندزبانه |
| `huggingface-tts.md` | parler-tts + MMS | MMS-fas برای فارسی |
| `persian-tts-training.md` | GitHub search + vast.ai | training guide |
| `music-generation.md` | audiocraft + Suno + Udio | موسیقی پس‌زمینه |
| `comfyui-stable-diffusion.md` | comfyanonymous/ComfyUI | thumbnail generation |
| `youtube-analytics.md` | Google Analytics API | CTR + A/B test |

### نکته TTS فارسی (مهم)
- edge-tts کیفیت تجاری ندارد — برای YouTube استفاده نکن
- بهترین راه: **GPT-SoVITS** با ۱-۵ دقیقه صدای خودت → voice clone
- **Fish Speech 1.5** هم `fa` پشتیبانی می‌کند — تست اول
- **MMS-TTS** از HuggingFace: `facebook/mms-tts-fas` — رایگان اما کیفیت پایین
- Training: vast.ai ~$1.5/hr A100 یا Google Colab Pro

### YouTube Automation Pipeline — وضعیت (آماده برای هفته بعد)

```
① Script  → screenwriting-youtube + LLM
② Voice   → Fish Speech / GPT-SoVITS (voice clone از صدای خودت)
③ Video   → ai-video-generation + video-effects-transitions
④ Music   → music-generation (MusicGen local یا Suno API)
⑤ Thumb   → comfyui-stable-diffusion + Pillow text overlay
⑥ Edit    → auto-editor (حذف سکوت) + amir video pip/concat
⑦ Sub     → amir subtitle (Whisper + DeepSeek)
⑧ Upload  → youtube-data-api (schedule + thumbnail)
⑨ Monitor → youtube-analytics (CTR + A/B test + retention)
```

---

## تصمیمات این session (30 مه 2026)

### دستورات جدید video: convert، pip، multi-delete، concat fix

#### `amir video convert`
تبدیل container فرمت بدون re-encode (stream copy). نکات معماری:
- `-movflags +faststart` برای HEVC هرگز استفاده نشود — باعث freeze در DaVinci/QuickTime می‌شود
- `hvc1` tag آیفون را **نباید** به `hev1` تغییر داد — bitstream تغییر نمی‌کند و فایل خراب می‌شود
- `--reencode` از VideoToolbox (H.264) استفاده می‌کند
- webm همیشه re-encode (VP9+Opus) — stream copy ممکن نیست
- ProRes در MP4/MKV: همیشه re-encode

#### `amir video pip`
PiP overlay با filter_complex. مثال:
```bash
amir video pip screen.mp4 \
  --pip person1.mov --start 00:01:00 --end 00:03:00 --pos tr --size 25 \
  --pip person2.mov --start 00:03:00 --end 00:05:00 --pos tl --size 25 \
  -o final.mp4
```
- موقعیت‌ها: `tl|tr|bl|br|center|X:Y`
- صدای هر pip در بازه زمانی فعالش mix می‌شود
- filter به temp file نوشته می‌شود تا quoting مشکل نداشته باشد

#### `amir video cut` — multi-delete
چند `-d` در یک pass با filter_complex:
```bash
amir video cut video.mp4 -d 00:02:10 00:02:25 -d 00:08:45 00:09:02 -o out.mp4
```
- single range: مسیر stream-copy سریع حفظ شده
- multiple ranges: filter_complex با trim+setpts+concat
- ranges قبل از اجرا sort و validate می‌شوند

#### `amir video concat` — رفع freeze با HEVC MOV
**مشکل:** `-f concat` demuxer + `setpts=PTS-STARTPTS` باعث freeze ویدیو با HEVC MOV می‌شد.
**راه‌حل:** `filter_complex` با `-i` مستقل برای هر فایل — هر codec با decoder خودش decode می‌شود.
**قانون:** `setpts/asetpts` در concat هرگز استفاده نشود روی HEVC input.

#### باگ‌های شناسایی‌شده و رفع‌شده
| باگ | علت | راه‌حل |
|-----|-----|---------|
| `--delete` infinite loop | `shift 3` وقتی arg نمانده بود | fallback به `shift 1` |
| `hvc1→hev1` tag fix غلط | bitstream بدون تبدیل → خراب | حذف tag fix، stream copy بدون دستکاری |
| `movflags +faststart` + HEVC | DaVinci و QuickTime reject | حذف faststart از stream copy |
| concat freeze با MOV | demuxer concat + HEVC decoder | filter_complex per-input |
| فریم سیاه در concat | PTS منفی انباشته از cut‌های قبلی | `avoid_negative_ts make_zero` + `-bf 0` |

---

## تصمیمات این session (29 مه 2026)

### مشکل ۷: دانلود YouTube — HTTP 500 + SABR

**علت دوگانه:**

1. **HTTP 500 (مشکل اول):** yt-dlp از `android_vr` client استفاده می‌کرد. YouTube این client را به SABR-only routing می‌کند — فرمت‌ها URL ندارند → HTTP 500.
   **راه‌حل:** مسدودسازی cookie برای YouTube URLs حذف شد. حالا Chrome cookies برای همه URLها (از جمله YouTube) اعمال می‌شود.

2. **HTTP 403 روی m3u8 fragments (مشکل دوم):** yt-dlp v2026.03.03 نمی‌توانست YouTube JS challenge را حل کند → فرمت‌های DASH (https) ناپدید می‌شدند → فقط m3u8 می‌ماند → fragment tokenها expire می‌شدند.
   **راه‌حل:** `uv tool upgrade yt-dlp` → v2026.03.17. نسخه جدید با `--remote-components ejs:github` (که قبلاً در video.sh بود) JS challenge را حل می‌کند و DASH 1080p در دسترس می‌شود.

**فایل‌های تغییریافته:** `lib/commands/video.sh` — بلاک `elif $IS_YOUTUBE_URL; then COOKIE_ARGS=()` حذف شد.

**نکته نگهداری:** اگر دانلود YouTube دوباره 360p یا خطا داد:
```bash
uv tool upgrade yt-dlp   # اول این
yt-dlp --version         # باید ≥ 2026.03.17 باشد
```

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

## تصمیمات این session (22 مه 2026)

### `amir apply` — اصلاح مسیر و پیش‌فرض رنگ

- **باگ مسیر:** `CV_DIR` به اشتباه به `$HOME/@-github/CV` اشاره می‌کرد (وجود ندارد). اصلاح شد به `${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}`.
- **پیش‌فرض `--color blue`:** اگر `--color` پاس نشود، `apply.sh` خودش `--color blue` را به args اضافه می‌کند تا sidebar altacv رنگ آبی کم‌رنگ (`E6F0FA`) داشته باشد.

---

## پروژه وابسته: CV / LinkedIn Content

مسیر: `$HOME/@-github/ApplyForge` — مستندات کامل در `ApplyForge/CLAUDE.md`

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

## قوانین Agent

### قوانین مشترک (از agent-constitution)
تمام فایل‌های `.agent/constitution/rules/` را بخوان و رعایت کن.
آپدیت: `git submodule update --remote .agent/constitution`

### قوانین اختصاصی این پروژه
تمام فایل‌های `.agent/local-rules/` را بخوان.
در صورت تناقض، **قوانین اختصاصی (local-rules) اولویت دارند.**

