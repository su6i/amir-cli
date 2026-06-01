---
title: "000Core: Global Constitution"
description: Core project standards and non-negotiable behavior rules.
location: .agent/rules/000-core.md
agent_priority: High
last_updated: 2026-02-21
---

# Core Rules

## Cost Control (24/7 CRITICAL)
- Before any major task, declare its complexity: TRIVIAL / MODERATE / CRITICAL
- If complexity is TRIVIAL: Write code without extra explanation (fewer tokens)
- If unsure what to do: STOP and ask one question, not 10 questions
- Never edit more than 20 files in a single session without approval
- One task = one commit. Get approval before moving to the next task

## Response Structure (Token Efficiency)
- Start your responses with code, do not give extra explanation
- Use the format: "✅ done" / "❌ blocked: [reason]" / "❓ need: [question]"
- Never explain the code again if it has already been explained

## Project
- Language: Python 3.12+
- Package management: ONLY `uv` (no direct pip)
- Entry point: `main.py` at the root
- Config: ONLY use `config.yaml` or `.env` (no hardcoding)
- All variables in `config.yaml` — never leave hardcoded values in code

## On Error
- First read the error, then diagnose
- If not solved after 3 attempts: Report and wait for approval
- Never add dependencies without approval
