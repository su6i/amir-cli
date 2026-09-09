#!/bin/bash

_watermark_usage() {
    usage_block <<'TXT'
Usage: amir watermark <input> [options]

Description:
  Apply an image or text watermark to an image or video file (via a Pillow
  based Python helper).

Options:
  input             Input file (image or video) — required
  -o, --output F    Output file path (default: alongside input)
  -i, --image F     Path to a watermark image
  -t, --text T      Watermark text
  -p, --pos POS     Position: SE | SW | NE | NW | C (default: SE)
  -r, --resize WxH  Resize output, e.g. 400x120

Examples:
  amir watermark photo.jpg --text "@amir" --pos SE
  amir watermark clip.mp4 --image logo.png --pos NW
TXT
}

run_watermark() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _watermark_usage
        return 0
    fi
    if [[ -z "$1" ]]; then
        _watermark_usage
        return 0
    fi

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
