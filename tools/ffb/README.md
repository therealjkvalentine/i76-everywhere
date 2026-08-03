# Custom force feedback for Interstate '76

The engine's own FFB is a closed 1997 system: on fixed events it plays a
pre-authored effect from `force\*.frc`. It has **no concept of slip, load or road
texture** — that vocabulary postdates it. So a communicative wheel has to be
synthesised from game state, outside the engine.

## Status

| piece | state |
|---|---|
| **FFB output** (`FfbCore.ps1`) | **WORKING** — acquires the T300 and drives arbitrary force |
| Telemetry read | player-entity chain resolves; steer/throttle live. Position/velocity offsets **not yet identified** |
| Force mixer | not built |
| Observability panel | not built |

## FfbCore.ps1 — the output layer

Drives DirectInput by hand through its COM vtables, compiled at runtime by
`Add-Type`. There is no managed DirectInput available offline (SharpDX is a NuGet
package) and no C compiler on this machine, so this needs nothing installed.

```powershell
. tools\ffb\FfbCore.ps1
$d = Ffb-Open                  # find + acquire the first FFB device
Ffb-Constant $d 6000           # steady force, -10000..10000, sign = direction
Ffb-Texture  $d 3000 $tick     # modulated force for road/buzz
Ffb-Stop $d ; Ffb-Close $d
```

### Five things that each cost a debugging round

Recorded because none produced a useful error message:

1. **`DirectInput8Create` needs a non-NULL `hinst`.** `GetModuleHandle($null)`
   returns NULL from PowerShell → `E_INVALIDARG` (0x80070057). Use
   `LoadLibraryA("dinput8.dll")`; DirectInput only wants *some* live module.
2. **`DIDFT_ANYINSTANCE` is `0x00FFFF00`**, not `0x0000FF00`. Wrong mask →
   `SetDataFormat` fails `E_INVALIDARG` with no other clue.
3. **Exclusive mode needs a real window owned by this process.** NULL hwnd →
   `E_HANDLE`; `GetConsoleWindow()` is *not* sufficient either (a child
   PowerShell may share or lack a console) and `Acquire` then fails
   `ERROR_INVALID_WINDOW_HANDLE` (0x80070578) even after `SetCooperativeLevel`
   returned OK. A hidden WinForms window works — and must stay referenced, or the
   GC destroys it and takes the acquisition with it.
4. **PowerShell parses `0xFFFFFFFF` as Int32 `-1`**, which will not coerce to the
   `UInt32` that `dwDuration` / `dwTriggerButton` want. Use `4294967295`.
5. **Periodic effects do not work on this wheel.** `CreateEffect(GUID_Sine)`
   returns `REGDB_E_CLASSNOTREG` (0x80040154) although constant force is fine.
   So texture is synthesised by modulating constant force — which is the better
   design anyway: one primitive, one place magnitude is decided, and the mixer
   stays additive.

## The constraint that shapes everything

**FFB requires DirectInput EXCLUSIVE acquisition.** The game takes it at startup,
so while the game holds the wheel we cannot. This is why the interposer is
flag-optional: you get the engine's weapon effects **or** our synthesised feel,
not both.

Freeing the device means stopping the game acquiring it. That is a one-instruction
patch — FFB init is called unconditionally from `0x402F93` (see
`docs/WHEEL-T300.md`), so NOPing that call skips it entirely and leaves the wheel
free. Reversible, memory-only. Not yet implemented.

## Telemetry — what is known

Player entity resolves via `[[[0x54a264]]+0x70]` (live-verified):

| offset | field |
|---|---|
| `+0x08` | world transform (rotation matrix) |
| `+0xe0` | steer applied (float) |
| `+0xe4` | throttle applied (float) |

**Position/velocity are not yet pinned.** Identifying them needs the car
*moving* — a stationary dump cannot distinguish a position field from any other
world-scale float. `ffb-telemetry-probe.ps1` samples the struct while you drive
and reports which offsets vary like position, which is the intended next step.

Once position is known, everything else derives from it without further RE:
speed and acceleration from position deltas, lateral acceleration (a slip proxy)
against heading from the transform, braking from negative longitudinal
acceleration, and collisions from acceleration spikes.

## Design language

Reuse the rumble mixer's, which is already field-proven (`i76-remap.ahk`):
hierarchy and restraint — continuous states held **low** so transients read on
top; a distinct signature per event; and set-on-change rather than spamming the
device.
