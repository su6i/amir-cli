#!/bin/bash

run_clean() {
    if [[ "$(uname -s)" != "Darwin" ]]; then
        echo "🪟 Windows: Please use PowerShell for system cleaning."
        return
    fi

    # ── Single-keypress reader (handles ESC sequences for arrow keys) ─────────
    _read_key() {
        local key rest
        IFS= read -r -s -n1 key
        if [[ "$key" == $'\x1b' ]]; then
            IFS= read -r -s -n2 -t 1 rest 2>/dev/null || rest=""
            key="${key}${rest}"
        fi
        printf '%s' "$key"
    }

    # ── Size helpers ──────────────────────────────────────────────────────────
    _sz()     { du -sh "$@" 2>/dev/null | awk '{print $1}' | tail -1; }
    _sz_sum() { du -sch "$@" 2>/dev/null | tail -1 | awk '{print $1}'; }
    _sz_logs() {
        find ~/Library/Logs -type f -mtime +7 2>/dev/null \
            | xargs du -ch 2>/dev/null | tail -1 | awk '{print $1}'
    }

    # ── Orphan detection (app no longer installed → its leftover data is safe) ─
    local UTM_ORPHANED=0 DOCKER_ORPHANED=0
    [[ ! -d "/Applications/UTM.app" ]] && UTM_ORPHANED=1
    [[ ! -d "/Applications/Docker.app" ]] && DOCKER_ORPHANED=1

    # ── Items ─────────────────────────────────────────────────────────────────
    local -a LABELS=(
        "Trash"
        "User Caches"
        "System Logs (> 7 days)"
        "VS Code workspaceStorage"
        "macOS Aerials Screensaver"
        "Claude Desktop VM"
        "Claude Desktop Update Cache"
        "Docker Installer Leftover"
        "UTM Container (orphaned)"
        "Docker Desktop Container (orphaned)"
    )

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
    SIZES[6]="$(_sz ~/Library/Caches/com.anthropic.claudefordesktop.ShipIt)"
    SIZES[7]="$(_sz ~/Library/Application\ Support/com.docker.install)"
    if [[ "$UTM_ORPHANED" == "1" ]]; then
        SIZES[8]="$(_sz ~/Library/Containers/com.utmapp.UTM)"
    else
        SIZES[8]="UTM.app installed — skipped"
    fi
    if [[ "$DOCKER_ORPHANED" == "1" ]]; then
        SIZES[9]="$(_sz ~/Library/Containers/com.docker.docker)"
    else
        SIZES[9]="Docker.app installed — skipped"
    fi

    for i in "${!SIZES[@]}"; do [[ -z "${SIZES[$i]}" ]] && SIZES[$i]="—"; done

    # ── State ─────────────────────────────────────────────────────────────────
    local -a SEL=(1 1 1 0 0 0 0 0 0 0)   # first 3 on by default
    local cursor=0
    local n=${#LABELS[@]}
    local msg=""

    # ── Render ────────────────────────────────────────────────────────────────
    _draw() {
        clear
        printf "\n🧹  amir clean — macOS\n"
        printf "══════════════════════════════════════════════════════════\n"
        local i
        for i in "${!LABELS[@]}"; do
            local mark="[ ]"
            [[ "${SEL[$i]}" == "1" ]] && mark="[✓]"
            if [[ "$i" == "$cursor" ]]; then
                printf "  \033[7m%s  %d.  %-36s  %s\033[0m\n" \
                    "$mark" "$((i+1))" "${LABELS[$i]}" "${SIZES[$i]}"
            else
                printf "  %s  %d.  %-36s  %s\n" \
                    "$mark" "$((i+1))" "${LABELS[$i]}" "${SIZES[$i]}"
            fi
        done
        printf "══════════════════════════════════════════════════════════\n"
        printf "  ↑↓ Move  │  Space/1-9,0 Toggle  │  Enter/d Delete  │  q Cancel\n"
        [[ -n "$msg" ]] && printf "\n  \033[33m%s\033[0m\n" "$msg"
    }

    # ── Main loop ─────────────────────────────────────────────────────────────
    while true; do
        _draw
        msg=""

        local key
        key="$(_read_key)"

        case "$key" in
            $'\x1b[A')   # Arrow Up
                [[ $cursor -gt 0 ]] && cursor=$((cursor - 1))
                ;;
            $'\x1b[B')   # Arrow Down
                [[ $cursor -lt $((n-1)) ]] && cursor=$((cursor + 1))
                ;;
            ' ')          # Space — toggle highlighted row
                [[ "${SEL[$cursor]}" == "1" ]] && SEL[$cursor]=0 || SEL[$cursor]=1
                ;;
            [1-9])        # Number — jump + toggle
                local idx=$((key - 1))
                cursor=$idx
                [[ "${SEL[$idx]}" == "1" ]] && SEL[$idx]=0 || SEL[$idx]=1
                ;;
            0)            # 0 — jump + toggle 10th item
                local idx=9
                cursor=$idx
                [[ "${SEL[$idx]}" == "1" ]] && SEL[$idx]=0 || SEL[$idx]=1
                ;;
            ''|$'\n'|$'\r'|d|D)
                local any=0 i
                for i in "${!SEL[@]}"; do [[ "${SEL[$i]}" == "1" ]] && any=1; done
                if [[ "$any" == "0" ]]; then
                    msg="⚠️  Nothing selected — toggle items first."
                    continue
                fi

                clear
                printf "\n🧹 Cleaning selected items...\n\n"

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
                [[ "${SEL[6]}" == "1" ]] && {
                    printf "  → Removing Claude Desktop update cache (ShipIt)...\n"
                    rm -rf ~/Library/Caches/com.anthropic.claudefordesktop.ShipIt 2>/dev/null
                }
                [[ "${SEL[7]}" == "1" ]] && {
                    printf "  → Removing Docker installer leftover...\n"
                    rm -rf ~/Library/Application\ Support/com.docker.install 2>/dev/null
                }
                [[ "${SEL[8]}" == "1" ]] && {
                    if [[ "$UTM_ORPHANED" == "1" ]]; then
                        printf "  → Removing orphaned UTM container...\n"
                        rm -rf ~/Library/Containers/com.utmapp.UTM 2>/dev/null
                    else
                        printf "  → Skipping UTM container — UTM.app is installed.\n"
                    fi
                }
                [[ "${SEL[9]}" == "1" ]] && {
                    if [[ "$DOCKER_ORPHANED" == "1" ]]; then
                        printf "  → Removing orphaned Docker Desktop container...\n"
                        rm -rf ~/Library/Containers/com.docker.docker 2>/dev/null
                    else
                        printf "  → Skipping Docker Desktop container — Docker.app is installed.\n"
                    fi
                }

                printf "\n✅ Done!\n"
                break
                ;;
            q|Q|$'\x1b')
                printf "\n❌ Cancelled.\n"
                break
                ;;
        esac
    done
}
