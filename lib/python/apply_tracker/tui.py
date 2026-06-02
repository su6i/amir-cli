#!/usr/bin/env python3
"""Textual TUI for apply tracker — arrow keys, sort, filter, actions."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input, Label, Static
from textual.containers import Vertical
from textual import on

from apply_tracker.service import (
    get_positions, get_stats, mark_sent, mark_status,
    SORT_CHOICES,
)
from apply_tracker.tracker import days_left

# ── Rich markup helpers ───────────────────────────────────────────────────────

def _deadline_cell(dl_str: str | None, d_left: int | None) -> str:
    if not dl_str:
        return "—"
    parts = dl_str.split("-")
    label = f"{parts[2]}/{parts[1]}" if len(parts) == 3 else dl_str[:7]
    if d_left is None:
        return label
    if d_left < 0:
        return f"[red bold]{label} ⚠[/]"
    if d_left <= 7:
        return f"[red]{label}[/]"
    if d_left <= 14:
        return f"[yellow]{label}[/]"
    return label


def _days_cell(d: int | None) -> str:
    if d is None:
        return "—"
    if d < 0:
        return f"[red bold]{d}d[/]"
    if d <= 7:
        return f"[red]{d}d[/]"
    if d <= 14:
        return f"[yellow]{d}d[/]"
    return f"{d}d"


def _fit_cell(fit: str | None) -> str:
    if not fit or fit == "?":
        return "?"
    try:
        score = float(str(fit).split("/")[0])
    except ValueError:
        return fit
    if score >= 8:
        return f"[green bold]{fit}[/]"
    if score >= 6:
        return f"[yellow]{fit}[/]"
    return f"[dim]{fit}[/]"


def _status_cell(status: str) -> str:
    return {
        "found":       "[dim]found[/]",
        "draft_ready": "[yellow]draft ready[/]",
        "sent":        "[green]✓ sent[/]",
        "replied":     "[blue bold]💬 replied[/]",
        "watching":    "[magenta]watching[/]",
        "rejected":    "[red]✗ rejected[/]",
        "bounced":     "[red]⚠ bounce[/]",
    }.get(status, status)


# ── App ───────────────────────────────────────────────────────────────────────

class ApplyTrackerTUI(App):
    CSS = """
    Screen { layout: vertical; }
    #sort-label {
        height: 1; padding: 0 2;
        color: $text-muted; background: $surface-darken-1;
    }
    #filter-bar {
        height: 3; padding: 0 1;
        background: $surface; border-top: solid $primary;
        display: none;
    }
    #filter-bar.visible { display: block; }
    DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("q",     "quit",          "Quit"),
        Binding("s",     "cycle_sort",    "Sort"),
        Binding("slash", "toggle_filter", "Filter /"),
        Binding("escape","clear_filter",  "Clear"),
        Binding("m",     "mark_sent",     "Mark sent"),
        Binding("x",     "reject",        "Reject"),
        Binding("o",     "open_url",      "Open URL"),
        Binding("tab",   "switch_kind",   "PhD ↔ Job"),
        Binding("r",     "refresh",       "Refresh"),
    ]

    def __init__(self, base_dir: Path, kind: str = "phd"):
        super().__init__()
        self.base_dir  = base_dir
        self.kind      = kind
        self._sort_idx = 0
        self._filter   = ""
        self._rows: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="sort-label")
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Vertical(
            Label("🔍 Filter (Enter/Esc):"),
            Input(placeholder="institution / country / status…", id="filter-input"),
            id="filter-bar",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    # ── data ──────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        sort_key = SORT_CHOICES[self._sort_idx % len(SORT_CHOICES)]
        rows = get_positions(self.base_dir, self.kind, sort_by=sort_key)

        if self._filter:
            q = self._filter.lower()
            rows = [r for r in rows if any(
                q in (r.get(f) or "").lower()
                for f in ("institution", "title", "country", "status", "track", "id")
            )]

        self._rows = rows
        self._rebuild_table()
        self._update_header()

    def _rebuild_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns(
            "Institution", "Deadline", "Left",
            "Fit", "Track", "Status", "Country",
        )
        for r in self._rows:
            table.add_row(
                r.get("institution") or r["id"],
                _deadline_cell(r.get("deadline"), r["days_left"]),
                _days_cell(r["days_left"]),
                _fit_cell(r.get("fit")),
                r.get("track") or "",
                _status_cell(r.get("status", "found")),
                r.get("country") or "—",
                key=r["id"],
            )

    def _update_header(self) -> None:
        sort_key = SORT_CHOICES[self._sort_idx % len(SORT_CHOICES)]
        pending = sum(1 for r in self._rows
                      if r["status"] not in ("sent","replied","rejected","bounced"))
        kind_label = "PhD" if self.kind == "phd" else "Job"
        self.title = (f"Apply Tracker — {kind_label} "
                      f"| {pending} pending / {len(self._rows)} total")
        self.query_one("#sort-label", Static).update(
            f" sort: [bold]{sort_key}[/]"
            + (f"  filter: [bold yellow]{self._filter}[/]" if self._filter else "")
        )

    # ── actions ───────────────────────────────────────────────────────────────

    def action_cycle_sort(self) -> None:
        self._sort_idx += 1
        self._load()

    def action_toggle_filter(self) -> None:
        bar = self.query_one("#filter-bar")
        bar.toggle_class("visible")
        if "visible" in bar.classes:
            self.query_one("#filter-input", Input).focus()

    def action_clear_filter(self) -> None:
        self._filter = ""
        self.query_one("#filter-bar").remove_class("visible")
        self.query_one("#filter-input", Input).value = ""
        self._load()

    @on(Input.Submitted, "#filter-input")
    def _filter_submitted(self, event: Input.Submitted) -> None:
        self._filter = event.value.strip()
        self.query_one("#filter-bar").remove_class("visible")
        self._load()

    def action_switch_kind(self) -> None:
        self.kind = "job" if self.kind == "phd" else "phd"
        self._sort_idx = 0
        self._filter   = ""
        self.query_one("#filter-input", Input).value = ""
        self._load()

    def action_refresh(self) -> None:
        self._load()

    def _current_row(self) -> dict | None:
        table = self.query_one(DataTable)
        if not self._rows:
            return None
        try:
            # Textual 8: get row key at cursor
            cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
            pos_id = str(cell_key.row_key.value)
        except Exception:
            return None
        return next((r for r in self._rows if r["id"] == pos_id), None)

    def action_mark_sent(self) -> None:
        row = self._current_row()
        if not row:
            return
        mark_sent(self.base_dir, row["id"], self.kind)
        self.notify(f"✓ {row['id']} marked as sent", severity="information")
        self._load()

    def action_reject(self) -> None:
        row = self._current_row()
        if not row:
            return
        mark_status(self.base_dir, row["id"], self.kind, "rejected")
        self.notify(f"✗ {row['id']} rejected", severity="warning")
        self._load()

    def action_open_url(self) -> None:
        row = self._current_row()
        if not row or not row.get("link"):
            self.notify("No URL for this position", severity="warning")
            return
        subprocess.Popen(["open", row["link"]])
        self.notify(f"Opening browser…")


def run_tui(base_dir: Path, kind: str = "phd") -> None:
    ApplyTrackerTUI(base_dir, kind).run()


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 \
        else Path.home() / "@-Amir/Apply/2026-2027"
    kind = sys.argv[2] if len(sys.argv) > 2 else "phd"
    run_tui(base, kind)
