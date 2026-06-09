#!/usr/bin/env python3
"""Daily PhD/Job alert — checks urgent deadlines and emails a summary."""
from __future__ import annotations

import base64
import sys
from email.mime.text import MIMEText
from pathlib import Path

ALERT_TO    = "sushiant60@gmail.com"
URGENT_DAYS = 7
NEW_DAYS    = 2   # high-fit positions added within this many days count as "new"


def _build_email(urgent: list[dict], high_fit: list[dict]) -> str:
    lines = ["PhD/Job Daily Alert\n" + "=" * 40]

    if urgent:
        lines.append(f"\n🔴 URGENT — deadline ≤{URGENT_DAYS} days ({len(urgent)} positions)\n")
        for r in urgent:
            dl   = r.get("deadline") or "--"
            left = r.get("days_left")
            left_str = f"{left}d" if left is not None else "--"
            fit  = r.get("fit") or "?"
            inst = r.get("institution") or r.get("id")
            lines.append(f"  [{left_str:>4}]  {inst:<35}  fit:{fit:<5}  deadline:{dl}")

    if high_fit:
        lines.append(f"\n🟡 HIGH FIT — pending, no deadline ({len(high_fit)} positions)\n")
        for r in high_fit:
            fit  = r.get("fit") or "?"
            inst = r.get("institution") or r.get("id")
            track = r.get("track") or ""
            lines.append(f"  fit:{fit:<5}  {inst:<35}  [{track}]")

    lines.append("\n---\nRun `amir apply web` to open the tracker.")
    return "\n".join(lines)


def _send_gmail(service, subject: str, body: str) -> bool:
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"]      = ALERT_TO
    msg["From"]    = ALERT_TO
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return True
    except Exception as e:
        print(f"  ❌ Gmail send failed: {e}", file=sys.stderr)
        return False


def run_alert(base_dir: Path) -> int:
    """Check positions and send alert if needed. Returns 0=sent, 1=nothing, 2=error."""
    from apply_tracker.gmail_sync import _get_credentials
    creds = _get_credentials()
    if creds is None:
        print("  ❌ Gmail not connected — run 'amir apply web' first", file=sys.stderr)
        return 2

    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("  ❌ google-api-python-client not installed", file=sys.stderr)
        return 2

    from apply_tracker.service import get_positions

    service = build("gmail", "v1", credentials=creds)

    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=NEW_DAYS)).isoformat()

    # Collect urgent positions across both kinds
    urgent   = []
    high_fit = []
    pending_statuses = {"found", "draft_ready"}

    for kind in ("phd", "job"):
        rows = get_positions(base_dir, kind=kind, sort_by="deadline", asc=True)
        for r in rows:
            if r.get("status") not in pending_statuses:
                continue
            days = r.get("days_left")
            fit_raw = r.get("fit") or ""
            try:
                fit_score = float(str(fit_raw).split("/")[0])
            except (ValueError, AttributeError):
                fit_score = 0.0

            if days is not None and 0 <= days <= URGENT_DAYS:
                urgent.append(r)
            elif days is None and fit_score >= 8:
                # Only include newly added high-fit positions
                added = (r.get("added_date") or "")[:10]
                if added >= cutoff:
                    high_fit.append(r)

    def _fit_key(r: dict) -> float:
        try:
            return float(str(r.get("fit") or "0").split("/")[0])
        except (ValueError, AttributeError):
            return 0.0

    urgent.sort(key=lambda r: r.get("days_left") or 9999)
    high_fit.sort(key=_fit_key, reverse=True)

    if not urgent and not high_fit:
        print("  ✓ Nothing urgent — no email sent.")
        return 1

    urgent_count   = len(urgent)
    highfit_count  = len(high_fit)
    subject_parts  = []
    if urgent_count:
        subject_parts.append(f"🔴 {urgent_count} urgent deadline{'s' if urgent_count > 1 else ''}")
    if highfit_count:
        subject_parts.append(f"🟡 {highfit_count} high-fit pending")
    subject = "PhD/Job Alert: " + " · ".join(subject_parts)

    body = _build_email(urgent, high_fit)
    ok   = _send_gmail(service, subject, body)

    if ok:
        print(f"  ✅ Alert sent → {ALERT_TO}")
        print(f"     {urgent_count} urgent, {highfit_count} high-fit")
        return 0
    return 2


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "@-Amir/Apply/2026-2027"
    sys.exit(run_alert(base))
