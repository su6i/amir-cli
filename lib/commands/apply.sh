#!/bin/bash

# ── apply_tracker wrap (wo-applyforge-0007) ──────────────────────────────────
# apply_tracker now lives in ApplyForge (src/apply_tracker/) — same wrap
# pattern as the CV generator below: (cd "$APPLYFORGE_DIR" && uv run ...).
_tracker_py() {
    local script="$1"; shift
    local applyforge_dir="${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}"
    _require_external_repo "amir apply" "ApplyForge" "$applyforge_dir" "APPLYFORGE_DIR" "ApplyForge" || return 1
    (cd "$applyforge_dir" && uv run python -m "src.apply_tracker.${script%.py}" "$@")
}

_apply_usage() {
    usage_block <<'TXT'
Usage: amir apply [subcommand] [args]

Description:
  Job/PhD application tracker and CV/cover-letter generator, backed by the
  ApplyForge repo. With no arguments, syncs [AMIR-SYNC] positions from
  Gmail, then prints this help. --help never touches the network.

Options:
  (no args)          Sync from Gmail, then show this help
  sync                Sync [AMIR-SYNC] positions from Gmail
  phd [flags]         Pending PhD positions — see "amir apply phd --help"
  job [flags]         Pending Job positions — see "amir apply job --help"
  tui [phd|job]       Terminal UI (arrow-key navigation)
  web [port]          Web interface on localhost:<port> (default 8765)
  stats               Overall application stats
  alert               Send the deadline-alert email (same one launchd sends daily)
  preview [args]      Preview the generated CV
  <url> [--color C] [--role R] [--lang L]   Generate a CV/cover letter for a job posting URL

Examples:
  amir apply sync
  amir apply phd --sort fit --min-fit 8
  amir apply tui job
  amir apply web 8765
  amir apply https://example.com/job/123
TXT
}

run_apply() {
    # ── help must answer before anything else ─────────────────────────────────
    # `--help` is the first thing anyone types against an unknown command, so it
    # must never touch the network, Gmail, or the CV generator. Without this
    # branch an unrecognised first arg fell through to the ApplyForge forward at
    # the bottom, which scraped "--help" as if it were a job-posting URL.
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _apply_usage
        return 0
    fi

    # ── PhD/Job urgent alert (shown on every apply invocation) ────────────────
    _apply_urgent_check

    local CV_DIR="${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}"

    if [[ -z "$1" ]]; then
        _apply_sync_both
        local rc=$?
        echo ""
        _apply_usage
        return $rc
    fi

    # ── alert ─────────────────────────────────────────────────────────────────
    if [[ "$1" == "alert" ]]; then
        local base_dir="${APPLY_BASE_DIR:-$HOME/@-Amir/Apply/2026-2027}"
        _tracker_py daily_alert.py "$base_dir"
        return $?
    fi

    # ── tui ───────────────────────────────────────────────────────────────────
    if [[ "$1" == "tui" ]]; then
        shift
        local kind="${1:-phd}"
        local base_dir="${APPLY_BASE_DIR:-$HOME/@-Amir/Apply/2026-2027}"
        _tracker_py tui.py "$base_dir" "$kind"
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
            kill -9 $old_pid 2>/dev/null
            # Wait until port is actually free (max 3s)
            local waited=0
            while lsof -ti:"$port" &>/dev/null && (( waited < 6 )); do
                sleep 0.5; (( waited++ ))
            done
        fi
        export APPLY_BASE_DIR="$base_dir"
        # Open browser after short delay (server needs ~1s to bind)
        { sleep 1.2 && open "http://localhost:$port"; } &
        _tracker_py web.py "$base_dir" "$port"
        return $?
    fi

    # ── stats ─────────────────────────────────────────────────────────────────
    if [[ "$1" == "stats" ]]; then
        local base_dir="${APPLY_BASE_DIR:-$HOME/@-Amir/Apply/2026-2027}"
        _tracker_py stats_cli.py "$base_dir"
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

    # ── unknown flag guard ────────────────────────────────────────────────────
    # Everything below forwards $1 to the CV generator as a job-posting URL. A
    # leading dash is a flag the user mistyped, never a URL — fail loudly here
    # instead of letting the scraper try to fetch it.
    case "$1" in
        --color|--role|--lang) ;;   # genuine generator flags, pass through
        -*)
            echo "❌ Unknown option: $1" >&2
            echo "" >&2
            _apply_usage >&2
            return 2
            ;;
    esac

    # ── ApplyForge CV generator ───────────────────────────────────────────────
    _require_external_repo "amir apply" "ApplyForge" "$CV_DIR" "APPLYFORGE_DIR" "ApplyForge" || return 1

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

    echo ""
    echo "  SYNC REQUEST — checking for [AMIR-SYNC] positions"
    echo "  base: $base_dir"
    echo ""

    _gmail_sync_direct "$base_dir"
}

_gmail_sync_direct() {
    local base_dir="$1"
    local applyforge_dir="${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}"
    _require_external_repo "amir apply sync" "ApplyForge" "$applyforge_dir" "APPLYFORGE_DIR" "ApplyForge" || return 1
    (cd "$applyforge_dir" && uv run python - <<PYEOF
import sys
from pathlib import Path
from src.apply_tracker.gmail_sync import fetch_and_process, has_valid_token
if not has_valid_token():
    print("  ❌ No Gmail token — run 'amir apply web' and click 'Connect Gmail' first")
    sys.exit(1)
r = fetch_and_process(Path('$base_dir'))
print(f"  {'✅' if r.get('ok') else '❌'} {r.get('message', 'Unknown error')}")
sys.exit(0 if r.get('ok') else 1)
PYEOF
)
}

_apply_urgent_check() {
    # Show urgent PhD/Job alerts if any deadlines ≤7 days
    local phd_dir="${PHD_SEARCH_DIR:-$HOME/@-Amir/Apply/2026-2027/PhD-Search}"
    local job_dir="${JOB_SEARCH_DIR:-$HOME/@-Amir/Apply/2026-2027/Job-Search}"

    if [[ -d "$phd_dir/found" ]]; then
        _tracker_py status.py "$phd_dir" --urgent-header --type phd 2>/dev/null
    fi
    if [[ -d "$job_dir/found" ]]; then
        _tracker_py status.py "$job_dir" --urgent-header --type job 2>/dev/null
    fi
}
