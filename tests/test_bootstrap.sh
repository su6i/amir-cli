#!/bin/bash
# tests/test_bootstrap.sh — WO-amir-cli-0010: companion-repo auto-bootstrap
# and API-key auto-provisioning. Never touches the network or the real
# ~/.amir/config.yaml. Run from anywhere:
#   bash tests/test_bootstrap.sh
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMIR_ROOT="$(dirname "$SCRIPT_DIR")"

PASS=0
FAIL=0
FAILED_CASES=()

pass() { PASS=$((PASS + 1)); printf "  OK   %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); FAILED_CASES+=("$1"); printf "  FAIL %s\n" "$1"; }

# ── Isolated environment: never touch the real ~/.amir ──────────────────────
TEST_TMP="$(mktemp -d)"
export AMIR_CONFIG_DIR="$TEST_TMP/amir_config"
export AMIR_ROOT
source "$AMIR_ROOT/lib/amir_lib.sh"

cleanup() { rm -rf "$TEST_TMP"; }
trap cleanup EXIT

echo "=== _ensure_external_repo: AMIR_NO_AUTO_INSTALL=1 guard ==="
FAKE_REPO_DIR="$TEST_TMP/no_clone_1/research_toolkit"
OUT="$(AMIR_NO_AUTO_INSTALL=1 _ensure_external_repo "amir trend" "research_toolkit" "$FAKE_REPO_DIR" "RESEARCH_TOOLKIT_DIR" "research_toolkit" 2>&1 </dev/null)"
RC=$?
if [[ $RC -eq 1 && "$OUT" == *"not found at: $FAKE_REPO_DIR"* && "$OUT" == *"git clone"* ]]; then
    pass "AMIR_NO_AUTO_INSTALL=1 -> exit 1, old hint text"
else
    fail "AMIR_NO_AUTO_INSTALL=1 -> exit 1, old hint text (rc=$RC out=$OUT)"
fi
if [[ -d "$FAKE_REPO_DIR" ]]; then
    fail "AMIR_NO_AUTO_INSTALL=1 -> must NOT clone (dir exists!)"
else
    pass "AMIR_NO_AUTO_INSTALL=1 -> no directory created"
fi

echo ""
echo "=== _ensure_external_repo: non-TTY stdin guard (no AMIR_NO_AUTO_INSTALL) ==="
FAKE_REPO_DIR2="$TEST_TMP/no_clone_2/research_toolkit"
OUT="$(_ensure_external_repo "amir trend" "research_toolkit" "$FAKE_REPO_DIR2" "RESEARCH_TOOLKIT_DIR" "research_toolkit" 2>&1 </dev/null)"
RC=$?
if [[ $RC -eq 1 && "$OUT" == *"not found at: $FAKE_REPO_DIR2"* ]]; then
    pass "non-TTY stdin -> exit 1, old hint text"
else
    fail "non-TTY stdin -> exit 1, old hint text (rc=$RC out=$OUT)"
fi
if [[ -d "$FAKE_REPO_DIR2" ]]; then
    fail "non-TTY stdin -> must NOT clone (dir exists!)"
else
    pass "non-TTY stdin -> no directory created (no network hit)"
fi

echo ""
echo "=== _ensure_external_repo: fast path (dir exists) is silent ==="
EXISTING_DIR="$TEST_TMP/already_here"
mkdir -p "$EXISTING_DIR"
OUT="$(_ensure_external_repo "amir trend" "research_toolkit" "$EXISTING_DIR" "RESEARCH_TOOLKIT_DIR" "research_toolkit" 2>&1 </dev/null)"
RC=$?
if [[ $RC -eq 0 && -z "$OUT" ]]; then
    pass "existing dir -> return 0, zero output"
else
    fail "existing dir -> return 0, zero output (rc=$RC out=$OUT)"
fi

echo ""
echo "=== _amir_ensure_api_key: found via exported env var ==="
ENV_FILE_1="$TEST_TMP/env1/.env"
mkdir -p "$(dirname "$ENV_FILE_1")"
: > "$ENV_FILE_1"
OUT="$(FAKE_TEST_KEY="from-env-var" _amir_ensure_api_key FAKE_TEST_KEY "$ENV_FILE_1" "https://example.com" 2>&1 </dev/null)"
RC=$?
if [[ $RC -eq 0 ]] && grep -q "^FAKE_TEST_KEY=from-env-var$" "$ENV_FILE_1"; then
    pass "env var found -> mirrored into target .env, no prompt"
else
    fail "env var found -> mirrored into target .env (rc=$RC file=$(cat "$ENV_FILE_1" 2>/dev/null))"
fi

echo ""
echo "=== _amir_ensure_api_key: found via config.yaml ==="
mkdir -p "$AMIR_CONFIG_DIR"
cat > "$AMIR_CONFIG_DIR/config.yaml" <<'EOF'
api_keys:
  FAKE_TEST_KEY2: from-config-yaml
EOF
ENV_FILE_2="$TEST_TMP/env2/.env"
mkdir -p "$(dirname "$ENV_FILE_2")"
: > "$ENV_FILE_2"
unset FAKE_TEST_KEY2 2>/dev/null
OUT="$(_amir_ensure_api_key FAKE_TEST_KEY2 "$ENV_FILE_2" "https://example.com" 2>&1 </dev/null)"
RC=$?
if [[ $RC -eq 0 ]] && grep -q "^FAKE_TEST_KEY2=from-config-yaml$" "$ENV_FILE_2"; then
    pass "config.yaml found -> mirrored into target .env, no prompt"
else
    fail "config.yaml found -> mirrored into target .env (rc=$RC file=$(cat "$ENV_FILE_2" 2>/dev/null))"
fi

echo ""
echo "=== _amir_ensure_api_key: nothing found, non-interactive -> no prompt ==="
ENV_FILE_3="$TEST_TMP/env3/.env"
mkdir -p "$(dirname "$ENV_FILE_3")"
: > "$ENV_FILE_3"
unset FAKE_TEST_KEY3 2>/dev/null
OUT="$(_amir_ensure_api_key FAKE_TEST_KEY3 "$ENV_FILE_3" "https://example.com" 2>&1 </dev/null)"
RC=$?
if [[ $RC -eq 0 && -z "$(grep '^FAKE_TEST_KEY3=' "$ENV_FILE_3" 2>/dev/null)" ]]; then
    pass "nothing found + non-interactive -> silent no-op, no prompt hang"
else
    fail "nothing found + non-interactive -> silent no-op (rc=$RC file=$(cat "$ENV_FILE_3" 2>/dev/null))"
fi

echo ""
echo "=== _amir_ensure_api_key: prompts ONLY when both are empty (stubbed) ==="
# Stub the TTY check and the actual prompt — never simulate a real TTY read.
_amir_stdin_is_tty() { return 0; }
_amir_prompt_for_key() { printf '%s' "stubbed-prompt-value"; }
ENV_FILE_4="$TEST_TMP/env4/.env"
mkdir -p "$(dirname "$ENV_FILE_4")"
: > "$ENV_FILE_4"
unset FAKE_TEST_KEY4 2>/dev/null
OUT="$(_amir_ensure_api_key FAKE_TEST_KEY4 "$ENV_FILE_4" "https://example.com" 2>&1 </dev/null)"
RC=$?
if [[ $RC -eq 0 ]] && grep -q "^FAKE_TEST_KEY4=stubbed-prompt-value$" "$ENV_FILE_4" \
   && grep -q "FAKE_TEST_KEY4: stubbed-prompt-value" "$AMIR_CONFIG_DIR/config.yaml"; then
    pass "stubbed prompt -> answer persisted to .env AND config.yaml"
else
    fail "stubbed prompt -> answer persisted to .env AND config.yaml (rc=$RC file=$(cat "$ENV_FILE_4" 2>/dev/null))"
fi
CONFIG_MODE="$(stat -f '%Lp' "$AMIR_CONFIG_DIR/config.yaml" 2>/dev/null || stat -c '%a' "$AMIR_CONFIG_DIR/config.yaml" 2>/dev/null)"
if [[ "$CONFIG_MODE" == "600" ]]; then
    pass "config.yaml left at mode 600"
else
    fail "config.yaml left at mode 600 (got: $CONFIG_MODE)"
fi

echo ""
echo "=== _amir_ensure_api_key: found key never re-prompts (guard against loop) ==="
# Key now already in config.yaml from the previous case — a second call with
# the prompt stub replaced by a failing stub proves it is never invoked again.
_amir_prompt_for_key() { echo "PROMPT SHOULD NOT HAVE BEEN CALLED" >&2; printf ''; }
ENV_FILE_5="$TEST_TMP/env5/.env"
mkdir -p "$(dirname "$ENV_FILE_5")"
: > "$ENV_FILE_5"
OUT="$(_amir_ensure_api_key FAKE_TEST_KEY4 "$ENV_FILE_5" "https://example.com" 2>&1 </dev/null)"
if grep -q "^FAKE_TEST_KEY4=stubbed-prompt-value$" "$ENV_FILE_5" && [[ "$OUT" != *"SHOULD NOT HAVE BEEN CALLED"* ]]; then
    pass "already-known key -> no re-prompt, mirrored silently"
else
    fail "already-known key -> no re-prompt (out=$OUT)"
fi

echo ""
echo "======================================"
echo "PASS: $PASS   FAIL: $FAIL"
if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo "Failed cases:"
    for c in "${FAILED_CASES[@]}"; do
        echo "  - $c"
    done
    exit 1
fi
exit 0
