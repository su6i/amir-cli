#!/bin/bash

# بررسی نصب بودن ImageMagick
if ! command -v magick &> /dev/null; then
    echo "Error: ImageMagick is not installed. Please run: brew install imagemagick"
    exit 1
fi

# متغیرهای پیش‌فرض
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

# تابع راهنما
# تابع راهنما
usage() {
    echo "Usage: $0 [input_file] [options]"
    echo "Options:"
    echo "  -i, --input   File path (Alternative)"
    echo "  -c, --color   Global color (Optional, overrides auto-average)"
    echo "  -t, --top     Pixels [Color]"
    echo "  -b, --bottom  Pixels [Color]"
    echo "  -l, --left    Pixels [Color]"
    echo "  -r, --right   Pixels [Color]"
    exit 1
}

# اگر اولین آرگومان فایل باشد (بدون دش)، آن را بردار
if [[ "$1" != -* && -n "$1" ]]; then
    INPUT_FILE="$1"
    shift
fi

# پارس کردن سایر آرگومان‌ها
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

# --- تغییر اصلی اینجاست ---
# اگر رنگی داده نشده، میانگین رنگ کل عکس محاسبه می‌شود
if [[ -z "$GLOBAL_COLOR" ]]; then
    # عکس را به ۱ پیکسل اسکیل می‌کنیم تا میانگین گرفته شود
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

CMD="magick \"$INPUT_FILE\""

if [[ "$TOP_PX" -gt 0 ]]; then
    CMD+=" -background \"$TOP_COL\" -gravity North -splice 0x${TOP_PX}"
fi

if [[ "$BOTTOM_PX" -gt 0 ]]; then
    CMD+=" -background \"$BOTTOM_COL\" -gravity South -splice 0x${BOTTOM_PX}"
fi

if [[ "$LEFT_PX" -gt 0 ]]; then
    CMD+=" -background \"$LEFT_COL\" -gravity West -splice ${LEFT_PX}x0"
fi

if [[ "$RIGHT_PX" -gt 0 ]]; then
    CMD+=" -background \"$RIGHT_COL\" -gravity East -splice ${RIGHT_PX}x0"
fi

CMD+=" \"$OUTPUT_FILE\""

echo "Processing $INPUT_FILE..."
eval $CMD

if [[ $? -eq 0 ]]; then
    echo "Success! Saved as: $OUTPUT_FILE"
else
    echo "Error processing image."
fi
