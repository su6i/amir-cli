from dataclasses import dataclass
from typing import Optional


@dataclass
class LanguageConfig:
    """Configuration for a specific language."""

    code: str
    name: str
    char_range: Optional[tuple] = None
    rtl: bool = False


LANGUAGE_REGISTRY = {
    # Top 25 by internet/YouTube reach (2026)
    "zh": LanguageConfig("zh", "Chinese", ("\u4e00", "\u9fff")),
    "en": LanguageConfig("en", "English"),
    "es": LanguageConfig("es", "Spanish"),
    "hi": LanguageConfig("hi", "Hindi", ("\u0900", "\u097F")),
    "ar": LanguageConfig("ar", "Arabic", ("\u0600", "\u06FF"), rtl=True),
    "bn": LanguageConfig("bn", "Bengali", ("\u0980", "\u09FF")),
    "pt": LanguageConfig("pt", "Portuguese"),
    "ru": LanguageConfig("ru", "Russian", ("\u0400", "\u04FF")),
    "ja": LanguageConfig("ja", "Japanese", ("\u3040", "\u30ff")),
    "fr": LanguageConfig("fr", "French"),
    "ur": LanguageConfig("ur", "Urdu", ("\u0600", "\u06FF"), rtl=True),
    "pa": LanguageConfig("pa", "Punjabi", ("\u0a00", "\u0a7f")),
    "vi": LanguageConfig("vi", "Vietnamese"),
    "tr": LanguageConfig("tr", "Turkish"),
    "ko": LanguageConfig("ko", "Korean", ("\uac00", "\ud7af")),
    "id": LanguageConfig("id", "Indonesian"),
    "de": LanguageConfig("de", "German"),
    "fa": LanguageConfig("fa", "Persian", ("\u0600", "\u06FF"), rtl=True),
    "gu": LanguageConfig("gu", "Gujarati", ("\u0a80", "\u0aff")),
    "it": LanguageConfig("it", "Italian"),
    "mr": LanguageConfig("mr", "Marathi", ("\u0900", "\u097f")),
    "te": LanguageConfig("te", "Telugu", ("\u0c00", "\u0c7f")),
    "ta": LanguageConfig("ta", "Tamil", ("\u0b80", "\u0bff")),
    "th": LanguageConfig("th", "Thai", ("\u0e00", "\u0e7f")),
    "ha": LanguageConfig("ha", "Hausa"),
    # Additional supported languages
    "el": LanguageConfig("el", "Greek", ("\u0370", "\u03FF")),
    "mg": LanguageConfig("mg", "Malagasy"),
    "nl": LanguageConfig("nl", "Dutch"),
    "pl": LanguageConfig("pl", "Polish"),
    "uk": LanguageConfig("uk", "Ukrainian", ("\u0400", "\u04FF")),
}


def get_language_config(lang_code: str) -> LanguageConfig:
    """Get language configuration with fallback to generic config."""

    return LANGUAGE_REGISTRY.get(lang_code, LanguageConfig(lang_code, lang_code.upper()))


def has_target_language_chars(text: str, lang_code: str) -> bool:
    """Check whether text contains characters from target language script."""

    if not text:
        return False

    lang_config = get_language_config(lang_code)
    if not lang_config.char_range:
        return True

    char_start, char_end = lang_config.char_range
    return any(char_start <= c <= char_end for c in text)
