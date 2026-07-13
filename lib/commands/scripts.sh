#!/bin/bash

run_scripts() {
    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local LIB_DIR="$(dirname "$SCRIPT_DIR")"
    local registry="$LIB_DIR/config/scripts.txt"

    mkdir -p "$(dirname "$registry")"
    touch "$registry"

    local ids=() descs=() cmds=()
    while IFS='|' read -r id desc cmd; do
        [[ -z "$id" || "$id" == \#* ]] && continue
        ids+=("$id")
        descs+=("$desc")
        cmds+=("$cmd")
    done < "$registry"

    if [[ ${#ids[@]} -eq 0 ]]; then
        echo "📭 No saved scripts yet. Add one to: $registry"
        echo "   Format: id|description|command"
        return 0
    fi

    _print_scripts_menu() {
        for i in "${!ids[@]}"; do
            printf "  %2d) %-14s %s\n" "$((i+1))" "${ids[$i]}" "${descs[$i]}"
        done
    }

    if [[ "$1" == "list" ]]; then
        echo "📜 Saved scripts:"
        _print_scripts_menu
        return 0
    fi

    # amir scripts <id> [args...] — run directly by name, no prompt
    if [[ -n "$1" ]]; then
        for i in "${!ids[@]}"; do
            if [[ "${ids[$i]}" == "$1" ]]; then
                local cmd="${cmds[$i]}"
                shift
                eval "$cmd" '"$@"'
                return $?
            fi
        done
        echo "❌ No saved script named '$1'."
        echo "📜 Saved scripts:"
        _print_scripts_menu
        return 1
    fi

    # No args — interactive picker
    echo "📜 Saved scripts:"
    _print_scripts_menu
    echo ""
    read -r -p "Select a script (number or name): " choice

    local idx=-1
    if [[ "$choice" =~ ^[0-9]+$ ]]; then
        idx=$((choice - 1))
    else
        for i in "${!ids[@]}"; do
            if [[ "${ids[$i]}" == "$choice" ]]; then
                idx=$i
                break
            fi
        done
    fi

    if [[ $idx -lt 0 || $idx -ge ${#ids[@]} ]]; then
        echo "❌ Invalid selection."
        return 1
    fi

    echo "▶️  Running: ${ids[$idx]}"
    eval "${cmds[$idx]}"
}
