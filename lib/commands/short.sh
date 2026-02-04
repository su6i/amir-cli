#!/bin/bash

run_short() {
    # Helper: Copy to Clipboard
    copy_to_clipboard() {
        local response="$1"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo -n "$response" | pbcopy
            echo "📋 Copied to clipboard (macOS)"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if command -v xclip &> /dev/null; then
                echo -n "$response" | xclip -selection clipboard
                echo "📋 Copied to clipboard (xclip)"
            elif command -v xsel &> /dev/null; then
                echo -n "$response" | xsel --clipboard
                echo "📋 Copied to clipboard (xsel)"
            fi
        elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
            if command -v clip.exe &> /dev/null; then
                echo -n "$response" | clip.exe
                echo "📋 Copied to clipboard (Windows)"
            fi
        fi
    }

    # Helper: Single Provider Attempt
    try_provider() {
        local provider="$1"
        local url="$2"
        local debug="$3"
        local response=""

        [[ $debug -eq 1 ]] && echo "☁️ Trying $provider..."

        case "$provider" in
            "is.gd")
                response=$(curl -s -m 5 "https://is.gd/?longurl=${url}" 2>&1)
                if [[ -n "$response" && "$response" =~ ^https:// && ! "$response" =~ "error" ]]; then
                    echo "$response"
                    return 0
                fi
                ;;
            "tinyurl.com"|"tinyurl")
                response=$(curl -s -m 5 "https://tinyurl.com/api-create.php?url=${url}" 2>&1)
                if [[ -n "$response" && "$response" =~ ^https:// ]]; then
                    echo "$response"
                    return 0
                fi
                ;;
            "da.gd")
                response=$(curl -s -m 5 "https://da.gd/shorten?url=${url}" 2>&1)
                if [[ -n "$response" && "$response" =~ ^https:// ]]; then
                     # trim newline
                    echo "${response}" | tr -d '\n'
                    return 0
                fi
                ;;
        esac
        return 1
    }

    short() {
        # Source Config
        local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local LIB_DIR="$(dirname "$SCRIPT_DIR")"
        if [[ -f "$LIB_DIR/config.sh" ]]; then
            source "$LIB_DIR/config.sh"
        else
            get_config() { echo "$3"; }
        fi
        
        local preferred_provider=$(get_config "short" "provider" "is.gd")

        if [[ -z "$1" ]]; then 
            echo "❌ Enter URL."
            return 1
        fi
        
        local url="$1"
        local debug=0
        
        # Parse flags
        [[ "$2" == "--debug" || "$2" == "-d" ]] && debug=1
        [[ "$1" == "--debug" || "$1" == "-d" ]] && url="$2" && debug=1
        
        # Ensure Protocol
        if [[ ! "$url" =~ ^https?:// ]]; then
            url="https://$url"
        fi
        
        echo "🔗 Shortening: $url"
        echo "   (Preferred: $preferred_provider)"
        echo ""
        
        # Order: Preferred first, then others
        local providers=("$preferred_provider" "is.gd" "tinyurl.com" "da.gd")
        # Remove duplicates handled by logic flow (skip if already tried)
        
        local tried=""
        
        for p in "${providers[@]}"; do
            # Skip if already tried (simple substring check or strict equality)
            if [[ "$tried" == *"$p"* ]]; then continue; fi
            
            local result=$(try_provider "$p" "$url" "$debug")
            if [[ $? -eq 0 ]]; then
                copy_to_clipboard "$result"
                echo "📍 Link: $result"
                echo ""
                return 0
            fi
            tried="$tried $p"
        done
        
        echo "❌ All services failed!"
        return 1
    }
    short "$@"
}
