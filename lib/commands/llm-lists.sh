#!/usr/bin/env zsh

# ═══════════════════════════════════════════════════════════════════
# LLM Provider Model Lists Fetcher
# ═══════════════════════════════════════════════════════════════════
#
# Usage: amir llm-lists [provider] [-e|--export format]
#
# Providers: gemini, openai, deepseek, groq, anthropic
# Export formats: pdf, md, jpg (optional)

llm_lists() {
    # 1. Robust AMIR_ROOT detection
    # If AMIR_ROOT is not set or doesn't look like this repo, try to detect it
    if [[ -z "$AMIR_ROOT" || ! -f "$AMIR_ROOT/lib/amir_lib.sh" ]]; then
        # Try finding it relative to this script's location
        local script_path="${BASH_SOURCE[0]}" # Bash way (works in both bash and zsh)
        [[ -z "$script_path" && -n "$ZSH_VERSION" ]] && script_path="${(%):-%N}" # Zsh-specific way

        if [[ -n "$script_path" ]]; then
            local cmd_dir="$(cd "$(dirname "$script_path")" && pwd)"
            export AMIR_ROOT="$(cd "$cmd_dir/../.." && pwd)"
        fi
    fi

    # Fallback if detection still fails
    [[ -z "$AMIR_ROOT" ]] && export AMIR_ROOT="$PWD"

    if [[ -f "$AMIR_ROOT/lib/amir_lib.sh" ]]; then
        source "$AMIR_ROOT/lib/amir_lib.sh"
    fi
    local provider=""
    local export_format=""
    local python_script=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -e|--export)
                export_format="$2"
                shift 2
                ;;
            -p|--providers)
                echo "🤖 Available LLM Providers:"
                echo "   • gemini    (Google Gemini SDK)"
                echo "   • openai    (GPT-4/o1 via OpenAI SDK)"
                echo "   • deepseek  (DeepSeek V3/R1 via API)"
                echo "   • groq      (Llama-3/Mistral via Groq)"
                echo "   • anthropic (Claude-3.5/3.7 via SDK)"
                return 0
                ;;
            gemini|openai|deepseek|groq|anthropic)
                provider="$1"
                shift
                ;;
            *)
                echo "❌ Unknown option: $1"
                echo "Usage: amir llm-lists [gemini|openai|deepseek|groq|anthropic] [-e|--export pdf|md|jpg]"
                return 1
                ;;
        esac
    done
    
    # Default to gemini if no provider specified
    if [[ -z "$provider" ]]; then
        echo "🤖 No provider specified. Available providers:"
        echo "   • gemini, openai, deepseek, groq, anthropic"
        echo ""
        echo "Usage: amir llm-lists <provider> [-e|--export pdf|md|jpg]"
        echo "       amir llm-lists --providers  (to see full list)"
        return 1
    fi
    
    # Create Python script
    python_script=$(mktemp /tmp/llm_list_XXXXXX.py)
    
    cat > "$python_script" << 'PYTHON_EOF'
import os
import sys

# 1. Safe dotenv loading
try:
    from dotenv import load_dotenv
    # Look for .env in current dir or AMIR_ROOT
    load_dotenv()
    amir_root = os.getenv("AMIR_ROOT")
    if amir_root and os.path.exists(os.path.join(amir_root, ".env")):
        load_dotenv(os.path.join(amir_root, ".env"))
except ImportError:
    pass

def get_models_list(provider):
    provider = provider.lower()
    print(f"\n🚀 Fetching models for: {provider.upper()}\n")
    
    try:
        # 1. Google Gemini (using new SDK)
        if provider == "gemini":
            try:
                from google import genai
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    print("❌ Error: GEMINI_API_KEY not found. Please add it to your .env file.")
                    return
                client = genai.Client(api_key=api_key)
                for model in client.models.list():
                    print(f"• {model.name} (Display: {model.display_name})")
            except ImportError:
                print("❌ Error: 'google-genai' package not installed.")
                return

        # 2. OpenAI
        elif provider == "openai":
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    print("❌ Error: OPENAI_API_KEY not found.")
                    return
                client = OpenAI(api_key=api_key)
                models = client.models.list()
                for m in models.data:
                    print(f"• {m.id}")
            except ImportError:
                print("❌ Error: 'openai' package not installed.")
                return

        # 3. DeepSeek (OpenAI Compatible)
        elif provider == "deepseek":
            try:
                from openai import OpenAI
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if not api_key:
                    print("❌ Error: DEEPSEEK_API_KEY not found.")
                    return
                client = OpenAI(
                    api_key=api_key, 
                    base_url="https://api.deepseek.com"
                )
                models = client.models.list()
                for m in models.data:
                    print(f"• {m.id}")
            except ImportError:
                print("❌ Error: 'openai' package not installed.")
                return

        # 4. Groq (OpenAI Compatible)
        elif provider == "groq":
            try:
                from openai import OpenAI
                api_key = os.getenv("GROQ_API_KEY")
                if not api_key:
                    print("❌ Error: GROQ_API_KEY not found.")
                    return
                client = OpenAI(
                    api_key=api_key, 
                    base_url="https://api.groq.com/openai/v1"
                )
                models = client.models.list()
                for m in models.data:
                    print(f"• {m.id}")
            except ImportError:
                print("❌ Error: 'openai' package not installed.")
                return

        # 5. Anthropic
        elif provider == "anthropic":
            print("📋 Known Anthropic Claude Models:")
            print("• claude-3-7-sonnet-20250219")
            print("• claude-3-5-sonnet-latest")
            print("• claude-3-5-haiku-latest")
            print("• claude-3-opus-latest")
            print("\n💡 Note: Anthropic doesn't provide a public models.list() API endpoint.")

        else:
            print(f"❌ Unknown provider: {provider}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error with {provider}: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    get_models_list(sys.argv[1])
PYTHON_EOF
    
    # Run Python script and capture output
    local output_file=$(mktemp /tmp/llm_output_XXXXXX.txt)
    
    # Ensure .env file exists in AMIR_ROOT
    if [[ ! -f "$AMIR_ROOT/.env" ]]; then
        echo "⚠️  Warning: No .env file found at $AMIR_ROOT/.env"
        echo "Create one with your API keys:"
        echo "  GEMINI_API_KEY=your_key_here"
        echo "  OPENAI_API_KEY=your_key_here"
        echo "  DEEPSEEK_API_KEY=your_key_here"
        echo "  GROQ_API_KEY=your_key_here"
        echo "  ANTHROPIC_API_KEY=your_key_here"
    fi
    
    # Run with Python from virtual environment if available
    if [[ -f "$AMIR_ROOT/lib/python/subtitle/.venv/bin/python" ]]; then
        AMIR_ROOT="$AMIR_ROOT" "$AMIR_ROOT/lib/python/subtitle/.venv/bin/python" "$python_script" "$provider" | tee "$output_file"
    else
        AMIR_ROOT="$AMIR_ROOT" python3 "$python_script" "$provider" | tee "$output_file"
    fi
    
    local exit_code=$?
    
    # Export if requested
    if [[ -n "$export_format" && $exit_code -eq 0 ]]; then
        case "$export_format" in
            md)
                local md_file="${provider}_models_$(date +%Y%m%d).md"
                {
                    echo "# ${provider^^} Models List"
                    echo ""
                    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
                    echo ""
                    echo "\`\`\`"
                    cat "$output_file"
                    echo "\`\`\`"
                } > "$md_file"
                echo ""
                echo "✅ Exported to: $md_file"
                ;;
            pdf)
                # Convert to PDF using system tools
                local md_file="${provider}_models_$(date +%Y%m%d).md"
                {
                    echo "# ${provider^^} Models List"
                    echo ""
                    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
                    echo ""
                    echo "\`\`\`"
                    cat "$output_file"
                    echo "\`\`\`"
                } > "$md_file"
                
                # Try to convert with pandoc if available
                if command -v pandoc &> /dev/null; then
                    local pdf_file="${provider}_models_$(date +%Y%m%d).pdf"
                    pandoc "$md_file" -o "$pdf_file" --pdf-engine=xelatex 2>/dev/null || \
                    pandoc "$md_file" -o "$pdf_file" 2>/dev/null
                    
                    if [[ -f "$pdf_file" ]]; then
                        echo ""
                        echo "✅ Exported to: $pdf_file"
                        rm "$md_file"
                    else
                        echo ""
                        echo "⚠️  PDF conversion failed. Markdown saved instead: $md_file"
                    fi
                else
                    echo ""
                    echo "⚠️  pandoc not found. Install with: brew install pandoc"
                    echo "Markdown saved instead: $md_file"
                fi
                ;;
            jpg)
                # Convert to image (requires convert/magick)
                if command -v convert &> /dev/null; then
                    local jpg_file="${provider}_models_$(date +%Y%m%d).jpg"
                    # Create temporary HTML
                    local html_file=$(mktemp /tmp/llm_XXXXXX.html)
                    {
                        echo "<html><body style='font-family: monospace; padding: 20px;'>"
                        echo "<h1>${provider^^} Models</h1>"
                        echo "<pre>$(cat "$output_file")</pre>"
                        echo "</body></html>"
                    } > "$html_file"
                    
                    # Try screenshot (macOS specific)
                    if command -v screencapture &> /dev/null; then
                        echo "⚠️  JPG export requires manual screenshot or wkhtmltoimage"
                        echo "Consider using: amir llm-lists $provider -e md"
                    fi
                else
                    echo "⚠️  Image export not available. Use -e md or -e pdf instead"
                fi
                ;;
            *)
                echo "❌ Unknown export format: $export_format"
                echo "Available: pdf, md, jpg"
                ;;
        esac
    fi
    
    # Cleanup
    rm -f "$python_script" "$output_file"
    
    return $exit_code
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]] || [[ "$ZSH_EVAL_CONTEXT" =~ :file$ ]]; then
    llm_lists "$@"
fi
