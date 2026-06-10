#!/usr/bin/env python3
"""FastAPI web interface — localhost:8765.

All data access goes through service.py, never db.py directly.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import uvicorn

from apply_tracker.service import (
    get_positions, get_stats, get_countries,
    mark_sent, mark_status,
)
from apply_tracker.tracker import days_left
import apply_tracker.gmail_sync as _gmail

import os as _os
BASE_DIR = Path(_os.environ.get("APPLY_BASE_DIR",
                str(Path.home() / "@-Amir/Apply/2026-2027")))
app = FastAPI(title="Apply Tracker", docs_url="/api/docs")


def _position_files(pos_id: str, kind: str) -> tuple[str, list[Path]]:
    """Return (draft_text, pdf_paths) from the applied/<pos_id>/ folder."""
    search_name = "PhD-Search" if kind == "phd" else "Job-Search"
    applied_dir = BASE_DIR / search_name / "applied" / pos_id
    draft_text  = ""
    pdfs: list[Path] = []
    if applied_dir.exists():
        draft_file = applied_dir / "email_draft.md"
        if draft_file.exists():
            draft_text = draft_file.read_text(encoding="utf-8")
        pdfs = sorted(applied_dir.glob("*.pdf"))
    return draft_text, pdfs

# ── shared formatters (HTML output) ──────────────────────────────────────────

def _deadline_fmt(dl: str | None) -> str:
    if not dl:
        return "—"
    p = dl.split("-")
    return f"{p[2]}/{p[1]}" if len(p) == 3 else dl[:7]


def _days_badge(d_left: int | None) -> str:
    if d_left is None:
        return '<span class="badge grey">—</span>'
    lbl = f"{d_left}d"
    cls = "urgent" if d_left <= 7 else "soon" if d_left <= 14 else "ok"
    return f'<span class="badge {cls}">{lbl}</span>'


def _fit_badge(fit: str | None) -> str:
    if not fit or fit == "?":
        return '<span class="fit grey">?</span>'
    try:
        s = float(str(fit).split("/")[0])
    except ValueError:
        return f'<span class="fit">{fit}</span>'
    cls = "high" if s >= 8 else "mid" if s >= 6 else "low"
    return f'<span class="fit {cls}">{fit}</span>'


def _status_badge(status: str) -> str:
    _m = {
        "found":       ("grey",   "À examiner"),
        "draft_ready": ("orange", "Draft prêt"),
        "sent":        ("green",  "✓ Envoyé"),
        "replied":     ("blue",   "💬 Réponse"),
        "watching":    ("purple", "👁 Veille"),
        "rejected":    ("red",    "✗ Refusé"),
        "bounced":     ("red",    "⚠ Bounce"),
    }
    cls, lbl = _m.get(status, ("grey", status))
    return f'<span class="badge {cls}">{lbl}</span>'


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
* { box-sizing:border-box; margin:0; padding:0;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
body { background:#f0f2f5; color:#1a1a2e; }
header { background:linear-gradient(135deg,#0d3b2e,#145a45); color:white;
         padding:16px 28px; display:flex; justify-content:space-between; align-items:center; }
header h1 { font-size:1.15rem; font-weight:700; }
header nav a { color:rgba(255,255,255,.8); text-decoration:none; margin-left:18px; font-size:.88rem; }
header nav a:hover, header nav a.active { color:white; font-weight:600; }
.container { max-width:1300px; margin:0 auto; padding:22px 14px; }
.toolbar { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; align-items:center; }
.toolbar select,.toolbar input[type=text],.toolbar input[type=number]
    { padding:5px 10px; border:1px solid #ddd; border-radius:6px; font-size:.83rem; background:white; }
.stats { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; margin-bottom:20px; }
.stat { background:white; border-radius:10px; padding:12px 8px; text-align:center;
        box-shadow:0 2px 6px rgba(0,0,0,.06); }
.stat .num { font-size:1.7rem; font-weight:800; line-height:1; color:#145a45; }
.stat .lbl { font-size:.66rem; color:#888; margin-top:4px; text-transform:uppercase; letter-spacing:.4px; }
.stat.urgent .num { color:#c62828; } .stat.sent .num { color:#2e7d32; }
table { width:100%; border-collapse:collapse; background:white; border-radius:12px;
        box-shadow:0 2px 8px rgba(0,0,0,.06); overflow:hidden; }
th { background:#fafafa; padding:9px 12px; text-align:left; font-size:.71rem; color:#888;
     text-transform:uppercase; letter-spacing:.4px; border-bottom:1px solid #eee; cursor:pointer; }
th:hover { background:#f0f0f0; } th.sorted { color:#145a45; font-weight:700; }
td { padding:9px 12px; font-size:.83rem; border-bottom:1px solid #f5f5f5; vertical-align:middle; }
tr:last-child td { border-bottom:none; } tr:hover td { background:#f8fffc; }
.badge { display:inline-block; padding:2px 8px; border-radius:20px; font-size:.69rem; font-weight:600; }
.badge.urgent{background:#fce4ec;color:#c62828} .badge.soon{background:#fff3e0;color:#e65100}
.badge.ok{background:#e8f5e9;color:#2e7d32} .badge.grey{background:#f5f5f5;color:#777}
.badge.green{background:#e8f5e9;color:#2e7d32} .badge.blue{background:#e3f2fd;color:#1565c0}
.badge.orange{background:#fff3e0;color:#e65100} .badge.red{background:#fce4ec;color:#c62828}
.badge.purple{background:#f3e5f5;color:#6a1b9a}
.fit{font-weight:700;font-size:.86rem}
.fit.high{color:#2e7d32} .fit.mid{color:#f57f17} .fit.low{color:#c62828} .fit.grey{color:#aaa}
.ab{padding:3px 9px;border:none;border-radius:4px;cursor:pointer;font-size:.73rem;font-weight:600}
.ab.sent{background:#e8f5e9;color:#2e7d32} .ab.open{background:#e3f2fd;color:#1565c0}
.ab.sent:hover{background:#c8e6c9} .ab.open:hover{background:#bbdefb}
.detail-row td{background:#f8fffc;padding:12px 16px;border-bottom:2px solid #e0f2e9}
.detail-row{display:none}
.detail-panel{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.detail-panel .info{flex:1;min-width:200px;font-size:.82rem;color:#444;line-height:1.7}
.detail-panel .actions{display:flex;gap:8px;flex-wrap:wrap}
.ab.folder{background:#fff3e0;color:#e65100} .ab.folder:hover{background:#ffe0b2}
.ab.draft{background:#f3e5f5;color:#6a1b9a} .ab.draft:hover{background:#e1bee7}
.ab.reject{background:#fce4ec;color:#c62828} .ab.reject:hover{background:#ffcdd2}
.ab.send-email{background:#1b5e20;color:#fff} .ab.send-email:hover{background:#2e7d32}
.draft-preview{margin-top:10px;background:#fafafa;border:1px solid #e0e0e0;border-radius:6px;
  padding:10px 14px;font-size:.78rem;white-space:pre-wrap;word-break:break-word;
  max-height:220px;overflow-y:auto;color:#333;font-family:monospace;line-height:1.5}
.pdf-list{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}
.pdf-chip{background:#fff3e0;border:1px solid #ffe0b2;border-radius:12px;
  padding:2px 8px;font-size:.72rem;color:#e65100}
.exp-badge{display:inline-block;padding:1px 6px;border-radius:10px;font-size:.68rem;
           font-weight:600;background:#e8eaf6;color:#283593;white-space:nowrap}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;align-items:center}
.chip{display:inline-block;padding:4px 13px;border-radius:14px;font-size:.75rem;font-weight:600;
      cursor:pointer;text-decoration:none;border:1.5px solid #ddd;background:#f5f5f5;color:#555;transition:.15s}
.chip:hover{background:#e0e0e0;border-color:#bbb}
.chip.active{background:#145a45;color:white;border-color:#145a45}
.chip.chip-rejected{border-color:#e57373;color:#c62828;background:#fff5f5}
.chip.chip-rejected.active{background:#e57373;border-color:#e57373;color:white}
.chip.chip-draft{border-color:#9c27b0;color:#6a1b9a;background:#f9f0ff}
.chip.chip-draft.active{background:#9c27b0;border-color:#9c27b0;color:white}
.chip.chip-sent{border-color:#43a047;color:#2e7d32;background:#f0fff4}
.chip.chip-sent.active{background:#43a047;border-color:#43a047;color:white}
.chip.chip-replied{border-color:#1565c0;color:#1565c0;background:#f0f7ff}
.chip.chip-replied.active{background:#1565c0;border-color:#1565c0;color:white}
tr.clickable{cursor:pointer} tr.clickable:hover td{background:#f0faf5}
.sync-btn{padding:5px 14px;border:1px solid rgba(255,255,255,.4);border-radius:6px;
          background:rgba(255,255,255,.15);color:white;cursor:pointer;
          font-size:.8rem;font-weight:600;text-decoration:none;display:inline-block}
.sync-btn:hover{background:rgba(255,255,255,.25)}
.sync-btn.warn{border-color:#ffcc80;background:rgba(255,152,0,.25);color:#ffe0b2}
.flash{padding:10px 16px;border-radius:8px;margin-bottom:14px;font-size:.85rem;font-weight:600}
.flash.ok{background:#e8f5e9;color:#1b5e20;border-left:4px solid #2e7d32}
.flash.err{background:#fce4ec;color:#b71c1c;border-left:4px solid #c62828}
.replied-card{background:white;border-radius:10px;padding:16px 20px;margin-bottom:14px;
              box-shadow:0 2px 8px rgba(0,0,0,.06);border-left:4px solid #1565c0}
.replied-card h4{font-size:.9rem;margin-bottom:6px}
.replied-card .meta{font-size:.78rem;color:#666;margin-bottom:8px}
.replied-card .notes{font-size:.83rem;color:#333;white-space:pre-wrap}
.section-title{font-size:1rem;font-weight:700;margin:20px 0 12px;color:#145a45}
footer{text-align:center;padding:14px;font-size:.71rem;color:#aaa;margin-top:16px}
"""


def _gmail_btn() -> str:
    try:
        if _gmail.has_valid_token():
            return ('<form method="post" action="/api/sync-gmail" style="display:inline">'
                    '<button class="sync-btn" type="submit">🔄 Sync Gmail</button></form>')
        if _gmail.creds_file_exists():
            return '<a href="/auth/gmail" class="sync-btn warn">🔑 Connect Gmail</a>'
        return '<a href="/auth/gmail/setup" class="sync-btn warn">⚙ Gmail Setup</a>'
    except Exception:
        return ""


def _page(content: str, active: str = "phd", flash: str = "", flash_type: str = "ok") -> str:
    today = date.today().strftime("%d %B %Y")
    flash_html = (f'<div class="flash {flash_type}">{flash}</div>' if flash else "")
    return f"""<!DOCTYPE html><html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Apply Tracker</title><style>{_CSS}</style></head><body>
<header>
  <h1>🎓 Apply Tracker</h1>
  <nav>
    <a href="/phd" {'class="active"' if active=="phd" else ""}>PhD</a>
    <a href="/job" {'class="active"' if active=="job" else ""}>Job</a>
    <a href="/replied" {'class="active"' if active=="replied" else ""}>Replied</a>
    <a href="/stats" {'class="active"' if active=="stats" else ""}>Stats</a>
    <a href="/api/docs" target="_blank">API</a>
    {_gmail_btn()}
  </nav>
</header>
<div class="container">{flash_html}{content}</div>
<footer>Amir SHIRALI POUR · Apply Tracker · {today}</footer>
<script>
const fi=document.getElementById('lf');
if(fi) fi.addEventListener('input',()=>{{
  const q=fi.value.toLowerCase();
  document.querySelectorAll('tbody tr.clickable').forEach(tr=>{{
    const show=tr.textContent.toLowerCase().includes(q);
    tr.style.display=show?'':'none';
    const det=document.getElementById('detail-'+tr.querySelector('td small')?.textContent?.trim());
    if(det) det.style.display='none';
  }});
}});
document.querySelectorAll('th[data-col]').forEach(th=>{{
  th.addEventListener('click',()=>{{
    const u=new URL(window.location);
    const c=u.searchParams.get('sort');
    u.searchParams.set('sort',th.dataset.col);
    u.searchParams.set('asc',c===th.dataset.col?(u.searchParams.get('asc')==='1'?'0':'1'):'1');
    window.location=u;
  }});
}});
function toggleDetail(pid){{
  const row=document.getElementById('detail-'+pid);
  if(!row) return;
  row.style.display=row.style.display==='table-row'?'none':'table-row';
}}
function filterBy(key, value){{
  const u=new URL(window.location.href);
  u.searchParams.set(key, value);
  window.location.href=u.toString();
}}
</script></body></html>"""


def _th(label: str, col: str, sort: str, asc: bool) -> str:
    cls = ' class="sorted"' if col == sort else ""
    arrow = ("↑" if asc else "↓") if col == sort else ""
    return f'<th{cls} data-col="{col}">{label} {arrow}</th>'


class _FilterState:
    """Carries current filter params so cells can build click-to-filter URLs."""
    def __init__(self, base: str, sort: str, asc: int,
                 country: str, min_fit: str, status: str,
                 track: str, fit: str):
        self.base = base
        self.sort = sort; self.asc = asc
        self.country = country; self.min_fit = min_fit
        self.status = status; self.track = track; self.fit = fit

    def url(self, **overrides) -> str:
        p = dict(sort=self.sort, asc=self.asc, country=self.country,
                 min_fit=self.min_fit, status=self.status,
                 track=self.track, fit=self.fit)
        p.update(overrides)
        qs = "&".join(f"{k}={v}" for k, v in p.items() if v not in (None, ""))
        return f"{self.base}?{qs}"


def _positions_html(rows: list[dict], kind: str, sort: str, asc: bool,
                    fs: "_FilterState | None" = None) -> str:
    header = (
        f'<tr><th style="width:32px;text-align:center;color:#ccc">#</th>'
        f"{_th('Institution','institution',sort,asc)}"
        f"{_th('Deadline','deadline',sort,asc)}"
        f"{_th('Days','days',sort,asc)}"
        f"{_th('Fit','fit',sort,asc)}"
        f"{_th('Exp','experience',sort,asc)}"
        f"{_th('Track','track',sort,asc)}"
        f"{_th('Country','country',sort,asc)}"
        f"{_th('Status','status',sort,asc)}"
        f"{_th('Added','newest',sort,asc)}"
        f"<th>Actions</th></tr>"
    )
    body = ""
    for idx, r in enumerate(rows, 1):
        pid        = r["id"]
        link       = r.get("link") or ""
        contact    = r.get("contact") or ""
        notes      = r.get("notes") or ""
        experience = r.get("experience") or ""
        added      = (r.get("added_date") or "")[-5:].replace("-", "/")  # MM/DD
        title      = r.get("title") or pid
        open_btn = (f'<a href="{link}" target="_blank">'
                    f'<button class="ab open">Open</button></a>') if link else ""
        sent_btn = "" if r.get("status") in ("sent","replied") else (
            f'<form method="post" action="/api/status" style="display:inline">'
            f'<input type="hidden" name="pos_id" value="{pid}">'
            f'<input type="hidden" name="kind" value="{kind}">'
            f'<input type="hidden" name="status" value="sent">'
            f'<button class="ab sent" type="submit">Mark sent</button></form>')
        reject_btn = "" if r.get("status") in ("rejected","sent","replied") else (
            f'<form method="post" action="/api/status" style="display:inline">'
            f'<input type="hidden" name="pos_id" value="{pid}">'
            f'<input type="hidden" name="kind" value="{kind}">'
            f'<input type="hidden" name="status" value="rejected">'
            f'<button class="ab reject" type="submit">✗ Reject</button></form>')

        exp_cell = (f'<span class="exp-badge">{experience[:22]}</span>'
                    if experience else '<span style="color:#ccc">—</span>')

        # Detail expand panel
        folder_btn = (
            f'<form method="post" action="/api/open-folder" style="display:inline">'
            f'<input type="hidden" name="pos_id" value="{pid}">'
            f'<input type="hidden" name="kind" value="{kind}">'
            f'<button class="ab folder" type="submit">📂 Open folder</button></form>')
        draft_cmd = f"amir apply {kind} draft {pid}"

        # Load draft preview + PDF list from applied/ folder
        draft_text, pdfs = _position_files(pid, kind)
        draft_preview = ""
        if draft_text:
            escaped = draft_text[:1800].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            draft_preview = f'<div class="draft-preview">{escaped}</div>'
        pdf_chips = ""
        if pdfs:
            chips_html = "".join(f'<span class="pdf-chip">📎 {p.name}</span>' for p in pdfs)
            pdf_chips  = f'<div class="pdf-list">{chips_html}</div>'

        # "Send & Mark Sent" — shown for all draft_ready positions
        send_btn = ""
        if r.get("status") == "draft_ready":
            pdf_note = f" + {len(pdfs)} PDF{'s' if len(pdfs)!=1 else ''}" if pdfs else ""
            if contact and "@" in contact:
                send_btn = (
                    f'<form method="post" action="/api/send-draft" style="display:inline"'
                    f' onsubmit="return confirm(\'Send to {contact}{pdf_note}?\')">'
                    f'<input type="hidden" name="pos_id" value="{pid}">'
                    f'<input type="hidden" name="kind" value="{kind}">'
                    f'<input type="hidden" name="contact" value="{contact}">'
                    f'<button class="ab send-email" type="submit">📤 Send & Mark Sent{pdf_note}</button></form>'
                )
            else:
                send_btn = (
                    f'<form method="post" action="/api/send-draft" style="display:inline">'
                    f'<input type="hidden" name="pos_id" value="{pid}">'
                    f'<input type="hidden" name="kind" value="{kind}">'
                    f'<input type="text" name="contact" placeholder="recipient@email.com"'
                    f' style="border:1px solid #ccc;border-radius:4px;padding:2px 6px;'
                    f'font-size:.73rem;width:170px;margin-right:4px" required>'
                    f'<button class="ab send-email" type="submit">📤 Send & Mark Sent{pdf_note}</button></form>'
                )

        detail = (
            f'<div class="detail-panel">'
            f'<div class="info">'
            f'<strong>{title[:80]}</strong><br>'
            f'{"📧 " + contact + "<br>" if contact else ""}'
            f'{"📝 " + notes[:100] + "<br>" if notes else ""}'
            f'</div>'
            f'<div class="actions">'
            f'{open_btn} {folder_btn} {send_btn} {sent_btn} {reject_btn}'
            f'<span style="font-size:.75rem;color:#888;align-self:center">'
            f'CLI: <code>{draft_cmd}</code></span>'
            f'</div></div>'
            f'{pdf_chips}{draft_preview}'
        )

        # Click-to-filter cells (JS filterBy — avoids <a>/<tr onclick> conflict)
        raw_country = r.get('country') or ''
        raw_track   = r.get('track') or ''
        raw_fit     = r.get('fit')
        _stop = "event.stopPropagation();"
        if raw_country:
            country_cell = (f'<span onclick="{_stop}filterBy(\'country\',\'{raw_country}\')" '
                            f'title="Filter: {raw_country}" style="cursor:pointer">'
                            f'{raw_country}</span>')
        else:
            country_cell = '—'
        if raw_track:
            track_cell = (f'<span onclick="{_stop}filterBy(\'track\',\'{raw_track}\')" '
                          f'title="Filter: {raw_track}" style="cursor:pointer;font-size:.75rem;'
                          f'background:#f0f4ff;border-radius:8px;padding:2px 7px">'
                          f'{raw_track}</span>')
        else:
            track_cell = ''
        if raw_fit is not None:
            fit_cell = (f'<span onclick="{_stop}filterBy(\'fit\',\'{raw_fit}\')" '
                        f'title="Filter fit={raw_fit}" style="cursor:pointer">'
                        f'{_fit_badge(raw_fit)}</span>')
        else:
            fit_cell = _fit_badge(raw_fit)

        body += (
            f'<tr class="clickable" onclick="toggleDetail(\'{pid}\')">'
            f'<td style="text-align:center;color:#bbb;font-size:.75rem;width:32px">{idx}</td>'
            f"<td><strong>{r.get('institution') or pid}</strong>"
            f"<br><small style='color:#aaa'>{pid}</small></td>"
            f"<td>{_deadline_fmt(r.get('deadline'))}</td>"
            f"<td>{_days_badge(r['days_left'])}</td>"
            f"<td>{fit_cell}</td>"
            f"<td>{exp_cell}</td>"
            f"<td>{track_cell}</td>"
            f"<td>{country_cell}</td>"
            f"<td>{_status_badge(r.get('status','found'))}</td>"
            f"<td style='color:#aaa;font-size:.75rem'>{added}</td>"
            f"<td></td>"
            f"</tr>"
            f'<tr class="detail-row" id="detail-{pid}">'
            f'<td colspan="10">{detail}</td>'
            f"</tr>"
        )
    return f"<table><thead>{header}</thead><tbody>{body}</tbody></table>"


def _stats_cards(st: dict, kind: str) -> str:
    bs = st["by_status"]
    total   = st["total"]
    pending = bs.get("found",0) + bs.get("draft_ready",0) + bs.get("watching",0)
    urgent  = 0  # can't compute without deadline data here
    return f"""<div class="stats">
      <div class="stat"><div class="num">{total}</div><div class="lbl">Total</div></div>
      <div class="stat"><div class="num">{pending}</div><div class="lbl">Pending</div></div>
      <div class="stat sent"><div class="num">{bs.get('sent',0)}</div><div class="lbl">Envoyés</div></div>
      <div class="stat"><div class="num">{bs.get('draft_ready',0)}</div><div class="lbl">Draft prêt</div></div>
      <div class="stat blue"><div class="num">{bs.get('replied',0)}</div><div class="lbl">Réponses</div></div>
      <div class="stat"><div class="num">{len(st['by_country'])}</div><div class="lbl">Countries</div></div>
    </div>"""


def _toolbar(action_url: str, sort: str, asc: int,
             countries: list[str], cur_country: str,
             cur_min_fit: str, cur_status: str,
             cur_track: str, cur_fit: str, form_id: str) -> str:

    def _qs(**overrides) -> str:
        p = dict(sort=sort, asc=asc, country=cur_country, status=cur_status,
                 track=cur_track, fit=cur_fit)
        p.update(overrides)
        return "&".join(f"{k}={v}" for k, v in p.items() if str(v) != "")

    def _chip(label: str, value: str, extra_cls: str = "") -> str:
        is_active = cur_status == value
        # clicking an active chip deactivates it (go back to default)
        target = "" if is_active else value
        active_cls = "active" if is_active else ""
        return f'<a href="{action_url}?{_qs(status=target)}" class="chip {extra_cls} {active_cls}">{label}</a>'

    chips = (
        _chip("À examiner", "found")
        + _chip("Draft prêt", "draft_ready", "chip-draft")
        + _chip("Envoyé", "sent", "chip-sent")
        + _chip("Répondu", "replied", "chip-replied")
        + _chip("Refusé", "rejected", "chip-rejected")
    )

    # Active filter badges — click to clear
    active = ""
    if cur_country:
        active += f'<a href="{action_url}?{_qs(country="")}" class="chip chip-sent active" style="font-size:.7rem">🌍 {cur_country} ✕</a>'
    if cur_track:
        active += f'<a href="{action_url}?{_qs(track="")}" class="chip chip-draft active" style="font-size:.7rem">📂 {cur_track} ✕</a>'
    if cur_fit:
        active += f'<a href="{action_url}?{_qs(fit="")}" class="chip chip-replied active" style="font-size:.7rem">⭐ fit={cur_fit} ✕</a>'

    return f"""<div class="toolbar">
      <label>🔍 <input id="lf" type="text" placeholder="Filter…" style="width:220px"></label>
    </div>
    <div class="chips">{chips}{(" <span style='color:#ccc'>|</span> " + active) if active else ""}</div>"""


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=RedirectResponse)
async def root():
    return "/phd"


@app.get("/phd", response_class=HTMLResponse)
async def phd_page(sort: str = "newest", asc: int = 1,
                   country: str = "", min_fit: str = "", status: str = "",
                   track: str = "", fit: str = "",
                   msg: str = "", err: str = ""):
    _min_fit = float(min_fit) if min_fit else None
    _fit     = int(float(fit)) if fit else None
    rows = get_positions(BASE_DIR, "phd", sort_by=sort, asc=bool(asc),
                         country=country or None, min_fit=_min_fit,
                         status=status or None)
    if status == "":
        rows = [r for r in rows if r.get("status") != "rejected"]
    if track:
        rows = [r for r in rows if r.get("track") == track]
    if _fit is not None:
        rows = [r for r in rows if int(float(r.get("fit") or 0)) == _fit]
    st   = get_stats(BASE_DIR)["phd"]
    ctr  = get_countries(BASE_DIR, "phd")
    fstate = _FilterState("/phd", sort, asc, country, min_fit, status, track, fit)
    content = (
        '<h2 style="margin-bottom:14px">PhD Positions</h2>'
        + _stats_cards(st, "phd")
        + _toolbar("/phd", sort, asc, ctr, country, min_fit, status, track, fit, "phdf")
        + _positions_html(rows, "phd", sort, bool(asc), fstate)
    )
    return HTMLResponse(_page(content, "phd",
                               flash=msg or err, flash_type="ok" if msg else "err"))


@app.get("/job", response_class=HTMLResponse)
async def job_page(sort: str = "newest", asc: int = 1,
                   country: str = "", min_fit: str = "", status: str = "",
                   track: str = "", fit: str = ""):
    _min_fit = float(min_fit) if min_fit else None
    _fit     = int(float(fit)) if fit else None
    rows = get_positions(BASE_DIR, "job", sort_by=sort, asc=bool(asc),
                         country=country or None, min_fit=_min_fit,
                         status=status or None)
    if status == "":
        rows = [r for r in rows if r.get("status") != "rejected"]
    if track:
        rows = [r for r in rows if r.get("track") == track]
    if _fit is not None:
        rows = [r for r in rows if int(float(r.get("fit") or 0)) == _fit]
    st   = get_stats(BASE_DIR)["job"]
    ctr  = get_countries(BASE_DIR, "job")
    fstate = _FilterState("/job", sort, asc, country, min_fit, status, track, fit)
    content = (
        '<h2 style="margin-bottom:14px">Job Positions</h2>'
        + _stats_cards(st, "job")
        + _toolbar("/job", sort, asc, ctr, country, min_fit, status, track, fit, "jobf")
        + _positions_html(rows, "job", sort, bool(asc), fstate)
    )
    return HTMLResponse(_page(content, "job"))


@app.get("/replied", response_class=HTMLResponse)
async def replied_page():
    """Dedicated page for all replied positions — see each professor's response."""
    phd_replied = get_positions(BASE_DIR, "phd", status="replied")
    job_replied = get_positions(BASE_DIR, "job", status="replied")

    def _cards(rows: list[dict], kind: str) -> str:
        if not rows:
            return '<p style="color:#aaa;font-style:italic">Aucune réponse</p>'
        html = ""
        for r in rows:
            reply_type = r.get("reply_type") or "—"
            reply_date = r.get("reply_date") or "—"
            notes      = r.get("notes") or ""
            contact    = r.get("contact") or "—"
            link       = r.get("link") or ""
            open_btn   = (f'<a href="{link}" target="_blank" style="float:right">'
                          f'<button class="ab open">↗ Open</button></a>') if link else ""
            color = {"positive": "#2e7d32", "negative": "#c62828",
                     "bounce": "#e65100", "info": "#1565c0"}.get(reply_type, "#555")
            html += f"""<div class="replied-card">
              {open_btn}
              <h4>{r.get('institution') or r['id']} — {r.get('title','')[:70]}</h4>
              <div class="meta">
                📧 Contact: <strong>{contact}</strong> &nbsp;|&nbsp;
                📅 Reply: <strong>{reply_date}</strong> &nbsp;|&nbsp;
                Type: <strong style="color:{color}">{reply_type}</strong>
              </div>
              {'<div class="notes">' + notes + '</div>' if notes else ''}
            </div>"""
        return html

    content = f"""
    <h2 style="margin-bottom:16px">Replied Positions</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
      <div>
        <div class="section-title">🎓 PhD ({len(phd_replied)})</div>
        {_cards(phd_replied, 'phd')}
      </div>
      <div>
        <div class="section-title">💼 Job ({len(job_replied)})</div>
        {_cards(job_replied, 'job')}
      </div>
    </div>"""
    return HTMLResponse(_page(content, "replied"))


@app.get("/stats", response_class=HTMLResponse)
async def stats_page():
    all_stats = get_stats(BASE_DIR)

    def _block(s: dict, label: str) -> str:
        by_s = "".join(
            f"<tr><td>{st}</td><td><strong>{n}</strong></td>"
            f"<td><div style='background:#145a45;height:8px;width:{min(n*8,200)}px;border-radius:4px'></div></td></tr>"
            for st, n in sorted(s["by_status"].items(), key=lambda x: -x[1])
        )
        by_c = "".join(
            f"<tr><td>{r['country']}</td><td><strong>{r['n']}</strong></td></tr>"
            for r in s["by_country"]
        )
        return f"""<div>
          <h3 style="margin-bottom:10px">{label} — {s['total']} positions</h3>
          <table><thead><tr><th>Status</th><th>N</th><th>Bar</th></tr></thead>
          <tbody>{by_s}</tbody></table>
          <br>
          <table><thead><tr><th>Country</th><th>N</th></tr></thead>
          <tbody>{by_c}</tbody></table>
        </div>"""

    content = (
        '<h2 style="margin-bottom:18px">Statistics</h2>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">'
        + _block(all_stats["phd"], "🎓 PhD")
        + _block(all_stats["job"], "💼 Job")
        + "</div>"
    )
    return HTMLResponse(_page(content, "stats"))


# ── REST API ──────────────────────────────────────────────────────────────────

@app.post("/api/open-folder")
async def api_open_folder(request: Request, pos_id: str = Form(...), kind: str = Form(...)):
    """Open position folder in Finder (macOS)."""
    import subprocess
    search_name = "PhD-Search" if kind == "phd" else "Job-Search"
    search_dir  = BASE_DIR / search_name

    # Prefer applied/ folder; fall back to found/<track>/<id>.md
    applied = BASE_DIR / search_name / "applied" / pos_id
    if applied.exists():
        path = applied
    else:
        from apply_tracker.tracker import _find_track_dir
        td = _find_track_dir(search_dir, pos_id, None)
        path = (td / f"{pos_id}.md") if td else search_dir

    try:
        subprocess.Popen(["open", str(path)])
    except Exception:
        pass

    # Return to same page
    ref = request.headers.get("referer", f"/{kind}")
    return RedirectResponse(ref, status_code=303)


@app.get("/api/positions")
async def api_positions(kind: str = "phd", status: str | None = None,
                        country: str | None = None, min_fit: float | None = None,
                        sort: str | None = None):
    return get_positions(BASE_DIR, kind, status=status,
                         country=country, min_fit=min_fit, sort_by=sort)


@app.post("/api/status")
async def api_status(request: Request, pos_id: str = Form(...), kind: str = Form(...),
                     status: str = Form(...)):
    kwargs = {}
    if status == "sent":
        kwargs["sent_date"] = date.today().isoformat()
    ok = mark_status(BASE_DIR, pos_id, kind, status, **kwargs)
    if ok:
        ref = request.headers.get("referer", f"/{kind}")
        return RedirectResponse(url=ref, status_code=303)
    return JSONResponse({"error": "position not found"}, status_code=404)


@app.get("/api/stats")
async def api_stats():
    return get_stats(BASE_DIR)


# ── Gmail sync ────────────────────────────────────────────────────────────────

@app.get("/auth/gmail/setup", response_class=HTMLResponse)
async def auth_gmail_setup():
    creds_path = str(_gmail.CREDS_FILE)
    content = f"""
    <h2 style="margin-bottom:16px">⚙ Gmail Setup</h2>
    <div style="background:white;border-radius:12px;padding:24px 28px;
                box-shadow:0 2px 8px rgba(0,0,0,.06);max-width:680px">
      <p style="margin-bottom:16px;color:#555;line-height:1.6">
        برای Sync خودکار، یک‌بار باید OAuth credentials از Google Cloud بسازی.
        فقط ۵ دقیقه وقت می‌برد.
      </p>
      <ol style="line-height:2.2;color:#333;padding-left:20px">
        <li>به <a href="https://console.cloud.google.com/apis/credentials"
            target="_blank" style="color:#145a45">console.cloud.google.com/apis/credentials</a> برو</li>
        <li>یک پروژه انتخاب یا بساز</li>
        <li>در منوی بالا: <strong>+ CREATE CREDENTIALS → OAuth client ID</strong></li>
        <li>Application type: <strong>Desktop app</strong></li>
        <li>Name: هر چیزی (مثلاً <em>amir-apply-tracker</em>)</li>
        <li>Download JSON → فایل را اینجا ذخیره کن:<br>
            <code style="background:#f5f5f5;padding:3px 8px;border-radius:4px;font-size:.85rem">
            {creds_path}</code></li>
        <li>مطمئن شو <strong>Gmail API</strong> فعال است در
            <a href="https://console.cloud.google.com/apis/library/gmail.googleapis.com"
            target="_blank" style="color:#145a45">APIs &amp; Services → Library</a></li>
      </ol>
      <div style="margin-top:20px">
        <a href="/auth/gmail/setup">
          <button class="ab open" style="padding:8px 20px;font-size:.85rem">
            🔄 Refresh (بعد از ذخیره فایل)
          </button>
        </a>
      </div>
    </div>"""
    return HTMLResponse(_page(content, ""))


@app.get("/auth/gmail", response_class=HTMLResponse)
async def auth_gmail(request: Request):
    """Start Google OAuth2 flow."""
    if not _gmail.creds_file_exists():
        return RedirectResponse("/auth/gmail/setup")
    callback = str(request.url_for("auth_gmail_callback"))
    try:
        auth_url = _gmail.start_auth_flow(callback)
        return RedirectResponse(auth_url)
    except Exception as e:
        content = (f'<div class="flash err">OAuth error: {e}<br>'
                   f'بررسی کن که فایل credentials درست است.</div>')
        return HTMLResponse(_page(content, ""))


@app.get("/auth/gmail/callback")
async def auth_gmail_callback(code: str = "", error: str = "", state: str = ""):
    """Receive OAuth2 callback, save token, redirect to /phd."""
    if error:
        return RedirectResponse(f"/phd?err=Gmail+auth+error:+{error}")
    if not code:
        return RedirectResponse("/phd?err=No+code+received+from+Google")
    ok = _gmail.complete_auth_flow(code)
    if ok:
        return RedirectResponse("/phd?msg=✓+Gmail+connected!+Now+click+Sync+Gmail.")
    return RedirectResponse("/phd?err=Auth+failed.+Check+credentials+file.")


@app.post("/api/send-draft")
async def api_send_draft(request: Request,
                         pos_id: str = Form(...),
                         kind: str = Form(...),
                         contact: str = Form(...)):
    """Find the Gmail draft for this position, attach PDFs, send it, mark as sent."""
    _, pdfs = _position_files(pos_id, kind)
    result  = _gmail.find_and_send_draft(contact, attachments=pdfs)
    ref     = request.headers.get("referer", f"/{kind}")
    base    = ref.split("?")[0]
    if not result.get("ok"):
        msg = result.get("message", "Send failed").replace(" ", "+")
        return RedirectResponse(f"{base}?err={msg}", status_code=303)
    mark_status(BASE_DIR, pos_id, kind, "sent",
                sent_date=date.today().isoformat())
    msg = result["message"].replace(" ", "+")
    return RedirectResponse(f"{base}?msg={msg}", status_code=303)


@app.post("/api/sync-gmail")
async def api_sync_gmail():
    """Fetch AMIR-SYNC drafts from Gmail and process them."""
    result = _gmail.fetch_and_process(BASE_DIR)
    if not result.get("ok"):
        return RedirectResponse(
            f"/phd?err={result.get('message','Sync failed')}", status_code=303)
    return RedirectResponse(
        f"/phd?msg={result['message']}", status_code=303)


# ── entry point ───────────────────────────────────────────────────────────────

def run_web(base_dir: Path, port: int = 8765, reload: bool = True) -> None:
    global BASE_DIR
    BASE_DIR = base_dir
    print(f"  🌐 Apply Tracker Web UI → http://localhost:{port}")
    print(f"  🌐 API docs             → http://localhost:{port}/api/docs")
    if reload:
        print(f"  👁 Watchdog active — auto-reload on file change")
        # reload=True requires app as import string
        import os
        os.environ["APPLY_BASE_DIR"] = str(base_dir)
        uvicorn.run(
            "apply_tracker.web:app",
            host="127.0.0.1",
            port=port,
            log_level="warning",
            reload=True,
            reload_dirs=[str(Path(__file__).parent)],
        )
    else:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 \
        else Path.home() / "@-Amir/Apply/2026-2027"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    run_web(base, port)
