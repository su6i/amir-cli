#!/bin/bash

run_dashboard() {
    dashboard() {
        echo -e "\n\033[1;34m"$(printf '%.0s─' {1..60})"\033[0m"
        
        # ۱. وضعیت حافظه دیسک
        echo -e "💾 \033[1;37mFree Disk Space:\033[0m \033[1;32m$(df -h / | awk 'NR==2 {print $4}')\033[0m"
        
        # ۲. لیست کارهای اخیر (TODOs)
        echo -e "\n\033[1;33m📝 Recent TODOs:\033[0m"
        local todo_file="$HOME/.su6i_scripts/todo_list.txt"
        if [[ -f "$todo_file" ]]; then
            tail -n 3 "$todo_file" | sed 's/^/   / '
        else
            echo "   (No pending tasks)"
        fi
        
        echo -e "\033[1;34m"$(printf '%.0s─' {1..60})"\033[0m"
        
        # ۳. تقویم مک (رویدادهای امروز و فردا)
        if command -v icalBuddy &> /dev/null; then
            # نمایش جلسات امروز
            echo -e "\033[1;35m📅 امروز:\033[0m"
            local today=$(icalBuddy -nc eventsToday)
            if [[ -z "$today" ]]; then
                echo "   ✅ برنامه‌ای ندارید."
            else
                echo "$today" | sed 's/^/   • /'
            fi
    
            # نمایش جلسات فردا
            echo -e "\n\033[1;36m🌅 فردا:\033[0m"
            local tomorrow=$(icalBuddy -nc eventsFrom:tomorrow to:tomorrow | grep -v "tomorrow")
            if [[ -z "$tomorrow" ]]; then
                echo "   ✅ برنامه‌ای ندارید."
            else
                echo "$tomorrow" | sed 's/^/   • /'
            fi
        else
            echo "   ⚠️ icalBuddy not installed (brew install ical-buddy)"
        fi
        
        echo -e "\033[1;34m"$(printf '%.0s─' {1..60})"\033[0m"
        
        # ۴. راهنمای هوشمند مدل‌های AI بر اساس سهمیه (Quota) سال ۲۰۲۶
        echo -e "\033[1;30m💡 Quick AI Strategy:\033[0m"
        echo -e "   • \033[1;30mGemma 3 27B: Most stable & highest free quota\033[0m"
        echo -e "   • \033[1;30mFlash-Lite 2.5: Best for high-frequency chat\033[0m"
        echo -e "   • \033[1;30mFlash 2.5: Reserved for complex code logic\033[0m"
        
        echo -e "\033[1;34m"$(printf '%.0s─' {1..60})"\033[0m\n"
    }
    dashboard
}
