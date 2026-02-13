#!/bin/bash

run_dashboard() {
    dashboard() {
        
        echo -e "\033[1;34m"$(printf '%.0s─' {1..60})"\033[0m"
        
        # 1. Disk Storage Status
        echo -e "💾 \033[1;37mFree Disk Space:\033[0m \033[1;32m$(df -h / | awk 'NR==2 {print $4}')\033[0m"
        
        echo -e "\033[1;34m"$(printf '%.0s─' {1..60})"\033[0m"

        # 2. Recent Tasks (TODOs)
        echo -e "\n\033[1;33m📝 Recent TODOs:\033[0m"
        
        # Source Config
        local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local LIB_DIR="$(dirname "$SCRIPT_DIR")"
        if [[ -f "$LIB_DIR/config.sh" ]]; then
            source "$LIB_DIR/config.sh"
        else
            get_config() { echo "$3"; }
        fi
        
        local default_file="$HOME/.amir/todo_list.txt"
        local todo_file=$(get_config "todo" "file" "$default_file")
        todo_file="${todo_file/#\~/$HOME}"
        if [[ -f "$todo_file" ]]; then
            sed 's/ ([0-9][0-9]\/[0-9][0-9])//g' "$todo_file" | nl -w2 -s'. ' | sed 's/^/   / '
        else
            echo "   (No pending tasks)"
        fi
        
        echo -e "\033[1;34m"$(printf '%.0s─' {1..60})"\033[0m"
        
        # 3. macOS Calendar (Today and Tomorrow events)
        if command -v icalBuddy &> /dev/null; then
            # Fetch Events
            local today_raw=$(icalBuddy -nc eventsToday)
            local tomorrow_raw=$(icalBuddy -nc eventsFrom:tomorrow to:tomorrow | grep -v "tomorrow")
            
            # Default messages if empty
            [[ -z "$today_raw" ]] && today_raw="✅ No events."
            [[ -z "$tomorrow_raw" ]] && tomorrow_raw="✅ No events."

            # Convert to arrays (splitting by newline)
            IFS=$'\n' read -rd '' -a today_lines <<< "$today_raw"
            IFS=$'\n' read -rd '' -a tomorrow_lines <<< "$tomorrow_raw"
            
            # Find max lines to iterate
            local max_lines=${#today_lines[@]}
            [[ ${#tomorrow_lines[@]} -gt $max_lines ]] && max_lines=${#tomorrow_lines[@]}

            # Calculate dynamic width for the left column (Today)
            
            # 1. Get Terminal Width (Default to 80 if tput fails)
            local term_width=$(tput cols 2>/dev/null || echo 80)
            local half_width=$((term_width / 2))
            
            # 2. Find max content length
            local max_content_len=0
            for line in "${today_lines[@]}"; do
                [[ ${#line} -gt $max_content_len ]] && max_content_len=${#line}
            done
            
            # 3. Determine Column Width: Max of (Half Screen) vs (Content + Padding)
            local col_width=$((half_width - 2)) # Default: Half screen minus safety margin
            local required_width=$((max_content_len + 4)) # Content + 4 spaces padding
            
            if [[ $required_width -gt $col_width ]]; then
                col_width=$required_width
            fi

            # Print Header using Manual Padding
            local header_padding=$((col_width - 8)) 
            # Actually using ${#var} on header string is safer if consistent
            local h1="📅 Today:"
            local h2="🌅 Tomorrow:"
            local p1=$((col_width - ${#h1})) 
            if [[ $p1 -lt 0 ]]; then p1=2; fi
            printf "   \033[1;35m%s\033[0m%${p1}s \033[1;36m%s\033[0m\n" "$h1" "" "$h2"

            # Print Rows Side-by-Side
            for (( i=0; i<max_lines; i++ )); do
                local left="${today_lines[i]}"
                local right="${tomorrow_lines[i]}"
                
                # Manual Padding Calculation
                local len_left=${#left}
                local pad_len=$((col_width - len_left))
                if [[ $pad_len -lt 0 ]]; then pad_len=1; fi
                
                # Print: Left Content + Spaces + Right Content
                printf "   %s%${pad_len}s %s\n" "$left" "" "$right"
            done
        else
            echo "   ⚠️ icalBuddy not installed (brew install ical-buddy)"
        fi
        
        echo -e "\033[1;34m"$(printf '%.0s─' {1..60})"\033[0m\n"
    }
    dashboard
}
