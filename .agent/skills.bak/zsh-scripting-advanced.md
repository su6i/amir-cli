---
description: Advanced Zsh bash scripting patterns for amir-cli — SIGINT handling, option parsing, sourced function traps, error propagation, and pipeline robustness.
updated: 2026-05-20
---

# Advanced Zsh/Bash Scripting (amir-cli Patterns)

## SIGINT Handling in Sourced Functions

**Problem:** `trap` in a sourced function is shared with the parent shell. A naive `trap 'exit 130' INT` would kill the entire shell session.

**Correct pattern:**

```bash
my_function() {
    local _ABORTED=0
    # Save original trap, set our handler
    trap '_ABORTED=1' INT

    # Step 1
    some_command
    local _EC=$?
    if [[ $_ABORTED -eq 1 || $_EC -eq 130 ]]; then
        trap - INT          # CRITICAL: restore default trap before returning
        cleanup_temp_files
        return 130
    fi

    # Step 2
    another_command
    if [[ $_ABORTED -eq 1 ]]; then
        trap - INT
        return 130
    fi

    trap - INT              # Always restore at normal exit too
    echo "$RESULT"
}
```

**Rules:**
- ALWAYS `trap - INT` before every `return` path (normal and abort)
- Check `_ABORTED` after each blocking call
- Propagate exit code 130 up the call stack
- In `$()` command substitution, SIGINT doesn't propagate automatically — check `$?` after the subshell

### SIGINT propagation through command substitution

```bash
# WRONG: SIGINT to subshell doesn't set _ABORTED in parent
result=$(my_function_with_trap "$url")

# CORRECT: capture exit code explicitly
local _EC=0
result=$(my_function_with_trap "$url")
_EC=$?
if [[ $_EC -eq 130 ]]; then
    return 130
fi
```

## Option Parsing (robust getopts alternative)

For complex CLI functions, use a manual while-loop parser instead of `getopts`:

```bash
parse_args() {
    local -a positional=()
    local resolution=""
    local quality=40

    local _i=0
    local -a _args=("$@")
    while (( _i < ${#_args[@]} )); do
        local _cur="${_args[_i]}"
        case "$_cur" in
            --resolution|-R)
                resolution="${_args[_i+1]}"
                (( _i += 2 ))
                ;;
            --quality)
                quality="${_args[_i+1]}"
                (( _i += 2 ))
                ;;
            --flag-with-no-value)
                some_flag=true
                (( _i++ ))
                ;;
            -*)
                echo "Unknown option: $_cur" >&2
                return 1
                ;;
            *)
                positional+=("$_cur")
                (( _i++ ))
                ;;
        esac
    done
}
```

**Why not `getopts`:** doesn't support long options (`--resolution`), can't handle `--key value` with space.

## Unicode Dash Normalization

Users copy-paste from rich text and get em/en dashes instead of ASCII hyphens. Normalize before parsing:

```bash
normalize_dashes() {
    local s="$1"
    s="${s//$'–'/-}"   # en dash →  -
    s="${s//$'—'/-}"   # em dash →  -
    s="${s//$'−'/-}"   # minus sign → -
    echo "$s"
}

# In option loop:
_norm=$(normalize_dashes "$_cur")
case "$_norm" in
    --resolution|-R) ... ;;
esac
```

## Exit Code Conventions (amir-cli)

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error |
| 2 | Usage error (bad arguments) |
| 130 | SIGINT abort (Ctrl+C) |

**Rule:** Never swallow exit codes. Always `local _EC=$?` immediately after a command and check it.

## Parallel Job Detection

```bash
# Count running instances of a process
count_active_jobs() {
    local _pattern="$1"
    pgrep -f "$_pattern" 2>/dev/null | wc -l | tr -d ' '
}

# Example: check for parallel subtitle jobs
_active=$(pgrep -f "[p]ython(3)? .* -m subtitle" 2>/dev/null | wc -l | tr -d ' ')
if [[ -n "$_active" && "$_active" =~ ^[0-9]+$ && "$_active" -ge 1 ]]; then
    echo "Parallel job detected"
fi
```

Note: The `[p]` trick in the pattern prevents `pgrep` from counting itself.

## Safe Temp File Cleanup

```bash
# Create temp file and guarantee cleanup
_TMPFILE=$(mktemp /tmp/amir_XXXXXX)
trap "rm -f '$_TMPFILE'; trap - EXIT INT TERM" EXIT INT TERM

# Do work with $_TMPFILE ...

# Explicit cleanup (trap will also catch unexpected exits)
rm -f "$_TMPFILE"
trap - EXIT INT TERM
```

## Logging Helpers

```bash
# Consistent log levels (used in amir-cli)
log_info()  { echo "ℹ️  $*" >&2; }
log_warn()  { echo "⚠️  $*" >&2; }
log_error() { echo "❌ $*" >&2; }
log_ok()    { echo "✅ $*" >&2; }

# Never mix stdout (data output) with stderr (logs)
# stdout = file paths, JSON, pipe-able data
# stderr = human-readable progress, warnings, errors
```

## Zsh Array Pitfalls

```bash
# Zsh arrays are 1-indexed by default in zsh, but this code runs under bash
# amir-cli uses bash (#!/bin/bash), not zsh — arrays are 0-indexed

local -a arr=("a" "b" "c")
echo "${arr[0]}"    # "a" in bash, empty in zsh
echo "${arr[@]}"    # all elements (same in both)
echo "${#arr[@]}"   # count (same in both)

# Safe iteration (works in both):
for item in "${arr[@]}"; do
    echo "$item"
done
```

## String Escaping for FFmpeg Filter Arguments

```bash
# FFmpeg filter chains use commas and colons as separators
# Escape subtitle file path:
_esc_path="${subtitle_file//\\/\\\\}"   # backslashes first
_esc_path="${_esc_path//:/\\:}"         # colons
_esc_path="${_esc_path//,/\\,}"         # commas

# In filter string:
"subtitles='${_esc_path}':force_style='...'"
```

## Gotchas

1. `local` variables in bash functions are NOT truly local to subshells — they're inherited. Use `(subshell)` if you need true isolation.
2. `set -e` (errexit) is NOT used in amir-cli — functions use explicit `_EC=$?` checks for clarity.
3. In `while read` loops, Ctrl+C doesn't trigger `trap INT` — it terminates the subshell. Design accordingly.
4. `${arr[_i]}` with arithmetic variable: prefer `${arr[$_i]}` to avoid edge cases.
5. Empty array check: `[[ ${#arr[@]} -eq 0 ]]` not `[[ -z "$arr" ]]` (latter only checks first element).
