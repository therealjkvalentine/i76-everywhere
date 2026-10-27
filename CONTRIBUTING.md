# Contributing to i76-everywhere

Thanks for helping keep a 1997 classic playable. This repo is scripts, source and documentation for running
**Interstate '76** on modern hardware. It deliberately contains **no game files**. Fixes, platform recipes, format
research, test reports and doc improvements are all welcome. Start at the docs hub, [docs/README.md](docs/README.md):
it sends you to the right folder for what you want to do.

## The one hard rule: no copyrighted content, ever

Never commit game data (executables, `*.ZFS`, textures, audio, movies, missions, other people's saves) or third-party
binaries. The game you test with is **yours** and stays outside the repository. PRs that add game content will be
closed. See [THIRD-PARTY.md](THIRD-PARTY.md).

Two standing exceptions, so the rule above is not read as contradicting the tree:

- **`shared/saves/`** holds the developer's own bookmark files (`save*.cmp`, `savegame.dir`). They are user-generated
  data, not Activision assets; the Windows setup installs them when a game folder has no saves, and the save editor's
  tests use them as byte-exact fixtures. Do not add anyone else's saves, and add your own only if a test needs that
  exact file (say which in the commit message).
- **Binaries of this project's own code** that the installers copy: `music-fix/Strlkup.dll`, `u32x/u32x.dll`,
  `tools/i76wheel.exe`. Each sits beside its source and build script and contains no game bytes. A changed binary is
  committed together with the source that built it, and its md5 goes in the CHANGELOG entry.

## Test on a copy, never on the game you play

Keep separate copies of the game for each edition you work on (Gold, Nitro): a **dev** copy where your builds land
first, a **test** copy that you set up the way a player would (the Patch Kit or the installer, from a clean GOG copy),
and the **main** copy you actually play, which only ever gets released builds. A PR is tested on dev and test, never on
main: a half-finished experiment in the folder you play in looks exactly like a regression. Run the game at the
machine itself, not over Remote Desktop (the 3D cannot start there).

## Before you open a PR

1. **Read the hub's "Settled: do not re-chase" list** ([docs/README.md](docs/README.md#settled-do-not-re-chase)) and
   search the [records index](docs/records/README.md). Several obvious ideas (Glide to Metal on the Mac, Mac force
   feedback, an HD texture pack) are settled dead ends; please don't re-open one without new evidence.
2. **Find or file the issue.** Issues are where work is tracked ([docs/process/PROCESS.md](docs/process/PROCESS.md)).
3. **Check [docs/engine/VERIFIED-FIXES.md](docs/engine/VERIFIED-FIXES.md)**, the symptom > cause > fix table. If your
   change fixes something, add a row; if it adds a fix, add it to [src/README.md](src/README.md) and
   [docs/engine/ENHANCEMENTS.md](docs/engine/ENHANCEMENTS.md).
4. **Run `pytest tests`** (offline, no game needed) before and after your change.
5. **Fill in the PR template** ([.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)): what and why,
   the platforms affected, how it was tested, the checklist.

## House rules (how this project earns trust)

- **Field-test in the actual game.** The ground truth is the game running, not a passing script. Say what you ran and
  what you saw; a screenshot or a log line helps.
- **Measure, and write it down.** A non-trivial change gets a dated record in [docs/records/](docs/records/) with the
  numbers: n, a control run, the spread. Run `python tools/records-index.py` afterwards. Records are not rewritten;
  living docs are corrected in place.
- **New behaviour goes behind a switch.** Engine changes are `I76_*` switches, off by default, until they are measured;
  a preset in [shared/presets/](shared/presets/) turns them on.
- **Verify byte-level changes against real saves.** The save format was reverse-engineered from real files and
  corrected more than once. If you touch the save parser or editor, diff your output against a known-good save.
- **Every write keeps a backup.** The installers keep every original beside the file they change and the editors write
  timestamped backups. Preserve that.
- **Keep the tone.** Plain Markdown, scripts with a header comment that says *why*, and honest about what is verified
  and what is guessed. No personal names, machine paths or addresses in anything you commit or post.

## Good first contributions

- **The open [`good first issue`](https://github.com/therealjkvalentine/i76-everywhere/labels/good%20first%20issue)
  issues.**
- **The QA queue: [`needs-qa`](https://github.com/therealjkvalentine/i76-everywhere/labels/needs-qa) issues.** Each one
  is a test that needs a person with the hardware (a wheel, a Mac, a Deck, a second PC): steps to run and boxes to
  tick. You do not need to write code to do these, and they are some of the most useful help there is.
- **Port a fix across platforms**: a working fix on one platform that the others lack.
- **Doc clarity**: if a step tripped you up, tighten it.

## Using an AI coding agent

Claude Code, Codex, Cursor and similar tools are welcome. Point yours at [AGENTS.md](AGENTS.md): its first section
says where things are, how to build and test, and the rules; the sections below it are the developer's lab doctrine
and only apply on machines that have those folders. What we expect from an agent-assisted PR is what we expect from
any PR, plus two things:

- measurements with n and a control, and a record file for anything non-trivial; no claim the agent could not check
  (say what needs hardware, and it goes to the QA queue);
- no private data in anything committed or posted, and **the agent named in the PR body** (tool and model), so
  reviewers know how it was made.

## Reporting instead of fixing

Not everything needs code. A good bug report, or a "this worked / didn't work on my machine" data point, is genuinely
useful: open an issue with the templates provided, and attach `mciproxy.log` from the game folder.

## Licensing of contributions

By contributing, you agree your original contributions are licensed under this project's [MIT License](LICENSE).
