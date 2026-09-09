#!/bin/bash
# doctor.sh — amir doctor: one-shot dependency health check.
# Reports every external tool, the Python venv, every optional external repo,
# and the agent-constitution symlink with an actionable fix command for each
# missing item. Exit code is honest: non-zero only when a REQUIRED item is
# missing (external tools + the .venv). Optional external repos and the
# constitution symlink are reported but never fail the exit code — they are
# genuinely optional, feature-specific dependencies (see README "Optional
# Dependencies").

_doctor_usage() {
    usage_block <<'TXT'
Usage: amir doctor

Description:
  One-shot dependency health check: required external tools (ffmpeg,
  yt-dlp, gallery-dl, qpdf, node, uv), the Python .venv, optional external
  repos (research_toolkit, ApplyForge, ai-router), and the
  agent-constitution symlink. Prints an actionable fix command for every
  missing item. Exits non-zero only when a REQUIRED item is missing.

Options:
  (none)

Examples:
  amir doctor
TXT
}

_doctor_root() {
    echo "${AMIR_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
}

_doctor_check_tool() {
    # _doctor_check_tool NAME FIX_CMD
    local name="$1" fix_cmd="$2"
    if command -v "$name" >/dev/null 2>&1; then
        echo "  ✅ $name"
        return 0
    fi
    echo "  ❌ $name — not found"
    echo "     Fix: $fix_cmd"
    return 1
}

_doctor_check_repo() {
    # _doctor_check_repo LABEL SHORT_NAME RESOLVED_PATH ENV_VAR DEP_KEY
    # DEP_KEY is passed to _amir_external_repo_https_url / _amir_external_repo_ssh_url
    # (lib/amir_lib.sh) — the single shared source of truth for these URLs.
    local label="$1" short_name="$2" resolved_path="$3" env_var="$4" dep_key="$5"
    if [[ -d "$resolved_path" ]]; then
        echo "  ✅ $label — $resolved_path"
        return 0
    fi
    local https_url ssh_url
    https_url="$(_amir_external_repo_https_url "$dep_key")"
    ssh_url="$(_amir_external_repo_ssh_url "$dep_key")"
    echo "  ❌ $label — not found at: $resolved_path"
    echo "     Fix:      git clone $https_url $resolved_path"
    echo "     With SSH: git clone $ssh_url $resolved_path"
    echo "     Or:  export $env_var=/path/to/$short_name"
    return 1
}

run_doctor() {
    if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
        _doctor_usage
        return 0
    fi

    local amir_root required_missing=0

    amir_root="$(_doctor_root)"

    print_header "amir doctor"

    echo ""
    echo "amir-cli install:"
    if git -C "$amir_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        local head_info
        head_info="$(git -C "$amir_root" log -1 --format='%h (%ad)' --date=short 2>/dev/null)"
        echo "  Commit: ${head_info:-unknown}"
    else
        echo "  Commit: unknown (not a git checkout)"
    fi

    echo ""
    echo "External tools (required):"
    _doctor_check_tool ffmpeg     "brew install ffmpeg"                              || required_missing=$((required_missing + 1))
    _doctor_check_tool yt-dlp     "uv tool install yt-dlp"                           || required_missing=$((required_missing + 1))
    _doctor_check_tool gallery-dl "uv tool install gallery-dl"                       || required_missing=$((required_missing + 1))
    _doctor_check_tool qpdf       "brew install qpdf"                                || required_missing=$((required_missing + 1))
    _doctor_check_tool node       "brew install node"                                || required_missing=$((required_missing + 1))
    _doctor_check_tool uv         "curl -LsSf https://astral.sh/uv/install.sh | sh"  || required_missing=$((required_missing + 1))

    echo ""
    echo "Python environment (required):"
    if [[ -x "$amir_root/.venv/bin/python" ]]; then
        echo "  ✅ .venv — $amir_root/.venv"
    else
        echo "  ❌ .venv — not found at: $amir_root/.venv"
        echo "     Fix: cd $amir_root && uv sync"
        required_missing=$((required_missing + 1))
    fi

    echo ""
    echo "External repositories (optional — only needed for specific commands):"
    _doctor_check_repo "research_toolkit (amir trend / amir research)" "research_toolkit" \
        "${RESEARCH_TOOLKIT_DIR:-$HOME/@-github/research_toolkit}" \
        "RESEARCH_TOOLKIT_DIR" "research_toolkit"
    _doctor_check_repo "ApplyForge (amir apply)" "ApplyForge" \
        "${APPLYFORGE_DIR:-$HOME/@-github/ApplyForge}" \
        "APPLYFORGE_DIR" "ApplyForge"
    _doctor_check_repo "ai-router (amir router)" "ai-router" \
        "${AI_ROUTER_DIR:-$HOME/@-github/ai-router}" \
        "AI_ROUTER_DIR" "ai-router"

    echo ""
    echo "Agent constitution symlink (optional):"
    local constitution_link="$amir_root/.agent/constitution"
    if [[ -L "$constitution_link" && -d "$constitution_link" ]]; then
        echo "  ✅ .agent/constitution → $(cd "$constitution_link" && pwd -P)"
    else
        local constitution_dir="${AGENT_CONSTITUTION_DIR:-$HOME/@-github/agent-constitution}"
        local const_https const_ssh
        const_https="$(_amir_external_repo_https_url agent-constitution)"
        const_ssh="$(_amir_external_repo_ssh_url agent-constitution)"
        echo "  ❌ .agent/constitution — missing or broken symlink"
        echo "     Fix:      git clone $const_https $constitution_dir"
        echo "     With SSH: git clone $const_ssh $constitution_dir"
        echo "     Then: ln -sfn $constitution_dir $constitution_link"
    fi

    echo ""
    if [[ $required_missing -gt 0 ]]; then
        echo "❌ $required_missing required dependency(ies) missing — see fixes above."
        return 1
    fi

    echo "✅ All required dependencies present."
    return 0
}
