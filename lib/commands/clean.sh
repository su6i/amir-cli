#!/bin/bash

run_clean() {
    clean() {
        OS_TYPE=$(uname -s)
    
        if [[ "$OS_TYPE" == "Darwin" ]]; then
            echo "🍎 OS Detected: macOS"
            echo "------------------------------------------"
            echo "📊 Analyzing system clutter..."
    
            # Calculate total size with error handling for empty paths
            trash_size=$(du -sh ~/.Trash 2>/dev/null | awk '{print $1}')
            [ -z "$trash_size" ] && trash_size="0B"
            
            cache_size=$(du -sh ~/Library/Caches 2>/dev/null | awk '{print $1}')
            [ -z "$cache_size" ] && cache_size="0B"
            
            echo "Current Clutter Status:"
            echo "  - Trash Size:  $trash_size"
            echo "  - User Caches: $cache_size"
            echo ""
    
            # Show top 3 largest items in Trash
            echo "🗑 Top 3 Items in Trash:"
            if [ "$(ls -A ~/.Trash 2>/dev/null)" ]; then
                find ~/.Trash -mindepth 1 -maxdepth 1 2>/dev/null | xargs du -sh 2>/dev/null | sort -rh | head -n 3 | awk '{print "  👉 " $2 " (" $1 ")"}'
            else
                echo "  (Trash is empty)"
            fi
            echo ""
    
            # Show top 3 largest items in Caches
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
                
                # Deletion operations
                [ "$(ls -A ~/.Trash 2>/dev/null)" ] && rm -rf ~/.Trash/* 2>/dev/null
                find ~/Library/Caches -mindepth 1 -delete 2>/dev/null
                find ~/Library/Logs -type f -mtime +7 -delete 2>/dev/null
                
                # System refresh
                osascript -e 'tell application "Finder" to empty trash' 2>/dev/null
                
                echo "✅ macOS System Cleaned Successfully!"
            else
                echo "❌ Operation cancelled."
            fi
    
        elif [[ "$OS_TYPE" == *"NT"* || "$OS_TYPE" == *"MINGW"* ]]; then
            echo "🪟 Windows System Detected - Functionality limited in Git Bash."
            echo "Please use PowerShell for deep system cleaning."
        fi
    }
    clean
}
