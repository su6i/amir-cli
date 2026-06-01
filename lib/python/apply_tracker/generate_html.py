"""Generate HTML tracker from tracking.json — called after every sync."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def _days_left(deadline: str | None) -> int | None:
    if not deadline:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return (datetime.strptime(deadline, fmt).date() - date.today()).days
        except ValueError:
            pass
    return None


def _deadline_badge(deadline: str | None) -> str:
    dl = _days_left(deadline)
    if deadline is None:
        return '<span class="deadline-badge watch">—</span>'
    label = deadline
    if dl is not None and dl < 0:
        return f'<span class="deadline-badge urgent">⚠️ {label}</span>'
    if dl is not None and dl <= 7:
        return f'<span class="deadline-badge urgent">{label}</span>'
    if dl is not None and dl <= 15:
        return f'<span class="deadline-badge soon">{label}</span>'
    if dl is not None and dl <= 60:
        return f'<span class="deadline-badge ok">{label}</span>'
    return f'<span class="deadline-badge watch">{label}</span>'


def _fit_badge(fit: str) -> str:
    try:
        val = float(str(fit).split("/")[0])
    except (ValueError, TypeError):
        return f'<span class="fit-score">{fit}</span>'
    color = "#2e7d32" if val >= 8 else "#f57f17" if val >= 6 else "#c62828"
    return f'<span class="fit-score" style="color:{color}">{fit}</span>'


def _status_badge(status: str) -> str:
    mapping = {
        "found":        ('grey',   'À examiner'),
        "draft_ready":  ('orange', 'Draft prêt'),
        "sent":         ('green',  '✅ Envoyé'),
        "replied":      ('blue',   '💬 Réponse reçue'),
        "watching":     ('purple', '👁 Surveillance'),
        "rejected":     ('red',    '❌ Refusé'),
        "bounced":      ('red',    '⚠️ Bounce'),
    }
    cls, label = mapping.get(status, ('grey', status))
    return f'<span class="badge {cls}">{label}</span>'


_COUNTRY_FLAGS = {
    "france": "🇫🇷", "artois": "🇫🇷", "inria": "🇫🇷", "montpellier": "🇫🇷",
    "paris": "🇫🇷", "grenoble": "🇫🇷", "lille": "🇫🇷", "rennes": "🇫🇷",
    "belgium": "🇧🇪", "leuven": "🇧🇪", "belgique": "🇧🇪", "uclouvain": "🇧🇪",
    "netherlands": "🇳🇱", "amsterdam": "🇳🇱",
    "germany": "🇩🇪", "munich": "🇩🇪", "berlin": "🇩🇪", "lmu": "🇩🇪", "tum": "🇩🇪",
    "canada": "🇨🇦", "mila": "🇨🇦", "montreal": "🇨🇦", "québec": "🇨🇦",
    "ireland": "🇮🇪", "ucd": "🇮🇪",
    "denmark": "🇩🇰", "aalborg": "🇩🇰", "copenhagen": "🇩🇰",
    "sweden": "🇸🇪", "chalmers": "🇸🇪", "orebro": "🇸🇪",
    "finland": "🇫🇮", "tampere": "🇫🇮",
    "switzerland": "🇨🇭", "eth": "🇨🇭",
    "austria": "🇦🇹", "linz": "🇦🇹", "graz": "🇦🇹",
    "germany": "🇩🇪",
    "greece": "🇬🇷", "athens": "🇬🇷",
}


def _flag(institution: str) -> str:
    low = institution.lower()
    for key, flag in _COUNTRY_FLAGS.items():
        if key in low:
            return flag
    return "🌍"


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── main generator ────────────────────────────────────────────────────────────

CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; color: #1a1a2e; }
  header { background: linear-gradient(135deg, #0d3b2e 0%, #145a45 100%); color: white; padding: 28px 40px; display: flex; justify-content: space-between; align-items: center; }
  header h1 { font-size: 1.4rem; font-weight: 700; letter-spacing: 0.5px; }
  header .meta { font-size: 0.8rem; opacity: 0.6; margin-top: 4px; }
  header .date { font-size: 0.85rem; opacity: 0.7; text-align: right; }
  .container { max-width: 1200px; margin: 0 auto; padding: 30px 20px; }
  .stats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; margin-bottom: 30px; }
  .stat-card { background: white; border-radius: 12px; padding: 18px 14px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
  .stat-card .num { font-size: 2rem; font-weight: 800; line-height: 1; }
  .stat-card .label { font-size: 0.72rem; color: #666; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-card.positions .num { color: #145a45; }
  .stat-card.urgent .num { color: #c62828; }
  .stat-card.sent .num { color: #2e7d32; }
  .stat-card.replied .num { color: #1565c0; }
  .stat-card.pending .num { color: #f57f17; }
  .stat-card.watch .num { color: #5e35b1; }
  .section { background: white; border-radius: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 24px; overflow: hidden; }
  .section-header { padding: 16px 24px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #f0f0f0; font-weight: 700; font-size: 0.95rem; }
  .section-header .icon { font-size: 1.2rem; }
  .section-header .count { margin-left: auto; background: #f0f0f0; border-radius: 20px; padding: 2px 10px; font-size: 0.78rem; color: #555; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #fafafa; padding: 10px 16px; text-align: left; font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; border-bottom: 1px solid #f0f0f0; }
  td { padding: 11px 16px; font-size: 0.85rem; border-bottom: 1px solid #f8f8f8; vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #f8fffc; }
  .badge { display: inline-block; padding: 3px 9px; border-radius: 20px; font-size: 0.72rem; font-weight: 600; }
  .badge.green { background: #e8f5e9; color: #2e7d32; }
  .badge.blue { background: #e3f2fd; color: #1565c0; }
  .badge.orange { background: #fff3e0; color: #e65100; }
  .badge.red { background: #fce4ec; color: #c62828; }
  .badge.purple { background: #f3e5f5; color: #6a1b9a; }
  .badge.grey { background: #f5f5f5; color: #555; }
  .badge.yellow { background: #fffde7; color: #f57f17; }
  .badge.teal { background: #e0f2f1; color: #00695c; }
  .fit-score { font-weight: 700; font-size: 0.9rem; }
  .action-item { display: flex; align-items: flex-start; gap: 14px; padding: 14px 24px; border-bottom: 1px solid #f0f0f0; }
  .action-item:last-child { border-bottom: none; }
  .action-prio { font-size: 1.1rem; flex-shrink: 0; padding-top: 2px; }
  .action-text { font-size: 0.85rem; }
  .action-text strong { display: block; margin-bottom: 3px; }
  .action-text .detail { color: #666; font-size: 0.78rem; }
  .action-text .deadline { color: #c62828; font-weight: 700; font-size: 0.78rem; display: block; margin-bottom: 2px; }
  .deadline-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }
  .deadline-badge.urgent { background: #fce4ec; color: #c62828; }
  .deadline-badge.soon { background: #fff3e0; color: #e65100; }
  .deadline-badge.ok { background: #e8f5e9; color: #2e7d32; }
  .deadline-badge.watch { background: #f3e5f5; color: #6a1b9a; }
  footer { text-align: center; padding: 20px; font-size: 0.75rem; color: #aaa; }
"""


def generate_html(search_dir: Path, track: str) -> str:
    """Generate full HTML for one track from its tracking.json."""
    tj = search_dir / "found" / track / "tracking.json"
    if not tj.exists():
        return ""
    data: dict = json.loads(tj.read_text())

    today_str = date.today().strftime("%-d %B %Y").replace(
        "January","janvier").replace("February","février").replace("March","mars").replace(
        "April","avril").replace("May","mai").replace("June","juin").replace(
        "July","juillet").replace("August","août").replace("September","septembre").replace(
        "October","octobre").replace("November","novembre").replace("December","décembre")

    track_label = {"ai_general": "AI General", "ai_finance": "AI Finance"}.get(track, track)

    # ── stats ─────────────────────────────────────────────────────────────────
    all_pos = list(data.items())
    total = len(all_pos)
    urgent = sum(1 for _, e in all_pos if (dl := _days_left(e.get("deadline"))) is not None and 0 <= dl <= 15)
    sent_count = sum(1 for _, e in all_pos if e.get("status") in ("sent", "replied", "bounced", "rejected"))
    replied_count = sum(1 for _, e in all_pos if e.get("status") == "replied")
    draft_count = sum(1 for _, e in all_pos if e.get("status") == "draft_ready")
    watch_count = sum(1 for _, e in all_pos if e.get("status") == "watching")

    # ── actions urgentes: positions with deadline <= 30 days or draft_ready ──
    action_items = []
    for pos_id, e in sorted(all_pos, key=lambda x: (_days_left(x[1].get("deadline")) or 9999)):
        dl = _days_left(e.get("deadline"))
        status = e.get("status", "found")
        if dl is None and status not in ("draft_ready", "watching"):
            continue
        if dl is not None and dl > 30 and status not in ("draft_ready",):
            continue
        if status in ("rejected", "bounced"):
            continue

        if status == "sent":
            prio = "✅"
        elif dl is not None and dl <= 0:
            prio = "🔴"
        elif dl is not None and dl <= 7:
            prio = "🔴"
        elif dl is not None and dl <= 15:
            prio = "🟠"
        else:
            prio = "🟡"

        title = _esc(e.get("title", pos_id))
        institution = _esc(e.get("institution", ""))
        deadline = e.get("deadline", "")
        dl_text = f"⏰ Deadline : {deadline}" + (f" — dans {dl} jours" if dl and dl > 0 else " — AUJOURD'HUI" if dl == 0 else " — PASSÉE" if dl and dl < 0 else "")
        notes = _esc(e.get("notes", ""))

        action_items.append(f"""
    <div class="action-item">
      <div class="action-prio">{prio}</div>
      <div class="action-text">
        <strong>{institution} — {title}</strong>
        <span class="deadline">{dl_text}</span>
        {f'<span class="detail">{notes}</span>' if notes else ''}
      </div>
    </div>""")

    if not action_items:
        action_items.append('<div style="padding:20px 24px;color:#aaa;font-size:0.9rem;">Aucune action urgente</div>')

    # ── pipeline table ────────────────────────────────────────────────────────
    pipeline_rows = []
    for pos_id, e in sorted(all_pos, key=lambda x: (_days_left(x[1].get("deadline")) or 9999)):
        if e.get("status") in ("rejected", "bounced"):
            continue
        institution = _esc(e.get("institution", pos_id))
        title = _esc(e.get("title", ""))
        flag = _flag(e.get("institution", "") + " " + e.get("location", ""))
        deadline = _deadline_badge(e.get("deadline"))
        fit = _fit_badge(e.get("fit", "?"))
        status = _status_badge(e.get("status", "found"))
        pipeline_rows.append(f"""
        <tr>
          <td><strong>{institution}</strong></td>
          <td>{flag}</td>
          <td>{title}</td>
          <td>{deadline}</td>
          <td>{fit}</td>
          <td>{status}</td>
        </tr>""")

    # ── sent table ────────────────────────────────────────────────────────────
    sent_rows = []
    for pos_id, e in all_pos:
        if e.get("status") not in ("sent", "replied"):
            continue
        institution = _esc(e.get("institution", pos_id))
        title = _esc(e.get("title", ""))
        flag = _flag(e.get("institution", "") + " " + e.get("location", ""))
        sent_date = _esc(e.get("sent_date") or "—")
        status = _status_badge(e.get("status", "sent"))
        sent_rows.append(f"""
        <tr>
          <td><strong>{institution}</strong></td><td>{flag}</td>
          <td>{title}</td><td>{sent_date}</td>
          <td>{status}</td>
        </tr>""")

    sent_section_body = "\n".join(sent_rows) if sent_rows else \
        '<tr><td colspan="5" style="text-align:center;color:#aaa;padding:20px">Aucun envoi</td></tr>'

    pipeline_body = "\n".join(pipeline_rows) if pipeline_rows else \
        '<tr><td colspan="6" style="text-align:center;color:#aaa;padding:20px">Aucune position</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Suivi Candidatures PhD — {track_label} — Amir SHIRALI POUR</title>
<style>{CSS}</style>
</head>
<body>

<header>
  <div>
    <h1>🤖 Suivi Candidatures PhD — {track_label}</h1>
    <div class="meta">Amir SHIRALI POUR — LLMs · Multi-Agent Systems · RAG · NLP Track</div>
  </div>
  <div class="date">
    Dernière mise à jour<br><strong>{today_str}</strong>
  </div>
</header>

<div class="container">

  <div class="stats">
    <div class="stat-card positions"><div class="num">{total}</div><div class="label">Positions trouvées</div></div>
    <div class="stat-card urgent"><div class="num">{urgent}</div><div class="label">Deadline &lt; 15j</div></div>
    <div class="stat-card sent"><div class="num">{sent_count}</div><div class="label">Envoyés</div></div>
    <div class="stat-card replied"><div class="num">{replied_count}</div><div class="label">Réponses</div></div>
    <div class="stat-card pending"><div class="num">{draft_count}</div><div class="label">Draft prêt</div></div>
    <div class="stat-card watch"><div class="num">{watch_count}</div><div class="label">À surveiller</div></div>
  </div>

  <div class="section">
    <div class="section-header"><span class="icon">🎯</span> Actions à faire — Par deadline</div>
    {"".join(action_items)}
  </div>

  <div class="section">
    <div class="section-header">
      <span class="icon">📋</span> Pipeline — Toutes les positions
      <span class="count">{len(pipeline_rows)}</span>
    </div>
    <table>
      <thead><tr><th>Institution</th><th>Pays</th><th>Sujet</th><th>Deadline</th><th>Fit</th><th>Statut</th></tr></thead>
      <tbody>{pipeline_body}</tbody>
    </table>
  </div>

  <div class="section">
    <div class="section-header">
      <span class="icon">✉️</span> Emails envoyés
      <span class="count">{len(sent_rows)}</span>
    </div>
    <table>
      <thead><tr><th>Institution</th><th>Pays</th><th>Sujet</th><th>Date envoi</th><th>Statut</th></tr></thead>
      <tbody>{sent_section_body}</tbody>
    </table>
  </div>

</div>

<footer>Amir SHIRALI POUR · Candidatures PhD {track_label} 2026–2027 · Mis à jour le {today_str}</footer>
</body>
</html>"""


_JOB_TRACK_LABELS = {
    "ai_ml":              "AI / ML",
    "devops":             "DevOps",
    "devops_alternance":  "DevOps Alternance",
    "polyvalent":         "Polyvalent",
    "ai_engineer":        "AI Engineer",
}

_PHD_TRACK_LABELS = {
    "ai_general": "AI General",
    "ai_finance": "AI Finance",
}


def generate_job_html(search_dir: Path, track: str) -> str:
    """Generate HTML tracker for a job track."""
    tj = search_dir / "found" / track / "tracking.json"
    if not tj.exists():
        return ""
    data: dict = json.loads(tj.read_text())

    today_str = date.today().strftime("%-d %B %Y").replace(
        "January","janvier").replace("February","février").replace("March","mars").replace(
        "April","avril").replace("May","mai").replace("June","juin").replace(
        "July","juillet").replace("August","août").replace("September","septembre").replace(
        "October","octobre").replace("November","novembre").replace("December","décembre")

    track_label = _JOB_TRACK_LABELS.get(track, track.replace("_", " ").title())

    all_pos = list(data.items())
    total = len(all_pos)
    urgent = sum(1 for _, e in all_pos if (dl := _days_left(e.get("deadline"))) is not None and 0 <= dl <= 15)
    sent_count = sum(1 for _, e in all_pos if e.get("status") in ("sent", "replied", "bounced", "rejected"))
    replied_count = sum(1 for _, e in all_pos if e.get("status") == "replied")
    draft_count = sum(1 for _, e in all_pos if e.get("status") == "draft_ready")
    watch_count = sum(1 for _, e in all_pos if e.get("status") == "watching")

    action_items = []
    for pos_id, e in sorted(all_pos, key=lambda x: (_days_left(x[1].get("deadline")) or 9999)):
        dl = _days_left(e.get("deadline"))
        status = e.get("status", "found")
        if dl is None and status not in ("draft_ready", "watching"):
            continue
        if dl is not None and dl > 30 and status not in ("draft_ready",):
            continue
        if status in ("rejected", "bounced"):
            continue

        prio = "✅" if status == "sent" else ("🔴" if dl is not None and dl <= 7 else ("🟠" if dl is not None and dl <= 15 else "🟡"))
        title = _esc(e.get("title", pos_id))
        institution = _esc(e.get("institution", ""))
        deadline = e.get("deadline", "")
        dl_text = f"⏰ Deadline : {deadline}" + (f" — dans {dl} jours" if dl and dl > 0 else " — AUJOURD'HUI" if dl == 0 else " — PASSÉE" if dl and dl < 0 else "") if deadline else ""
        notes = _esc(e.get("notes", ""))
        action_items.append(f"""
    <div class="action-item">
      <div class="action-prio">{prio}</div>
      <div class="action-text">
        <strong>{institution} — {title}</strong>
        {f'<span class="deadline">{dl_text}</span>' if dl_text else ''}
        {f'<span class="detail">{notes}</span>' if notes else ''}
      </div>
    </div>""")

    if not action_items:
        action_items.append('<div style="padding:20px 24px;color:#aaa;font-size:0.9rem;">Aucune action urgente</div>')

    pipeline_rows = []
    for pos_id, e in sorted(all_pos, key=lambda x: (_days_left(x[1].get("deadline")) or 9999)):
        if e.get("status") in ("rejected", "bounced"):
            continue
        institution = _esc(e.get("institution", pos_id))
        title = _esc(e.get("title", ""))
        location = _esc(e.get("location", ""))
        flag = _flag(e.get("institution", "") + " " + e.get("location", ""))
        deadline = _deadline_badge(e.get("deadline"))
        fit = _fit_badge(e.get("fit", "?"))
        status = _status_badge(e.get("status", "found"))
        pipeline_rows.append(f"""
        <tr>
          <td><strong>{institution}</strong></td>
          <td>{flag}</td>
          <td>{title}</td>
          <td>{location}</td>
          <td>{deadline}</td>
          <td>{fit}</td>
          <td>{status}</td>
        </tr>""")

    sent_rows = []
    for pos_id, e in all_pos:
        if e.get("status") not in ("sent", "replied"):
            continue
        institution = _esc(e.get("institution", pos_id))
        title = _esc(e.get("title", ""))
        flag = _flag(e.get("institution", "") + " " + e.get("location", ""))
        sent_date = _esc(e.get("sent_date") or "—")
        status = _status_badge(e.get("status", "sent"))
        sent_rows.append(f"""
        <tr>
          <td><strong>{institution}</strong></td><td>{flag}</td>
          <td>{title}</td><td>{sent_date}</td>
          <td>{status}</td>
        </tr>""")

    pipeline_body = "\n".join(pipeline_rows) if pipeline_rows else \
        '<tr><td colspan="7" style="text-align:center;color:#aaa;padding:20px">Aucune position</td></tr>'
    sent_section_body = "\n".join(sent_rows) if sent_rows else \
        '<tr><td colspan="5" style="text-align:center;color:#aaa;padding:20px">Aucun envoi</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Suivi Candidatures Job — {track_label} — Amir SHIRALI POUR</title>
<style>{CSS}</style>
</head>
<body>

<header>
  <div>
    <h1>💼 Suivi Candidatures Job — {track_label}</h1>
    <div class="meta">Amir SHIRALI POUR — Python · DevOps · AI/ML · France</div>
  </div>
  <div class="date">
    Dernière mise à jour<br><strong>{today_str}</strong>
  </div>
</header>

<div class="container">

  <div class="stats">
    <div class="stat-card positions"><div class="num">{total}</div><div class="label">Positions trouvées</div></div>
    <div class="stat-card urgent"><div class="num">{urgent}</div><div class="label">Deadline &lt; 15j</div></div>
    <div class="stat-card sent"><div class="num">{sent_count}</div><div class="label">Envoyés</div></div>
    <div class="stat-card replied"><div class="num">{replied_count}</div><div class="label">Réponses</div></div>
    <div class="stat-card pending"><div class="num">{draft_count}</div><div class="label">Draft prêt</div></div>
    <div class="stat-card watch"><div class="num">{watch_count}</div><div class="label">À surveiller</div></div>
  </div>

  <div class="section">
    <div class="section-header"><span class="icon">🎯</span> Actions à faire</div>
    {"".join(action_items)}
  </div>

  <div class="section">
    <div class="section-header">
      <span class="icon">📋</span> Pipeline — Toutes les positions
      <span class="count">{len(pipeline_rows)}</span>
    </div>
    <table>
      <thead><tr><th>Entreprise</th><th>Pays</th><th>Poste</th><th>Lieu</th><th>Deadline</th><th>Fit</th><th>Statut</th></tr></thead>
      <tbody>{pipeline_body}</tbody>
    </table>
  </div>

  <div class="section">
    <div class="section-header">
      <span class="icon">✉️</span> Emails envoyés
      <span class="count">{len(sent_rows)}</span>
    </div>
    <table>
      <thead><tr><th>Entreprise</th><th>Pays</th><th>Poste</th><th>Date envoi</th><th>Statut</th></tr></thead>
      <tbody>{sent_section_body}</tbody>
    </table>
  </div>

</div>

<footer>Amir SHIRALI POUR · Candidatures Job {track_label} 2026–2027 · Mis à jour le {today_str}</footer>
</body>
</html>"""


def regenerate_all(search_dir: Path, kind: str = "phd") -> None:
    """Regenerate HTML for all tracks in a search dir. kind='phd' or 'job'."""
    found = search_dir / "found"
    if not found.exists():
        return
    for track_dir in found.iterdir():
        if not track_dir.is_dir():
            continue
        tj = track_dir / "tracking.json"
        if not tj.exists():
            continue
        if kind == "job":
            html = generate_job_html(search_dir, track_dir.name)
            out_name = "suivi_candidatures_job.html"
        else:
            html = generate_html(search_dir, track_dir.name)
            out_name = "suivi_candidatures_PhD.html"
        if html:
            out = track_dir / out_name
            out.write_text(html, encoding="utf-8")
            print(f"  ✓ HTML regenerated: {track_dir.name} → {out_name}")


if __name__ == "__main__":
    import sys
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "@-Amir/Apply/2026-2027"
    regenerate_all(base / "PhD-Search", kind="phd")
    regenerate_all(base / "Job-Search", kind="job")
