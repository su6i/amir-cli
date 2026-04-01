from datetime import datetime
from typing import Dict


def format_publish_date(value: str) -> str:
    """Normalize common date forms to YYYY-MM-DD (+ weekday) for post headers."""
    if not value:
        return ""
    value = str(value).strip()
    fa_weekdays = {
        0: "دوشنبه",
        1: "سه\u200cشنبه",
        2: "چهارشنبه",
        3: "پنج\u200cشنبه",
        4: "جمعه",
        5: "شنبه",
        6: "یکشنبه",
    }
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return f"{dt.strftime('%Y-%m-%d')} ({fa_weekdays.get(dt.weekday(), dt.strftime('%A'))})"
        except ValueError:
            continue
    return value


def compose_post_file_header(platform: str, metadata: Dict[str, str], fallback_title: str) -> str:
    """Human-readable header added above saved post text files."""
    title = (metadata.get("title") or fallback_title or "").strip()
    publish_date = (metadata.get("publish_date") or "").strip()
    webpage_url = (metadata.get("webpage_url") or "").strip()
    uploader = (metadata.get("uploader") or "").strip()

    lines = []
    if title:
        lines.append(title)
    if publish_date:
        if platform == "telegram":
            clean_date = publish_date.split(" ")[0]
            lines.append(f"\nDate: {clean_date}")
        else:
            lines.append(f"تاریخ انتشار: {publish_date}")
    if uploader:
        lines.append(f"\nمنتشرکننده: {uploader}")
    if webpage_url:
        lines.append(f"\nلینک مرجع:\n {webpage_url}")
    if not lines:
        return ""
    return "\n".join(lines) + "\n\n" + ("─" * 20) + "\n\n"