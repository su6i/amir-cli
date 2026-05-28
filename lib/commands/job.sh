#!/bin/bash
# amir apply job — Job application tracker

_JOB_SEARCH_DIR="${JOB_SEARCH_DIR:-$HOME/@-Amir/Apply/2026-2027/Job-Search}"

run_job() {
    local cmd="${1:-status}"
    shift || true

    case "$cmd" in
        status)
            _job_python status.py "$@"
            ;;
        show|list)
            _job_show "$@"
            ;;
        draft)
            _job_draft "$@"
            ;;
        sent)
            _job_tracker sent "$@"
            ;;
        reply)
            _job_tracker reply "$@"
            ;;
        open)
            _job_open "$@"
            ;;
        search)
            _job_search "$@"
            ;;
        sync)
            _job_sync
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

_job_search() {
    echo ""
    echo "  Job Position Search"
    echo "  ───────────────────────────────────────────────────────────"
    echo ""
    echo "  ℹ  Automatic search requires Claude Code session (Web Search + Gmail MCP)."
    echo "     Run one of these in the Claude Code terminal:"
    echo ""
    echo "     > check my Gmail for new job position newsletters (APEC, LinkedIn, etc.)"
    echo "     > search for DevOps/AI Engineer jobs in France and add to tracker"
    echo "     > search LinkedIn/APEC for new AI Engineer positions in Grenoble/Montpellier"
    echo ""
    echo "  Manual sources to check:"
    echo "    APEC     → https://www.apec.fr"
    echo "    LinkedIn → https://www.linkedin.com/jobs"
    echo "    Indeed   → https://fr.indeed.com"
    echo "    Welcome  → https://www.welcometothejungle.com"
    echo "    Talent   → https://www.talent.io"
    echo ""
    echo "  Sync Gmail newsletters automatically:"
    echo "    → amir apply job sync"
    echo ""
    echo "  Add a position manually:"
    echo "    → amir apply job new <id> --track <devops|ai_engineer|polyvalent>"
    echo ""
}

_job_sync() {
    echo ""
    echo "  ℹ  Job sync requires Gmail MCP access."
    echo "     Run from Claude Code session:"
    echo "       > sync my job application emails from Gmail newsletters"
    echo ""
    echo "  Or add positions manually:"
    echo "       amir apply job new <id> --track <devops|ai_engineer|polyvalent>"
    echo ""
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
