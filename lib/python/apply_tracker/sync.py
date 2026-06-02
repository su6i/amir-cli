#!/usr/bin/env python3
"""Parse [AMIR-SYNC] Gmail draft content and create position files + update tracking."""

import json
import re
import sys
from datetime import date
from pathlib import Path

from apply_tracker.tracker import load_tracking, save_tracking, _parse_deadline

TRACK_MAP = {
    "ai_ml":               ("job",  "ai_ml"),
    "devops":              ("job",  "devops"),
    "devops_alternance":   ("job",  "devops_alternance"),
    "polyvalent":          ("job",  "polyvalent"),
    "phd_ai_general":      ("phd",  "ai_general"),
    "phd_ai_finance":      ("phd",  "ai_finance"),
    # shorthand aliases
    "ai_general":          ("phd",  "ai_general"),
    "ai_finance":          ("phd",  "ai_finance"),
}

POSITION_MD_TEMPLATE = """\
# {track_label} — {title}

| Champ | Valeur |
|-------|--------|
| **Entreprise/Institution** | {institution} |
| **Titre** | {title} |
| **Lieu** | {location} |
| **Deadline** | {deadline} |
| **Lien** | {link} |
| **Contact** | {contact} |
| **Fit score** | {fit} |
| **Source** | {source} |

## Notes
Ajouté automatiquement via sync le {today}.
"""


def parse_sync_content(text: str) -> list[dict]:
    """Parse the structured block format from [AMIR-SYNC] draft."""
    positions = []
    blocks = re.split(r"\n---+\n", text.strip())

    for block in blocks:
        if not block.strip():
            continue
        pos: dict = {}
        for line in block.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().upper().replace(" ", "_").replace("/", "_")
            val = val.strip()
            if not val:
                continue
            if key == "TRACK":
                pos["track"] = val.lower()
            elif key == "ID":
                pos["id"] = val
            elif key == "TITLE":
                pos["title"] = val
            elif key in ("COMPANY_INSTITUTION", "COMPANY", "INSTITUTION"):
                pos["institution"] = val
            elif key == "DEADLINE":
                pos["deadline"] = val
            elif key == "LOCATION":
                pos["location"] = val
            elif key == "LINK":
                pos["link"] = val
            elif key == "FIT":
                pos["fit"] = val
            elif key == "CONTACT":
                pos["contact"] = val
            elif key == "SOURCE":
                pos["source"] = val
        if "track" in pos and "id" in pos:
            positions.append(pos)
    return positions


def apply_positions(positions: list[dict], base_dir: Path) -> tuple[int, int]:
    """Create .md files and update tracking.json. Returns (added, skipped)."""
    global _db_conn_cache
    added = skipped = 0
    today = date.today().isoformat()

    # Open SQLite connection once for the whole batch
    _db_conn_cache = {}
    try:
        from apply_tracker.db import get_db
        _db_conn_cache[base_dir] = get_db(base_dir)
    except Exception:
        pass

    # Resolve search dirs
    phd_dir = base_dir / "PhD-Search"
    job_dir = base_dir / "Job-Search"

    for pos in positions:
        track_raw = pos.get("track", "")
        mapping = TRACK_MAP.get(track_raw)
        if not mapping:
            print(f"  WARN: unknown track '{track_raw}' for {pos.get('id')} — skipping",
                  file=sys.stderr)
            skipped += 1
            continue

        kind, track_name = mapping
        search_dir = phd_dir if kind == "phd" else job_dir
        track_dir = search_dir / "found" / track_name
        track_dir.mkdir(parents=True, exist_ok=True)

        pos_id = pos["id"]
        md_file = track_dir / f"{pos_id}.md"

        # Skip if already exists
        if md_file.exists():
            skipped += 1
            continue

        # Create .md file
        track_label = track_name.replace("_", " ").title()
        content = POSITION_MD_TEMPLATE.format(
            track_label=track_label,
            title=pos.get("title", pos_id),
            institution=pos.get("institution", ""),
            location=pos.get("location", ""),
            deadline=pos.get("deadline", ""),
            link=pos.get("link", ""),
            contact=pos.get("contact", ""),
            fit=pos.get("fit", "?"),
            source=pos.get("source", "routine"),
            today=today,
        )
        md_file.write_text(content)

        # Update tracking.json
        tj_file = track_dir / "tracking.json"
        data = json.loads(tj_file.read_text()) if tj_file.exists() else {}
        if pos_id not in data:
            entry = {
                "status": "found",
                "track": track_name,
                "deadline": _parse_deadline(pos.get("deadline", "")),
                "fit": pos.get("fit", "?"),
                "title": pos.get("title", pos_id),
                "institution": pos.get("institution", ""),
                "location": pos.get("location", ""),
                "link": pos.get("link", ""),
                "contact": pos.get("contact", ""),
                "source": pos.get("source", ""),
                "sent_date": None,
                "reply_date": None,
                "reply_type": None,
                "notes": f"sync:{today}",
            }
            data[pos_id] = entry
            tj_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

            # Dual-write to SQLite
            try:
                entry["id"] = pos_id
                _db_conn_cache[base_dir].execute  # check open
                from apply_tracker.db import upsert as db_upsert
                db_upsert(_db_conn_cache[base_dir], entry, kind)
            except Exception:
                pass

        print(f"  + {pos_id}  [{track_name}]  {pos.get('title','')[:55]}")
        added += 1

    return added, skipped


def process_sync_file(sync_file: Path, base_dir: Path) -> int:
    """Process a local sync text file (written by Claude Code from Gmail draft)."""
    if not sync_file.exists():
        print(f"No sync file found at {sync_file}", file=sys.stderr)
        return 1

    text = sync_file.read_text()
    positions = parse_sync_content(text)

    if not positions:
        print("  No positions found in sync file.")
        return 0

    print(f"  Processing {len(positions)} position(s)...")
    added, skipped = apply_positions(positions, base_dir)
    print(f"\n  ✓ {added} added | {skipped} skipped (already exist)")

    # Archive processed sync file
    archive = sync_file.parent / f"sync_archive_{date.today().isoformat()}.txt"
    sync_file.rename(archive)
    print(f"  Archived → {archive.name}")

    # Regenerate HTML trackers
    try:
        from apply_tracker.generate_html import regenerate_all
        phd_dir = base_dir / "PhD-Search"
        job_dir = base_dir / "Job-Search"
        if phd_dir.exists():
            regenerate_all(phd_dir, kind="phd")
        if job_dir.exists():
            regenerate_all(job_dir, kind="job")
    except Exception as e:
        print(f"  ⚠ HTML regeneration failed: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("base_dir", help="Path to Apply/2026-2027 directory")
    p.add_argument("--sync-file", default=None,
                   help="Path to sync content file (default: base_dir/sync_queue.txt)")
    args = p.parse_args()

    bd = Path(args.base_dir)
    sf = Path(args.sync_file) if args.sync_file else bd / "sync_queue.txt"
    sys.exit(process_sync_file(sf, bd))
