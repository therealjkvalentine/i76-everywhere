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
