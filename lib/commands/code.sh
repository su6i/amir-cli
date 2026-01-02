#!/bin/bash

# Define global variables used by chat/code
# These were at the top of the original file
BASE_DIR="$HOME/.su6i_scripts"
CHAT_LOG="$BASE_DIR/chat_history.md"
CODE_LOG="$BASE_DIR/code_history.md"

run_code() {
    code() {
        # بررسی سوییچ تاریخچه
        if [[ "$1" == "--history" ]]; then
            if command -v glow >/dev/null 2>&1; then
                glow "$CODE_LOG"
            else
                less "$CODE_LOG"
            fi
            return 0
        fi
    
        if [ -f "$BASE_DIR/.env" ]; then source "$BASE_DIR/.env"; fi
        local api_key="$GEMINI_API_KEY"
        local instruction="" code_content=""
    
        if [[ ! -t 0 ]]; then
            code_content=$(cat); instruction="$*"
        elif [[ -f "$1" ]]; then
            code_content=$(cat "$1"); instruction="${@:2}"
        elif [[ "$1" == "clip" ]]; then
            code_content=$(pbpaste); instruction="${@:2}"
        else
            instruction="$*"
        fi
    
        [ -z "$instruction" ] && instruction="Refactor or explain this."
        local final_prompt="Instruction: $instruction\n\nContent:\n\`\`\`\n$code_content\n\`\`\`"
        local m_list="gemini-2.5-flash|gemini-3-flash-preview|gemini-2.5-flash-lite|gemma-3-27b-it"
    
        echo -e "💻 \033[1;34mAnalyzing with Flash & Gemma...\033[0m"
    
        export TEMP_GEMINI_KEY="$api_key" TEMP_PROMPT="$final_prompt" MODEL_STR="$m_list" LOG_PATH="$CODE_LOG" RAW_INS="$instruction"
    
        python3 << 'PYTHON_EOF'
import urllib.request, json, os, sys, subprocess
from datetime import datetime

def call_gemini(model, prompt, key):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload = {'contents': [{'parts': [{'text': prompt}]}]}
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"ERR:{e}"

api_key, prompt, models = os.environ.get('TEMP_GEMINI_KEY'), os.environ.get('TEMP_PROMPT'), os.environ.get('MODEL_STR').split('|')
log_path, ins = os.environ.get('LOG_PATH'), os.environ.get('RAW_INS')

for m in models:
    print(f"Trying {m}...", end=" ", flush=True)
    result = call_gemini(m, prompt, api_key)
    if not result.startswith("ERR:"):
        print("\033[1;32mOK!\033[0m")
        print(f'\n\033[1;36m🛠️ Result ({m}):\033[0m\n{result}')
        
        # کپی در کلیپ‌بورد
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        process.communicate(input=result.encode('utf-8'))

        # ثبت در تاریخچه (Markdown)
        with open(log_path, "a") as f:
            f.write(f"\n# 🛠️ CODE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Model:** `{m}`\n\n**Instruction:** {ins}\n\n**Result:**\n{result}\n\n---\n")
        break
PYTHON_EOF
        unset TEMP_GEMINI_KEY TEMP_PROMPT MODEL_STR LOG_PATH RAW_INS
    }
    code "$@"
}
