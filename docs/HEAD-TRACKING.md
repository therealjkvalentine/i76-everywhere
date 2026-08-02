# Head tracking — opentrack into Interstate '76

Turn your head, the view turns. **Working and field-confirmed** on the GOG Gold
build (`i76.exe` MD5 `60abf7bc699da72476128ddce991a3d1`).

Script: [`../i76-headtrack.ahk`](../i76-headtrack.ahk) ·
Test harness: [`../i76-headtrack-test.ahk`](../i76-headtrack-test.ahk)

---

## Quick start

1. **opentrack** → Output = **freetrack 2.0 Enhanced** → press **Start**.
2. Run **`HEADTRACK.bat`** (portable copy) or `_ahk\i76-headtrack.ahk`.
3. Focus the game. **Ctrl+Alt+H** toggles DIGITAL ⇄ ANALOG (it always starts in
   DIGITAL).

| key | does |
|---|---|
| **Ctrl+Alt+H** | digital ⇄ analog |
| **Ctrl+Alt+[** / **]** | yaw sensitivity down / up, live |
| **Ctrl+Alt+−** / **=** | pitch sensitivity down / up, live |
| **Ctrl+Alt+L** | log 6 s of telemetry to `headtrack-log.txt` |
| **Ctrl+Alt+F** | freeze output at a fixed angle (diagnostic) |

Nothing happens unless the **game window has focus** — deliberate, so head
movement can never type into the desktop. It also means telemetry read from
outside the game always looks frozen; use Ctrl+Alt+L instead.

---

## Transport: freetrack shared memory, not vjoy

opentrack's **freetrack 2.0 Enhanced** output publishes `FT_SharedMem`; the
script reads `Yaw@12`, `Pitch@16` (floats, **radians**) after three leading ints.

Chosen over opentrack's vjoy output deliberately: this machine enumerates **no
winmm device at index 0** — the two real devices sit at ids 4 and 8, which is
why the working `input.map` binds `joystick5` rather than the doctrine's
`joystick1`. Feeding head data through *another* virtual stick makes that worse
and can shift what the 1997 engine binds at startup. Shared memory touches no
joystick at all.

Measured: a comfortable head turn reaches **±0.43 rad in yaw but only ±0.17 in
pitch**. The axes need separate scaling — see the expo section.

---

## The two modes

**DIGITAL** (default) — head angle past a threshold holds the glance arrow key.
Uses the engine's own glance, so it is smooth and free. Field verdict: "working
great".

**ANALOG** — a **hybrid**, for reasons documented below:
- **yaw**: continuous, by injecting the engine's own look-input delta
- **pitch**: the held **Down** arrow key, because no working injection path for
  pitch was found

---

## What the camera actually is (hard-won)

The memory map's labels for this block are **wrong**, and its structure is not
what it looks like.

| address | map calls it | what it actually is |
|---|---|---|
| `0x4c2970` | `cam_pitch` | moves the view **horizontally** |
| `0x4c2968` | — | moves the view **vertically** |
| `0x4c2964` | `cam_yaw` | not the yaw; vertical-ish, tracks `0x4c2968` |
| `0x4c296c`, `0x4c2974` | — | part of the same transform |

**They are not five independent Euler angles.** They are components of one view
transform that must stay mutually consistent. Freezing three while injecting into
two makes the ground textures vanish and terrain render as sky.

**They are outputs, not inputs.** Fifteen per-frame instructions write them —
three camera-mode handlers (`~0x406b00`, `~0x4072xx`, `~0x4077xx`) × five floats.
The camera-mode FSM is at `0x4c2728`, its jump table at `0x4c2990`.

**The engine springs them back to centre.** Measured, after writing 0.6 and
releasing: `0.6 → 0.366 → 0.241 → 0.147 → 0.089 → 0.059 → 0.036 → 0.004`.
That decay is proportional to the value, which is why poking absolute angles
produced a shake that got worse the further you looked.

### The input path (what analog actually drives)

| address | is |
|---|---|
| `0x536770` | yaw look input |
| `0x536778` | pitch look input |
| `0x536780` | roll look input |

All three camera handlers read these with **`fild`** (`0x406B14` / `0x40728C` /
`0x4076AA` for yaw). The input poll writes them from seven sites in
`0x44Exxx`–`0x44Fxxx`, all 5-byte `mov [disp32], eax`.

They are a **rate, not an angle**: hold a value and the view keeps panning; zero
it and it springs back. Analog therefore runs a **P controller** — read the
current angle, push a delta proportional to the error — and the camera settles
where the push balances the spring. Because the engine derives the whole
transform itself, it always agrees with itself: no shake, no missing terrain.

While analog is on, the poll's seven writes are NOPed so our delta survives the
frame; otherwise an 8 ms write only sometimes lands before the camera reads it.
Restored on mode switch and exit, plus a startup self-heal for force-kills. This
is safe by construction — these are **inputs**, not part of the view transform.

---

## Known limits and dead ends

**Pitch injection does not work on this build.** `0x536778` accepts our value —
the delta computes correctly and reads back *exactly* as written, so nothing
clobbers it — but the camera never responds, at any magnitude from 9 to 9380.
The engine evidently gates pitch on something the input poll sets alongside the
value. Not found. Analog therefore drives pitch with the arrow key, which works
perfectly. **This is the open question** if anyone wants to take it further: watch
what *else* the poll writes at `0x44f053` / `0x44fd0b` when Up is held.

**`Up` is LOOK BACK, not glance up.** Nodding up threw the view to the rear, so
the up key is disabled (`PITCH_UP_KEY := 0`). Only nodding *down* is bound.

**Injected writes do not follow the engine's own scale.** The engine's arrow-key
glance moves the camera floats only ~±0.2 with an int delta of just −13..+6, yet
`YAW_RANGE = 4.0` is what actually feels right. A "correction" to 0.30 on the
radians theory made yaw barely move. Trust the field value.

**Do not trust "saturation" figures from injection.** An earlier calibration
concluded the camera saturates at ±133 — that was an artefact of injecting values
far outside the design range, and several rounds of wrong scaling followed from
treating it as ground truth.

**The camera floats are not reliable feedback.** `0x4c2970` reads 0.00 while yaw
visibly works, so the P loop runs effectively as feedforward.

**NOPing the camera writes (`PATCH_ENABLED`) breaks rendering.** Off by default;
kept only as a research tool.

---

## Tuning

All at the top of the script; sensitivity is also live on the hotkeys above.

| setting | default | does |
|---|---|---|
| `YAW_RANGE` | 4.0 | how far a full head turn looks (field-confirmed) |
| `KP` | 90 | error → delta gain |
| `PITCH_ON` / `PITCH_OFF` | 0.05 / 0.03 | nod thresholds, with hysteresis |
| `EXPO` / `EXPO_P` | 1.7 / 2.2 | soften the centre without losing full travel |
| `EXPO_REF` / `EXPO_REF_P` | 0.45 / 0.17 | each axis's own full head travel |
| `INVERT` / `INVERT_PITCH` | 1 / 1 | both axes run opposite to the engine |

---

## Diagnosing it

Three lessons that cost several wrong turns:

1. **Camera telemetry is meaningless unless the game is live and focused.**
   Paused-at-a-menu readings look identical to "nothing is happening" and nearly
   produced three wrong conclusions.
2. **Log from inside the script** (Ctrl+Alt+L). Reading memory from a PowerShell
   window can never see the script working, because it only writes while the game
   has focus.
3. **A syntax check is not a load check.** `AutoHotkeyU32.exe /iLib NUL <script>`
   reports PASS on a file that will not actually run — a stray `}` closing the
   `Tick:` *label* got through it and left the script dead for several rounds.
   Launch it and confirm the process is alive a few seconds later.
