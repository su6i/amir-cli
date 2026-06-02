#!/usr/bin/env python3
"""CLI stats printer — called by `amir apply stats`."""
from __future__ import annotations
import sys
from pathlib import Path
from apply_tracker.service import get_stats

BOLD  = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[32m"
RED   = "\033[31m"
DIM   = "\033[2m"


def main(base_dir: Path) -> None:
    all_stats = get_stats(base_dir)

    for kind, label in [("phd", "🎓 PhD"), ("job", "💼 Job")]:
        s = all_stats[kind]
        print(f"\n  {BOLD}{label} — {s['total']} positions{RESET}")
        print(f"  {'─' * 36}")
        for status, n in sorted(s["by_status"].items(), key=lambda x: -x[1]):
            bar = "█" * min(n, 40)
            color = GREEN if status in ("sent","replied") else \
                    RED   if status in ("rejected","bounced") else DIM
            print(f"  {color}{status:<14}{RESET}  {n:3}  {color}{bar}{RESET}")

        if s["by_country"]:
            print(f"\n  Countries:")
            for r in s["by_country"]:
                bar = "▪" * r["n"]
                print(f"    {r['country']:<16} {r['n']:3}  {bar}")

    print()


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 \
        else Path.home() / "@-Amir/Apply/2026-2027"
    main(base)
