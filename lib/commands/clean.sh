#!/bin/bash

run_clean() {
    clean() {
        OS_TYPE=$(uname -s)
    
        if [[ "$OS_TYPE" == "Darwin" ]]; then
            echo "🍎 OS Detected: macOS"
            echo "------------------------------------------"
            echo "📊 Analyzing system clutter..."
    
            # محاسبه حجم کلی با مدیریت خطا برای مسیرهای خالی
            trash_size=$(du -sh ~/.Trash 2>/dev/null | awk '{print $1}')
            [ -z "$trash_size" ] && trash_size="0B"
            
            cache_size=$(du -sh ~/Library/Caches 2>/dev/null | awk '{print $1}')
            [ -z "$cache_size" ] && cache_size="0B"
            
            echo "Current Clutter Status:"
            echo "  - Trash Size:  $trash_size"
            echo "  - User Caches: $cache_size"
            echo ""
    
            # نمایش ۳ مورد بزرگ سطل آشغال
            echo "🗑 Top 3 Items in Trash:"
            if [ "$(ls -A ~/.Trash 2>/dev/null)" ]; then
                find ~/.Trash -mindepth 1 -maxdepth 1 2>/dev/null | xargs du -sh 2>/dev/null | sort -rh | head -n 3 | awk '{print "  👉 " $2 " (" $1 ")"}'
            else
                echo "  (Trash is empty)"
            fi
            echo ""
    
            # نمایش ۳ مورد بزرگ کش‌ها
            echo "📂 Top 3 Items in User Caches:"
            if [ "$(ls -A ~/Library/Caches 2>/dev/null)" ]; then
                find ~/Library/Caches -mindepth 1 -maxdepth 1 2>/dev/null | xargs du -sh 2>/dev/null | sort -rh | head -n 3 | awk '{print "  👉 " $2 " (" $1 ")"}'
            else
                echo "  (Caches are empty)"
            fi
            
            echo "------------------------------------------"
            echo -n "⚠️ Proceed with cleaning? (y/n): "
            read confirmation
            
            if [[ "$confirmation" == "y" || "$confirmation" == "Y" ]]; then
                echo "🧹 Cleaning in progress..."
                
                # عملیات حذف
                [ "$(ls -A ~/.Trash 2>/dev/null)" ] && rm -rf ~/.Trash/* 2>/dev/null
                find ~/Library/Caches -mindepth 1 -delete 2>/dev/null
                find ~/Library/Logs -type f -mtime +7 -delete 2>/dev/null
                
                # رفرش سیستم
                osascript -e 'tell application "Finder" to empty trash' 2>/dev/null
                
                echo "✅ macOS System Cleaned Successfully!"
            else
                echo "❌ Operation cancelled."
            fi
    
        elif [[ "$OS_TYPE" == *"NT"* || "$OS_TYPE" == *"MINGW"* ]]; then
            echo "🪟 OS Detected: Windows"
            # ... (بخش ویندوز ثابت می‌ماند)
        fi
    }
    clean
}
