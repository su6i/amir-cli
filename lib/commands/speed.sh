#!/bin/bash

_speed_usage() {
    usage_block <<'TXT'
Usage: amir speed

Description:
  Run a network quality test (macOS built-in `networkQuality`).

Options:
  (none)

Examples:
  amir speed
TXT
}
run_speed() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _speed_usage
        return 0
    fi
    speed() {
        echo "⏳ Testing Network Quality..."
        networkQuality 2>/dev/null || echo "Command not available on this system."
    }
    speed
}
