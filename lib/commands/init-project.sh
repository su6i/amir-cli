#!/bin/bash

run_init_project() {

    # Constitution submodule config (override URL with AMIR_CONSTITUTION_URL)
    local CONSTITUTION_URL="${AMIR_CONSTITUTION_URL:-git@github.com:su6i/agent-constitution.git}"
    local CONSTITUTION_PATH=".agent/constitution"

    # ── 1. Determine target & mode ─────────────────────────────────────────────
    local TARGET_DIR="${1:-.}"
    [[ "$TARGET_DIR" == "." || "$TARGET_DIR" == "./" ]] && TARGET_DIR="$(pwd)"
    TARGET_DIR="$(cd "$(dirname "$TARGET_DIR")" 2>/dev/null && pwd)/$(basename "$TARGET_DIR")" || TARGET_DIR="$(pwd)/$1"

    local PROJECT_NAME
    PROJECT_NAME="$(basename "$TARGET_DIR")"

    local MODE
    if [[ ! -d "$TARGET_DIR" ]]; then
        MODE="NEW"
    elif [[ ! -d "$TARGET_DIR/.agent" ]]; then
        MODE="SCAFFOLD"
    else
        MODE="UPDATE"
    fi

    echo ""
    echo "⚡ amir init-project"
    echo "   Constitution : $CONSTITUTION_URL"
    echo "   Target       : $TARGET_DIR"
    case "$MODE" in
        NEW)      echo "   Mode    : ✨ New project (will create dir + git init)" ;;
        SCAFFOLD) echo "   Mode    : 🏗  Scaffold existing project (first time)" ;;
        UPDATE)   echo "   Mode    : 🔄 Update existing constitution submodule" ;;
    esac
    echo ""

    # ── 2. Create dir + git init ───────────────────────────────────────────────
    if [[ "$MODE" == "NEW" ]]; then
        mkdir -p "$TARGET_DIR"
        echo "   ➕ Created $PROJECT_NAME/"
        cd "$TARGET_DIR" || return 1
        git init -q
        echo "   ✅ git init"
    else
        cd "$TARGET_DIR" || return 1
        if [[ ! -d ".git" ]]; then
            echo "   ⚠️  Not a git repo — running git init..."
            git init -q
            echo "   ✅ git init"
        fi
    fi

    # ── 3. Add agent-constitution as submodule ─────────────────────────────────
    echo "📦 Setting up agent-constitution submodule..."
    mkdir -p ".agent"

    local submodule_exists=false
    if [[ -f ".gitmodules" ]] && grep -qF "$CONSTITUTION_PATH" ".gitmodules" 2>/dev/null; then
        submodule_exists=true
    fi

    if $submodule_exists; then
        echo "   🔸 Submodule already registered"
        if [[ "$MODE" == "UPDATE" ]]; then
            git submodule update --remote --merge "$CONSTITUTION_PATH" 2>/dev/null && \
                echo "   ✅ Submodule updated to latest" || \
                echo "   ⚠️  Update failed — run: git submodule update --remote $CONSTITUTION_PATH"
        fi
    else
        git submodule add "$CONSTITUTION_URL" "$CONSTITUTION_PATH" 2>/dev/null && \
            echo "   ✅ Submodule added ($CONSTITUTION_URL)" || {
            echo "   ❌ git submodule add failed."
            echo "      Check SSH access: ssh -T git@github.com"
            return 1
        }
    fi

    # ── 4. Local rules placeholder ─────────────────────────────────────────────
    if [[ ! -d ".agent/local-rules" ]]; then
        mkdir -p ".agent/local-rules"
        echo "   ➕ .agent/local-rules/ (project-specific overrides)"
    fi

    # ── 5. Generate CLAUDE.md ──────────────────────────────────────────────────
    if [[ ! -f "CLAUDE.md" ]]; then
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
Read these from \`.agent/constitution/skills/\` before implementing domain-specific logic:
${SKILLS_HINT}

## Key Constraints
<!-- TODO: any project-specific rules -->

## Rules & Workflows
- Rules     : \`.agent/constitution/rules/\` — read 000-core.md, global.md, 040-git.md before every task
- Local     : \`.agent/local-rules/\` — project-specific overrides (take precedence over constitution)
- Workflows : \`.agent/constitution/workflows/\` — pick the relevant one per task type
- Skills    : \`.agent/constitution/skills/\` — domain knowledge modules

## Updating the constitution
\`\`\`bash
git submodule update --remote .agent/constitution
\`\`\`

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
    local GITIGNORE_TEMPLATE="$CONSTITUTION_PATH/templates/gitignore.template"
    if [[ ! -f ".gitignore" ]]; then
        if [[ -f "$GITIGNORE_TEMPLATE" ]]; then
            cp "$GITIGNORE_TEMPLATE" ".gitignore"
            echo "   ✅ .gitignore from template"
        else
            printf ".storage/\n.env\n__pycache__/\n*.pyc\n.venv/\n" > ".gitignore"
            echo "   ✅ .gitignore (minimal fallback)"
        fi
    else
        for rule in ".storage/" ".env" "__pycache__/"; do
            grep -qF "$rule" ".gitignore" || echo "$rule" >> ".gitignore"
        done
        echo "   🔸 .gitignore exists, critical rules verified"
    fi

    # ── 8. Git stage ───────────────────────────────────────────────────────────
    echo "💾 Staging..."
    git add .gitmodules .agent/ CLAUDE.md .gitignore src/ tests/ docs/ assets/ lib/ 2>/dev/null
    echo "   ✅ Staged"

    echo ""
    echo "🎉 Done! ${PROJECT_NAME} is now agent-governed."
    echo "   Constitution : ${CONSTITUTION_PATH}/ (submodule — $(git -C "$CONSTITUTION_PATH" describe --tags --always 2>/dev/null || echo 'latest'))"
    echo "   Update later : git submodule update --remote ${CONSTITUTION_PATH}"
    if grep -q "TODO" "CLAUDE.md" 2>/dev/null; then
        echo "   ✏️  Open CLAUDE.md and fill in the TODOs before your first session."
    fi
    echo ""
}
