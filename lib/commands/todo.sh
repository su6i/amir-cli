#!/bin/bash

_todo_usage() {
    usage_block <<'TXT'
Usage: amir todo [task|list|done <number>]

Description:
  A simple local TODO list, stored at ~/.amir/todo_list.txt (overridable via
  todo.file in config).

Options:
  (no args)      Show the list (same as "list")
  "task text"    Add a new item
  list           Show the list
  done <number>  Remove item <number> (as shown in the list)

Examples:
  amir todo
  amir todo "write the report"
  amir todo done 2
TXT
}

run_todo() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _todo_usage
        return 0
    fi

    todo() {
        # Source Config
        local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local LIB_DIR="$(dirname "$SCRIPT_DIR")"
        if [[ -f "$LIB_DIR/config.sh" ]]; then
            source "$LIB_DIR/config.sh"
        else
            get_config() { echo "$3"; }
        fi
        
        local default_file="$HOME/.amir/todo_list.txt"
        local file=$(get_config "todo" "file" "$default_file")
        
        # Expand ~ if present in config path
        file="${file/#\~/$HOME}"
        
        mkdir -p "$(dirname "$file")"
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
    
        elif [[ "$1" == "list" ]]; then
            echo -e "\033[1;33m📝 Your TODO List:\033[0m"
            if [[ ! -s "$file" ]]; then
                echo "   (Empty)"
            else
                sed 's/ ([0-9][0-9]\/[0-9][0-9])//g' "$file" | nl -w2 -s'. ' | sed 's/^/   /'
            fi

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
