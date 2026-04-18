import re
from typing import Optional, Tuple

from openai import OpenAI


def call_llm_for_post(
    processor,
    system: str,
    user: str,
    has_gemini: bool = False,
    genai_module=None,
) -> Optional[str]:
    """Call LLM with DeepSeek -> Gemini fallback for social post generation."""
    system = system.encode("utf-8", errors="replace").decode("utf-8")
    user = user.encode("utf-8", errors="replace").decode("utf-8")
    try:
        ds_client = OpenAI(api_key=processor.api_key, base_url="https://api.deepseek.com/v1")
        resp = ds_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e1:
        processor.logger.warning(f"⚠️ DeepSeek unavailable for post: {e1} — trying Gemini…")
        try:
            if not has_gemini or genai_module is None:
                raise RuntimeError("Gemini unavailable")
            gc = genai_module.Client(api_key=processor.google_api_key)
            gresp = gc.models.generate_content(
                model="gemini-2.0-flash",
                contents=[f"{system}\n\n{user}"],
            )
            return gresp.text.strip()
        except Exception as e2:
            processor.logger.error(f"❌ Post generation failed: {e2}")
            return None


def sanitize_post(text: str, platform: str) -> str:
    """Post-process LLM output to enforce platform-specific formatting rules."""
    if platform == "telegram":
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.DOTALL)
        text = re.sub(r"__(.+?)__", r"\1", text, flags=re.DOTALL)
        text = re.sub(r"\*(.+?)\*", r"\1", text, flags=re.DOTALL)
        text = re.sub(r"^-{3,}\s*\n?", "", text)
        text = re.sub(r"\n?-{3,}\s*$", "", text)
        text = text.strip()
        if len(text) > 1024:
            cut = text[:1024].rfind("\n")
            if cut < 800:
                cut = text[:1024].rfind(" ")
            text = text[: cut if cut > 500 else 1024].rstrip()
            if len(text) < len(text.strip()):
                pass
            text += "..." if len(text) < 1024 else ""
    return text


def telegram_sections_complete(text: str) -> Tuple[bool, list]:
    """Return (ok, missing) for required Telegram post sections."""
    missing = []

    for marker, label in [
        ("🎙", "🎙️ host/channel intro line"),
        ("📊", "📊 host follower/background line"),
        ("👤", "👤 main guest line"),
        ("🏅", "🏅 guest background line"),
    ]:
        if marker not in text:
            missing.append(label)

    short_mode = ("🧾 خلاصه کوتاه" in text) or ("🧾 Short Summary" in text)
    if short_mode:
        if "📽️" not in text:
            missing.append("📽️ title icon")
        if "⏱" not in text:
            missing.append("⏱️ duration")
        if "🧾" not in text:
            missing.append("🧾 short summary section")
        if "#" not in text:
            missing.append("hashtags (#)")
        return (len(missing) == 0, missing)

    for marker, label in [
        ("\U0001f4fd", "📽️ title icon"),
        ("\U0001f534", "🔴 pull-quote"),
        ("\U0001f6a8", "🚨 key-points header"),
        ("\u2728", "✨ summary paragraph"),
        ("\U0001f4cc", "📌 audience line"),
        ("\u23f1", "⏱️ duration"),
    ]:
        if marker not in text:
            missing.append(label)
    bullet_count = text.count("\U0001f539")
    if bullet_count < 5:
        missing.append(f"🔹 bullet points (found {bullet_count}, need 5)")
    if "#" not in text:
        missing.append("hashtags (#)")
    return (len(missing) == 0, missing)