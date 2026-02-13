#!/bin/bash

run_clip() {
    clip() {
        # 1. If input is piped (e.g., echo "hello" | clip)
        if [[ ! -t 0 ]]; then
            local input_text=$(cat)
            
            # If a filename is provided as an argument, save text into it
            if [[ $# -gt 0 ]]; then
                local target="$1"
                echo -n "$input_text" > "$target"
                local full_path=$(realpath "$target")
                
                # Copy file in macOS
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    osascript -e "set the clipboard to (POSIX file \"$full_path\") as «class furl»" 2>/dev/null
                fi
                echo "💾 Saved to file and copied: $full_path"
            else
                # Copy text only to clipboard
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    echo -n "$input_text" | pbcopy
                else
                    echo -n "$input_text" | xclip -selection clipboard 2>/dev/null || echo -n "$input_text" | xsel --clipboard 2>/dev/null
                fi
                echo "✅ Text from pipe copied to clipboard"
            fi
            return 0
        fi
    
        # 2. If no arguments are provided
        if [[ $# -eq 0 ]]; then
            echo "❌ Error: No input provided."
            echo "Usage: clip <file>  OR  clip <text>  OR  echo 'hi' | clip"
            return 1
        fi
    
        # 3. Check if argument is an existing file or plain text
        if [[ -f "$1" ]]; then
            # --- File Copy Section ---
            local full_path=$(realpath "$1")
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # Copy as file (for Paste in Telegram/Finder)
                osascript -e "set the clipboard to (POSIX file \"$full_path\") as «class furl»" 2>/dev/null
                echo "📁 File copied (as object): $full_path"
            else
                # In Linux, copy file path
                echo -n "$full_path" | xclip -selection clipboard 2>/dev/null
                echo "📍 File path copied: $full_path"
            fi
        else
            # --- Plain Text Copy Section ---
            local text_to_copy="$*"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo -n "$text_to_copy" | pbcopy
            else
                echo -n "$text_to_copy" | xclip -selection clipboard 2>/dev/null || echo -n "$text_to_copy" | xsel --clipboard 2>/dev/null
            fi
            echo "🔤 Text copied to clipboard: '$text_to_copy'"
        fi
    }
    clip "$@"
}
