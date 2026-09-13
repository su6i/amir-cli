#!/bin/bash
# tests/test_pdf.sh — WO-amir-cli-0012 item 1 (lib/commands/pdf.sh +
# lib/nodejs/render_puppeteer.js): four bugs from the arix note (2026-08-09).
#   D1 — get_config now resolves (pdf.sh sources lib/config.sh)
#   D2 — DYLD_FALLBACK_LIBRARY_PATH hoisted to the top of the file once
#   D3 — PIL-fallback page collection survives (process substitution, not a
#        piped `| while read` subshell)
#   D4 — --force-rtl/--rtl reaches the puppeteer, weasyprint AND pandoc
#        engines (the direction-decision regex itself is covered by
#        tests/test_pdf_rtl.js)
# Never touches the network, never touches the real ~/.amir/config.yaml
# (HOME is overridden to a temp dir for every case that needs config.sh).
# Run from anywhere:
#   bash tests/test_pdf.sh
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMIR_ROOT="$(dirname "$SCRIPT_DIR")"
PDF_SH="$AMIR_ROOT/lib/commands/pdf.sh"

PASS=0
FAIL=0
FAILED_CASES=()
pass() { PASS=$((PASS + 1)); printf "  OK   %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); FAILED_CASES+=("$1"); printf "  FAIL %s\n" "$1"; }

TEST_TMP="$(mktemp -d)"
cleanup() { rm -rf "$TEST_TMP"; }
trap cleanup EXIT

# ══════════════════════════════════════════════════════════════════
# D1 — get_config resolution (font_fa picked up over the hardcoded font)
# ══════════════════════════════════════════════════════════════════
echo "=== D1: pdf.sh sources config.sh -> get_config resolves pdf.font_fa ==="

# `source pdf.sh split` (no further args) is the one CLI branch that both
# (a) runs the file's top-level setup block -- the exact fix under test --
# and (b) cannot exit the sourcing shell: run_pdf_split() with $#==0 prints
# its usage and `return`s, it never calls `exit`. Every other top-level
# branch in pdf.sh (--help, or zero-args-on-a-tty) calls `exit`, which
# would kill this test script if sourced, so this is the only safe branch.
FAKE_HOME_1="$TEST_TMP/home_with_config"
mkdir -p "$FAKE_HOME_1/.amir"
CUSTOM_FONT="$FAKE_HOME_1/custom-persian-font.ttf"
cat > "$FAKE_HOME_1/.amir/config.yaml" <<EOF
pdf:
  font_fa: $CUSTOM_FONT
EOF

RESULT_1="$(HOME="$FAKE_HOME_1" AMIR_PDF_FONT_FA= bash -c "source \"$PDF_SH\" split </dev/null >/dev/null 2>&1
font_fa=\"\${AMIR_PDF_FONT_FA:-\$(get_config pdf font_fa '')}\"
if [[ -z \"\$font_fa\" ]]; then font_fa=/Library/Fonts/B-NAZANIN.TTF; fi
printf '%s' \"\$font_fa\"")"

if [[ "$RESULT_1" == "$CUSTOM_FONT" ]]; then
    pass "configured pdf.font_fa ($CUSTOM_FONT) wins over the hardcoded B-NAZANIN path"
else
    fail "configured pdf.font_fa should win over hardcoded font (got: '$RESULT_1', want: '$CUSTOM_FONT')"
fi

FAKE_HOME_2="$TEST_TMP/home_no_config"
mkdir -p "$FAKE_HOME_2"
RESULT_2="$(HOME="$FAKE_HOME_2" AMIR_PDF_FONT_FA= bash -c "source \"$PDF_SH\" split </dev/null >/dev/null 2>&1
font_fa=\"\${AMIR_PDF_FONT_FA:-\$(get_config pdf font_fa '')}\"
if [[ -z \"\$font_fa\" ]]; then
    font_fa=/Library/Fonts/B-NAZANIN.TTF
    [[ ! -f \"\$font_fa\" ]] && font_fa=\"\$HOME/Library/Fonts/B-NAZANIN.TTF\"
fi
printf '%s' \"\$font_fa\"")"

if [[ "$RESULT_2" == "/Library/Fonts/B-NAZANIN.TTF" || "$RESULT_2" == "$FAKE_HOME_2/Library/Fonts/B-NAZANIN.TTF" ]]; then
    pass "no config file -> still falls back to the hardcoded B-NAZANIN path (fallback not broken)"
else
    fail "no config file should fall back to hardcoded font (got: '$RESULT_2')"
fi

if grep -qE 'source "\$LIB_DIR/config\.sh"' "$PDF_SH"; then
    pass "pdf.sh sources \$LIB_DIR/config.sh (grep)"
else
    fail "pdf.sh should source \$LIB_DIR/config.sh (grep found nothing)"
fi

# ══════════════════════════════════════════════════════════════════
# D2 — DYLD_FALLBACK_LIBRARY_PATH hoisted once, not copy-pasted
# ══════════════════════════════════════════════════════════════════
echo ""
echo "=== D2: DYLD_FALLBACK_LIBRARY_PATH exported once, both paths get it ==="

DYLD_COUNT="$(grep -c 'export DYLD_FALLBACK_LIBRARY_PATH=' "$PDF_SH")"
if [[ "$DYLD_COUNT" -eq 1 ]]; then
    pass "DYLD_FALLBACK_LIBRARY_PATH is exported exactly once in pdf.sh (was copy-pasted before)"
else
    fail "expected exactly 1 DYLD_FALLBACK_LIBRARY_PATH export in pdf.sh, found $DYLD_COUNT"
fi

# It must be at top-level (before the first function def), not nested
# inside run_pdf_linkedin_post() or run_pdf() anymore.
DYLD_LINE="$(grep -n 'export DYLD_FALLBACK_LIBRARY_PATH=' "$PDF_SH" | head -1 | cut -d: -f1)"
FIRST_FUNC_LINE="$(grep -n '^run_pdf_linkedin_post()' "$PDF_SH" | head -1 | cut -d: -f1)"
if [[ -n "$DYLD_LINE" && -n "$FIRST_FUNC_LINE" && "$DYLD_LINE" -lt "$FIRST_FUNC_LINE" ]]; then
    pass "DYLD_FALLBACK_LIBRARY_PATH export is at top-level (line $DYLD_LINE), before run_pdf_linkedin_post (line $FIRST_FUNC_LINE)"
else
    fail "DYLD_FALLBACK_LIBRARY_PATH export should be above run_pdf_linkedin_post() (dyld_line=$DYLD_LINE func_line=$FIRST_FUNC_LINE)"
fi

# ══════════════════════════════════════════════════════════════════
# D3 — PIL-fallback page collection: process substitution, not a subshell
# ══════════════════════════════════════════════════════════════════
echo ""
echo "=== D3: PIL fallback page collection survives (processed non-empty) ==="

# Extract the ACTUAL fixed loop from the live file (not a hand-copy) so
# this test is a true regression guard: if someone reverts D3 back to a
# `| while read` pipe, this extraction still runs the (now-buggy) real
# code and the test fails. (Only the loop itself, not the `local bname=...`
# line above it -- this harness supplies its own $bname/$tmp_dir.)
D3_SNIPPET="$(awk '/while read -r p; do/,/done < <\(find/' "$PDF_SH")"

if [[ -z "$D3_SNIPPET" ]]; then
    fail "could not extract the D3 collection snippet from pdf.sh (markers moved?)"
else
    if echo "$D3_SNIPPET" | grep -q 'done < <('; then
        pass "extracted snippet uses process substitution (done < <(...)), not a piped subshell"
    else
        fail "extracted snippet does NOT use process substitution -- D3 regressed"
    fi

    _d3_collect() {
        local tmp_dir="$1"
        local bname="$2"
        local processed=()
        eval "$D3_SNIPPET"
        # Bash 3.2 (macOS default, no `mapfile`): guard the expansion so an
        # empty array doesn't trip `set -u` as "unbound variable".
        if [[ "${#processed[@]}" -gt 0 ]]; then
            printf '%s\n' "${processed[@]}"
        fi
    }

    D3_TMPDIR="$TEST_TMP/d3_pages"
    mkdir -p "$D3_TMPDIR"
    touch "$D3_TMPDIR/render_000_page_1.png" "$D3_TMPDIR/render_000_page_2.png" "$D3_TMPDIR/render_000_page_3.png"
    # A distractor file that must NOT match the glob.
    touch "$D3_TMPDIR/render_000.png"

    # Portable read loop instead of `mapfile`/`readarray` (bash 4+ only;
    # this repo targets bash 3.2, the macOS default).
    D3_RESULT=()
    while IFS= read -r d3_line; do
        D3_RESULT+=("$d3_line")
    done < <(_d3_collect "$D3_TMPDIR" "render_000")

    if [[ "${#D3_RESULT[@]}" -eq 3 ]]; then
        pass "processed collected all 3 fake *_page_*.png files (non-empty, correct count)"
    else
        fail "expected 3 collected pages, got ${#D3_RESULT[@]}: ${D3_RESULT[*]:-<empty>}"
    fi

    D3_MATCH=false
    if [[ "${#D3_RESULT[@]}" -gt 0 ]]; then
        for d3_item in "${D3_RESULT[@]}"; do
            [[ "$d3_item" == *"render_000_page_2.png" ]] && D3_MATCH=true
        done
    fi
    if [[ "$D3_MATCH" == "true" ]]; then
        pass "processed contains page 2 specifically (not just the first match)"
    else
        fail "processed should contain render_000_page_2.png, got: ${D3_RESULT[*]:-<empty>}"
    fi
fi

# ══════════════════════════════════════════════════════════════════
# D4 — --force-rtl/--rtl reaches all three engines (assert on the
# constructed command; nothing here actually renders a PDF)
# ══════════════════════════════════════════════════════════════════
echo ""
echo "=== D4: --rtl reaches puppeteer, weasyprint AND pandoc (constructed command) ==="

STUB_BIN="$TEST_TMP/stub_bin"
mkdir -p "$STUB_BIN"
NODE_LOG="$TEST_TMP/node_argv.log"
PANDOC_LOG="$TEST_TMP/pandoc_argv.log"

cat > "$STUB_BIN/node" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "$AMIR_TEST_NODE_LOG"
exit 0
EOF
cat > "$STUB_BIN/pandoc" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "$AMIR_TEST_PANDOC_LOG"
exit 0
EOF
chmod +x "$STUB_BIN/node" "$STUB_BIN/pandoc"

INPUT_MD="$TEST_TMP/tiny.md"
echo "# hi" > "$INPUT_MD"

# -- puppeteer (default engine): force_rtl is the LAST positional arg --
: > "$NODE_LOG"
PATH="$STUB_BIN:$PATH" AMIR_TEST_NODE_LOG="$NODE_LOG" \
    bash "$PDF_SH" "$INPUT_MD" --engine puppeteer --rtl -o "$TEST_TMP/out1.pdf" >/dev/null 2>&1
LAST_ARG="$(tail -1 "$NODE_LOG" | awk '{print $NF}')"
if [[ "$LAST_ARG" == "true" ]]; then
    pass "puppeteer: --rtl reaches render_puppeteer.js (last arg = true)"
else
    fail "puppeteer: --rtl should reach render_puppeteer.js as 'true' (got: '$LAST_ARG')"
fi

: > "$NODE_LOG"
PATH="$STUB_BIN:$PATH" AMIR_TEST_NODE_LOG="$NODE_LOG" \
    bash "$PDF_SH" "$INPUT_MD" --engine puppeteer -o "$TEST_TMP/out1b.pdf" >/dev/null 2>&1
LAST_ARG_NO_RTL="$(tail -1 "$NODE_LOG" | awk '{print $NF}')"
if [[ "$LAST_ARG_NO_RTL" == "false" ]]; then
    pass "puppeteer: without --rtl, force_rtl arg is 'false' (not force-on by default)"
else
    fail "puppeteer: without --rtl expected 'false', got '$LAST_ARG_NO_RTL'"
fi

# -- pandoc: -V dir=rtl only when --rtl is set --
: > "$PANDOC_LOG"
PATH="$STUB_BIN:$PATH" AMIR_TEST_PANDOC_LOG="$PANDOC_LOG" \
    bash "$PDF_SH" "$INPUT_MD" --engine pandoc --rtl -o "$TEST_TMP/out2.pdf" >/dev/null 2>&1
if tail -1 "$PANDOC_LOG" | grep -q -- '-V dir=rtl'; then
    pass "pandoc: --rtl reaches pandoc as '-V dir=rtl'"
else
    fail "pandoc: --rtl should add '-V dir=rtl'"
fi

: > "$PANDOC_LOG"
PATH="$STUB_BIN:$PATH" AMIR_TEST_PANDOC_LOG="$PANDOC_LOG" \
    bash "$PDF_SH" "$INPUT_MD" --engine pandoc -o "$TEST_TMP/out2b.pdf" >/dev/null 2>&1
if tail -1 "$PANDOC_LOG" | grep -q -- '-V dir=rtl'; then
    fail "pandoc: without --rtl, '-V dir=rtl' should NOT be present"
else
    pass "pandoc: without --rtl, no '-V dir=rtl' added"
fi

# -- weasyprint: python_cmd resolves to an absolute venv path when present
# (bypassing PATH), so it can't be stubbed the same way as node/pandoc.
# Assert on the constructed command at the source level instead.
if grep -qE 'render_weasy\.py" "\$abs_file" "\$tmp_out" "\$font_fa" "\$force_rtl"' "$PDF_SH"; then
    pass "weasyprint: --rtl (\$force_rtl) is wired into the render_weasy.py invocation (source-level)"
else
    fail "weasyprint: render_weasy.py invocation should pass \$force_rtl as its 4th arg"
fi

# ══════════════════════════════════════════════════════════════════
echo ""
echo "=== Summary ==="
echo "PASS: $PASS  FAIL: $FAIL"
if [[ "$FAIL" -gt 0 ]]; then
    echo ""
    echo "Failed cases:"
    for c in "${FAILED_CASES[@]}"; do echo "  - $c"; done
    exit 1
fi
exit 0
