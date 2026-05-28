#!/usr/bin/env python3
"""Manage search_sources.md files — add, list, remove entries."""

import sys
from pathlib import Path


def _is_data_line(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith("#")


def add_source(src_file: Path, name: str, url: str, desc: str = "",
               priority: int | None = None) -> None:
    lines = src_file.read_text().splitlines(keepends=True)

    new_line = f"{name:<14}| {url:<80}| {desc}\n"

    data_indices = [i for i, l in enumerate(lines) if _is_data_line(l)]

    if priority is not None:
        # Insert before the Nth data entry (1-based)
        if priority < 1:
            priority = 1
        if priority <= len(data_indices):
            insert_at = data_indices[priority - 1]
        else:
            # Past the end — insert after last data entry
            insert_at = (data_indices[-1] + 1) if data_indices else len(lines)
    else:
        # Default: insert before GMAIL NEWSLETTERS section
        gmail_idx = next(
            (i for i, l in enumerate(lines) if "── GMAIL" in l),
            len(lines),
        )
        insert_at = gmail_idx

    lines.insert(insert_at, new_line)
    src_file.write_text("".join(lines))

    pos_label = f"position {priority}" if priority is not None else "end of list"
    print(f"  ✓  Added '{name.strip()}' at {pos_label}")
    print(f"     {url.strip()}")


def list_sources(src_file: Path) -> None:
    if not src_file.exists():
        print(f"File not found: {src_file}", file=sys.stderr)
        sys.exit(1)

    n = 0
    for line in src_file.read_text().splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("# ──"):
            section = s.split("── ", 1)[1].rstrip(" ─")
            print(f"\n  ── {section}")
            continue
        if s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        name = parts[0] if len(parts) > 0 else ""
        url  = parts[1] if len(parts) > 1 else ""
        n += 1
        print(f"  {n:2d}.  {name:<14}  {url}")
    print()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("src_file", help="Path to *_search_sources.md")
    sub = p.add_subparsers(dest="cmd")

    s_add = sub.add_parser("add")
    s_add.add_argument("name")
    s_add.add_argument("url")
    s_add.add_argument("desc", nargs="?", default="")
    s_add.add_argument("-p", "--priority", type=int, default=None,
                       metavar="N", help="Insert at position N (1-based)")

    s_list = sub.add_parser("list")

    args = p.parse_args()
    f = Path(args.src_file)

    if args.cmd == "add":
        add_source(f, args.name, args.url, args.desc, args.priority)
    elif args.cmd == "list":
        list_sources(f)
    else:
        p.print_help()
