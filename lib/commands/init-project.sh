#!/bin/bash

run_init_project() {

    # Constitution central-source config (rule 045 / bootstrap-installer skill).
    # ".agent/constitution" is a symlink to ONE clone shared by every project —
    # never a per-repo submodule (a submodule pins a per-repo SHA and drifts).
    # Override the clone URL with AMIR_CONSTITUTION_URL, or the local clone
    # location with AGENT_CONSTITUTION_DIR. Default URL is HTTPS for
    # portability: anyone cloning a project that uses this can fetch the
    # public constitution without SSH keys on the account.
    local CONSTITUTION_URL="${AMIR_CONSTITUTION_URL:-https://github.com/su6i/agent-constitution.git}"
    local CONSTITUTION_CENTRAL="${AGENT_CONSTITUTION_DIR:-$HOME/@-github/agent-constitution}"
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
        UPDATE)   echo "   Mode    : 🔄 Update existing constitution link" ;;
    esac
    echo ""

    # ── 1b. Guard: never nest a NEW project inside another git repo ─────────────
    # Creating a repo inside another corrupts submodules and lets `uv init` hijack
    # the parent's pyproject.toml as a workspace. This is the #1 init footgun.
    if [[ "$MODE" == "NEW" ]]; then
        local parent_dir; parent_dir="$(dirname "$TARGET_DIR")"
        if git -C "$parent_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
            local enclosing; enclosing="$(git -C "$parent_dir" rev-parse --show-toplevel 2>/dev/null)"
            echo "   🚫 Refusing to create a project INSIDE an existing git repo:"
            echo "        enclosing repo : $enclosing"
            echo "        would create   : $TARGET_DIR"
            echo "      cd to a location outside that repo and re-run, or set"
            echo "      AMIR_ALLOW_NESTED=1 to override deliberately."
            if [[ "${AMIR_ALLOW_NESTED:-0}" != "1" ]]; then
                return 1
            fi
            echo "   ⚠️  AMIR_ALLOW_NESTED=1 — proceeding despite nesting."
        fi
    fi

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

    # ── 3. Link agent-constitution from the central clone (no submodule) ───────
    # Single source of truth (rule 045): one clone on disk, symlinked into every
    # project. Idempotent for all three modes — NEW/SCAFFOLD get the link for
    # the first time, UPDATE re-pulls the central clone and re-links (a no-op
    # if already current). Never `git submodule` — see bootstrap-installer skill.
    echo "📦 Linking agent-constitution (central clone, symlink)..."
    mkdir -p ".agent"

    if [[ -d "$CONSTITUTION_CENTRAL/.git" ]]; then
        git -C "$CONSTITUTION_CENTRAL" pull --ff-only >/dev/null 2>&1 && \
            echo "   ✅ Central clone up to date ($CONSTITUTION_CENTRAL)" || \
            echo "   ⚠️  Could not pull $CONSTITUTION_CENTRAL (offline/no access?) — using local copy as-is"
    else
        git clone "$CONSTITUTION_URL" "$CONSTITUTION_CENTRAL" 2>/dev/null && \
            echo "   ✅ Cloned constitution → $CONSTITUTION_CENTRAL" || {
            echo "   ❌ git clone failed for $CONSTITUTION_URL"
            echo "      Check network/SSH access, or set AGENT_CONSTITUTION_DIR to an existing local clone."
            return 1
        }
    fi

    ln -sfn "$CONSTITUTION_CENTRAL" "$CONSTITUTION_PATH"
    echo "   ✅ ${CONSTITUTION_PATH} → ${CONSTITUTION_CENTRAL} (symlink)"

    # ── 4. Local rules placeholder ─────────────────────────────────────────────
    if [[ ! -d ".agent/local-rules" ]]; then
        mkdir -p ".agent/local-rules"
        echo "   ➕ .agent/local-rules/ (project-specific overrides)"
    fi

    # ── 5. Detect stack ────────────────────────────────────────────────────────
    # STACK_KIND drives both the CLAUDE.md hints and the language setup below.
    local STACK_KIND="unknown"
    local STACK="<!-- e.g. Python 3.12, FastAPI, PostgreSQL -->"
    local SKILLS_HINT="<!-- e.g. python-core-standards, fastapi-best-practices -->"

    if [[ -f "pyproject.toml" || -f "requirements.txt" || -f "setup.py" ]]; then
        STACK_KIND="python"; STACK="Python"
        SKILLS_HINT="python-core-standards, python-containerization"
    elif [[ -f "package.json" ]]; then
        STACK_KIND="node"; STACK="Node.js / TypeScript"
        SKILLS_HINT="js-ts-code-quality, modern-web-ui"
    elif [[ -f "go.mod" ]]; then
        STACK_KIND="go"; STACK="Go"
        SKILLS_HINT="github-code-quality, ops-automation"
    elif [[ -f "Cargo.toml" ]]; then
        STACK_KIND="rust"; STACK="Rust"
        SKILLS_HINT="github-code-quality, ops-automation"
    fi

    # ── 5b. Language setup (Python default) ─────────────────────────────────────
    # Python or unspecified projects get a uv-managed pyproject.toml + pinned
    # interpreter. --no-readme / --vcs none keep uv from clobbering the README
    # and .gitignore we generate ourselves below.
    if [[ "$STACK_KIND" == "python" || "$STACK_KIND" == "unknown" ]]; then
        if [[ ! -f "pyproject.toml" ]]; then
            if command -v uv >/dev/null 2>&1; then
                echo "🐍 Python setup (uv)..."
                # --no-workspace: never attach to / mutate a parent uv project's
                # pyproject.toml (the workspace-hijack footgun).
                if uv init --no-readme --vcs none --no-workspace >/dev/null 2>&1; then
                    STACK_KIND="python"; STACK="Python (uv)"
                    [[ "$SKILLS_HINT" == "<!--"* ]] && SKILLS_HINT="python-core-standards, python-containerization"
                    echo "   ✅ uv init → pyproject.toml + .python-version"
                else
                    echo "   ⚠️  uv init failed — skipping Python scaffold"
                fi
            else
                echo "   ⚠️  uv not found — skipping pyproject.toml (install: https://docs.astral.sh/uv/)"
            fi
        else
            echo "   🔸 pyproject.toml exists, skipping uv init"
        fi
    fi

    # ── 5c. Resolve vault workspace (rule 035) ───────────────────────────────────
    # Computed here (before CLAUDE.md is generated) so CLAUDE.md can point at the
    # real path; reused by section 8 below to actually write SESSION.md.
    local PROJECT_SLUG
    if [[ -n "${AGENT_PROJECT_SLUG:-}" ]]; then
        PROJECT_SLUG="${AGENT_PROJECT_SLUG}"
    else
        local remote_url; remote_url="$(git remote get-url origin 2>/dev/null)"
        if [[ -n "$remote_url" ]]; then
            PROJECT_SLUG="${remote_url##*/}"; PROJECT_SLUG="${PROJECT_SLUG%.git}"
        else
            PROJECT_SLUG="$PROJECT_NAME"
        fi
    fi
    PROJECT_SLUG="$(printf '%s' "$PROJECT_SLUG" | tr '[:upper:]' '[:lower:]')"
    local VAULT_BASE="${XDG_DATA_HOME:-$HOME/.local/share}/agent-projects"
    local VAULT_WORKSPACE="$VAULT_BASE/$PROJECT_SLUG/workspace"

    # ── 6. Generate CLAUDE.md ──────────────────────────────────────────────────
    if [[ ! -f "CLAUDE.md" ]]; then
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
- Storage : persistent data/artifacts live in the rule-035 vault
            (\`~/.local/share/agent-projects/${PROJECT_SLUG}/data/\`), never in
            the repo. A local \`.storage/\` is scratch only and is git-ignored.

## First Session (do this before any feature work)
This project is freshly scaffolded — \`CLAUDE.md\`, \`README.md\`, and \`.env.example\`
still contain TODO placeholders. Follow
\`.agent/constitution/workflows/first-session.md\` to fill them in. Tasks live
ONLY in the central \`_memory/TODO.md\` under \`## ${PROJECT_NAME}\` (rule 050) —
never a repo TODO, never a per-project vault TODO (rules 035/040/045/050).

## Rules & Workflows
- Rules     : \`.agent/constitution/rules/\` — read 000-core.md, global.md, 040-git.md before every task
- Local     : \`.agent/local-rules/\` — project-specific overrides (take precedence over constitution)
- Workflows : \`.agent/constitution/workflows/\` — pick the relevant one per task type
- Skills    : \`.agent/constitution/skills/\` — domain knowledge modules

## Updating the constitution
\`.agent/constitution\` is a symlink to one central clone shared by every project — no submodule.
\`\`\`bash
git -C ~/@-github/agent-constitution pull --ff-only
\`\`\`

## Global Rules
Git protocol, cost control, and code quality are in ~/.claude/CLAUDE.md (auto-loaded).
CLAUDEOF
        echo "   ✅ CLAUDE.md (fill in the TODOs)"
    else
        echo "   🔸 CLAUDE.md already exists, skipping"
    fi

    # ── 7. Standard directories (+ .gitkeep so git tracks them) ─────────────────
    # No lib/ — generic .gitignore patterns hide it; source goes under src/.
    # No .storage/ — persistent data lives in the rule-035 vault data/ dir;
    # .storage/ stays git-ignored as scratch only.
    echo "🏗️  Creating standard directories..."
    for dir in src tests docs assets; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"; echo "   ➕ $dir/"
        else
            echo "   🔸 $dir/ exists"
        fi
        # git does not track empty dirs — keep them with .gitkeep
        [[ -z "$(ls -A "$dir" 2>/dev/null)" ]] && touch "$dir/.gitkeep"
    done
    [[ -d ".agent/local-rules" && -z "$(ls -A .agent/local-rules 2>/dev/null)" ]] && touch ".agent/local-rules/.gitkeep"

    # ── 8. Vault workspace files (SESSION.md — rules 035/040/045/050) ──────────
    # Work-log files are never committed and must never even live in the repo
    # working tree (035's golden rule: .gitignore alone doesn't survive a
    # merge). They belong in the central vault's workspace/ dir.
    echo "📝 Creating vault workspace files..."

    # Prefer the constitution's own scaffolder (creates the full vault: data/
    # shared/references/secrets/workspace, with secrets/ chmod 700) — fall
    # back to a bare mkdir if it's unavailable for any reason (fail-open).
    if [[ -x "$CONSTITUTION_PATH/bin/scaffold-vault.sh" ]]; then
        "$CONSTITUTION_PATH/bin/scaffold-vault.sh" "$PROJECT_SLUG" >/dev/null 2>&1
    fi
    mkdir -p "$VAULT_WORKSPACE"

    # Tasks: NEVER a per-project TODO.md (rule 050) — one central file only.
    echo "   📌 Tasks: add a '## ${PROJECT_NAME}' section in the central _memory/TODO.md (rule 050) — no per-project TODO.md"

    # SESSION.md — running session log.
    if [[ ! -f "$VAULT_WORKSPACE/SESSION.md" ]]; then
        printf '# SESSION — %s\n\n_Running log of what happened each session._\n' "$PROJECT_NAME" > "$VAULT_WORKSPACE/SESSION.md"
        echo "   ✅ SESSION.md → $VAULT_WORKSPACE/SESSION.md"
    else
        echo "   🔸 SESSION.md already exists in vault workspace"
    fi

    echo "   📌 Work log lives outside the repo: $VAULT_WORKSPACE  (rules 035/040/045)"

    # README.md — human-facing entry point.
    if [[ ! -f "README.md" ]]; then
        local QUICKSTART="# TODO: real setup/run commands"
        [[ "$STACK_KIND" == "python" ]] && QUICKSTART=$'uv sync\nuv run python main.py'
        cat > "README.md" << READMEEOF
# ${PROJECT_NAME}

<!-- TODO: one-line description of what this project does -->

## Quickstart
\`\`\`bash
${QUICKSTART}
\`\`\`

## Documentation
- Agent guide: [CLAUDE.md](CLAUDE.md)
- Constitution (rules / workflows / skills): \`.agent/constitution/\`
READMEEOF
        echo "   ✅ README.md"
    else
        echo "   🔸 README.md already exists"
    fi

    # .env.example — placeholder env vars (never real secrets).
    if [[ ! -f ".env.example" ]]; then
        cat > ".env.example" << 'ENVEOF'
# Copy to .env and fill in real values. .env is git-ignored; .env.example is committed.
# TODO: list every variable the project needs. Examples:
# OPENAI_API_KEY=sk-...
# DATABASE_URL=postgresql://user:pass@localhost:5432/db
ENVEOF
        echo "   ✅ .env.example"
    else
        echo "   🔸 .env.example already exists"
    fi

    # ── 9. .gitignore ───────────────────────────────────────────────────────────
    # Seed from the curated constitution template (or a safe fallback), then
    # ALWAYS enforce the critical rules. This is the fix for data/secrets that
    # previously slipped through when a template was copied verbatim.
    local GITIGNORE_TEMPLATE="$CONSTITUTION_PATH/templates/gitignore.template"
    if [[ ! -f ".gitignore" ]]; then
        if [[ -f "$GITIGNORE_TEMPLATE" ]]; then
            cp "$GITIGNORE_TEMPLATE" ".gitignore"
            echo "   ✅ .gitignore from constitution template"
        else
            printf '# Minimal fallback — constitution template not found\n.storage/\n.env\n.env.*\n!.env.example\n.venv/\n__pycache__/\n*.py[cod]\n.DS_Store\n' > ".gitignore"
            echo "   ✅ .gitignore (minimal fallback)"
        fi
    else
        echo "   🔸 .gitignore exists"
    fi
    # Enforce critical rules regardless of how .gitignore got here.
    # ".agent/constitution" is the symlink to the central clone (section 3) —
    # it must never be staged as a repo entry; only .agent/local-rules is ours.
    local added=0
    for rule in ".storage/" ".env" ".venv/" "__pycache__/" ".DS_Store" ".agent/constitution" "TODO.md" "SESSION.md"; do
        if ! grep -qxF "$rule" ".gitignore" 2>/dev/null; then
            echo "$rule" >> ".gitignore"; added=1
        fi
    done
    [[ "$added" == 1 ]] && echo "   ➕ Ensured critical ignore rules"

    # ── 9b. Install the constitution git hooks ──────────────────────────────────
    # Deterministic enforcement (no commits to main, docs checklist, and no AI
    # co-authorship), so the rules can't be forgotten. Bypass: git commit --no-verify
    if [[ -d ".git" ]]; then
        mkdir -p ".git/hooks"
        local _hook _src
        for _hook in pre-commit commit-msg; do
            _src="$CONSTITUTION_PATH/templates/hooks/$_hook"
            if [[ -f "$_src" ]]; then
                cp "$_src" ".git/hooks/$_hook" && chmod +x ".git/hooks/$_hook"
                echo "   ✅ $_hook hook installed (.git/hooks/$_hook)"
            else
                echo "   ⚠️  $_hook hook template not found in constitution clone — skipped"
            fi
        done
    fi

    # ── 10. Git stage ───────────────────────────────────────────────────────────
    # No .gitmodules (no submodule), no TODO.md/SESSION.md (vault-only, and now
    # gitignored above). `git add .agent` only picks up local-rules/ — the
    # constitution symlink is excluded by the .gitignore rule from section 9.
    echo "💾 Staging..."
    git add .agent CLAUDE.md README.md .env.example .gitignore \
            src tests docs assets \
            pyproject.toml .python-version main.py 2>/dev/null
    echo "   ✅ Staged"

    echo ""
    echo "🎉 Done! ${PROJECT_NAME} is now agent-governed."
    echo "   Constitution : ${CONSTITUTION_PATH}/ (symlink → $CONSTITUTION_CENTRAL, $(git -C "$CONSTITUTION_PATH" describe --tags --always 2>/dev/null || echo 'latest'))"
    echo "   Update later : git -C $CONSTITUTION_CENTRAL pull --ff-only"
    echo "   Work log     : $VAULT_WORKSPACE/SESSION.md  (never in this repo)"
    echo "   Tasks        : central _memory/TODO.md → section '## ${PROJECT_NAME}' (rule 050)"
    echo "   ▶ Next       : follow .agent/constitution/workflows/first-session.md"
    echo ""
}
