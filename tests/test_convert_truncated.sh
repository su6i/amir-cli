#!/bin/bash
# amir video convert: truncated mp4 (ftyp + mdat, no moov) must give a clear message.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok() { echo "  OK   $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL $1"; FAIL=$((FAIL+1)); }

# ftyp box (24 bytes) + mdat box header with payload, no moov
printf '\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2' > "$TMP/broken.mp4"
printf '\x00\x00\x10\x00mdat' >> "$TMP/broken.mp4"
head -c 4088 /dev/zero >> "$TMP/broken.mp4"

echo "=== convert truncated mp4 ==="
out=$(cd "$TMP" && HOME="$TMP" bash "$ROOT/amir" video convert broken.mp4 --cpu 2>&1); rc=$?
[[ $rc -ne 0 ]] && ok "exits non-zero" || bad "exit code $rc"
[[ "$out" == *"incomplete or truncated download"* ]] && ok "truncated-download message shown" || bad "message missing: $out"
[[ "$out" != *"--reencode"* ]] && ok "no --reencode mention" || bad "--reencode mentioned"
[[ ! -e "$TMP/broken.mp4.mp4" && ! -e "$TMP/broken_converted.mp4" ]] && ok "no output file left" || bad "stray output"

echo "======================================"
echo "PASS: $PASS   FAIL: $FAIL"
[[ $FAIL -eq 0 ]]
