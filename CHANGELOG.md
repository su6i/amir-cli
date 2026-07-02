# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
