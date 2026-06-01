#!/bin/bash
# research.sh — Professor/supervisor research: discover by keywords, analyze papers, generate emails.
# Bridges amir-cli to the research_toolkit professor_scout pipeline.
#
# Usage:
#   amir research discover --keywords "MARL portfolio" [options]
#   amir research professor --professor "Name" --institution "Lab" [options]

_research_toolkit_dir() {
    echo "${RESEARCH_TOOLKIT_DIR:-$HOME/@-github/research_toolkit}"
}

_research_python() {
    echo "$(_research_toolkit_dir)/.venv/bin/python"
}

_research_check_env() {
    local toolkit_dir python_bin
    toolkit_dir="$(_research_toolkit_dir)"
    python_bin="$(_research_python)"

    if [[ ! -d "$toolkit_dir" ]]; then
        echo "❌ research_toolkit not found at: $toolkit_dir"
        echo "   Set RESEARCH_TOOLKIT_DIR or clone: github.com/your/research_toolkit"
        return 1
    fi
    if [[ ! -x "$python_bin" ]]; then
        echo "❌ research_toolkit venv not found. Run: cd $toolkit_dir && bash install.sh"
        return 1
    fi
    return 0
}

_research_help() {
    echo ""
    echo "Usage: amir research <subcommand> [options]"
    echo ""
    echo "Subcommands:"
    printf "  %-12s %s\n" "discover"   "Find potential supervisors by topic keywords (ArXiv + DBLP)"
    printf "  %-12s %s\n" "professor"  "Deep-research a specific professor: papers → overlap → email"
    echo ""
    echo "discover options:"
    printf "  %-30s %s\n" "--keywords KW [KW ...]"        "Topic keywords (required)"
    printf "  %-30s %s\n" "--sources arxiv dblp"          "Sources (default: both)"
    printf "  %-30s %s\n" "--since-year YEAR"             "Papers since year (default: 2022)"
    printf "  %-30s %s\n" "--min-papers N"                "Min topic-relevant papers per author (default: 2)"
    printf "  %-30s %s\n" "--top N"                       "Candidates to show (default: 10)"
    printf "  %-30s %s\n" "--format txt|md|xlsx"          "Output format (default: txt)"
    printf "  %-30s %s\n" "--categories cs.LG q-fin.CP"   "ArXiv category filter"
    printf "  %-30s %s\n" "--profile PATH"                "Candidate profile .md for LLM scoring"
    printf "  %-30s %s\n" "--save PATH"                   "Override output path"
    echo ""
    echo "professor options:"
    printf "  %-30s %s\n" "--professor NAME"              "Professor full name (required)"
    printf "  %-30s %s\n" "--institution LAB"             "Institution / lab name"
    printf "  %-30s %s\n" "--email EMAIL"                 "Professor email"
    printf "  %-30s %s\n" "--gender M|F"                  "For salutation (default: M)"
    printf "  %-30s %s\n" "--lang fr|en"                  "Email language (default: fr)"
    printf "  %-30s %s\n" "--story TEXT"                  "Your genuine motivation (overrides profile tone)"
    printf "  %-30s %s\n" "--since-year YEAR"             "Fetch papers since year (default: 2021)"
    printf "  %-30s %s\n" "--scholar-url URL"             "Google Scholar / personal page (for non-CS profs)"
    printf "  %-30s %s\n" "--profile PATH"                "Candidate profile .md"
    printf "  %-30s %s\n" "--tracking PATH"               "Path to tracking.json to update"
    printf "  %-30s %s\n" "--position-id ID"              "Position ID in tracking.json"
    echo ""
    echo "Examples:"
    echo "  amir research discover --keywords \"MARL portfolio optimization\""
    echo "  amir research discover --keywords \"NLP sentiment finance\" --format md --top 15"
    echo "  amir research professor --professor \"Vianney Perchet\" --institution \"CREST\" --lang fr"
    echo ""
}

_run_discover() {
    _research_check_env || return 1

    local toolkit_dir python_bin
    toolkit_dir="$(_research_toolkit_dir)"
    python_bin="$(_research_python)"

    local keywords=() sources=() categories=()
    local since_year="" min_papers="" top_n="" fmt="" save="" profile=""
    local show_help=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --keywords)
                shift
                while [[ $# -gt 0 && "$1" != --* ]]; do keywords+=("$1"); shift; done ;;
            --sources)
                shift
                while [[ $# -gt 0 && "$1" != --* ]]; do sources+=("$1"); shift; done ;;
            --categories)
                shift
                while [[ $# -gt 0 && "$1" != --* ]]; do categories+=("$1"); shift; done ;;
            --since-year)  since_year="$2"; shift 2 ;;
            --min-papers)  min_papers="$2"; shift 2 ;;
            --top)         top_n="$2";      shift 2 ;;
            --format)      fmt="$2";        shift 2 ;;
            --save)        save="$2";       shift 2 ;;
            --profile)     profile="$2";    shift 2 ;;
            --help|-h)     show_help=true;  shift ;;
            *) shift ;;
        esac
    done

    if [[ "$show_help" == true || ${#keywords[@]} -eq 0 ]]; then
        _research_help; return 0
    fi

    local cmd=("$python_bin" main.py discover --keywords "${keywords[@]}")
    [[ ${#sources[@]}    -gt 0 ]] && cmd+=(--sources    "${sources[@]}")
    [[ ${#categories[@]} -gt 0 ]] && cmd+=(--categories "${categories[@]}")
    [[ -n "$since_year" ]]        && cmd+=(--since-year "$since_year")
    [[ -n "$min_papers" ]]        && cmd+=(--min-papers "$min_papers")
    [[ -n "$top_n" ]]             && cmd+=(--top        "$top_n")
    [[ -n "$fmt" ]]               && cmd+=(--format     "$fmt")
    [[ -n "$profile" ]]           && cmd+=(--profile    "$profile")

    # Anchor output to caller's CWD, not toolkit dir
    if [[ -z "$save" ]]; then
        local slug today ext
        slug="${keywords[0]// /_}"; slug="${slug:0:20}"
        today="$(date +%Y%m%d)"
        ext="${fmt:-txt}"
        save="$(pwd)/discover_${slug}_${today}.${ext}"
    fi
    cmd+=(--save "$save")

    (cd "$toolkit_dir" && "${cmd[@]}")
}

_run_professor() {
    _research_check_env || return 1

    local toolkit_dir python_bin
    toolkit_dir="$(_research_toolkit_dir)"
    python_bin="$(_research_python)"

    local professor="" institution="" email="" gender="" lang="" story=""
    local since_year="" scholar_url="" profile="" tracking="" position_id=""
    local show_help=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --professor)    professor="$2";    shift 2 ;;
            --institution)  institution="$2";  shift 2 ;;
            --email)        email="$2";        shift 2 ;;
            --gender)       gender="$2";       shift 2 ;;
            --lang)         lang="$2";         shift 2 ;;
            --story)        story="$2";        shift 2 ;;
            --since-year)   since_year="$2";   shift 2 ;;
            --scholar-url)  scholar_url="$2";  shift 2 ;;
            --profile)      profile="$2";      shift 2 ;;
            --tracking)     tracking="$2";     shift 2 ;;
            --position-id)  position_id="$2";  shift 2 ;;
            --help|-h)      show_help=true;    shift ;;
            *) shift ;;
        esac
    done

    if [[ "$show_help" == true || -z "$professor" ]]; then
        _research_help; return 0
    fi

    local cmd=("$python_bin" main.py research --professor "$professor")
    [[ -n "$institution" ]]  && cmd+=(--institution  "$institution")
    [[ -n "$email" ]]        && cmd+=(--email        "$email")
    [[ -n "$gender" ]]       && cmd+=(--gender       "$gender")
    [[ -n "$lang" ]]         && cmd+=(--lang         "$lang")
    [[ -n "$story" ]]        && cmd+=(--story        "$story")
    [[ -n "$since_year" ]]   && cmd+=(--since-year   "$since_year")
    [[ -n "$scholar_url" ]]  && cmd+=(--scholar-url  "$scholar_url")
    [[ -n "$profile" ]]      && cmd+=(--profile      "$profile")
    [[ -n "$tracking" ]]     && cmd+=(--tracking     "$tracking")
    [[ -n "$position_id" ]]  && cmd+=(--position-id  "$position_id")

    (cd "$toolkit_dir" && "${cmd[@]}")
}

run_research() {
    local subcmd="${1:-}"
    [[ -n "$subcmd" ]] && shift

    case "$subcmd" in
        discover)   _run_discover   "$@" ;;
        professor)  _run_professor  "$@" ;;
        ""|--help|-h) _research_help ;;
        *)
            echo "❌ Unknown subcommand: $subcmd"
            _research_help
            return 1 ;;
    esac
}
