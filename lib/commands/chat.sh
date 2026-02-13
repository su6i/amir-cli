#!/bin/bash

# Define global variables used by chat/code
# These were at the top of the original file
BASE_DIR="$HOME/.amir"
CHAT_LOG="$BASE_DIR/chat_history.md"
CODE_LOG="$BASE_DIR/code_history.md"

run_chat() {
    chat() {
        # Check history switch
        if [[ "$1" == "--history" ]]; then
            if command -v glow >/dev/null 2>&1; then
                glow "$CHAT_LOG"
            else
                less "$CHAT_LOG"
            fi
            return 0
        fi
    
        if [ -f "$BASE_DIR/.env" ]; then source "$BASE_DIR/.env"; fi
        local api_key="$GEMINI_API_KEY"
        local prompt="$*"
        if [[ -z "$api_key" || -z "$prompt" ]]; then echo "❌ Missing API key or Prompt"; return 1; fi
    
        local m_list="gemini-2.5-flash-lite|gemini-3-flash-preview|gemini-2.0-flash|gemma-3-27b-it"
        echo -e "⏳ \033[1;33mConnecting to Chat models...\033[0m"
    
        export TEMP_GEMINI_KEY="$api_key" TEMP_PROMPT="$prompt" MODEL_STR="$m_list" LOG_PATH="$CHAT_LOG"
    
        python3 << 'PYTHON_EOF'
import urllib.request, json, os, sys
from datetime import datetime

def call_gemini(model, prompt, key):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload = {'contents': [{'parts': [{'text': prompt}]}]}
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), 
                                   headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"ERR:{e}"

api_key, prompt, models = os.environ.get('TEMP_GEMINI_KEY'), os.environ.get('TEMP_PROMPT'), os.environ.get('MODEL_STR').split('|')
log_path = os.environ.get('LOG_PATH')

for m in models:
    print(f"Checking {m}...", end=" ", flush=True)
    result = call_gemini(m, prompt, api_key)
    if not result.startswith("ERR:"):
        print("\033[1;32mOK!\033[0m")
        print(f'\n\033[1;32m🤖 Response ({m}):\033[0m\n{result}')
        
        # ثبت در تاریخچه
        with open(log_path, "a") as f:
            f.write(f"\n# 💬 CHAT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Model:** `{m}`\n\n**Q:** {prompt}\n\n**A:**\n{result}\n\n---\n")
        break
PYTHON_EOF
        unset TEMP_GEMINI_KEY TEMP_PROMPT MODEL_STR LOG_PATH
    }
    chat "$@"
}
