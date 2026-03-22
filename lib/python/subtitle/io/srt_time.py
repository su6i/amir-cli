from datetime import timedelta


def parse_to_sec(t_str: str) -> float:
    """Convert SRT time format to seconds."""
    try:
        h, m, s_ms = t_str.replace(",", ".").split(":")
        s, ms = s_ms.split(".")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    except Exception:
        return 0.0


def format_time(seconds: float) -> str:
    """Convert seconds into SRT time format."""
    td = timedelta(seconds=float(seconds))
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def normalize_digits(text: str) -> str:
    """Normalize Persian/Arabic-Indic digits to ASCII for robust parsing."""
    if not text:
        return text
    return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
