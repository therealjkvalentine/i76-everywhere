# The two FFB stacks — what runs where, what overlaps, what fights

Two threads built force feedback for this game from opposite directions and neither
knew the other's code. Both work. They have **never been run together**, and three of
their pieces actively contradict each other. This is the map; it is what the merge of
2026-09-06 produced, not a new design.

## The two stacks

| | **Windows stack** — `tools/ffb/` | **Mac stack** — `ffb-shim/` |
|---|---|---|
| where it runs | outside the process, PowerShell | inside the process, a C DLL that **replaces** `i7_sfrce.dll` |
| how it gets state | `ReadProcessMemory` on the entity chain + the block at `0x4f2328` | the engine hands it the block as the call argument, every tick |
| what it drives | T300 wheel over DirectInput (`FfbCore.ps1`), bass shakers (`LfeSynth.ps1`) | XInput gamepad motors |
| its idea of feel | **synthesise** what a 1997 engine has no vocabulary for — slip, load, road texture — from game state | **replay what the engine decided**, textured by the game's own `.gpw` skid/surface audio |
| status | output, telemetry, mixer, interposer and calibration all working; feel tuning not started | field-run and tuned on the Mac over 2026-07-19/20 |
| written up in | `tools/ffb/README.md`, [FFB-DESIGN-LIBRARY.md](FFB-DESIGN-LIBRARY.md) | [FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md), `ffb-shim/README.md` |

`sound-rumble/` is a third, experimental path: a `dsound.dll` proxy that derives rumble
from the audio actually playing. It is a backup for platforms where the shim cannot go,
and is **mutually exclusive with the shim** — its installer already refuses to sit
quietly alongside one.

## Where they independently agree

Worth trusting more than either alone, because the two routes share no code and no
method — one measured a live process from outside, the other disassembled the DLL:

- the **six-slot hardpoint array** at block `+0x030`, stride `0x1C`;
- `+0x160` is the **sim delta-time**, ~1/20 s;
- `+0x0D8` is *not* a seventh slot — it is a different structure updating at tick rate;
- the engine's **effect table beats the input flag** as a "a weapon actually fired"
  signal. The Windows side reached this by watching the input bytes produce no response
  across two field sessions; the shim reached it by being handed the same records. Both
  now key weapons off the engine's decision, not off a button.

Field-by-field comparison, including which side named what, is in
[MEMORY-MAP-INDEX.md](MEMORY-MAP-INDEX.md) under "The effect-slot array".

## Where they disagree

**Block `+0x10` in each hardpoint record.** Measured live it reads like a *direction*
(0.8104, 180.8 — and 180.8 looks like degrees). Disassembled it is the *firing
frequency*, with direction living on the impact nodes instead. The DLL's own log line
carries both (`Hardpoint:%d WpnId:%d Freq:%d Gain:%d Direction:%d`), so the format
cannot settle it. Both halves key weapon effects off this record, so it is worth one
drive: fire the same weapon pointed different ways and watch whether `+0x10` moves.

## Where they fight — read before running both

**1. The Windows crash workaround silences the shim.** `Telemetry.ps1` zeroes
`0x52bbe4`, the resolved `I7FF_SIM_Effect` pointer, so effects are built but never
call into the DLL where the fault at `I7_SFRCE.DLL+0x2505` lives. The shim *is* the
DLL behind that pointer. Zero it and the shim stops receiving anything.

The two fixes are alternatives, not layers, and the shim is the stronger one where it
runs: the fault is in the **original** DLL, so replacing that DLL removes the reason to
bypass it, and the force stream keeps flowing into code we control. On a shimmed
install, do not zero the pointer. On a stock install, keep zeroing it.

**2. Pad-motor ownership is now shim-first everywhere.** `i76-remap.ahk` ships
`gShimOwnsRumble := true`, which skips its own rumble mixer entirely so the two never
fight over one motor. That is correct on the Mac. On any machine **without** the shim —
the Windows rig, the Steam Deck — it silently turns pad rumble off, and nothing warns
you. Set it to `false` there.

This is not auto-detected, deliberately: the marker exists (`ffb-shim/install.sh` leaves
the stock DLL as `i7_sfrce_org.dll` beside the game exe, so its presence means "the shim
is installed"), but nobody has run that check on a real Windows or Deck install, and a
wrong guess here reads as "my rumble broke" rather than as an error.

**3. Three outputs, never run together.** Wheel, shakers and pad have each only ever
run alone. `docs/READY-TO-TEST.md` §A7 already flags wheel-vs-shaker interference as
unproven; the pad is now a third claimant on the same events.

## Telemetry: two wires carrying the same picture

The shim sends its own format to UDP `127.0.0.1:17676` (consumed by
`tools/ffb-udp-listen.py`, aimed at SimTools/SimHub — [MOTION-SIM.md](MOTION-SIM.md)).
The Windows stack sends SimTools PluginAPI and OutSim formats on 4123/4124
(`tools/ffb/ffb-telemetry-udp.ps1`). No port collision, but it is two encodings of one
data set, and only one of them needs `ReadProcessMemory` to produce it.

An obvious consolidation — let the in-process shim feed the PowerShell mixer instead of
the mixer scanning memory for what the engine already knows — is **untried**, and would
need the shim running on Windows, which has never been done.

## Still unproven

- `+0x10`: frequency or direction (above).
- The shim has only ever run under Wine on the Mac. It is an ordinary win32 DLL, so it
  should load on Windows, but that is an expectation, not a result.
- Everything in `docs/READY-TO-TEST.md` §A7: shift-detection thresholds have never seen
  a real drive, and whether world explosions reach the effect table at all is unknown.
- Whether the shim's `.gpw`-derived skid texture and the Windows mixer's synthesised
  road texture describe the same surface the same way.
