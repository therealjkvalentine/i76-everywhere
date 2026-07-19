# FFB shim — rumble from the game's OWN force-feedback stream

Interstate '76's force feedback is a **plugin architecture**: every sim tick the
engine fills a 364-byte force-state block (engine, speed, terrain surface,
skid/slide/airborne/oil flags, per-hardpoint weapon fire, steering-kick force
vector, tire status, and impact events with direction + damage) and hands it to
`i7_SFRCE.DLL` — a tiny DLL with **three stdcall exports** that is the only
thing in the game that touches DirectInput. Full reverse-engineering record:
[docs/FFB-DEEP-DIVE.md](../docs/FFB-DEEP-DIVE.md) → distilled in
[docs/MEMORY-MAP-INDEX.md](../docs/MEMORY-MAP-INDEX.md).

This shim **replaces** that DLL. The game then:

- activates FFB with **no DirectInput device at all** (this is what makes it
  work on Mac/Wine, where the game's native FFB path is otherwise dead — there
  is no registry gate in Gold; activation only needed the DLL to say yes);
- streams its real physics-driven force state into our code every tick;

and the shim:

- drives **XInput gamepad rumble** directly (impacts/engine/terrain → left
  motor; weapon fire/one-shots → right motor), using the real DLL's own
  magnitude formulas where known;
- writes a live telemetry line to `C:\AutoHotkey\ffb-state.txt` (speed,
  surface, flags, forces, motor levels) and appends every impact event to
  `C:\AutoHotkey\ffb-events.txt` — **this is the viewer**: watch the stream,
  tune the mapping, and answer the remaining unknowns (surface-id order,
  gain scales) from real play.

**STATUS: builds clean, spec-complete against the disassembly, NOT yet run
against the live game.** Rumble constants are first-guess; the telemetry
exists precisely so they can be tuned from a field run.

## Build (no binaries in the repo — same rule as smack-music-fix)

    brew install mingw-w64     # once
    ./build.sh                 # -> I7_SFRCE.DLL (32-bit PE, no CRT imports)

## Install

    ./install.sh               # Mac: finds the wrapper game dir, backs up the
                               # original as i7_sfrce_org.dll, drops ours in
    ./install.sh --revert      # put the original back

**Windows / Steam Deck warning:** the real `i7_sfrce.dll` + a DirectInput FFB
wheel gives *authentic* wheel force feedback there (the Deck's docked-wheel
setup, docs/STEAMDECK.md). Installing this shim REPLACES that with pad rumble —
only do it on a platform (Mac) or setup (pad-only) where real FFB isn't in
play. `--revert` undoes it.

## Files

- `i7ffshim.c` — the shim (block struct, rumble mapping, telemetry)
- `i7_sfrce.def` — the three exports, ordinal-exact vs the original
- `build.sh` / `install.sh`
