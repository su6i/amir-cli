#!/bin/bash
# amir img extend — extend an image's canvas on one or more sides
# (invoked as a standalone script by lib/commands/img.sh; not sourced by `amir`)

# Help function (exit_code lets --help exit 0 while real errors still exit 1)
usage() {
    local exit_code="${1:-1}"
    echo "Usage: amir img extend <input_file> [options]"
    echo ""
    echo "Description:"
    echo "  Extend an image's canvas on the top/bottom/left/right, filling the new"
    echo "  area with a given color (or the image's own average color if none is"
    echo "  given). Saves to <name>_extended.<ext> alongside the input."
    echo ""
    echo "Options:"
    echo "  input_file             Image to extend — required"
    echo "  -i, --input FILE       Same as the positional input_file"
    echo "  -t, --top PX [COLOR]   Extend the top by PX pixels"
    echo "  -b, --bottom PX [COLOR]  Extend the bottom by PX pixels"
    echo "  -l, --left PX [COLOR]  Extend the left by PX pixels"
    echo "  -r, --right PX [COLOR] Extend the right by PX pixels"
    echo "  -c, --color COLOR      Default color for all sides (if a side has none)"
    echo "  -h, --help             Show this help"
    echo ""
    echo "Note: if no color is given at all, the image's own average color is used."
    echo ""
    echo "Examples:"
    echo "  amir img extend photo.jpg --top 100 --color white"
    echo "  amir img extend photo.jpg --top 50 --bottom 50"
    exit "$exit_code"
}

if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" || $# -eq 0 ]]; then
    usage 0
fi

# Check if ImageMagick is installed
if ! command -v magick &> /dev/null; then
    echo "Error: ImageMagick is not installed. Please run: brew install imagemagick"
    exit 1
fi

# Default variables
INPUT_FILE=""
GLOBAL_COLOR=""
TOP_PX=0
TOP_COL=""
BOTTOM_PX=0
BOTTOM_COL=""
LEFT_PX=0
LEFT_COL=""
RIGHT_PX=0
RIGHT_COL=""

# If first argument is a file (no dash), pick it up
if [[ "$1" != -* && -n "$1" ]]; then
    INPUT_FILE="$1"
    shift
fi

# Parse remaining arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -i|--input)
            INPUT_FILE="$2"
            shift; shift
            ;;
        -c|--color)
            GLOBAL_COLOR="$2"
            shift; shift
            ;;
        -t|--top)
            TOP_PX="$2"
            shift
            if [[ -n "$2" && "$2" != -* ]]; then
                TOP_COL="$2"
                shift
            fi
            shift
            ;;
        -b|--bottom)
            BOTTOM_PX="$2"
            shift
            if [[ -n "$2" && "$2" != -* ]]; then
                BOTTOM_COL="$2"
                shift
            fi
            shift
            ;;
        -l|--left)
            LEFT_PX="$2"
            shift
            if [[ -n "$2" && "$2" != -* ]]; then
                LEFT_COL="$2"
                shift
            fi
            shift
            ;;
        -r|--right)
            RIGHT_PX="$2"
            shift
            if [[ -n "$2" && "$2" != -* ]]; then
                RIGHT_COL="$2"
                shift
            fi
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$INPUT_FILE" ]]; then
    echo "Error: Input file is required."
    usage
fi

FILENAME=$(basename -- "$INPUT_FILE")
EXTENSION="${FILENAME##*.}"
NAME="${FILENAME%.*}"
OUTPUT_FILE="${NAME}_extended.${EXTENSION}"

# --- Main Logic Here ---
# If no color provided, calculate average image color
if [[ -z "$GLOBAL_COLOR" ]]; then
    # Scale image to 1x1 pixel to get average color
    echo "Calculating average color..."
    AUTO_BG=$(magick "$INPUT_FILE" -scale 1x1! -format "%[pixel:p{0,0}]" info:)
    GLOBAL_COLOR="$AUTO_BG"
    echo "Auto-detected average color: $GLOBAL_COLOR"
fi
# -------------------------

TOP_COL="${TOP_COL:-$GLOBAL_COLOR}"
BOTTOM_COL="${BOTTOM_COL:-$GLOBAL_COLOR}"
LEFT_COL="${LEFT_COL:-$GLOBAL_COLOR}"
RIGHT_COL="${RIGHT_COL:-$GLOBAL_COLOR}"

CMD=(magick "$INPUT_FILE")

if [[ "$TOP_PX" -gt 0 ]]; then
    CMD+=(-background "$TOP_COL" -gravity North -splice "0x${TOP_PX}")
fi

if [[ "$BOTTOM_PX" -gt 0 ]]; then
    CMD+=(-background "$BOTTOM_COL" -gravity South -splice "0x${BOTTOM_PX}")
fi

if [[ "$LEFT_PX" -gt 0 ]]; then
    CMD+=(-background "$LEFT_COL" -gravity West -splice "${LEFT_PX}x0")
fi

if [[ "$RIGHT_PX" -gt 0 ]]; then
    CMD+=(-background "$RIGHT_COL" -gravity East -splice "${RIGHT_PX}x0")
fi

CMD+=("$OUTPUT_FILE")

echo "Processing $INPUT_FILE..."
"${CMD[@]}"

if [[ $? -eq 0 ]]; then
    echo "Success! Saved as: $OUTPUT_FILE"
else
    echo "Error processing image."
fi
