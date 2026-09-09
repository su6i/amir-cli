#!/bin/bash

_keyboard_usage() {
    usage_block <<'TXT'
Usage: amir keyboard [lang] [options]

Description:
  Print the Apple keyboard layout diagram for a given language, with optional
  modifier layers (Shift/Option) or a reverse character lookup.

Options:
  lang           Layout language: fr | en | fa (default: fr)
  -f, --find CHAR   Show which key(s) produce CHAR
  -a, --auto        Detect the current system keyboard layout
  -s, --shift       Show the Shift layer
  -o, --opt         Show the Option (Alt) layer
  -n, --normal      Show the base (unshifted) layer
  -h, --help        Show this help

Examples:
  amir keyboard fr
  amir keyboard fr --opt
  amir keyboard --find e
TXT
}

run_keyboard() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _keyboard_usage
        return 0
    fi
    local SCRIPT_DIR
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local LIB_DIR
    LIB_DIR="$(dirname "$SCRIPT_DIR")"
    python3 "$LIB_DIR/python/keyboard_layout.py" "$@"
}
