#!/bin/bash

run_init_project() {

    # ── 1. Locate agent-constitution repo ─────────────────────────────────────
    local SOURCE_ROOT=""

    if [[ -n "$AMIR_CONSTITUTION_PATH" && -d "$AMIR_CONSTITUTION_PATH" ]]; then
        SOURCE_ROOT="$AMIR_CONSTITUTION_PATH"
    else
        local SIBLING="$SCRIPT_DIR/../agent-constitution"
        [[ -d "$SIBLING" ]] && SOURCE_ROOT="$(cd "$SIBLING" && pwd)"
    fi

    if [[ -z "$SOURCE_ROOT" ]]; then
        echo "❌ Could not locate 'agent-constitution' repository."
        echo "   Set AMIR_CONSTITUTION_PATH or place it alongside amir-cli."
        return 1
    fi

    # ── 2. Determine target & mode ─────────────────────────────────────────────
    local TARGET_DIR="${1:-.}"
    [[ "$TARGET_DIR" == "." || "$TARGET_DIR" == "./" ]] && TARGET_DIR="$(pwd)"
    TARGET_DIR="$(cd "$(dirname "$TARGET_DIR")" 2>/dev/null && pwd)/$(basename "$TARGET_DIR")" || TARGET_DIR="$(pwd)/$1"

    local PROJECT_NAME
    PROJECT_NAME="$(basename "$TARGET_DIR")"

    # Detect mode
    local MODE
    if [[ ! -d "$TARGET_DIR" ]]; then
        MODE="NEW"              # directory doesn't exist → brand new project
    elif [[ ! -d "$TARGET_DIR/.agent" ]]; then
        MODE="SCAFFOLD"         # dir exists, no .agent yet → existing project, first time
    else
        MODE="UPDATE"           # .agent already there → refresh/update
    fi

    echo ""
    echo "⚡ amir init-project"
    echo "   Source  : $SOURCE_ROOT"
    echo "   Target  : $TARGET_DIR"
    case "$MODE" in
        NEW)      echo "   Mode    : ✨ New project (will create dir + git init)" ;;
        SCAFFOLD) echo "   Mode    : 🏗  Scaffold existing project (first time)" ;;
        UPDATE)   echo "   Mode    : 🔄 Update existing constitution" ;;
    esac
    echo ""

    # ── 3. Create dir + git init for new projects ──────────────────────────────
    if [[ "$MODE" == "NEW" ]]; then
        mkdir -p "$TARGET_DIR"
        echo "   ➕ Created $PROJECT_NAME/"
        cd "$TARGET_DIR" || return 1
        git init -q
        echo "   ✅ git init"
    else
        cd "$TARGET_DIR" || return 1
        if [[ ! -d ".git" ]]; then
            echo "   ⚠️  Not a git repo. Running git init..."
            git init -q
            echo "   ✅ git init"
        fi
    fi

    # ── 4. Copy constitution artifacts ────────────────────────────────────────
    echo "📂 Installing constitution..."

    _copy() {
        local src="$1" dst="$2"
        mkdir -p "$(dirname "$dst")"
        [[ -e "$dst" ]] && mv "$dst" "$dst.bak"
        [[ -e "$src" ]] && cp -R "$src" "$dst" && echo "   ✅ $(basename "$dst")" || echo "   ⚠️  Not found: $(basename "$src")"
    }

    # Rules (always full copy)
    mkdir -p ".agent/rules"
    for f in "$SOURCE_ROOT/.agent/rules/"*; do
        [[ -f "$f" ]] && _copy "$f" ".agent/rules/$(basename "$f")"
    done

    # Workflows (essential only)
    mkdir -p ".agent/workflows"
    for wf in init-project.md documentation.md ai-optimization.md quality-assurance.md communication.md; do
        [[ -f "$SOURCE_ROOT/.agent/workflows/$wf" ]] && _copy "$SOURCE_ROOT/.agent/workflows/$wf" ".agent/workflows/$wf"
    done

    # Skills (full library)
    _copy "$SOURCE_ROOT/.agent/skills" ".agent/skills"

    # ── 5. Generate CLAUDE.md ─────────────────────────────────────────────────
    if [[ ! -f "CLAUDE.md" ]]; then
        # Auto-detect tech stack
        local STACK="<!-- e.g. Python 3.12, FastAPI, PostgreSQL -->"
        local SKILLS_HINT="<!-- e.g. python-core-standards, fastapi-best-practices -->"

        if [[ -f "pyproject.toml" || -f "requirements.txt" || -f "setup.py" ]]; then
            STACK="Python"
            SKILLS_HINT="python-core-standards, python-containerization"
        elif [[ -f "package.json" ]]; then
            STACK="Node.js / TypeScript"
            SKILLS_HINT="js-ts-code-quality, modern-web-ui"
        elif [[ -f "go.mod" ]]; then
            STACK="Go"
            SKILLS_HINT="github-code-quality, ops-automation"
        elif [[ -f "Cargo.toml" ]]; then
            STACK="Rust"
            SKILLS_HINT="github-code-quality, ops-automation"
        fi

        cat > "CLAUDE.md" << CLAUDEOF
# CLAUDE.md — ${PROJECT_NAME}

## Project
<!-- TODO: describe what this project does in 1-2 sentences -->

## Tech Stack
${STACK}

## Relevant Skills
Read these from \`.agent/skills/\` before implementing domain-specific logic:
${SKILLS_HINT}

## Key Constraints
<!-- TODO: any project-specific rules -->

## Rules & Workflows
- Rules     : \`.agent/rules/\` — read 000-core.md, global.md, 040-git.md before every task
- Workflows : \`.agent/workflows/\` — pick the relevant one per task type
- Skills    : \`.agent/skills/\` — 75 domain knowledge modules

## Global Rules
Git protocol, cost control, and code quality are in ~/.claude/CLAUDE.md (auto-loaded).
CLAUDEOF
        echo "   ✅ CLAUDE.md (fill in the TODOs)"
    else
        echo "   🔸 CLAUDE.md already exists, skipping"
    fi

    # ── 6. Standard directories ────────────────────────────────────────────────
    echo "🏗️  Creating standard directories..."
    for dir in src tests docs assets lib .storage/temp .storage/data; do
        [[ ! -d "$dir" ]] && mkdir -p "$dir" && echo "   ➕ $dir/" || echo "   🔸 $dir/ exists"
    done

    # ── 7. .gitignore ──────────────────────────────────────────────────────────
    local GITIGNORE_TEMPLATE="$SOURCE_ROOT/templates/gitignore.template"
    if [[ ! -f ".gitignore" ]]; then
        if [[ -f "$GITIGNORE_TEMPLATE" ]]; then
            cp "$GITIGNORE_TEMPLATE" ".gitignore"
            echo "   ✅ .gitignore from template"
        else
            printf ".storage/\n.env\n__pycache__/\n*.pyc\n.venv/\n" > ".gitignore"
            echo "   ✅ .gitignore (minimal fallback)"
        fi
    else
        # Ensure critical ignores are present
        for rule in ".storage/" ".env" "__pycache__/"; do
            grep -qF "$rule" ".gitignore" || echo "$rule" >> ".gitignore"
        done
        echo "   🔸 .gitignore exists, critical rules verified"
    fi

    # ── 8. Git stage ───────────────────────────────────────────────────────────
    echo "💾 Staging..."
    git add .agent/ CLAUDE.md .gitignore src/ tests/ docs/ assets/ lib/ 2>/dev/null
    echo "   ✅ Staged"

    echo ""
    echo "🎉 Done! ${PROJECT_NAME} is now agent-governed."
    if grep -q "TODO" "CLAUDE.md" 2>/dev/null; then
        echo "   ✏️  Open CLAUDE.md and fill in the TODOs before your first session."
    fi
    echo ""
}
