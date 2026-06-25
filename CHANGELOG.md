# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
