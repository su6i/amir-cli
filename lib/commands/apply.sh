#!/bin/bash

run_apply() {
    # Base directory for the CV generator project
    local CV_DIR="$HOME/@-github/CV"
    
    if [[ ! -d "$CV_DIR" ]]; then
        echo "❌ Error: CV project directory not found at $CV_DIR" >&2
        return 1
    fi

    if [[ -z "$1" ]]; then
        echo "Usage: amir apply <job-url> [--template altacv|lato]"
        return 1
    fi

    # The CV project requires commands to be run from its root
    # We sub-shell into it and execute uv run
    echo "🚀 Forwarding command to CV Generator at $CV_DIR..."
    (cd "$CV_DIR" && uv run main.py apply "$@")
}
