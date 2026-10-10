#!/bin/bash
# tests/test_todo.sh — unit/functional tests for `amir todo`
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMIR_ROOT="$(dirname "$SCRIPT_DIR")"
AMIR="$AMIR_ROOT/amir"

PASS=0
FAIL=0
FAILED_CASES=()

# Set up clean temporary sandbox: never touch ~/.amir or ~/.config
TMP_DIR=$(mktemp -d 2>/dev/null || mktemp -d -t 'amir-todo-test')
trap 'rm -rf "$TMP_DIR"' EXIT

export HOME="$TMP_DIR/home"
mkdir -p "$HOME"
export AMIR_TODO_FILE="$TMP_DIR/todo_list.txt"

assert_pass() {
    local desc="$1"
    PASS=$((PASS + 1))
    printf "  OK   %s\n" "$desc"
}

assert_fail() {
    local desc="$1"
    local reason="${2:-}"
    FAIL=$((FAIL + 1))
    FAILED_CASES+=("$desc ($reason)")
    printf "  FAIL %s [%s]\n" "$desc" "$reason"
}

echo "=== amir todo tests ==="

# 1. add quoted multi-word
out=$("$AMIR" --no-venv todo add "buy fresh milk" 2>&1 </dev/null)
rc=$?
if [[ $rc -eq 0 ]] && grep -qF -- "- buy fresh milk" "$AMIR_TODO_FILE" && printf '%s\n' "$out" | grep -qF -- "buy fresh milk"; then
    assert_pass "add quoted multi-word"
else
    assert_fail "add quoted multi-word" "rc=$rc out=$out"
fi

# 2. add unquoted multi-word
out=$("$AMIR" --no-venv todo add read chapter two 2>&1 </dev/null)
rc=$?
if [[ $rc -eq 0 ]] && grep -qF -- "- read chapter two" "$AMIR_TODO_FILE" && printf '%s\n' "$out" | grep -qF -- "read chapter two"; then
    assert_pass "add unquoted multi-word"
else
    assert_fail "add unquoted multi-word" "rc=$rc out=$out"
fi

# 3. empty add writes nothing
before_content=$(cat "$AMIR_TODO_FILE" 2>/dev/null || true)
out1=$("$AMIR" --no-venv todo add 2>&1 </dev/null)
rc1=$?
out2=$("$AMIR" --no-venv todo add "" 2>&1 </dev/null)
rc2=$?
after_content=$(cat "$AMIR_TODO_FILE" 2>/dev/null || true)
if [[ $rc1 -eq 0 && $rc2 -eq 0 && "$before_content" == "$after_content" ]] && printf '%s\n' "$out1" | grep -qF -- "Usage:"; then
    assert_pass "empty add writes nothing"
else
    assert_fail "empty add writes nothing" "rc1=$rc1 rc2=$rc2 changed=$([ "$before_content" != "$after_content" ] && echo yes || echo no)"
fi

# 4. unknown verb rejected and not appended
before_content=$(cat "$AMIR_TODO_FILE" 2>/dev/null || true)
out1=$("$AMIR" --no-venv todo foo 2>&1 </dev/null)
rc1=$?
out2=$("$AMIR" --no-venv todo invalid command 2>&1 </dev/null)
rc2=$?
after_content=$(cat "$AMIR_TODO_FILE" 2>/dev/null || true)
if [[ $rc1 -ne 0 && $rc2 -ne 0 && "$before_content" == "$after_content" ]] && printf '%s\n' "$out1" | grep -qF -- "Usage:"; then
    assert_pass "unknown verb rejected and not appended"
else
    assert_fail "unknown verb rejected and not appended" "rc1=$rc1 rc2=$rc2"
fi

# Extra check: bare "task with space" still works
out_bare=$("$AMIR" --no-venv todo "write the report" 2>&1 </dev/null)
rc_bare=$?
if [[ $rc_bare -eq 0 ]] && grep -qF -- "- write the report" "$AMIR_TODO_FILE"; then
    assert_pass "bare task with space adds item"
else
    assert_fail "bare task with space adds item" "rc=$rc_bare"
fi

# 5. done out of range exit 1 and file unchanged
# Current file has 3 items: "buy fresh milk", "read chapter two", "write the report"
count=$(wc -l < "$AMIR_TODO_FILE" | tr -d '[:space:]')
before_content=$(cat "$AMIR_TODO_FILE")
out1=$("$AMIR" --no-venv todo done 99 2>&1 </dev/null)
rc1=$?
out2=$("$AMIR" --no-venv todo done 0 2>&1 </dev/null)
rc2=$?
after_content=$(cat "$AMIR_TODO_FILE")
if [[ $rc1 -eq 1 && $rc2 -eq 1 && "$before_content" == "$after_content" ]] && \
   printf '%s\n' "$out1" | grep -qF "❌ No item 99 (the list has $count)." && \
   printf '%s\n' "$out2" | grep -qF "❌ No item 0 (the list has $count)."; then
    assert_pass "done out of range exit 1 and file unchanged"
else
    assert_fail "done out of range exit 1 and file unchanged" "rc1=$rc1 rc2=$rc2"
fi

# 6. done in range removes the right line
# Current file lines: 1: buy fresh milk, 2: read chapter two, 3: write the report
out=$("$AMIR" --no-venv todo done 2 2>&1 </dev/null)
rc=$?
if [[ $rc -eq 0 ]] && ! grep -qF -- "- read chapter two" "$AMIR_TODO_FILE" && \
   grep -qF -- "- buy fresh milk" "$AMIR_TODO_FILE" && \
   grep -qF -- "- write the report" "$AMIR_TODO_FILE" && \
   printf '%s\n' "$out" | grep -qF "✅ Item 2 removed."; then
    assert_pass "done in range removes the right line"
else
    assert_fail "done in range removes the right line" "rc=$rc"
fi

# 7. clear refused without TTY/AMIR_YES
before_content=$(cat "$AMIR_TODO_FILE")
out=$(AMIR_YES= "$AMIR" --no-venv todo clear 2>&1 </dev/null)
rc=$?
after_content=$(cat "$AMIR_TODO_FILE")
if [[ $rc -ne 0 && "$before_content" == "$after_content" && -s "$AMIR_TODO_FILE" ]]; then
    assert_pass "clear refused without TTY/AMIR_YES"
else
    assert_fail "clear refused without TTY/AMIR_YES" "rc=$rc"
fi

# 8. clear works with AMIR_YES=1
out=$(AMIR_YES=1 "$AMIR" --no-venv todo clear 2>&1 </dev/null)
rc=$?
if [[ $rc -eq 0 && ! -s "$AMIR_TODO_FILE" ]] && printf '%s\n' "$out" | grep -qF "✅ List cleared."; then
    assert_pass "clear works with AMIR_YES=1"
else
    assert_fail "clear works with AMIR_YES=1" "rc=$rc"
fi

# 9. list reprinted after each mutation
# Mutation A: add
out_add=$("$AMIR" --no-venv todo add "mutation check item" 2>&1 </dev/null)
# Mutation B: done
out_done=$("$AMIR" --no-venv todo done 1 2>&1 </dev/null)
# Mutation C: clear
out_clear=$(AMIR_YES=1 "$AMIR" --no-venv todo clear 2>&1 </dev/null)

has_add_header=$(printf '%s\n' "$out_add" | grep -q "Your TODO List" && echo yes || echo no)
has_add_item=$(printf '%s\n' "$out_add" | grep -q "mutation check item" && echo yes || echo no)
has_done_header=$(printf '%s\n' "$out_done" | grep -q "Your TODO List" && echo yes || echo no)
has_clear_header=$(printf '%s\n' "$out_clear" | grep -q "Your TODO List" && echo yes || echo no)
has_clear_empty=$(printf '%s\n' "$out_clear" | grep -q "(Empty)" && echo yes || echo no)

if [[ "$has_add_header" == "yes" && "$has_add_item" == "yes" && \
      "$has_done_header" == "yes" && \
      "$has_clear_header" == "yes" && "$has_clear_empty" == "yes" ]]; then
    assert_pass "list reprinted after each mutation"
else
    assert_fail "list reprinted after each mutation" "add_h=$has_add_header done_h=$has_done_header clear_h=$has_clear_header"
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
