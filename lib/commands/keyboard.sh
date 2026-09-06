#!/bin/bash

_keyboard_usage() {
    echo "Usage: amir keyboard [args...]"
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
