#!/bin/bash
# tests/test_help.sh — smoke test: every command/subcommand's --help must
# exit 0 and print more than 3 lines. Run from anywhere:
#   bash tests/test_help.sh
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMIR_ROOT="$(dirname "$SCRIPT_DIR")"
AMIR="$AMIR_ROOT/amir"

PASS=0
FAIL=0
FAILED_CASES=()

check() {
    local desc="$1"
    shift
    local out
    out=$("$AMIR" --no-venv "$@" 2>&1 </dev/null)
    local rc=$?
    local lines
    lines=$(printf '%s\n' "$out" | wc -l | tr -d ' ')

    if [[ $rc -eq 0 && $lines -gt 3 ]]; then
        PASS=$((PASS + 1))
        printf "  OK   [%3d lines] %s\n" "$lines" "$desc"
    else
        FAIL=$((FAIL + 1))
        FAILED_CASES+=("$desc (exit=$rc lines=$lines)")
        printf "  FAIL [exit=%s lines=%s] %s\n" "$rc" "$lines" "$desc"
    fi
}

echo "=== Top-level commands ==="
check "video --help"               video --help
check "download --help"            download --help
check "init-project --help"        init-project --help
check "sync-constitution --help"   sync-constitution --help
check "update --help"              update --help
check "update-projects --help"     update-projects --help
check "pdf --help"                 pdf --help
check "info --help"                info --help
check "img --help"                 img --help
check "transfer --help"            transfer --help
check "lock --help"                lock --help
check "unlock --help"              unlock --help
check "clean --help"               clean --help
check "qr --help"                  qr --help
check "weather --help"             weather --help
check "short --help"               short --help
check "pass --help"                pass --help
check "speed --help"               speed --help
check "todo --help"                todo --help
check "clip --help"                clip --help
check "router --help"              router --help
check "dashboard --help"           dashboard --help
check "watermark --help"           watermark --help
check "subtitle --help"            subtitle --help
check "apply --help"               apply --help
check "keyboard --help"            keyboard --help
check "trend --help"               trend --help
check "research --help"            research --help
check "skill --help"               skill --help
check "audio --help"               audio --help
check "scripts --help"             scripts --help
check "doctor --help"              doctor --help
check "split --help"               split --help
check "help"                       help

echo ""
echo "=== amir help <command> delegation ==="
check "help video"                 help video
check "help audio"                 help audio
check "help img"                   help img
check "help apply"                 help apply
check "help job"                   help job
check "help phd"                   help phd
check "help skill"                 help skill
check "help subtitle"              help subtitle
check "help pdf"                   help pdf
check "help download"              help download
check "help router"                help router
check "help update"                help update

echo ""
echo "=== video subcommands ==="
check "video concat --help"        video concat --help
check "video cut --help"           video cut --help
check "video trim --help"          video trim --help
check "video pip --help"           video pip --help
check "video convert --help"       video convert --help
check "video record --help"        video record --help
check "video outro --help"         video outro --help
check "video tiktok --help"        video tiktok --help
check "video tt --help"            video tt --help
check "video split --help"         video split --help

echo ""
echo "=== audio subcommands ==="
check "audio extract --help"       audio extract --help
check "audio convert --help"       audio convert --help
check "audio cut --help"           audio cut --help
check "audio normalize --help"     audio normalize --help
check "audio fade --help"          audio fade --help
check "audio trim-silence --help"  audio trim-silence --help
check "audio split --help"         audio split --help
check "audio concat --help"        audio concat --help
check "audio to-video --help"      audio to-video --help
check "audio youtube --help"       audio youtube --help
check "audio transcribe --help"    audio transcribe --help

echo ""
echo "=== img subcommands ==="
check "img crop --help"            img crop --help
check "img convert --help"         img convert --help
check "img stack --help"           img stack --help
check "img upscale --help"         img upscale --help
check "img lab --help"             img lab --help
check "img scan --help"            img scan --help
check "img rotate --help"          img rotate --help
check "img compress --help"        img compress --help
check "img burst --help"           img burst --help
check "img extend --help"          img extend --help

echo ""
echo "=== apply / job / phd / skill subcommands ==="
check "apply phd --help"           apply phd --help
check "apply job --help"           apply job --help
check "skill harvest --help"       skill harvest --help
check "skill search --help"        skill search --help
check "skill list --help"          skill list --help
check "skill show --help"          skill show --help

echo ""
echo "=== pdf subcommands ==="
check "pdf linkedin-post --help"   pdf linkedin-post --help
check "pdf split --help"           pdf split --help

echo ""
echo "=== no-arg behavior (REQUIRES args -> usage, exit 0) ==="
check "video (no args)"            video
check "audio (no args)"            audio
check "img (no args)"              img
check "info (no args)"             info
check "subtitle (no args)"         subtitle
check "download (no args)"         download
check "apply job (no args)"        apply job
check "apply phd (no args)"        apply phd

echo ""
echo "=== no-regression: commands that stay useful with no args ==="
check "doctor (no args)"           doctor
check "update --check"             update --check

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
