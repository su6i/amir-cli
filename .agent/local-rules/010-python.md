---
title: "010Python: Coding Standards"
description: Python specific coding standards, tools, and best practices.
location: .agent/rules/010-python.md
agent_priority: Medium
last_updated: 2026-02-21
---

# Python Standards

## Tools (Only these)
- Package manager: `uv sync` / `uv add` / `uv run`
- Formatter: `ruff format`
- Linter: `ruff check --fix`
- Type checker: `mypy` with strict mode
- Test: `pytest` with coverage

## Code
- Functions up to 20 lines — split if larger
- Mandatory Type hints for all public functions
- Docstrings for public functions (one line is enough)
- Error handling: Never use bare `except:`
- Logging instead of print in production code

## File Structure
src/
├── core/      # Main logic
├── api/       # API endpoints
├── models/    # Data models
└── utils/     # Helper functions

## Run after every change
`uv run ruff check --fix . && uv run mypy src/`
