#!/bin/bash

run_preview() {
    # Base directory for the CV generator project
    local CV_DIR="$HOME/@-github/CV"
    
    if [[ ! -d "$CV_DIR" ]]; then
        echo "❌ Error: CV project directory not found at $CV_DIR" >&2
        return 1
    fi

    # Forward the preview command to the CV project
    echo "🚀 Generating CV Preview at $CV_DIR..."
    (cd "$CV_DIR" && uv run main.py preview "$@")
}
