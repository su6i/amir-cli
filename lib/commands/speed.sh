#!/bin/bash

_speed_usage() { echo "Usage: amir speed"; }
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
