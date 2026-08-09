# Interstate '76 Everywhere — session doctrine

## Input bindings: input.map is the ONLY live file (field-proven 2026-07-18)

The engine reads **`input.map`** in the game folder. It does **not** read
`KEYBOARD.MAP`, `keyboard.map`, `JOYSTICK.MAP`, or `joystick.map` at runtime —
editing those changes nothing in-game (proven by restoring stock arrow bindings
in KEYBOARD.MAP: zero effect; adding the same blocks to input.map: fixed).
Those files carry warning banners in the installs. They remain useful only as
the reference **vocabulary** for token spellings (axis names, key names).

Rules for ANY control change:

1. Edit `input.map` in the game prefix, never the other .MAP files.
2. Back up first (`input.map.pre-<change>` convention, see the existing trail).
3. Validate before shipping: `python3 tools/lint-input-map.py <game dir>`.
   It checks every token against the exe's own string table and catches the
   known silent killers (`Up/Down` is not a token — the Y axis is `Down/Up`;
   chords-by-accident; two analog sources in one block).
4. Never rebind via the in-game Control Configuration menu (it corrupts —
   docs/VERIFIED-FIXES.md).

   **How to recognise a menu-corrupted input.map — check this FIRST when a
   controller "stops working".** Field case 2026-08-02: a wheel that steered and
   braked fine went completely dead. Hours went into drivers, winmm calibration
   and the registry; the actual cause was that the in-game menu had rewritten
   input.map. The signature, all three at once:

   - the **`steer` and `throttle` blocks are GONE** (no analog sink = no wheel,
     no pedals, no matter how healthy the device is)
   - **zero `joystick1` references**, and
   - every button re-pointed at some other slot (here `joystick8`, which was a
     3Dconnexion emulator, not the wheel)
   - the file is markedly **smaller** than a good one (3234 B vs 5219 B)

   `python3 tools/lint-input-map.py <game dir>` now fails on all of that, so
   **lint before you debug hardware**. Recover by restoring a known-good
   input.map — the portable zip carries one — then re-lint.

   Symptom-to-cause, so the next agent skips the detour: *device is perfect in
   the vendor's control panel but dead in game* means the game's own config, not
   the device. The vendor panel talks DirectInput; the 1997 engine reads winmm
   and this file.
5. Field-test on real hardware before marking anything verified; this repo's
   history is full of retractions for skipping that.

Full control-design doctrine: docs/CONTROL-DOCTRINE.md. Binding reference:
docs/input.map.reference, docs/GAMEPAD-PC-MAC.md.

## Community resources: check before reverse-engineering

**[docs/COMMUNITY-RESOURCES.md](docs/COMMUNITY-RESOURCES.md)** indexes the published work on
this game **by the problem it solves** — weapon and car stats, level heightmaps and the tools
that render them, editing/modding downloads, and gameplay doctrine. People have been taking
I'76 apart since 2000; a question that looks open is often already answered.

**[docs/WEAPON-STATS.md](docs/WEAPON-STATS.md)** mirrors the full weapon table locally (rate of
fire, range, projectile speed, weight, ammo, damage). Its ammo figures matched the values read
out of the live game **eight for eight**, which is why it doubles as a **search oracle**: when
hunting an unknown field, the published number tells you what to look for.

## Engine reference: what we know about I'76's internals

**`../i76-uncap-lab/docs/ENGINE-REFERENCE.md`** is the consolidated map of the engine — read it
before any new RE, trainer, mod, FFB or motion-sim work. It covers, with per-claim confidence
tags and how each was established:

- **Memory map** — the world position table for *every* vehicle (`0x54E11C`, stride 0x20, no
  pointer chase), the player entity chain and its velocity/controls offsets, the camera and eye
  transform, the FFB effect block (including a ready-made frame-time source at `+0x160`), and
  the entity/group tables.
- **Frame loop and render seam** — where the sim advances, where the scene is drawn, and the
  present function pointer that can be hooked without patching code.
- **Physics** — measured, not assumed: gravity is dt-correct (−9.89 at 20 Hz vs −9.74 m/s² at
  60 Hz), acceleration curves are indistinguishable across frame rates, weapon cadence is
  timer-driven. **The "high FPS breaks I'76" lore did not reproduce.** The gravity constant is
  an immediate at `0x43A6A1`, which is why data watchpoints never catch it.
- **Handling model** — the fitted yaw-rate equation and its constants.
- **13 traps that produce wrong data rather than errors**, each of which cost real time.

## Automated testing: you can drive the game from a script

**`../i76-uncap-lab/autotest/` — read its README before doing anything interactive with the
game.** It is a working harness for launching I'76, navigating its menus, sending control
input, and reading game state out of memory, all unattended. Built during the 60 FPS work
(`../i76-uncap-lab/`, a sandbox copy of the install — the playable install is never touched).

What it gives you:

- `autotest/enter-melee.ps1` — cold launch → intro skip → menus → a drivable mission, verified
  by memory rather than by screenshot. Also documents the TRIP-campaign route when you need
  other moving vehicles (mission 1 = "keep up with Taurus").
- `autotest/lib/memlib.ps1` — read speed, velocity (**`VY` = fall speed**), yaw, controls, and
  **every vehicle's world position** (`0x54E11C`, stride 0x20). Memory reads are exact and
  ~1000× cheaper than screenshots; prefer them for all verification.
- `autotest/lib/inputlib.ps1` / `maplib.ps1` / `focuslib.ps1` — key + mouse injection, the
  cursor mapping and cropped screen capture, and window focusing.
- `tools/physics-trace.ps1` + `tools/trace-diff.py` — deterministic scripted-input traces and a
  checkpoint diff, so physics claims are settled with numbers.

**Check the config before reverse-engineering:
[`../i76-uncap-lab/docs/CONFIG-OPTIONS.md`](../i76-uncap-lab/docs/CONFIG-OPTIONS.md)** indexes
every `dgVoodoo.conf` knob **by symptom**, and — critically — **which section each must live in**
(dgVoodoo silently ignores a key in the wrong section). Two problems that cost hours of
debugger work were one config line each. It also documents the DLL's runtime control file.

Clicking the menus is now **screenshot → read coordinate → click it**: the OS cursor position
*is* the engine's 640x480 UI coordinate, 1:1. `Capture-UI` crops to the game and rescales so one
image pixel is one cursor unit; `Click-UI` takes the number you read off it. Do **not** re-fit
cursor calibration constants — two earlier fits were wrong, both because the *measurement*
captured through a distorted aspect ratio.

Traps that produce **wrong data rather than errors** (full list in the README):

1. **NaN defeats range filters** in memory scans (`x < lo -or x > hi` never skips NaN) — use
   `abs(x - target) <= tol`.
2. **`VirtualQueryEx` needs `PROCESS_QUERY_INFORMATION`** — with `VM_READ` alone it enumerates
   *zero* regions and silently dumps empty files.
3. **Discrete key taps aren't comparable across frame rates** — they faked a 48-vs-25 m/s
   difference. Use continuous holds, or write the input block directly.
4. *(Historical, both fixed — see CONFIG-OPTIONS.md)* the game freezing and screenshots going
   stale while unfocused was `EnableInactiveAppState` being in the wrong section, **not** an
   engine limitation.

## Other hard-won invariants

- The joystick device token is **`joystick1`** — bare `Joystick` is DEAD
  (field-settled 2026-07-18: all bare-token bindings did nothing, all
  joystick1 bindings worked; the old "Button3 confirmed on bare Joystick"
  note was wrong). The lint tool cannot catch this — both spellings parse.

- The game prefix lives inside the Mac wrappers under
  `~/Applications/Sikarugir/…/Contents/SharedSupport/prefix/…`. All live game
  files (input.map, savegame.dir, saves) are THERE, not in this repo.
- `savegame.dir` truncates its newest entry on every game save (engine bug);
  the launcher stubs re-pad at boot and mid-session. Never "fix" the file size
  down. Save prune/delete work only with the game closed.
- Parallel Claude sessions run on this repo: re-check git state before staging
  and stage only your own hunks.

  **That is not sufficient on its own, field case 2026-08-08.** Staging only your
  own files does not protect you, because the OTHER session may stage everything.
  It happened twice in one afternoon: a wheel-buttons commit swallowed six files
  of unrelated music work, and an FFB commit swallowed a half-finished draft of a
  tool another session was still writing. Both commit messages then described only
  a fraction of what they contained.

  What actually helps:

  * **Commit your own files as soon as they are coherent.** An uncommitted file is
    what gets swept; time spent sitting in the working tree is exposure.
  * **Check `git log` after committing**, not just before. "nothing to commit,
    working tree clean" when you expected to commit means someone already took it.
  * To split a mixed commit that has NOT been pushed: `git reset --soft HEAD~1`,
    `git reset HEAD`, then re-commit in groups — and **verify the tree SHA is
    unchanged afterwards** (`git rev-parse HEAD^{tree}`). Equal trees prove the
    split moved nothing and lost nothing. Do not rewrite anything already pushed.
  * Also check whether it was really the other session. Staging four files and then
    writing a commit message for one of them produces exactly the same mess, from
    your own hand.

## The game does not start over Remote Desktop. Check this FIRST.

**Field case 2026-08-08, and it cost more time than any other single mistake in
this repo's history.** The game hung on "PLEASE STAND BY" forever. An entire
session went into bisecting it: three different `Strlkup.dll` builds tested to
byte-identical hangs, then Lossless Scaling, opentrack, AutoHotkey, the wheel,
dgVoodoo config, joystick enumeration and hidden modal dialogs all ruled out.
The agent concluded it had broken the user's setup and said so.

**The user was connected over RDP.** Nothing was broken. Reconnect at the
physical monitor and the game starts normally.

RDP gives the session a virtual display adapter with no 3D. A Glide/D3D11 present
blocks forever instead of failing, so the symptom is a **hang, not an error**, and
it looks exactly like a bad patch.

The signature — all of these together:

- blocked in a `UserRequest` wait with **~0.3s CPU over 140s** (it is not spinning,
  it is waiting on the display)
- all renderer modules loaded, nothing obviously missing
- screenshot capture fails with **"handle is invalid"** (same root cause: there is
  no real console display to grab)
- **the hang does not change when you change the thing you suspect** — this is the
  tell that should trigger the RDP check, and it fired repeatedly here, ignored

`Interstate 76/PLAY-i76-dgvoodoo.bat` has carried the warning in its header the
whole time: *"Run this ON THE PHYSICAL CONSOLE (not over RDP - 3D won't init on
RDP)."* It was read aloud during the failed bisection and not acted on. **Reading
a warning is not the same as checking it.**

This applies to agents too: a PowerShell/Bash tool call runs inside the user's
session, so **an agent testing the game over RDP is testing under RDP** and every
measurement it takes is invalid in the same way. Before trusting any launch-time
result, confirm the session type:

```powershell
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SystemInformation]::TerminalServerSession   # True = RDP, do not trust any launch result
query session                                                     # ">console" = at the monitor
```

Both verified. Two caveats found while verifying them, because the obvious check
is the one that does not work:

- **`$env:SESSIONNAME` is empty** in an agent's PowerShell process — not
  `"Console"`, not `"RDP-Tcp#1"`, empty. It is the check most people reach for and
  it silently reads as "not RDP" here.
- `query session` exits **255 even on success**; read its output, not its exit
  code.
