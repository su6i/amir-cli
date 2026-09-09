#!/bin/bash

# amir help              — show the full command overview (below)
# amir help <command>    — delegate to that command's own --help (same
#                           source+call pattern as the `amir` entry script's
#                           dispatcher, so this never drifts from reality)
run_help() {
    local target="$1"

    if [[ -n "$target" && "$target" != "--help" && "$target" != "-h" ]]; then
        case "$target" in
            video)              source "$LIB_DIR/commands/video.sh"; run_video --help ;;
            download)           source "$LIB_DIR/commands/download.sh"; run_download --help ;;
            init-project)       source "$LIB_DIR/commands/init-project.sh"; run_init_project --help ;;
            sync-constitution)  source "$LIB_DIR/commands/sync-constitution.sh"; run_sync_constitution --help ;;
            update)             source "$LIB_DIR/commands/update.sh"; run_update --help ;;
            update-projects)    source "$LIB_DIR/commands/update-projects.sh"; run_update_projects --help ;;
            pdf)                "$LIB_DIR/commands/pdf.sh" --help ;;
            info)               source "$LIB_DIR/commands/info.sh"; run_info --help ;;
            img)                source "$LIB_DIR/commands/img.sh"; run_img --help ;;
            transfer)           source "$LIB_DIR/commands/transfer.sh"; run_transfer --help ;;
            lock)                source "$LIB_DIR/commands/lock.sh"; run_lock --help ;;
            unlock)              source "$LIB_DIR/commands/lock.sh"; run_unlock --help ;;
            clean)               source "$LIB_DIR/commands/clean.sh"; run_clean --help ;;
            qr)                  source "$LIB_DIR/commands/qr.sh"; run_qr --help ;;
            weather)             source "$LIB_DIR/commands/weather.sh"; run_weather --help ;;
            short)                source "$LIB_DIR/commands/short.sh"; run_short --help ;;
            pass)                 source "$LIB_DIR/commands/pass.sh"; run_pass --help ;;
            speed)                source "$LIB_DIR/commands/speed.sh"; run_speed --help ;;
            todo)                 source "$LIB_DIR/commands/todo.sh"; run_todo --help ;;
            clip)                 source "$LIB_DIR/commands/clip.sh"; run_clip --help ;;
            router|ai)            source "$LIB_DIR/commands/router.sh"; run_router --help ;;
            dashboard)            source "$LIB_DIR/commands/dashboard.sh"; run_dashboard --help ;;
            watermark)            source "$LIB_DIR/commands/watermark.sh"; run_watermark --help ;;
            subtitle)             source "$LIB_DIR/commands/subtitle.sh"; run_subtitle --help ;;
            apply)                source "$LIB_DIR/commands/apply.sh"; run_apply --help ;;
            keyboard)             source "$LIB_DIR/commands/keyboard.sh"; run_keyboard --help ;;
            trend)                source "$LIB_DIR/commands/trend.sh"; run_trend --help ;;
            research)             source "$LIB_DIR/commands/research.sh"; run_research --help ;;
            skill)                source "$LIB_DIR/commands/skill.sh"; run_skill --help ;;
            audio)                source "$LIB_DIR/commands/audio.sh"; run_audio --help ;;
            scripts)              source "$LIB_DIR/commands/scripts.sh"; run_scripts --help ;;
            doctor)               source "$LIB_DIR/commands/doctor.sh"; run_doctor --help ;;
            split)                echo "Usage: amir split <media_file> <mb>" ;;
            llm-lists)            source "$LIB_DIR/commands/llm-lists.sh"; llm_lists --help ;;
            job)                  source "$LIB_DIR/commands/apply.sh"; source "$LIB_DIR/commands/job.sh"; run_job --help ;;
            phd)                  source "$LIB_DIR/commands/apply.sh"; source "$LIB_DIR/commands/phd.sh"; run_phd --help ;;
            *)
                echo "❌ Unknown command: $target"
                echo ""
                echo "Run 'amir help' for the full command list."
                return 1
                ;;
        esac
        return $?
    fi

    print_header "Amir CLI Help"
    echo "Usage: $(basename "$0") <command> [args]"
    echo "       $(basename "$0") help <command>     Show that command's own --help"
    echo ""
    echo -e "${BOLD}Multimedia:${NC}"
    echo "  video <file> [res] [q]       Compress/Process video (Smart Selection)"
    echo "  video concat <files...>      Concatenate videos in the given order"
    echo "  video cut / trim <file> [opts]  Cut / delete range / extract range (with -s/-e, -d, -x)"
    echo "  video pip <main> --pip <f>   Picture-in-picture overlay"
    echo "  video convert <file>         Convert container format (stream copy)"
    echo "  video record [opts]          Screen recording (AVFoundation)"
    echo "  video outro <file> --image I Append a still-image outro card"
    echo "  video tiktok / tt <url>      Download from TikTok"
    echo "  video batch [res]            Batch process videos in folder"
    echo "  video codecs                 Show available codecs"
    echo "  download <url> [opts]        Download video/photo/carousel (YouTube, IG, TikTok, X, 1000+ sites)"
    echo "  audio <subcmd> [args]        Audio tools (extract, cut, normalize, fade, concat, to-video, youtube...)"
    echo "  split <file> <mb>            Split audio/video into ~N MB chunks"
    echo "  img <subcmd> <file> [opts]   Resize/crop/upscale/round/rotate/pad/convert/stack/extend/compress/burst"
    echo "  info <file>                  Show detailed file info"
    echo "  subtitle <file> [opts]       Generate subtitles (AI Rendering)"
    echo "  pdf <file...> [opts]         Multi-engine PDF renderer (+ linkedin-post, split subcommands)"
    echo "  watermark <file> [opts]      Apply an image/text watermark"

    echo ""
    echo -e "${BOLD}Utilities:${NC}"
    echo "  clip <text|file>             Smart clipboard tool"
    echo "  clean                        Clean system cache/trash"
    echo "  transfer <file>              Upload a file, copy the link to clipboard"
    echo "  lock / unlock <file>         GPG-encrypt / decrypt a file"
    echo "  qr <text|link|phone|email>   Generate a QR code"
    echo "  weather [city]               Quick weather report"
    echo "  short <url>                  Shorten a URL"
    echo "  pass [length]                Generate a random password"
    echo "  speed                        Network quality test"
    echo "  todo [task|list|done N]      Manage local todo list"
    echo "  dashboard                    Disk space, TODOs, calendar overview"
    echo "  keyboard [lang] [opts]       Apple keyboard layout diagram (fr/en/fa)"

    echo ""
    echo -e "${BOLD}Research & Trends:${NC}"
    echo "  trend [keyword]              Trending content & research (default: YouTube most viewed)"
    echo "  trend [keyword] --source S   Source: youtube github arxiv reddit producthunt indiehackers"
    echo "  trend [keyword] --lang CODE  Language filter: fa en de ar zh ... (default: any)"
    echo "  trend [keyword] --region CC  Region: IR US GB DE ... (default: global)"
    echo "  trend [keyword] --metric M   Sort by: views likes stars citations comments"
    echo "  trend [keyword] --ideas      Generate AI ideas from collected data"
    echo "  research discover --keywords K [opts]   Find PhD/postdoc supervisors by topic (ArXiv+DBLP)"
    echo "  research professor --professor N [opts] Deep-research a specific professor + draft email"

    echo ""
    echo -e "${BOLD}Applications (PhD/Job tracker):${NC}"
    echo "  apply [subcmd]                Sync + CV/cover-letter generator — see 'amir help apply'"
    echo "  apply phd [subcmd]            PhD application tracker"
    echo "  apply job [subcmd]            Job application tracker"

    echo ""
    echo -e "${BOLD}AI & Productivity:${NC}"
    echo "  router \"<prompt>\" [--model M]  AI gateway: gemini/gemma(free), deepseek, minimax, grok + memory"
    echo "  router audit | cost | models  Cost ledger / dashboard / provider model lists"
    echo "  llm-lists <provider>          List a provider's available models"
    echo "  scripts [id|list]            Pick & run a saved script (no args = menu; includes"
    echo "                                weather/qr/pass/dashboard/transfer/short/lock/unlock/speed)"
    echo "  skill <subcmd>                Search GitHub / harvest / list / show skill files"

    echo ""
    echo -e "${BOLD}System:${NC}"
    echo "  help [command]               Show this overview, or one command's own --help"
    echo "  doctor                       Check external tools/repos/venv, print a fix command for each missing one"
    echo "  update [opts]                Update repo, Python/Node deps, and uv-tool copies (yt-dlp etc); see --check/--brew"
    echo "  update-projects [dir]         Refresh agent-constitution hooks/link across all projects"
    echo "  init-project [dir]            Scaffold a project with the agent-constitution"
    echo "  sync-constitution [dir]        Pull the latest agent-constitution into one project"
    echo ""
    echo "Run 'amir help <command>' for any command's full usage."
    echo ""
}
