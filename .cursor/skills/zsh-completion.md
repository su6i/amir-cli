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

## Template: Robust Subcommand Structure

```bash
#compdef _myapp myapp

_myapp() {
    local cur context state line
    typeset -A opt_args

    _arguments -C \
        '1: :_cmds' \
        '*:: :->args'

    case $state in
        args)
            case $words[1] in
                deploy)
                    _arguments \
                        '(-e --env)'{-e,--env}'[Target environment]:env:(prod staging)' \
                        '*:file:_files'
                    ;;
            esac
            ;;
    esac
}

_cmds() {
    local -a commands
    commands=(
        'deploy:Deploy to server'
        'build:Build project'
    )
    _describe -t commands 'myapp commands' commands
}

_myapp "$@"
```
