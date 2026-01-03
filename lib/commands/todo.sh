#!/bin/bash

run_todo() {
    todo() {
        local file="$HOME/.su6i_scripts/todo_list.txt"
        touch "$file"
    
        if [[ -z "$1" ]]; then
            echo -e "\033[1;33m📝 Your TODO List:\033[0m"
            if [[ ! -s "$file" ]]; then
                echo "   (Empty)"
            else
                sed 's/ ([0-9][0-9]\/[0-9][0-9])//g' "$file" | nl -w2 -s'. ' | sed 's/^/   /'
            fi
            echo "💡 Add: amir todo 'task'"
            echo "💡 Done: amir todo done [number]"
    
        elif [[ "$1" == "done" ]]; then
            if [[ -z "$2" ]]; then
                echo "❌ Enter item number. (e.g., amir todo done 1)"
            else
                sed -i '' "${2}d" "$file"
                echo "✅ Item $2 removed."
            fi
        else
            echo "- $1" >> "$file"
            echo "✅ Added."
        fi
    }
    todo "$@"
}
