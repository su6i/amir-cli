---
description: Best practices for writing robust Zsh completion scripts, avoiding common "bad substitution" errors and ensuring flag visibility.
---

# Skill: Robust Zsh Completion

This skill documents proven patterns for writing Zsh completion scripts (`_arguments`, `_describe`, `_files`) that avoid common errors like `bad substitution` and ensure a smooth user experience.

## 🛑 Common Pitfalls

1.  **Bad Substitution Error:** Often caused by malformed arrays passed to `_arguments` or `_values`, or incorrect variable expansion logic within the completion function.
2.  **Hidden Flags:** Flags (e.g., `-f`) not showing up until the user types the hyphen, or failing to autocomplete entirely.
3.  **Colon Confusion:** Descriptions containing `:` (e.g., "Quality: High") break completion parsing if not escaped or handled correctly.

## ✅ Best Practices

### 1. Use `_describe` for Simple Lists (Safest Option)
When you just want to offer a list of "Thing: Description", use `_describe`. It is far less fragile than `_values` or `_arguments` for simple positionals.

```bash
# Define array with 'Value:Description' format
local -a qualities
qualities=(
    '40:Smallest file (max compression)'
    '60:Balanced (Default)'
)
# -t acts as a group title
_describe -t qualities 'quality factor' qualities
```

### 2. Flags: Group Short & Long Versions
To ensure both `-h` and `--help` work and are recognized as the same option (so you don't complete `-h` if `--help` is already there), use the grouping syntax `{...}` in `_arguments`.

```bash
_arguments -s \
    '(-f --force)'{-f,--force}'[Force overwrite]' \
    '(-v --verbose)'{-v,--verbose}'[Show detailed logs]' \
    '*:filename:_files'
```
*   `(-f --force)`: This list tells Zsh that `-f` and `--force` are mutually exclusive (same option).
*   `{-f,--force}`: This expands to generate completion for both forms.

### 3. Handle Special Characters (Colons)
If your Description text contains a colon `:`, it **must** be escaped with a backslash if it's inside a string used by `_alternative` or complex `_arguments`. For `_describe`, standard "Value:Desc" format usually handles colons in Desc *after* the first separator well, but be careful.

```bash
# Valid for _alternative (note the escaped space and colon)
_alternative \
    'commands:Management:((stats\:Show\ AI\ data reset\:Reset\ data))'
```

### 4. Context Awareness with `CURRENT`
Don't define every flag globally if they only apply to specific subcommands or positions. Use `case $((CURRENT))` to scope completions.

```bash
_amir() {
    local cur context state line
    # Global context variables
    cur="${words[CURRENT]}"

    case "${words[2]}" in
        img)
            case $((CURRENT)) in
                3) _describe ... ;; # Sub-command
                4) _files ... ;;    # File argument
            esac
            ;;
    esac
}
```


### 5. Arrays for Dynamic content
Always declare arrays explicitly with `local -a` to avoid Zsh strict mode issues.

```bash
local -a options
options=('a:Option A' 'b:Option B')
_describe -t options 'my options' options
```

### 6. Breaking Recursive File Loops & Complex Subcommands
For complex logic (like switching context from files to flags), use **Helper Functions**. This avoids quoting hell and "bad substitution" errors in `_alternative`.

```bash
# Define helper at bottom of file
_my_options() {
    local -a opts=('a:Option A' 'b:Option B')
    _describe -t opts 'options' opts
}

# In Main Loop
if [[ -d "$prev" ]]; then
    # Switch context completely
    _alternative \
        'flags:Options:_my_options' 
else
    # mixed mode
    _alternative \
         'files:Files:_files' \
         'flags:Options:_my_options'
fi
```

### 7. Robust File Filtering (Space-Separated Globs)
For maximum compatibility and to avoid issues with `EXTENDED_GLOB` settings, use space-separated patterns instead of parentheses `|` groups. This is the most stable way to ensure only specific extensions are shown.

```bash
# STABLE: Posix-friendly space-separated globs
_files -g "*.mp4 *.mov *.mkv *.avi *.MP4 *.MOV *.MKV *.webm *.WEBM"

# AVOID: Sometimes fails if Zsh options aren't perfectly aligned
_files -g "*.(mp4|mov|mkv)"
```

### 8. Prioritizing Resolutions/Flags Over Files
To prevent a "stray PDF" from appearing when you want to suggest resolutions, use `_alternative`. If Zsh has a choice between a strict glob and a generic description, it might show both. By using `_alternative`, you can force priority.

```bash
# Pattern for amir compress: Priority to resolutions after first file
if [[ -n "${words[3]}" ]]; then
    _alternative \
        'resolutions:Resolution Options:_amir_resolutions' \
        'flags:Command Flags:_amir_flags'
    # NOTE: We OMIT _files here to stop suggesting more files once input is provided
fi
```

### 10. Context-Aware Subcommand Filtering
When a subcommand implies a specific input type (e.g. `batch` implies directories), ensure the completion reflects this by strictly filtering out other types. Don't show directories if the user is supposed to select a single file, and vice versa.

### 11. Strict File-Only Completion (Excluding Directories)
Even with `-g` (glob), `_files` usually includes directories for navigation. To strictly exclude directories (e.g., when a command ONLY accepts files and subcommands), use `_path_files -f`.

```bash
# STRICT: Only show video files, no directories for navigation
_path_files -f -g "*.mp4 *.mov *.mkv *.avi *.MP4 *.MOV *.MKV *.webm *.WEBM"
```

### 12. Forcing Headers/Grouping (Local Zstyle Injection)
If headers are bunched at the top or grouping isn't working in the user's environment, inject `zstyle` settings locally inside the completion function context.

```bash
_amir_audio() {
    # Force headers to appear directly above their respective items
    zstyle ":completion:${curcontext}:*" group-name ''
    zstyle ":completion:${curcontext}:*" format '-- %d --'

    _alternative \
        'cmds:Commands:((...))' \
        'dirs:Directories:_files -/'
}
```

---
*Updated: 2026-02-13 - Added Local Zstyle Injection & Robust Grouping.*
