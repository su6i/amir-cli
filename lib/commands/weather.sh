#!/bin/bash

_weather_usage() { echo "Usage: amir weather [city]"; }

run_weather() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _weather_usage
        return 0
    fi

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
