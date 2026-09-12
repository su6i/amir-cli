#!/usr/bin/env bash
# amir router — single AI gateway (ai-router repo: $HOME/@-github/ai-router/src/delegate.py, overridable via AI_ROUTER_DIR).
# Multi-model: gemini/gemma (FREE) · minimax · deepseek-v4-flash/-pro · grok.
# Conversation memory via --session, proof + cost ledger via audit.

_router_usage() {
    usage_block <<'TXT'
Usage: amir router "<prompt>" [options]
       amir router audit
       amir router cost
       amir router models [provider]

Description:
  Single AI gateway (ai-router repo): send a prompt to a model, or use one
  of the ledger/catalog subcommands. With no prompt and no subcommand,
  shows this help (no network call).

Options:
  "<prompt>"          Free-text prompt to send
  -m, --model M       Model alias: minimax (default, prepaid) | flash | pro |
                       grok | gemini | gemini-lite | gemma (FREE tier)
  -s, --session S     Reuse conversation memory across calls under name S
  --new               Reset the session named by --session
  --system T          System prompt text
  --out FILE          Write the response to FILE
  --plan FILE         Read the prompt from a plan file
  audit               Show the cost/usage ledger
  cost                Show the cost dashboard
  models [provider]   List provider model catalogs (delegates to amir llm-lists)

Examples:
  amir router --model gemini write a python fib function
  amir router -s code --model gemini now add memoization
  amir router --model deepseek-v4-flash --plan PLAN.md --out ANSWER.md
  amir router audit
TXT
}

run_router() {
    # --help must answer before touching the (optional) ai-router repo.
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _router_usage
        return 0
    fi

    local ai_router_dir="${AI_ROUTER_DIR:-$HOME/@-github/ai-router}"
    _ensure_external_repo "amir router" "ai-router" "$ai_router_dir" "AI_ROUTER_DIR" "ai-router" || return 1
    local DELEGATE="$ai_router_dir/src/delegate.py"
    if [[ ! -f "$DELEGATE" ]]; then
        echo "❌ ai-router repo found at $ai_router_dir but src/delegate.py is missing (repo layout changed?)" >&2
        return 1
    fi

    case "$1" in
        audit)
            python3 "$DELEGATE" --audit; return $? ;;
        cost)
            echo "📊 amir router cost — dashboard not built yet (next task)."
            echo "   For now: amir router audit  (raw ledger)"; return 0 ;;
        models)
            shift
            if [[ -f "$LIB_DIR/commands/llm-lists.sh" ]]; then
                source "$LIB_DIR/commands/llm-lists.sh"; llm_lists "$@"; return $?
            fi
            echo "❌ llm-lists.sh not found"; return 1 ;;
        "")
            _router_usage
            return 0 ;;
    esac

    # General form: separate known flags from free-text prompt words.
    local args=() prompt=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -m|--model)   args+=(--model "$2"); shift 2 ;;
            -s|--session) args+=(--session "$2"); shift 2 ;;
            --system)     args+=(--system "$2"); shift 2 ;;
            --out)        args+=(--out "$2"); shift 2 ;;
            --plan)       args+=(--plan "$2"); shift 2 ;;
            --new)        args+=(--new); shift ;;
            *)            prompt+=("$1"); shift ;;
        esac
    done
    [[ ${#prompt[@]} -gt 0 ]] && args+=(-p "${prompt[*]}")
    python3 "$DELEGATE" "${args[@]}"
}
