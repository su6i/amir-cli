#!/bin/bash

run_qr() {
    qr() {
        if [[ -z "$1" ]]; then 
            echo "❌ Enter text, link, phone number or email."
            return 1
        fi
        
        local input="$1"
        local protocol_type="Text"
    
        if [[ "$input" =~ ^[0-9+]+$ ]] && [[ ${#input} -ge 8 ]]; then
            input="tel:$input"
            protocol_type="Phone Number"
        elif [[ "$input" == *@*.* ]]; then
            input="mailto:$input"
            protocol_type="Email"
        elif [[ "$input" == *.* && "$input" != http* && "$input" != *\ * ]]; then
            input="https://$input"
            protocol_type="URL"
        fi
    
        echo "📌 Mode: $protocol_type | Data: $input"
        qrencode -t ANSIUTF8 "$input"
    
        local temp_qr
        temp_qr=$(mktemp "$(amir_preferred_temp_dir "$PWD")/temp_qr_amir_XXXXXX.png")
        qrencode -o "$temp_qr" -s 10 "$input"
        
        osascript -e "set the clipboard to (read (POSIX file \"$temp_qr\") as JPEG picture)" 2>/dev/null
        
        if [[ -n "$2" ]]; then
            local output="$2"
            [[ "$output" != *.png ]] && output="${output}.png"
            mv "$temp_qr" "$output"
            echo "✅ QR Code saved: $output"
        else
            rm "$temp_qr"
            echo "✅ QR Code copied to clipboard."
        fi
    }
    qr "$@"
}
