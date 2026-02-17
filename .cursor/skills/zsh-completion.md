---
name: zsh-completion
description: Zsh Completion Technical Encyclopedia: 'compdef' Architecture, '_arguments' Parameter Specs, Zstyle Caching, and Error Handling.
---

# Skill: Robust Zsh Completion (Technical Encyclopedia)

Comprehensive technical protocols for the design and implementation of advanced command-line completion systems for the Zsh shell in the 2025 ecosystem. This document defines the standards for `compdef` orchestration, `_arguments` parameter specifications, and high-performance `zstyle` caching.

[Back to README](../../README.md)

---

## 1. The Zsh Completion System (Compsys)
Standardizing the architecture of `_`-prefixed completion functions.

### 1.1 `compdef` Orchestration Logic
*   **The Entry Point:** Utilizing `#compdef command_name` as the top-line directive to register the function with the shell's completion engine (v2).
*   **Function Naming:** Mandatory use of the `_`-prefix (e.g., `_my_tool`).
*   **Initialization:** Utilizing `compinit` in `.zshrc` to activate the programmable completion system.

### 1.2 `_arguments` Parameter Specification
The "Core Engine" for most Zsh completions. Use grouping `{...}` to sync short and long flags.
```zsh
_my_tool() {
  _arguments -s -S \
    '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \
    '(-h --help)'{-h,--help}'[Show help message]' \
    '--mode[Select mode]:mode:(fast slow auto)' \
    '*:filename:_files' # Recursive File completion
}
```

---

## 2. Advanced Context Management
Providing intelligent completion based on the current state of the command line.

### 2.1 State-Based Decision Logic
*   **Logic:** Utilizing `$words`, `$CURRENT`, and `$context` variables to determine where the user is in the command structure (e.g., "In a sub-command").
*   **Implementation Pattern:**
    ```bash
    case $((CURRENT)) in
        2) _describe -t commands 'subcommand' '(img:Image audio:Audio)' ;;
        3) _files -g "*.mp4" ;;
    esac
    ```

### 2.2 Helper Functions & Alternatives
For complex logic, usehelper functions inside `_alternative` to avoid "bad substitution" errors.

---

## 3. Performance & Visual Standards
Optimizing speed and ergonomics for modern terminals.

### 3.1 High-Performance `zstyle` Caching
*   **Logic:** Utilizing `zstyle ':completion:*' use-cache on` to store result sets in `~/.zcompcache`.
*   **Local Injection:** Force headers to appear directly above items:
    ```bash
    zstyle ":completion:${curcontext}:*" group-name ''
    zstyle ":completion:${curcontext}:*" format '-- %d --'
    ```

### 3.2 Robust File Filtering
Use space-separated globs for maximum stability:
`_files -g "*.mp4 *.mov *.mkv *.avi"`
(Avoid `(mp4|mov)` which can fail depending on shell options).

---

## 4. Troubleshooting & Verification
*   **Bad Substitution:** Often caused by malformed arrays or incorrect expansion. Declare arrays with `local -a`.
*   **Colon Confusion:** Escape colons `\:` in descriptions when using `_alternative`.
*   **Sluggishness:** Use `zstyle` caching or pre-generate static lookup tables.

---
*Updated: 2026-02-15 - Merged Architectural Encyclopedia with Practical Robust Patterns.*
