#!/usr/bin/env bash
# amir skill — search GitHub for high-starred repos and create skill files

SKILL_DIR="${AMIR_ROOT}/.agent/skills"

run_skill() {
    local subcmd="${1:-help}"
    shift 2>/dev/null

    case "$subcmd" in
        harvest)  skill_harvest "$@" ;;
        list)     skill_list "$@" ;;
        search)   skill_search "$@" ;;
        show)     skill_show "$@" ;;
        *)        skill_help ;;
    esac
}

skill_help() {
    cat <<'EOF'
Usage: amir skill <subcommand> [options]

Subcommands:
  harvest <query> [--min-stars N] [--limit N] [--pick N]
      Search GitHub, rank by stars, fetch READMEs, generate skill file

  search <query> [--min-stars N] [--limit N]
      Search GitHub and display results without creating a skill

  list [--grep PATTERN]
      List all existing skill files

  show <skill-name>
      Display contents of a skill file

Examples:
  amir skill harvest "persian tts voice cloning"
  amir skill harvest "youtube automation" --min-stars 1000 --limit 20
  amir skill search "davinci resolve python" --min-stars 500
  amir skill list --grep video
  amir skill show opensource-tts
EOF
}

# ── List existing skills ───────────────────────────────────────────────────────
skill_list() {
    local grep_pat=""
    [[ "$1" == "--grep" ]] && grep_pat="$2"

    echo "📚 Skills in ${SKILL_DIR}:"
    echo ""
    local count=0
    while IFS= read -r f; do
        local name
        name=$(basename "$f" .md)
        local desc
        desc=$(grep -m1 "^description:" "$f" 2>/dev/null | sed 's/description: *//;s/^"//;s/"$//')
        if [[ -z "$grep_pat" || "$name $desc" == *"$grep_pat"* ]]; then
            printf "  %-40s %s\n" "$name" "${desc:0:70}"
            count=$(( count + 1 ))
        fi
    done < <(find "$SKILL_DIR" -name "*.md" | sort)
    echo ""
    echo "Total: $count skills"
}

# ── Show a skill ──────────────────────────────────────────────────────────────
skill_show() {
    local name="${1:-}"
    [[ -z "$name" ]] && echo "❌ Usage: amir skill show <skill-name>" && return 1

    local path="${SKILL_DIR}/${name}.md"
    [[ ! -f "$path" ]] && path="${SKILL_DIR}/${name}"
    [[ ! -f "$path" ]] && echo "❌ Skill not found: $name" && return 1

    cat "$path"
}

# ── Search GitHub ─────────────────────────────────────────────────────────────
skill_search() {
    local query="" min_stars=200 limit=15

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --min-stars) min_stars="$2"; shift 2 ;;
            --limit)     limit="$2";     shift 2 ;;
            *) query="${query:+$query }$1"; shift ;;
        esac
    done

    [[ -z "$query" ]] && echo "❌ Usage: amir skill search <query>" && return 1

    echo "🔍 Searching GitHub: \"$query\" (min ⭐${min_stars})"
    echo ""

    local encoded_query
    encoded_query=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$query")

    gh api "search/repositories?q=${encoded_query}+stars:>=${min_stars}&sort=stars&per_page=${limit}" \
        --jq '.items[] | "\(.stargazers_count)\t\(.full_name)\t\(.description // "no description")"' 2>/dev/null \
        | sort -rn \
        | awk -F'\t' '{printf "%6s⭐  %-45s %s\n", $1, $2, substr($3,1,60)}'
}

# ── Harvest: search → fetch → create skill ────────────────────────────────────
skill_harvest() {
    local query="" min_stars=500 limit=20 pick=5 out_name=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --min-stars) min_stars="$2"; shift 2 ;;
            --limit)     limit="$2";     shift 2 ;;
            --pick)      pick="$2";      shift 2 ;;
            -o|--output) out_name="$2";  shift 2 ;;
            *) query="${query:+$query }$1"; shift ;;
        esac
    done

    [[ -z "$query" ]] && echo "❌ Usage: amir skill harvest <query> [options]" && return 1

    if ! command -v gh &>/dev/null; then
        echo "❌ gh CLI required. Install: brew install gh"
        return 1
    fi

    echo "🔍 Searching GitHub: \"$query\" (min ⭐${min_stars}, top ${pick} repos)"
    echo ""

    local encoded_query
    encoded_query=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$query")

    local results
    results=$(gh api "search/repositories?q=${encoded_query}+stars:>=${min_stars}&sort=stars&per_page=${limit}" \
        --jq '.items[:'"$pick"'] | .[] | "\(.stargazers_count)\t\(.full_name)\t\(.description // "")\t\(.html_url)"' 2>/dev/null \
        | sort -rn)

    if [[ -z "$results" ]]; then
        echo "❌ No repos found. Try lower --min-stars or different query."
        return 1
    fi

    echo "📦 Top repos found:"
    local i=1
    while IFS=$'\t' read -r stars repo desc url; do
        printf "  %d. %6s⭐  %-40s %s\n" "$i" "$stars" "$repo" "${desc:0:50}"
        i=$(( i + 1 ))
    done <<< "$results"
    echo ""

    # Build output filename from query
    if [[ -z "$out_name" ]]; then
        out_name=$(echo "$query" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
        out_name="${out_name}.md"
    fi
    local out_path="${SKILL_DIR}/${out_name}"

    echo "📥 Fetching READMEs..."
    local combined_content=""
    local repo_list=""
    while IFS=$'\t' read -r stars repo desc url; do
        echo "   → ${repo} (${stars}⭐)"
        local readme
        readme=$(gh api "repos/${repo}/readme" --jq '.content' 2>/dev/null \
            | python3 -c "import sys,base64; print(base64.b64decode(sys.stdin.read().strip()).decode('utf-8','replace'))" 2>/dev/null \
            | head -200)
        if [[ -n "$readme" ]]; then
            combined_content+="

=== REPO: ${repo} (${stars}⭐) ===
Description: ${desc}

${readme}
"
            repo_list+="- [${repo}](${url}) — ${desc}
"
        fi
    done <<< "$results"

    if [[ -z "$combined_content" ]]; then
        echo "❌ Could not fetch any READMEs."
        return 1
    fi

    echo ""
    echo "🤖 Generating skill file with Claude..."

    local today
    today=$(date +%Y-%m-%d)
    local skill_name
    skill_name=$(basename "$out_name" .md)

    local prompt="You are writing a skill file for an AI agent system (Claude Code).
The skill should be practical, code-heavy, and focused on what an AI agent needs to USE these tools, not just understand them.

Query that produced these repos: \"${query}\"

Here are the top GitHub READMEs:
${combined_content}

Write a skill markdown file with this exact frontmatter:
---
title: \"Skill: ${skill_name}\"
description: [one-line summary of what this skill covers]
location: .agent/skills/${skill_name}.md
agent_priority: Standard
last_updated: ${today}
sources:
${repo_list}---

Then write the skill body:
- Decision table at the top (which tool for which use case)
- Installation for each major tool
- Practical Python/CLI code examples
- Common pitfalls
- Keep total under 450 lines
- Focus on code, not prose"

    local skill_content
    skill_content=$(echo "$prompt" | claude --print 2>/dev/null)

    if [[ -z "$skill_content" ]]; then
        echo "⚠️  claude CLI not available — writing raw README summary instead."
        skill_content="---
title: \"Skill: ${skill_name}\"
description: Auto-harvested from GitHub top repos for: ${query}
location: .agent/skills/${skill_name}.md
agent_priority: Standard
last_updated: ${today}
sources:
${repo_list}---

# Skill: ${skill_name}

> Auto-harvested on ${today} from top GitHub repos for query: \"${query}\"
> Review and refine this file manually.

${combined_content}"
    fi

    echo "$skill_content" > "$out_path"

    local lines
    lines=$(wc -l < "$out_path")
    echo "✅ Skill written: ${out_path} (${lines} lines)"
    echo ""
    echo "💡 Review with:  amir skill show ${skill_name}"
    echo "💡 Commit with:  git add -f .agent/skills/${out_name}"
}
