# Configuration reference — every knob, where it lives, and what it fixes

> **Correction 2026-10-03: the dgVoodoo results here from 2026-08-09 to 2026-10-02 are void.** In that window
> dgVoodoo 2.87.3 was rejecting this sandbox's `dgVoodoo.conf` as a whole and running a 2020 global
> `%APPDATA%\dgVoodoo\dgVoodoo.conf`. A key in a section it does not belong to rejects the whole file; it is
> not skipped, as this page says below. So every row that reports what a key did or did not do in that window
> is void until it is re-measured on an accepted conf: `FPSLimit`, `CaptureMouse`, `FreeMouse`, forced
> refresh, `Resolution`, MSAA. **`EnableInactiveAppState` belongs in `[Glide]` only.** Putting it in
> `[General]` and `[DirectX]`, as the first row below advised, is what made dgVoodoo reject the file. Before
> trusting a conf finding, prove the file is loaded: flip a visible key (`3DfxWatermark = true`) and hide the
> global file. Record: [DGVOODOO-CONF-REJECTED.md](DGVOODOO-CONF-REJECTED.md).

**Read this before reverse-engineering anything about windowing, focus, mouse, or frame rate.**
Twice now a problem that looked like it needed a debugger turned out to be one line in a config
file. The freeze-when-unfocused hunt cost hours of hardware-breakpoint work and the answer was
`EnableInactiveAppState` sitting in the wrong section.

Files, in the order you should check them:

| file | owns | where |
|---|---|---|
| `dgVoodoo.conf` | window, resolution, scaling, mouse, focus, frame limit | `game/` |
| `captures/i76uncap.ctl` | the 60 FPS DLL's runtime behaviour | `captures/` |
| `input.map` | key bindings | `game/` |
| `i76.cfg` / registry | in-game settings written by the game itself | `game/` |

---

## 1. "Is there a setting for this?" — by symptom

| symptom / goal | setting | section | value |
|---|---|---|---|
| Game freezes when it loses focus; screenshots come back identical | `EnableInactiveAppState` | **`[Glide]` only** (corrected 2026-10-03: this said `[General]` *and* `[DirectX]`, which makes dgVoodoo reject the whole file; see the note at the top) | `true` |
| Frame rate / sim speed | `FPSLimit` | `[GeneralExt]` | `19.2` stock; the DLL overrides at runtime |
| Menu clicks land in the wrong place | `ScalingMode` + `Resolution` | `[General]` / `[DirectX]` | see §3 — **do not** re-fit coordinates |
| Cursor confined to the window | `CaptureMouse` | `[General]` | `true` |
| Cursor behaves oddly and you suspect dgVoodoo | `FreeMouse` | `[GeneralExt]` | `false` — see §3, **not** the fix |
| Window size (the one that actually matters) | `Resolution` | **`[DirectX]`** | owns window size |
| 3D render target size | `Resolution` | `[Glide]` | keep equal to the `[DirectX]` one |
| Black screen + dead input on a modal dialog | `FullscreenAttributes` | `[GeneralExt]` | `fake` |
| Magenta/purple road patches on night missions | `DitheringEffect` | `[GlideExt]` | `pure32bit` |
| Texture corruption / crashes | `MemorySizeOfTMU` | `[Glide]` | `2048`, 1 TMU |
| Tearing | `ForceVerticalSync` | `[Glide]` | `true` (off when frame-gen owns present) |

**The section is load-bearing.** dgVoodoo silently ignores a key in the wrong section — no
warning, no log line, it just does nothing. `EnableInactiveAppState` was present in `[Glide]`
for weeks and had no effect; the same line in `[General]` fixed it immediately. When a setting
"doesn't work", check its section before concluding the setting is wrong.

### Verifying a setting actually took effect

Never assume. Each of these has a cheap check:

```powershell
# focus / inactive state - frame counter must advance while the game is NOT foreground
..\autotest\diagnose\capture-focus-snapshots.ps1     # prints "delta while unfocused: N; 0 = frozen"

# frame rate - measure it, don't trust the conf
. .\lib\memlib.ps1; $c = Mem-Open
$a = (Mem-Player $c).Frame; Start-Sleep 2; $b = (Mem-Player $c).Frame
"{0:N1} fps" -f (($b - $a) / 2)

# cursor mapping - the derivation must match reality
..\autotest\calibrate\cursor-absolute-test.ps1        # confirms the mapping is absolute at all
```

---

## 2. Discovering options that aren't listed here

dgVoodoo has many conf-only settings that never appear in its control panel (`FreeMouse` is
one). To find them:

1. `refs/` has no dgVoodoo source — it is closed. The authority is **`ReadmeGeneral.txt`** and
   **`ReadmeGlide.txt`** shipped in the dgVoodoo distribution.
2. The CPL writes a *complete* conf with every key at its default. Run `dgVoodooCpl.exe`
   against a scratch folder and diff its output against ours to see keys we never set:
   ```powershell
   Compare-Object (Get-Content .\game\dgVoodoo.conf) (Get-Content .\scratch\dgVoodoo.conf) `
       | Where-Object SideIndicator -eq '=>'
   ```
3. Keys are parsed case-insensitively but **the compact `WxH` form matters** — the
   `h:1680, v:1080` subproperty syntax silently failed to parse and fell back to 640x480.

**When you learn a new one, add a row to §1 and a comment in `game/dgVoodoo.conf` itself.**
The conf is the copy people actually read; `docs/dgVoodoo.conf.reference` mirrors it.

---

## 3. The mouse — solved, do not re-derive

Historically this was the harness's worst area: two separate empirical calibrations
(`screen = 3.98·OS + 393`, later `3.6·OS + 568`) that both drifted across the form and missed
small controls like the `A.I. DRIVERS [-]` button. **Both were wrong, and neither needed to
exist.** The real relationship is exact:

> **The OS cursor position IS the engine's 640x480 UI coordinate, 1:1.**
> `SetCursorPos(x, y)` puts the game's cursor on UI point `(x, y)`.

Everything else is only needed to *read* screenshots. The screen position of a UI point is
derived, never fitted (`autotest/lib/maplib.ps1`, `Init-CursorMap`):

```
frame  : dgVoodoo renders [Glide] Resolution (1680x1050 = 16:10), aspect-fit into the window
         -> 2304x1440 at screen left 568 on a 3440x1440 display
unit   : u = frame_h / 480                                = 3.0 px per UI unit
pillar : ScalingMode=*_ar preserves the APP's 4:3 aspect, so the 640x480 UI is PILLARBOXED
         inside the 16:10 frame:  (frame_w/u - 640)/2     = 64 units
origin : ui_left = frame_left + pillar*u                  = 760 px
         screen_x = 760 + 3*ux        screen_y = 3*uy
```

Two facts make this trustworthy rather than another fit:

- **The mapping is absolute.** `autotest/calibrate/cursor-absolute-test.ps1` parks the cursor on the same
  target from three different previous positions; the game draws it in the same place every
  time. (Only a 3–10 px animated element at UI ~(54,2) differs — mask the top-left corner in
  any frame differencing.)
- **The pillarbox is documented by dgVoodoo itself**, and by our own conf: *`stretched_ar`
  "just pillarboxes 4:3 inside the wider buffer"*. The 64 units is not a fudge factor.

### Why the earlier measurements were wrong

The fit that produced the bogus 0.8333 slope was **measuring its own capture bug**: it
downscaled the 16:10 frame (2304x1440) into a 4:3 bitmap (640x480), squeezing x by exactly
5/6 = 0.8333. Correct the aspect and both axes come out at slope 1.000.

**If you ever feel the urge to re-fit these constants, check your capture's aspect ratio
first.** A whole-frame centroid is also useless here — menu items brighten on hover, and the
highlight outweighs the cursor sprite, which is what produced >1000 px residuals.

### `FreeMouse` is not the fix

`FreeMouse = false` (default) lets dgVoodoo manage cursor mapping and is correct. Setting it
`true` was considered and is **unnecessary** — the mapping was always exact; only the
measurement was broken. Leave it alone.

### The one API you need

```powershell
. .\lib\maplib.ps1
Capture-UI 'shot.png'      # crops to the UI and rescales so 1 image px == 1 UI unit == 1 OS coord
# open shot.png, read the control's pixel coordinate, then:
Click-UI 206 295           # A.I. DRIVERS [+]
```

That is the whole workflow: **screenshot → read coordinate → click it.** No sweeping, no
calibration, no trial and error. Verified by clicking `[+]` three times and `[-]` twice on a
counter starting at `00` and reading back `01`.

---

## 4. Screenshots

`CopyFromScreen` grabs the **whole virtual desktop** (3440x1440 here) unless you crop. Three
rects are available, all derived:

| helper | region | use for |
|---|---|---|
| `Get-UIRect` | the 4:3 UI, 1920x1440 at x=760 | **default** — maps 1:1 to cursor coords |
| `Get-FrameRect` | the full 16:10 render, 2304x1440 at x=568 | when you need the pillarbox bars too |
| *(none)* | full desktop | almost never — wastes time and confuses diffs |

`Capture-UI` uses `Get-UIRect` and rescales to 640x480, which is both the smallest useful
image and the one whose coordinates you can act on directly.

Screenshots are still ~150 ms and awkward to analyse — **prefer memory reads** for anything
numeric (see `ENGINE-REFERENCE.md`). Use screenshots for the 2D shell, where there is no
memory map yet.

---

## 5. `captures/i76uncap.ctl` — the DLL's runtime knobs

Plain `key=value` lines, re-read live; no relaunch needed.

| key | effect |
|---|---|
| `fpscap` | target frame rate (e.g. `20`, `60`) |
| `extras` | extra interpolated frames per sim tick |
| `interp` | entity interpolation on/off |
| `pace` | frame pacing |
| `enabled` | master switch for the hook |
| `record` | per-frame in-process recorder |
| `savestate` / `loadstate` | **disabled** — structurally unsafe, see `RESULTS.md` |
