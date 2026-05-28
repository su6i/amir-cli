#!/bin/bash

run_apply() {
    # ── PhD/Job urgent alert (shown on every apply invocation) ────────────────
    _apply_urgent_check

    local CV_DIR="${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}"

    if [[ -z "$1" ]]; then
        echo "Usage:"
        echo "  amir apply <job-url> [--template <name>] [--lang auto|fr|en] [--color <name>]"
        echo "  amir apply preview   [--template <name>] [--role <ai|it|phd>] [--lang fr|en]"
        echo "  amir apply phd       <status|show|draft|sent|reply|open|init>"
        echo "  amir apply job       <status|show|new|draft|sent|reply|open|sync|init>"
        return 1
    fi

    # ── phd subcommand ────────────────────────────────────────────────────────
    if [[ "$1" == "phd" ]]; then
        shift
        if [[ -f "$LIB_DIR/commands/phd.sh" ]]; then
            source "$LIB_DIR/commands/phd.sh"
            run_phd "$@"
            return $?
        fi
        echo "❌ phd.sh not found" >&2
        return 1
    fi

    # ── job subcommand ────────────────────────────────────────────────────────
    if [[ "$1" == "job" ]]; then
        shift
        if [[ -f "$LIB_DIR/commands/job.sh" ]]; then
            source "$LIB_DIR/commands/job.sh"
            run_job "$@"
            return $?
        fi
        echo "❌ job.sh not found" >&2
        return 1
    fi

    # ── ApplyForge CV generator ───────────────────────────────────────────────
    if [[ ! -d "$CV_DIR" ]]; then
        echo "❌ Error: CV project directory not found at $CV_DIR" >&2
        return 1
    fi

    if [[ "$1" == "preview" ]]; then
        shift
        echo "🚀 Generating CV Preview at $CV_DIR..."
        (cd "$CV_DIR" && uv run main.py preview "$@")
    else
        echo "🚀 Forwarding command to CV Generator at $CV_DIR..."
        local args=("$@")
        if [[ ! " $* " =~ " --color " ]]; then
            args+=("--color" "blue")
        fi
        (cd "$CV_DIR" && uv run main.py apply "${args[@]}")
    fi
}

_apply_urgent_check() {
    # Show urgent PhD/Job alerts if any deadlines ≤7 days
    local phd_dir="${PHD_SEARCH_DIR:-$HOME/@-Amir/Apply/2026-2027/PhD-Search}"
    local job_dir="${JOB_SEARCH_DIR:-$HOME/@-Amir/Apply/2026-2027/Job-Search}"

    if [[ -d "$phd_dir/found" ]]; then
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/status.py" \
            "$phd_dir" --urgent-header --type phd 2>/dev/null
    fi
    if [[ -d "$job_dir/found" ]]; then
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/status.py" \
            "$job_dir" --urgent-header --type job 2>/dev/null
    fi
}
