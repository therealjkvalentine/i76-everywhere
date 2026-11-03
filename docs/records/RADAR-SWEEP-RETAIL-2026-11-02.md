# Radar sweep in retail 1.0: clockwise, 30 steps, 6.0 s a turn, frame-rate neutral (2026-11-02)

Ported 2026-11-03 from the I26 emu-radar lane (lab capture `radar-20261102`, `radar.md`). No kit change. A player who
finds the cockpit radar "too slow and backwards" is describing the original.

**Rig.** Retail 1.0 `I76.EXE` (`6cc509ad`), 86Box at BelowNormal, emulated P166, Windows 95 RTM, T01 scene-1 bookmark,
sim physics, the 3D cockpit, no target locked. Two sessions, 4 tests (2 boots x a warm restart). Radar crops captured at
about 19 per second (host), the beam bearing taken from the scope's light-green pixels, host time mapped to guest ticks by
serial-port heartbeats, the unwrapped bearing fitted.

| condition | fps | rate, deg/s | period, s | steps (median dt, median deg) |
|---|---|---|---|---|
| parked, 600 m range, 640x480 | 13.9 | +59.87 | 6.01 | 119 (0.199 s, 11.5) |
| parked, range 100 m, 640x480 | 13.7 | +59.93 | 6.01 | 72 (0.203 s, 11.7) |
| parked, 600 m, 320x200 | 31.5 | +59.82 | 6.02 | 118 (0.198 s, 12.0) |
| parked, range 100 m, 320x200 | 31.5 | +59.92 | 6.01 | 70 (0.206 s, 11.9) |
| driving 13.5-22 m/s, 320x200 | 28.8 | +60.03 | 6.00 | 63 (0.178 s, 13.0) |
| driving 13.5-21 m/s, 640x480 | 12.7 | +58.39 | 6.17 | 54 (0.170 s, 11.9) |

+ = clockwise on screen. **Verdict:** clockwise, one turn in 6.0 s of game time, 30 positions of 12 deg stepped every
0.2 s, with no dependence on the frame rate (13-32 fps), the range setting or the car's speed. This matches the Gold spec
(`camera.md`, "Sweep"), so the sweep is the same in R and G ([BUILD-RULES.md](../engine/BUILD-RULES.md) s.2) and closes
EXE-DIFF-MAP's "retail radar rows were not read". Late segments with the mission failed or the car crashing are not used.
