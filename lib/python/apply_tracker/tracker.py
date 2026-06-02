#!/usr/bin/env python3
"""tracking.json CRUD — source of truth for application status."""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

VALID_STATUSES = {"found", "draft_ready", "sent", "replied", "bounced", "rejected", "watching"}


# ── tracking.json helpers ─────────────────────────────────────────────────────

def tracking_path(track_dir: Path) -> Path:
    return track_dir / "tracking.json"


def load_tracking(track_dir: Path) -> dict:
    p = tracking_path(track_dir)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def save_tracking(track_dir: Path, data: dict) -> None:
    p = tracking_path(track_dir)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def get_entry(track_dir: Path, pos_id: str) -> dict | None:
    data = load_tracking(track_dir)
    return data.get(pos_id)


def update_entry(track_dir: Path, pos_id: str, **fields) -> dict:
    data = load_tracking(track_dir)
    entry = data.setdefault(pos_id, {"status": "found"})
    for k, v in fields.items():
        entry[k] = v
    save_tracking(track_dir, data)

    # Dual-write to SQLite
    try:
        from apply_tracker.db import get_db, update_status as db_update
        # Infer base_dir and kind from track_dir path
        # track_dir = .../PhD-Search/found/ai_general
        search_dir = track_dir.parent.parent
        base_dir   = search_dir.parent
        kind = "phd" if "phd" in search_dir.name.lower() else "job"
        conn = get_db(base_dir)
        db_update(conn, pos_id, kind, **{k: v for k, v in fields.items()})
    except Exception:
        pass

    return entry


# ── position .md parser ───────────────────────────────────────────────────────

def parse_position_md(md_path: Path) -> dict:
    """Extract metadata from a position markdown file."""
    text = md_path.read_text(errors="replace")
    info: dict = {"id": md_path.stem, "title": md_path.stem}

    # Title from first H1
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        info["title"] = m.group(1).strip()

    # Also check for "**Fit global : 8/10**" style inline bold
    m_fit = re.search(r"\*\*Fit\s+\w*\s*[:：]\s*(\d+/\d+)\*\*", text, re.IGNORECASE)
    if m_fit:
        info["fit"] = m_fit.group(1)

    # Parse markdown table rows: | **Key** | Value |
    for row in re.finditer(r"\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|", text):
        key = row.group(1).strip().lower()
        val = row.group(2).strip().strip("*")
        if "deadline" in key:
            info["deadline"] = _parse_deadline(val)
        elif "fit" in key or "score" in key:
            info["fit"] = val.replace("*", "").strip()
        elif "titre" in key or "title" in key:
            info["title"] = val
        elif "université" in key or "university" in key or "institution" in key:
            info["institution"] = val
        elif "langue" in key and "candidature" in key:
            info["lang"] = val
        elif "pays" in key:
            info["country"] = val
        elif "directeur" in key or "supervisor" in key or "contact" in key:
            info["contact"] = val
        elif "lien" in key or "link" in key:
            info["link"] = val
        elif "financement" in key or "funding" in key:
            info["funding"] = val

    return info


def _parse_deadline(val: str) -> str | None:
    """Parse deadline strings like '07/06/2026', 'Juillet 2026', 'En continu'."""
    val = val.strip()
    # DD/MM/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", val)
    if m:
        try:
            d = datetime.strptime(val[:10], "%d/%m/%Y")
            return d.strftime("%Y-%m-%d")
        except ValueError:
            pass
    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", val)
    if m:
        return val[:10]
    # "Juillet 2026" style
    months = {
        "janvier": 1, "février": 2, "mars": 3, "avril": 4,
        "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    # Try to find "9 juin 2026" or "le 9 juin 2026" patterns (with day)
    for name, num in months.items():
        m2 = re.search(rf"\b(\d{{1,2}})\s+{name}\s+(\d{{4}})\b", val, re.IGNORECASE)
        if m2:
            day, year = int(m2.group(1)), int(m2.group(2))
            return f"{year}-{num:02d}-{day:02d}"
    # Month + year only (no day)
    for name, num in months.items():
        m2 = re.search(rf"\b{name}\b.*?(\d{{4}})", val, re.IGNORECASE)
        if m2:
            return f"{m2.group(1)}-{num:02d}-01"
    return None  # "En continu", "À définir", etc.


def days_left(deadline_str: str | None) -> int | None:
    if not deadline_str:
        return None
    try:
        d = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        return (d - date.today()).days
    except ValueError:
        return None


# ── init tracking.json from existing files ────────────────────────────────────

def init_tracking(search_dir: Path, track: str) -> int:
    """Scan found/<track>/*.md and applied/ to build initial tracking.json."""
    track_dir = search_dir / "found" / track
    applied_dir = search_dir / "applied"

    if not track_dir.exists():
        print(f"Track dir not found: {track_dir}", file=sys.stderr)
        return 1

    data: dict = {}
    skip_prefixes = ("summary", "suivi_", "rapport_", "template_")

    for md_file in sorted(track_dir.glob("*.md")):
        stem_lower = md_file.stem.lower()
        if any(stem_lower.startswith(p) for p in skip_prefixes):
            continue

        info = parse_position_md(md_file)
        pos_id = md_file.stem

        # Determine status from applied/ folder
        applied_folder = applied_dir / pos_id
        status = "found"

        if applied_folder.exists():
            has_pdf = any(applied_folder.glob("*.pdf"))
            has_draft = (applied_folder / "email_draft.md").exists()
            if has_pdf:
                status = "sent"
            elif has_draft:
                status = "draft_ready"

        data[pos_id] = {
            "status": status,
            "track": track,
            "deadline": info.get("deadline"),
            "fit": info.get("fit", "?"),
            "title": info.get("title", pos_id),
            "institution": info.get("institution", ""),
            "lang": info.get("lang", ""),
            "contact": info.get("contact", ""),
            "link": info.get("link", ""),
            "sent_date": None,
            "reply_date": None,
            "reply_type": None,
            "notes": "",
        }

    save_tracking(track_dir, data)
    return len(data)


# ── CLI entry point ───────────────────────────────────────────────────────────

def cmd_sent(search_dir: Path, pos_id: str, sent_date: str | None, track: str | None) -> None:
    track_dir = _find_track_dir(search_dir, pos_id, track)
    if not track_dir:
        print(f"ERROR: position '{pos_id}' not found in any track", file=sys.stderr)
        sys.exit(1)

    today = sent_date or date.today().isoformat()
    update_entry(track_dir, pos_id, status="sent", sent_date=today)
    print(f"✓  {pos_id} marked as sent ({today})")


def cmd_reply(search_dir: Path, pos_id: str, reply_type: str, notes: str, track: str | None) -> None:
    track_dir = _find_track_dir(search_dir, pos_id, track)
    if not track_dir:
        print(f"ERROR: position '{pos_id}' not found", file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    update_entry(track_dir, pos_id, status="replied", reply_date=today,
                 reply_type=reply_type, notes=notes)
    print(f"✓  {pos_id} reply recorded: {reply_type} ({today})")


def _find_track_dir(search_dir: Path, pos_id: str, track: str | None) -> Path | None:
    if track:
        td = search_dir / "found" / track
        if (td / "tracking.json").exists():
            data = load_tracking(td)
            if pos_id in data:
                return td
        return None

    found_dir = search_dir / "found"
    for td in found_dir.iterdir():
        if not td.is_dir():
            continue
        tj = td / "tracking.json"
        if tj.exists() and pos_id in json.loads(tj.read_text()):
            return td
    return None


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("search_dir")
    sub = p.add_subparsers(dest="cmd")

    s_init = sub.add_parser("init")
    s_init.add_argument("track")

    s_sent = sub.add_parser("sent")
    s_sent.add_argument("pos_id")
    s_sent.add_argument("--date")
    s_sent.add_argument("--track")

    s_reply = sub.add_parser("reply")
    s_reply.add_argument("pos_id")
    s_reply.add_argument("--type", required=True,
                         choices=["positive", "negative", "bounce", "info"])
    s_reply.add_argument("--notes", default="")
    s_reply.add_argument("--track")

    args = p.parse_args()
    sd = Path(args.search_dir)

    if args.cmd == "init":
        count = init_tracking(sd, args.track)
        print(f"✓  Initialized {count} entries in {args.track}/tracking.json")
    elif args.cmd == "sent":
        cmd_sent(sd, args.pos_id, args.date, args.track)
    elif args.cmd == "reply":
        cmd_reply(sd, args.pos_id, args.type, args.notes, args.track)
    else:
        p.print_help()
