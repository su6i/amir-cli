# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## 2026-07-12 — clip clipboard-to-file, pdf split, completion fixes

- **feat(completions):** added `altacv-contact-up`/`altacv-contact-side` to
  `--template`'s tab-completion list (new ApplyForge template variants — see
  its own changelog).
- **fix(completions):** `amir apply <job-url> --template ... --stack ...` had the
  same fixed-word-position completion bug as `apply preview` — the dispatch
  only recognized `phd`/`job`/`sync`/`tui`/`web`/`stats`/`alert` as word 3, so
  a job URL (or any unrecognized word) at that position got zero completion
  for every flag after it. Now any non-keyword word 3 (a URL) routes through
  `_apply_arguments` the same way `preview` does. Also added `--stack` to
  `_apply_arguments` completion (see ApplyForge's own changelog for the
  feature itself).
- **fix(llm-lists):** replaced the `groq` provider with `grok` (xAI) across
  `lib/commands/llm-lists.sh`, completions, and docs — the owner has never
  used Groq (the LPU inference host) and only holds an xAI/Grok API key, so
  `groq` was dead weight that also collided by name with the unrelated
  `grok` model already used in `amir router --model grok`. `GROQ_API_KEY` →
  `GROK_API_KEY`, base URL → `https://api.x.ai/v1`.
- **fix(clip):** `amir clip <single-word-non-existing-file>` (e.g. `amir clip
  notes.md`) now saves the current clipboard content into that file, instead
  of overwriting the clipboard with the literal argument text. Multi-word
  arguments still copy as plain text (unchanged).
- **feat(pdf):** new `amir pdf split <file.pdf> --pages <spec> [--combined]
  [-o out]` subcommand, implemented via `qpdf`'s native page-range syntax.
  `--pages 1,3,4` / `1,2-3,4-8` produces one PDF per comma-separated group;
  `--combined` merges the selected pages/ranges into a single output PDF
  instead.
- **fix(completions):** `--theme` was never wired into `amir pdf`'s zsh
  completion — added, backed by a dynamic `_amir_pdf_themes` function that
  lists `lib/themes/*.css`.
- **fix(completions):** `amir apply preview --role <TAB>` and any flag typed
  after it stopped completing, because the dispatch only called
  `_apply_arguments` when `CURRENT == 4`. Now handled for `CURRENT >= 4`,
  matching the pattern already used by `subtitle`.
- **feat(completions):** `amir router` had no subcommand/flag completion at
  all (only the top-level command name completed) — added `audit`/`cost`/
  `models` subcommands and `-m/--model`, `-s/--session`, `--new`, `--system`,
  `--out`, `--plan` flags.
- **chore:** removed dead `chat)`/`code)` blocks from `completions/_amir` and
  deleted the orphaned `lib/commands/chat.sh`/`code.sh` — `amir chat`/`amir
  code` were already replaced by `amir router` at the entry-point dispatcher
  level, but the completion blocks and source files were never cleaned up,
  so tab-completion kept advertising two commands that no longer run.
- **docs:** documented the general fixed-position `case $((CURRENT))`
  completion pitfall in `docs/TECHNICAL.md` (§3) — it affected multiple
  commands and will resurface when adding new flag-style subcommands.

## 2026-07-06 — gitignore node_modules (wo-applyforge-0011)

- `lib/nodejs/node_modules/` was tracked in git (4177 files, never gitignored) —
  discovered while scrubbing leaked personal data from history, since it was the
  source of hundreds of unrelated npm-maintainer emails showing up in the audit.
  Purged from all history via `git filter-repo` and added to `.gitignore`.
  Restore locally with `npm install --prefix lib/nodejs`.

## 2026-07-06 — Apply Tracker moved to ApplyForge (wo-applyforge-0007)

- **Refactor:** `lib/python/apply_tracker/` deleted from this repo and moved to
  ApplyForge (`src/apply_tracker/`) — the tracker depends on ApplyForge's own
  CV-generation pipeline, so keeping it here duplicated that dependency.
  `amir apply web/tui/sync/stats/alert` and `amir phd`/`amir job` are unaffected
  from the user's side; internally they now shell out to ApplyForge via a new
  `_tracker_py()` helper in `lib/commands/apply.sh`
  (`cd "$APPLYFORGE_DIR" && uv run python -m src.apply_tracker.<module>`),
  the same wrap pattern already used for `amir apply <url>` → `main.py apply`.
  Data (tracking.json, tracker.db, the `~/@-Amir/Apply/2026-2027` vault) is
  untouched. Updated `docs/APPLY_TRACKER.md` and `docs/fa/APPLY_TRACKER_FA.md`
  architecture sections to reflect the new location.

## 2026-07-03 — init-project: three footguns removed

- **Targeted staging:** `init-project` now stages only the files it created or
  deliberately modified this run (tracked in an explicit list) instead of
  `git add src tests docs assets …`, which used to sweep pre-existing
  WIP/untracked files into the index. A pre-existing `main.py`/`.python-version`
  is never staged even when `uv init` runs. Re-running on an already-scaffolded
  repo stages nothing.
- **No silent Python scaffold:** on an existing repo with no stack markers
  (no pyproject/requirements/package.json/go.mod/Cargo.toml), `uv init` now
  asks interactively and skips when non-interactive — media/docs repos no
  longer get junk `pyproject.toml`/`main.py`. NEW projects keep the Python
  default.
- **Legacy submodule guard:** if `.agent/constitution` is a real directory
  (legacy submodule/clone), the command refuses and prints the migration steps.
  Previously `ln -sfn` dropped the symlink *inside* the directory
  (`.agent/constitution/agent-constitution`), leaving the submodule plus a junk
  nested link.

## 2026-07-03 — install the pre-merge-commit hook · neutral env var names

- **Renamed (no alias, breaking):** `AMIR_CONSTITUTION_URL` →
  `AGENT_CONSTITUTION_URL` (init-project clone URL) and
  `AMIR_CONSTITUTION_PATH` → `AGENT_CONSTITUTION_PATH` (sync-constitution
  source override). Constitution-related settings carry no personal branding —
  anyone adopting the constitution repo gets neutral `AGENT_*` names, matching
  the existing `AGENT_CONSTITUTION_DIR`. If you exported the old names in your
  shell profile, rename them.

- `amir init-project` and `amir update-projects` now install the constitution's
  new **`pre-merge-commit`** hook alongside `pre-commit`/`commit-msg`, so the
  privacy and skill-version gates also cover merge commits (git never runs
  pre-commit on automatic merges). Requires an agent-constitution clone that
  contains `templates/hooks/pre-merge-commit` — update the central clone first,
  otherwise the hook step reports a failure for that project.

## 2026-07-02 — init-project template: rule-050 compliance

- `init-project` no longer creates a per-project `TODO.md` anywhere (repo or
  vault) — tasks live only in the central `_memory/TODO.md` (rule 050); the
  command now prints a pointer instead.
- Generated `CLAUDE.md`: storage line points at the rule-035 vault `data/`
  dir (was `~/.<project>/`), and no absolute personal path is embedded
  (040 security check).
- Final summary output updated accordingly.

## [Unreleased] - 2026-07-02

### Fixed
- `amir init-project` — two rule-compliance fixes (035/040/045):
  - `.agent/constitution` is now a symlink to one central clone
    (`AGENT_CONSTITUTION_DIR`, default `~/@-github/agent-constitution`) instead
    of a per-repo `git submodule`, which pinned a SHA and drifted.
  - `TODO.md`/`SESSION.md` are created in the project's vault workspace
    (`~/.local/share/agent-projects/<slug>/workspace/`) instead of the repo
    root — these are per-session work-log files and must never be committed
    or even sit in the working tree. `.gitignore` also enforces this if
    either file is ever created locally by hand.
- `amir update-projects` — now detects and handles both the symlink pattern
  (refreshes the link; pulls the one central clone once up front, not per
  project) and the legacy submodule pattern (updated in place, unchanged
  behavior) so newly-scaffolded projects aren't silently skipped. New flag
  `--no-link` (`--no-submodule` kept as a back-compat alias).

## [Unreleased] - 2026-07-01

### Added
- `amir router` — single multi-model AI gateway wrapping the vault router
  (`~/.local/share/agent-projects/_router/delegate.py`): gemini/gemma (free tier),
  `deepseek-v4-flash`/`-pro`, `minimax` (prepaid default), `grok`. Conversation
  memory via `--session`, provider-echoed proof + cost ledger via
  `amir router audit`, provider model catalogs via `amir router models`, cost
  dashboard placeholder `amir router cost`. Routing policy lives in
  `_router/STRATEGY.md`. Natural prompts work unquoted:
  `amir router --model gemini write a fib function`.

### Removed
- `amir chat` and `amir code` — superseded by `amir router` (use
  `amir router --model gemini "..."` for the old free-tier behaviour). Handler
  files `lib/commands/chat.sh` and `code.sh` are left in place but no longer wired
  into the dispatcher; safe to delete later.

## [Unreleased] - 2026-06-22

### Added
- `amir init-project` and `amir update-projects` now install the constitution
  **`commit-msg`** hook alongside `pre-commit` (forbids AI co-authorship in commit
  messages — see agent-constitution `rules/040-git.md`).
- `amir pdf linkedin-post <folder>` renders trilingual (FR/EN/FA) LinkedIn posts
  with **WeasyPrint** via `lib/python/render_post.py` (guides + `guide.trilingue.pdf`
  + `carrousel.linkedin.pdf`), driven by a per-post `post.yml`. Subcommands let you
  rebuild only what changed: `carousel`, or `guide <fr en fa tri>` (one or several
  targets at once — e.g. `guide fa` rebuilds just the Persian guide). See
  `docs/TRILINGUAL_POSTS.md`.
- Guide body text is justified; bare URLs and the author signature render LTR, and
  « … » around a purely-Latin phrase are isolated LTR, even in the RTL Persian guide.
- Vendored fonts in `lib/fonts/` (Vazirmatn + DejaVu) and a restricted
  `FONTCONFIG_FILE` so macOS renders Persian/RTL correctly (no junk
  Noto-Yezidi / Hiragino / Microsoft-Sans fallbacks). Background skill:
  `.agent/constitution/skills/weasyprint-rtl-persian-pdf.md`.
- Auto-generation of YouTube PO-Token using `rustypipe-botguard`.
- `--normalize` flag to force FFmpeg transcoding to H.264/AAC for older macOS devices.
- `--po-token` flag to manually pass YouTube GVS PO tokens.
- `--yt-dlp-args` flag to manually pass underlying yt-dlp arguments.

### Changed
- AV1, VP9, and Opus formats are now preserved and played natively on modern macOS (via QuickTime), avoiding slow and unnecessary FFmpeg transcoding.

---

## [Unreleased] - 2026-06-12

### Added
- `amir img compress` — new subcommand to compress images to a target file size (default 300KB).
  - Binary-search JPEG quality (85→50) then auto dimension reduction (80%→20%) until target is met.
  - `--uniform`: auto-detects a common resize scale across all input files so outputs share the same physical dimensions (useful for document front/back pairs).
  - `--grayscale`: converts to grayscale before encoding — halves file size with no text readability loss, ideal for official documents and scans.
  - `--target KB`, `--min-quality`, `--max-quality`, `--overwrite`, `--suffix`, `-o dir`.
  - Full zsh autocompletion including flag values for `--target`, `--scale`, and `--max/min-quality`.

---

## [Unreleased] - 2026-06-09

### Changed
- `amir init-project` — production-grade scaffold output:
  - Constitution submodule now defaults to **HTTPS** (`https://github.com/su6i/agent-constitution.git`)
    for portability; override with `AMIR_CONSTITUTION_URL` (e.g. the SSH form).
  - Dropped `lib/` from the scaffold (collided with the `.gitignore` `lib/` pattern)
    and stopped creating `.storage/` dirs (data lives in `~/.<project>/`).
  - Adds `.gitkeep` to every empty dir so git actually tracks `src/ tests/ docs/ assets/`.
  - Detects the stack; for Python/unspecified runs `uv init --no-readme --vcs none
    --no-workspace` → `pyproject.toml` + pinned `.python-version`.
  - Generates starter `README.md` and `.env.example`; `TODO.md` opens with a
    First Session checklist.
  - `.gitignore` always enforces critical rules (`.storage/ .env .venv/
    __pycache__/ .DS_Store`) even when seeded from a template.

### Added
- `amir update-projects [base-dir]` — new command that propagates the latest
  constitution + `pre-commit` hook across every project under `base-dir`
  (default `$AMIR_PROJECTS_DIR` or `~/@-github`) that uses the constitution
  submodule. Idempotent and non-destructive. Flags: `--dry-run`, `--no-hook`,
  `--no-submodule`, `--exclude`. Excludes `amir-cli`/`agent-constitution` by
  default. Replaces the ad-hoc one-off shell loop.
- `amir init-project` installs the constitution `pre-commit` hook into every new
  project (blocks direct commits to `main` + enforces the docs checklist).

### Fixed
- `amir init-project` now **refuses** to create a project inside an existing git
  repo (the nesting footgun that corrupts submodules and lets `uv init` hijack a
  parent `pyproject.toml` workspace). Override with `AMIR_ALLOW_NESTED=1`.
- `uv init` is invoked with `--no-workspace` so it can never mutate a parent
  uv project's `pyproject.toml`.
