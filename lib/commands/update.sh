#!/bin/bash
# amir update — update repository, dependencies, tools, and system packages
#
# Usage: amir update [options]
#   --check        Report-only mode; do not mutate any state
#   --no-git       Skip git repository update (Step 1)
#   --brew         Enable Homebrew formula upgrades (Step 5, disabled by default)
#   --all-tools    Upgrade all uv tools instead of the fixed list (Step 3)
#   -h, --help     Show this help message and exit

_amir_ytdlp_ver() {
    local _d
    for _d in "$1"/lib/python*/site-packages/yt_dlp-*.dist-info; do
        [[ -d "$_d" ]] || continue
        _d="${_d##*/yt_dlp-}"
        printf '%s' "${_d%.dist-info}"
        return 0
    done
    return 1
}

run_update() {
    # ── defaults ────────────────────────────────────────────────────────────
    local CHECK_MODE=0
    local NO_GIT=0
    local DO_BREW=0
    local ALL_TOOLS=0
    local FAILURES=""

    # ── parse args ──────────────────────────────────────────────────────────
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --check)        CHECK_MODE=1 ;;
            --no-git)       NO_GIT=1 ;;
            --brew)         DO_BREW=1 ;;
            --all-tools)    ALL_TOOLS=1 ;;
            -h|--help)
                cat <<'EOF'
Usage: amir update [options]

Update the repository, Python dependencies, tools, and system packages.

Options:
  --check        Report-only mode; inspect versions without mutating state
  --no-git       Skip git repository update (Step 1)
  --brew         Enable Homebrew formula upgrades (Step 5, disabled by default)
  --all-tools    Upgrade all uv tools instead of the fixed list (Step 3)
  -h, --help     Show this help message and exit
EOF
                return 0 ;;
            -*)             echo "❌ Unknown option: $1"; return 1 ;;
            *)              echo "❌ Unexpected argument: $1"; return 1 ;;
        esac
        shift
    done

    # ── local helpers ───────────────────────────────────────────────────────
    _record_failure() {
        local msg="$1"
        if [[ -z "$FAILURES" ]]; then
            FAILURES="  - $msg"
        else
            FAILURES="$FAILURES
  - $msg"
        fi
    }

    _format_version_row() {
        local name="$1"
        local b="$2"
        local a="$3"
        if [[ $CHECK_MODE -eq 1 || -z "$b" || "$b" == "$a" ]]; then
            printf "  %-20s %s\n" "$name" "$a"
        else
            printf "  %-20s %s -> %s\n" "$name" "$b" "$a"
        fi
    }

    # Tool versions come from one `uv tool list` snapshot rather than running
    # each binary. A uv tool's NAME is not always its binary name — mlx-whisper
    # installs `mlx_whisper`, openai-whisper installs `whisper` — so calling
    # `<tool> --version` left half the table showing "?", and gdown's own
    # --version prints its install path alongside the number. One parse is both
    # cheaper and correct. yt-dlp keeps the dist-info reader above, because the
    # .venv copy is not a uv tool and would otherwise be invisible here.
    _uv_tool_snapshot() {
        uv tool list 2>/dev/null | awk '/^[A-Za-z]/ { print $1, $2 }'
    }
    _uv_tool_ver() {
        printf '%s\n' "$2" | awk -v n="$1" '$1 == n { v = $2; sub(/^v/, "", v); print v; exit }'
    }

    echo ""
    echo "🔄 amir update"

    # Capture initial versions before potential upgrades
    local b_ytdlp_uv=""
    local b_ytdlp_venv=""
    local b_gallery_dl=""
    local b_mlx_whisper=""
    local b_static_ffmpeg=""
    local b_gdown=""
    local b_openai_whisper=""

    if [[ $CHECK_MODE -eq 0 ]]; then
        local SNAP_BEFORE
        SNAP_BEFORE=$(_uv_tool_snapshot)

        b_ytdlp_uv=$(_amir_ytdlp_ver "$HOME/.local/share/uv/tools/yt-dlp" 2>/dev/null)
        [[ -z "$b_ytdlp_uv" ]] && b_ytdlp_uv="?"

        b_ytdlp_venv=$(_amir_ytdlp_ver "$AMIR_ROOT/.venv" 2>/dev/null)
        [[ -z "$b_ytdlp_venv" ]] && b_ytdlp_venv="?"

        b_gallery_dl=$(_uv_tool_ver gallery-dl "$SNAP_BEFORE")
        [[ -z "$b_gallery_dl" ]] && b_gallery_dl="?"

        b_mlx_whisper=$(_uv_tool_ver mlx-whisper "$SNAP_BEFORE")
        [[ -z "$b_mlx_whisper" ]] && b_mlx_whisper="?"

        b_static_ffmpeg=$(_uv_tool_ver static-ffmpeg "$SNAP_BEFORE")
        [[ -z "$b_static_ffmpeg" ]] && b_static_ffmpeg="?"

        b_gdown=$(_uv_tool_ver gdown "$SNAP_BEFORE")
        [[ -z "$b_gdown" ]] && b_gdown="?"

        b_openai_whisper=$(_uv_tool_ver openai-whisper "$SNAP_BEFORE")
        [[ -z "$b_openai_whisper" ]] && b_openai_whisper="?"
    fi

    # ── Step 1: Git repository update ────────────────────────────────────────
    echo ""
    echo "-- Step 1: Repository update (git) --"
    # --check evaluates every guard and reports the decision it WOULD take, and
    # stops just short of the pull itself. Announcing only "skipped: --check
    # mode" here would hide the one answer this step is asked for — whether the
    # pull is safe on the current branch and tree.
    if [[ $NO_GIT -eq 1 ]]; then
        echo "skipped (--no-git)"
    else
        if ! git -C "$AMIR_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
            echo "not a git repository -- skipping git pull"
        else
            local git_status
            git_status=$(git -C "$AMIR_ROOT" status --porcelain 2>/dev/null)
            if [[ -n "$git_status" ]]; then
                echo "working tree has uncommitted changes -- skipping git pull"
            else
                local default_ref
                local default_branch
                default_ref=$(git -C "$AMIR_ROOT" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null)
                if [[ $? -eq 0 && -n "$default_ref" ]]; then
                    default_branch="${default_ref##*/}"
                else
                    default_branch="main"
                fi

                local current_branch
                current_branch=$(git -C "$AMIR_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)
                if [[ "$current_branch" != "$default_branch" ]]; then
                    echo "on branch '$current_branch', not '$default_branch' -- skipping git pull"
                elif [[ $CHECK_MODE -eq 1 ]]; then
                    echo "would run: git pull --ff-only (on '$default_branch', tree clean)"
                else
                    local before_sha
                    before_sha=$(git -C "$AMIR_ROOT" rev-parse --short HEAD 2>/dev/null)
                    if git -C "$AMIR_ROOT" pull --ff-only; then
                        local after_sha
                        after_sha=$(git -C "$AMIR_ROOT" rev-parse --short HEAD 2>/dev/null)
                        if [[ "$before_sha" == "$after_sha" ]]; then
                            echo "already up to date"
                        else
                            echo "$before_sha -> $after_sha"
                        fi
                    else
                        echo "❌ git pull failed"
                        _record_failure "git pull failed"
                    fi
                fi
            fi
        fi
    fi

    # ── Step 2: Python dependencies (uv sync) ────────────────────────────────
    echo ""
    echo "-- Step 2: Python dependencies (uv sync) --"
    if [[ $CHECK_MODE -eq 1 ]]; then
        echo "would run: uv sync --project \"$AMIR_ROOT\" (uv.lock is never modified by this command)"
    else
        if uv sync --project "$AMIR_ROOT"; then
            echo "Python dependencies synchronized"
        else
            echo "❌ uv sync failed"
            _record_failure "uv sync failed"
        fi
    fi

    # ── Step 3: uv tools ─────────────────────────────────────────────────────
    echo ""
    echo "-- Step 3: uv tools upgrade --"
    if [[ $ALL_TOOLS -eq 1 ]]; then
        if [[ $CHECK_MODE -eq 1 ]]; then
            echo "would run: uv tool upgrade --all"
        else
            echo "Upgrading all uv tools..."
            if uv tool upgrade --all; then
                echo "All uv tools upgraded successfully"
            else
                echo "❌ uv tool upgrade --all failed"
                _record_failure "uv tool upgrade --all failed"
            fi
        fi
    else
        local uv_tools_output
        uv_tools_output=$(uv tool list 2>/dev/null)
        local fixed_tools="yt-dlp gallery-dl mlx-whisper static-ffmpeg gdown openai-whisper"
        local tool
        for tool in $fixed_tools; do
            if echo "$uv_tools_output" | grep -q "$tool"; then
                if [[ $CHECK_MODE -eq 1 ]]; then
                    echo "would upgrade: $tool (installed)"
                else
                    echo "Upgrading $tool..."
                    if uv tool upgrade "$tool"; then
                        echo "  $tool upgraded successfully"
                    else
                        echo "❌ uv tool upgrade $tool failed"
                        _record_failure "uv tool upgrade $tool failed"
                    fi
                fi
            else
                if [[ $CHECK_MODE -eq 1 ]]; then
                    echo "skipped: $tool (not installed)"
                fi
            fi
        done
    fi

    # ── Step 4: Node.js dependencies ─────────────────────────────────────────
    echo ""
    echo "-- Step 4: Node.js dependencies (npm install) --"
    if [[ ! -f "$AMIR_ROOT/lib/nodejs/package.json" ]]; then
        echo "skipped: $AMIR_ROOT/lib/nodejs/package.json does not exist"
    elif ! command -v npm >/dev/null 2>&1; then
        echo "skipped: npm not found on PATH"
    elif [[ $CHECK_MODE -eq 1 ]]; then
        echo "would run: npm install --prefix \"$AMIR_ROOT/lib/nodejs\" --no-audit --no-fund"
    else
        echo "Installing Node.js dependencies..."
        if npm install --prefix "$AMIR_ROOT/lib/nodejs" --no-audit --no-fund; then
            echo "Node.js dependencies installed successfully"
        else
            echo "❌ npm install failed"
            _record_failure "npm install failed"
        fi
    fi

    # ── Step 5: Homebrew formulae ────────────────────────────────────────────
    echo ""
    echo "-- Step 5: Homebrew formulae --"
    if [[ $DO_BREW -eq 0 ]]; then
        echo "skipped (pass --brew to run)"
    elif ! command -v brew >/dev/null 2>&1; then
        echo "skipped: brew not found on PATH"
    else
        local brew_formulae="ffmpeg qpdf imagemagick librsvg qrencode bc"
        local formula
        for formula in $brew_formulae; do
            if brew list --formula "$formula" >/dev/null 2>&1; then
                if [[ $CHECK_MODE -eq 1 ]]; then
                    echo "would upgrade: $formula (installed)"
                else
                    echo "Upgrading $formula..."
                    if brew upgrade "$formula"; then
                        echo "  $formula upgraded successfully"
                    else
                        echo "❌ brew upgrade $formula failed"
                        _record_failure "brew upgrade $formula failed"
                    fi
                fi
            fi
        done
    fi

    # ── Step 6: Version table ────────────────────────────────────────────────
    echo ""
    echo "-- Step 6: Version table --"
    local a_ytdlp_uv
    a_ytdlp_uv=$(_amir_ytdlp_ver "$HOME/.local/share/uv/tools/yt-dlp" 2>/dev/null)
    [[ -z "$a_ytdlp_uv" ]] && a_ytdlp_uv="?"

    local a_ytdlp_venv
    a_ytdlp_venv=$(_amir_ytdlp_ver "$AMIR_ROOT/.venv" 2>/dev/null)
    [[ -z "$a_ytdlp_venv" ]] && a_ytdlp_venv="?"

    local SNAP_AFTER
    SNAP_AFTER=$(_uv_tool_snapshot)

    local a_gallery_dl
    a_gallery_dl=$(_uv_tool_ver gallery-dl "$SNAP_AFTER")
    [[ -z "$a_gallery_dl" ]] && a_gallery_dl="?"

    local a_mlx_whisper
    a_mlx_whisper=$(_uv_tool_ver mlx-whisper "$SNAP_AFTER")
    [[ -z "$a_mlx_whisper" ]] && a_mlx_whisper="?"

    local a_static_ffmpeg
    a_static_ffmpeg=$(_uv_tool_ver static-ffmpeg "$SNAP_AFTER")
    [[ -z "$a_static_ffmpeg" ]] && a_static_ffmpeg="?"

    local a_gdown
    a_gdown=$(_uv_tool_ver gdown "$SNAP_AFTER")
    [[ -z "$a_gdown" ]] && a_gdown="?"

    local a_openai_whisper
    a_openai_whisper=$(_uv_tool_ver openai-whisper "$SNAP_AFTER")
    [[ -z "$a_openai_whisper" ]] && a_openai_whisper="?"

    _format_version_row "yt-dlp (uv tool)" "$b_ytdlp_uv" "$a_ytdlp_uv"
    _format_version_row "yt-dlp (.venv)"   "$b_ytdlp_venv" "$a_ytdlp_venv"
    _format_version_row "gallery-dl"       "$b_gallery_dl" "$a_gallery_dl"
    _format_version_row "mlx-whisper"      "$b_mlx_whisper" "$a_mlx_whisper"
    _format_version_row "static-ffmpeg"    "$b_static_ffmpeg" "$a_static_ffmpeg"
    _format_version_row "gdown"            "$b_gdown" "$a_gdown"
    _format_version_row "openai-whisper"   "$b_openai_whisper" "$a_openai_whisper"

    # ── Cleanup helper functions ─────────────────────────────────────────────
    unset -f _record_failure _format_version_row _uv_tool_snapshot _uv_tool_ver 2>/dev/null

    # ── Finish / Error reporting ─────────────────────────────────────────────
    if [[ $CHECK_MODE -eq 1 ]]; then
        return 0
    fi

    if [[ -n "$FAILURES" ]]; then
        echo ""
        echo "Failures:"
        echo "$FAILURES"
        return 1
    fi

    return 0
}
