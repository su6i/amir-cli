#!/bin/bash

run_init_project() {
    # 1. Determine Paths
    # We want to link to the LIVE constitution repo.
    # Logic: Check Env Var -> Check Sibling Directory -> Error
    
    local LIVE_SOURCE=""
    
    # Check 1: AMIR_CONSTITUTION_PATH env var
    if [[ -n "$AMIR_CONSTITUTION_PATH" && -d "$AMIR_CONSTITUTION_PATH" ]]; then
        LIVE_SOURCE="$AMIR_CONSTITUTION_PATH"
    fi
    
    # Check 2: Sibling directory (assuming amir-cli and agent-constitution are in the same folder)
    if [[ -z "$LIVE_SOURCE" ]]; then
        local SIBLING="$SCRIPT_DIR/../agent-constitution"
        if [[ -d "$SIBLING" ]]; then
            LIVE_SOURCE="$(cd "$SIBLING" && pwd)"
        fi
    fi

    if [[ -z "$LIVE_SOURCE" ]]; then
        echo "❌ Error: Could not locate 'agent-constitution' repository."
        echo "   Checked: \$AMIR_CONSTITUTION_PATH and ../agent-constitution"
        return 1
    fi
    
    local SOURCE_ROOT="$LIVE_SOURCE"
    
    local TARGET_DIR=""
    local MODE=""

    if [[ -n "$1" ]]; then
        TARGET_DIR="$1"
        if [[ "$TARGET_DIR" == "." || "$TARGET_DIR" == "./" ]]; then
            MODE="UPDATE"
        else
            MODE="NEW"
        fi
    else
        TARGET_DIR="sample-project"
        MODE="DEFAULT"
    fi

    echo "⚡ Initiating Agent Constitution Injection..."
    echo "📍 Source Constitution: $SOURCE_ROOT"
    
    if [[ "$MODE" == "UPDATE" ]]; then
        echo "🔄 Mode: Update/Scaffold Current Directory"
        echo "🎯 Target: $(pwd)"
    else
        echo "✨ Mode: New Project"
        echo "🎯 Target: $TARGET_DIR"
    fi

    # 2. Safety Checks & Creation
    if [ ! -d "$TARGET_DIR" ]; then
        echo "📂 Creating new project directory: $TARGET_DIR"
        mkdir -p "$TARGET_DIR"
    fi

    if [ ! -d "$TARGET_DIR/.git" ]; then
        echo "⚠️  Warning: Target is not a git repository. Proceeding anyway..."
    fi

    # 3. Copy Protocol Artifacts
    echo "📂 Copying protocols..."

    # Function to copy with backup
    safe_copy() {
        local src="$1"
        local dst="$2"
        
        # Ensure parent dir exists
        mkdir -p "$(dirname "$dst")"

        if [ -e "$dst" ]; then
            echo "   🔸 Backing up existing $(basename "$dst")..."
            mv "$dst" "$dst.bak"
        fi
        
        if [ -e "$src" ]; then
            cp -R "$src" "$dst"
            echo "   ✅ Installed $(basename "$src")"
        else
            echo "   ⚠️  Source not found: $(basename "$src")"
        fi
    }

    # New Path Mappings based on user request:
    # Source .cursor/rules -> Target .cursor/rules
    # Source .cursor/workflows -> Target .cursor/workflows
    # Source .cursor/prompts -> Target .cursor/prompts
    
    mkdir -p "$TARGET_DIR/.cursor"
    
    # Note: Adjusting source paths based on expected Agent Constitution structure.
    # Assuming the LIVE source has .cursor/rules, .cursor/workflows, etc.
    # If source structure is flat (older version), we might need fallback, but relying on user's structure.
    
    safe_copy "$SOURCE_ROOT/.cursor/rules" "$TARGET_DIR/.cursor/rules"
    safe_copy "$SOURCE_ROOT/.cursor/workflows" "$TARGET_DIR/.cursor/workflows"
    safe_copy "$SOURCE_ROOT/.cursor/prompts" "$TARGET_DIR/.cursor/prompts"

    # 4. Scaffold Standard Directories
    echo "🏗️  Creating standard directory structure..."
    DIRS=(
        "src"
        "tests"
        "docs"
        "assets"
        "lib"
        ".storage/temp"
        ".storage/data"
    )

    for dir in "${DIRS[@]}"; do
        TARGET_PATH="$TARGET_DIR/$dir"
        if [ ! -d "$TARGET_PATH" ]; then
            mkdir -p "$TARGET_PATH"
            echo "   ➕ Created $dir/"
        else
            echo "   🔸 Exists $dir/"
        fi
    done
    
    # Copy generic assets from Amir CLI itself (not Constitution repo)
    # LIB_DIR is .../lib, so assets are at .../assets
    LOCAL_ASSETS="$LIB_DIR/../assets"
    if [[ -f "$LOCAL_ASSETS/linkedin_su6i.svg" ]]; then
        safe_copy "$LOCAL_ASSETS/linkedin_su6i.svg" "$TARGET_DIR/assets/linkedin_su6i.svg"
    fi

    # 5. Standardize .gitignore (Append if missing)
    GITIGNORE="$TARGET_DIR/.gitignore"
    if [ ! -f "$GITIGNORE" ]; then
        touch "$GITIGNORE"
    fi

    # Minimal critical ignores
    IGNORES=(
        ".storage/"
        "prompts/gen_*.txt"
        "prompts/task_*.txt"
        ".DS_Store"
    )

    echo "🛡️  updating .gitignore..."
    for rule in "${IGNORES[@]}"; do
        if ! grep -qF "$rule" "$GITIGNORE"; then
            echo "$rule" >> "$GITIGNORE"
            echo "   ➕ Added $rule"
        fi
    done

    # 6. Git Add
    if [ -d "$TARGET_DIR/.git" ]; then
        echo "💾 Staging changes..."
        local CURRENT_PWD=$(pwd)
        cd "$TARGET_DIR" || return 1
        
        if command -v git &> /dev/null; then
            git add .cursor/ .gitignore src/ tests/ docs/ assets/ lib/
            echo "   ✅ Files flagged for commit."
        else
             echo "⚠️  Git not found, skipping stage."
        fi
        cd "$CURRENT_PWD"
    else
        echo "ℹ️  Skipped git add (not a repo)."
    fi

    echo "🎉 Constitution Installed! This project is now Agent-Governed."
}
