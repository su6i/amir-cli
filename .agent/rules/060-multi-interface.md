---
title: "060MultiInterface: Single Core, Multiple Shells Architecture"
description: Standard architecture for projects requiring multiple interfaces (CLI, Web, Telegram, Browser Extension). Defines layer separation, directory structure, and integration rules.
location: .agent/rules/060-multi-interface.md
agent_priority: High
last_updated: 2026-06-01
---

# Single Core, Multiple Shells Architecture

## When This Rule Applies

Any project that exposes its functionality through **more than one interface** — CLI + Web UI, CLI + Telegram bot, or any combination — must follow this architecture.

---

## Core Principle

Business logic lives in one place. Interfaces are thin shells that translate user input into core function calls.

FastAPI is the **universal adapter**, not the application brain. Once the API layer exists, every other interface (Telegram bot, Chrome extension, mobile app, Raycast) becomes a thin HTTP client.

```
┌──────────────────────────────────────────────────┐
│                  Core / Services                  │
│          (pure Python, no I/O, no HTTP)           │
└───────────────────────┬──────────────────────────┘
                        │
               ┌────────▼────────┐
               │   FastAPI App   │  ← universal adapter
               │   PORT configed │    (not the brain)
               └──┬──────────┬───┘
                  │          │
     ┌────────────▼──┐    ┌──▼──────────────────┐
     │  CLI (main.py)│    │  Web UI (Jinja2)     │
     │  direct call  │    │  served by FastAPI   │
     └───────────────┘    └─────────────────────┘
                                   │
               ┌───────────────────┼───────────────┐
               │                   │               │
     ┌─────────▼──┐    ┌───────────▼──┐  ┌────────▼──────┐
     │  Telegram   │    │   Chrome     │  │  Future       │
     │  Webhook    │    │   Extension  │  │  clients      │
     │  → FastAPI  │    │  HTTP fetch  │  │               │
     └────────────┘    └──────────────┘  └───────────────┘
```

---

## Standard Directory Structure

```
my_project/
├── src/
│   ├── core/        # Pure business logic and algorithms — NO HTTP, NO I/O
│   ├── schemas/     # Pydantic models for validation (used by ALL layers)
│   ├── services/    # External I/O: databases, LLMs, third-party APIs
│   ├── api/         # FastAPI routers, middlewares, webhooks
│   ├── cli/         # CLI entry points (Typer or argparse) → call core/services
│   ├── bot/         # Telegram webhook handlers → delegate to core/services
│   └── web/         # Static files or Jinja2 templates
├── tests/
└── main.py          # Entry point: subcommands (serve, telegram, etc.)
```

---

## Non-Negotiable Rules

### 1. No I/O in core/
Files inside `core/` must never handle HTTP requests, read user input, or call external services directly. They receive data as Python objects and return Python objects. Period.

### 2. Validation in schemas/, not only in routers
Pydantic models belong in `src/schemas/` and must be used by **core functions** too — not just FastAPI endpoints. This ensures CLI and other direct callers get the same data integrity guarantees.

```python
# ✅ correct — validation happens before reaching any interface
async def discover(params: DiscoverParams) -> list[Author]:  # DiscoverParams is a Pydantic model
    ...

# ❌ wrong — validation only in the FastAPI router
@router.post("/discover")
async def discover_endpoint(params: DiscoverParams):
    raw_params = {"keywords": params.keywords}  # now CLI gets no validation
    return await discover_raw(raw_params)
```

### 3. Telegram bot uses Webhook, not Long-Polling
When a FastAPI server is already running, the Telegram bot must integrate as a webhook endpoint (`POST /webhook/telegram`) — not as a separate long-polling process. This keeps the architecture unified and reduces resource usage.

```python
# ✅ correct — webhook registered in FastAPI
@router.post("/webhook/telegram")
async def telegram_webhook(update: dict):
    await bot_handler.process(update)
```

### 4. CORS configured from day one
Chrome extensions and any browser-based client make cross-origin requests. `CORSMiddleware` must be configured at project start — not added later when bugs appear.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "http://localhost:*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5. Interfaces are thin — no business logic
Files in `api/`, `cli/`, `bot/` may only: parse input → call core/services → format output. If a route handler or command function exceeds ~15 lines of logic, that logic belongs in `core/` or `services/`.

### 6. One entry point, multiple subcommands
`main.py` is the single entry point for all modes:

```bash
uv run python main.py serve      # FastAPI + Web UI on configured port
uv run python main.py telegram   # Telegram webhook server
uv run python main.py discover   # CLI mode
```

---

## Testing Strategy

Because `core/` has no I/O dependencies, unit tests require no HTTP mocking:

```python
# Unit test — no FastAPI, no HTTP, no mocking
async def test_discover_filters_by_min_papers():
    result = await discover(DiscoverParams(keywords=["nlp"], min_papers=3))
    assert all(a.papers_count >= 3 for a in result)
```

Integration tests cover the API layer separately using `httpx.AsyncClient`.

---

## See Also

- `.agent/rules/lang/python/fastapi.md` — FastAPI-specific coding rules (routers, async, schemas)
- `.agent/rules/010-python.md` — Python standards (uv, ruff, mypy)
