#!/bin/bash
# amir update-projects — propagate the latest agent-constitution + pre-commit
# hook to every project under a base directory that links the constitution
# (rule 045: one central clone, symlinked into each project — see
# lib/commands/init-project.sh). Legacy projects still on the old per-repo
# git-submodule pattern are also detected and kept working (their submodule is
# updated in place; re-run `amir init-project` on them to migrate to the
# symlink pattern). Idempotent and non-destructive. Written for bash 3.2 (no
# mapfile / assoc arrays).

run_update_projects() {
    local CONSTITUTION_PATH=".agent/constitution"
    local HOOKS_REL="$CONSTITUTION_PATH/templates/hooks"
    local CONSTITUTION_CENTRAL="${AGENT_CONSTITUTION_DIR:-$HOME/@-github/agent-constitution}"

    # ── defaults ────────────────────────────────────────────────────────────
    local BASE_DIR="${AMIR_PROJECTS_DIR:-$HOME/@-github}"
    local DRY_RUN=0
    local DO_HOOK=1
    local DO_LINK=1
    # amir-cli & agent-constitution are excluded by default: the former is the
    # CLI's own repo (often mid-work), the latter is the constitution itself.
    local EXCLUDES="amir-cli agent-constitution"

    # ── parse args ──────────────────────────────────────────────────────────
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)      DRY_RUN=1 ;;
            --no-hook)      DO_HOOK=0 ;;
            --no-link)      DO_LINK=0 ;;
            --no-submodule) DO_LINK=0 ;;  # deprecated alias, kept for back-compat
            --exclude)      shift; EXCLUDES="$EXCLUDES $1" ;;
            --exclude=*)    EXCLUDES="$EXCLUDES ${1#*=}" ;;
            -h|--help)
                cat <<'EOF'
Usage: amir update-projects [BASE_DIR] [options]

(Re)installs the agent-constitution pre-commit/commit-msg hooks and refreshes
the constitution link in every project under BASE_DIR that uses it — either
the current symlink pattern (one central clone, re-linked per project) or the
legacy per-repo git-submodule pattern (still supported, updated in place).

  BASE_DIR           Directory to scan (default: $AMIR_PROJECTS_DIR or ~/@-github)
  --dry-run          List what would happen, change nothing
  --no-hook          Don't (re)install the pre-commit/commit-msg hooks
  --no-link          Don't refresh the constitution link/submodule
  --exclude "a b"    Extra project names to skip
                     (default excludes: amir-cli agent-constitution)

Notes:
  • Symlink-pattern projects: the central clone
    ($AGENT_CONSTITUTION_DIR, default ~/@-github/agent-constitution) is pulled
    ONCE up front, then every project's symlink is refreshed (cheap, no
    per-project network call).
  • Legacy submodule-pattern projects keep working as before; re-run
    `amir init-project` on them to migrate to the symlink pattern.
    SSH submodule URLs may prompt for your key passphrase — run once:
    ssh-add --apple-use-keychain ~/.ssh/id_ed25519
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
    echo "   Link      : $([[ $DO_LINK == 1 ]] && echo update || echo skip)"
    echo "   Hook      : $([[ $DO_HOOK == 1 ]] && echo install || echo skip)"
    echo "   Excludes  : $EXCLUDES"
    [[ $DRY_RUN == 1 ]] && echo "   Mode      : DRY-RUN (no changes)"
    echo ""

    # Refresh the ONE central clone up front — every symlink-pattern project
    # then just gets a cheap re-link below, no per-project network call.
    if [[ $DO_LINK == 1 && $DRY_RUN == 0 && -d "$CONSTITUTION_CENTRAL/.git" ]]; then
        git -C "$CONSTITUTION_CENTRAL" pull --ff-only >/dev/null 2>&1 && \
            echo "✅ central clone up to date ($CONSTITUTION_CENTRAL)" || \
            echo "⚠️  could not pull $CONSTITUTION_CENTRAL (offline/no access?) — using local copy as-is"
        echo ""
    fi

    local updated=0 skipped=0 failed=0
    local d name
    for d in "$BASE_DIR"/*/; do
        d="${d%/}"
        name="$(basename "$d")"

        # Detect which pattern this project uses; skip projects that use neither.
        local mode=""
        if [[ -L "$d/$CONSTITUTION_PATH" ]]; then
            mode="symlink"
        elif [[ -f "$d/.gitmodules" ]] && grep -qF "$CONSTITUTION_PATH" "$d/.gitmodules" 2>/dev/null; then
            mode="submodule"
        else
            continue
        fi

        case " $EXCLUDES " in
            *" $name "*) echo "   ⏭  $name (excluded)"; skipped=$((skipped+1)); continue ;;
        esac

        echo "── $name ($mode) ──"
        if [[ $DRY_RUN == 1 ]]; then
            echo "   would: $([[ $DO_LINK == 1 ]] && echo "refresh $mode")  $([[ $DO_HOOK == 1 ]] && echo '+ install hooks')"
            updated=$((updated+1)); continue
        fi

        local ok=1
        if [[ $DO_LINK == 1 ]]; then
            case "$mode" in
                symlink)
                    if ln -sfn "$CONSTITUTION_CENTRAL" "$d/$CONSTITUTION_PATH" 2>/dev/null; then
                        echo "   ✅ constitution link refreshed"
                    else
                        echo "   ⚠️  could not refresh symlink"; ok=0
                    fi
                    ;;
                submodule)
                    if git -C "$d" submodule update --remote "$CONSTITUTION_PATH" >/dev/null 2>&1; then
                        echo "   ✅ constitution submodule updated (legacy — re-run 'amir init-project' here to migrate to the symlink pattern)"
                    else
                        echo "   ⚠️  submodule update failed (SSH access? run: ssh -T git@github.com)"; ok=0
                    fi
                    ;;
            esac
        fi

        if [[ $DO_HOOK == 1 ]]; then
            if [[ -f "$d/$HOOKS_REL/pre-commit" ]]; then
                local hooks_dir
                hooks_dir="$(git -C "$d" rev-parse --git-path hooks 2>/dev/null)"
                [[ "$hooks_dir" != /* ]] && hooks_dir="$d/$hooks_dir"
                mkdir -p "$hooks_dir"
                local _h
                for _h in pre-commit pre-merge-commit commit-msg; do
                    if cp "$d/$HOOKS_REL/$_h" "$hooks_dir/$_h" 2>/dev/null && chmod +x "$hooks_dir/$_h"; then
                        echo "   ✅ $_h hook installed"
                    else
                        echo "   ⚠️  $_h hook install failed"; ok=0
                    fi
                done
            else
                echo "   ⚠️  hook template not found — update the link first"; ok=0
            fi
        fi

        if [[ $ok == 1 ]]; then updated=$((updated+1)); else failed=$((failed+1)); fi
    done

    echo ""
    echo "🎉 Done.  updated=$updated  skipped=$skipped  failed=$failed"
    [[ $failed -gt 0 ]] && echo "   Some projects failed — re-run, or check SSH access for SSH-URL submodules."
    return 0
}
