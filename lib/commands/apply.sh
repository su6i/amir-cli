#!/bin/bash

run_apply() {
    # ── PhD/Job urgent alert (shown on every apply invocation) ────────────────
    _apply_urgent_check

    local CV_DIR="${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}"

    if [[ -z "$1" ]]; then
        _apply_sync_both
        local rc=$?
        echo ""
        echo "Usage:"
        echo "  amir apply               → sync + help"
        echo "  amir apply sync          → sync از Gmail"
        echo "  amir apply phd [flags]   → pending PhD  (--sort fit|deadline|country  --country France  --min-fit 8)"
        echo "  amir apply job [flags]   → pending Job"
        echo "  amir apply tui [phd|job] → TUI ترمینال گرافیکی (کلیدهای جهت‌دار)"
        echo "  amir apply web [port]    → Web interface روی localhost:8765"
        echo "  amir apply stats         → آمار کلی"
        echo "  amir apply preview       → پیش‌نمایش CV"
        echo "  amir apply <url>         → تولید CV/CL برای آگهی"
        return $rc
    fi

    # ── tui ───────────────────────────────────────────────────────────────────
    if [[ "$1" == "tui" ]]; then
        shift
        local kind="${1:-phd}"
        local base_dir="${APPLY_BASE_DIR:-$HOME/@-Amir/Apply/2026-2027}"
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/tui.py" "$base_dir" "$kind"
        return $?
    fi

    # ── web ───────────────────────────────────────────────────────────────────
    if [[ "$1" == "web" ]]; then
        shift
        local port="${1:-8765}"
        local base_dir="${APPLY_BASE_DIR:-$HOME/@-Amir/Apply/2026-2027}"
        # Kill any existing process on this port
        local old_pid
        old_pid=$(lsof -ti:"$port" 2>/dev/null)
        if [[ -n "$old_pid" ]]; then
            echo "  ↻ Restarting (killing old process on :$port)..."
            kill "$old_pid" 2>/dev/null
            sleep 0.5
        fi
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/web.py" "$base_dir" "$port"
        return $?
    fi

    # ── stats ─────────────────────────────────────────────────────────────────
    if [[ "$1" == "stats" ]]; then
        local base_dir="${APPLY_BASE_DIR:-$HOME/@-Amir/Apply/2026-2027}"
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/stats_cli.py" "$base_dir"
        return $?
    fi

    # ── sync (both phd + job) ─────────────────────────────────────────────────
    if [[ "$1" == "sync" ]]; then
        shift
        _apply_sync_both "$@"
        return $?
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

_apply_sync_both() {
    local base_dir="${APPLY_BASE_DIR:-$HOME/@-Amir/Apply/2026-2027}"
    local sync_file="$base_dir/sync_queue.txt"

    echo ""
    echo "  SYNC REQUEST — checking for [AMIR-SYNC] positions"
    echo "  base: $base_dir"
    echo ""

    if [[ -f "$sync_file" ]]; then
        echo "  Found sync_queue.txt — processing..."
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/sync.py" "$base_dir" \
            --sync-file "$sync_file"
    else
        # Signal to Claude Code to perform Gmail sync
        echo "  CLAUDE_ACTION: GMAIL_SYNC"
        echo "  Read Gmail drafts with subject containing [AMIR-SYNC],"
        echo "  write positions to: $sync_file"
        echo "  then re-run: amir apply sync"
        echo ""
        echo "  Or ask Claude Code directly:"
        echo "    > sync new positions from Gmail and job sites"
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
