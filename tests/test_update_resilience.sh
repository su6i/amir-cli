#!/bin/bash
# tests/test_update_resilience.sh — WO-amir-cli-0011: `amir update` must
# retry a transient network failure once and report it as a warning (exit
# 0), while a genuine hard failure gets no retry and a non-zero exit.
#
# This suite stubs `uv` on PATH and points AMIR_ROOT at an empty scratch
# directory (no .git, no lib/nodejs/package.json), so every other step in
# run_update is a guaranteed local no-op by construction. Nothing here ever
# touches the real network.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

PASS=0
FAIL=0
FAILED_CASES=()

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        PASS=$((PASS + 1)); printf "  OK   %s\n" "$desc"
    else
        FAIL=$((FAIL + 1)); FAILED_CASES+=("$desc")
        printf "  FAIL %s\n" "$desc"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        FAIL=$((FAIL + 1)); FAILED_CASES+=("$desc")
        printf "  FAIL %s\n" "$desc"
    else
        PASS=$((PASS + 1)); printf "  OK   %s\n" "$desc"
    fi
}

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1)); printf "  OK   %s\n" "$desc"
    else
        FAIL=$((FAIL + 1)); FAILED_CASES+=("$desc (expected=$expected actual=$actual)")
        printf "  FAIL %s (expected=%s actual=%s)\n" "$desc" "$expected" "$actual"
    fi
}

# _run_scenario SCENARIO ERROR_MSG
# Sets globals: SCEN_OUT, SCEN_RC, SCEN_CALLS
_run_scenario() {
    local error_msg="$1"
    local sandbox fakebin callcount_file fake_amir_root
    sandbox="$(mktemp -d "${TMPDIR:-/tmp}/amir_update_test.XXXXXX")"
    fakebin="$sandbox/bin"
    mkdir -p "$fakebin"
    callcount_file="$sandbox/calls"
    : > "$callcount_file"

    cat > "$fakebin/uv" <<EOF
#!/bin/bash
if [[ "\$1" == "sync" ]]; then exit 0; fi
if [[ "\$1" == "tool" && "\$2" == "list" ]]; then echo "gallery-dl 1.0.0"; exit 0; fi
if [[ "\$1" == "tool" && "\$2" == "upgrade" && "\$3" == "gallery-dl" ]]; then
    echo -n "x" >> "$callcount_file"
    echo "error: Failed to upgrade gallery-dl" >&2
    echo "  Caused by: $error_msg" >&2
    exit 1
fi
exit 0
EOF
    chmod +x "$fakebin/uv"

    fake_amir_root="$sandbox/amir_root"
    mkdir -p "$fake_amir_root"

    SCEN_OUT=$(
        PATH="$fakebin:$PATH" \
        AMIR_ROOT="$fake_amir_root" \
        bash -c "source '$REPO_ROOT/lib/help_common.sh'; source '$REPO_ROOT/lib/commands/update.sh'; run_update" \
        2>&1
    )
    SCEN_RC=$?
    SCEN_CALLS=$(wc -c < "$callcount_file" | tr -d ' ')

    rm -rf "$sandbox"
}

echo "=== Scenario 1: transient network failure (pypi timeout) ==="
_run_scenario "operation timed out"

assert_contains    "shows retry-once notice"            "retrying once"                        "$SCEN_OUT"
assert_contains    "Warnings block header present"      "Warnings (transient, retry later):"   "$SCEN_OUT"
assert_contains    "gallery-dl listed under Warnings"   "gallery-dl: network timeout"          "$SCEN_OUT"
assert_not_contains "no Failures block"                 "Failures:"                             "$SCEN_OUT"
assert_eq          "upgrade command called exactly twice (1 + 1 retry)" "2" "$SCEN_CALLS"
assert_eq          "exit code is 0 (warning only)"       "0" "$SCEN_RC"

echo ""
echo "=== Scenario 2: hard (non-network) failure ==="
_run_scenario "permission denied writing to target directory"

assert_not_contains "no retry-once notice"               "retrying once"                        "$SCEN_OUT"
assert_not_contains "no Warnings block"                  "Warnings (transient, retry later):"   "$SCEN_OUT"
assert_contains     "Failures block header present"      "Failures:"                             "$SCEN_OUT"
assert_contains     "gallery-dl listed under Failures"   "uv tool upgrade gallery-dl failed"    "$SCEN_OUT"
assert_eq           "upgrade command called exactly once (no retry)" "1" "$SCEN_CALLS"
assert_eq           "exit code is non-zero (hard failure)" "1" "$SCEN_RC"

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
