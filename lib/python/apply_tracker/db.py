#!/usr/bin/env python3
"""SQLite layer for apply tracker.

Schema note: (id, kind) is the PK so the same position id cannot
accidentally appear in both phd and job with divergent state.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from pathlib import Path

DB_FILENAME = "tracker.db"

# ── country inference ─────────────────────────────────────────────────────────

_COUNTRY_KEYS: list[tuple[str, str]] = [
    ("france", "France"), ("inria", "France"), ("artois", "France"),
    ("paris", "France"), ("grenoble", "France"), ("lille", "France"),
    ("rennes", "France"), ("nantes", "France"), ("toulouse", "France"),
    ("bordeaux", "France"), ("lyon", "France"), ("montpellier", "France"),
    ("belgium", "Belgium"), ("leuven", "Belgium"), ("belgique", "Belgium"),
    ("uclouvain", "Belgium"), ("ghent", "Belgium"),
    ("netherlands", "Netherlands"), ("amsterdam", "Netherlands"),
    ("delft", "Netherlands"), ("uva", "Netherlands"),
    ("germany", "Germany"), ("munich", "Germany"), ("berlin", "Germany"),
    ("lmu", "Germany"), ("tum", "Germany"),
    ("canada", "Canada"), ("mila", "Canada"), ("montreal", "Canada"),
    ("québec", "Canada"), ("uqam", "Canada"), ("hec", "Canada"),
    ("ireland", "Ireland"), ("ucd", "Ireland"), ("dublin", "Ireland"),
    ("denmark", "Denmark"), ("aalborg", "Denmark"), ("copenhagen", "Denmark"),
    ("sweden", "Sweden"), ("chalmers", "Sweden"), ("orebro", "Sweden"),
    ("finland", "Finland"), ("tampere", "Finland"), ("helsinki", "Finland"),
    ("switzerland", "Switzerland"), ("eth", "Switzerland"), ("zurich", "Switzerland"),
    ("austria", "Austria"), ("linz", "Austria"), ("graz", "Austria"),
    ("greece", "Greece"), ("athens", "Greece"),
    ("spain", "Spain"), ("barcelona", "Spain"), ("madrid", "Spain"),
    ("italy", "Italy"), ("milan", "Italy"), ("rome", "Italy"),
    ("uk", "UK"), ("london", "UK"), ("cambridge", "UK"), ("oxford", "UK"),
]


def _infer_country(institution: str, location: str) -> str | None:
    text = f"{institution} {location}".lower()
    for key, country in _COUNTRY_KEYS:
        if key in text:
            return country
    return None


def _fit_score(fit: str | None) -> float | None:
    if not fit:
        return None
    m = re.match(r"(\d+(?:\.\d+)?)", str(fit))
    return float(m.group(1)) if m else None


# ── schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id           TEXT NOT NULL,
    kind         TEXT NOT NULL CHECK(kind IN ('phd','job')),
    track        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'found',
    title        TEXT,
    institution  TEXT,
    country      TEXT,
    location     TEXT,
    deadline     TEXT,
    fit          TEXT,
    fit_score    REAL,
    experience   TEXT,
    link         TEXT,
    contact      TEXT,
    lang         TEXT,
    source       TEXT,
    notes        TEXT,
    sent_date    TEXT,
    reply_date   TEXT,
    reply_type   TEXT,
    added_date   TEXT DEFAULT (date('now')),
    updated_date TEXT DEFAULT (date('now')),
    PRIMARY KEY (id, kind)
);
CREATE INDEX IF NOT EXISTS idx_kind_status ON positions(kind, status);
CREATE INDEX IF NOT EXISTS idx_deadline    ON positions(deadline);
CREATE INDEX IF NOT EXISTS idx_country     ON positions(country);
CREATE INDEX IF NOT EXISTS idx_fit_score   ON positions(fit_score);
"""

# ── connection ────────────────────────────────────────────────────────────────


def get_db(base_dir: Path) -> sqlite3.Connection:
    """Open (or create) tracker.db in base_dir and ensure schema exists."""
    db_path = base_dir / DB_FILENAME
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    # Column migrations (ALTER TABLE IF NOT EXISTS workaround)
    for col, definition in [("experience", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE positions ADD COLUMN {col} {definition}")
            conn.commit()
        except Exception:
            pass
    return conn


# ── write ops ─────────────────────────────────────────────────────────────────


def upsert(conn: sqlite3.Connection, pos: dict, kind: str) -> None:
    """Insert or update a position.

    On conflict: preserves existing status/sent_date/reply fields if the
    incoming value is NULL — so a re-sync never overwrites manual edits.
    """
    country = _infer_country(pos.get("institution", "") or "",
                             pos.get("location", "") or "")
    fit_s = _fit_score(pos.get("fit"))

    conn.execute("""
        INSERT INTO positions
            (id, kind, track, status, title, institution, country, location,
             deadline, fit, fit_score, experience, link, contact, lang, source,
             notes, sent_date, reply_date, reply_type, added_date, updated_date)
        VALUES
            (:id, :kind, :track, :status, :title, :institution, :country,
             :location, :deadline, :fit, :fit_score, :experience, :link,
             :contact, :lang, :source, :notes, :sent_date, :reply_date,
             :reply_type, date('now'), date('now'))
        ON CONFLICT(id, kind) DO UPDATE SET
            track        = excluded.track,
            title        = COALESCE(excluded.title,       positions.title),
            institution  = COALESCE(excluded.institution, positions.institution),
            country      = COALESCE(excluded.country,     positions.country),
            location     = COALESCE(excluded.location,    positions.location),
            deadline     = COALESCE(excluded.deadline,    positions.deadline),
            fit          = COALESCE(excluded.fit,         positions.fit),
            fit_score    = COALESCE(excluded.fit_score,   positions.fit_score),
            experience   = COALESCE(excluded.experience,  positions.experience),
            link         = COALESCE(excluded.link,        positions.link),
            contact      = COALESCE(excluded.contact,     positions.contact),
            lang         = COALESCE(excluded.lang,        positions.lang),
            source       = COALESCE(excluded.source,      positions.source),
            status       = CASE
                             WHEN excluded.status != 'found' THEN excluded.status
                             ELSE positions.status
                           END,
            sent_date    = COALESCE(positions.sent_date,  excluded.sent_date),
            reply_date   = COALESCE(positions.reply_date, excluded.reply_date),
            reply_type   = COALESCE(positions.reply_type, excluded.reply_type),
            updated_date = date('now')
    """, {
        "id":          pos["id"],
        "kind":        kind,
        "track":       pos.get("track", ""),
        "status":      pos.get("status", "found"),
        "title":       pos.get("title"),
        "institution": pos.get("institution"),
        "country":     country,
        "location":    pos.get("location"),
        "deadline":    pos.get("deadline"),
        "fit":         pos.get("fit"),
        "fit_score":   fit_s,
        "experience":  pos.get("experience"),
        "link":        pos.get("link"),
        "contact":     pos.get("contact"),
        "lang":        pos.get("lang"),
        "source":      pos.get("source"),
        "notes":       pos.get("notes"),
        "sent_date":   pos.get("sent_date"),
        "reply_date":  pos.get("reply_date"),
        "reply_type":  pos.get("reply_type"),
    })
    conn.commit()


def update_status(conn: sqlite3.Connection, pos_id: str, kind: str,
                  status: str, **kwargs) -> bool:
    """Update status (and optional extra fields) for one position.
    Returns True if a row was updated."""
    fields: dict = {"status": status, "updated_date": date.today().isoformat()}
    fields.update(kwargs)
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["_id"]   = pos_id
    fields["_kind"] = kind
    cur = conn.execute(
        f"UPDATE positions SET {set_clause} WHERE id = :_id AND kind = :_kind",
        fields,
    )
    conn.commit()
    return cur.rowcount > 0


# ── read ops ──────────────────────────────────────────────────────────────────

_DEFAULT_ORDER = (
    "CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline, fit_score DESC"
)


def query(
    conn: sqlite3.Connection,
    kind: str | None = None,
    track: str | None = None,
    status: str | None = None,
    min_fit: float | None = None,
    country: str | None = None,
    pending_only: bool = False,
    order_by: str = _DEFAULT_ORDER,
) -> list[dict]:
    clauses: list[str] = []
    params: dict = {}

    if kind:
        clauses.append("kind = :kind");        params["kind"]    = kind
    if track:
        clauses.append("track = :track");      params["track"]   = track
    if status:
        clauses.append("status = :status");    params["status"]  = status
    if min_fit is not None:
        clauses.append("fit_score >= :min_fit"); params["min_fit"] = min_fit
    if country:
        clauses.append("country = :country");  params["country"] = country
    if pending_only:
        clauses.append(
            "status NOT IN ('sent','replied','rejected','bounced')"
        )

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM positions {where} ORDER BY {order_by}", params
    ).fetchall()
    return [dict(r) for r in rows]


def find_position(conn: sqlite3.Connection, pos_id: str,
                  kind: str | None = None) -> dict | None:
    if kind:
        row = conn.execute(
            "SELECT * FROM positions WHERE id = ? AND kind = ?", (pos_id, kind)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM positions WHERE id = ?", (pos_id,)
        ).fetchone()
    return dict(row) if row else None


def stats(conn: sqlite3.Connection, kind: str) -> dict:
    """Return aggregate counts for a quick summary."""
    rows = conn.execute("""
        SELECT status, COUNT(*) as n
        FROM positions WHERE kind = ?
        GROUP BY status
    """, (kind,)).fetchall()
    counts = {r["status"]: r["n"] for r in rows}
    countries = conn.execute("""
        SELECT country, COUNT(*) as n
        FROM positions WHERE kind = ? AND country IS NOT NULL
        GROUP BY country ORDER BY n DESC
    """, (kind,)).fetchall()
    return {
        "by_status":  counts,
        "by_country": [dict(r) for r in countries],
        "total":      sum(counts.values()),
    }


# ── migration ─────────────────────────────────────────────────────────────────


def migrate_from_json(base_dir: Path, conn: sqlite3.Connection) -> int:
    """Read every tracking.json and upsert into SQLite. Safe to re-run."""
    count = 0
    for search_label, kind in [("PhD-Search", "phd"), ("Job-Search", "job")]:
        found_dir = base_dir / search_label / "found"
        if not found_dir.exists():
            continue
        for track_dir in sorted(found_dir.iterdir()):
            if not track_dir.is_dir():
                continue
            tj = track_dir / "tracking.json"
            if not tj.exists():
                continue
            data: dict = json.loads(tj.read_text())
            for pos_id, entry in data.items():
                entry["id"] = pos_id
                upsert(conn, entry, kind)
                count += 1
    return count


if __name__ == "__main__":
    import sys
    base = Path(sys.argv[1]) if len(sys.argv) > 1 \
        else Path.home() / "@-Amir/Apply/2026-2027"
    conn = get_db(base)
    n = migrate_from_json(base, conn)
    print(f"✓ Migrated {n} positions to {base / DB_FILENAME}")

    s_phd = stats(conn, "phd")
    s_job = stats(conn, "job")
    print(f"  PhD: {s_phd['total']} positions — {s_phd['by_status']}")
    print(f"  Job: {s_job['total']} positions — {s_job['by_status']}")
    print(f"  Countries (PhD): {[r['country'] for r in s_phd['by_country']]}")
