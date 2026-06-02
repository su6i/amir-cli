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

import os as _os
BASE_DIR = Path(_os.environ.get("APPLY_BASE_DIR",
                str(Path.home() / "@-Amir/Apply/2026-2027")))
app = FastAPI(title="Apply Tracker", docs_url="/api/docs")

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
.replied-card{background:white;border-radius:10px;padding:16px 20px;margin-bottom:14px;
              box-shadow:0 2px 8px rgba(0,0,0,.06);border-left:4px solid #1565c0}
.replied-card h4{font-size:.9rem;margin-bottom:6px}
.replied-card .meta{font-size:.78rem;color:#666;margin-bottom:8px}
.replied-card .notes{font-size:.83rem;color:#333;white-space:pre-wrap}
.section-title{font-size:1rem;font-weight:700;margin:20px 0 12px;color:#145a45}
footer{text-align:center;padding:14px;font-size:.71rem;color:#aaa;margin-top:16px}
"""


def _page(content: str, active: str = "phd") -> str:
    today = date.today().strftime("%d %B %Y")
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
  </nav>
</header>
<div class="container">{content}</div>
<footer>Amir SHIRALI POUR · Apply Tracker · {today}</footer>
<script>
const fi=document.getElementById('lf');
if(fi) fi.addEventListener('input',()=>{{
  const q=fi.value.toLowerCase();
  document.querySelectorAll('tbody tr').forEach(tr=>{{
    tr.style.display=tr.textContent.toLowerCase().includes(q)?'':'none';
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
</script></body></html>"""


def _th(label: str, col: str, sort: str, asc: bool) -> str:
    cls = ' class="sorted"' if col == sort else ""
    arrow = ("↑" if asc else "↓") if col == sort else ""
    return f'<th{cls} data-col="{col}">{label} {arrow}</th>'


def _positions_html(rows: list[dict], kind: str, sort: str, asc: bool) -> str:
    header = (
        f"<tr>{_th('Institution','institution',sort,asc)}"
        f"{_th('Deadline','deadline',sort,asc)}"
        f"{_th('Days','days',sort,asc)}"
        f"{_th('Fit','fit',sort,asc)}"
        f"{_th('Track','track',sort,asc)}"
        f"{_th('Country','country',sort,asc)}"
        f"{_th('Status','status',sort,asc)}"
        f"<th>Actions</th></tr>"
    )
    body = ""
    for r in rows:
        pid  = r["id"]
        link = r.get("link") or ""
        open_btn = (f'<a href="{link}" target="_blank">'
                    f'<button class="ab open">Open</button></a>') if link else ""
        sent_btn = "" if r.get("status") in ("sent","replied") else (
            f'<form method="post" action="/api/status" style="display:inline">'
            f'<input type="hidden" name="pos_id" value="{pid}">'
            f'<input type="hidden" name="kind" value="{kind}">'
            f'<input type="hidden" name="status" value="sent">'
            f'<button class="ab sent" type="submit">✓ Sent</button></form>')
        body += (
            f"<tr>"
            f"<td><strong>{r.get('institution') or pid}</strong>"
            f"<br><small style='color:#aaa'>{pid}</small></td>"
            f"<td>{_deadline_fmt(r.get('deadline'))}</td>"
            f"<td>{_days_badge(r['days_left'])}</td>"
            f"<td>{_fit_badge(r.get('fit'))}</td>"
            f"<td>{r.get('track','')}</td>"
            f"<td>{r.get('country') or '—'}</td>"
            f"<td>{_status_badge(r.get('status','found'))}</td>"
            f"<td>{open_btn} {sent_btn}</td>"
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
             cur_min_fit: float, cur_status: str, form_id: str) -> str:
    c_opts = "<option value=''>All countries</option>" + "".join(
        f"<option {'selected' if c==cur_country else ''}>{c}</option>"
        for c in countries
    )
    s_opts = "".join(
        f"<option {'selected' if s==cur_status else ''}>{s}</option>"
        for s in ["", "found", "draft_ready", "sent", "replied", "watching"]
    )
    return f"""<div class="toolbar">
      <label>🔍 <input id="lf" type="text" placeholder="Filter…" style="width:180px"></label>
      <label>Country:
        <select name="country" form="{form_id}"
                onchange="document.getElementById('{form_id}').submit()">{c_opts}</select>
      </label>
      <label>Min fit:
        <input type="number" name="min_fit" form="{form_id}"
               min="0" max="10" value="{cur_min_fit or ''}" style="width:54px" placeholder="0">
      </label>
      <label>Status:
        <select name="status" form="{form_id}">{s_opts}</select>
      </label>
      <form id="{form_id}" method="get" action="{action_url}">
        <input type="hidden" name="sort" value="{sort}">
        <input type="hidden" name="asc" value="{asc}">
        <button type="submit" class="ab open">Apply</button>
      </form>
    </div>"""


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=RedirectResponse)
async def root():
    return "/phd"


@app.get("/phd", response_class=HTMLResponse)
async def phd_page(sort: str = "deadline", asc: int = 1,
                   country: str = "", min_fit: float = 0, status: str = ""):
    rows = get_positions(BASE_DIR, "phd", sort_by=sort,
                         country=country or None, min_fit=min_fit or None,
                         status=status or None)
    st   = get_stats(BASE_DIR)["phd"]
    ctr  = get_countries(BASE_DIR, "phd")
    content = (
        '<h2 style="margin-bottom:14px">PhD Positions</h2>'
        + _stats_cards(st, "phd")
        + _toolbar("/phd", sort, asc, ctr, country, min_fit, status, "phdf")
        + _positions_html(rows, "phd", sort, bool(asc))
    )
    return HTMLResponse(_page(content, "phd"))


@app.get("/job", response_class=HTMLResponse)
async def job_page(sort: str = "deadline", asc: int = 1,
                   country: str = "", min_fit: float = 0, status: str = ""):
    rows = get_positions(BASE_DIR, "job", sort_by=sort,
                         country=country or None, min_fit=min_fit or None,
                         status=status or None)
    st   = get_stats(BASE_DIR)["job"]
    ctr  = get_countries(BASE_DIR, "job")
    content = (
        '<h2 style="margin-bottom:14px">Job Positions</h2>'
        + _stats_cards(st, "job")
        + _toolbar("/job", sort, asc, ctr, country, min_fit, status, "jobf")
        + _positions_html(rows, "job", sort, bool(asc))
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
            open_btn   = (f'<a href="{link}" target="_blank">'
                          f'<button class="ab open" style="float:right">Open</button></a>') if link else ""
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

@app.get("/api/positions")
async def api_positions(kind: str = "phd", status: str | None = None,
                        country: str | None = None, min_fit: float | None = None,
                        sort: str | None = None):
    return get_positions(BASE_DIR, kind, status=status,
                         country=country, min_fit=min_fit, sort_by=sort)


@app.post("/api/status")
async def api_status(pos_id: str = Form(...), kind: str = Form(...),
                     status: str = Form(...)):
    kwargs = {}
    if status == "sent":
        kwargs["sent_date"] = date.today().isoformat()
    ok = mark_status(BASE_DIR, pos_id, kind, status, **kwargs)
    if ok:
        return RedirectResponse(url=f"/{kind}", status_code=303)
    return JSONResponse({"error": "position not found"}, status_code=404)


@app.get("/api/stats")
async def api_stats():
    return get_stats(BASE_DIR)


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
