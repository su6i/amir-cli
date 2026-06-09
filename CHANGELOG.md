# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- `amir init-project` installs the constitution `pre-commit` hook into every new
  project (blocks direct commits to `main` + enforces the docs checklist).

### Fixed
- `amir init-project` now **refuses** to create a project inside an existing git
  repo (the nesting footgun that corrupts submodules and lets `uv init` hijack a
  parent `pyproject.toml` workspace). Override with `AMIR_ALLOW_NESTED=1`.
- `uv init` is invoked with `--no-workspace` so it can never mutate a parent
  uv project's `pyproject.toml`.
