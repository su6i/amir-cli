# CLAUDE.md — Generic Agent Bootloader

This file is intentionally generic and **identical across all repositories**. It
contains **no project-specific, personal, or session data** — a committed
`CLAUDE.md` is public, so anything project- or person-specific here is a leak
(rule 035). Do not add such content to this file.

## Read First

1. `rules/DIGEST.md` — the short auto-generated list of non-negotiables (in this
   repo, or under `.agent/constitution/` if the constitution is vendored here).
2. `AGENTS.md` — the canonical agent entry point; it routes to the full `rules/`.

## Project-Specific Guidance

Anything specific to THIS project — architecture notes, module maps, per-project
conventions — lives in `CLAUDE.local.md`: **gitignored, never committed** (rule
040 blocks `*.local.md`). It may be a symlink to the project vault
(`<vault>/workspace/CLAUDE.local.md`, rule 035). Never put project or personal
detail in this committed file.

## Non-Negotiables (full text in `rules/`)

- Feature branch first; never commit to `main`.
- Commit format `[type]: [description]`; no AI co-authorship ever.
- English only in all repo content (rule 000 §Language Policy).
- No personal data, secrets, or hardcoded personal paths in any committed file.
- Merge only after owner approval; the owner pushes, never the agent.
