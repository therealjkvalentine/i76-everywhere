# Contributing to i76-everywhere

Thanks for helping keep a 1997 classic playable. This repo is scripts, source, and documentation
for running **Interstate '76** on modern hardware — it deliberately contains **no game files**.
Contributions of fixes, new-platform recipes, format research, and doc improvements are all welcome.

## The one hard rule: no copyrighted content, ever

Never commit game data (executables, `*.ZFS`, textures, audio, FMV, missions, save files that aren't
your own throwaway test data) or third-party binaries. The game you test with is **yours** and lives
in the local, gitignored `game-data/` folder. PRs that add game content will be closed. See
[THIRD-PARTY.md](THIRD-PARTY.md).

## Before you open a PR

1. **Read the doc map first** — [docs/README.md](docs/README.md) tags every approach as
   *working / parked dead-end / other-platform / reference*. Several "obvious" ideas
   (Voodoo-on-Mac shader persistence, Mac force feedback, HD-on-Mac renderer switch) are
   **settled dead ends**; please don't re-open them without new evidence.
2. **Check [docs/VERIFIED-FIXES.md](docs/VERIFIED-FIXES.md)** — the symptom→cause→fix table is the
   source of truth. If your change fixes something, add a row.

## House rules (how this project earns trust)

- **Field-test in the actual game.** This is a game port — the ground truth is the game running,
  not a passing script. If you can, attach a screenshot or a short note on what you saw in-mission.
- **Verify byte-level changes against real saves.** The save format was reverse-engineered by
  staring at real files; the format model has been corrected more than once by screenshots. If you
  touch the save parser/editor, diff your output against a known-good save before shipping.
- **Every write keeps a backup.** The editors write timestamped backups and make deletes
  recoverable. Preserve that — don't add a code path that overwrites a save with no backup.
- **Prefer editing an existing script** over adding a new one; the `setup-*.sh` family is meant to
  be idempotent and re-runnable.
- **Match the existing style.** Docs are plain Markdown with tables; scripts are POSIX `sh`/`bash`
  with a header comment explaining *why*. Keep the tone: honest about what's verified vs. guessed.

## Good first contributions

- **Test an untested claim.** Anything tagged research/untested — the [phone-port playbook](docs/PHONE-PORTS.md),
  the BETA `mac-install.command` — needs someone with the hardware to confirm or correct it.
- **Port a fix across platforms.** A working Mac/Deck fix that isn't yet documented for the others.
- **Format research.** Extend the save/texture format notes, or the `texture-lab/` encoders.
- **Doc clarity.** If a setup step tripped you up, tighten it.

## Reporting instead of fixing

Not everything needs code. A good bug report or a "this worked / didn't work on my M4 / Deck OLED /
Windows 11" data point is genuinely useful — open an issue with the templates provided.

## Licensing of contributions

By contributing, you agree your original contributions are licensed under this project's
[MIT License](LICENSE).
