#!/bin/bash
# trend.sh — Research Toolkit integration: trending content & idea search
# Bridges amir-cli to the research_toolkit Multi-Agent RAG pipeline.
#
# Usage:
#   amir trend [keyword] [--source SOURCE] [--lang CODE] [--region CODE]
#              [--metric METRIC] [--limit N] [--semantic] [--ideas]
#
# Defaults: source=youtube, metric=views, limit=10
#           No keyword → global trending (most viewed)

_trend_toolkit_dir() {
    echo "${RESEARCH_TOOLKIT_DIR:-$HOME/@-github/research_toolkit}"
}

_trend_help() {
    echo ""
    echo "Usage: amir trend [keyword] [options]"
    echo ""
    echo "  No keyword → show most-viewed videos globally (trending)"
    echo ""
    echo "Options:"
    printf "  %-22s %s\n" "--source SOURCE"    "Platform to search (default: youtube)"
    printf "  %-22s %s\n" "--lang CODE"         "Language filter, e.g. fa en de ar (default: any)"
    printf "  %-22s %s\n" "--region CODE"       "Region filter, e.g. IR US GB (default: global)"
    printf "  %-22s %s\n" "--metric METRIC"     "Sort by: views likes stars citations comments (default: views)"
    printf "  %-22s %s\n" "--limit N"           "Number of results (default: 10)"
    printf "  %-22s %s\n" "--semantic"          "Use semantic vector search instead of keyword"
    printf "  %-22s %s\n" "--ideas"             "Generate cross-source ideas from collected data"
    printf "  %-22s %s\n" "--count N"           "Number of ideas to generate (default: 10, use with --ideas)"
    printf "  %-22s %s\n" "--help"              "Show this help"
    echo ""
    echo "Sources:"
    printf "  %-16s %s\n" "youtube"       "Videos — views, likes, comments"
    printf "  %-16s %s\n" "github"        "Repositories — stars, forks"
    printf "  %-16s %s\n" "arxiv"         "Academic papers — citations"
    printf "  %-16s %s\n" "reddit"        "Posts — score, comments"
    printf "  %-16s %s\n" "producthunt"   "Products — votes, comments"
    printf "  %-16s %s\n" "indiehackers"  "Projects — upvotes"
    echo ""
    echo "Examples:"
    echo "  amir trend                                 # Global trending (most viewed)"
    echo "  amir trend \"AI tools\"                      # Search YouTube for 'AI tools'"
    echo "  amir trend --region IR                     # Trending in Iran"
    echo "  amir trend \"موزیک\" --lang fa               # Persian music videos"
    echo "  amir trend \"LLM\" --source github --metric stars --limit 20"
    echo "  amir trend \"deep learning\" --source arxiv  # Academic papers"
    echo "  amir trend \"devops\" --ideas                # Generate ideas from devops sources"
    echo ""
}

_research_help() {
    echo ""
    echo "Usage: amir research <subcommand> [options]"
    echo ""
    echo "Subcommands:"
    printf "  %-12s %s\n" "discover"  "Find potential PhD supervisors by topic keywords (ArXiv + DBLP)"
    printf "  %-12s %s\n" "trend"     "Search/trending content across YouTube, GitHub, arXiv, Reddit, etc."
    printf "  %-12s %s\n" "ideas"     "Generate cross-source ideas from collected data"
    echo ""
    echo "discover options:"
    printf "  %-28s %s\n" "--keywords KW [KW ...]"      "Topic keywords (required)"
    printf "  %-28s %s\n" "--sources arxiv dblp"        "Sources to search (default: both)"
    printf "  %-28s %s\n" "--since-year YEAR"           "Papers since year (default: 2022)"
    printf "  %-28s %s\n" "--min-papers N"              "Min relevant papers per author (default: 2)"
    printf "  %-28s %s\n" "--top N"                     "Number of candidates to show (default: 10)"
    printf "  %-28s %s\n" "--format txt|md|xlsx"        "Output format (default: txt)"
    printf "  %-28s %s\n" "--categories cs.LG q-fin.CP" "ArXiv category filter (optional)"
    printf "  %-28s %s\n" "--profile PATH"              "Candidate profile .md for LLM scoring"
    printf "  %-28s %s\n" "--save PATH"                 "Override output file path"
    echo ""
    echo "Examples:"
    echo "  amir research discover --keywords \"MARL portfolio optimization\""
    echo "  amir research discover --keywords \"NLP finance sentiment\" --format md --top 15"
    echo "  amir research discover --keywords \"mean field games\" --sources dblp --since-year 2021"
    echo ""
}

_run_research_discover() {
    local toolkit_dir python_bin
    toolkit_dir="$(_trend_toolkit_dir)"
    python_bin="$toolkit_dir/.venv/bin/python"

    if [[ ! -d "$toolkit_dir" ]]; then
        echo "❌ Research toolkit not found at: $toolkit_dir"
        return 1
    fi
    if [[ ! -x "$python_bin" ]]; then
        echo "❌ research_toolkit venv not found. Run: cd $toolkit_dir && bash install.sh"
        return 1
    fi

    local keywords=()
    local sources=()
    local since_year="" min_papers="" top_n="" fmt="" save="" profile="" categories=()
    local show_help=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --keywords)
                shift
                while [[ $# -gt 0 && "$1" != --* ]]; do
                    keywords+=("$1"); shift
                done ;;
            --sources)
                shift
                while [[ $# -gt 0 && "$1" != --* ]]; do
                    sources+=("$1"); shift
                done ;;
            --categories)
                shift
                while [[ $# -gt 0 && "$1" != --* ]]; do
                    categories+=("$1"); shift
                done ;;
            --since-year)   since_year="$2";  shift 2 ;;
            --min-papers)   min_papers="$2";  shift 2 ;;
            --top)          top_n="$2";       shift 2 ;;
            --format)       fmt="$2";         shift 2 ;;
            --save)         save="$2";        shift 2 ;;
            --profile)      profile="$2";     shift 2 ;;
            --help|-h)      show_help=true;   shift ;;
            *)              shift ;;
        esac
    done

    if [[ "$show_help" == true || ${#keywords[@]} -eq 0 ]]; then
        _research_help
        return 0
    fi

    local cmd=("$python_bin" main.py discover --keywords "${keywords[@]}")
    [[ ${#sources[@]}    -gt 0 ]] && cmd+=(--sources    "${sources[@]}")
    [[ ${#categories[@]} -gt 0 ]] && cmd+=(--categories "${categories[@]}")
    [[ -n "$since_year" ]]        && cmd+=(--since-year "$since_year")
    [[ -n "$min_papers" ]]        && cmd+=(--min-papers "$min_papers")
    [[ -n "$top_n" ]]             && cmd+=(--top         "$top_n")
    [[ -n "$fmt" ]]               && cmd+=(--format      "$fmt")
    [[ -n "$save" ]]              && cmd+=(--save        "$save")
    [[ -n "$profile" ]]           && cmd+=(--profile     "$profile")

    # If --save not given, generate default path anchored to caller's CWD
    if [[ -z "$save" ]]; then
        local user_cwd slug today ext
        user_cwd="$(pwd)"
        slug="${keywords[0]// /_}"
        slug="${slug:0:20}"
        today="$(date +%Y%m%d)"
        ext="${fmt:-txt}"
        cmd+=(--save "${user_cwd}/discover_${slug}_${today}.${ext}")
    fi

    (cd "$toolkit_dir" && "${cmd[@]}")
}

run_trend() {
    # Route `amir research discover` before the trend arg-parser takes over
    if [[ "$1" == "discover" ]]; then
        shift
        _run_research_discover "$@"
        return $?
    fi

    local toolkit_dir
    toolkit_dir="$(_trend_toolkit_dir)"

    if [[ ! -d "$toolkit_dir" ]]; then
        echo "❌ Research toolkit not found at: $toolkit_dir"
        echo "   Set RESEARCH_TOOLKIT_DIR in .env or export it before running."
        return 1
    fi

    # Use the toolkit's own venv python directly to avoid venv conflicts
    local python_bin="$toolkit_dir/.venv/bin/python"
    if [[ ! -x "$python_bin" ]]; then
        echo "❌ research_toolkit venv not found at: $toolkit_dir/.venv"
        echo "   Run: cd $toolkit_dir && bash install.sh"
        return 1
    fi

    # ── Defaults ──────────────────────────────────────────────────────────────
    local source="youtube"
    local lang=""
    local region=""
    local metric="views"
    local limit=10
    local semantic=false
    local ideas=false
    local count=10
    local keyword=""
    local show_help=false

    # ── Argument parsing ──────────────────────────────────────────────────────
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --source|-s)
                source="$2"; shift 2 ;;
            --lang|-l)
                lang="$2"; shift 2 ;;
            --region|-r)
                region="$2"; shift 2 ;;
            --metric|-m)
                metric="$2"; shift 2 ;;
            --limit|-n)
                limit="$2"; shift 2 ;;
            --count|-c)
                count="$2"; shift 2 ;;
            --semantic)
                semantic=true; shift ;;
            --ideas|--idea)
                ideas=true; shift ;;
            --help|-h)
                show_help=true; shift ;;
            -*)
                echo "❌ Unknown option: $1"
                _trend_help
                return 1 ;;
            *)
                # Positional: keyword (allow multi-word quoted or single token)
                if [[ -z "$keyword" ]]; then
                    keyword="$1"
                else
                    keyword="$keyword $1"
                fi
                shift ;;
        esac
    done

    if [[ "$show_help" == true ]]; then
        _trend_help
        return 0
    fi

    # ── Ideas mode ────────────────────────────────────────────────────────────
    if [[ "$ideas" == true ]]; then
        if [[ -z "$keyword" ]]; then
            echo "❌ --ideas requires a keyword. Example: amir trend \"AI tools\" --ideas"
            return 1
        fi
        local idea_cmd=("$python_bin" main.py idea --keywords "$keyword")
        [[ -n "$source" ]] && idea_cmd+=(--sources "$source")
        idea_cmd+=(--count "$count")

        echo "🧠 Generating $count ideas for: \"$keyword\" ..."
        (cd "$toolkit_dir" && "${idea_cmd[@]}")
        return $?
    fi

    # ── Query / Trending mode ─────────────────────────────────────────────────
    local cmd=("$python_bin" main.py query)

    if [[ -z "$keyword" ]]; then
        # No keyword → trending mode (most viewed)
        cmd+=(--trending)
    else
        cmd+=("$keyword")
    fi

    cmd+=(--source "$source")
    cmd+=(--metric "$metric")
    cmd+=(--limit "$limit")

    [[ -n "$lang" ]]          && cmd+=(--lang "$lang")
    [[ -n "$region" ]]        && cmd+=(--region "$region")
    [[ "$semantic" == true ]] && cmd+=(--semantic)

    (cd "$toolkit_dir" && "${cmd[@]}")
}
