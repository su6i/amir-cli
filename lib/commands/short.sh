#!/bin/bash

run_short() {
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

    short() {
        if [[ -z "$1" ]]; then 
            echo "❌ Enter URL."
            return 1
        fi
        
        local url="$1"
        local debug=0
        
        # بررسی debug flags
        [[ "$2" == "--debug" || "$2" == "-d" ]] && debug=1
        [[ "$1" == "--debug" || "$1" == "-d" ]] && url="$2" && debug=1
        
        # اگر http/https نداشت، اضافه کن
        if [[ ! "$url" =~ ^https?:// ]]; then
            url="https://$url"
        fi
        
        echo "🔗 Shortening: $url"
        echo ""
        
        local response
        
        # 1. Try is.gd
        [[ $debug -eq 1 ]] && echo "☁️ Trying is.gd..."
        response=$(curl -s -m 5 "https://is.gd/?longurl=${url}" 2>&1)
        if [[ -n "$response" && "$response" =~ ^https:// && ! "$response" =~ "error" ]]; then
            copy_to_clipboard "$response"
            echo "📍 Link: $response"
            echo ""
            return 0
        fi
        
        # 2. Try tinyurl.com
        [[ $debug -eq 1 ]] && echo "☁️ Trying tinyurl.com..."
        response=$(curl -s -m 5 "https://tinyurl.com/api-create.php?url=${url}" 2>&1)
        if [[ -n "$response" && "$response" =~ ^https:// ]]; then
            copy_to_clipboard "$response"
            echo "📍 Link: $response"
            echo ""
            return 0
        fi
        
        # 3. Try da.gd
        [[ $debug -eq 1 ]] && echo "☁️ Trying da.gd..."
        response=$(curl -s -m 5 "https://da.gd/shorten?url=${url}" 2>&1)
        if [[ -n "$response" && "$response" =~ ^https:// ]]; then
            copy_to_clipboard "$response"
            echo "📍 Link: $response"
            echo ""
            return 0
        fi
        
        echo "❌ All services failed!"
        return 1
    }
    short "$@"
}
