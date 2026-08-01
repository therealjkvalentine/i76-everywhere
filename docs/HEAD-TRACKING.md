# Head tracking — opentrack into Interstate '76

Turn your head, the view turns. Two tiers, same script
([`../i76-headtrack.ahk`](../i76-headtrack.ahk)): a **digital** glance that works
today on the engine's own keys, and an **analog** camera write that uses the
memory map from [GHIDRA-MEMORY-MAP.md](GHIDRA-MEMORY-MAP.md).

## Transport: freetrack shared memory, NOT vjoy

opentrack can emit to a virtual joystick, and that was the original setup here.
We deliberately moved to **freetrack 2.0 Enhanced** (the `FT_SharedMem` block):

> This machine enumerates **no winmm device at index 0** — the two real devices
> sit at ids 4 and 8, which is exactly why the working `input.map` binds
> `joystick5` rather than the doctrine's `joystick1`. Feeding head data through
> *another* virtual stick makes that enumeration worse and can shift what the
> 1997 engine binds at startup. Shared memory touches no joystick at all.

Set it in opentrack: **Output → freetrack 2.0 Enhanced**, then **Start**.
(To go back to the joystick output, the previous config is saved beside it as
`default.ini.pre-freetrack`.)

**Verified live 2026-08-01:** `FT_SharedMem` present; `Yaw` at byte offset 12 as
a **float in radians**, about ±0.65 (≈±37°) for a comfortable head turn; read
successfully both from .NET and from AutoHotkey's `MapViewOfFile` path.

FreeTrackData layout used: `DataID@0, CamWidth@4, CamHeight@8, Yaw@12,
Pitch@16, Roll@20` (all floats after the three ints).

## Tier 1 — DIGITAL (default, works now)

Head yaw past `YAW_ON` (0.18 rad ≈ 10°) holds the glance arrow key; it releases
inside `YAW_OFF` (0.12 rad) — the same hysteresis + held-state machinery the
right stick already uses in `i76-remap.ahk`, so every key-down has a matching
key-up. Works in every view and needs nothing but the game running.

## Tier 2 — ANALOG (Ctrl+Alt+H to toggle)

Writes the live camera yaw float straight into the running game:

| what | address (i76.exe Gold) | source |
|---|---|---|
| `cam_yaw` | `0x4c2964` | confirmed, `tools/i76-addresses.json` |
| `cam_view_mode` | `0x4c2728` | confirmed (FSM: which F1..F11 view) |

The engine's `cockpit_look_apply` (`0x406b00`) recomputes those floats **every
frame** from the int inputs at `0x536770/78`, so the script re-writes at ~66 Hz
against a 20 FPS sim to win the race. Writing the int inputs instead does *not*
work — they're in the input-state block the per-frame input poll overwrites
(same reason injecting `weapon_fire` at `0x5367db` fails; see
GHIDRA-MEMORY-MAP.md PART 7).

**Not yet field-confirmed:** the exact `cam_view_mode` values for the cockpit
views. The script currently gates analog writes to modes `2` and `5` (the FSM's
switch values are documented as 2/5/9/0x1a, and a live read in chase view
returned 7). Confirm in-game and adjust `ADDR_VIEW_MODE` gating at the top of
the script if the cockpit turns out to be a different value.

## Running it

```
HEADTRACK.bat          (portable copy)   - or run _ahk\i76-headtrack.ahk directly
```
Start opentrack and press **Start** first. **Ctrl+Alt+H** toggles DIGITAL ⇄ ANALOG.

Tunables at the top of the script: `YAW_ON` / `YAW_OFF` (digital thresholds),
`ANALOG_GAIN` (head radians → camera radians), `ANALOG_MAX` (clamp), `INVERT`
(set 1 if looking left turns the view right).

## Safety rules it follows

Straight from the wheel regression in [INPUT-REMAPPER.md](INPUT-REMAPPER.md):
every key-down has a matching key-up via a held-state table; keys release on
centre, when tracking drops out, on mode switch, and on exit; **it only acts
while the game window is active**, so head movement can never type into the
desktop; and no construct can raise a modal dialog.

It runs *alongside* `i76-remap.ahk` — that one owns the pad, this one owns the
head; they share no keys.
