#!/bin/bash

run_lock() {
    lock() {
        if [[ -z "$1" || ! -f "$1" ]]; then 
            echo "❌ File not found."
            return 1
        fi
        
        local input="$1"
        local output="${input}.gpg"
        
        echo "🔐 Encrypting: $input → $output"
        
        if gpg -c --cipher-algo AES256 "$input" 2>/dev/null; then
            echo "✅ File encrypted: $output"
            echo "⚠️  Keep the password safe!"
            echo "📍 Original file still exists: $input"
            echo "💡 To remove original: rm $input"
        else
            echo "❌ Encryption failed!"
            return 1
        fi
    }
    lock "$@"
}

run_unlock() {
    unlock() {
        if [[ -z "$1" || ! -f "$1" ]]; then 
            echo "❌ File not found."
            return 1
        fi
        
        local input="$1"
        
        # Check if file is encrypted (ends with .gpg)
        if [[ "$input" != *.gpg ]]; then
            echo "❌ This doesn't look like an encrypted file (.gpg)"
            echo "💡 Try: amir unlock ${input}.gpg"
            return 1
        fi
        
        local output="${input%.gpg}"  # Remove .gpg extension
        
        echo "🔓 Decrypting: $input → $output"
        
        if gpg -d -o "$output" "$input" 2>/dev/null; then
            echo "✅ File decrypted: $output"
            echo "📍 Encrypted file still exists: $input"
            echo "💡 To remove encrypted: rm $input"
        else
            echo "❌ Decryption failed!"
            echo "⚠️  Wrong password or corrupted file?"
            return 1
        fi
    }
    unlock "$@"
}
