# Repo layout plan: progressive discovery (2026-10-26)

Owner: "there are more opportunities to consolidate, like a shared/ directory and some hierarchy of all the random fixes and
docs we have; the dual purpose is progressive discovery by agents or humans: someone looking for installation or fix work
can learn/find what we've done and work on it easily." Goal: a state we can launch and share with the community this week.

PR #129 (root-cleanup) moved loose files by file type (windows/, mac/, tools/save-editor, docs/research). This plan extends
it by **journey**: a reader arrives with one of five intents and reaches the right folder in at most two clicks, each
folder's README being the next index. Planned under Fable; executed by an Opus lane on the PR branch.

## 1. The five journeys and where each lands

| I want to... | first click | second click |
|---|---|---|
| **play** (I have the game, make it good) | README.md download / Install | `windows/` `mac/` `deck/` README |
| **install or package** for a platform, or understand what the kit changes | `docs/README.md` > Install | `shared/README.md` (the payload), the platform README, `tools/patch-kit/README.md` |
| **fix or extend** something | `docs/README.md` > Fix | `src/README.md` (fix catalogue: component > what it fixes > switch > record), then the component README and its records |
| **understand the engine / a format** | `docs/README.md` > Engine | `docs/engine/`, `re/README.md` |
| **see what has been tried** (before re-chasing it) | `docs/README.md` > History | `docs/research/` (dead ends, feasibility), `docs/records/README.md` (every lane record by topic) |

## 2. Target layout

```
/
  README.md                players. Videos are owner-managed (drag-drop in the GitHub UI): never edit that section.
  CONTRIBUTING.md          humans with dev tools: refreshed (s.4)
  AGENTS.md                agents: contributor quick start on top (s.4); the developer's lab doctrine below it, marked as such
  CLAUDE.md -> AGENTS.md   LICENSE  CHANGELOG.md  ROADMAP.md  THIRD-PARTY.md  INSTALL.md
  INSTALL.bat  mac-install.command  index.html  i76-save-editor.html     entry points and public URLs (stay)
  windows/  mac/  deck/    per-platform install + launch. Each README answers, in this order: install, what it changes in
                           the game folder, how to undo, troubleshooting, where the code behind each step lives.
  shared/                  the payload every platform copies into a game folder: presets/  controls/  saves/
                           renderer/ (dgVoodoo.conf, dgVoodoo.windows.conf, dgVoodoo.daily-driver-2026-10-03.conf, dxvk.conf,
                           interstate-76.dxw). shared/README.md: one table, file > which installer copies it where > why.
  src/                     PHASE 2 (s.5). The fixes themselves: music-fix/ u32x/ smack-music-fix/ ffb-shim/ sound-rumble/.
                           In phase 1 only src/README.md is created (the fix catalogue) and it links the folders where they are.
  tools/                   dev tooling, unchanged inside; tools/README.md groups every subfolder: build & package | test
                           harness | research & RE | media | one-off.
  tests/
  docs/
    README.md              THE HUB (rewritten, s.3)
    guides/                how-to for players and installers: CONTROLS, GAMEPAD-PC-MAC, WHEEL-T300, FIGHTERSTICK, DECK-CONTROLS,
                           STEAMDECK, STEAMDECK-INPUT-MODES, MAC-BUILD, WINDOWS-PLAYBOOK, MULTIPLAYER, COOP, GAME-NIGHT, MUSIC,
                           HEAD-TRACKING, INPUT-REMAPPER, MODDING-GUIDE, MISSION-LAUNCH, DXWND-TUNING, SOUND-HD-PACK,
                           Interstate76-Controls-Quick-Reference.pdf, README-DETAILS
    engine/                how the fixes work and what the game is: ENHANCEMENTS, VERIFIED-FIXES, DRAW-DISTANCE, HANDLING-MODEL,
                           FORCE-FEEDBACK-AND-VISUALS, FFB-DESIGN-LIBRARY, FFB-STACKS, HAPTICS-ARCHITECTURE, MOTION-OUTPUT,
                           CONTROL-DOCTRINE, LEVEL-FORMAT, SAVE-FORMAT-GAPS, SAVE-FREEZE-ROOT-CAUSE, WEAPON-STATS, PARTS-REFERENCE,
                           MUSIC-TRACK-MAP, I76-GAMEPLAY-REFERENCE, MEMORY-MAP-INDEX, ASSET-BIBLE (+ asset-bible/), VISUAL-QUALITY-MAC,
                           FIND-WHAT-WRITES, EDITOR-FIELD-TESTS
    research/              feasibility, dead ends, prior art (existing folder +): HD-TEXTURES-RESEARCH, VOODOO-PARKED,
                           DXGI-DGVOODOO-RESEARCH, COCKPIT-HIRES-FEASIBILITY, COOP-SPIKE, PRIOR-ART-I26-2026-10-21,
                           INSTALLER-LESSONS-OPENRA, CONTENT-FEASIBILITY-2026-10-25, RE-FIELD-GUIDE, RE-METHODOLOGY, RE-RESOURCES,
                           COMMUNITY-RESOURCES, COMMUNITY-SITEMAP
    process/               how the project runs: PROCESS, RELEASE-PLAN, AGENTS-GAME-FOLDER, PARALLEL-SESSIONS,
                           LEGITIMACY-AND-SCOPE, SCOPE-AND-LEGITIMACY (merge the two if they overlap; keep both names as links
                           otherwise), NITRO-LAN-WEEKEND, OWNER-TEST-LIST, LAB-DOCTRINE (the part of AGENTS.md that is the
                           developer's machine-specific doctrine, see s.4)
    status/                dated plans, backlogs and snapshots (history, read-only): BACKLOG-*, STATUS-*, ARSENAL-PLAN-*,
                           CLEANUP-PLAN-*, COPIES-PLAN-*, LAYOUT-PROPOSAL-*, REPO-ORGANIZATION-PROPOSAL, this file,
                           OPEN-FEATURES-*, OWNER-MORNING-*, RC-*, DOC-CORRECTIONS-PENDING-SIBLINGS
    records/               the 173 lane records, unchanged, + README.md: an index generated by tools/records-index.py
                           (date from the filename, title from the first heading, topic from a keyword table), grouped by topic
    release/  asset-bible/ unchanged (asset-bible may move under engine/ if nothing outside docs links it)
  re/  lab/                public snapshots, unchanged
```

## 3. The hub: docs/README.md

Rewrite from scratch (the current one is a 2026-10-03 inventory). Shape:

1. Five headed sections in the journey order of s.1, each 3-8 links with a half-line of what the reader gets there. Play
   points back at README.md and the platform READMEs; Install at shared/, the platform READMEs, tools/patch-kit; Fix at
   src/README.md, docs/engine/ENHANCEMENTS.md, docs/engine/VERIFIED-FIXES.md, docs/process/PROCESS.md (issues, QA queue,
   records); Engine at docs/engine/ and re/; History at docs/research/, docs/records/README.md, docs/status/.
2. "Settled: do not re-chase" - the parked dead ends in one list (Voodoo on Mac, Mac FFB, HD textures, the FPSLimit result,
   the quadtree cache ...) each linking its evidence. This list exists in the old hub's tags; carry every "parked" item over.
3. "Conventions": records are dated and measured (n, control, spread); living docs are undated and current; status/ is
   history; paths inside records are as written on the day.

Keep it under 150 lines. No tables wider than 3 columns.

## 4. Contributors and their agents

**AGENTS.md** gets a new first section, ~40 lines, "Working on this repo from anywhere": where things are (the hub), the
no-game-files rule, how to build the proxy (`music-fix/README.md` build section; mingw), how to run `pytest tests`, what
cannot be tested without hardware (say so in the PR; the QA queue exists for that), the issue / PR flow (docs/process/
PROCESS.md: issues are the task layer, every non-trivial change gets a dated record with measurements), the privacy rule
(no names, machine paths, IPs), and "the sections below are the developer's lab doctrine: they apply only on machines that
have those folders; skip them elsewhere". The lab doctrine itself moves to docs/process/LAB-DOCTRINE.md with AGENTS.md
including it by link **only if** the owner's sessions still load it (CLAUDE.md points at AGENTS.md; keep the doctrine text in
AGENTS.md below the new section unless a test shows a linked file is read by the owner's tooling - do not risk it this
week: keep it inline, add the section on top).

**CONTRIBUTING.md** refreshed: drop the dated items (setup-*.sh family, game-data/, phone-port playbook); add: the dev /
test / main install tiers and that PRs are tested on a copy, never a playable install; "Good first contributions" = the
open `good first issue` and `needs-qa` issues (people with the hardware can run the QA queue without writing code); a
section "Using an AI coding agent" (Claude Code, Codex, Cursor): point it at AGENTS.md; what we expect from agent-assisted
PRs (measurements with n, a record file, no private data, the agent named in the PR body); the PR template.

## 5. Phase 2 (after launch, separate PR): src/

Group music-fix/, u32x/, smack-music-fix/, ffb-shim/, sound-rumble/ under src/. Not now because the owner's main checkout
carries uncommitted edits in music-fix/ (a pull that renames those paths would leave the autostash unable to apply), one lab
script builds from the music-fix path, and the kit builders read music-fix/Strlkup.dll. Do it when the owner's music-fix
work is committed: git mv, re-point tools/package-*.ps1, windows/setup-windows.ps1, the lab script, and verify the kit zip
file lists as in PR #129.

## 6. Rules for the lane

- Every move is `git mv`. Before each move grep the repo (scripts, builders, tests, .github, docs) and C:\Users\james\i76-uncap-lab
  for the name; re-point every repo reference; list every lab reference in the PR for follow-up; never edit game folders.
- Markdown links to a moved doc are re-pointed **repo-wide, records included** (filenames are unique; a link is not history).
  Backticked paths inside records stay as written.
- README.md: touch only a link target that a move broke. Never the video section.
- Verification as in PR #129: rebuild the Windows Patch Kit and the Mac kit, diff file lists against published v0.8.1 and the
  lab's newest Mac kit (must be identical); `pytest tests` (the 2 known failures only); `sh -n` / PowerShell parse on every
  touched script; a markdown link check whose broken-link count is not above main's 369.
- Commit per step (shared/, docs hierarchy, hub, indexes, AGENTS/CONTRIBUTING) so a step can be reverted alone.
- PR body: replace the layout tree with the new one, add this plan's s.1 table, the phase-2 note, the lab references, the
  verification results, and the line "Planned under Fable 5.1 from the owner's brief; executed by an Opus lane."
