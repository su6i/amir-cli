#!/bin/bash
# lib/help_common.sh — shared --help / usage helpers for amir-cli command modules.
#
# Sourced once from the `amir` entry script (after amir_lib.sh, which defines
# $BOLD/$NC), so every command module can rely on these being present without
# re-sourcing this file itself.
#
# Bash 3.2 compatible: no associative arrays, no `local -n`, no `${var,,}`.

# amir_help_requested "$@" — true (0) if the first positional argument is a
# help request. Usage: `amir_help_requested "$@" && { cmd_usage; return 0; }`
amir_help_requested() {
    case "$1" in
        --help|-h|help) return 0 ;;
        *) return 1 ;;
    esac
}

# usage_block <<'TXT'
# Usage: amir <cmd> [options]
#
# Description:
#   One or two lines saying what the command does.
#
# Options:
#   --flag VALUE   what it does
#
# Examples:
#   amir <cmd> --flag value
# TXT
#
# Prints stdin verbatim, bolding the four section headers (Usage:,
# Description:, Options:, Examples:) with the entry script's $BOLD/$NC. Falls
# back to plain text if those vars are unset (e.g. when a command module is
# sourced standalone, outside `amir`).
usage_block() {
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        case "$line" in
            Usage:*|Description:*|Options:*|Examples:*)
                echo -e "${BOLD}${line}${NC}"
                ;;
            *)
                echo "$line"
                ;;
        esac
    done
}
