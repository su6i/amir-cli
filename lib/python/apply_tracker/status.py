#!/usr/bin/env python3
"""Terminal status table for PhD/Job applications — color-blind friendly."""

import json
import sys
from pathlib import Path

from apply_tracker.tracker import (
    load_tracking, parse_position_md, days_left, init_tracking
)

# ── display helpers ───────────────────────────────────────────────────────────

BOLD  = "\033[1m"
DIM   = "\033[2m"
RESET = "\033[0m"
UNDERLINE = "\033[4m"


def urgency_tag(days: int | None) -> str:
    if days is None:
        return "     "
    if days <= 7:
        return f"{BOLD}[!!!]{RESET}"
    if days <= 14:
        return "[!! ]"
    if days <= 30:
        return "[!  ]"
    return "[   ]"


def days_str(days: int | None) -> str:
    if days is None:
        return "  --"
    if days < 0:
        return f"{days:4d}"
    return f"{days:3d}d"


STATUS_LABEL = {
    "found":       "found      ",
    "draft_ready": "draft ready",
    "sent":        "sent       ",
    "replied":     "replied    ",
    "bounced":     "bounced    ",
    "rejected":    "rejected   ",
    "watching":    "watching   ",
}


def format_deadline(dl: str | None) -> str:
    if not dl:
        return "   --   "
    parts = dl.split("-")
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}"
    return dl[:7]


# ── main display functions ────────────────────────────────────────────────────

def collect_entries(search_dir: Path, filter_track: str | None = None,
                    urgent_only: bool = False) -> list[dict]:
    """Collect all entries from all tracks under found/."""
    found_dir = search_dir / "found"
    if not found_dir.exists():
        return []

    entries = []
    for td in sorted(found_dir.iterdir()):
        if not td.is_dir():
            continue
        if filter_track and td.name != filter_track:
            continue

        tj = td / "tracking.json"
        if not tj.exists():
            # Auto-init if .md files exist
            mds = [f for f in td.glob("*.md") if f.stem not in
                   {"summary", "suivi_candidatures_phd", "rapport_envois"}]
            if mds:
                init_tracking(search_dir, td.name)
                if not tj.exists():
                    continue
            else:
                continue

        data = json.loads(tj.read_text())
        for pos_id, entry in data.items():
            dl = entry.get("deadline")
            d_left = days_left(dl)
            if urgent_only and (d_left is None or d_left > 14):
                continue
            entries.append({
                "id": pos_id,
                "track": td.name,
                "deadline": dl,
                "days_left": d_left,
                "fit": entry.get("fit", "?"),
                "status": entry.get("status", "found"),
                "institution": entry.get("institution", ""),
                "title": entry.get("title", pos_id),
            })

    # Sort: urgent first (by days_left), then no-deadline last
    entries.sort(key=lambda e: (
        e["days_left"] is None,
        e["days_left"] if e["days_left"] is not None else 9999
    ))
    return entries


def print_status_table(search_dir: Path, filter_track: str | None = None,
                       urgent_only: bool = False, search_type: str = "phd") -> None:
    entries = collect_entries(search_dir, filter_track, urgent_only)
    # Exclude already-handled statuses from urgent view
    if urgent_only:
        entries = [e for e in entries if e["status"] not in
                   ("sent", "replied", "rejected", "bounced")]

    if not entries:
        if urgent_only:
            print("  No urgent deadlines (≤14 days).")
        else:
            print("  No positions found. Run 'amir apply phd init' first.")
        return

    col_id   = max(len(e["id"]) for e in entries)
    col_id   = max(col_id, 20)

    header = (
        f"  {'':5}  "
        f"{'ID':<{col_id}}  "
        f"{'Deadline':8}  "
        f"{'Left':4}  "
        f"{'Fit':5}  "
        f"{'Track':<15}  "
        f"Status"
    )
    sep = "  " + "─" * (len(header) - 2)
    print()
    print(f"  {UNDERLINE}{BOLD}{'Apply Tracker':}{RESET} — "
          f"{search_type.upper()} | "
          f"{len(entries)} positions"
          + (f" | filter: {filter_track}" if filter_track else ""))
    print(sep)
    print(header)
    print(sep)

    for e in entries:
        tag = urgency_tag(e["days_left"])
        d_str = days_str(e["days_left"])
        dl_str = format_deadline(e["deadline"])
        status = STATUS_LABEL.get(e["status"], e["status"])

        line = (
            f"  {tag}  "
            f"{e['id']:<{col_id}}  "
            f"{dl_str:8}  "
            f"{d_str:4}  "
            f"{e['fit']:5}  "
            f"{e['track']:<15}  "
            f"{status}"
        )

        if e["days_left"] is not None and e["days_left"] <= 7:
            print(BOLD + line + RESET)
        else:
            print(line)

    print(sep)
    # Summary line
    urgent_count = sum(1 for e in entries if e["days_left"] is not None and e["days_left"] <= 14)
    sent_count   = sum(1 for e in entries if e["status"] == "sent")
    draft_count  = sum(1 for e in entries if e["status"] == "draft_ready")
    replied_count= sum(1 for e in entries if e["status"] == "replied")
    print(f"  {BOLD}{urgent_count} urgent{RESET} (≤14d) | "
          f"{draft_count} draft ready | "
          f"{sent_count} sent | "
          f"{replied_count} replied\n")


def print_urgent_header(search_dir: Path, search_type: str = "phd") -> None:
    """One-line urgent alert — shown at start of every `amir apply` call."""
    entries = [
        e for e in collect_entries(search_dir, urgent_only=True)
        if e["status"] not in ("sent", "replied", "rejected", "bounced")
    ]
    if not entries:
        return

    parts = []
    for e in entries:
        dl = e["days_left"]
        if dl is None:
            continue
        if dl <= 7:
            tag = f"[!!!{dl}d]"
        else:
            tag = f"[!!{dl}d]"
        parts.append(f"{tag} {e['id']}")

    if parts:
        label = f"{search_type.upper()} Alert"
        print(f"  {BOLD}⚠  {label}:{RESET} " + "  ".join(parts[:4]))


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("search_dir")
    p.add_argument("--track", default=None)
    p.add_argument("--urgent-header", action="store_true")
    p.add_argument("--urgent", action="store_true")
    p.add_argument("--type", dest="search_type", default="phd")
    args = p.parse_args()

    sd = Path(args.search_dir)

    if args.urgent_header:
        print_urgent_header(sd, args.search_type)
    elif args.urgent:
        print_status_table(sd, args.track, urgent_only=True, search_type=args.search_type)
    else:
        print_status_table(sd, args.track, search_type=args.search_type)
