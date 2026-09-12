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
    if [[ -n "${RESEARCH_TOOLKIT_DIR:-}" ]]; then
        echo "$RESEARCH_TOOLKIT_DIR"
    elif [[ -n "${AMIR_ROOT:-}" && -d "$AMIR_ROOT/lib/research_toolkit" ]]; then
        echo "$AMIR_ROOT/lib/research_toolkit"
    else
        echo "$HOME/@-github/research_toolkit"
    fi
}

_trend_help() {
    usage_block <<'TXT'
Usage: amir trend [keyword] [options]

Description:
  Trending content & idea search across YouTube, GitHub, ArXiv, Reddit,
  Product Hunt and Indie Hackers, via the research_toolkit Multi-Agent RAG
  pipeline. No keyword shows globally trending (most-viewed) content.

Options:
  keyword                Search term (omit for global trending)
  --source, -s SOURCE    Platform: youtube github arxiv reddit producthunt
                          indiehackers (default: youtube)
  --lang, -l CODE        Language filter, e.g. fa en de ar (default: any)
  --region, -r CODE      Region filter, e.g. IR US GB (default: global)
  --metric, -m METRIC    Sort by: views likes stars citations comments (default: views)
  --limit, -n N          Number of results (default: 10)
  --semantic              Use semantic vector search instead of keyword
  --ideas                 Generate cross-source ideas from collected data
  --count, -c N           Number of ideas to generate (default: 10, use with --ideas)

Sources:
  youtube        Videos — views, likes, comments
  github         Repositories — stars, forks
  arxiv          Academic papers — citations
  reddit         Posts — score, comments
  producthunt    Products — votes, comments
  indiehackers   Projects — upvotes

Examples:
  amir trend
  amir trend "AI tools"
  amir trend --region IR
  amir trend "LLM" --source github --metric stars --limit 20
  amir trend "devops" --ideas
TXT
}

run_trend() {
    # --help must answer before touching the (optional) research_toolkit repo.
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _trend_help
        return 0
    fi

    local toolkit_dir
    toolkit_dir="$(_trend_toolkit_dir)"

    _ensure_external_repo "amir trend" "research_toolkit" "$toolkit_dir" "RESEARCH_TOOLKIT_DIR" "research_toolkit" || return 1

    # Use the toolkit's own venv python directly to avoid venv conflicts
    local python_bin="$toolkit_dir/.venv/bin/python"
    if [[ ! -x "$python_bin" ]]; then
        if [[ "${AMIR_NO_AUTO_INSTALL:-}" == "1" ]] || ! _amir_stdin_is_tty; then
            echo "❌ research_toolkit venv not found at: $toolkit_dir/.venv"
            echo "   Run: cd $toolkit_dir && bash install.sh"
            return 1
        fi
        echo "📦 research_toolkit venv not found — running install.sh (this can take a few minutes) ..." >&2
        (cd "$toolkit_dir" && bash install.sh) || { echo "❌ install.sh failed" >&2; return 1; }
        if [[ ! -x "$python_bin" ]]; then
            echo "❌ research_toolkit venv still not found after install.sh" >&2
            return 1
        fi
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

    # ── Auto-provision the API key(s) this run actually needs ────────────────
    local -a _trend_needed_keys=()
    case "$source" in
        youtube)     _trend_needed_keys+=(YOUTUBE_API_KEY) ;;
        github)      _trend_needed_keys+=(GITHUB_TOKEN) ;;
        reddit)      _trend_needed_keys+=(REDDIT_CLIENT_ID REDDIT_CLIENT_SECRET) ;;
        producthunt) _trend_needed_keys+=(PRODUCTHUNT_API_TOKEN) ;;
        *) ;;
    esac
    [[ "$ideas" == true ]] && _trend_needed_keys+=(GEMINI_API_KEY)

    local _trend_key _trend_help_url
    for _trend_key in "${_trend_needed_keys[@]}"; do
        case "$_trend_key" in
            YOUTUBE_API_KEY)       _trend_help_url="https://console.cloud.google.com/apis/library/youtube.googleapis.com" ;;
            GITHUB_TOKEN)          _trend_help_url="https://github.com/settings/tokens" ;;
            REDDIT_CLIENT_ID|REDDIT_CLIENT_SECRET)
                                   _trend_help_url="https://www.reddit.com/prefs/apps" ;;
            PRODUCTHUNT_API_TOKEN) _trend_help_url="https://api.producthunt.com/v2/docs" ;;
            GEMINI_API_KEY)        _trend_help_url="https://aistudio.google.com/app/apikey" ;;
        esac
        _amir_ensure_api_key "$_trend_key" "$toolkit_dir/.env" "$_trend_help_url"
    done

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
