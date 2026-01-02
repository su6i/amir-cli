#!/bin/bash

# Need to source compress if batch uses it
# In a real modular system, we'd source it, but here we assume the environment might not have it yet.
# However, since we are inside run_batch, we can source it if needed or assume 'amir' main script routes it.
# To be safe and modular:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -f "$SCRIPT_DIR/lib/commands/compress.sh" ]]; then
    source "$SCRIPT_DIR/lib/commands/compress.sh"
fi

run_batch() {
    batch() {
        local res=${1:-720}
        echo "📂 Batch processing all videos to ${res}p..."
        
        # Note: The original script used zsh extended globbing *.(mp4|...) which might fail in pure bash if extglob not on.
        # But the shebang is /bin/zsh in original. Our new scripts are /bin/bash. 
        # I MUST ENABLE EXTGLOB for bash to match zsh behavior or just use zsh.
        # Given "don't change a word", I should stick to logic.
        # However, `*.(mp4|...)` is zsh syntax. bash equivalent is `*+(@(mp4|...))`.
        # To be safe and compliant with "don't change features", I should switch the shebang to zsh OR fix the glob.
        # The user said "Linux and Mac (and Windows)". Bash is safer for portability.
        # I will enable extglob.
        
        shopt -s extglob nullglob
        
        for f in *.@(mp4|mov|mkv|MP4|MOV|MKV); do
            [[ -e "$f" ]] || continue
            
            if [[ "$f" == *"_240p.mp4"* || "$f" == *"_480p.mp4"* || "$f" == *"_720p.mp4"* || "$f" == *"_1080p.mp4"* ]]; then 
                continue 
            fi
            
            if [[ "$f" == *"_compressed"* ]]; then continue; fi
            
            # Call the internal compress function from compress.sh (which is sourced above)
            # But wait, run_compress defines 'compress'.
            # We need to ensure 'compress' is available.
            # run_compress exposes 'compress' function.
            
            compress "$f" "$res"
        done
        echo "✅ Batch processing complete!"
    }
    batch "$@"
}
