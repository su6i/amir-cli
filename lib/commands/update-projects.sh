#!/bin/bash
# amir update-projects — propagate the latest agent-constitution + pre-commit
# hook to every project under a base directory that uses the constitution
# submodule. Idempotent and non-destructive (only updates the submodule pointer
# and installs the hook). Written for bash 3.2 (no mapfile / assoc arrays).

run_update_projects() {
    local CONSTITUTION_PATH=".agent/constitution"
    local HOOKS_REL="$CONSTITUTION_PATH/templates/hooks"

    # ── defaults ────────────────────────────────────────────────────────────
    local BASE_DIR="${AMIR_PROJECTS_DIR:-$HOME/@-github}"
    local DRY_RUN=0
    local DO_HOOK=1
    local DO_SUBMODULE=1
    # amir-cli & agent-constitution are excluded by default: the former is the
    # CLI's own repo (often mid-work), the latter is the constitution itself.
    local EXCLUDES="amir-cli agent-constitution"

    # ── parse args ──────────────────────────────────────────────────────────
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)      DRY_RUN=1 ;;
            --no-hook)      DO_HOOK=0 ;;
            --no-submodule) DO_SUBMODULE=0 ;;
            --exclude)      shift; EXCLUDES="$EXCLUDES $1" ;;
            --exclude=*)    EXCLUDES="$EXCLUDES ${1#*=}" ;;
            -h|--help)
                cat <<'EOF'
Usage: amir update-projects [BASE_DIR] [options]

(Re)installs the agent-constitution pre-commit hook and updates the constitution
submodule in every project under BASE_DIR that uses the submodule.

  BASE_DIR           Directory to scan (default: $AMIR_PROJECTS_DIR or ~/@-github)
  --dry-run          List what would happen, change nothing
  --no-hook          Don't (re)install the pre-commit hook
  --no-submodule     Don't update the constitution submodule
  --exclude "a b"    Extra project names to skip
                     (default excludes: amir-cli agent-constitution)

Notes:
  • Projects with an SSH submodule URL may prompt for your key passphrase.
    Run once:  ssh-add --apple-use-keychain ~/.ssh/id_ed25519
  • The installed hook is strict: it blocks commits to main and commits that
    change code without touching docs. Bypass per-commit with --no-verify.
EOF
                return 0 ;;
            -*)             echo "❌ Unknown option: $1"; return 1 ;;
            *)              BASE_DIR="$1" ;;
        esac
        shift
    done

    BASE_DIR="$(cd "$BASE_DIR" 2>/dev/null && pwd)"
    if [[ -z "$BASE_DIR" || ! -d "$BASE_DIR" ]]; then
        echo "❌ Base directory not found."
        return 1
    fi

    echo ""
    echo "🔄 amir update-projects"
    echo "   Scanning  : $BASE_DIR"
    echo "   Submodule : $([[ $DO_SUBMODULE == 1 ]] && echo update || echo skip)"
    echo "   Hook      : $([[ $DO_HOOK == 1 ]] && echo install || echo skip)"
    echo "   Excludes  : $EXCLUDES"
    [[ $DRY_RUN == 1 ]] && echo "   Mode      : DRY-RUN (no changes)"
    echo ""

    local updated=0 skipped=0 failed=0
    local d name
    for d in "$BASE_DIR"/*/; do
        d="${d%/}"
        name="$(basename "$d")"

        # only projects that use the constitution submodule
        { [[ -f "$d/.gitmodules" ]] && grep -qF "$CONSTITUTION_PATH" "$d/.gitmodules" 2>/dev/null; } || continue

        case " $EXCLUDES " in
            *" $name "*) echo "   ⏭  $name (excluded)"; skipped=$((skipped+1)); continue ;;
        esac

        echo "── $name ──"
        if [[ $DRY_RUN == 1 ]]; then
            echo "   would: $([[ $DO_SUBMODULE == 1 ]] && echo 'update submodule')  $([[ $DO_HOOK == 1 ]] && echo '+ install hook')"
            updated=$((updated+1)); continue
        fi

        local ok=1
        if [[ $DO_SUBMODULE == 1 ]]; then
            if git -C "$d" submodule update --remote "$CONSTITUTION_PATH" >/dev/null 2>&1; then
                echo "   ✅ constitution updated"
            else
                echo "   ⚠️  submodule update failed (SSH access? run: ssh -T git@github.com)"; ok=0
            fi
        fi

        if [[ $DO_HOOK == 1 ]]; then
            if [[ -f "$d/$HOOKS_REL/pre-commit" ]]; then
                local hooks_dir
                hooks_dir="$(git -C "$d" rev-parse --git-path hooks 2>/dev/null)"
                [[ "$hooks_dir" != /* ]] && hooks_dir="$d/$hooks_dir"
                mkdir -p "$hooks_dir"
                local _h
                for _h in pre-commit commit-msg; do
                    if cp "$d/$HOOKS_REL/$_h" "$hooks_dir/$_h" 2>/dev/null && chmod +x "$hooks_dir/$_h"; then
                        echo "   ✅ $_h hook installed"
                    else
                        echo "   ⚠️  $_h hook install failed"; ok=0
                    fi
                done
            else
                echo "   ⚠️  hook template not found — update the submodule first"; ok=0
            fi
        fi

        if [[ $ok == 1 ]]; then updated=$((updated+1)); else failed=$((failed+1)); fi
    done

    echo ""
    echo "🎉 Done.  updated=$updated  skipped=$skipped  failed=$failed"
    [[ $failed -gt 0 ]] && echo "   Some projects failed — re-run, or check SSH access for SSH-URL submodules."
    return 0
}
