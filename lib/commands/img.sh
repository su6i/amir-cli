#!/bin/bash

run_img() {
    img() {
        local input="$1"
        local size="$2"
        local gravity_code="$3"
        echo "DEBUG: Size='$size' Gravity='$gravity_code'"

        if [[ -z "$input" || ! -f "$input" ]]; then 
            echo "❌ Image file not found."
            return 1
        fi
        if [[ -z "$size" ]]; then 
            echo "❌ Enter size (e.g., 512 or 400x120)"
            return 1
        fi

        # استانداردسازی سایز
        if [[ ! "$size" == *"x"* ]]; then size="${size}x${size}"; fi
        local width=$(echo $size | cut -dx -f1)
        local height=$(echo $size | cut -dx -f2)
        local output="${input%.*}_${width}x${height}.${input##*.}"

        # تشخیص ابزار موجود بر اساس سیستم‌عامل
        local cmd=""
        if command -v magick &> /dev/null; then
            cmd="magick"
        elif command -v convert &> /dev/null; then
            cmd="convert"
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            cmd="sips"
        fi

        if [[ -z "$cmd" ]]; then
            echo "❌ Error: ImageMagick is not installed."
            return 1
        fi

        if [[ -n "$gravity_code" ]]; then
            # نگاشت کدهای ۱ تا ۹ به جهات جغرافیایی
            local g="center"
            case "$gravity_code" in
                "7") g="northwest" ;; "8") g="north" ;; "9") g="northeast" ;;
                "4") g="west"      ;; "5") g="center" ;; "6") g="east"      ;;
                "1") g="southwest" ;; "2") g="south"  ;; "3") g="southeast" ;;
            esac

            echo "✂️  Cropping with $cmd (Gravity: $g)..."
            if [[ "$cmd" == "sips" ]]; then
                # شبیه‌سازی کراپ در مک (فقط عمودی را پشتیبانی می‌کند)
                local s_g="center"
                [[ "$gravity_code" =~ [789] ]] && s_g="top"
                [[ "$gravity_code" =~ [123] ]] && s_g="bottom"
                sips -Z $width "$input" --out "$output" > /dev/null
                sips --cropToHeightWidth $height $width "$output" > /dev/null
            else
                # کراپ حرفه‌ای در لینوکس و ویندوز
                $cmd "$input" -resize "${width}x${height}^" -gravity "$g" -extent "${width}x${height}" "$output"
            fi
        else
            echo "🖼  Resizing with $cmd..."
            if [[ "$cmd" == "sips" ]]; then
                sips -z $height $width "$input" --out "$output" > /dev/null
            else
                $cmd "$input" -resize "${width}x${height}!" "$output"
            fi
        fi
        echo "✅ Image saved: $output"
    }
    img "$@"
}