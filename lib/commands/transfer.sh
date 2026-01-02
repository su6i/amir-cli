#!/bin/bash

run_transfer() {
    transfer() {
        if [[ -z "$1" || ! -f "$1" ]]; then 
            echo "❌ File not found."
            return 1
        fi
        
        local filename=$(basename "$1")
        local filesize=$(ls -lh "$1" | awk '{print $5}')
        
        echo "📁 File: $filename ($filesize)"
        echo ""
        
        # Array of services to try (معتبرتر و پایدارتر)
        local -a services=(
            "catbox"
            "anonfiles"
            "pixeldrain"
            "uguu"
        )
        
        for service in "${services[@]}"; do
            echo "☁️ Trying $service..."
            
            case "$service" in
                "catbox")
                    # catbox.moe - بسیار معتبر و پایدار
                    local response=$(curl -4 -s -F "reqtype=fileupload" -F "fileToUpload=@$1" "https://catbox.moe/user/api.php" 2>&1)
                    
                    if [[ "$response" =~ ^https://files.catbox.moe ]]; then
                        echo "✅ Upload successful via catbox.moe!"
                        echo "📍 Link: $response"
                        echo -n "$response" | pbcopy 2>/dev/null || echo -n "$response" | xclip -selection clipboard 2>/dev/null
                        echo "📋 Link copied to clipboard"
                        return 0
                    fi
                    ;;
                    
                "anonfiles")
                    # anonfiles.com - معتبر و دارای تاریخچه طولانی
                    local response=$(curl -4 -s -F "file=@$1" "https://api.anonfiles.com/upload" 2>&1)
                    
                    if echo "$response" | grep -q '"url"'; then
                        local link=$(echo "$response" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
                        if [[ -n "$link" ]]; then
                            echo "✅ Upload successful via anonfiles.com!"
                            echo "📍 Link: $link"
                            echo -n "$link" | pbcopy 2>/dev/null || echo -n "$link" | xclip -selection clipboard 2>/dev/null
                            echo "📋 Link copied to clipboard"
                            return 0
                        fi
                    fi
                    ;;
                    
                "pixeldrain")
                    # pixeldrain.com - قابل اعتماد و سریع
                    local response=$(curl -4 -s -F "file=@$1" "https://pixeldrain.com/api/file" 2>&1)
                    
                    if echo "$response" | grep -q '"success"'; then
                        local id=$(echo "$response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
                        if [[ -n "$id" ]]; then
                            local link="https://pixeldrain.com/u/$id"
                            echo "✅ Upload successful via pixeldrain.com!"
                            echo "📍 Link: $link"
                            echo -n "$link" | pbcopy 2>/dev/null || echo -n "$link" | xclip -selection clipboard 2>/dev/null
                            echo "📋 Link copied to clipboard"
                            return 0
                        fi
                    fi
                    ;;
                    
                "uguu")
                    # uguu.se - ساده و معتبر
                    local response=$(curl -4 -s -F "files=@$1" "https://uguu.se/api.php?action=upload" 2>&1)
                    
                    if echo "$response" | grep -q '"url"'; then
                        local link=$(echo "$response" | grep -o '"url":"[^"]*"' | head -1 | cut -d'"' -f4)
                        if [[ -n "$link" ]]; then
                            echo "✅ Upload successful via uguu.se!"
                            echo "📍 Link: $link"
                            echo -n "$link" | pbcopy 2>/dev/null || echo -n "$link" | xclip -selection clipboard 2>/dev/null
                            echo "📋 Link copied to clipboard"
                            return 0
                        fi
                    fi
                    ;;
            esac
            
            echo "⚠️  $service failed, trying next..."
            echo ""
        done
        
        echo "❌ All upload services failed!"
        echo ""
        echo "💡 Possible solutions:"
        echo "   1. Check your internet connection: curl -4 google.com"
        echo "   2. Try disabling VPN (utun interfaces detected)"
        echo "   3. Check firewall settings"
        echo "   4. Try again in a few moments"
        return 1
    }
    transfer "$@"
}
