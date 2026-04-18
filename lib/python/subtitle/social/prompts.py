import os
import re
from typing import Any, Dict, List, Optional, Tuple

from subtitle.config import get_language_config


def _to_ascii_digits(text: str) -> str:
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    out = text
    for i, d in enumerate(persian_digits):
        out = out.replace(d, str(i))
    for i, d in enumerate(arabic_digits):
        out = out.replace(d, str(i))
    return out


def _is_short_video(duration: str, threshold_minutes: int = 15) -> bool:
    if not duration:
        return False
    txt = _to_ascii_digits(str(duration)).lower()

    hhmmss = re.findall(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", txt)
    if hhmmss:
        h, m, s = hhmmss[0]
        hours = int(h) if len(h) > 1 and int(h) >= 1 else 0
        mins = int(m)
        secs = int(s or 0)
        total_min = (hours * 60) + mins + (secs / 60.0)
        return total_min < threshold_minutes

    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes|minute\(s\)|دقیقه)", txt)
    if m:
        return float(m.group(1)) < threshold_minutes

    h = re.search(r"(\d+(?:\.\d+)?)\s*(?:hour|hours|hr|hrs|ساعت)", txt)
    if h:
        return (float(h.group(1)) * 60.0) < threshold_minutes

    return False


def _clip_hint(text: str, max_len: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def _format_followers(value: Any) -> Tuple[str, str]:
    if isinstance(value, (int, float)) and int(value) > 0:
        c = int(value)
        return f"{c:,}", f"{c:,}"

    raw = str(value or "").strip()
    if raw and raw.lower() not in {"none", "null", "nan", "0"}:
        digits = re.sub(r"[^0-9]", "", raw)
        if digits:
            c = int(digits)
            return f"{c:,}", f"{c:,}"
        return raw, raw

    return "نامشخص", "unknown"


def _extract_guest_name(title: str, description: str) -> str:
    desc = str(description or "")
    patterns = [
        r"\b([A-Z][A-Za-z'\.-]+(?:\s+[A-Z][A-Za-z'\.-]+){1,3})\s+is\s+(?:an?|the)\b",
        r"\bFollow\s+([A-Z][A-Za-z'\.-]+(?:\s+[A-Z][A-Za-z'\.-]+){0,3})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, desc)
        if m:
            return m.group(1).strip()

    # Fallback: use first chunk of the title.
    title_clean = re.sub(r"\s+", " ", str(title or "")).strip()
    if not title_clean:
        return ""
    for sep in (":", "|", "-"):
        if sep in title_clean:
            return title_clean.split(sep, 1)[0].strip()
    return title_clean


def get_post_prompt(
    processor,
    platform: str,
    title: str,
    srt_lang_name: str,
    full_text: str,
    prompt_file: Optional[str] = None,
    srt_lang: str = "fa",
    duration: str = "",
    all_srt_langs: Optional[List[str]] = None,
    source_lang: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Return (system_prompt, user_prompt) tuple for the given platform."""
    file_user_prompt: Optional[str] = None

    candidates = []
    if prompt_file:
        candidates.append(os.path.expandvars(os.path.expanduser(prompt_file)))
    candidates.append(os.path.expanduser(f"~/.amir/prompts/{platform}.txt"))

    for p in candidates:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    file_user_prompt = f.read().format(
                        title=title,
                        srt_lang_name=srt_lang_name,
                        full_text=full_text,
                    )
                processor.logger.info(f"📄 Using custom prompt file for {platform}: {p}")
                break
            except KeyError as ke:
                processor.logger.warning(f"⚠️ Prompt file {p} has unknown variable {ke} — using built-in.")
            except Exception as pe:
                processor.logger.warning(f"⚠️ Could not read prompt file {p}: {pe} — using built-in.")

    all_langs = all_srt_langs or [srt_lang]

    def lang_name_fa(code: str) -> str:
        fa_names = {
            "fa": "فارسی",
            "en": "انگلیسی",
            "de": "آلمانی",
            "fr": "فرانسوی",
            "ar": "عربی",
            "es": "اسپانیایی",
            "it": "ایتالیایی",
            "ru": "روسی",
            "zh": "چینی",
            "ja": "ژاپنی",
            "ko": "کره‌ای",
            "tr": "ترکی",
            "pt": "پرتغالی",
            "nl": "هلندی",
            "pl": "لهستانی",
            "sv": "سوئدی",
        }
        return fa_names.get(code, get_language_config(code).name)

    subs_line_fa = "با زیرنویس " + " و ".join(lang_name_fa(l) for l in all_langs)
    subs_line_en = "With " + " & ".join(get_language_config(l).name for l in all_langs) + " subtitles"
    dur = duration if duration else "(از تایم‌استمپ محاسبه کن)"
    dur_en = duration if duration else "(calculate from SRT)"
    src_lang_fa = lang_name_fa(source_lang) if source_lang else ""
    src_info_fa = f"زبان ویدیو: {src_lang_fa}" if src_lang_fa else ""
    src_info_en = f"Video language: {get_language_config(source_lang).name}" if source_lang else ""
    short_video = _is_short_video(duration)
    hashtags_lang_fa = src_lang_fa if src_lang_fa else "زبان اصلی ویدیو"
    hashtags_lang_en = get_language_config(source_lang).name if source_lang else "the original video language"

    metadata = metadata or {}
    host_name = str(metadata.get("uploader") or metadata.get("channel") or "").strip()
    channel_name = str(metadata.get("channel") or host_name or "").strip()
    followers_fa, followers_en = _format_followers(
        metadata.get("channel_follower_count") or metadata.get("subscriber_count")
    )
    guest_hint = _extract_guest_name(title, str(metadata.get("description") or ""))
    description_hint = _clip_hint(str(metadata.get("description") or ""))

    host_name_fa = host_name or "نامشخص"
    channel_name_fa = channel_name or "نامشخص"
    guest_hint_fa = guest_hint or "نامشخص"
    host_name_en = host_name or "unknown"
    channel_name_en = channel_name or "unknown"
    guest_hint_en = guest_hint or "unknown"
    description_hint = description_hint or "unknown"

    telegram_intro_fa = (
        "پست باید دقیقاً با این ۴ خط شروع شود (قبل از هر بخش دیگر):\n"
        "🎙️ میزبان و کانال: [نام میزبان] | [نام کانال]\n"
        "📊 دنبال‌کننده‌ها و سوابق میزبان: [تعداد دنبال‌کننده] | [یک جمله درباره سوابق میزبان]\n"
        "👤 مهمان اصلی: [نام مهمان اصلی]\n"
        "🏅 سوابق مهمان: [یک جمله درباره جایگاه/سوابق مهمان]\n\n"
        "داده‌های مرجع برای همین ۴ خط (اگر فیلدی نبود «نامشخص» بنویس و چیزی نساز):\n"
        f"- میزبان: {host_name_fa}\n"
        f"- کانال: {channel_name_fa}\n"
        f"- تعداد دنبال‌کننده: {followers_fa}\n"
        f"- مهمان احتمالی: {guest_hint_fa}\n"
        f"- توضیح/بیوی ویدیو: {description_hint}\n"
    )

    telegram_intro_en = (
        "The post MUST start with these exact 4 lines (before any other section):\n"
        "🎙️ Host & Channel: [host name] | [channel name]\n"
        "📊 Host Reach & Background: [follower count] | [one sentence host background]\n"
        "👤 Main Guest: [primary guest name]\n"
        "🏅 Guest Background: [one sentence guest credentials/background]\n\n"
        "Reference data for these 4 lines (if missing, write 'unknown' and do not invent):\n"
        f"- Host: {host_name_en}\n"
        f"- Channel: {channel_name_en}\n"
        f"- Followers: {followers_en}\n"
        f"- Possible main guest: {guest_hint_en}\n"
        f"- Video bio/description: {description_hint}\n"
    )

    if platform == "telegram":
        if srt_lang == "fa":
            system = (
                "You write structured Telegram posts in fluent Persian (Farsi) for a technology and AI channel. "
                "Your style is analytical and informative — no hype, no promotional language, no superlatives. "
                "Summarise facts and ideas from the content objectively, as a researcher or journalist would. "
                "Do NOT translate word-for-word — extract key insights and write concisely. "
                "STRICTLY follow the exact format template provided. "
                "NEVER use markdown syntax like ** or __ — Telegram does not render them."
            )
            if short_video:
                user = file_user_prompt or (
                    f"{telegram_intro_fa}\n"
                    f"برای ویدیوی کوتاه (کمتر از ۱۵ دقیقه) فقط یک خلاصه کوتاه بنویس. هیچ بخش bullet یا قالب بلند ننویس.\n\n"
                    f"📽️ [عنوان]\n"
                    f"⏱️ مدت: {dur}\n"
                    f"🧾 خلاصه کوتاه: [یک پاراگراف ۳ تا ۵ جمله‌ای از محتوای ویدیو]\n\n"
                    f"#[هشتگ۱] #[هشتگ۲] #[هشتگ۳] #[هشتگ۴] #[هشتگ۵]\n\n"
                    f"قانون مهم: همان ۴ خط معرفی میزبان/مهمان باید ابتدای پست باشد.\n"
                    f"قانون مهم: همه هشتگ‌ها باید به زبان اصلی ویدیو باشند ({hashtags_lang_fa}).\n\n"
                    f"اطلاعات ویدیو:\n"
                    f"عنوان اصلی: {title}\n"
                    f"مدت: {dur}\n"
                    + (f"{src_info_fa}\n" if src_info_fa else "")
                    + f"زبان‌های زیرنویس: {', '.join(lang_name_fa(l) for l in all_langs)}\n\n"
                    f"محتوای زیرنویس:\n{full_text}"
                )
            else:
                user = file_user_prompt or (
                    f"{telegram_intro_fa}\n"
                    f"یک پست تلگرام بنویس دقیقاً بر اساس این قالب:\n\n"
                    f"📽️ [عنوان کامل ویدیو به فارسی — ترجمه طبیعی، نه تحت‌اللفظی]\n"
                    f"{subs_line_fa}\n\n"
                    f"🔴 «[یک نقل‌قول مستقیم یا گزاره‌ی کلیدی از ویدیو — بدون تعریف و تمجید]»\n\n"
                    f"[یک پاراگراف ۲ جمله‌ای توصیفی — چه کسی، درباره چه چیزی، در چه زمینه‌ای — بدون ارزش‌گذاری]\n\n"
                    f"🚨 نکات مهم:\n\n"
                f"🔹 [موضوع اول]: [یک جمله توصیفی ≤۱۲ کلمه]\n\n"
                f"🔹 [موضوع دوم]: [یک جمله توصیفی ≤۱۲ کلمه]\n\n"
                f"🔹 [موضوع سوم]: [یک جمله توصیفی ≤۱۲ کلمه]\n\n"
                f"🔹 [موضوع چهارم]: [یک جمله توصیفی ≤۱۲ کلمه]\n\n"
                f"✨ [یک جمله — موضوع اصلی این ویدیو در یک خط]\n\n"
                f"⏱️ مدت: {dur}\n\n"
                f"#[هشتگ۱] #[هشتگ۲] #[هشتگ۳] #[هشتگ۴] #[هشتگ۵]\n\n"
                f"اطلاعات ویدیو:\n"
                f"عنوان اصلی: {title}\n"
                f"مدت: {dur}\n"
                + (f"{src_info_fa}\n" if src_info_fa else "")
                + f"زبان‌های زیرنویس: {', '.join(lang_name_fa(l) for l in all_langs)}\n\n"
                f"محتوای زیرنویس:\n{full_text}\n\n"
                f"⛔ قوانین اجباری — تخطی از اینها مجاز نیست:\n"
                f"① همه بخش‌های قالب را بنویس: 🔴 + پاراگراف + 🚨 (۴ بخش 🔹) + ✨ + ⏱️ + هشتگ‌ها\n"
                f"② هرگز بخشی را حذف نکن\n"
                f"③ دقیقاً ۴ بخش 🔹\n"
                f"④ ⏱️ مدت را دقیقاً همان‌طور که در اطلاعات ویدیو آمده بنویس\n"
                f"⑤ ۵ هشتگ مرتبط\n"
                f"⑥ نقل‌قول داخل « »\n"
                f"⑦ بین هر بخش یک خط خالی\n"
                f"⑧ بدون markdown (نه ** نه __ نه *)\n"
                f"⑨ کل پست فارسی؛ اما هشتگ‌ها حتماً باید به زبان اصلی ویدیو باشند ({hashtags_lang_fa})\n"
                f"⑩ هر 🔹 باید کوتاه باشد — حداکثر ۱۲ کلمه\n"
                f"⑪ هدف ۸۵۰–۹۵۰ کاراکتر — با کوتاه کردن هر بخش به این محدوده برس. فراتر رفتن از ۱۰۲۴ کاراکتر ممنوع است.\n"
                f"⑫ پست باید دقیقاً با ۴ خط معرفی میزبان/کانال و مهمان شروع شود."
            )
        else:
            lang_en = get_language_config(srt_lang).name
            system = (
                f"You write structured Telegram posts in fluent {lang_en} for a technology and AI channel. "
                "Your style is analytical and factual — no hype, no promotional language, no superlatives. "
                "Summarise facts and ideas from the content objectively, as a researcher or journalist would. "
                "Do NOT translate word-for-word — extract key insights and write concisely. "
                "STRICTLY follow the exact format template provided. "
                "NEVER use markdown syntax like ** or __ — Telegram does not render them."
            )
            duration_line = f"⏱️ Duration: {duration}" if duration else "⏱️ Duration: [read from SRT timestamps]"
            if short_video:
                user = file_user_prompt or (
                    f"{telegram_intro_en}\n"
                    f"For short videos (under 15 minutes), write only a concise summary post. Do NOT use the long multi-section template.\n\n"
                    f"📽️ [Title in {lang_en}]\n"
                    f"⏱️ Duration: {dur_en}\n"
                    f"🧾 Short Summary: [one concise paragraph, 3-5 sentences]\n\n"
                    f"#[hashtag1] #[hashtag2] #[hashtag3] #[hashtag4] #[hashtag5]\n\n"
                    f"Important rule: keep the 4 host/guest intro lines at the very top.\n"
                    f"Important rule: all hashtags MUST be in the original video language ({hashtags_lang_en}).\n\n"
                    f"Video info:\n"
                    f"Original title: {title}\n"
                    f"Duration: {dur_en}\n"
                    + (f"{src_info_en}\n" if src_info_en else "")
                    + f"Subtitle languages: {', '.join(all_langs)}\n\n"
                    f"Subtitle content:\n{full_text}"
                )
            else:
                user = file_user_prompt or (
                    f"{telegram_intro_en}\n"
                    f"Write a Telegram post following this EXACT format:\n\n"
                    f"📽️ [Full video title in {lang_en} — natural translation, not literal]\n"
                    f"{subs_line_en}\n\n"
                    f"🔴 «[A direct quote or key factual statement from the video — no praise or hype]»\n\n"
                    f"[1–2 sentences: who, about what, in what context — descriptive, no value judgements]\n\n"
                    f"🚨 Key points:\n\n"
                f"🔹 [Topic 1]: [one descriptive sentence ≤12 words]\n\n"
                f"🔹 [Topic 2]: [one descriptive sentence ≤12 words]\n\n"
                f"🔹 [Topic 3]: [one descriptive sentence ≤12 words]\n\n"
                f"🔹 [Topic 4]: [one descriptive sentence ≤12 words]\n\n"
                f"✨ [One sentence: what is the main subject of this video]\n\n"
                f"{duration_line}\n\n"
                f"#[hashtag1] #[hashtag2] #[hashtag3] #[hashtag4] #[hashtag5]\n\n"
                f"Video info:\n"
                f"Original title: {title}\n"
                f"Duration: {dur_en}\n"
                + (f"{src_info_en}\n" if src_info_en else "")
                + f"Subtitle languages: {', '.join(all_langs)}\n\n"
                f"Subtitle content:\n{full_text}\n\n"
                f"⛔ MANDATORY RULES — no exceptions:\n"
                f"① Write ALL sections: 📽️ title + subtitle line + 🔴 + paragraph + 🚨 (4× 🔹) + ✨ + ⏱️ + hashtags\n"
                f"② NEVER drop a section to shorten the post\n"
                f"③ Exactly 4 bullet points (🔹) — not 3, exactly 4\n"
                f"④ ⏱️ Duration: copy it exactly from the video info above — do not omit\n"
                f"⑤ Exactly 5 relevant hashtags at the end\n"
                f"⑥ Quote inside « » — not inside \" \"\n"
                f"⑦ One blank line between every section\n"
                f"⑧ NO markdown — no ** no __ no * — Telegram renders them as literal characters\n"
                f"⑨ Entire post in {lang_en}; hashtags must be in the original video language ({hashtags_lang_en})\n"
                f"⑩ Each 🔹 must be brief — max 12 words\n"
                f"⑪ Target 850–950 characters — shorten each section to fit. NEVER exceed 1024 characters.\n"
                f"⑫ The post must start with the required 4 host/guest intro lines."
            )
        return system, user

    if platform == "youtube":
        system = (
            "You are an expert YouTube SEO specialist and video description writer. "
            "Write an optimized YouTube video description that maximizes search visibility. "
            "Use natural language rich with relevant keywords. "
            "Write in the same language as the subtitle content provided."
        )
        user = file_user_prompt or (
            f"Write an SEO-optimized YouTube video description.\n\n"
            f"Video title: {title}\n\n"
            f"Subtitle content (language: {srt_lang_name}):\n{full_text}\n\n"
            f"The description must:\n"
            f"- Start with a strong 1-2 sentence hook summarizing the video\n"
            f"- Have 3-5 bullet points of key takeaways\n"
            f"- Include a short paragraph with natural SEO keywords\n"
            f"- End with 5-10 relevant hashtags\n"
            f"- Be 150-350 words total\n"
            f"- Be written in the same language as the subtitle content"
        )
        return system, user

    if platform == "linkedin":
        system = (
            "You are a professional LinkedIn content writer for a senior tech/AI expert. "
            "Write thought-leadership posts that drive engagement from engineers, managers, and founders. "
            "Tone: authoritative but approachable. No fluff. "
            "Write in the same language as the subtitle content provided."
        )
        user = file_user_prompt or (
            f"Write a professional LinkedIn post about this video.\n\n"
            f"Video title: {title}\n\n"
            f"Subtitle content (language: {srt_lang_name}):\n{full_text}\n\n"
            f"The post must:\n"
            f"- Open with a bold insight or surprising fact from the video\n"
            f"- Share 2-3 key learnings in short punchy sentences\n"
            f"- End with a question to drive comments\n"
            f"- Include 3-5 professional hashtags\n"
            f"- Be 100-200 words"
        )
        return system, user

    raise ValueError(
        f"Unknown platform: {platform!r}. "
        "Supported: telegram, youtube, linkedin. "
        "Add new ones inside _get_post_prompt()."
    )