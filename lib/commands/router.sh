#!/usr/bin/env bash
# amir router — single AI gateway (delegate.py in the vault).
# Multi-model: gemini/gemma (FREE) · minimax · deepseek-v4-flash/-pro · grok.
# Conversation memory via --session, proof + cost ledger via audit.
# Source of truth for routing policy: ~/.local/share/agent-projects/_router/STRATEGY.md

run_router() {
    local DELEGATE="$HOME/.local/share/agent-projects/_router/delegate.py"
    if [[ ! -f "$DELEGATE" ]]; then
        echo "❌ router not found: $DELEGATE"; return 1
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
        ""|-h|--help)
            cat <<'EOF'
Usage:
  amir router "<prompt>" [--model M] [--session S] [--new] [--system T]
  amir router audit            # cost / usage ledger
  amir router cost             # cost dashboard
  amir router models [prov]    # list provider model catalogs

Models (--model): minimax (default, prepaid) | flash | pro | grok
                  gemini | gemini-lite | gemma   (FREE tier)
Memory: reuse --session NAME across calls; --new resets it.
Examples:
  amir router --model gemini write a python fib function
  amir router -s code --model gemini now add memoization
  amir router --model deepseek-v4-flash --plan PLAN.md --out ANSWER.md
EOF
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
