#!/bin/bash

run_clean() {
    if [[ "$(uname -s)" != "Darwin" ]]; then
        echo "🪟 Windows: Please use PowerShell for system cleaning."
        return
    fi

    # ── Size helpers ──────────────────────────────────────────────────────────
    _sz() { du -sh "$@" 2>/dev/null | awk '{print $1}' | tail -1; }
    _sz_sum() { du -sch "$@" 2>/dev/null | tail -1 | awk '{print $1}'; }
    _sz_logs() {
        find ~/Library/Logs -type f -mtime +7 2>/dev/null \
            | xargs du -ch 2>/dev/null | tail -1 | awk '{print $1}'
    }

    # ── Labels ────────────────────────────────────────────────────────────────
    local -a LABELS=(
        "Trash"
        "User Caches"
        "System Logs (> 7 days)"
        "VS Code workspaceStorage"
        "macOS Aerials Screensaver"
        "Claude Desktop VM"
    )

    # ── Calculate sizes once ──────────────────────────────────────────────────
    printf "\n📊 Analyzing system clutter...\n"
    local -a SIZES
    SIZES[0]="$(_sz ~/.Trash)"
    SIZES[1]="$(_sz ~/Library/Caches)"
    SIZES[2]="$(_sz_logs)"
    SIZES[3]="$(_sz ~/Library/Application\ Support/Code/User/workspaceStorage)"
    SIZES[4]="$(_sz_sum \
        ~/Library/Application\ Support/com.apple.wallpaper/aerials \
        ~/Library/Containers/com.apple.wallpaper.extension.aerials/Data)"
    SIZES[5]="$(_sz ~/Library/Application\ Support/Claude/vm_bundles/claudevm.bundle)"

    for i in "${!SIZES[@]}"; do [[ -z "${SIZES[$i]}" ]] && SIZES[$i]="—"; done

    # ── Default: standard items ON, hidden caches OFF ─────────────────────────
    local -a SEL=(1 1 1 0 0 0)

    # ── Toggle menu ───────────────────────────────────────────────────────────
    while true; do
        clear
        printf "\n🧹  amir clean — macOS\n"
        printf "══════════════════════════════════════════════════════════\n"
        local i
        for i in "${!LABELS[@]}"; do
            local mark="[ ]"
            [[ "${SEL[$i]}" == "1" ]] && mark="[✓]"
            printf "  %s  %d.  %-38s  %s\n" \
                "$mark" "$((i+1))" "${LABELS[$i]}" "${SIZES[$i]}"
        done
        printf "══════════════════════════════════════════════════════════\n"
        printf "  Toggle: 1-6  │  Delete selected: d  │  Cancel: q\n"
        printf "  > "
        read -r input

        case "$input" in
            [1-6])
                local idx=$((input - 1))
                [[ "${SEL[$idx]}" == "1" ]] && SEL[$idx]=0 || SEL[$idx]=1
                ;;
            d|D)
                local any=0
                for i in "${!SEL[@]}"; do [[ "${SEL[$i]}" == "1" ]] && any=1; done
                if [[ "$any" == "0" ]]; then
                    printf "\n  ⚠️  Nothing selected.\n"; sleep 1; continue
                fi

                printf "\n🧹 Cleaning selected items...\n"

                [[ "${SEL[0]}" == "1" ]] && {
                    printf "  → Emptying Trash...\n"
                    rm -rf ~/.Trash/* 2>/dev/null
                    osascript -e 'tell application "Finder" to empty trash' 2>/dev/null
                }
                [[ "${SEL[1]}" == "1" ]] && {
                    printf "  → Clearing User Caches...\n"
                    find ~/Library/Caches -mindepth 1 -delete 2>/dev/null
                }
                [[ "${SEL[2]}" == "1" ]] && {
                    printf "  → Removing old System Logs...\n"
                    find ~/Library/Logs -type f -mtime +7 -delete 2>/dev/null
                }
                [[ "${SEL[3]}" == "1" ]] && {
                    printf "  → Removing VS Code workspaceStorage...\n"
                    rm -rf ~/Library/Application\ Support/Code/User/workspaceStorage 2>/dev/null
                }
                [[ "${SEL[4]}" == "1" ]] && {
                    printf "  → Removing Aerials Screensaver cache...\n"
                    rm -rf ~/Library/Application\ Support/com.apple.wallpaper/aerials 2>/dev/null
                    rm -rf ~/Library/Containers/com.apple.wallpaper.extension.aerials/Data/* 2>/dev/null
                }
                [[ "${SEL[5]}" == "1" ]] && {
                    printf "  → Removing Claude Desktop VM bundle...\n"
                    rm -rf ~/Library/Application\ Support/Claude/vm_bundles/claudevm.bundle 2>/dev/null
                }

                printf "\n✅ Done!\n"
                break
                ;;
            q|Q)
                printf "\n❌ Cancelled.\n"
                break
                ;;
        esac
    done
}
