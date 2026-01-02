#!/bin/bash

run_clip() {
    clip() {
        # 1. اگر ورودی از طریق Pipe باشد (مثل: echo "hello" | clip)
        if [[ ! -t 0 ]]; then
            local input_text=$(cat)
            
            # اگر نام فایلی به عنوان آرگومان داده شده باشد، متن را در آن ذخیره کن
            if [[ $# -gt 0 ]]; then
                local target="$1"
                echo -n "$input_text" > "$target"
                local full_path=$(realpath "$target")
                
                # کپی کردن فایل در مک
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    osascript -e "set the clipboard to (POSIX file \"$full_path\") as «class furl»" 2>/dev/null
                fi
                echo "💾 Saved to file and copied: $full_path"
            else
                # فقط کپی کردن متن در کلیپ‌بورد
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    echo -n "$input_text" | pbcopy
                else
                    echo -n "$input_text" | xclip -selection clipboard 2>/dev/null || echo -n "$input_text" | xsel --clipboard 2>/dev/null
                fi
                echo "✅ Text from pipe copied to clipboard"
            fi
            return 0
        fi
    
        # 2. اگر آرگومانی داده نشده باشد
        if [[ $# -eq 0 ]]; then
            echo "❌ Error: No input provided."
            echo "Usage: clip <file>  OR  clip <text>  OR  echo 'hi' | clip"
            return 1
        fi
    
        # 3. بررسی اینکه آیا آرگومان یک فایل موجود است یا متن ساده
        if [[ -f "$1" ]]; then
            # --- بخش کپی فایل ---
            local full_path=$(realpath "$1")
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # کپی به صورت فایل (برای Paste در تلگرام/فایندر)
                osascript -e "set the clipboard to (POSIX file \"$full_path\") as «class furl»" 2>/dev/null
                echo "📁 File copied (as object): $full_path"
            else
                # در لینوکس مسیر فایل کپی می‌شود
                echo -n "$full_path" | xclip -selection clipboard 2>/dev/null
                echo "📍 File path copied: $full_path"
            fi
        else
            # --- بخش کپی متن ساده ---
            local text_to_copy="$*"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo -n "$text_to_copy" | pbcopy
            else
                echo -n "$text_to_copy" | xclip -selection clipboard 2>/dev/null || echo -n "$text_to_copy" | xsel --clipboard 2>/dev/null
            fi
            echo "🔤 Text copied to clipboard: '$text_to_copy'"
        fi
    }
    clip "$@"
}
