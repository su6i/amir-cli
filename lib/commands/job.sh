#!/bin/bash
# amir apply job — Job application tracker

_JOB_SEARCH_DIR="${JOB_SEARCH_DIR:-$HOME/@-Amir/Apply/2026-2027/Job-Search}"

run_job() {
    if [[ -z "$1" || "$1" == --* ]]; then
        _job_python status.py --pending-only "$@"
        return $?
    fi
    local cmd="$1"; shift

    case "$cmd" in
        status)
            _job_python status.py "$@"
            ;;
        pending)
            _job_python status.py --pending-only "$@"
            ;;
        show|list)
            _job_show "$@"
            ;;
        draft)
            _job_draft "$@"
            ;;
        sent)
            if [[ -z "$1" ]]; then
                _job_python status.py --filter-status sent
            else
                _job_tracker sent "$@"
            fi
            ;;
        reject)
            if [[ -z "$1" ]]; then
                _job_python status.py --filter-status rejected
            else
                _job_python service_cli.py reject "$1" job
            fi
            ;;
        reply)
            _job_tracker reply "$@"
            ;;
        open)
            _job_open "$@"
            ;;
        sources|list-sources)
            _job_sources
            ;;
        search)
            _job_search "$@"
            ;;
        add-source)
            _job_add_source "$@"
            ;;
        sync)
            _job_sync_cmd
            ;;
        init)
            _job_init "$@"
            ;;
        new)
            _job_new "$@"
            ;;
        *)
            _job_usage
            ;;
    esac
}

_job_python() {
    local script="$1"; shift
    PYTHONPATH="$LIB_DIR/python" uv run python \
        "$LIB_DIR/python/apply_tracker/$script" \
        "$_JOB_SEARCH_DIR" --type job "$@"
}

_job_show() {
    local pos_id="$1"
    if [[ -z "$pos_id" ]]; then
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/status.py" \
            "$_JOB_SEARCH_DIR" --list --type job
        return 0
    fi

    local pos_file
    pos_file=$(find "$_JOB_SEARCH_DIR/found" -name "${pos_id}.md" 2>/dev/null | head -1)

    if [[ -z "$pos_file" ]]; then
        echo "❌  Position not found: $pos_id" >&2
        return 1
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  POSITION: $pos_id"
    echo "═══════════════════════════════════════════════════════════"
    cat "$pos_file"

    local draft="$_JOB_SEARCH_DIR/applied/$pos_id/email_draft.md"
    if [[ -f "$draft" ]]; then
        echo ""
        echo "═══════════════════════════════════════════════════════════"
        echo "  DRAFT EMAIL"
        echo "═══════════════════════════════════════════════════════════"
        cat "$draft"
    else
        echo ""
        echo "  (no draft yet — run: amir apply job draft $pos_id)"
    fi
    echo ""
}

_job_draft() {
    local pos_id=""
    local force_flag=""
    local lang_flag=""
    local track_flag=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force) force_flag="--force"; shift ;;
            --lang)  lang_flag="--lang $2"; shift 2 ;;
            --track) track_flag="--track $2"; shift 2 ;;
            *) pos_id="$1"; shift ;;
        esac
    done

    if [[ -z "$pos_id" ]]; then
        echo "Usage: amir apply job draft <position-id> [--force] [--lang fr|en]" >&2
        return 1
    fi

    PYTHONPATH="$LIB_DIR/python" uv run python \
        "$LIB_DIR/python/apply_tracker/draft.py" \
        "$_JOB_SEARCH_DIR" "$pos_id" \
        $force_flag $lang_flag $track_flag \
        --type job
}

_job_tracker() {
    local subcmd="$1"; shift
    PYTHONPATH="$LIB_DIR/python" uv run python \
        "$LIB_DIR/python/apply_tracker/tracker.py" \
        "$_JOB_SEARCH_DIR" "$subcmd" "$@"
}

_job_open() {
    local which="${1:-}"
    local found_dir="$_JOB_SEARCH_DIR/found"

    if [[ -n "$which" && -f "$found_dir/$which/suivi.html" ]]; then
        open "$found_dir/$which/suivi.html"
    elif [[ -f "$found_dir/suivi.html" ]]; then
        open "$found_dir/suivi.html"
    else
        echo "ℹ  No HTML tracker found yet."
        echo "   Use 'amir apply job status' for terminal view."
    fi
}

_job_sources() {
    local sources_file="${_JOB_SEARCH_DIR}/../context/job_search_sources.md"
    echo ""
    echo "  Job Search Sources (priority-ordered)"
    echo "  ───────────────────────────────────────────────────────────"
    if [[ -f "$sources_file" ]]; then
        echo ""
        while IFS='|' read -r name url desc; do
            name="${name#"${name%%[![:space:]]*}"}"
            if [[ "$name" =~ ^#[[:space:]]*── ]]; then
                local section="${name#*── }"; section="${section%% ─*}"
                echo "  ── ${section}"; continue
            fi
            [[ "$name" =~ ^# ]] && continue
            [[ -z "$name" ]] && continue
            url="${url#"${url%%[![:space:]]*}"}"
            printf "    %-14s  %s\n" "$name" "$url"
        done < "$sources_file"
        echo ""
        echo "  Edit: $sources_file"
        echo "  Add:  amir apply job add-source <name> <url> [-p <position>]"
    else
        echo "  Not found: $sources_file"
    fi
    echo ""
}

_job_search() {
    echo ""
    echo "  Job Position Search — How to find new positions"
    echo "  ───────────────────────────────────────────────────────────"
    echo ""
    echo "  With Claude Code (Web Search + Gmail MCP):"
    echo "    > check my Gmail for new job newsletters (APEC, LinkedIn, etc.)"
    echo "    > search LinkedIn/APEC for AI Engineer positions in Grenoble/Montpellier"
    echo "    > sync my job application emails"
    echo ""
    echo "  Without Claude (DeepSeek + manual):"
    echo "    amir apply job sources        ← see priority-ordered site list"
    echo "    amir apply job new <id>       ← add position manually"
    echo "    amir apply job draft <id>     ← generate email draft"
    echo ""
}

_job_add_source() {
    local name="" url="" desc="" priority_flag=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -p|--priority) priority_flag="--priority $2"; shift 2 ;;
            *) [[ -z "$name" ]] && name="$1" || { [[ -z "$url" ]] && url="$1" || desc="$1"; }; shift ;;
        esac
    done
    if [[ -z "$name" || -z "$url" ]]; then
        echo "Usage: amir apply job add-source <name> <url> [description] [-p <position>]" >&2
        echo "  -p, --priority N   Insert at position N (default: end of list)" >&2
        return 1
    fi
    local src="$_JOB_SEARCH_DIR/../context/job_search_sources.md"
    PYTHONPATH="$LIB_DIR/python" uv run python \
        "$LIB_DIR/python/apply_tracker/sources.py" "$src" \
        add "$name" "$url" "$desc" $priority_flag
}

_job_sync_cmd() {
    local base_dir="${APPLY_BASE_DIR:-$HOME/@-Amir/Apply/2026-2027}"
    local sync_file="$base_dir/sync_queue.txt"
    local use_gmail=0
    for arg in "$@"; do [[ "$arg" == "--gmail" ]] && use_gmail=1; done
    echo ""
    echo "  SYNC REQUEST — Job tracks only"
    if (( use_gmail )); then
        _gmail_sync_direct "$base_dir"
    elif [[ -f "$sync_file" ]]; then
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/sync.py" "$base_dir" \
            --sync-file "$sync_file"
    else
        echo "  CLAUDE_ACTION: GMAIL_SYNC_JOB"
        echo "  Tip: run 'amir apply job sync --gmail' to sync directly from Gmail OAuth"
        echo "  write to: $sync_file  then re-run: amir apply job sync"
    fi
}

_job_new() {
    local pos_id="$1"
    local track="polyvalent"
    shift || true

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --track) track="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    if [[ -z "$pos_id" ]]; then
        echo "Usage: amir apply job new <id> [--track devops|ai_engineer|polyvalent]" >&2
        return 1
    fi

    local track_dir="$_JOB_SEARCH_DIR/found/$track"
    mkdir -p "$track_dir"

    local md_file="$track_dir/${pos_id}.md"
    if [[ -f "$md_file" ]]; then
        echo "ℹ  Position already exists: $md_file"
        return 0
    fi

    cat > "$md_file" << EOF
# Position — ${pos_id}

| Champ | Valeur |
|-------|--------|
| **Entreprise** |  |
| **Titre** |  |
| **Lieu** |  |
| **Contrat** | CDI / CDD / Stage / Alternance |
| **Deadline** |  |
| **Lien** |  |
| **Fit score** |  |

## Description

## Notes

EOF

    echo "✓  Created: $md_file"
    echo "   Fill in the details, then run: amir apply job draft $pos_id"
}

_job_init() {
    local track="${1:-}"
    if [[ -z "$track" ]]; then
        echo "Initializing all job tracks..."
        for d in "$_JOB_SEARCH_DIR/found"/*/; do
            local t
            t=$(basename "$d")
            _job_tracker init "$t" 2>/dev/null && echo "  ✓ $t"
        done
    else
        _job_tracker init "$track"
    fi
}

_job_usage() {
    echo ""
    echo "  amir apply job — Job Application Tracker"
    echo ""
    echo "  Commands:"
    echo "    status [--track devops|ai_engineer|polyvalent|all]  Show all positions"
    echo "    show   [<id>]                   Show position + draft (no ID = list)"
    echo "    list                            List all position IDs and titles"
    echo "    search                          How to find new job positions"
    echo "    add-source <name> <url> [desc]  Add a search source"
    echo "               [-p N]              Insert at position N (default: end)"
    echo "    new    <id> [--track <track>]   Create new position file"
    echo "    draft  <id> [--force]           Generate email draft (DeepSeek)"
    echo "    sent   <id> [--date DATE]       Mark as sent"
    echo "    reply  <id> --type positive|negative|bounce|info"
    echo "    open   [track]                  Open HTML tracker"
    echo "    sync                            Sync Gmail job newsletters"
    echo "    init   [track]                  Initialize tracking.json"
    echo ""
}

# Expose urgent header for apply.sh
job_urgent_header() {
    if [[ -d "$_JOB_SEARCH_DIR/found" ]]; then
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/status.py" \
            "$_JOB_SEARCH_DIR" --urgent-header --type job 2>/dev/null
    fi
}
