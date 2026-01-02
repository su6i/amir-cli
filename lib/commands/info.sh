#!/bin/bash

run_info() {
    info() {
        local target="$1"
        local full_path=$(realpath "$target" 2>/dev/null || echo "$target")
        
        if [[ ! -e "$target" ]]; then
            echo "❌ Error: '$target' not found."
            return 1
        fi
    
        echo -e "\033[1;34m📊 General Info for: $(basename "$target")\033[0m"
        echo "------------------------------------------"
        
        local birth_time="N/A"
        local device_info=""
        
        if [[ "$OSTYPE" == "darwin"* ]]; then
            birth_time=$(stat -f "%SB" "$target")
            local mod_time=$(stat -f "%Sm" "$target")
            local size_bytes=$(stat -f "%z" "$target")
            local file_type=$(stat -f "%HT" "$target")
            
            # تلاش اول: متادیتای سیستم مک
            device_info=$(mdls -name kMDItemModel -name kMDItemSoftware -name kMDItemCreator "$full_path" 2>/dev/null | awk -F' = ' '{print $2}' | tr -d '()"\n' | sed 's/null//g')
        fi
    
        # ۲. پردازش مدیا و استخراج تگ سازنده (Encoder/Handler)
        local media_info=""
        local extra_tags=""
        if [[ "$target" =~ \.(mp4|mkv|mp3|wav|mov|avi|flv|wmv|m4a|flac|webm)$ ]]; then
            if command -v ffprobe >/dev/null 2>&1; then
                media_info=$(ffprobe -v error -show_entries format=duration,size -show_entries stream=width,height,codec_name,bit_rate -of default=noprint_wrappers=1 "$target")
                # تلاش دوم: استخراج تگ‌های مخفی از داخل خود فایل
                extra_tags=$(ffprobe -v error -show_entries format_tags=encoder,handler_name,com.apple.quicktime.software -of default=noprint_wrappers=1 "$target" | awk -F'=' '{print $2}' | tr '\n' ' ' | sed 's/null//g')
            fi
        fi
    
        # ۳. ترکیب اطلاعات دستگاه و تگ‌های مدیا
        local final_dev="${device_info} ${extra_tags}"
    
        export PY_SIZE="$size_bytes" PY_MOD="$mod_time" PY_BIRTH="$birth_time"
        export PY_TYPE="$file_type" PY_MEDIA="$media_info" PY_DEV="$final_dev"
    
        python3 << 'PYTHON_EOF'
import os

def format_size(bytes_val):
    try:
        b = float(bytes_val)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if b < 1024: return f"{b:.2f} {unit}"
            b /= 1024
    except: return bytes_val

def format_duration(seconds_val):
    try:
        s = float(seconds_val)
        return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}"
    except: return seconds_val

dev = os.environ.get('PY_DEV', '').strip()
if not dev or dev == "": dev = "Unknown / Generic"

print(f"📄 Type:     {os.environ.get('PY_TYPE')}")
print(f"📏 Size:     {format_size(os.environ.get('PY_SIZE'))}")
print(f"🐣 Created:  {os.environ.get('PY_BIRTH')}")
print(f"📅 Modified: {os.environ.get('PY_MOD')}")
print(f"💻 Device:   {dev}")

media = os.environ.get('PY_MEDIA', '')
if media:
    print(f"\n\033[1;35m🎬 Media Metadata (Formatted):\033[0m")
    for line in media.split('\n'):
        if '=' in line:
            k, v = line.split('=', 1)
            if k == 'size': v = format_size(v)
            elif k == 'duration': v = format_duration(v)
            elif k == 'bit_rate':
                try: v = f"{float(v)/1_000_000:.2f} Mbps"
                except: pass
            print(f"  🔹 {k:12} = {v}")
PYTHON_EOF
        echo "------------------------------------------"
    }
    info "$@"
}
