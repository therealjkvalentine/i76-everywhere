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

## Watching vs. shimming — which is less invasive depends on the box

The obvious question is why intercept at all: if the engine fills a block every tick, why
not just read it? The answer differs per machine, and it is not a matter of taste.

**On Windows with the wheel attached, watching is correct — and it is already what
`tools/ffb/` does.** `I7FF_InitSystem` opens a DirectInput force-feedback device at
startup; with the T300 enumerable that succeeds, the exe sets `0x52bbd0 = 1`, and
`ffb_tick` (`0x445ba0`) fills `0x4f2328` every sim tick. Reading it costs one
`ReadProcessMemory`. The shim buys nothing there.

**On the Mac there is nothing to watch.** Wine has no DirectInput force-feedback backend,
so `InitSystem` fails, `0x52bbd0` stays 0 — and the tick function is gated on that flag,
so the block is never filled at all. The shim's first job is not interception, it is
**activation**: replacing the DLL removes the DirectInput requirement entirely (the three
exports only have to return `HRESULT >= 0`), and the engine then streams its real force
state into code we control.

**The tempting shortcut has a landmine.** You could skip the DLL swap and just write
`0x52bbd0 = 1` from outside — one dword, no file replaced — and the tick function would
indeed start filling the block. But mind the order inside `ffb_init` (`0x445a60`):

```
0x445ad1  je   0x445b08         ; InitSystem failed -> stay off forever
0x445add  mov  [0x52bbd0], 1    ; FFB ACTIVE
0x445af3  call HeapCreate(0,0,0)
0x445af9  mov  [0x52bbcc], eax  ; private heap for impact-event nodes
```

The heap is created **after** the branch you failed. Flip the flag from outside and
`0x52bbcc` is still NULL, so the first impact reaches `HeapAlloc(NULL, 0, 0x20)` in
`0x445f70`. Continuous state — engine, speed, surface, slip flags, the hardpoint records —
would read fine; getting hit is what breaks, in a game about getting hit. Untested, and
worth one careful try before assuming it works.

**"Invasive" also cuts both ways.** The shim is a file swap outside the process that
`ffb-shim/install.sh --revert` undoes, and it never writes to a running game. The watcher
opens the process for read *and write*, and `Telemetry.ps1` does write — zeroing
`0x52bbe4` to dodge the crash in the stock DLL. Neither path is passive; they are invasive
in different places.

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

## Picking it up on the Windows box

Nothing here needs installing on Windows — the wheel/shaker stack *is* the
memory-watching path, and it already runs there. In rough order of value:

1. **Settle `+0x10`.** `tools/ffb/ffb-watch-effects.ps1` already prints the record. Fire
   the same weapon pointed different ways: if `+0x10` tracks where you are aimed it is a
   direction, if it tracks the weapon it is the firing frequency. Both halves key weapon
   effects off this record, so it is the cheapest disambiguation on the list.
2. **Set `gShimOwnsRumble := false` in `i76-remap.ahk` before judging pad rumble.** It
   ships `true`, which is Mac-correct — the shim owns the motor there. On a box with no
   shim it simply turns the pad mixer off, and the symptom reads as "rumble stopped
   working" rather than as an error.
3. **Leave `0x52bbe4` alone if you ever run the shim on Windows** — that pointer is what
   calls it. On a stock install keep zeroing it. The two crash fixes are alternatives, not
   layers.
4. **A7's two unknowns still stand**: shift-detection thresholds have never seen a real
   drive, and whether world explosions reach the effect table at all. Both are answered by
   driving, not by reading.
5. **Does the shim even load on Windows?** It is an ordinary win32 DLL out of
   `ffb-shim/build.sh`, so it should, but nobody has tried. Only worth the time if you
   want the in-process feed to replace the memory scan.
