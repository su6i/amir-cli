---
title: "050: Session Start Protocol"
description: At the start of every session, read TODO.md and announce pending items before taking any action.
location: .agent/rules/050-session-start.md
agent_priority: High
last_updated: 2026-06-01
---

# Session Start Protocol

## Rule (Non-Negotiable)

**At the start of every session — before any action — these steps are mandatory:**

1. Look for `TODO.md` in the project root
2. If it exists: read it and announce all open items grouped by priority level
3. Ask: "Where do we start?"

## Announcement Format

```
📋 TODO — [N] open items:

Level 1 (incomplete / in-progress):
  • [item title]

Level 2 (high-impact features):
  • [item title]

Level 3 (long-term):
  • [item title]

Known bugs:
  • [bug title]

Where do we start?
```

## Notes

- If `TODO.md` does not exist: inform the user and offer to create it
- `TODO.md` should be in `.gitignore` — it is a local workspace file, not tracked
- After completing or updating any item, update `TODO.md` immediately
- If the project has no `TODO.md`, check for `ROADMAP.md` or `TASKS.md` as alternatives

## Why This Rule Exists

Without a session-start announcement, context from previous sessions is lost and the agent
starts cold — repeating work, missing in-progress items, or asking the user to re-explain
what was already decided. This rule ensures continuity across sessions.
