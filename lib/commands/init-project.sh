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

    # 3. Intelligent File Copy (Selective)
    echo "📂 Copying essential protocols..."

    # Function to copy specific files safely
    copy_file() {
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
            echo "   ✅ Installed $(basename "$dst")"
        else
            echo "   ⚠️  Source not found: $(basename "$src")"
        fi
    }

    # Create target structure
    mkdir -p "$TARGET_DIR/.cursor/rules"
    mkdir -p "$TARGET_DIR/.cursor/workflows"
    
    # --- SELECTIVE COPY LOGIC ---
    
    # Rules: Copy specific rules, rename global.mdc.md -> global.mdc if needed
    # We explicitly look for the correct file at source
    
    # Global Constitution
    if [[ -f "$SOURCE_ROOT/.cursor/rules/global.mdc" ]]; then
         copy_file "$SOURCE_ROOT/.cursor/rules/global.mdc" "$TARGET_DIR/.cursor/rules/global.mdc"
    elif [[ -f "$SOURCE_ROOT/.cursor/rules/global.mdc.md" ]]; then
         # Fix double extension on copy
         copy_file "$SOURCE_ROOT/.cursor/rules/global.mdc.md" "$TARGET_DIR/.cursor/rules/global.mdc"
    fi

    # Workflows: Copy essential workflows ONLY (avoid copying unrelated agent prompts)
    # Define the whitelist of workflows to copy
    ESSENTIAL_WORKFLOWS=(
        "init-project.md"
        "documentation.md"
        "ai-optimization.md"
        "quality-assurance.md"
        "social-media-showcase.md"
    )

    for wf in "${ESSENTIAL_WORKFLOWS[@]}"; do
        if [[ -f "$SOURCE_ROOT/.cursor/workflows/$wf" ]]; then
             copy_file "$SOURCE_ROOT/.cursor/workflows/$wf" "$TARGET_DIR/.cursor/workflows/$wf"
        fi
    done

    # Skills: Copy ALL skills
    if [[ -d "$SOURCE_ROOT/.cursor/skills" ]]; then
         copy_file "$SOURCE_ROOT/.cursor/skills" "$TARGET_DIR/.cursor/skills"
    fi

    # 4. Scaffold Standard Directories
    echo "🏗️  Creating standard directory structure..."
    DIRS=(
        "src"
        "tests"
        "docs"
        "assets"
        "lib"
        "Roadmap"  # Added Roadmap
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
    LOCAL_ASSETS="$LIB_DIR/../assets"
    if [[ -f "$LOCAL_ASSETS/linkedin_su6i.svg" ]]; then
        copy_file "$LOCAL_ASSETS/linkedin_su6i.svg" "$TARGET_DIR/assets/linkedin_su6i.svg"
    fi

    # 5. .gitignore Standard (Copy from Template)
    GITIGNORE_TEMPLATE="$SOURCE_ROOT/templates/gitignore.template"
    TARGET_GITIGNORE="$TARGET_DIR/.gitignore"
    
    if [[ -f "$GITIGNORE_TEMPLATE" ]]; then
        echo "🛡️  Installing standard .gitignore from template..."
        if [[ "$MODE" == "NEW" || ! -f "$TARGET_GITIGNORE" ]]; then
            copy_file "$GITIGNORE_TEMPLATE" "$TARGET_GITIGNORE"
        else
            echo "   🛡️  Appending project rules to existing .gitignore..."
            # For updates, we just ensure critical ignores are there
            # Since gitignore is now a template, we can also choose to overwrite or append
            # Adding Roadmap/ as a project specific rule just in case
            if ! grep -qF "Roadmap/" "$TARGET_GITIGNORE"; then
                echo -e "\n# Project Specific\nRoadmap/" >> "$TARGET_GITIGNORE"
                echo "   ➕ Added Roadmap/"
            fi
        fi
    else
        echo "   ⚠️  Warning: gitignore.template not found at $GITIGNORE_TEMPLATE"
        # Fallback to minimal if template missing
        if [[ ! -f "$TARGET_GITIGNORE" ]]; then
            echo "Roadmap/" > "$TARGET_GITIGNORE"
        fi
    fi

    # 6. Git Add
    if [ -d "$TARGET_DIR/.git" ]; then
        echo "💾 Staging changes..."
        local CURRENT_PWD=$(pwd)
        cd "$TARGET_DIR" || return 1
        
        if command -v git &> /dev/null; then
            git add .cursor/ .gitignore src/ tests/ docs/ assets/ lib/ Roadmap/
            echo "   ✅ Files flagged for commit."
        else
             echo "⚠️  Git not found, skipping stage."
        fi
        cd "$CURRENT_PWD"
    else
        echo "ℹ️  Skipped git add (not a repo)."
    fi

    echo "🎉 Constitution Installed! This project is now strictly Agent-Governed."
    echo "📜 Please review the Workflows in .cursor/workflows/"
}
