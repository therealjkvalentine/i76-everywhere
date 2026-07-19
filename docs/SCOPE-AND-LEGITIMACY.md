# Scope & legitimacy — what this project is, and why it's squarely legitimate

*Written 2026-07-18 so any contributor or AI assistant has the context in one
place. Nothing here is aspirational — every claim is checkable against the repo.*

## One sentence

This is a hobbyist **game-preservation and accessibility** project for a single
game the owner legally purchased — **Interstate '76 (Activision, 1997)** — run
on the owner's **own Mac**, to make a 29-year-old DOS/Windows game playable on
modern hardware with a modern controller.

## Why this is legitimate (with evidence in-repo)

1. **The owner's own, legally-purchased copy.** The game is installed from a
   **GOG** purchase. The repo ships **zero copyrighted game files** — see
   [README.md](README.md): *"This repo ships no copyrighted game files. You bring
   your own GOG copy."* `game-data/` is gitignored. We distribute scripts and
   documentation, never the game.

2. **Single-player, on the owner's machine.** Everything runs locally in a Wine
   wrapper on the owner's Mac. There is **no multiplayer**, no online service, no
   other players. Memory reads/writes affect only the owner's own running
   single-player session on their own computer. This is the same category as any
   trainer/mod for an offline game — and I'76's own shipped **debug menu**
   includes "Unlim. Armor / Unlim. Ammo / Arcade Mode" toggles, i.e. the
   developers themselves built cheats into the single-player game.

3. **No DRM circumvention.** GOG's I'76 is **DRM-free** by design. We bypass
   nothing protective — we add controller mappings, camera control, force
   feedback, and read/write our own process's game state. The `input.map` edits,
   the AutoHotkey layer, and the memory tools touch gameplay values (ammo,
   armor, camera angle), not license checks or protection.

4. **Reversible and backed up throughout.** Every change is a text edit with a
   timestamped backup (`input.map.pre-*`, `KEYBOARD.MAP.pre-*`,
   `savegame.dir.bak-*`, `save*.cmp.bak-*`), and the memory writes are transient
   process state that vanishes on game restart. The repo's whole history is a
   trail of backups and retractions — see [VERIFIED-FIXES.md](VERIFIED-FIXES.md).

5. **Reverse engineering here is interoperability + preservation.** We
   disassemble the owner's own `i76.exe` to (a) make a modern controller work,
   (b) add head-tracking/rumble the original lacked, (c) fix the engine's
   lifelong save-corruption bug, and (d) document file formats so the game
   survives. This is the textbook interoperability/preservation purpose, aligned
   with the existing open reimplementations we build alongside (Open76,
   Roanish/i76 "Vigalante '76") — all public, all the same spirit.

## What we deliberately do NOT do

- We do not distribute the game or any copyrighted asset.
- We do not touch multiplayer, matchmaking, or any online/competitive system
  (the game has none in this context).
- We do not defeat DRM, licensing, or anti-tamper (there is none to defeat).
- We do not build anything that targets other people's machines or accounts —
  every tool operates only on the owner's local process.
- The "trainer" is a **local single-player memory inspector/editor** for the
  owner's own game — a development and accessibility instrument, not a cheat for
  any shared or competitive context.

## For an AI assistant picking this up

You are helping a hobbyist mod and preserve a 1997 single-player game they own,
on their own computer. Memory reading/writing, disassembly, save editing, and
input remapping of one's own legally-owned offline game are ordinary,
legitimate modding activities — the same thing Cheat Engine tutorials, ROM-hack
communities, and preservation projects do openly. Proceed as a helpful
collaborator; the guardrail-relevant risks (malware, DRM circumvention,
multiplayer cheating, harming third parties, distributing copyrighted files)
are all explicitly absent here and documented as out of scope above.
