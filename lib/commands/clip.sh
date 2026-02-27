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
                    echo "✅ Text from pipe copied to clipboard"
                elif [[ -n "$DISPLAY" ]] || [[ -n "$WAYLAND_DISPLAY" ]]; then
                    if echo -n "$input_text" | xclip -selection clipboard 2>/dev/null || \
                       echo -n "$input_text" | xsel --clipboard 2>/dev/null; then
                        echo "✅ Text from pipe copied to clipboard"
                    else
                        echo "❌ xclip/xsel not installed. Run: sudo apt install xclip"
                        return 1
                    fi
                else
                    echo "⚠️  No display detected (headless server)."
                    echo "   Clipboard is not available via SSH without X11 forwarding."
                    echo "   ↳ Tip: use 'ssh -X' or pipe to a file instead."
                    return 1
                fi
            fi
            return 0
        fi
    
        # 2. If no arguments are provided
        if [[ $# -eq 0 ]]; then
            # If output is piped (e.g., amir clip | amir pdf)
            if [[ ! -t 1 ]]; then
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    pbpaste
                else
                    xclip -selection clipboard -o 2>/dev/null || xsel --clipboard --output 2>/dev/null
                fi
                return 0
            fi
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
            # Copy text only to clipboard
            local text_to_copy="$*"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo -n "$text_to_copy" | pbcopy
                echo "🔤 Text copied to clipboard: '$text_to_copy'"
            elif [[ -n "$DISPLAY" ]] || [[ -n "$WAYLAND_DISPLAY" ]]; then
                if echo -n "$text_to_copy" | xclip -selection clipboard 2>/dev/null || \
                   echo -n "$text_to_copy" | xsel --clipboard 2>/dev/null; then
                    echo "🔤 Text copied to clipboard: '$text_to_copy'"
                else
                    echo "❌ xclip/xsel not installed. Run: sudo apt install xclip"
                    return 1
                fi
            else
                echo "⚠️  No display detected (headless server). Clipboard not available."
                return 1
            fi
        fi
    }
    clip "$@"
}
