#!/usr/bin/env python3
"""Thin CLI bridge to service.py — called directly from bash commands."""
import sys
from pathlib import Path

PHD_SEARCH = Path.home() / "@-Amir/Apply/2026-2027"


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: service_cli.py <action> <pos_id> <kind>", file=sys.stderr)
        sys.exit(1)

    action, pos_id, kind = sys.argv[1], sys.argv[2], sys.argv[3]
    base = PHD_SEARCH

    from apply_tracker.service import mark_status

    if action == "reject":
        ok = mark_status(base, pos_id, kind, "rejected")
        if ok:
            print(f"✗  {pos_id} rejected")
        else:
            print(f"ERROR: {pos_id} not found", file=sys.stderr)
            sys.exit(1)
    elif action == "watch":
        ok = mark_status(base, pos_id, kind, "watching")
        if ok:
            print(f"👁  {pos_id} marked as watching")
        else:
            print(f"ERROR: {pos_id} not found", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
