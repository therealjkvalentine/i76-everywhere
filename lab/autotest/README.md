# Automated testing harness for Interstate '76

**Everything needed to drive I'76 from a script: launch it, get into a mission, press its
buttons, steer the car, and read the game's own state out of memory.** Written while building
the 60 FPS patch, but it is general-purpose — use it for any I'76 experiment, mod, or
regression test. All of it works unattended, on the sandbox copy in `../game`.

Every technique here cost real time to discover; the notes marked **GOTCHA** are the ones that
silently produce *wrong results* rather than errors. Read those before trusting any output.

```powershell
. .\lib\focuslib.ps1    # focus the game window (required before any screenshot)
. .\lib\inputlib.ps1    # keyboard + mouse injection
. .\lib\maplib.ps1      # screen->game cursor coordinate mapping
. .\lib\memlib.ps1      # read/write game state (fast, exact - prefer this)
```

---

## 1. Launching and getting into a mission

```powershell
.\enter-melee.ps1              # cold launch -> INSTANT MELEE, empty arena, unattended
.\enter-melee.ps1 -NoLaunch    # game already running
.\enter-melee.ps1 -KeepAI      # keep the 1 AI car (default removes it)
```

It launches `../game/i76.exe -glide`, skips the intro, walks the menus, and **verifies arrival
by memory** (player entity non-zero) rather than by screenshot. Exit code 0 = in a mission.

- **Melee** (`MELEE > AUTO MELEE > INSTANT MELEE > ENTER AREA`) is the fastest repeatable
  drivable state. Default car ABX Leprechaun, arena Tombstone.
- **Trip campaign** (`TRIP > NEW TRIP`) starts mission 1 ("keep up with Taurus") — use this
  when you need **other moving vehicles**. It runs a cutscene first; skip with ESC + click.
- The mission ends on death and drops to a STANDINGS screen — set AI drivers to 0 for long
  unattended runs (`enter-melee.ps1` does this by default).

## 2. Seeing the game (screenshots)

```powershell
$proc = Get-GamePid
Force-Foreground $proc.MainWindowHandle    # still wise before a capture
Capture-UI 'shot.png'                      # cropped to the game, 1 px == 1 cursor unit
```

- **Crop to the game, not the desktop.** `CopyFromScreen` grabs the whole virtual screen
  (3440x1440 here). `Capture-UI` (maplib) crops to the 4:3 UI and rescales to 640x480 so image
  coordinates *are* cursor coordinates. `Get-UIRect` / `Get-FrameRect` give the rects if you
  want to capture yourself.

- **GOTCHA — the game must be FOCUSED or your screenshot is a stale frame.** I'76 renders
  through dgVoodoo/Glide, which only presents a live image to the desktop while it is the
  foreground window. Unfocused, `CopyFromScreen` silently returns *the last frame from when it
  was focused* — every capture comes back byte-identical and you conclude "nothing changed".
- **GOTCHA — a background process can't call `SetForegroundWindow`.** Windows' foreground lock
  denies it. `Force-Foreground` defeats it (AttachThreadInput + `SPI_SETFOREGROUNDLOCKTIMEOUT=0`
  + an ALT tap). It returns `$true` on success — check it.
- **FIXED (2026-08-09): the game now runs while unfocused.** Set
  `EnableInactiveAppState = true` in **[General]** (and [DirectX]) of `dgVoodoo.conf` - it was
  only in [Glide], where it had no effect. Verified: 30 frames advanced in 1.5 s with focus
  elsewhere (previously exactly 0), and screenshots taken unfocused are live (7.7% of pixels
  changing vs byte-identical before). This removes the single biggest obstacle in the harness.
- **GOTCHA (historical, pre-fix) — I'76 freezes its simulation when the window loses focus.**
  If you see the frame counter stall and every sim value go bit-identical, check that setting
  first. `Ensure-SimRunning` still verifies it rather than assuming.
- Screenshots are slow (~150 ms) and expensive to analyse. **Prefer memory reads** (§4).

## 3. Pressing buttons and driving

```powershell
Send-Key $VK.W 60          # tap (scancode)
Hold-Key $VK.W 1500        # hold 1.5 s - accelerate
Click-Screen 1648 1385     # click a menu item at a SCREEN pixel (auto-maps)
```

- Keys go through `keybd_event` with **scan codes**; DirectInput ignores posted `WM_KEY`
  messages, so `SendKeys` does nothing.
- Driving: **W/S throttle (notched — tap repeatedly to add notches), A/D steer, X reverse,
  C handbrake** (from `input.map`).
- **GOTCHA — fire is `Enter` (or mouse LeftBtn), NOT Space.** `input.map`'s comment header says
  "Space fire" and it is wrong; the `weapon_fire` block binds `Enter`. Firing Space does nothing,
  silently — an ammo scan run that way produced 471 pure-noise candidates while the HUD still
  read 2000. Read the binding block, never the comment.
- **The menus are MOUSE-ONLY** — they ignore ENTER and number keys. The in-mission pause menu
  ("Spanner's Cafe", ESC) is the exception and takes keyboard.
- **The menu cursor IS 1:1 with the OS cursor**, in the engine's own 640x480 space:
  `SetCursorPos(x, y)` puts the game's cursor on UI point `(x, y)`. So the workflow is
  **screenshot → read the coordinate off the image → click that number**:

  ```powershell
  Capture-UI 'shot.png'   # crops to the UI, rescaled so 1 image px == 1 OS cursor unit
  Click-UI 206 295        # A.I. DRIVERS [+], read straight off shot.png
  ```

  No sweeping and no calibration. `maplib.ps1` derives the screen-side transform
  (`screen = 760 + 3·ux, 3·uy` here) from the display size and dgVoodoo's `Resolution` +
  `ScalingMode`; nothing is hand-tuned.
- **GOTCHA — do NOT re-fit cursor constants.** Two earlier two-point calibrations
  (`3.98·OS + 393`, then `3.6·OS + 568`) were both wrong and both missed small controls. The
  bogus slope came from *measuring through a distorted capture*: downscaling the 16:10 frame
  into a 4:3 bitmap squeezes x by exactly 5/6. Fix the aspect and the slope is 1.000.
  If a click misses, check your capture's aspect ratio and `ScalingMode` — see
  [docs/CONFIG-OPTIONS.md](../docs/CONFIG-OPTIONS.md) §3.
- **GOTCHA — whole-frame centroids can't locate the cursor.** Menu items brighten on hover and
  the highlight outweighs the cursor sprite. Also mask UI ~(54,2): that corner animates on its
  own. `..\autotest\calibrate\solve-cursor-map.ps1` does it correctly if you ever need to re-measure.
- **GOTCHA — you cannot drive by writing the input block.** `Mem-SetThrottle` / `Mem-SetSteer`
  exist and the writes land, but the engine refills `0x5367CC`/`0x5367D4` from the keyboard every
  frame and they are gone before anything reads them. Probed 2026-08-09: writing 127, 100 and 60
  all **read back as 0**, and the entity's applied throttle (`+0xE4`) never left `0.000` while the
  car coasted from 2.5 to 1.0 m/s. (The values are `int`, roughly −128..127 — but writing floats
  was not the problem; ints are clobbered too.)
- **Hold real keys instead, with `Key-Down` / `Key-Up`.** `Hold-Key` blocks for its whole
  duration, which is useless when you need throttle held *while* sampling memory. `Key-Down`/
  `Key-Up` are non-blocking, so the pattern is: `Key-Down $VK_W`, poll in a loop re-asserting the
  key each pass, then `Key-Up`. A held key is identical at any frame rate — **discrete taps are
  not**, and once faked a 15× yaw difference that was pure sampling artefact.

## 4. Reading game state (fast, exact — use this)

```powershell
. .\lib\memlib.ps1
$ctx = Mem-Open
if (Mem-InMission $ctx) {
    $p = Mem-Player $ctx        # speed, velocity (VY = FALL SPEED), yaw rate, controls, position
    $all = Mem-Entities $ctx    # every vehicle: index, X/Y/Z, radius  (slot 0 = player)
}
Mem-Close $ctx
```

Key addresses (Gold `i76.exe`, MD5 `60ABF7BC…`, base 0x400000, no ASLR):

| what | address | notes |
|---|---|---|
| player entity | `[[[0x54A264]]+0x70]` | 0 when not in a mission — the in-mission test |
| **world positions, ALL entities** | `0x54E11C`, stride `0x20` | `[x,y,z][radius]`; slot 0 = player. Read-only intel: the renderer does NOT draw from it |
| eye/view transform | `0x5FCDC4` | position + 3×3 matrix; **is** render-consumed (poking it moves the view) |
| frame counter | `0x5A7E1C` | ++ per rendered frame — measure real FPS from this |
| speed / velocity | entity `+0xAC` / `+0xBC` | `+0xC0` is vertical = **fall speed** |
| yaw rate / steer / throttle | `+0xCC` / `+0xE0` / `+0xE4` | |
| input block | `0x5367CC` throttle, `0x5367D4` steer | **writes are clobbered every frame — cannot drive with these** |

### Attitude: pitch, yaw and roll

```powershell
$a = Mem-EyeAngles $ctx     # .Pitch .Yaw .Roll (degrees) + .PX .PY .PZ
$v = Mem-Floats $ctx 0x5FCDC4 12    # the raw block, in ONE read
```

The eye transform at `0x5FCDC4` is the only place the car's attitude can be read — the entity
struct holds only *local part* transforms (four wheels at stride `0x54`, plus the steering matrix
at `+0x91C`), not the chassis world matrix. Layout:

| floats | meaning |
|---|---|
| `[0..2]` | world position |
| `[3..5]` | right vector |
| `[6..8]` | forward vector |
| `[9..11]` | up vector |
| `[12..14]` | scale (`1, 1, 0.8`) |

- **GOTCHA — always read a matrix in ONE `ReadProcessMemory` call** (`Mem-Floats`). Reading 12
  floats one at a time spreads the read over milliseconds; a moving camera updates midway and the
  rows come back non-orthonormal (dotting to 0.97 instead of 0). That torn read previously
  produced two confident, wrong conclusions about where orientation is stored.
- Roll is the tilt of `up` about `forward` against world-up projected perpendicular to `forward` —
  it is **not** simply `right.y`, which reads 0 even when the car is rolled 19°.

## 5. Debugging the engine

- `..\src\find-reads.c` — attaches as a debugger and sets **hardware data breakpoints**
  (Dr0-3) on up to 4 addresses, logging which instruction reads/writes each. This is how the
  renderer's transform reads were separated from the AI/culling reads.
  **GOTCHA: it has crashed the game on detach** — use short windows, expect a relaunch.
- `..\src\inject.c` — `CreateRemoteThread(LoadLibraryA)` DLL injector.
- `..\tools\instruments\xref.py <addr>...` — disassembles the exe's whole `.text` once and prints every
  static reference to an address, with context. Finds writers that fire too rarely to catch on a
  hardware breakpoint. **Limit: it only sees absolute-displacement operands.** Anything reached
  through a register base (per-entity fields, the camera state block) has *no* static xref — the
  camera Euler search returned only its initialiser for exactly this reason.
- `..\tools\instruments\disasm.py <addr> [n] [-back k]` — disassemble at a VA. Works off the on-disk exe
  (no ASLR), so no attach needed. **Do not name a script `dis.py`** — it shadows the stdlib `dis`
  module that `inspect` imports, and capstone dies on a circular import.
- `..\tools\framerate\snap-static.ps1` + `..\tools\framerate\ratio-scan.py` / `..\tools\framerate\find-dt.py` — raw dumps of the
  static range, compared across frame rates. `ratio-scan` finds values 3× smaller at 60 Hz;
  `find-dt` keeps only dwords sitting at 1/rate in *every* snapshot at *both* rates.
- **GOTCHA — a 3× ratio in a 1.3M-dword scan is usually chance.** `ratio-scan` returned 7 clean
  hits; `..\tools\framerate\sample-addrs.ps1` then showed all 7 are **constant within a run** (min == max
  over 14,000 samples) and arbitrary between runs. Always re-sample a scan hit over time before
  believing it.
- **GOTCHA — `$PSScriptRoot` is not reliably expanded in a `param()` default under
  `powershell -File`.** An `-OutDir` defaulting to `"$PSScriptRoot\..\captures"` silently wrote to
  the drive root. Resolve paths in the body instead.
- **GOTCHA — `[double]::IsFinite` does not exist** in .NET Framework 4.x (PowerShell 5.1). Use
  `-not [double]::IsNaN($_) -and -not [double]::IsInfinity($_)`.
- `..\tools\instruments\dump-memory.ps1` + a Python value-search — dump all writable regions once and
  search offline; a PowerShell byte-loop over 180 MB never finishes, Python does it in seconds.
- **GOTCHA — `VirtualQueryEx` needs `PROCESS_QUERY_INFORMATION` (0x400).** With `VM_READ`
  alone it returns 0 and you silently enumerate *zero* regions and dump empty files.
- **GOTCHA — the game locks its loaded DLL.** Rebuilding `i76uncap.dll` fails with LNK1104
  while the game runs; kill the game first or you keep testing the old binary.
- **GOTCHA — PowerShell aliases shadow your helper functions.** A function named `ri` becomes
  `Remove-Item`; `$pid` is reserved. Name helpers `Rd32`/`RdF`/`RdBlk`.
- **GOTCHA — NaN breaks range filters.** `if ($x -lt $lo -or $x -gt $hi) { skip }` never skips
  NaN, so a memory scan returns hundreds of thousands of garbage hits. Test with
  `abs(x - target) <= tol`, which is false for NaN.
- **GOTCHA — `Get-Content | Set-Content -Encoding utf8` silently corrupts every non-ASCII
  character.** PowerShell 5.1 decodes a BOM-less file as the system ANSI codepage, so a UTF-8 em
  dash (`E2 80 94`) is read as three cp1252 characters and re-encoded as three UTF-8 sequences.
  Nothing errors; the file just fills with mojibake. One bulk edit mangled 13 documents and ~40
  scripts this way and had to be recovered from git. For any script that rewrites repo text, use
  explicit encodings at both ends:

  ```powershell
  $enc = New-Object Text.UTF8Encoding $false      # UTF-8, no BOM
  $t = [IO.File]::ReadAllText($path, $enc)
  [IO.File]::WriteAllText($path, $t, $enc)
  ```

  The damage is reversible (decode UTF-8 → cp1252 bytes → decode UTF-8) but only while it is
  *uniform*; once clean and corrupted text mix in one file, `git checkout` is the fix. The same
  trap applies to the repair script itself — keep such a script **pure ASCII**, or PowerShell
  mis-decodes its own source and it will not even parse.

## 6. Writing a regression test

The pattern that makes physics claims verifiable:

1. `enter-melee.ps1` for a known start state (add `-KeepAI` only if you *want* opponents).
2. Hold a **constant** control input with `Key-Down` (not taps, and not the input block).
3. Sample `Mem-Player` / `Mem-EyeAngles` on a fixed cadence into a CSV.
4. Diff the trace against a reference run at checkpoints.

`..\tools\framerate\physics-trace.ps1` implements this; it is how "does the physics still match at 60 Hz"
is answered with numbers instead of opinion. **Fall speed (`VY`) is the canonical check** — the
famous I'76 breakage is that jumps fall wrong when the frame rate changes.

### Designing a comparison that actually survives

Hard-won, after several confident wrong answers (see `docs/framerate/DEAD-ENDS.md` for each):

- **Reach a steady state, then apply a step, then measure the response.** Report the result both
  in *seconds* and in *frames*: dt-correct systems match in seconds and differ 3× in frames;
  frame-coupled systems do the opposite. `..\tools\framerate\roll-test.ps1` is the template.
- **Compare something dimensionless** when runs cannot be made identical. `analyse-airborne.py`
  divides degrees actually turned by degrees the stored angular velocity asked for, so jumps of
  different sizes on different terrain become comparable and terrain cancels out.
- **Never express a threshold in frames.** "At least 5 frames" is 0.25 s at 20 Hz and 0.083 s at
  60 Hz — the fast run then qualifies on events the slow run never sees. Use seconds.
- **Dedupe samples by frame** before any per-sample test. The sampler is faster than the game, so
  at 20 Hz several rows share a frame with identical values, and a strict inequality breaks on
  every duplicate.
- **Do NOT compare trajectories across launches.** Spawn heading is not reproducible, and hilly
  terrain is chaotic: two runs at the *same* frame rate diverged by 150 m and 285 m. This produced
  a fully retracted "60 Hz is 11% slower" result.
- **Always run the same-rate control.** Two runs at one frame rate tell you the noise floor. Half
  the retractions in this repo would have been caught by that one extra run.

## 7. Another game folder, and the folder gate

Every script that starts the game takes `-GameDir <folder>`; the default is still the sandbox (`..\game`).
`lib\gamedir.ps1` (`Resolve-LabGameDir`) is the one guard: the folder must be inside this lab (the sandbox,
`game-alt`, a `game-dd-<date>\Interstate 76` twin; `game-*/` is git-ignored), must not be reached through a junction,
and the playable installs are refused by name. Scripts with the parameter: `proxy-run.ps1`, `test-escmenu.ps1`,
`enter-melee.ps1`, `menu-route-test.ps1`, `option6-trip-test.ps1`, `saves\leg-b.ps1`, `saves\garage-ui.ps1`,
`..\TEST-FRAMERATE.ps1`, `..\tools\graphics\conf-probe.ps1`. Most also take `-DryRun` (resolved paths, nothing
started) and `-KeepInstalledDll` (run the folder's own `STRLKUP.DLL` instead of installing `music-fix\Strlkup.dll`).

A script sets `$I76GameDirInUse = <folder>` **before** dot-sourcing the libs; `Get-GamePid`, `Mem-Open` and
`Init-CursorMap` then take the process running from that folder (and its `dgVoodoo.conf`) when several lab copies
exist. Not set = the first lab process, as before.

`option6-trip-test.ps1 -Launcher <PLAY.bat | x.ps1>` starts that launcher instead of `TEST-FRAMERATE.ps1` and walks
the same trip clicks; the launcher file must be inside the lab and the game it starts must run from `-GameDir`.

**`gate-folder.ps1 -GameDir <folder> [-Launcher <bat>] [-Bookmark saveNNN -Row k] [-Only 2,4] [-DryRun]`** runs the
daily-driver checklist (i76-everywhere `docs\records\NEW-DAILY-DRIVER-RECIPE.md` 5.1) on one folder and writes
`runs\gate\<ts>\results.md`: conf accepted with the global conf hidden, leg-b x3, the trip route through the
folder's launcher with the frame rate, the save screen (NO, then YES onto a scratch bookmark it adds and removes),
Esc-menu Exit, melee by menus, `lint-input-map.py`, `check-ffb.ps1`. The player-state files are copied out first
and compared by md5 at the end (anything changed is put back): the folder's saves end byte-identical. The header
of the script lists what each row does. Written and dry-run without the game (2026-10-03): the in-game half of
every row is unrun until the first console run; run it on the sandbox first as the control.
