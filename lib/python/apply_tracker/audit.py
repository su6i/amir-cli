#!/usr/bin/env python3
"""Manager-agent audit for PhD apply workflow.

Runs after CV + lettre de motivation are produced and checks:
  1. Supervisor profile — researched and complete
  2. One-folder rule — ApplyForge/Applied/<date>_<id>/ has all files
  3. Lettre de motivation — personalized salutation, named paper, CLIL/project hook
  4. CV — key sections in correct order (Language Acquisition before Finance)
  5. Tracking status consistency
"""

import json
import re
import sys
from pathlib import Path
from datetime import date, datetime

PASS = "✅"
WARN = "⚠️ "
FAIL = "❌"

# Required files in the apply folder
REQUIRED_FILES = ["CV", "Lettre", "JobPosting", "Email"]


# ── helpers ────────────────────────────────────────────────────────────────────

def _find_apply_folder(applyforge_dir: Path, pos_id: str) -> Path | None:
    applied = applyforge_dir / "Applied"
    if not applied.exists():
        return None
    # Extract meaningful keywords from pos_id (skip 2-letter country codes)
    keywords = [w.lower() for w in pos_id.split("_") if len(w) > 3]
    candidates = []
    for d in applied.iterdir():
        if not d.is_dir():
            continue
        dname = d.name.lower()
        # Exact pos_id match
        if pos_id.lower() in dname:
            return d
        # Keyword match: folder must contain at least 2 keywords from pos_id
        matches = sum(1 for kw in keywords if kw in dname)
        if matches >= 2:
            candidates.append((matches, d))
    if candidates:
        candidates.sort(key=lambda x: (-x[0], x[1].name), reverse=False)
        return candidates[-1][1]
    return None


def _read_tex_or_pdf_text(folder: Path, keyword: str) -> str:
    """Return text of first .tex file whose name contains keyword."""
    for f in folder.iterdir():
        if keyword.lower() in f.name.lower() and f.suffix == ".tex":
            try:
                return f.read_text(errors="ignore")
            except Exception:
                pass
    return ""


def _check(label: str, ok: bool, detail: str = "", warn_only: bool = False) -> tuple[str, bool]:
    icon = PASS if ok else (WARN if warn_only else FAIL)
    line = f"  {icon}  {label}"
    if detail:
        line += f"\n         {detail}"
    return line, ok


# ── audit sections ─────────────────────────────────────────────────────────────

def audit_supervisor(entry: dict) -> list[tuple[str, bool]]:
    results = []
    sup = entry.get("supervisor")
    if not sup:
        results.append((f"  {FAIL}  Supervisor profile missing in tracking.json\n"
                        "         Run: amir apply phd research <id>  then update tracking.json", False))
        return results

    results.append(_check("Supervisor researched", True,
                           f"{sup.get('name','?')} — {sup.get('title','?')}"))
    results.append(_check("Supervisor gender known",
                           sup.get("gender") in ("M", "F"),
                           f"gender={sup.get('gender','?')}"))
    results.append(_check("Salutation personalized",
                           bool(sup.get("salutation")) and "Monsieur" in sup.get("salutation","") or "Madame" in sup.get("salutation",""),
                           f"salutation='{sup.get('salutation','')}'"))
    results.append(_check("Key papers recorded",
                           bool(sup.get("key_papers")),
                           f"{len(sup.get('key_papers',[]))} paper(s)"))
    results.append(_check("Research areas recorded",
                           bool(sup.get("research_areas")),
                           f"{', '.join(sup.get('research_areas',[])[:3])}"))
    results.append(_check("Research date present",
                           bool(sup.get("researched_date")),
                           sup.get("researched_date","missing"), warn_only=True))
    return results


def audit_folder(apply_folder: Path | None, pos_id: str) -> list[tuple[str, bool]]:
    results = []
    if not apply_folder:
        results.append((f"  {FAIL}  Apply folder not found in ApplyForge/Applied/\n"
                        f"         Run: amir apply phd lettre {pos_id}", False))
        return results

    results.append(_check("Apply folder exists", True, str(apply_folder)))

    files = list(apply_folder.iterdir())
    names = " ".join(f.name for f in files)

    has_cv = any("CV" in f.name and f.suffix == ".pdf" for f in files)
    has_lettre = any("Lettre" in f.name and f.suffix == ".pdf" for f in files)
    has_job = any("JobPosting" in f.name for f in files)
    has_email = any("Email" in f.name or "email" in f.name for f in files)

    results.append(_check("CV PDF present", has_cv))
    results.append(_check("Lettre de motivation PDF present", has_lettre))
    results.append(_check("Job posting present", has_job))
    results.append(_check("Email draft present", has_email))
    return results


def audit_lettre(apply_folder: Path | None, sup: dict | None) -> list[tuple[str, bool]]:
    results = []
    if not apply_folder:
        return results

    text = _read_tex_or_pdf_text(apply_folder, "Lettre")
    if not text:
        results.append((f"  {WARN}  Lettre .tex not found — cannot audit content", False))
        return results

    # Salutation check
    has_generic = bool(re.search(r"Madame,\s*Monsieur", text))
    results.append(_check("No generic 'Madame, Monsieur'", not has_generic,
                           "Found generic salutation — must be personalized" if has_generic else ""))

    if sup:
        name_parts = sup.get("name", "").split()
        last_name = name_parts[-1] if name_parts else ""
        has_name = last_name and last_name.lower() in text.lower()
        results.append(_check(f"Supervisor name ({last_name}) in lettre", has_name))

        papers = sup.get("key_papers", [])
        paper_found = False
        for paper in papers:
            first_word = paper.split()[0].lower()
            if len(first_word) > 3 and first_word in text.lower():
                paper_found = True
                break
        results.append(_check("Supervisor paper referenced", paper_found,
                               "Name at least one key paper by the supervisor"))

    has_clil = "CLIL" in text or "LinguaGame" in text or "persuasif" in text.lower() or "jeu" in text.lower()
    results.append(_check("Project hook present (CLIL/LinguaGame/persuasif)", has_clil,
                           warn_only=not has_clil))

    has_adum = "ADUM" in text or "adum.fr" in text
    results.append(_check("ADUM portal mentioned", has_adum, warn_only=True))

    word_count = len(text.split())
    ok_length = 300 < word_count < 750
    results.append(_check(f"Lettre length ({word_count} words, target 400–650)",
                           ok_length, "Too long — trim to fit 1 page" if word_count >= 750 else
                           ("Too short" if word_count <= 300 else ""), warn_only=word_count >= 750))

    # Page count — must be exactly 1 page
    pdf_file = next((f for f in apply_folder.iterdir()
                     if "Lettre" in f.name and f.suffix == ".pdf"), None)
    if pdf_file:
        try:
            import subprocess
            out = subprocess.check_output(["pdfinfo", str(pdf_file)],
                                          stderr=subprocess.DEVNULL, text=True)
            pages_line = next((l for l in out.splitlines() if "Pages:" in l), "")
            n_pages = int(pages_line.split()[-1]) if pages_line else 0
            results.append(_check(f"Lettre is 1 page (got {n_pages})",
                                   n_pages == 1,
                                   "Shorten the lettre — a PhD cover letter must fit on 1 page"))
        except Exception:
            results.append((f"  {WARN}  Could not check PDF page count (pdfinfo missing)", False))
    return results


def audit_cv(apply_folder: Path | None, entry: dict | None = None) -> list[tuple[str, bool]]:
    results = []
    if not apply_folder:
        return results

    text = _read_tex_or_pdf_text(apply_folder, "CV")
    if not text:
        results.append((f"  {WARN}  CV .tex not found — cannot audit content", False))
        return results

    results.append(_check("CV compiles (tex present)", True))

    # Derive priority keywords from supervisor research areas (not hardcoded)
    priority_keywords: list[str] = []
    if entry:
        sup = entry.get("supervisor", {})
        areas = sup.get("research_areas", [])
        title = entry.get("title", "")
        # Map research areas → CV section keywords
        area_text = " ".join(areas + [title]).lower()
        if any(w in area_text for w in ["game", "persuasif", "ludique", "clil", "language", "learning"]):
            priority_keywords.append("AI for Language Acquisition")
        if any(w in area_text for w in ["epistemic", "belief", "cognitive", "reasoning", "logic"]):
            priority_keywords.append("AI for Research Automation")
        if any(w in area_text for w in ["speech", "tts", "audio", "voice"]):
            priority_keywords.append("Speech Processing")

    # Check that priority sections exist
    for section in priority_keywords:
        results.append(_check(f"Section '{section}' present in CV", section in text))

    # Check priority sections appear before non-priority ones (position-aware)
    if priority_keywords:
        positions = {s: text.find(s) for s in priority_keywords if s in text}
        non_priority = ["Deep Learning for Financial", "Speech Processing"]
        for prio in list(positions.keys())[:2]:
            for non in non_priority:
                if non in text and non not in positions:
                    non_pos = text.find(non)
                    prio_pos = positions[prio]
                    results.append(_check(
                        f"'{prio[:30]}' before '{non[:25]}'",
                        prio_pos < non_pos,
                        "Most relevant sections should appear first",
                        warn_only=True
                    ))
                    break

    # Project-specific keyword checks (derived from supervisor/title)
    if entry:
        sup = entry.get("supervisor", {})
        areas = sup.get("research_areas", [])
        title = entry.get("title", "").lower()
        area_text = " ".join(areas).lower()

        if "game" in area_text or "ludique" in title or "persuasif" in title:
            results.append(_check("LinguaGame / CLIL present for gaming-focused position",
                                   "LinguaGame" in text or "CLIL" in text))
        if "epistemic" in area_text or "belief" in area_text:
            results.append(_check("Epistemic Logic / belief revision mentioned",
                                   "Epistemic" in text or "belief" in text.lower(),
                                   warn_only=True))
    return results


def audit_tracking(entry: dict, pos_id: str) -> list[tuple[str, bool]]:
    results = []
    deadline = entry.get("deadline")
    if deadline:
        try:
            dl = datetime.strptime(deadline, "%Y-%m-%d").date()
            days = (dl - date.today()).days
            urgent = days <= 7
            results.append(_check(f"Deadline: {deadline} ({days}d left)",
                                   days > 0,
                                   "OVERDUE" if days <= 0 else ("URGENT — send today" if days <= 3 else ""),
                                   warn_only=days > 0 and days <= 7))
        except ValueError:
            pass

    status = entry.get("status", "found")
    results.append(_check(f"Status: {status}", True))
    results.append(_check("Contact email recorded", bool(entry.get("contact")),
                           entry.get("contact", "missing")))
    return results


# ── main ───────────────────────────────────────────────────────────────────────

def run_audit(search_dir: Path, pos_id: str, applyforge_dir: Path) -> int:
    from apply_tracker.tracker import load_tracking

    found_dir = search_dir / "found"
    pos_track = None
    for td in found_dir.iterdir():
        if not td.is_dir():
            continue
        tj = td / "tracking.json"
        if not tj.exists():
            continue
        data = json.loads(tj.read_text())
        if pos_id in data:
            pos_track = td.name
            entry = data[pos_id]
            break
    else:
        print(f"❌  Position '{pos_id}' not found in tracking.json", file=sys.stderr)
        return 1

    apply_folder = _find_apply_folder(applyforge_dir, pos_id)
    sup = entry.get("supervisor")

    print()
    print(f"  ══════════════════════════════════════════════════════")
    print(f"  🔍  AUDIT — {pos_id}")
    title = entry.get("title", "")[:60]
    if title:
        print(f"       {title}")
    print(f"  ══════════════════════════════════════════════════════")

    sections = [
        ("TRACKING", audit_tracking(entry, pos_id)),
        ("SUPERVISOR RESEARCH", audit_supervisor(entry)),
        ("ONE-FOLDER STRUCTURE", audit_folder(apply_folder, pos_id)),
        ("LETTRE DE MOTIVATION", audit_lettre(apply_folder, sup)),
        ("CV QUALITY", audit_cv(apply_folder, entry)),
    ]

    total = passed = 0
    blockers = []

    for section_name, checks in sections:
        print(f"\n  ── {section_name}")
        for line, ok in checks:
            print(line)
            total += 1
            if ok:
                passed += 1
            elif FAIL in line:
                blockers.append(line.strip())

    score = int(passed / total * 100) if total else 0
    print()
    print(f"  ══════════════════════════════════════════════════════")
    print(f"  Score: {passed}/{total} checks passed ({score}%)")

    if blockers:
        print(f"\n  {FAIL}  Blockers to fix before sending:")
        for b in blockers:
            print(f"       • {b[:80]}")
    elif score == 100:
        print(f"\n  {PASS}  All checks passed — ready to send!")
    else:
        print(f"\n  {WARN}  Minor issues — review warnings above")

    print(f"  ══════════════════════════════════════════════════════")
    print()
    return 0 if not blockers else 1


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("search_dir")
    p.add_argument("pos_id")
    p.add_argument("--applyforge", default=None)
    args = p.parse_args()

    import os
    applyforge = Path(args.applyforge) if args.applyforge else \
        Path(os.environ.get("APPLYFORGE_DIR", Path.home() / "@-github/ApplyForge"))

    sys.exit(run_audit(Path(args.search_dir), args.pos_id, applyforge))
