# tools/haptics - one host for wheel FFB, pad rumble, bass shakers and motion simulator output

The implementation of [docs/HAPTICS-ARCHITECTURE.md](../../docs/HAPTICS-ARCHITECTURE.md), phases A and B: everything
that can be built and verified without the game. Nothing here launches `i76.exe`, touches a game folder, or opens a
device unless you pass `--live`.

```
 i76tel frames + events          Core (pure, no I/O, engine clock)                     Renderers (IRenderer)
 (UDP 7676 / shm / .i76rec /  -> Derive -> HapticCore:                              -> Wheel.DirectInput  (T300, constant force)
  scripted synthetic session)      ReferenceMixer  = tools/ffb/FfbMixer.ps1, ported    -> Pad.XInput         (L heavy / R texture)
                                   EffectEngine    = effects/*.json "chain" effects    -> Lfe.Synth          (LfeSynth.ps1 DSP -> WAV / EVO 4)
                                   duck, shaker voice budget, lints                     -> Lfe.Loopback       (WASAPI game-audio bed)
                                   -> Bus (+ Voices) + VehicleState (motion interface)  -> Motion.FileSink    (the raw VehicleState as CSV)
                                                                                        -> Motion.Udp         (LFS OutSim / OutGauge, Forza, i76motion: motion/README.md)
```

## Quick start

```powershell
tools\haptics\haptics.ps1 test                                   # every test: golden vs FfbMixer.ps1, C#, Python
tools\haptics\haptics.ps1 replay synthetic --out out\demo        # scripted 20 s session -> wheel CSV, pad CSV, shaker WAV, motion CSV
tools\haptics\haptics.ps1 replay C:\path\drive3.csv              # a tools/ffb capture
tools\haptics\haptics.ps1 replay session.i76rec --sinks lfe-wav --solo impact.collision
tools\haptics\haptics.ps1 preview --effect landing               # one effect alone, all devices, to files
tools\haptics\haptics.ps1 lint                                   # the design-rule lints
tools\haptics\haptics.ps1 synth --out replays\s.i76rec           # write the scripted session as real datagrams
tools\haptics\haptics.ps1 motion all --check                      # motion output: 7 synthetic scenarios -> packet logs, checked
tools\haptics\haptics.ps1 motion braking --targets flypt --send   # ... to FlyPT Mover on 127.0.0.1:4123 in real time (motion/README.md)
python tools\haptics\design\report.py                            # the design facility report (design/out/report/index.html)
```

The host binary is `src\Host\bin\Release\net8.0\i76haptics.exe` (`haptics.ps1` builds it on first use; .NET 8 SDK,
no NuGet packages). `haptics.ps1 help` lists every command.

## Layout

| path | what |
|---|---|
| `src/Haptics/Core/` | `ReferenceMixer` (line-for-line port of `FfbMixer.ps1`, incl. the 560dcd2 blast/duck fix), `Derive` (frames -> Tel-Sample, host-derived events, `VehicleState`), `EffectEngine` (chain effects), `HapticCore` (the pipeline step), `Bus` |
| `src/Haptics/Effects/` | effect/rig loading, the expression language, tune build from the tunemap, lints |
| `src/Haptics/Transport/` | i76tel layouts (frozen v2 + v3 headers embedded, live header parsed at run time), codec, `ShmReader` (seqlock, open-existing read-only), `UdpListener`, `.i76rec` recorder/reader, `Synthetic` sessions |
| `src/Haptics/Renderers/` | the five renderers and `RendererRegistry` |
| `src/Haptics/Pipeline.cs` | the host loop (250 Hz core grid on the engine clock; real-time pacing with a lateness histogram) |
| `src/Host/` | the CLI |
| `effects/*.json` | one file per effect (schema: `schema/effect.schema.json`) |
| `rigs/*.json` | outputs, renderer per output, device facts (schema: `schema/rig.schema.json`) |
| `schema/legacy-tunemap.json` | where each of FfbMixer.ps1's 66 tunables lives now |
| `stock/stock-ffb-reference.json` | what the stock `i7_sfrce.dll` did per event (generated) |
| `design/` | Python design facility: `migrate_tune.py`, `stock_reference.py`, `gpw_spectra.py`, `report.py`, `i76rec.py`, tests |
| `tests/` | `golden/make-golden.ps1` (runs the real FfbMixer.ps1), `Haptics.Tests` (C# runner) |
| `src/Haptics/Core/Motion/`, `motion/` | the motion output: MotionCore, `targets.json`, the validator `i76motion.py`, `make_synthetic.py`, `motion_preview.html` ([motion/README.md](motion/README.md)) |

Gitignored: `bin/ obj/`, `tests/golden/out`, `tests/out`, `design/out` (everything derived from the owner's game files:
analyses, spectrograms, the report), `out/`.

## How it is proven equivalent to what exists

* **Core = FfbMixer.ps1.** `tests/golden/make-golden.ps1` dot-sources the real `tools/ffb/FfbMixer.ps1` and runs it over
  51 synthetic drives (every `ffb-mixer-test.ps1` scenario, the nine `ffb-lfe-probe.ps1` scenarios, the blast-duck fix,
  stale-sim gate, RPM engine) plus the two captured drives; the C# port reproduces every output (force, channels,
  notes, every bus field, the pad down-mix, the wheel renderer) - 566,368 values, 0 mismatches at 1e-6.
* **Effect files = the tune.** `design/migrate_tune.py --diff` shows all 66 keys in exactly one place with the same
  value, and the golden drives replay identically with the tune read back from the files.
* **Lfe.Synth = LfeSynth.ps1.** The nine probe scenarios rendered through the host are sample-identical to the WAVs
  `ffb-lfe-probe.ps1` writes.
* **Transport = i76tel.** Host-written v2 and v3 sessions decode in the proxy agent's own `i76tel.py`
  (`decode_datagram`), event for event.

## How to add an effect

1. Copy a chain effect (e.g. `effects/landing.json`) to `effects/<id>.json`; `id` must equal the file name.
2. `source`: an `event` (`IMPACT`, `SOUND_START`, `LANDING`, ... - `EffectSet.EventFields` lists them and their fields)
   with optional `where` filters and a `level` expression, or a continuous `channel` expression over frame variables
   (`speed`, `rpm`, `flag_grip_limit`, `accel_x`, `susp_max`, ... - `EffectSet.FrameVariables`). Expressions:
   `+ - * / ( )`, `clamp min max abs sqrt pow`.
3. `response` (gain, threshold, min-force floor, gamma), `envelope` (attack/hold/decay ms + `retrigger` restart|max|ignore,
   or `smooth_ms` for continuous), `carrier` (base..high Hz by level).
4. `routing`: `wheel` {amp (fraction of full scale), shape impulse|buzz, hz, direction +1|-1|side|wheel_side|impact_x|from_yaw},
   `pad` taps [{motor L|R, gain}], `lfe` {amp, hz}. Texture goes to the pad's R motor, weight to L and to the shaker,
   force to the wheel (HAPTICS-ARCHITECTURE 6.3).
5. `mix`: group, priority, optional `duck` {groups, depth}. `reference`: stock id + the sounds the game plays for it.
6. `preview`: the event to inject (or frame values) so `haptics.ps1 preview --effect <id>` can render it alone.
7. `haptics.ps1 lint`, `haptics.ps1 preview --effect <id>`, `python design/report.py --only <id>`, `haptics.ps1 test`.

Legacy effects (`"model": "legacy.*"`) hold the reference model's numbers: edit the value in the effect file (the
tunemap says which key it is), never in FfbMixer.ps1, then run the tests - the golden will then differ from
FfbMixer.ps1 by design, so update `Tune.Defaults` only when FfbMixer.ps1 itself is retired.

## Outputs, devices and the --live rule

| sink | renderer | file (default) | live (`--live`) |
|---|---|---|---|
| `wheel-file` | Wheel.DirectInput | `<tag>.wheel.csv` (model, voices, device force) | DirectInput constant force on `device_match` (exclusive; the game must not hold it - mode A, HAPTICS-ARCHITECTURE 3.3; the host does not write `0x52bbe4`) |
| `pad-file` | Pad.XInput | `<tag>.pad.csv` | `XInputSetState` on `slot`; motors zeroed on exit |
| `lfe-wav` | Lfe.Synth | `<tag>.lfe.wav` (16 kHz mono) | waveOut to the device whose name matches `device_name_match` (EVO4) |
| `loopback-wav` | Lfe.Loopback | mixed into the shaker WAV from `--loopback-wav FILE` | WASAPI loopback of the default render endpoint, mixed under the synth |
| `motion-file` | Motion.FileSink | `<tag>.motion.csv` (the VehicleState) | - |
| `motion-udp` | Motion.Udp | `<tag>.<target>.<format>.i76rec` packet logs + `<tag>.motionout.csv` | UDP to the enabled `motion/targets.json` targets, loopback only (third-party software, no actuator) |

**Motion.** [docs/MOTION-OUTPUT.md](../../docs/MOTION-OUTPUT.md) phases M0-M3 are built: `Motion.Udp` (sink `motion-udp`,
command `haptics.ps1 motion`) runs MotionCore on `CoreStep.State` / `Events` and writes LFS OutSim classic / OutSimPack2 /
OutGauge, Forza Sled / Dash and our own i76motion v1; setup of FlyPT Mover / SimHub / SimTools, sign conventions, the
validator and what is stubbed: [motion/README.md](motion/README.md). Another motion renderer still plugs in the same way:
implement `IRenderer`, read `CoreStep.State` (`Core/VehicleState.cs` documents frames, axes, units),
`RendererRegistry.Register("Motion.<name>", ...)`, and name it in `rigs/*.json`.

## Stubbed, unverified, or left open (honest list)

* **Live device paths were not run** (the console was not available): wheel acquire/force, XInput, waveOut streaming.
  They are ports of the field-proven PowerShell paths (FfbCore.ps1, LfeSynth.ps1, i76-remap.ahk's XInput) and are
  behind `--live`; owner tests C2-C4 below exercise them.
* **WASAPI loopback**: the COM chain (enumerator, IAudioClient loopback Initialize, capture client, Start) was opened
  once for 1 s with nothing playing and succeeded (44.1 kHz x2 float); WASAPI delivers no packets while the endpoint
  is idle, so the packet path was not exercised with real audio. The bed DSP (resample, HP/LP, gate, duck) is tested
  offline from a WAV.
* **No real `.i76rec` exists yet**: the scripted synthetic session stands in until owner test C1 records one.
* **SHOT magnitude**: i76tel SHOT carries damage per hit, not the hardpoint FFB gain (5/10/60) the weapon channel was
  tuned on; `weapon.fire#/source/shot_mag` is a nominal `10` until a capture maps one to the other.
* **Explosion reach**: blast level = `clamp(1 - dist/100 m)` floored at the reference model's blast threshold; the
  engine's own concussion range is unknown (backlog P4-20).
* **Lints that fire on the shipped tune** (reported, not changed - feel decisions are the owner's): 4 continuous
  shaker sources (rule <= 3), heave carrier 35 Hz inside the engine's 26-38 Hz sweep and scrub 70 Hz inside the road
  bed's 55-72 Hz, continuous wheel channels reaching 91% of the clamp (rule 40-70%), and "every bed at full + one
  transient" headroom above 0.95.
* **HP/LP**: the shipped shaker chain is HP 11 Hz / LP 85 Hz (x1.35 inside LfeCore), not the "22/90" the design text
  says; the rig file carries the shipped values.
* **B4 real-time loop: exit criterion NOT met.** A 600 s replay at 250 Hz (`replay out\b4\synthetic-600s.i76rec --realtime`,
  all four file sinks, 2026-10-10, n = 1, on a desktop doing other work) gave 149,997 updates: p50 0.00 ms, p99 0.44 ms,
  p99.9 0.58 ms, max 13.6 ms. 3 updates were more than 8 ms late (target: none). Still to do: rule out file-sink I/O and GC
  (rerun with no sinks, `GCSettings.LatencyMode = SustainedLowLatency`, a multimedia timer), then repeat for n >= 3.
* Golden real drives: `drive2.csv` / `drive3.csv` are gitignored, so a fresh checkout has none. Set
  `I76_REAL_DRIVES=<folder>` (for example the main checkout's `tools\ffb`) before `haptics.ps1 test`, or the two real-drive checks are skipped.
* **Motion**: M4 (SimHub .simdef, Open Game Telemetry), M5 (proxy motion fields) and M6 (washout, direct actuator path) are
  not built; no desk bench (FlyPT / SimHub) was run by an agent (nothing may be installed): owner tests 16-24. Details in
  [motion/README.md](motion/README.md).
* `i76tel.py --record` (design A1) was not added: the proxy agent owns `i76tel.py`; recording is `haptics.ps1 record`.

## Owner-console tests (Phase C)

Also in [docs/OWNER-TEST-LIST.md](../../docs/OWNER-TEST-LIST.md). Lab copy only; A/A before A/B; report n.

* **C1 Record a real session.** Lab game with `I76_TELEMETRY=1 I76_SOUND_EVENTS=1 I76_DAMAGE_EVENTS=1`, then
  `haptics.ps1 record --udp --out replays\t01-c1.i76rec --seconds 300` while driving t01 (shoot, hit a wall, jump, get
  shot). Then `haptics.ps1 decode replays\t01-c1.i76rec --events` and `haptics.ps1 replay replays\t01-c1.i76rec`.
  Pass: v3 frames, SOUND_START with is_player 1 for your own weapons and 0 for an AI car's, DAMAGE_SIDE on hits.
* **C2 All three outputs together, dry run then live.** `haptics.ps1 live --source udp` (files only) during a drive; then
  `--live` with the wheel, pad and shakers connected (FFB-STACKS fight 3). Question: interference and dropouts, not feel.
* **C3 Latency.** Fire one shot and ram one wall with `--live --record`; phone microphone on the shaker; compare event
  frame times in the recording with the shaker onset.
* **C4 Coexistence (mode A).** With the host holding the wheel (`--live`), pull the trigger: does the game's DLL still play
  anything? (Decides whether mode C is needed for both feels.)
* **C5 Hardpoint +0x10.** Same weapon aimed two ways with `tools\ffb\ffb-watch-effects.ps1`: firing frequency or direction?
* **C6 Explosion reach.** An AI car explodes nearby; note the EXPLOSION distance and whether a concussion node appeared;
  set `explosion.blast#/source/reach_m` from it.
* **C7 Pad and shaker preview by hand.** `haptics.ps1 preview --effect <id> --live --sinks pad,lfe` for impact.collision,
  landing, weapon.fire, slip.grip_limit: one at a time, does each read as what it is? (Owner present: devices move.)
* **C8 Feel session.** Report open on a second screen, one effect file at a time (hot-reloaded by `live`), two-lap method.
