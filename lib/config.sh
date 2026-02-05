
#!/bin/bash

# Configuration File Path
CONFIG_FILE="$HOME/.amir/config.yaml"

# Helper: Read value from YAML
# Usage: get_config "section" "key" "default_value"
get_config() {
    local section="$1"
    local key="$2"
    local default="$3"
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo "$default"
        return
    fi
    
    # Python-based parser (since we verified python3 is available, just not the yaml module)
    # Actually, the user's environment showed 'no yaml' module for python.
    # So we fallback to awk for simple "key: value" parsing under sections.
    # Assumption: Config is simple 2-level YAML.
    # section:
    #   key: value
    
    local value=$(awk -v section="$section" -v key="$key" '
        BEGIN { in_section=0; result="" }
        
        # Detect section start (e.g. "pdf:")
        $1 == section":" { in_section=1; next }
        
        # Detect other section start (stop processing)
        /^[a-zA-Z0-9_]+:/ { if (in_section) exit }
        
        # Extract key within section
        in_section && $1 == key":" {
            # Remove key: and leading whitespace
            sub(key":", "", $0)
            # Remove inline comments headers
            sub(/#[^"'\''*]*$/, "", $0) 
            # Trim leading/trailing whitespace
            gsub(/^[ \t]+|[ \t]+$/, "", $0)
            print $0
            exit
        }
    ' "$CONFIG_FILE")
    
    if [[ -n "$value" ]]; then
        echo "$value"
    else
        echo "$default"
    fi
}

# Helper: Initialize Config if missing
init_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        mkdir -p "$(dirname "$CONFIG_FILE")"
        cat <<EOF > "$CONFIG_FILE"
# Amir CLI Configuration

# PDF Command Settings
pdf:
  radius: 10          # Default corner radius (int)
  rotate: 0           # Default rotation angle (deg)

# Video Compression Settings
compress:
  resolution: 720     # Target height (p) e.g. 480, 720, 1080
  quality: 60         # Constant Rate Factor / Quality (0-100)

# Audio Extraction Settings
mp3:
  bitrate: 320        # Default bitrate in kbps

# Image Manipulation Settings
img:
  default_size: 1080  # Default resize target if not specified

# QR Code Settings
qr:
  size: 10            # Pixel size per module (dot)

# Password Generator Settings
pass:
  length: 16          # Default password length

# Weather Settings
weather:
  default_city: Montpellier # Default city if argument missing

# Todo Settings
todo:
  file: ~/.amir/todo_list.txt # Path to todo file

# URL Shortener Settings
short:
  provider: is.gd     # Preferred provider (is.gd, tinyurl.com, da.gd)
EOF
    fi
}
