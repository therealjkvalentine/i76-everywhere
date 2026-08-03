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
