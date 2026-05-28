#!/bin/bash

run_keyboard() {
    local SCRIPT_DIR
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local LIB_DIR
    LIB_DIR="$(dirname "$SCRIPT_DIR")"
    python3 "$LIB_DIR/python/keyboard_layout.py" "$@"
}
