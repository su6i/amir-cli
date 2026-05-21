---
description: Claude Code CLI configuration, subagent patterns, hooks, MCP, and settings for amir-cli development workflow.
updated: 2026-05-20
---

# Claude Code Integration

## Project Configuration

### Settings File (`.claude/settings.local.json`)
Controls which Bash commands Claude can run without asking permission:

```json
{
  "permissions": {
    "allow": [
      "Bash(amir *)",
      "Bash(ffmpeg *)",
      "Bash(ffprobe *)",
      "Bash(yt-dlp *)",
      "Bash(node *)",
      "Bash(python3 *)",
      "Bash(uv run *)",
      "Bash(pip install *)",
      "Bash(brew install *)",
      "Bash(git *)",
      "Bash(gh *)"
    ]
  }
}
```

**Rule:** Use wildcard patterns (`amir *`) not specific commands. One entry per tool family.

### CLAUDE.md (Project Memory)
Claude reads `CLAUDE.md` on every session start. Keep it updated with:
- Security rules (sensitive data check before commit)
- Architecture decisions with dates
- Key file map
- Active bugs and their workarounds

**Pattern:** After any non-trivial change, add a dated section to CLAUDE.md.

## Subagent Patterns

### When to spawn a subagent
```
Main context: write/edit code, ask questions, make decisions
Explore agent: read-only search ("find all callers of X", "list files matching *.sh")
Plan agent: design strategy before implementing
general-purpose: research + multi-step tasks with many tool calls
```

### Parallel subagent example
```
Two independent lookups → spawn both simultaneously:
- Agent 1 (Explore): "find where _subtitle_run is called"
- Agent 2 (Explore): "grep for AMIR_SUBTITLE_ env vars across the codebase"
→ Both results arrive together, faster than sequential.
```

### Subagent prompt template
```markdown
## Context
[What project this is, what you're trying to do, what you've already tried]

## Task
[Specific, bounded task]

## Expected Output
[Format, length, what to include/exclude]

## Do NOT
[Common mistakes or things to avoid]
```

## Plan Mode (`/plan`)

Use Plan Mode for any task that touches multiple files or has unclear scope:

1. Enter with `/plan` or spawn `Plan` subagent
2. Describe the task; agent returns step-by-step plan with file paths
3. Review and approve before exiting
4. Never exit plan mode prematurely — `/plan` approval is the gate before implementation

## Memory System

Auto-memory stored at: `/Users/su6i/.claude/projects/*/memory/`

Types:
- `user_*.md` — user profile, preferences
- `feedback_*.md` — corrections and confirmed approaches
- `project_*.md` — ongoing work, decisions, deadlines
- `reference_*.md` — where to find things in external systems

**Rule:** After any correction or confirmed non-obvious approach, save a feedback memory.

## Hooks (`.claude/settings.local.json`)

Hooks run shell commands before/after tool events:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "echo 'Running: $TOOL_INPUT'"}]
      }
    ]
  }
}
```

Useful hooks for amir-cli:
- `PreToolUse` on `Edit`: run `git diff --stat` to show scope before editing
- `PostToolUse` on `Bash`: capture long ffmpeg output to temp file instead of polluting context

## Slash Commands (User-Invocable Skills)

Custom skills can be triggered with `/skill-name` if registered. Claude Code reads skill files from the project when referenced in CLAUDE.md.

**To register a skill as a slash command:** Reference it in CLAUDE.md under "Available Skills" with the exact filename.

## MCP (Model Context Protocol)

MCP servers extend Claude Code with additional tools. Configure in `~/.claude/mcp_servers.json`:

```json
{
  "servers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Volumes/SanDisk"]
    }
  }
}
```

Useful for amir-cli: mount external drives (SanDisk subtitle folder) so Claude can read output files directly.

## Gotchas

- `.claude/settings.local.json` is NOT committed to git (sensitive permissions). Document the pattern in CLAUDE.md instead.
- `CLAUDE.md` IS committed. Never put personal data, API keys, or absolute paths to private files in it.
- Subagents start cold — they don't see the current conversation. Always include full context in the prompt.
- Claude Code reads `CLAUDE.md` from project root AND all parent directories up to `~/.claude/CLAUDE.md`.
