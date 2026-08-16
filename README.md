# i76-everywhere

**Interstate '76 (GOG Gold, 1997) running well on everything: Apple Silicon Macs, Steam Deck,
and modern Windows — plus a full save editor and the reverse-engineered file formats.**

This repo ships **no copyrighted game files**. You bring your own GOG copy; everything here is
scripts, source, and documentation. Downloaded/copyrighted material lives in a local, gitignored
`game-data/` folder.

## Start here

| You want to… | Go to |
|---|---|
| **Play on a Mac** (Apple Silicon) | [docs/MAC-BUILD.md](docs/MAC-BUILD.md) — the shipping build: software renderer via DxWnd in a self-contained Wine wrapper. Instant start, music, clean quit, 20 FPS physics-safe |
| **Play on a Steam Deck** | [docs/STEAMDECK.md](docs/STEAMDECK.md) — the pretty Glide path (dgVoodoo→Vulkan) + force feedback |
| **Play on Windows** | [docs/WINDOWS-PLAYBOOK.md](docs/WINDOWS-PLAYBOOK.md) — max graphics, FFB, frame-gen |
| **Edit your saves** (no install) | **[Open the save editor in your browser →](https://therealjkvalentine.github.io/i76-everywhere/i76-save-editor.html)** — drag a save in, download it back out. Details: [the save editor](#the-save-editor) |
| **Understand the file formats** | [i76-save-editor.py](i76-save-editor.py) docstring (save format) + [docs/HD-TEXTURES-RESEARCH.md](docs/HD-TEXTURES-RESEARCH.md) (ZFS/VQM/M16) |
| **Know what's already settled** | [docs/README.md](docs/README.md) — the doc map: what works, what's a parked dead end. **Read before re-chasing anything** |
| **Every fix, one table** | [docs/VERIFIED-FIXES.md](docs/VERIFIED-FIXES.md) — symptom → root cause → fix, all verified in play |

## Open improvements

Live backlog of things still worth fixing, **non-frame-rate** ones first because they affect
normal play at any frame rate. (Frame-rate-specific bugs have their own tracked list in
[`../i76-uncap-lab/docs/framerate/MEASUREMENTS.md`](../i76-uncap-lab/docs/framerate/MEASUREMENTS.md).)

| # | Issue | Status / leads |
|---|---|---|
| 1 | **Saving/popups freeze the game** ("not responding"), the mouse does nothing in the window, and it only works sometimes | ✅ **ROOT CAUSE FOUND & PROVEN (2026-08-10) — [docs/SAVE-FREEZE-ROOT-CAUSE.md](docs/SAVE-FREEZE-ROOT-CAUSE.md).** The shell polls **`GetCursorPos` (screen coords) and hit-tests against its 640×480 button rects**, so on a stretched window the cursor is never "inside" YES/NO and the popup's poll loop spins forever without pumping messages. Diagnosed on a live hung process (EIP → `user32!GetCursorPos`, out-param held `(2692,1041)` vs a 640×480 UI) and **proven by unsticking it**: a click at UI-space (470,255) — the screen's top-left corner, not where the button appears — released it instantly, CPU 96%→7%. **Emergency unstick: move the mouse to the top-left ~640×480 of the screen and click where the button would be there.** Real fix: keep `ClipCursor(0,0,640,480)` asserted during shell screens |
| 1b | **"Always says you are overwriting"** | Separate bug: the save-slot allocator returns −1 (`sprintf("save%3.3d", -1)` → `save-01.cmp`). See [docs/SAVE-FORMAT-GAPS.md](docs/SAVE-FORMAT-GAPS.md) |
| 2 | Shell/menu architecture background (why menus, garage, popups and save all behave alike) | [docs/SHELL-MENU-AND-SAVE-FREEZE.md](docs/SHELL-MENU-AND-SAVE-FREEZE.md) — one shell (`i76shell.dll`) drives them all |
| 3 | **Draw distance + texture LOD** — landscapes pop in late; high-res textures only appear close | Enhancement, not a bug. Likely levers: the engine's LOD distance thresholds (the `obj_model` variant/slot swap system), fog/far-plane constants, dgVoodoo texture settings |

## The gamepad layout

The full controller scheme — native `input.map` bindings plus the AutoHotkey/XInput
layer (shift layer, look-back fire, rumble). These render from the **live configs**
via [tools/pad-diagram.py](tools/pad-diagram.py); regenerate after any binding change
(`open-pad-diagram.command` also gives an interactive HTML with the mouse/keyboard
tables) — never hand-edit them.

![Controller layout — base layer](docs/pad-layout.svg)

![Controller layout — LB held, shift layer](docs/pad-layout-shift.svg)

Design doctrine: [docs/CONTROL-DOCTRINE.md](docs/CONTROL-DOCTRINE.md) ·
Gamepad reference: [docs/GAMEPAD-PC-MAC.md](docs/GAMEPAD-PC-MAC.md)

## The save editor

A single self-contained web page styled after the game's garage paperwork.
**Zero-install:** [use it right now in any browser](https://therealjkvalentine.github.io/i76-everywhere/i76-save-editor.html)
— drag a save file in, edit, download it back out (nothing is uploaded; it all runs locally in the page).

- `./i76-save-editor.command` (Mac) — opens the editor with your saves auto-loaded and
  **writes edits straight back** (timestamped backups on every write; deletes are recoverable)
- `i76-save-editor.html` — the same page anywhere (Windows/Deck browser): drag saves in,
  download edits out
- `i76-save-editor.py` — the same parser as a terminal tool

What it edits: equipped parts (any weapon on any mount — off-spec swaps clearly marked),
armor (the DEFENSE panel numbers), every part's location (car/van/repair), condition, part
swaps with **measured DPS + range** on every weapon (data: Local Ditch), scene selection
("Scene № on a diner check"), save-as-slot, delete/restore. The save format was
reverse-engineered in this repo — details in the `.py` docstring.

## Highlights under the hood

- **Cutscene-music fix** ([smack-music-fix/](smack-music-fix/)): a proxy `SMACKW32.DLL` that
  recreates the 1997 CD-drive behavior (music stops when a movie starts) — fixes a GOG bug
  the community called unfixable. Ordinal-exact export forwarding; works on Mac and Windows.
- **Exactly-20 FPS physics** everywhere (the engine ties physics to framerate; scene 5's
  canyon jump is impossible above it): DxWnd delay on Mac, dgVoodoo `FPSLimit` on Deck/Windows.
- **The `.M16` hardware-texture format cracked** (round-trip encoder in
  [tools/i76img.py](tools/i76img.py)) — the RE prize from an enhanced-texture-pack
  experiment that was ultimately **retired** (marginal in-game gain; palette-indexed
  tiles break on night missions). Full writeup: [docs/HD-TEXTURES-RESEARCH.md](docs/HD-TEXTURES-RESEARCH.md).
- **The Voodoo path** (Glide→dgVoodoo→DXVK→MoltenVK→Metal) works but is **parked on Mac** —
  MoltenVK can't persist compiled pipelines. [docs/VOODOO-PARKED.md](docs/VOODOO-PARKED.md)
  has the exact announcement that would revive it.

## Provenance

Grown from [mac-gaming-ports](https://github.com/therealjkvalentine/mac-gaming-ports)'
`games/interstate-76/`, promoted to its own repo. Credits: UCyborg's AiO patch, dgVoodoo
(Dege), DxWnd (gho), Local Ditch Gaming (weapon measurements: Greg Schwartz / Zaphod-AVA),
the Open76 and Roanish/i76 reimplementation projects, and That Tony's format work.
