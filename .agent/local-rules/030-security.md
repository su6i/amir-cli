---
title: "030Security: Secret Protection"
description: Mandatory security standards and secret protection rules.
location: .agent/rules/030-security.md
agent_priority: Critical
last_updated: 2026-02-21
---

# Security Rules

## NEVER
- Never write any API key, password, or token directly in the code
- Do not add `.env` file to git (must be in .gitignore)
- Never log any secret
- Do not use `eval()` or `exec()` with user input
- Do not construct SQL queries with f-strings (SQL injection)

## Correct Pattern for Secrets
```python
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("DEEPSEEK_API_KEY")  # ✅ Correct
API_KEY = "sk-1234..."                    # ❌ Forbidden
```

## Check before every commit
- `git diff --staged | grep -i "api_key\|secret\|password\|token"`
- If there are results: STOP and report
