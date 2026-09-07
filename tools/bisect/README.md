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
i76.exe       9a232dcc      i76shell.dll  8960fa16
STRLKUP.DLL   e5951e0f      glide2x.dll   c319a4f3   (GOG's own Glide wrapper)
```

## The layers, and what each is suspected of

| layer | what it changes | known/suspected effects |
|---|---|---|
| `01-exe-framepatch` | `i76.exe` → the frame/PIT-patched build | the stock exe drives its sim off the PIT and misbehaves on modern hardware. **Probably needed for basic playability** — try this first. |
| `02-dgvoodoo` | GOG's `glide2x` → dgVoodoo + ddraw/d3d8/d3d9 + `dgVoodoo.conf` | resolution, aspect, FPS limit. **Also owns the mouse cursor** — `CaptureMouse` decides whether the pointer is drawn where you click. |
| `03-u32x` | retargets the exe's USER32 imports to `u32x.dll` | translates cursor coordinates between the game's 640×480 space and the screen. Menu clicks land correctly only when this matches the dgVoodoo mouse mode. |
| `04-music` | `Strlkup.dll` proxy | plays `music\*.mp3` through the engine's CD-audio calls; makes the in-game AUDIO CONTROL slider work. |
| `05-shell-textentry` | two bytes in `i76shell.dll` | **only meaningful on a PATCHED shell.** Stock GOG already has the correct bytes, so on vanilla this layer is a no-op — which is itself the proof that the typing bug was never the game's. |
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
