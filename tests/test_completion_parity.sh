#!/bin/bash
# Contract test: every verb offered by zsh completion (completions/_amir) must be
# reachable in the matching dispatcher. A verb offered but not handled is a bug.
# Bash 3.2 compatible; no network.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMP="$ROOT/completions/_amir"
CMD="$ROOT/lib/commands"
MISMATCH=0
CHECKED=0

# Print the verbs of a completion array: lines like 'verb:description'.
verbs_of_array() {
    awk -v name="$1" '
        $0 ~ "^[[:space:]]*" name "=\\(" { if ($0 ~ /\)[[:space:]]*$/) next; on=1; next }
        on && /^[[:space:]]*\)/ { on=0 }
        on { print }
    ' "$COMP" | sed -n "s/^[[:space:]]*['\"]\\([A-Za-z0-9_-]*\\):.*/\\1/p"
}

# Verbs of the inline audio _alternative list: (verb\:Desc ...)
audio_verbs() {
    grep "acmds:Audio Command" "$COMP" | sed 's/.*((//' |
        grep -o '[A-Za-z0-9_-]*\\:' | sed 's/\\://'
}

# True if file has a case arm or [[ == ]] test for the verb.
reachable() {
    local verb="$1"; shift
    local f
    for f in "$@"; do
        [[ -f "$f" ]] || continue
        grep -E -q "^[[:space:]]*([A-Za-z0-9_|*-]+\|)?${verb}(\|[A-Za-z0-9_|*-]+)?\)|==[[:space:]]*\"?${verb}\"?[[:space:]]*(\]\]|\|\|)|\"?${verb}\"?[[:space:]]*\)" "$f" && return 0
    done
    return 1
}

check() { # label verb file...
    local label="$1" verb="$2"; shift 2
    CHECKED=$((CHECKED+1))
    if ! reachable "$verb" "$@"; then
        echo "MISMATCH $label $verb: offered by completion, no dispatcher arm in $(basename "$1")"
        MISMATCH=$((MISMATCH+1))
    fi
}

echo "=== completion / dispatcher parity ==="

# array-name  command-label  dispatcher-file
for spec in \
    "commands|amir|$ROOT/amir" \
    "video_subcmds|video|$CMD/video.sh" \
    "todo_opts|todo|$CMD/todo.sh" \
    "router_cmds|router|$CMD/router.sh" \
    "apply_cmds|apply|$CMD/apply.sh" \
    "img_actions|img|$CMD/img.sh" \
    "script_opts|scripts|$CMD/scripts.sh"
do
    arr="${spec%%|*}"; rest="${spec#*|}"; label="${rest%%|*}"; file="${rest#*|}"
    for v in $(verbs_of_array "$arr"); do
        if [[ "$arr" == "commands" ]]; then
            # top-level command: case arm in the entry point, or a lib/commands module
            CHECKED=$((CHECKED+1))
            if ! reachable "$v" "$ROOT/amir" && [[ ! -f "$CMD/$v.sh" ]]; then
                echo "MISMATCH amir $v: offered by completion, no dispatcher arm in amir"
                MISMATCH=$((MISMATCH+1))
            fi
        else
            check "$label" "$v" "$file"
        fi
    done
done

for v in $(audio_verbs); do
    check audio "$v" "$CMD/audio.sh"
done

echo "Checked $CHECKED verbs; mismatches: $MISMATCH"
[[ $MISMATCH -eq 0 ]]
