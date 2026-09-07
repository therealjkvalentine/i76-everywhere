# i76-bisect — start from stock, add one thing at a time

A separate install for finding out **which of our modifications causes what**. It is not the
daily driver and nothing here touches it
(`~/Downloads/Interstate76-i76-everywhere-portable-*/Interstate 76`).

```
game/    the playable folder. With no layers applied it is the GOG release, unmodified.
mods/    every modification, staged but NOT installed. One directory per layer.
LAYERS.ps1
```

## Why

Two days of debugging happened on top of a stack of accumulated modifications — a patched
exe, a patched shell, a USER32 proxy, a Glide wrapper, a music proxy, three AutoHotkey layers
— with no way to attribute a symptom to any one of them. Several "bugs" turned out to be a
layer rather than the game, and one of them (bookmark names dropping every character but the
first) was a **two-byte patch shipped by somebody else**, which cost a weekend to find.

So: begin at stock, and re-add deliberately.

## Use

```powershell
powershell -ExecutionPolicy Bypass -File LAYERS.ps1            # window
powershell -ExecutionPolicy Bypass -File LAYERS.ps1 -Status    # text
powershell -ExecutionPolicy Bypass -File LAYERS.ps1 -Apply 02-dgvoodoo -Play
powershell -ExecutionPolicy Bypass -File LAYERS.ps1 -Reset     # back to stock
```

Applied state is detected by hashing the files actually in `game/`, not remembered in a
config — so it cannot drift out of sync with reality, and it stays right even if you copy a
file in by hand.

Vanilla fingerprints, so "is this stock?" is always answerable:

```
i76.exe       9a232dcc      i76shell.dll  deb41008
STRLKUP.DLL   e5951e0f      glide2x.dll   c319a4f3   (GOG's own Glide wrapper)
```

## The layers, and what each is suspected of

| layer | what it changes | known/suspected effects |
|---|---|---|
| `01-exe-framepatch` | `i76.exe` → the frame/PIT-patched build | the stock exe drives its sim off the PIT and misbehaves on modern hardware. **Probably needed for basic playability** — try this first. |
| `02-dgvoodoo` | GOG's `glide2x` → dgVoodoo + ddraw/d3d8/d3d9 + `dgVoodoo.conf` | resolution, aspect, FPS limit. **Also owns the mouse cursor** — `CaptureMouse` decides whether the pointer is drawn where you click. |
| `03-u32x` | retargets the exe's USER32 imports to `u32x.dll` | translates cursor coordinates between the game's 640×480 space and the screen. Menu clicks land correctly only when this matches the dgVoodoo mouse mode. |
| `04-music` | `Strlkup.dll` proxy | plays `music\*.mp3` through the engine's CD-audio calls; makes the in-game AUDIO CONTROL slider work. |
| `05-shell-textentry` | two bytes in `i76shell.dll` | **only meaningful on a PATCHED shell** (layer 09). Stock GOG already has the correct bytes, so on vanilla this is a no-op — which is itself the proof that the typing bug was never the game's. |
| `06-u32x-ghosting` | `u32x.dll` → same source + `DisableProcessWindowsGhosting()` | stops the Save Bookmark screen dying ~5.9 s after it opens. Needs `03-u32x`. |
| `07-ahk` | `_ahk\` scripts | controller remap, Fighterstick layer, cursor overlay, opentrack autostart. |
| `08-extras` | `i76wheel.exe` | mouse wheel → keystrokes; the engine's mouse device has no wheel channel. |

## Suggested order

Play a little at each step — load a bookmark, save one, enter a mission, quit — before adding
the next.

1. **nothing** — does stock GOG run at all, and how badly does it behave without the frame patch?
2. `01-exe-framepatch` — expected to make it actually playable.
3. `02-dgvoodoo` — resolution and aspect. Watch the cursor here.
4. `03-u32x` — menu clicks. Watch the cursor here too; this and dgVoodoo interact.
5. `04-music`
6. `07-ahk`, `08-extras` — input conveniences.

`05-shell-textentry` and `06-u32x-ghosting` are fixes, not features: add them when the
matching symptom appears, and note whether it does.

## One thing that is probably NOT a layer

The daily driver crashed three times (2026-09-05/06/07) with an identical signature:

```
Faulting module: AcGenral.DLL   offset 0x00098ad3   exception 0xc0000005
```

`AcGenral.DLL` is Windows' **application-compatibility shim engine** — the game faulting
inside a shim Windows applies to it, not in its own code or ours. Other i76 paths on this
machine have `DWM8And16BitMitigation` registered, which lives in `AcGenral`. No compat layer
is registered for the portable path, so Windows is matching it from its own database.

Worth testing here: whether this install crashes the same way, and whether an explicit compat
setting changes it. If it reproduces on **stock, with no layers**, it is environmental and no
amount of bisecting our modifications will find it.

---

# Findings, 2026-09-07

## 1. The crash is environmental, not one of our layers

**Windows loads its compatibility shim engine into STOCK GOG with zero layers applied:**

```
COMPAT SHIMS ACTIVE: apphelp.dll, AcGenral.DLL      (stock i76.exe, nothing else applied)
```

The daily driver's three identical crashes were `AcGenral.DLL +0x00098ad3`, and `AcGenral` is
where the shims live. Since it is loaded regardless of anything we do, **bisecting our
modifications can never find that crash** - it is Windows shimming a 1997 game. Other i76
paths on this machine have `DWM8And16BitMitigation` registered explicitly, which is one of
those shims; the portable path has none registered, so Windows is matching it from its own
database.

Next step for that specific bug is a compatibility setting experiment, not a layer bisect.

## 2. "Vanilla" is not playable, so layer 01 is mandatory

Stock GOG `i76.exe` (9a232dcc) stops at a real Win32 dialog:

> Please insert CD "Interstate '76 CD 2"

even with the complete data set. The CD check lives in the stock exe; the patched exe does not
have it. So the true baseline for *playing* is `01-exe-framepatch`, not bare vanilla. Bare
vanilla is still the right baseline for *file comparison*.

## 3. Layer 01 alone crashes - it needs the dgVoodoo renderer

```
01 alone            i76.exe +0x00032963, 0xc0000005, dies in ~14s
01 + 02             runs; intro plays ("July 3rd, 1976. On a desert road outside Lubbock")
                    104 modules, glide2x loaded, steady CPU
```

The frame-patched exe cannot drive GOG's own `glide2x`. **`01` and `02` are effectively one
step**, which is worth knowing before treating them as independent variables.

## 4. The portable's "original" shell was never original

This one matters, and it is exactly the confusion this harness exists to prevent.

```
i76shell.dll.orig   8960fa16   bytes 40 0c   <- the portable's "pristine" backup: PATCHED
GOG sandbox shell   deb41008   bytes 41 08   <- actually pristine
```

The portable install keeps `i76shell.dll.orig` as though it were the untouched shell. It is
not: it already carries the two-byte change that stops `ToAscii`'s output word being zeroed,
which is what makes bookmark names drop every character but (occasionally) the first. Anyone
"reverting to the original" with that file reverts to the bug.

Layer 0 now uses the GOG sandbox shell, and the patched one is `09-patched-shell` - apply it
to **reproduce** the typing bug, then `05-shell-textentry` to fix it. That pair is a clean
demonstration that the fault was never the game's.

## Note for whoever automates this next

Menu click coordinates from the daily driver **do not transfer** to this install - an intro
sequence that lands on the main menu there ended up in the Options menu here. Before drawing
any conclusion from a click, prove the click landed: hover the control and check it
highlights (a brightness delta over the control's box works well, ~50 -> ~130 for a menu
item). A miss and a silent failure look identical, and one 25 px error already cost most of a
day.
