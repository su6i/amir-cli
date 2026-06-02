#!/usr/bin/env python3
"""Gmail OAuth2 integration — fetch and process AMIR-SYNC drafts."""
from __future__ import annotations

import base64
from pathlib import Path

SCOPES      = ["https://www.googleapis.com/auth/gmail.modify"]
CREDS_FILE  = Path.home() / ".amir" / "gmail_credentials.json"
TOKEN_FILE  = Path.home() / ".amir" / "gmail_token.json"

# Holds the in-progress OAuth2 flow between /auth/gmail and /auth/gmail/callback
_pending_flow = None


# ── auth helpers ──────────────────────────────────────────────────────────────

def creds_file_exists() -> bool:
    return CREDS_FILE.exists()


def has_valid_token() -> bool:
    if not TOKEN_FILE.exists():
        return False
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds.valid:
            return True
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
            return True
    except Exception:
        pass
    return False


def _get_credentials():
    """Return valid Credentials object, refreshing if needed. Returns None if not authed."""
    if not TOKEN_FILE.exists():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds.valid:
            return creds
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
            return creds
    except Exception:
        pass
    return None


def start_auth_flow(callback_url: str) -> str:
    """Start OAuth2 flow. Returns the Google authorization URL."""
    global _pending_flow
    from google_auth_oauthlib.flow import Flow
    _pending_flow = Flow.from_client_secrets_file(
        str(CREDS_FILE), scopes=SCOPES, redirect_uri=callback_url)
    auth_url, _ = _pending_flow.authorization_url(
        prompt="consent", access_type="offline")
    return auth_url


def complete_auth_flow(code: str) -> bool:
    """Exchange authorization code for token and persist it. Returns True on success."""
    global _pending_flow
    if _pending_flow is None:
        return False
    try:
        _pending_flow.fetch_token(code=code)
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(_pending_flow.credentials.to_json())
        _pending_flow = None
        return True
    except Exception:
        _pending_flow = None
        return False


# ── Gmail body extraction ─────────────────────────────────────────────────────

def _extract_body(draft: dict) -> str:
    """Extract plaintext body from a Gmail API draft object (base64url-decoded)."""
    msg     = draft.get("message", {})
    payload = msg.get("payload", {})

    def _decode(part: dict) -> str:
        data = part.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return ""

    if payload.get("mimeType") == "text/plain":
        return _decode(payload)

    def _search(parts: list) -> str:
        for p in parts:
            if p.get("mimeType") == "text/plain":
                t = _decode(p)
                if t:
                    return t
            nested = p.get("parts", [])
            if nested:
                t = _search(nested)
                if t:
                    return t
        return ""

    return _search(payload.get("parts", []))


# ── main sync ─────────────────────────────────────────────────────────────────

def fetch_and_process(base_dir: Path) -> dict:
    """Fetch AMIR-SYNC Gmail drafts, create positions, trash drafts. Returns result dict."""
    creds = _get_credentials()
    if creds is None:
        return {"ok": False, "error": "not_authenticated",
                "message": "Gmail not connected. Click 'Connect Gmail' first."}

    try:
        from googleapiclient.discovery import build
    except ImportError:
        return {"ok": False, "error": "missing_dep",
                "message": "google-api-python-client not installed. Run: uv sync"}

    service = build("gmail", "v1", credentials=creds)

    # Search for drafts containing AMIR-SYNC
    resp   = service.users().drafts().list(userId="me", q="AMIR-SYNC").execute()
    drafts = resp.get("drafts", [])

    if not drafts:
        return {"ok": True, "added": 0, "skipped": 0, "trashed": 0,
                "message": "No AMIR-SYNC drafts found in Gmail."}

    bodies:    list[str] = []
    draft_ids: list[str] = []

    for d in drafts:
        full = service.users().drafts().get(
            userId="me", id=d["id"], format="full").execute()
        body = _extract_body(full)
        if body and ("TRACK:" in body):
            bodies.append(body)
            draft_ids.append(d["id"])

    if not bodies:
        return {"ok": True, "added": 0, "skipped": 0, "trashed": 0,
                "message": "Drafts found but no parseable TRACK: content."}

    # Parse + apply to SQLite / tracking.json
    from apply_tracker.sync import parse_sync_content, apply_positions
    positions = []
    for body in bodies:
        positions.extend(parse_sync_content(body))

    added, skipped = apply_positions(positions, base_dir)

    # Trash processed drafts
    trashed = 0
    for did in draft_ids:
        try:
            service.users().drafts().delete(userId="me", id=did).execute()
            trashed += 1
        except Exception:
            pass

    # Regenerate HTML trackers
    try:
        from apply_tracker.generate_html import regenerate_all
        phd_dir = base_dir / "PhD-Search"
        job_dir = base_dir / "Job-Search"
        if phd_dir.exists():
            regenerate_all(phd_dir, kind="phd")
        if job_dir.exists():
            regenerate_all(job_dir, kind="job")
    except Exception:
        pass

    return {
        "ok":      True,
        "added":   added,
        "skipped": skipped,
        "trashed": trashed,
        "message": f"✓ {added} added, {skipped} skipped, {trashed} draft(s) trashed.",
    }
