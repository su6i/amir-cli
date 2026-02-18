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
    '--engine[Set rendering engine]:engine:(puppeteer weasyprint pil pandoc)' \
    '--weasyprint[Use WeasyPrint engine]' \
    '--pil[Use PIL hardcopy fallback]' \
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

*   **Colon Confusion (CRITICAL):** Colons (`:`) in help strings within `_arguments` specifications MUST be escaped with a backslash (`\:`). Zsh completion specs use colons as separators; unescaped colons will cause the shell to interpret the help text as a new command part, leading to `zsh: command not found` errors. 
    *   **Bad Example:** `[HH:MM:SS]` (Crashes)
    *   **Good Example:** `[HH\:MM\:SS]` (Works)
*   **Explicit Positional Indices:** When using `_arguments` for complex commands with subcommands, use explicit numeric indices (e.g., `'1: : '`, `'2: : '`) to align the argument mapping. This ensures Zsh knows which words have already been provided as commands and which are flags/files.

---
---
*Updated: 2026-02-18 - Added "No Invention of the Wheel" protocols, Colon Escaping fixes, and Explicit Positional Alignment standards.*
