#!/bin/bash

run_clip() {
    # OSC 52: copy text to the LOCAL machine's clipboard through SSH tunnel.
    # Works on iTerm2, WezTerm, Kitty, Windows Terminal, tmux (set-clipboard on).
    # No X11, no display, no xclip needed.
    _osc52_copy() {
        local text="$1"
        # Strip trailing newlines so pastes never have a phantom newline at the end
        text="${text%$'\n'}"
        local b64
        b64=$(printf '%s' "$text" | base64 | tr -d '\n')
        # tmux requires a different escape wrapping
        if [[ -n "$TMUX" ]]; then
            printf "\033Ptmux;\033\033]52;c;%s\a\033\\" "$b64"
        else
            printf "\033]52;c;%s\a" "$b64"
        fi
        echo "✅ Copied to your local clipboard via OSC 52"
    }

    clip() {
        # 1. If input is piped (e.g., echo "hello" | clip)
        if [[ ! -t 0 ]]; then
            local input_text
            input_text=$(cat)

            # If a filename is provided as an argument, save text into it
            if [[ $# -gt 0 ]]; then
                local target="$1"
                echo -n "$input_text" > "$target"
                local full_path
                full_path=$(realpath "$target")

                # Copy file in macOS
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    osascript -e "set the clipboard to (POSIX file \"$full_path\") as «class furl»" 2>/dev/null
                fi
                echo "💾 Saved to file and copied: $full_path"
            else
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    printf '%s' "$input_text" | pbcopy
                    echo "✅ Copied to clipboard"
                elif [[ -n "$DISPLAY" ]] || [[ -n "$WAYLAND_DISPLAY" ]]; then
                    if printf '%s' "$input_text" | xclip -selection clipboard 2>/dev/null || \
                       printf '%s' "$input_text" | xsel --clipboard 2>/dev/null; then
                        echo "✅ Copied to clipboard"
                    else
                        _osc52_copy "$input_text"
                    fi
                else
                    # Headless server: use OSC 52 to send to local terminal clipboard
                    _osc52_copy "$input_text"
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
            local full_path
            full_path=$(realpath "$1")
            if [[ "$OSTYPE" == "darwin"* ]]; then
                osascript -e "set the clipboard to (POSIX file \"$full_path\") as «class furl»" 2>/dev/null
                echo "📁 File copied (as object): $full_path"
            else
                # Copy file contents via OSC 52 (works over SSH)
                _osc52_copy "$(cat "$full_path")"
                echo "📍 File contents copied: $full_path"
            fi
        else
            # --- Plain Text Copy Section ---
            local text_to_copy="$*"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                printf '%s' "$text_to_copy" | pbcopy
                echo "🔤 Text copied to clipboard: '$text_to_copy'"
            elif [[ -n "$DISPLAY" ]] || [[ -n "$WAYLAND_DISPLAY" ]]; then
                if printf '%s' "$text_to_copy" | xclip -selection clipboard 2>/dev/null || \
                   printf '%s' "$text_to_copy" | xsel --clipboard 2>/dev/null; then
                    echo "🔤 Text copied to clipboard: '$text_to_copy'"
                else
                    _osc52_copy "$text_to_copy"
                fi
            else
                _osc52_copy "$text_to_copy"
            fi
        fi
    }
    clip "$@"
}
