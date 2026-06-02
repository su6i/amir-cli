#!/bin/bash
# amir apply phd — PhD application tracker

_PHD_SEARCH_DIR="${PHD_SEARCH_DIR:-$HOME/@-Amir/Apply/2026-2027/PhD-Search}"

run_phd() {
    # If no args or first arg is a flag, default to pending view
    if [[ -z "$1" || "$1" == --* ]]; then
        _phd_python status.py --pending-only "$@"
        return $?
    fi
    local cmd="$1"; shift

    case "$cmd" in
        status)
            _phd_python status.py "$@"
            ;;
        pending)
            _phd_python status.py --pending-only "$@"
            ;;
        show|list)
            _phd_show "$@"
            ;;
        draft)
            _phd_draft "$@"
            ;;
        sent)
            if [[ -z "$1" ]]; then
                _phd_python status.py --filter-status sent
            else
                _phd_tracker sent "$@"
            fi
            ;;
        reply)
            _phd_tracker reply "$@"
            ;;
        open)
            _phd_open "$@"
            ;;
        research)
            _phd_research "$@"
            ;;
        lettre)
            _phd_lettre "$@"
            ;;
        audit)
            _phd_audit "$@"
            ;;
        sources|list-sources)
            _phd_sources
            ;;
        search)
            _phd_search "$@"
            ;;
        add-source)
            _phd_add_source "$@"
            ;;
        sync)
            _phd_sync "$@"
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

_phd_audit() {
    local pos_id="${1:-}"
    if [[ -z "$pos_id" ]]; then
        echo "Usage: amir apply phd audit <position-id>" >&2
        return 1
    fi
    PYTHONPATH="$LIB_DIR/python" uv run python \
        "$LIB_DIR/python/apply_tracker/audit.py" \
        "$_PHD_SEARCH_DIR" "$pos_id" \
        --applyforge "${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}"
}

_phd_lettre() {
    # Scaffold the complete apply folder under PhD-Search/applied/<pos_id>/
    local pos_id="${1:-}"
    if [[ -z "$pos_id" ]]; then
        echo "Usage: amir apply phd lettre <position-id>" >&2
        return 1
    fi

    local applyforge_dir="${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}"
    local out_dir="$_PHD_SEARCH_DIR/applied/${pos_id}"

    # Locate position file
    local pos_file
    pos_file=$(find "$_PHD_SEARCH_DIR/found" -name "${pos_id}.md" 2>/dev/null | head -1)
    if [[ -z "$pos_file" ]]; then
        echo "❌  Position not found: $pos_id" >&2; return 1
    fi

    mkdir -p "$out_dir"

    # Generate PhD CV via ApplyForge spontaneous pipeline
    echo "  📄 Generating PhD CV from master_cv.json..."
    (cd "$applyforge_dir" && uv run main.py spontaneous phd 2>/dev/null) || true

    # Find generated CV and copy
    local generated_cv
    generated_cv=$(find "$applyforge_dir/Applied" -name "*CV_PhD*" -newer "$pos_file" 2>/dev/null | head -1)
    if [[ -n "$generated_cv" ]]; then
        cp "$generated_cv" "$out_dir/"
        echo "  ✓ CV copied: $(basename "$generated_cv")"
    else
        echo "  ⚠️  CV not found — run manually: cd $applyforge_dir && uv run main.py spontaneous phd"
    fi

    # Copy position file as JobPosting
    cp "$pos_file" "$out_dir/JobPosting_${pos_id}.md"
    echo "  ✓ JobPosting copied"

    # Copy email draft if exists
    local draft="$out_dir/email_draft.md"
    if [[ -f "$draft" ]]; then
        echo "  ✓ Email draft already present"
    fi

    echo ""
    echo "  ──────────────────────────────────────────────────────"
    echo "  📁 Folder ready: $out_dir"
    echo "  Contents:"
    ls -1 "$out_dir/"
    echo ""
    echo "  ⚠️  MISSING: Lettre de motivation PDF"
    echo "  → Ask Claude Code: 'write lettre de motivation for $pos_id'"
    echo "  ──────────────────────────────────────────────────────"
    echo ""

    # Open folder
    open "$out_dir" 2>/dev/null || true
}

_phd_research() {
    local pos_id="$1"
    if [[ -z "$pos_id" ]]; then
        echo "Usage: amir apply phd research <position-id>" >&2
        return 1
    fi

    # Show position info
    local pos_file
    pos_file=$(find "$_PHD_SEARCH_DIR/found" -name "${pos_id}.md" 2>/dev/null | head -1)
    if [[ -z "$pos_file" ]]; then
        echo "❌  Position not found: $pos_id" >&2; return 1
    fi

    local supervisor
    supervisor=$(grep -i "supervisor\|directeur\|encadrant\|contact\|responsable" "$pos_file" | head -3)

    echo ""
    echo "  ── Supervisor Research Required ──────────────────────────────────"
    echo ""
    echo "  Position : $pos_id"
    [[ -n "$supervisor" ]] && echo "  From .md : $supervisor"
    echo ""
    echo "  ACTION (Claude Code session) :"
    echo "  ┌─────────────────────────────────────────────────────────────────"
    echo "  │  1. Web search: supervisor name + institution + publications"
    echo "  │  2. Confirm: gender, title (MCF/PR/HDR), recent papers"
    echo "  │  3. Update tracking.json — add 'supervisor' object:"
    echo "  │     { name, gender (M/F), title, salutation, email,"
    echo "  │       research_areas[], key_papers[], workshops[] }"
    echo "  │  4. Then run: amir apply phd draft $pos_id"
    echo "  └─────────────────────────────────────────────────────────────────"
    echo ""
    echo "  Tip: in Claude Code → 'research supervisor for $pos_id and update tracking.json'"
    echo ""
}

_phd_sources() {
    local sources_file="${_PHD_SEARCH_DIR}/../context/phd_search_sources.md"
    echo ""
    echo "  PhD Search Sources (priority-ordered)"
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
        echo "  Add:  amir apply phd add-source <name> <url> [-p <position>]"
    else
        echo "  Not found: $sources_file"
    fi
    echo ""
}

_phd_search() {
    echo ""
    echo "  PhD Position Search — How to find new positions"
    echo "  ───────────────────────────────────────────────────────────"
    echo ""
    echo "  With Claude Code (Web Search + Gmail MCP):"
    echo "    > search new PhD positions in AI/LLM/MARL and add to tracker"
    echo "    > check my Gmail for new PhD position newsletters"
    echo "    > search ADUM/ABG/Inria for new LLM/NLP positions"
    echo ""
    echo "  Without Claude (DeepSeek + manual):"
    echo "    amir apply phd sources        ← see priority-ordered site list"
    echo "    amir apply phd draft <id>     ← generate email draft"
    echo ""
    echo "  After finding a position:"
    echo "    Create: $_PHD_SEARCH_DIR/found/<track>/<id>.md"
    echo "    Then:   amir apply phd init <track>"
    echo ""
}

_phd_add_source() {
    local name="" url="" desc="" priority_flag=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -p|--priority) priority_flag="--priority $2"; shift 2 ;;
            *) [[ -z "$name" ]] && name="$1" || { [[ -z "$url" ]] && url="$1" || desc="$1"; }; shift ;;
        esac
    done
    if [[ -z "$name" || -z "$url" ]]; then
        echo "Usage: amir apply phd add-source <name> <url> [description] [-p <position>]" >&2
        echo "  -p, --priority N   Insert at position N (default: end of list)" >&2
        return 1
    fi
    local src="$_PHD_SEARCH_DIR/../context/phd_search_sources.md"
    PYTHONPATH="$LIB_DIR/python" uv run python \
        "$LIB_DIR/python/apply_tracker/sources.py" "$src" \
        add "$name" "$url" "$desc" $priority_flag
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
    echo "    research <id>                          Research supervisor — must run before draft"
    echo "    lettre   <id>                          Scaffold apply folder + generate CV + copy files"
    echo "    audit    <id>                          Manager-agent QA — run after lettre+CV are ready"
    echo "    search                                 How to find new PhD positions"
    echo "    add-source <name> <url> [desc]         Add a search source"
    echo "               [-p N, --priority N]        Insert at position N (default: end)"
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
_phd_sync() {
    local base_dir="${APPLY_BASE_DIR:-$HOME/@-Amir/Apply/2026-2027}"
    local sync_file="$base_dir/sync_queue.txt"
    echo ""
    echo "  SYNC REQUEST — PhD tracks only"
    if [[ -f "$sync_file" ]]; then
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/sync.py" "$base_dir" \
            --sync-file "$sync_file"
    else
        echo "  CLAUDE_ACTION: GMAIL_SYNC_PHD"
        echo "  Check Gmail for [AMIR-SYNC] drafts (PhD positions only),"
        echo "  write to: $sync_file  then re-run: amir apply phd sync"
        echo ""
        echo "  Or ask Claude Code:"
        echo "    > sync new PhD positions from Gmail and ADUM/ABG/Inria"
    fi
}

phd_urgent_header() {
    if [[ -d "$_PHD_SEARCH_DIR" ]]; then
        PYTHONPATH="$LIB_DIR/python" uv run python \
            "$LIB_DIR/python/apply_tracker/status.py" \
            "$_PHD_SEARCH_DIR" --urgent-header --type phd 2>/dev/null
    fi
}
