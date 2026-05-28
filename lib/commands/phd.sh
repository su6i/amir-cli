#!/bin/bash
# amir apply phd — PhD application tracker

_PHD_SEARCH_DIR="${PHD_SEARCH_DIR:-$HOME/@-Amir/Apply/2026-2027/PhD-Search}"

run_phd() {
    local cmd="${1:-status}"
    shift || true

    case "$cmd" in
        status)
            _phd_python status.py "$@"
            ;;
        show|list)
            _phd_show "$@"
            ;;
        draft)
            _phd_draft "$@"
            ;;
        sent)
            _phd_tracker sent "$@"
            ;;
        reply)
            _phd_tracker reply "$@"
            ;;
        open)
            _phd_open "$@"
            ;;
        search)
            _phd_search "$@"
            ;;
        init)
            _phd_init "$@"
            ;;
        *)
            _phd_usage
            ;;
    esac
}

_phd_python() {
    local script="$1"; shift
    local script_path="$LIB_DIR/python/apply_tracker/$script"
    if [[ ! -f "$script_path" ]]; then
        echo "❌  Script not found: $script_path" >&2
        return 1
    fi
    PYTHONPATH="$LIB_DIR/python" uv run python "$script_path" "$_PHD_SEARCH_DIR" "$@"
}

_phd_show() {
    local pos_id="$1"
    if [[ -z "$pos_id" ]]; then
        # Show list of available IDs instead of error
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/status.py" \
            "$_PHD_SEARCH_DIR" --list --type phd
        return 0
    fi

    # Find position file
    local pos_file
    pos_file=$(find "$_PHD_SEARCH_DIR/found" -name "${pos_id}.md" 2>/dev/null | head -1)

    if [[ -z "$pos_file" ]]; then
        echo "❌  Position not found: $pos_id" >&2
        return 1
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  POSITION: $pos_id"
    echo "═══════════════════════════════════════════════════════════"
    cat "$pos_file"

    local draft="$_PHD_SEARCH_DIR/applied/$pos_id/email_draft.md"
    if [[ -f "$draft" ]]; then
        echo ""
        echo "═══════════════════════════════════════════════════════════"
        echo "  DRAFT EMAIL"
        echo "═══════════════════════════════════════════════════════════"
        cat "$draft"
    else
        echo ""
        echo "  (no draft yet — run: amir apply phd draft $pos_id)"
    fi
    echo ""
}

_phd_draft() {
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
        echo "Usage: amir apply phd draft <position-id> [--force] [--lang fr|en]" >&2
        return 1
    fi

    PYTHONPATH="$LIB_DIR/python" uv run python \
        "$LIB_DIR/python/apply_tracker/draft.py" \
        "$_PHD_SEARCH_DIR" "$pos_id" \
        $force_flag $lang_flag $track_flag \
        --type phd
}

_phd_tracker() {
    local subcmd="$1"; shift
    PYTHONPATH="$LIB_DIR/python" uv run python \
        "$LIB_DIR/python/apply_tracker/tracker.py" \
        "$_PHD_SEARCH_DIR" "$subcmd" "$@"
}

_phd_open() {
    local which="${1:-general}"
    local html_file

    case "$which" in
        finance) html_file="$_PHD_SEARCH_DIR/found/ai_finance/suivi_candidatures_PhD.html" ;;
        general) html_file="$_PHD_SEARCH_DIR/found/ai_general/suivi_candidatures_PhD.html" ;;
        all)
            open "$_PHD_SEARCH_DIR/found/ai_general/suivi_candidatures_PhD.html" 2>/dev/null
            open "$_PHD_SEARCH_DIR/found/ai_finance/suivi_candidatures_PhD.html" 2>/dev/null
            return
            ;;
        *)
            echo "Usage: amir apply phd open [general|finance|all]" >&2
            return 1
            ;;
    esac

    if [[ -f "$html_file" ]]; then
        open "$html_file"
    else
        echo "❌  File not found: $html_file" >&2
    fi
}

_phd_search() {
    local source="${1:-all}"
    echo ""
    echo "  PhD Position Search"
    echo "  ───────────────────────────────────────────────────────────"
    echo ""
    echo "  ℹ  Automatic search requires Claude Code session (Web Search + Gmail MCP)."
    echo "     Run one of these in the Claude Code terminal:"
    echo ""
    echo "     > search new PhD positions in AI/LLM/MARL and add to tracker"
    echo "     > check my Gmail for new PhD position newsletters"
    echo "     > search ADUM/ABG/Inria for new LLM/multi-agent PhD positions"
    echo ""
    echo "  Manual sources to check:"
    echo "    ADUM     → https://www.adum.fr"
    echo "    ABG      → https://www.abg.asso.fr/fr/recrutement/sujet-de-these/informatique"
    echo "    Inria    → https://jobs.inria.fr/public/classic/en/offres?filtre=doctorants"
    echo "    Mila     → https://mila.quebec/en/prospective-students-postdocs"
    echo "    Euraxess → https://euraxess.ec.europa.eu/jobs/search"
    echo ""
    echo "  To add a found position:"
    echo "    Create: $_PHD_SEARCH_DIR/found/<track>/<id>.md"
    echo "    Then:   amir apply phd init <track>"
    echo ""
}

_phd_init() {
    local track="${1:-}"
    if [[ -z "$track" ]]; then
        echo "Initializing all tracks..."
        _phd_tracker init ai_general
        _phd_tracker init ai_finance
    else
        _phd_tracker init "$track"
    fi
}

_phd_usage() {
    echo ""
    echo "  amir apply phd — PhD Application Tracker"
    echo ""
    echo "  Commands:"
    echo "    status [--track general|finance|all]   Show all positions with urgency"
    echo "    show   [<id>]                          Show position + draft (no ID = list)"
    echo "    list                                   List all position IDs and titles"
    echo "    search                                 How to find new PhD positions"
    echo "    draft  <id> [--force] [--lang fr|en]   Generate email draft (DeepSeek)"
    echo "    sent   <id> [--date YYYY-MM-DD]        Mark as sent"
    echo "    reply  <id> --type positive|negative|bounce|info"
    echo "    open   [general|finance|all]           Open HTML tracker in browser"
    echo "    init   [track]                         Initialize tracking.json from files"
    echo ""
    echo "  Examples:"
    echo "    amir apply phd status"
    echo "    amir apply phd show FR_artois_llm_multiagent"
    echo "    amir apply phd draft FR_artois_llm_multiagent"
    echo "    amir apply phd sent FR_artois_llm_multiagent"
    echo ""
}

# Expose urgent header for apply.sh
phd_urgent_header() {
    if [[ -d "$_PHD_SEARCH_DIR" ]]; then
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/status.py" \
            "$_PHD_SEARCH_DIR" --urgent-header --type phd 2>/dev/null
    fi
}
