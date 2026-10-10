#!/bin/bash

_todo_usage() {
    if command -v usage_block >/dev/null 2>&1; then
        usage_block <<'TXT'
Usage: amir todo [task|add <text...>|list|done <number>|clear]

Description:
  A simple local TODO list, stored at ~/.amir/todo_list.txt (overridable via
  todo.file in config or AMIR_TODO_FILE environment variable).

Options:
  (no args)          Show the list (same as "list")
  list               Show the list
  add <text...>      Add a new item (multi-word, quoted or unquoted)
  "task text"        Add a new item (bare text with spaces)
  done <number>      Remove item <number> (as shown in the list)
  clear              Empty the list (requires confirmation or AMIR_YES=1)

Examples:
  amir todo
  amir todo add write the report
  amir todo "write the report"
  amir todo done 2
  amir todo clear
TXT
    else
        cat <<'TXT'
Usage: amir todo [task|add <text...>|list|done <number>|clear]

Description:
  A simple local TODO list, stored at ~/.amir/todo_list.txt (overridable via
  todo.file in config or AMIR_TODO_FILE environment variable).

Options:
  (no args)          Show the list (same as "list")
  list               Show the list
  add <text...>      Add a new item (multi-word, quoted or unquoted)
  "task text"        Add a new item (bare text with spaces)
  done <number>      Remove item <number> (as shown in the list)
  clear              Empty the list (requires confirmation or AMIR_YES=1)

Examples:
  amir todo
  amir todo add write the report
  amir todo "write the report"
  amir todo done 2
  amir todo clear
TXT
    fi
}

_todo_print_list() {
    local target_file="$1"
    echo -e "\033[1;33m📝 Your TODO List:\033[0m"
    if [[ ! -s "$target_file" ]]; then
        echo "   (Empty)"
    else
        sed 's/ ([0-9][0-9]\/[0-9][0-9])//g' "$target_file" | nl -w2 -s'. ' | sed 's/^/   /'
    fi
}

run_todo() {
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || "${1:-}" == "help" ]]; then
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
        local file="${AMIR_TODO_FILE:-}"
        if [[ -z "$file" ]]; then
            file=$(get_config "todo" "file" "$default_file")
        fi

        # Expand ~ if present in config path
        file="${file/#\~/$HOME}"

        mkdir -p "$(dirname "$file")"
        touch "$file"

        if [[ $# -eq 0 || -z "${1:-}" ]]; then
            _todo_print_list "$file"
            echo "💡 Add: amir todo 'task'"
            echo "💡 Done: amir todo done [number]"
            return 0

        elif [[ "$1" == "list" ]]; then
            _todo_print_list "$file"
            return 0

        elif [[ "$1" == "add" ]]; then
            shift
            local text="$*"
            if [[ -z "$text" ]]; then
                _todo_usage
                return 0
            fi
            echo "- $text" >> "$file"
            echo "✅ Added."
            _todo_print_list "$file"
            return 0

        elif [[ "$1" == "done" ]]; then
            local n="${2:-}"
            local line_count=0
            if [[ -f "$file" ]]; then
                line_count=$(wc -l < "$file" | tr -d '[:space:]')
            fi
            if [[ -z "$n" || ! "$n" =~ ^[1-9][0-9]*$ || "$n" -gt "$line_count" ]]; then
                echo "❌ No item $n (the list has $line_count)."
                return 1
            fi
            sed "${n}d" "$file" > "$file.tmp" && mv "$file.tmp" "$file"
            echo "✅ Item $n removed."
            _todo_print_list "$file"
            return 0

        elif [[ "$1" == "clear" ]]; then
            if [[ "${AMIR_YES:-}" != "1" ]]; then
                if [[ ! -t 0 ]]; then
                    echo "❌ Cannot confirm clear in non-interactive mode. Set AMIR_YES=1 to bypass." >&2
                    return 1
                fi
                local confirm=""
                read -r -p "Clear all TODO items? [y/N] " confirm
                case "$confirm" in
                    [yY]|[yY][eE][sS]) ;;
                    *)
                        echo "Cancelled."
                        return 0
                        ;;
                esac
            fi
            > "$file"
            echo "✅ List cleared."
            _todo_print_list "$file"
            return 0

        elif [[ $# -eq 1 && "$1" == *" "* ]]; then
            echo "- $1" >> "$file"
            echo "✅ Added."
            _todo_print_list "$file"
            return 0

        else
            _todo_usage
            return 1
        fi
    }
    todo "$@"
}
