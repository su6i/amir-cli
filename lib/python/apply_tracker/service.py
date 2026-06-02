#!/usr/bin/env python3
"""Business-logic layer — single entry point for all UIs (CLI, TUI, Web).

All three interfaces import from here; db.py is never called directly by UIs.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from apply_tracker.db import (
    get_db, query as _db_query, update_status as _db_update,
    find_position, stats as _db_stats, upsert,
)
from apply_tracker.tracker import days_left, _find_track_dir, update_entry


# ── base dir ──────────────────────────────────────────────────────────────────

def _base(search_dir_or_base: Path) -> Path:
    """Accept either the base dir or a PhD-Search/Job-Search dir."""
    name = search_dir_or_base.name.lower()
    if "phd" in name or "job" in name:
        return search_dir_or_base.parent
    return search_dir_or_base


def _kind_from_path(search_dir: Path) -> str:
    return "phd" if "phd" in search_dir.name.lower() else "job"


# ── sort map ──────────────────────────────────────────────────────────────────

SORT_CHOICES = ["deadline", "fit", "country", "status", "institution", "newest"]

# Each entry: (asc_sql, desc_sql)
_ORDER: dict[str, tuple[str, str]] = {
    "deadline":    (
        "CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline",
        "CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline DESC",
    ),
    "fit":         (
        "fit_score ASC NULLS LAST",
        "fit_score DESC NULLS LAST",
    ),
    "country":     (
        "country NULLS LAST, deadline",
        "country DESC NULLS LAST",
    ),
    "status":      (
        "status, deadline",
        "status DESC, deadline",
    ),
    "institution": (
        "institution NULLS LAST, deadline",
        "institution DESC NULLS LAST",
    ),
    "newest":      (
        "COALESCE(added_date,'1900-01-01') DESC, id ASC",
        "COALESCE(added_date,'1900-01-01') ASC, id DESC",
    ),
}
_DEFAULT_ORDER = _ORDER["deadline"][0]


def _order(sort_by: str | None, asc: bool = True) -> str:
    entry = _ORDER.get(sort_by or "")
    if entry is None:
        return _DEFAULT_ORDER
    return entry[0] if asc else entry[1]


# ── shared entry dict ─────────────────────────────────────────────────────────

def _enrich(row: dict) -> dict:
    """Add computed fields (days_left) so every UI gets the same dict."""
    row = dict(row)
    row["days_left"] = days_left(row.get("deadline"))
    return row


# ── read operations ───────────────────────────────────────────────────────────

def get_positions(
    base_dir: Path,
    kind: str,
    *,
    track: str | None = None,
    status: str | None = None,
    pending_only: bool = False,
    country: str | None = None,
    min_fit: float | None = None,
    sort_by: str | None = None,
    asc: bool = True,
) -> list[dict]:
    """Return enriched position dicts for any UI to consume."""
    conn = get_db(base_dir)
    rows = _db_query(
        conn, kind=kind, track=track, status=status,
        pending_only=pending_only, country=country,
        min_fit=min_fit, order_by=_order(sort_by, asc),
    )
    return [_enrich(r) for r in rows]


def get_stats(base_dir: Path) -> dict:
    """Stats for both kinds."""
    conn = get_db(base_dir)
    return {
        "phd": _db_stats(conn, "phd"),
        "job": _db_stats(conn, "job"),
    }


def get_countries(base_dir: Path, kind: str) -> list[str]:
    conn = get_db(base_dir)
    rows = _db_query(conn, kind=kind)
    return sorted({r["country"] for r in rows if r.get("country")})


# ── write operations ──────────────────────────────────────────────────────────

def mark_sent(base_dir: Path, pos_id: str, kind: str,
              sent_date: str | None = None) -> bool:
    """Mark a position as sent in both SQLite and JSON."""
    today = sent_date or date.today().isoformat()
    conn  = get_db(base_dir)
    ok    = _db_update(conn, pos_id, kind, "sent", sent_date=today)

    # Mirror to JSON
    search_name = "PhD-Search" if kind == "phd" else "Job-Search"
    search_dir  = base_dir / search_name
    try:
        td = _find_track_dir(search_dir, pos_id, None)
        if td:
            update_entry(td, pos_id, status="sent", sent_date=today)
    except Exception:
        pass

    return ok


def mark_status(base_dir: Path, pos_id: str, kind: str,
                status: str, **kwargs) -> bool:
    """Generic status update in both SQLite and JSON."""
    conn = get_db(base_dir)
    ok   = _db_update(conn, pos_id, kind, status, **kwargs)

    search_name = "PhD-Search" if kind == "phd" else "Job-Search"
    search_dir  = base_dir / search_name
    try:
        td = _find_track_dir(search_dir, pos_id, None)
        if td:
            update_entry(td, pos_id, status=status, **kwargs)
    except Exception:
        pass

    return ok
