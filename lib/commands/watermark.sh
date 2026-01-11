#!/bin/bash

run_watermark() {
    print_header "🌊 Universal Watermarker"
    
    # Check dependencies (Pillow)
    # We assume 'python3' is available. 
    # Ideally should use a venv for amir-cli. for now use system python or simple check.
    
    SCRIPT_PATH="$LIB_DIR/python/watermarker.py"
    
    python3 "$SCRIPT_PATH" "$@"
    
    if [ $? -eq 0 ]; then
        log_success "Watermarking completed."
    else
        log_error "Watermarking failed."
    fi
}
