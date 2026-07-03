#!/bin/bash

run_sync_constitution() {

    local CONSTITUTION_PATH=".agent/constitution"

    # ── 1. Target ─────────────────────────────────────────────────────────────
    local TARGET_DIR="${1:-.}"
    [[ "$TARGET_DIR" == "." || "$TARGET_DIR" == "./" ]] && TARGET_DIR="$(pwd)"
    TARGET_DIR="$(cd "$TARGET_DIR" 2>/dev/null && pwd)"

    if [[ -z "$TARGET_DIR" || ! -d "$TARGET_DIR" ]]; then
        echo "❌ Target directory not found: $1"
        return 1
    fi

    cd "$TARGET_DIR" || return 1

    echo ""
    echo "🔄 amir sync-constitution"
    echo "   Target : $TARGET_DIR"
    echo ""

    # ── 2. Submodule path (preferred) ─────────────────────────────────────────
    if [[ -f ".gitmodules" ]] && grep -qF "$CONSTITUTION_PATH" ".gitmodules" 2>/dev/null; then
        echo "📦 Updating submodule..."
        git submodule update --remote --merge "$CONSTITUTION_PATH" && \
            echo "   ✅ Constitution updated to latest" || \
            echo "   ❌ Update failed — check SSH access: ssh -T git@github.com"
        local ref
        ref="$(git -C "$CONSTITUTION_PATH" describe --tags --always 2>/dev/null || echo 'unknown')"
        echo "   Version: $ref"
        echo ""
        echo "Review changes:  git diff $CONSTITUTION_PATH"
        echo ""
        return 0
    fi

    # ── 3. Fallback: locate constitution repo for copy-based sync ─────────────
    local SOURCE_ROOT=""
    if [[ -n "${AGENT_CONSTITUTION_PATH:-}" && -d "${AGENT_CONSTITUTION_PATH:-}" ]]; then
        SOURCE_ROOT="$AGENT_CONSTITUTION_PATH"
    else
        local SIBLING="$SCRIPT_DIR/../agent-constitution"
        [[ -d "$SIBLING" ]] && SOURCE_ROOT="$(cd "$SIBLING" && pwd)"
    fi

    if [[ -z "$SOURCE_ROOT" ]]; then
        echo "❌ No submodule found and cannot locate agent-constitution repo."
        echo "   Run 'amir init-project .' to set up the submodule, or"
        echo "   set AGENT_CONSTITUTION_PATH to the repo path."
        return 1
    fi

    echo "   Source : $SOURCE_ROOT (copy-based fallback)"
    echo ""

    # ── 3. Detect legacy agent directories ───────────────────────────────────
    local LEGACY_DIRS=()
    for d in ".agents" ".antigravity" ".cursor"; do
        [[ -d "$d" ]] && LEGACY_DIRS+=("$d")
    done

    # ── 4. Migrate project-specific content from legacy dirs ─────────────────
    # Called only if .agent/ doesn't exist yet
    _migrate_legacy() {
        local legacy_dir="$1"
        local migrated=0

        # Standard rule filenames to skip (already covered by agent-constitution)
        local STANDARD_RULES=("000-core.md" "010-python.md" "020-tdd.md" "030-security.md" "040-git.md" "global.md" "translation_rules.md")

        echo "   🔍 Scanning $legacy_dir/ for project-specific content..."

        while IFS= read -r -d '' f; do
            local rel_path="${f#$legacy_dir/}"
            local basename_f
            basename_f="$(basename "$f")"

            # Skip Persian/non-English versions
            [[ "$basename_f" == *.fa.md ]] && continue
            [[ "$basename_f" == *.fa ]] && continue

            # Skip non-markdown files (PDFs, binaries, etc.)
            [[ "$basename_f" != *.md ]] && continue

            # Skip standard constitution rules
            local is_standard=false
            for std in "${STANDARD_RULES[@]}"; do
                [[ "$basename_f" == "$std" ]] && is_standard=true && break
            done
            $is_standard && echo "   ⏭️  Skipping standard: $rel_path" && continue

            # Skip if already exists in standard skills
            if [[ -f "$SOURCE_ROOT/skills/$basename_f" ]]; then
                echo "   ⏭️  Already in constitution skills: $basename_f"
                continue
            fi

            # Determine destination
            local dst
            if [[ "$rel_path" == skills/* ]]; then
                dst=".agent/skills/$basename_f"
            elif [[ "$basename_f" == "rules.md" ]]; then
                dst=".agent/rules/project-rules.md"
            else
                # instructions/, any other .md → rules
                dst=".agent/rules/$basename_f"
            fi

            if [[ -f "$dst" ]]; then
                echo "   🔸 Already exists, skipping: $dst"
            else
                mkdir -p "$(dirname "$dst")"
                cp -f "$f" "$dst"
                echo "   📦 Migrated: $rel_path → $dst"
                (( migrated++ ))
            fi
        done < <(find "$legacy_dir" -name "*.md" -print0 2>/dev/null)

        echo "   ✅ Migrated $migrated project-specific file(s) from $legacy_dir/"
    }

    # ── 5. Create .agent/ if needed, then migrate ────────────────────────────
    if [[ ! -d ".agent" ]]; then
        if [[ ${#LEGACY_DIRS[@]} -eq 0 ]]; then
            echo "❌ No .agent/ or legacy agent directory found."
            echo "   Run 'amir init-project .' to set up from scratch."
            return 1
        fi

        echo "📦 No .agent/ found. Migrating project-specific content from legacy dirs..."
        mkdir -p ".agent/rules" ".agent/skills"
        for d in "${LEGACY_DIRS[@]}"; do
            _migrate_legacy "$d"
        done
        echo ""
    else
        # .agent/ exists — report if legacy dirs are also present (optional cleanup)
        if [[ ${#LEGACY_DIRS[@]} -gt 0 ]]; then
            echo "ℹ️  Legacy dirs found alongside .agent/: ${LEGACY_DIRS[*]}"
            echo "   They were not modified. Remove them manually when ready."
            echo ""
        fi
    fi

    # ── 6. Sync standard content from agent-constitution ─────────────────────
    _sync_dir() {
        local src_dir="$1" dst_dir="$2" label="$3"
        local count=0
        mkdir -p "$dst_dir"
        for f in "$src_dir"/*; do
            [[ -f "$f" ]] || continue
            cp -f "$f" "$dst_dir/$(basename "$f")"
            (( count++ ))
        done
        echo "   ✅ $label: $count files synced"
    }

    echo "📋 Syncing rules (project-specific rules preserved)..."
    _sync_dir "$SOURCE_ROOT/rules" ".agent/rules" "rules"

    echo "🧠 Syncing skills..."
    _sync_dir "$SOURCE_ROOT/skills" ".agent/skills" "skills"

    echo "🔄 Syncing core workflows..."
    mkdir -p ".agent/workflows"
    local wf_count=0
    for wf in init-project.md documentation.md ai-optimization.md quality-assurance.md communication.md; do
        local src="$SOURCE_ROOT/workflows/$wf"
        [[ -f "$src" ]] && cp -f "$src" ".agent/workflows/$wf" && (( wf_count++ ))
    done
    echo "   ✅ workflows: $wf_count files synced"

    # ── 7. Detect project-exclusive skills (not in agent-constitution) ──────────
    local exclusive_skills=()
    for f in ".agent/skills/"*.md; do
        [[ -f "$f" ]] || continue
        local skill_name
        skill_name="$(basename "$f")"
        if [[ ! -f "$SOURCE_ROOT/skills/$skill_name" ]]; then
            exclusive_skills+=("$skill_name")
        fi
    done

    # ── 8. Summary ────────────────────────────────────────────────────────────
    echo ""
    echo "✅ Done."
    echo "   • CLAUDE.md, .gitignore, and project-specific files: untouched"
    if [[ ${#LEGACY_DIRS[@]} -gt 0 && ! -d ".agent" ]]; then
        echo "   • Legacy dirs migrated — review .agent/rules/ before committing"
    fi

    if [[ ${#exclusive_skills[@]} -gt 0 ]]; then
        echo ""
        echo "💡 Project-exclusive skills found (not in agent-constitution):"
        for s in "${exclusive_skills[@]}"; do
            echo "   ➕ $s"
        done
        echo ""
        echo "   Consider adding them to agent-constitution:"
        echo "   cp .agent/skills/<skill> /path/to/agent-constitution/.agent/skills/"
        echo "   Then: amir sync-constitution /path/to/agent-constitution  # (or commit manually)"
    fi

    echo ""
    echo "Review changes:  git diff .agent/"
    echo ""
}
