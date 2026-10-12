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
tools\haptics\haptics.ps1 play replays\s.i76rec --port 17676      # send it to 127.0.0.1:17676 in real time (a stand-in game for `live`)
tools\haptics\haptics.ps1 motion all --check                      # motion output: 7 synthetic scenarios -> packet logs, checked
tools\haptics\haptics.ps1 motion braking --targets flypt --send   # ... to FlyPT Mover on 127.0.0.1:4123 in real time (motion/README.md)
python tools\haptics\design\report.py                            # the design facility report (design/out/report/index.html)
```

**Watching it run:** add `--debug-udp` to `live`, `replay` or `motion` and open I76 Debug (`tools\debug\DEBUG.bat --tee 17676`,
then `live --source udp --port 17676 --debug-udp`): the bus, every effect's wheel / pad / shaker contribution, the pad motors,
the shaker level and spectrum, the stems playing and the motion channels, status word and packet rates, live in a browser
(`src/Haptics/DebugPublisher.cs`; loopback 127.0.0.1:17680, at most 60 datagrams per second; off by default, zero cost when off).

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
| `src/Haptics/RealTime.cs` | the real-time wait (high-resolution timer + spin, boosted thread), pre-JIT, per-update LoopStats, ChunkedList (B4 section) |
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

## Lfe.Stems: the HD sound pack's LFE stems on the shaker

A third shaker source beside Lfe.Synth (synthesised from the bus) and Lfe.Loopback (the game-audio bed), as
[docs/SOUND-HD-PACK.md](../../docs/SOUND-HD-PACK.md) section 4 recommends: the per-sound 25-90 Hz stems that
`tools/soundhd` writes to `out\pack-v1\lfe\` (16 kHz mono, plus `lfe-manifest.json`), played on the i76tel v3
`SOUND_START` / `SOUND_STOP` events. Code: `src/Haptics/Renderers/LfeStems.cs`; tests: `tests/Haptics.Tests/StemsTests.cs`.

```powershell
tools\soundhd\.venv\Scripts\python tools\soundhd\soundhd.py build                # the stems are gitignored audio: build them once (~2 min)
tools\haptics\haptics.ps1 stems status                                           # manifest, stems on disk, the effective source gains
tools\haptics\haptics.ps1 stems render --name whcan --dist 25                    # one SOUND_START -> out\stems\stem_whcan.lfe.wav + .stems.wav
$env:I76_LFE_SOURCES='synth=0,stems=1'; tools\haptics\haptics.ps1 replay synthetic   # one run with stems only
python tools\haptics\design\stems_view.py                                        # each stem next to what Lfe.Synth makes for the same event
```

* **Voices.** `SOUND_START`: the name is looked up in the manifest (`by_alias`, case-insensitive, with or without
  `.gpw`) and a voice starts on the first sample of the core update that carried the event. Modes 1 (loop) and 2
  (sustained) loop until the `SOUND_STOP` with the same voice address (Derive now passes it as the event field
  `voice`); a stop fades out over `fade_ms`. One-shots end at the stem's end. A `SOUND_STOP` with no live voice is
  counted and ignored; `loop_max_s` can cap a loop whose stop never arrives (default off).
* **Gain.** vol% / 100 x distance attenuation x manifest `suggested_gain` x `category_gain` x `gain`. The player's own
  sounds and 2D sounds (no position) play at full level; others by `distance.curve` (`inverse` = DirectSound's
  rolloff law, `inverse_square`, `linear`, `none`) between `ref_m` and `max_m`, silent beyond `max_m` and while no
  player is present. The distance is taken at the start; a moving source is not tracked (no position updates exist).
* **Rate.** For `rate_scale.categories` (engine loops) the playback rate is event Hz / the stock sample rate (read
  from the pack's `manifest.json`), so idle (8268.75 Hz) plays the stem x0.75. The player's own engine loop then
  follows the frame rpm with the engine's pitch law (`8268.75 + 8268.75 x (rpm - 1050) / 4950`, callback 0x424ca0),
  because `SOUND_START` only carries the start Hz. AI engine loops keep their start Hz.
* **Budget.** `max_voices` (6) with priority player > nearby (within `near_m`, or 2D) > far, then level: a new voice
  steals the weakest only if it outranks it, otherwise it is dropped. A soft limiter (tanh above `limiter.knee`, never
  above `limiter.ceiling`) keeps the stems sum bounded before it joins the synth.
* **Mix.** The stems are summed into Lfe.Synth **before** its HP/LP and limiter, like the loopback bed, and are not
  ducked under transients (they are the transients). `outputs.lfe.sources` in the rig sets the gain of each source:
  `{"synth": 1, "stems": 1}` both (shipped), `{"synth": 0, ...}` stems only, `{"stems": 0}` synth only (then Lfe.Stems is
  not opened at all). `I76_LFE_SOURCES=synth=..,stems=..` overrides the rig for one run; the Lfe.Stems summary line
  prints the gains in force and where they came from. With the default gains every existing render is sample-identical
  until a `SOUND_START` with a stem arrives (the probe and golden tests are unchanged).
* **Opened** automatically with any `lfe` sink when the rig's `outputs.stems` is enabled and `sources.stems > 0`; the
  sink `stems` opens it explicitly (alone it renders a standalone `<tag>.stems.wav`). In file mode it always writes
  `<tag>.stems.wav`, the stems signal alone after its limiter. Live, it rides on Lfe.Synth's waveOut stream.
* **Fallback.** No manifest, or none of its stems on disk: one log line, the summary says `shaker = Lfe.Synth only`, and
  the output is byte-identical to synth only (tested). A sound without a stem (tyres, horns, UI, CB) is counted per name.

Open or unverified: nothing here has run against the game or a shaker (owner test 16). The stems are not compensated
by the rig's response curve (`resp_hz` / `resp_rel`), which the synth's oscillators are; across 25-90 Hz that curve
asks for 1.0-1.5x, so stems may feel slightly weaker than synth content of the same level. The 7 dropper / nitro
stems have no Lfe.Synth effect on their event at all (the design view lists them). Event-to-shaker latency is the
synth's plus one core update at most.

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
* **B4 real-time loop: exit criterion met on replay (n = 2 x 600 s), see "B4 real-time loop" below.** Not yet run against
  the game or with `--live` devices; the live loop was measured fed by `haptics.ps1 play` on loopback.
* Golden real drives: `drive2.csv` / `drive3.csv` are gitignored, so a fresh checkout has none. Set
  `I76_REAL_DRIVES=<folder>` (for example the main checkout's `tools\ffb`) before `haptics.ps1 test`, or the two real-drive checks are skipped.
* **Motion**: M4 (SimHub .simdef, Open Game Telemetry), M5 (proxy motion fields) and M6 (washout, direct actuator path) are
  not built; no desk bench (FlyPT / SimHub) was run by an agent (nothing may be installed): owner tests 17-25. Details in
  [motion/README.md](motion/README.md).
* `i76tel.py --record` (design A1) was not added: the proxy agent owns `i76tel.py`; recording is `haptics.ps1 record`.

## B4 real-time loop: timing, diagnosis and results

Code: `src/Haptics/RealTime.cs` (RtWaiter, RtWarmup, LoopStats, ChunkedList), `Pipeline.Run` (replay `--realtime`),
`Program.Live` (the `live` command), `MotionUdpRenderer.OutputLoop`. Every real-time run writes `<tag>.deadlines.txt`
(`live.deadlines.txt` for live): the histogram, the wait mode, why each update over 1 ms was late (the work before the
wait overran, or the wake-up was late; was there a GC), GC counts and pause, per-stage times (p50 / p99 / p99.9 / max
for input, core, every renderer) and the ten worst updates with their stage breakdown. Motion.Udp's summary line adds
its send timing (gaps between ticks, tick lateness).

* **Tick thread.** `RtWaiter`: `timeBeginPeriod(1)`, a `CREATE_WAITABLE_TIMER_HIGH_RESOLUTION` waitable timer to 0.6 ms
  before the deadline, then a spin on the stopwatch; thread priority Highest + MMCSS "Games";
  `GCSettings.LatencyMode = SustainedLowLatency` for the run; every host method JIT-compiled before the clock starts
  (update #1 otherwise compiled the hot path for 6-8 ms). Deadlines are absolute (k x 4 ms), not "previous + 4 ms".
* **live is three threads.** A source thread (blocking UDP receive or 1 ms shm poll, `--record`, decode, Derive) hands
  frames to the tick over a queue; a reload thread checks `effects/*.json` once a second (that directory scan used to
  run on the tick); the tick drains the queue, steps the core and renders.
* **Motion on its own schedule.** In real-time runs `Motion.Udp` only feeds MotionCore from the core update; its own
  boosted thread wakes at every output tick (1 / `output_hz` on the wall clock) and sends. Offline replays are unchanged
  (byte-identical packet logs, tested).
* **No regrowing buffers.** Lfe.Synth's WAV buffer is a `ChunkedList<short>` (64 K chunks). Lfe.Stems' `Recorded`
  is still a `List<short>` (same regrow, only when stems are built; not touched here).
* `--rt legacy` (or `I76_RT=legacy`) brings back the old wait (Thread.Sleep(1) + 1.5 ms spin, no boost, no pre-JIT,
  motion sent from the core update) for A/B; `--rt hires` is the default.
* `haptics.ps1 play <rec> --port N` sends a recording to 127.0.0.1:N at its recorded times (its own pacing is printed),
  which stands in for the game: `play out\b4\synthetic-120s.i76rec --port 17676` beside
  `live --source udp --port 17676 --sinks wheel-file,pad-file,lfe-wav,motion-file,motion-udp --seconds 124`.

**Diagnosis (what the instrumentation showed).**
1. **live: the timer resolution.** The old live loop slept with `Thread.Sleep(1)` but never called `timeBeginPeriod`;
   since Windows 10 2004 the timer resolution is per process, so each sleep lasted ~15.6 ms and the loop ran in bursts
   of four updates: p50 6 ms late, 38 % of updates over 8 ms. Motion ticks rode on those updates, so they left at
   8 / 12 ms spacing even when the loop was on time (100 Hz ticks on a 250 Hz grid).
2. **replay: wake-up and preemption.** In a 120 s `--rt legacy` replay, 64 of the 68 updates later than 1 ms woke late
   from Sleep(1) with slack in hand; none had a GC since the previous update. Two more were update #1 (JIT, 6 ms).
3. **The 600 s maximum: a List regrow.** With the timer fixed, the one late update in 600 s (#131,073, 2.9 ms) spent
   6.8 ms in Lfe.Synth: 131,072 x 64 samples = 2^23, the WAV buffer's List doubling from 8 M to 16 M samples. That is the
   mechanism of the original 13.6 ms. Fixed with the chunked buffer.
4. **GC is not a problem at this rate**: 473 gen0 / 42 gen1 / 6 gen2 collections in 600 s, 55-61 ms total pause,
   none behind a missed deadline; the worst was a gen1 at about 1.8 s that made one core step take 5.7 ms (1.8 ms late).
   So no NoGC region and no pooling: the hot path still allocates (sample clones, CoreStep, event lists).

**Results (2026-10-11, this desktop doing other work, file sinks only, no device opened).** Lateness = wake time minus
deadline, per 4 ms core update.

| run | n updates | p50 | p99 | p99.9 | max | > 8 ms |
|---|---|---|---|---|---|---|
| before: 600 s replay, old loop (2026-10-10) | 149,997 | 0.00 | 0.44 | 0.58 | 13.6 | 3 |
| before: 120 s replay, old loop | 29,997 | 0.00 | 0.47 | 2.18 | 12.08 | 4 |
| before: 120 s replay, `--rt legacy` (instrumented) | 29,997 | 0.00 | 0.46 | 1.76 | 5.75 | 0 |
| after: 120 s replay | 29,997 | 0.00 | 0.40 | 0.45 | 7.87 (update #1, JIT; pre-JIT added after) | 0 |
| after: 600 s replay (pre-JIT, List regrow still in) | 149,997 | 0.00 | 0.39 | 0.44 | 2.90 | 0 |
| **after: 600 s replay (B4 run)** | **149,997** | **0.00** | **0.41** | **0.47** | **2.24** | **0** |
| before: live, old loop, 64 s, play at 60 Hz | 15,997 | 6.13 | 13.74 | 14.19 | 24.53 | 6,081 |
| live, new threads but `--rt legacy`, 124 s | 31,000 | 0.00 | 0.41 | 0.70 | 22.32 | 7 |
| after: live, 64 s | 15,984 | 0.00 | 0.41 | 0.71 | 1.58 | 0 |
| **after: live, 124 s** | **30,951** | **0.00** | **0.40** | **0.52** | **1.23** | **0** |

Motion.Udp send timing in the same live runs (100 Hz, 10 ms period):

| run | gaps | p1 / p50 / p99 / max gap (ms) | gaps > 1 ms off 10 ms | tick lateness p50 / p99 / max |
|---|---|---|---|---|
| `--rt legacy` (sent from the core update) | 12,187 | 7.83 / 10.40 / 12.18 / 30.20 | 12,173 | 2.16 / 3.46 / 25.27 ms |
| after (own output thread), 64 s | 6,225 | 9.61 / 10.00 / 10.39 / 11.50 | 2 | 0.01 / 0.40 / 2.03 ms |
| **after, 124 s** | **12,192** | **9.60 / 10.00 / 10.40 / 10.71** | **0** | **0.01 / 0.40 / 0.79 ms** |

The `play` sender itself kept p99 0.41 ms, max 1.8-2.3 ms in every run. Open: n is 2 for the 600 s replay and 2 for
live; nothing here ran with the game rendering on the same machine (owner test C2 / C3), where CPU contention is what
MMCSS and the Highest priority are for.

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
