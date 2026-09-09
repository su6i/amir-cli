#!/bin/bash

_lock_usage() {
    usage_block <<'TXT'
Usage: amir lock <file>

Description:
  Encrypt a file with GPG (AES256, interactive password prompt) to
  <file>.gpg. The original file is left in place.

Options:
  file   File to encrypt — required

Examples:
  amir lock secrets.txt
TXT
}

run_lock() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _lock_usage
        return 0
    fi
    if [[ -z "$1" ]]; then
        _lock_usage
        return 0
    fi
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

_unlock_usage() {
    usage_block <<'TXT'
Usage: amir unlock <file>

Description:
  Decrypt a GPG-encrypted <file>.gpg back to its original file (drops the
  .gpg extension). The encrypted file is left in place.

Options:
  file   File to decrypt — required, must end in .gpg

Examples:
  amir unlock secrets.txt.gpg
TXT
}

run_unlock() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _unlock_usage
        return 0
    fi
    if [[ -z "$1" ]]; then
        _unlock_usage
        return 0
    fi
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
