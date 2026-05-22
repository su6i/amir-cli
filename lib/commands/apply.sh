#!/bin/bash

run_apply() {
    # Base directory for the CV generator project
    local CV_DIR="${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}"
    
    if [[ ! -d "$CV_DIR" ]]; then
        echo "❌ Error: CV project directory not found at $CV_DIR" >&2
        return 1
    fi

    if [[ -z "$1" ]]; then
        echo "Usage:"
        echo "  amir apply <job-url> [--template <name>] [--lang auto|fr|en] [--color <name>]"
        echo "  amir apply preview   [--template <name>] [--role <ai|it|phd>] [--lang fr|en] [--color <name>] [--no-localize-preview]"
        return 1
    fi

    # Check if subcommand is preview
    if [[ "$1" == "preview" ]]; then
        shift
        echo "🚀 Generating CV Preview at $CV_DIR..."
        (cd "$CV_DIR" && uv run main.py preview "$@")
    else
        echo "🚀 Forwarding command to CV Generator at $CV_DIR..."
        # Inject --color blue as default if no --color flag is already present
        local args=("$@")
        if [[ ! " $* " =~ " --color " ]]; then
            args+=("--color" "blue")
        fi
        (cd "$CV_DIR" && uv run main.py apply "${args[@]}")
    fi
}
