#!/bin/bash

_qr_usage() {
    usage_block <<'TXT'
Usage: amir qr <text|link|phone|email> [output.png]

Description:
  Generate a QR code and copy it to the clipboard, or save it to a PNG file.
  The input is auto-detected: a run of 8+ digits becomes a tel: link, an
  address with an "@" becomes a mailto: link, anything with a "." and no
  spaces/scheme becomes an https:// URL, everything else is plain text.

Options:
  text|link|phone|email   Data to encode — required
  output.png              If given, save the QR code here instead of the
                           clipboard (".png" is appended if missing)

Examples:
  amir qr "https://example.com"
  amir qr 15551234567
  amir qr "hello world" out.png
TXT
}

run_qr() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _qr_usage
        return 0
    fi
    if [[ -z "$1" ]]; then
        _qr_usage
        return 0
    fi
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
