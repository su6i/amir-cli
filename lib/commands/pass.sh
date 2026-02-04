#!/bin/bash

run_pass() {
    pass() {
        # Source Config
        local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local LIB_DIR="$(dirname "$SCRIPT_DIR")"
        if [[ -f "$LIB_DIR/config.sh" ]]; then
            source "$LIB_DIR/config.sh"
        else
            get_config() { echo "$3"; }
        fi

        local default_len=$(get_config "pass" "length" "16")
        local len=${1:-$default_len}
        local p=$(LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*()_+' < /dev/urandom | head -c "$len")
        echo "$p" | pbcopy 2>/dev/null || echo -n "$p" | xclip -selection clipboard 2>/dev/null
        echo "🔑 Password ($len chars) copied: $p"
    }
    pass "$@"
}
