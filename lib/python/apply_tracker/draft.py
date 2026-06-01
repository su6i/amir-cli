#!/usr/bin/env python3
"""Email draft generation via DeepSeek API."""

import os
import sys
from datetime import date
from pathlib import Path

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from apply_tracker.tracker import parse_position_md, load_tracking, update_entry, _find_track_dir


# ── API key loader ─────────────────────────────────────────────────────────────

def _load_deepseek_key() -> str:
    for env in ("DEEPSEEK_API_KEY", "DEEPSEEK_API"):
        if os.environ.get(env):
            return os.environ[env]
    for path in [
        os.path.join(os.getcwd(), ".env"),
        os.path.expanduser("~/.amir/.env"),
        os.path.expanduser("~/.env"),
        os.path.expanduser("~/.amir/config"),
    ]:
        if not os.path.exists(path):
            continue
        try:
            for line in open(path):
                line = line.strip()
                for prefix in ("DEEPSEEK_API_KEY=", "DEEPSEEK_API="):
                    if line.startswith(prefix):
                        key = line.split("=", 1)[1].strip().strip("\"'")
                        if key and "REPLACE" not in key:
                            return key
        except Exception:
            pass
    return ""


# ── prompt builders ────────────────────────────────────────────────────────────

PHD_PROMPT = """Tu es un assistant expert en candidatures académiques.

## Profil du candidat
{profile}

## Poste visé
{position}

## Profil du superviseur (recherché au préalable)
{supervisor_profile}

## Consignes strictes
1. Écris un email de candidature complet en {lang}.
2. Utilise la civilité exacte du superviseur (ex: "Monsieur de Lima," ou "Madame X,") — jamais "Madame, Monsieur".
3. Référence NOMMÉMENT au moins un article récent du superviseur et montre le lien avec l'expérience du candidat.
4. Montre le lien direct entre l'expérience MARL/multi-agents/LLM du candidat et le sujet.
5. Longueur : 3-4 paragraphes concis. Pas de formules creuses.
6. Termine avec une signature complète (nom, diplôme, email, LinkedIn, ville).
7. NE PAS inclure les années d'expérience sauf si le poste l'exige explicitement.
8. Format de sortie : commence directement par l'objet de l'email, puis le corps complet.

Objet: [sujet précis, pas générique]

[Corps du message]
"""

JOB_PROMPT = """Tu es un assistant expert en candidatures professionnelles.

## Profil du candidat
{profile}

## Poste visé
{position}

## Consignes strictes
1. Écris un email de candidature/relance/cold outreach en {lang}.
2. Adapte le ton au contexte (candidature directe, relance, cold email).
3. Mets en avant les compétences techniques les plus pertinentes.
4. Longueur : 3 paragraphes maximum. Direct et professionnel.
5. Termine avec une signature complète.
6. Format de sortie : commence par l'objet, puis le corps complet.

Objet: [sujet précis]

[Corps du message]
"""


def _build_supervisor_profile(search_dir, pos_id: str, track: str | None) -> str:
    """Extract supervisor profile from tracking.json for use in prompt."""
    if not track:
        return "⚠️  Profil superviseur non renseigné — lancer d'abord: amir apply phd research <id>"
    try:
        track_dir = search_dir / "found" / track
        data = load_tracking(track_dir)
        entry = data.get(pos_id, {})
        sup = entry.get("supervisor")
        if not sup:
            return (
                "⚠️  Profil superviseur manquant dans tracking.json.\n"
                "Avant d'envoyer ce draft, rechercher le superviseur dans Claude Code :\n"
                "  > amir apply phd show <id>  puis mettre à jour tracking.json avec clé 'supervisor'."
            )
        lines = [
            f"Nom : {sup.get('name', '?')}",
            f"Genre : {'Masculin' if sup.get('gender') == 'M' else 'Féminin' if sup.get('gender') == 'F' else '?'}",
            f"Titre : {sup.get('title', '?')}",
            f"Civilité à utiliser : {sup.get('salutation', '?')}",
            f"Email : {sup.get('email', '?')}",
            f"Laboratoire : {sup.get('lab', '?')}",
        ]
        if sup.get("research_areas"):
            lines.append("Axes de recherche : " + ", ".join(sup["research_areas"]))
        if sup.get("key_papers"):
            lines.append("Publications clés :")
            for p in sup["key_papers"]:
                lines.append(f"  - {p}")
        if sup.get("workshops"):
            lines.append("Activités récentes : " + "; ".join(sup["workshops"]))
        return "\n".join(lines)
    except Exception as e:
        return f"(erreur lecture profil superviseur: {e})"


def _build_email_draft_md(pos_id: str, position_info: dict,
                           generated_text: str, search_type: str) -> str:
    today = date.today().strftime("%d/%m/%Y")
    title = position_info.get("title", pos_id)
    institution = position_info.get("institution", "")
    deadline = position_info.get("deadline", "—")
    fit = position_info.get("fit", "?")
    contact = position_info.get("contact", "")
    link = position_info.get("link", "")

    header = f"""# Brouillon email — {institution} — {title[:60]}
**Fit : {fit} | Deadline : {deadline} | Généré le {today}**

---

## Métadonnées

| Champ | Valeur |
|-------|--------|
| **À** | {contact} |
| **Objet** | (voir corps ci-dessous) |
| **Lien** | {link} |

---

## Corps du message

{generated_text.strip()}
"""
    return header


# ── main generation function ───────────────────────────────────────────────────

def generate_draft(
    search_dir: Path,
    pos_id: str,
    search_type: str = "phd",
    force: bool = False,
    lang: str | None = None,
    track: str | None = None,
) -> int:
    # Find position file
    found_dir = search_dir / "found"
    pos_file = None
    pos_track = track

    if track:
        candidate = found_dir / track / f"{pos_id}.md"
        if candidate.exists():
            pos_file = candidate
    else:
        for td in found_dir.iterdir():
            if not td.is_dir():
                continue
            candidate = td / f"{pos_id}.md"
            if candidate.exists():
                pos_file = candidate
                pos_track = td.name
                break

    if not pos_file:
        print(f"ERROR: position file not found for '{pos_id}'", file=sys.stderr)
        return 1

    # Check for existing draft
    applied_dir = search_dir / "applied" / pos_id
    draft_file = applied_dir / "email_draft.md"

    if draft_file.exists() and not force:
        print(f"Draft already exists: {draft_file}")
        print("Use --force to regenerate.")
        return 0

    # Parse position
    pos_info = parse_position_md(pos_file)
    effective_lang = lang or pos_info.get("lang", "Français")
    if effective_lang.lower() in ("fr", "français", "french"):
        effective_lang = "français"
    else:
        effective_lang = "anglais"

    # Load profile
    context_dir = search_dir.parent / "context"
    profile_file = context_dir / "profile.md"
    if not profile_file.exists():
        # Fallback: PhD-Search context
        profile_file = search_dir.parent / "PhD-Search" / "context" / "profile.md"
    if not profile_file.exists():
        profile_file = search_dir / "context" / "profile.md"

    profile_text = profile_file.read_text() if profile_file.exists() else "(profile not found)"
    position_text = pos_file.read_text()

    # Load supervisor profile from tracking.json if available
    supervisor_profile_text = _build_supervisor_profile(search_dir, pos_id, pos_track)

    # Build prompt
    template = PHD_PROMPT if search_type == "phd" else JOB_PROMPT
    prompt = template.format(
        profile=profile_text,
        position=position_text,
        lang=effective_lang,
        supervisor_profile=supervisor_profile_text,
    ) if search_type == "phd" else template.format(
        profile=profile_text,
        position=position_text,
        lang=effective_lang,
    )

    # API call
    api_key = _load_deepseek_key()
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not found. Set it in ~/.amir/.env or env.", file=sys.stderr)
        return 1
    if not HAS_OPENAI:
        print("ERROR: openai package not installed. Run: uv add openai", file=sys.stderr)
        return 1

    print(f"  Generating draft for {pos_id} (DeepSeek)...")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1200,
        )
        generated = resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"ERROR: DeepSeek API call failed: {e}", file=sys.stderr)
        return 1

    # Save draft
    applied_dir.mkdir(parents=True, exist_ok=True)
    content = _build_email_draft_md(pos_id, pos_info, generated, search_type)
    draft_file.write_text(content)

    # Update tracking
    if pos_track:
        track_dir = found_dir / pos_track
        update_entry(track_dir, pos_id, status="draft_ready")

    print(f"  ✓ Saved → {draft_file}")
    return 0


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("search_dir")
    p.add_argument("pos_id")
    p.add_argument("--force", action="store_true")
    p.add_argument("--lang")
    p.add_argument("--track")
    p.add_argument("--type", dest="search_type", default="phd")
    args = p.parse_args()

    sys.exit(generate_draft(
        Path(args.search_dir),
        args.pos_id,
        search_type=args.search_type,
        force=args.force,
        lang=args.lang,
        track=args.track,
    ))
