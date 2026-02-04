#!/bin/bash

run_weather() {
    weather() {
        # Source Config
        local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local LIB_DIR="$(dirname "$SCRIPT_DIR")"
        if [[ -f "$LIB_DIR/config.sh" ]]; then
            source "$LIB_DIR/config.sh"
        else
            get_config() { echo "$3"; }
        fi
        
        local default_city=$(get_config "weather" "default_city" "Montpellier")
        local city=${1:-$default_city}
        curl -s "wttr.in/${city}?0m2t" 
    }
    weather "$@"
}
