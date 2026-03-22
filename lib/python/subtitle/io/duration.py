from typing import Dict, List


def to_persian_digits(value) -> str:
    """Convert Arabic/Latin digits to Persian-Indic numerals (۰–۹)."""
    arabic_to_persian = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(value).translate(arabic_to_persian)


def format_total_seconds(total_sec: float, lang: str = "fa") -> str:
    """Format raw seconds into human-readable duration."""
    total_sec = int(total_sec)
    hours = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60

    if lang == "fa":
        if hours > 0:
            ret = f"{to_persian_digits(hours)} ساعت"
            if mins > 0:
                ret += f" و {to_persian_digits(mins)} دقیقه"
            return ret
        if mins > 0:
            if secs >= 30:
                return f"{to_persian_digits(mins)} دقیقه و {to_persian_digits(secs)} ثانیه"
            return f"{to_persian_digits(mins)} دقیقه"
        return f"{to_persian_digits(secs)} ثانیه"

    if hours > 0:
        ret = f"{hours} hr"
        if mins > 0:
            ret += f" {mins} min"
        return ret
    if mins > 0:
        if secs >= 30:
            return f"{mins} min {secs} sec"
        return f"{mins} min"
    return f"{secs} sec"


def srt_duration_str(entries: List[Dict], lang: str = "fa") -> str:
    """Return human-readable duration from the last SRT entry's end timestamp."""
    if not entries:
        return ""
    last_end = entries[-1]["end"]
    try:
        hms, _ms = last_end.split(",")
        h, m, s = map(int, hms.split(":"))
        total_sec = h * 3600 + m * 60 + s
        return format_total_seconds(total_sec, lang=lang)
    except Exception:
        return ""
