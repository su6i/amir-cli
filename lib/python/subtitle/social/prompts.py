import os
from typing import List, Optional, Tuple

from subtitle.config import get_language_config


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
            user = file_user_prompt or (
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
                f"⑨ کل پست فارسی (هشتگ‌ها می‌توانند انگلیسی باشند)\n"
                f"⑩ هر 🔹 باید کوتاه باشد — حداکثر ۱۲ کلمه\n"
                f"⑪ هدف ۷۰۰–۸۵۰ کاراکتر — با کوتاه کردن هر بخش به این محدوده برس. فراتر رفتن از ۱۰۲۴ کاراکتر ممنوع است."
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
            user = file_user_prompt or (
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
                f"⑨ Entire post in {lang_en}\n"
                f"⑩ Each 🔹 must be brief — max 12 words\n"
                f"⑪ Target 700–850 characters — shorten each section to fit. NEVER exceed 1024 characters."
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