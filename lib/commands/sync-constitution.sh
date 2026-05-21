#!/bin/bash

run_sync_constitution() {

    # ── 1. Locate agent-constitution ──────────────────────────────────────────
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

    # ── 2. Target ─────────────────────────────────────────────────────────────
    local TARGET_DIR="${1:-.}"
    [[ "$TARGET_DIR" == "." || "$TARGET_DIR" == "./" ]] && TARGET_DIR="$(pwd)"
    TARGET_DIR="$(cd "$TARGET_DIR" 2>/dev/null && pwd)"

    if [[ -z "$TARGET_DIR" || ! -d "$TARGET_DIR" ]]; then
        echo "❌ Target directory not found: $1"
        return 1
    fi

    if [[ ! -d "$TARGET_DIR/.agent" ]]; then
        echo "❌ No .agent/ found in $TARGET_DIR — run 'amir init-project' first."
        return 1
    fi

    echo ""
    echo "🔄 amir sync-constitution"
    echo "   Source : $SOURCE_ROOT"
    echo "   Target : $TARGET_DIR"
    echo ""

    cd "$TARGET_DIR" || return 1

    # Sync a directory: overwrite files that exist in source, never delete target-only files
    _sync_dir() {
        local src_dir="$1" dst_dir="$2" label="$3"
        local count=0
        mkdir -p "$dst_dir"
        for f in "$src_dir"/*; do
            [[ -f "$f" ]] || continue
            cp -f "$f" "$dst_dir/$(basename "$f")"
            (( count++ ))
        done
        echo "   ✅ $label: $count files updated"
    }

    echo "📋 Syncing rules (project-specific rules preserved)..."
    _sync_dir "$SOURCE_ROOT/.agent/rules" ".agent/rules" "rules"

    echo "🧠 Syncing skills..."
    _sync_dir "$SOURCE_ROOT/.agent/skills" ".agent/skills" "skills"

    echo "🔄 Syncing core workflows..."
    mkdir -p ".agent/workflows"
    local wf_count=0
    for wf in init-project.md documentation.md ai-optimization.md quality-assurance.md communication.md; do
        src="$SOURCE_ROOT/.agent/workflows/$wf"
        [[ -f "$src" ]] && cp -f "$src" ".agent/workflows/$wf" && (( wf_count++ ))
    done
    echo "   ✅ workflows: $wf_count files updated"

    echo ""
    echo "✅ Done. Your project-specific files (CLAUDE.md and non-standard rules) were not touched."
    echo ""
    echo "Review changes:"
    echo "   git diff .agent/"
    echo ""
}
