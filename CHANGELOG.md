# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## 2026-07-24 — fix: dedupe cover-art stream in embed_video_cover_art()

Follow-up to the 2026-07-23 mac-playback fixes: even with those fixed, a
downloaded reel (`Video_by_yashar_1280p.mp4`, already `h264`/`aac`, no codec
issue at all) still would not play, thumbnail visible but video refusing to
load.

`ffprobe` showed **two** `mjpeg` video streams instead of one: the correctly
tagged cover (`attached_pic=1`) plus a second `mjpeg` stream with every
disposition flag at `0` — not `attached_pic`, not even `default`. A stray
video track like that (single frame, ~0 duration, not marked as a thumbnail)
is exactly the kind of malformed asset AVFoundation/QuickTime/Quick Look
reject outright, even though the file's own poster-frame metadata (and thus
the Finder thumbnail) stays intact.

Root cause, reproduced locally with a throwaway test file: `embed_video_cover_art()`
used a blanket `-map 0 -map 1`, so any *existing* cover-art stream from a
prior embed call (e.g. `find_existing_downloaded_video` reusing an
already-processed file across two `amir download` runs of the same URL) got
folded back into the output — and lost its `attached_pic` disposition in the
process, since `-disposition:v:1` only ever targets the newest stream. Every
extra call added one more zombie video stream.

- **fix(video):** `embed_video_cover_art()` now maps `0:v:0 / 0:a? / 1:v:0`
  instead of `0 / 1`, so it always rebuilds from just the primary video +
  audio + one fresh cover, regardless of how many stray streams the input
  already carries. Verified idempotent by running the fixed command twice in
  a row on the same file (and once on an already-corrupted double-cover
  file) — always exactly 3 streams, single `attached_pic` cover, both times.
- The reported broken file was repaired in place with the same corrected
  ffmpeg invocation (re-muxed, no re-encode) rather than requiring a
  re-download.

---

## 2026-07-23 — fix: restore macOS-playable video normalization

`ensure_mac_playable_video()` in `lib/commands/video.sh` was regressed by the
2026-06-22 PO-Token commit: `av1`/`av01`/`vp9` video codecs and `opus`/`vorbis`
audio codecs were added to the "already compatible" list, even though the
comment right above them still warned that vp9/av1 in an mp4 container is
unreliable on macOS. As a result, `amir download`/`amir dl` stopped
transcoding such files to H.264/AAC, and Quick Look (spacebar preview) could
no longer play them.

Confirmed against a real Instagram reel download
(`vp9` video / `aac` audio in an `.mp4` container) that Quick Look failed to
play before the fix and played correctly after re-running normalization.

- **fix(video):** removed `av1`/`av01`/`vp9`/`opus`/`vorbis` from the
  compatibility allow-list in `ensure_mac_playable_video()`, restoring the
  pre-2026-06-22 behavior of transcoding them to H.264/AAC. The `--normalize`
  / force-normalize flag added in that same commit is unaffected.
- **fix(download):** the fix above turned out not to be enough on its own —
  `_download_instagram()`'s `yt-dlp -J` probe (used to decide reel/video vs.
  photo/carousel) ran with **no cookies at all**, even though
  `--browser`/`--cookies` were already parsed a few lines above it. Instagram
  now returns an empty/auth-blocked response to anonymous format probes, so
  the probe silently failed, `has_video` fell back to `no`, and every reel
  got routed to the `gallery-dl` photo path instead of `video_download` —
  which meant `ensure_mac_playable_video()` never ran on it at all,
  regardless of the fix above. The probe now builds the same
  `--cookies`/`--cookies-from-browser` args as `_gallery_dl_download()`
  before calling `yt-dlp -J`. Verified end-to-end on the same reel URL:
  probe now detects the video, download goes through `video_download`, and
  the saved file is `h264`/`aac` in `.mp4`.

---

## 2026-07-17 — feat: amir clean gains orphan-detection items

Found while auditing disk usage on a low-space Mac: `~/Library/Containers/
com.utmapp.UTM` and `com.docker.docker` can linger at several GB each after
UTM.app/Docker.app are uninstalled, and `com.docker.install` /
`com.anthropic.claudefordesktop.ShipIt` accumulate as installer/update
leftovers regardless. `lib/commands/clean.sh` now lists four more items:

- **Claude Desktop Update Cache** (`~/Library/Caches/
  com.anthropic.claudefordesktop.ShipIt`) — always safe, pure updater cache.
- **Docker Installer Leftover** (`~/Library/Application Support/
  com.docker.install`) — always safe, not Docker's runtime data.
- **UTM Container (orphaned)** / **Docker Desktop Container (orphaned)** —
  only sized and deletable when `/Applications/UTM.app` /
  `/Applications/Docker.app` is absent; the app-presence check runs again at
  delete time (not just at display time) so toggling the item can never wipe
  a live VM/container if the app got reinstalled mid-session.

All four default OFF, same as the existing Aerials/Claude VM items.

---

## 2026-07-13 — security: eval-based command injection fixes

Audit against `agent-constitution/rules/030-security.md` ("Do not use
`eval()` ... with user input") found two `eval` call sites in amir-cli;
both fixed by switching to Bash arrays, which eliminates the shell
re-parsing step that made injection possible in the first place.

- **fix(extend)!:** `lib/commands/extend.sh:145` built the ImageMagick
  command as one concatenated string (`CMD="magick \"$INPUT_FILE\" ..."`)
  from unvalidated CLI args (input/output filenames, `--top/--bottom/
  --left/--right` colors) and ran it via unquoted `eval $CMD`. A crafted
  argument broke out of the string and ran arbitrary shell commands, e.g.
  `amir img extend photo.jpg --top 20 'red; touch pwned #'`. Verified
  exploitable before the fix and closed after: `CMD` is now a Bash array
  (`CMD=(magick "$INPUT_FILE"); CMD+=(-background "$TOP_COL" ...)`) invoked
  directly as `"${CMD[@]}"` — every value is passed to `magick` as a single
  literal argument, never re-interpreted as shell syntax. Pre-existing bug,
  unrelated to today's earlier changes; found while auditing the whole repo
  against the security rule for the `amir scripts` change below.
- **fix(scripts):** `lib/commands/scripts.sh`'s two `eval "$cmd" ...`
  call sites (added earlier today for the `amir scripts` feature) are
  gone — replaced with `read -ra cmd_arr <<< "$cmd"` (splits the trusted
  `lib/config/scripts.txt` command string into an array) followed by
  `"${cmd_arr[@]}" "$@"`. Same behavior (`amir scripts <id> [args...]`
  still runs multi-word registry commands with extra args appended), no
  `eval` in the path from user-supplied arguments to a shell.

## 2026-07-13 — docs/TECHNICAL.md accuracy pass (follow-up)

`docs/TECHNICAL.md` was missed in the scripts-subcommand commit below — this
closes that gap:

- **docs(scripts):** documented the new `amir scripts` registry as a
  lightweight alternative extension path (new subsection under "🛠 Extending
  Amir CLI"), and added `lib/config/` + `lib/commands/scripts.sh` to the
  Project Structure tree.
- **docs(research):** split the `### `trend` / `research`` section in two —
  `research` was never actually an alias for `trend` (separate
  `research.sh` since commit `1930927`, 2026-06-01); it's a PhD/postdoc
  supervisor-scout pipeline (`discover`/`professor` subcommands) that just
  happens to bridge the same Research Toolkit repo. Removed the false
  `amir research "open source AI"` alias example from `trend`'s usage
  block and wrote a real architecture/subcommand section for `research`.
- **docs(llm-lists):** updated the LLM Model Discovery section for its
  `amir router models` rename (2026-07-13, see below) — usage examples,
  heading, and a note on why the dispatcher entry was safe to drop
  (pure passthrough, same underlying `llm_lists()` function). Also fixed a
  pre-existing stale provider name (`Groq` → `Grok (xAI)`, the actual
  provider since `groq`→`grok` was renamed 2026-07-12) while in the
  neighborhood.
- **docs(readme):** the top-level "✨ Features" bullets in README had drifted
  even further out of sync than the sections below them: **AI Powered**
  still advertised "Chat with Gemini/Gemma, generate code" (`amir
  chat`/`amir code` — deleted 2026-07-12, replaced by `amir router`) and
  `Groq` (renamed to `Grok` 2026-07-12); rewritten to describe `amir
  router`/`amir router models`. **Research & Trends** didn't mention `amir
  research` (the professor-scout pipeline, see above) at all — added.
  **System Utilities**/**File Transfer** now note the `amir scripts`
  relocation for `pass`/`lock`/`unlock`/`qr`/`transfer` (still directly
  callable too).
- **docs(technical):** the `~/.amir/` storage-layout diagram still listed
  `chat_history.md`/`code_history.md` — dead since `chat.sh`/`code.sh` were
  deleted 2026-07-12 (verified: nothing under `lib/`/`amir` writes those
  paths anymore). Removed them and added a pointer to where `amir router`
  actually keeps session memory/cost-ledger data now (outside `~/.amir/`,
  in the `_router` vault).

## 2026-07-13 — scripts subcommand

- **feat(scripts):** new `amir scripts` subcommand — a picker for saved
  one-off scripts. `amir scripts` with no args shows a numbered menu and
  prompts for a selection; `amir scripts list` just prints the menu;
  `amir scripts <id> [args...]` runs a saved entry directly, skipping the
  prompt. Registry lives in `lib/config/scripts.txt` (`id|description|command`
  per line, `#`-comments allowed) so new scripts can be added by editing that
  file — no code changes needed. Seeded with `mcp-map`, which runs
  `~/.claude/scripts/apply-mcp-map.py` (per-project MCP connector
  allocation). Intended destination for current top-level subcommands that
  turn out to be low-traffic, to keep `amir help` shorter over time.
- **feat(completions):** `amir scripts` wired into zsh tab-completion — word 2
  offers `scripts` alongside the other top-level commands, word 3 offers
  `list` plus every saved id/description pulled live from
  `lib/config/scripts.txt`, so new registry entries show up in completion
  automatically without touching `completions/_amir`.
- **chore(scripts):** moved 9 low-traffic subcommands into the `scripts`
  registry — `weather`, `qr`, `pass`, `dashboard`, `transfer`, `short`,
  `lock`, `unlock`, `speed`. Picked by counting real invocations in
  `~/.zsh_history` (Feb–Jul 2026, 13k commands): all 9 had 0–4 hits vs.
  hundreds/dozens for `video`/`img`/`pdf`/`apply`/etc. Each still works as a
  direct top-level command (`amir weather` unchanged, dispatcher untouched)
  — they're just dropped from `amir help` and the word-2 tab-completion
  list, and now also reachable via `amir scripts weather` / the `amir
  scripts` menu. Kept `sync-constitution`/`init-project`/`update-projects`/
  `skill`/`split`/`watermark`/`trend`/`research` at top level for now despite
  low counts — infra/workflow commands, not one-off utility scripts;
  candidates for a later pass.
- **fix(dl/kb aliases):** dropped the `dl` (→`download`) and `kb`
  (→`keyboard`) aliases entirely — dispatcher case patterns (`download|dl` →
  `download`, `keyboard|kb` → `keyboard`), their `commands=()` completion
  entries, and the `Alias:`/`(alias: ...)` mentions in README. `amir dl` /
  `amir kb` now fall through to the default (compress) case instead of
  running download/keyboard — no more aliases, one name per command.
- **fix(llm-lists):** removed the top-level `amir llm-lists` command —
  `amir router models` has been a 1:1 passthrough to the same
  `lib/commands/llm-lists.sh` function all along (`run_router`'s `models`
  case just sources it and forwards `"$@"`), so nothing was lost. Dropped
  the dispatcher case in `amir`, the `commands=()` completion entry, and the
  dead completion block in `completions/_amir` — and while there, fixed
  `amir router models`'s own completion, which had drifted from the real
  `llm-lists` one (wrong/incomplete provider list, no `-e`/`--export`
  pdf\|md\|jpg completion at all). It now carries the exact provider +
  export-flag completion `llm-lists` had. README env-var hints
  (`OPENAI_API_KEY` etc.) repointed from `llm-lists <provider>` to `amir
  router models <provider>`. Also purged `dl`/`kb`/`llm-lists` and other
  already-stale/removed names (`transfer lock unlock qr weather short pass
  speed chat code dashboard`) from the `amir help <TAB>` value list in
  `completions/_amir`, which had drifted out of sync with the real command
  set.
- **docs(research):** fixed a stale "Alias for `amir trend`" description for
  `amir research` in `amir help`, `completions/_amir`, and README —
  leftover from before commit `1930927` (2026-06-01) split `research.sh` out
  of `trend.sh` into its own PhD/postdoc supervisor-scout pipeline
  (`amir research discover --keywords ...`, `amir research professor
  --professor ... --institution ...`). The two commands are unrelated
  (trending content vs. academic outreach) and both stay — `research` was
  never actually redundant, its docs just never caught up with the refactor.
  Added a proper README subsection for it (options, `RESEARCH_TOOLKIT_DIR`
  setup) since it previously had none at all.

## 2026-07-12 — clip clipboard-to-file, pdf split, completion fixes

- **feat(completions):** added `altacv-contact-up`/`altacv-contact-side` to
  `--template`'s tab-completion list (new ApplyForge template variants — see
  its own changelog).
- **fix(completions):** `amir apply <job-url> --template ... --stack ...` had the
  same fixed-word-position completion bug as `apply preview` — the dispatch
  only recognized `phd`/`job`/`sync`/`tui`/`web`/`stats`/`alert` as word 3, so
  a job URL (or any unrecognized word) at that position got zero completion
  for every flag after it. Now any non-keyword word 3 (a URL) routes through
  `_apply_arguments` the same way `preview` does. Also added `--stack` to
  `_apply_arguments` completion (see ApplyForge's own changelog for the
  feature itself).
- **fix(llm-lists):** replaced the `groq` provider with `grok` (xAI) across
  `lib/commands/llm-lists.sh`, completions, and docs — the owner has never
  used Groq (the LPU inference host) and only holds an xAI/Grok API key, so
  `groq` was dead weight that also collided by name with the unrelated
  `grok` model already used in `amir router --model grok`. `GROQ_API_KEY` →
  `GROK_API_KEY`, base URL → `https://api.x.ai/v1`.
- **fix(clip):** `amir clip <single-word-non-existing-file>` (e.g. `amir clip
  notes.md`) now saves the current clipboard content into that file, instead
  of overwriting the clipboard with the literal argument text. Multi-word
  arguments still copy as plain text (unchanged).
- **feat(pdf):** new `amir pdf split <file.pdf> --pages <spec> [--combined]
  [-o out]` subcommand, implemented via `qpdf`'s native page-range syntax.
  `--pages 1,3,4` / `1,2-3,4-8` produces one PDF per comma-separated group;
  `--combined` merges the selected pages/ranges into a single output PDF
  instead.
- **fix(completions):** `--theme` was never wired into `amir pdf`'s zsh
  completion — added, backed by a dynamic `_amir_pdf_themes` function that
  lists `lib/themes/*.css`.
- **fix(completions):** `amir apply preview --role <TAB>` and any flag typed
  after it stopped completing, because the dispatch only called
  `_apply_arguments` when `CURRENT == 4`. Now handled for `CURRENT >= 4`,
  matching the pattern already used by `subtitle`.
- **feat(completions):** `amir router` had no subcommand/flag completion at
  all (only the top-level command name completed) — added `audit`/`cost`/
  `models` subcommands and `-m/--model`, `-s/--session`, `--new`, `--system`,
  `--out`, `--plan` flags.
- **chore:** removed dead `chat)`/`code)` blocks from `completions/_amir` and
  deleted the orphaned `lib/commands/chat.sh`/`code.sh` — `amir chat`/`amir
  code` were already replaced by `amir router` at the entry-point dispatcher
  level, but the completion blocks and source files were never cleaned up,
  so tab-completion kept advertising two commands that no longer run.
- **docs:** documented the general fixed-position `case $((CURRENT))`
  completion pitfall in `docs/TECHNICAL.md` (§3) — it affected multiple
  commands and will resurface when adding new flag-style subcommands.

## 2026-07-06 — gitignore node_modules (wo-applyforge-0011)

- `lib/nodejs/node_modules/` was tracked in git (4177 files, never gitignored) —
  discovered while scrubbing leaked personal data from history, since it was the
  source of hundreds of unrelated npm-maintainer emails showing up in the audit.
  Purged from all history via `git filter-repo` and added to `.gitignore`.
  Restore locally with `npm install --prefix lib/nodejs`.

## 2026-07-06 — Apply Tracker moved to ApplyForge (wo-applyforge-0007)

- **Refactor:** `lib/python/apply_tracker/` deleted from this repo and moved to
  ApplyForge (`src/apply_tracker/`) — the tracker depends on ApplyForge's own
  CV-generation pipeline, so keeping it here duplicated that dependency.
  `amir apply web/tui/sync/stats/alert` and `amir phd`/`amir job` are unaffected
  from the user's side; internally they now shell out to ApplyForge via a new
  `_tracker_py()` helper in `lib/commands/apply.sh`
  (`cd "$APPLYFORGE_DIR" && uv run python -m src.apply_tracker.<module>`),
  the same wrap pattern already used for `amir apply <url>` → `main.py apply`.
  Data (tracking.json, tracker.db, the `~/@-Amir/Apply/2026-2027` vault) is
  untouched. Updated `docs/APPLY_TRACKER.md` and `docs/fa/APPLY_TRACKER_FA.md`
  architecture sections to reflect the new location.

## 2026-07-03 — init-project: three footguns removed

- **Targeted staging:** `init-project` now stages only the files it created or
  deliberately modified this run (tracked in an explicit list) instead of
  `git add src tests docs assets …`, which used to sweep pre-existing
  WIP/untracked files into the index. A pre-existing `main.py`/`.python-version`
  is never staged even when `uv init` runs. Re-running on an already-scaffolded
  repo stages nothing.
- **No silent Python scaffold:** on an existing repo with no stack markers
  (no pyproject/requirements/package.json/go.mod/Cargo.toml), `uv init` now
  asks interactively and skips when non-interactive — media/docs repos no
  longer get junk `pyproject.toml`/`main.py`. NEW projects keep the Python
  default.
- **Legacy submodule guard:** if `.agent/constitution` is a real directory
  (legacy submodule/clone), the command refuses and prints the migration steps.
  Previously `ln -sfn` dropped the symlink *inside* the directory
  (`.agent/constitution/agent-constitution`), leaving the submodule plus a junk
  nested link.

## 2026-07-03 — install the pre-merge-commit hook · neutral env var names

- **Renamed (no alias, breaking):** `AMIR_CONSTITUTION_URL` →
  `AGENT_CONSTITUTION_URL` (init-project clone URL) and
  `AMIR_CONSTITUTION_PATH` → `AGENT_CONSTITUTION_PATH` (sync-constitution
  source override). Constitution-related settings carry no personal branding —
  anyone adopting the constitution repo gets neutral `AGENT_*` names, matching
  the existing `AGENT_CONSTITUTION_DIR`. If you exported the old names in your
  shell profile, rename them.

- `amir init-project` and `amir update-projects` now install the constitution's
  new **`pre-merge-commit`** hook alongside `pre-commit`/`commit-msg`, so the
  privacy and skill-version gates also cover merge commits (git never runs
  pre-commit on automatic merges). Requires an agent-constitution clone that
  contains `templates/hooks/pre-merge-commit` — update the central clone first,
  otherwise the hook step reports a failure for that project.

## 2026-07-02 — init-project template: rule-050 compliance

- `init-project` no longer creates a per-project `TODO.md` anywhere (repo or
  vault) — tasks live only in the central `_memory/TODO.md` (rule 050); the
  command now prints a pointer instead.
- Generated `CLAUDE.md`: storage line points at the rule-035 vault `data/`
  dir (was `~/.<project>/`), and no absolute personal path is embedded
  (040 security check).
- Final summary output updated accordingly.

## [Unreleased] - 2026-07-02

### Fixed
- `amir init-project` — two rule-compliance fixes (035/040/045):
  - `.agent/constitution` is now a symlink to one central clone
    (`AGENT_CONSTITUTION_DIR`, default `~/@-github/agent-constitution`) instead
    of a per-repo `git submodule`, which pinned a SHA and drifted.
  - `TODO.md`/`SESSION.md` are created in the project's vault workspace
    (`~/.local/share/agent-projects/<slug>/workspace/`) instead of the repo
    root — these are per-session work-log files and must never be committed
    or even sit in the working tree. `.gitignore` also enforces this if
    either file is ever created locally by hand.
- `amir update-projects` — now detects and handles both the symlink pattern
  (refreshes the link; pulls the one central clone once up front, not per
  project) and the legacy submodule pattern (updated in place, unchanged
  behavior) so newly-scaffolded projects aren't silently skipped. New flag
  `--no-link` (`--no-submodule` kept as a back-compat alias).

## [Unreleased] - 2026-07-01

### Added
- `amir router` — single multi-model AI gateway wrapping the vault router
  (`~/.local/share/agent-projects/_router/delegate.py`): gemini/gemma (free tier),
  `deepseek-v4-flash`/`-pro`, `minimax` (prepaid default), `grok`. Conversation
  memory via `--session`, provider-echoed proof + cost ledger via
  `amir router audit`, provider model catalogs via `amir router models`, cost
  dashboard placeholder `amir router cost`. Routing policy lives in
  `_router/STRATEGY.md`. Natural prompts work unquoted:
  `amir router --model gemini write a fib function`.

### Removed
- `amir chat` and `amir code` — superseded by `amir router` (use
  `amir router --model gemini "..."` for the old free-tier behaviour). Handler
  files `lib/commands/chat.sh` and `code.sh` are left in place but no longer wired
  into the dispatcher; safe to delete later.

## [Unreleased] - 2026-06-22

### Added
- `amir init-project` and `amir update-projects` now install the constitution
  **`commit-msg`** hook alongside `pre-commit` (forbids AI co-authorship in commit
  messages — see agent-constitution `rules/040-git.md`).
- `amir pdf linkedin-post <folder>` renders trilingual (FR/EN/FA) LinkedIn posts
  with **WeasyPrint** via `lib/python/render_post.py` (guides + `guide.trilingue.pdf`
  + `carrousel.linkedin.pdf`), driven by a per-post `post.yml`. Subcommands let you
  rebuild only what changed: `carousel`, or `guide <fr en fa tri>` (one or several
  targets at once — e.g. `guide fa` rebuilds just the Persian guide). See
  `docs/TRILINGUAL_POSTS.md`.
- Guide body text is justified; bare URLs and the author signature render LTR, and
  « … » around a purely-Latin phrase are isolated LTR, even in the RTL Persian guide.
- Vendored fonts in `lib/fonts/` (Vazirmatn + DejaVu) and a restricted
  `FONTCONFIG_FILE` so macOS renders Persian/RTL correctly (no junk
  Noto-Yezidi / Hiragino / Microsoft-Sans fallbacks). Background skill:
  `.agent/constitution/skills/weasyprint-rtl-persian-pdf.md`.
- Auto-generation of YouTube PO-Token using `rustypipe-botguard`.
- `--normalize` flag to force FFmpeg transcoding to H.264/AAC for older macOS devices.
- `--po-token` flag to manually pass YouTube GVS PO tokens.
- `--yt-dlp-args` flag to manually pass underlying yt-dlp arguments.

### Changed
- AV1, VP9, and Opus formats are now preserved and played natively on modern macOS (via QuickTime), avoiding slow and unnecessary FFmpeg transcoding.

---

## [Unreleased] - 2026-06-12

### Added
- `amir img compress` — new subcommand to compress images to a target file size (default 300KB).
  - Binary-search JPEG quality (85→50) then auto dimension reduction (80%→20%) until target is met.
  - `--uniform`: auto-detects a common resize scale across all input files so outputs share the same physical dimensions (useful for document front/back pairs).
  - `--grayscale`: converts to grayscale before encoding — halves file size with no text readability loss, ideal for official documents and scans.
  - `--target KB`, `--min-quality`, `--max-quality`, `--overwrite`, `--suffix`, `-o dir`.
  - Full zsh autocompletion including flag values for `--target`, `--scale`, and `--max/min-quality`.

---

## [Unreleased] - 2026-06-09

### Changed
- `amir init-project` — production-grade scaffold output:
  - Constitution submodule now defaults to **HTTPS** (`https://github.com/su6i/agent-constitution.git`)
    for portability; override with `AMIR_CONSTITUTION_URL` (e.g. the SSH form).
  - Dropped `lib/` from the scaffold (collided with the `.gitignore` `lib/` pattern)
    and stopped creating `.storage/` dirs (data lives in `~/.<project>/`).
  - Adds `.gitkeep` to every empty dir so git actually tracks `src/ tests/ docs/ assets/`.
  - Detects the stack; for Python/unspecified runs `uv init --no-readme --vcs none
    --no-workspace` → `pyproject.toml` + pinned `.python-version`.
  - Generates starter `README.md` and `.env.example`; `TODO.md` opens with a
    First Session checklist.
  - `.gitignore` always enforces critical rules (`.storage/ .env .venv/
    __pycache__/ .DS_Store`) even when seeded from a template.

### Added
- `amir update-projects [base-dir]` — new command that propagates the latest
  constitution + `pre-commit` hook across every project under `base-dir`
  (default `$AMIR_PROJECTS_DIR` or `~/@-github`) that uses the constitution
  submodule. Idempotent and non-destructive. Flags: `--dry-run`, `--no-hook`,
  `--no-submodule`, `--exclude`. Excludes `amir-cli`/`agent-constitution` by
  default. Replaces the ad-hoc one-off shell loop.
- `amir init-project` installs the constitution `pre-commit` hook into every new
  project (blocks direct commits to `main` + enforces the docs checklist).

### Fixed
- `amir init-project` now **refuses** to create a project inside an existing git
  repo (the nesting footgun that corrupts submodules and lets `uv init` hijack a
  parent `pyproject.toml` workspace). Override with `AMIR_ALLOW_NESTED=1`.
- `uv init` is invoked with `--no-workspace` so it can never mutate a parent
  uv project's `pyproject.toml`.

## Unreleased
- fix(download): Restore missing caption sidecar (.txt) and fix yt-dlp import error in gallery-dl.

