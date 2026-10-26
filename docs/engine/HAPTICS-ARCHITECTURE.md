# Haptics architecture: one framework for wheel FFB, pad rumble, bass transducers and motion

*Design and research pass, 2026-10-10. Read-only: nothing was run, no game folder or existing code was touched.
This is the plan an implementation agent works from; it is not a record of anything built.*

**Owner's request, condensed.** Organise the force-feedback work so that (a) any game event or any sound the
engine plays can be an *input*, (b) a middle layer holds the mapping, mixing and a *design facility* that can show
the stock FFB behaviour for an event, the spectrum of the sound the game plays for it, and a live preview, and
(c) *outputs* are the DirectInput wheel, XInput pad motors, bass transducers over an audio device (the "audio
interposer harness" paused earlier), and later a UDP motion feed.

Evidence legend, used on every claim that matters: **[live]** measured in a running game and cited; **[static]** a
cited instruction or source line; **[built-untested]** code exists, never run live; **[proposed]** this document.
Where a fact is not known it says **unknown**.

---

## 0. Short version

Almost every piece exists. What does not exist is the *organisation*: three stacks (PowerShell wheel+shaker,
Mac in-process pad shim, dsound-proxy rumble) each with its own idea of an event, two telemetry wires in two
encodings, a mixer whose tune table is the only "design" artefact, and no tool that looks at a stock sound and
says what to shift into haptics.

The design therefore:

1. **Keeps one inbound wire**: the proxy's `I76_TELEMETRY` frame + event ring (`tools/telemetry/i76tel.h`,
   verified live 2026-10-01). It gains sound-start/stop events (the P4 tap from SOUND-INTERPOSER-REVIEW) and a
   damage-side event, as **i76tel v3**. Nothing else reads game memory from outside.
2. **Puts the whole middle layer in one external host process** (`tools/haptics/`), split into pure-function
   `Core` (events + frame -> device-independent force bus), `Renderers` (wheel / pad / lfe / udp), `Transport`
   (shm + UDP), and an offline Python `Design` toolset. The existing `FfbMixer.ps1` bus (`Steady / Tactile /
   Transient / Motion / Lfe`) is the bus; the existing `FfbCore.ps1`, `LfeSynth.ps1`, `Mix-RenderPad` are the
   first renderers.
3. **Makes effects data, not code**: `effects/*.json` (one per effect, ShakeIt-shaped response chain +
   AHAP-shaped envelope, per-output routing), `rigs/*.json` (device curves), `stock/stock-ffb-reference.json`
   (what `i7_sfrce.dll` did per event, from FFB-DEEP-DIVE), `analysis/<sound>.json` (per-WAV spectral analysis).
4. **Transducers**: the synthesiser we already stream from `LfeSynth.ps1` to the Audient EVO 4 is the primary
   transducer path (telemetry-driven, per the design library's "synthesise, don't tap"). The *game-audio* tap the
   owner wants in addition is a **WASAPI shared-mode loopback capture inside the host**, band-limited and mixed
   under the synth, not a `dsound.dll` proxy and not a virtual cable (section 5).
5. **Everything buildable without the game**: recorded telemetry replays, a scripted-telemetry probe that already
   exists (`ffb-lfe-probe.ps1`), unit tests in the `ffb-mixer-test.ps1` style, offline spectra from `I76.ZFS`.
   Console time is reserved for the eight tests in section 7.3.

---

## 1. Inventory: what exists, where, in what state

### 1.1 Capture (game -> data)

| piece | path | what it does | status |
|---|---|---|---|
| Telemetry export | `music-fix/strlkproxy.c` "TELEMETRY EXPORT" (~line 4101), `tools/telemetry/i76tel.h`, `i76tel.py` | `I76_TELEMETRY=1`: once per rendered frame, 628-byte `i76tel_frame_t` (pose, velocity, body rates, accel, steer/throttle, gear, rpm, flags incl. airborne/skid/grip-limit/oil/nitrous, surface, ground normal, armour/chassis x4, 6 wheels with grip/susp/flat/skid, weapon, the exe's FFB block copies) + 36-byte events `SHOT` (0x4a6e90), `EXPLOSION` (0x49ead0, world pos + distance), `IMPACT` (0x4a7c80, impact vector + hp lost). UDP 127.0.0.1:7676 and shm `Local\I76Telemetry` (seqlock) | **[live]** 1,067/1,067 frames, SHOT/IMPACT/EXPLOSION seen (`tools/telemetry/verification-2026-10-01.txt`). Zero cost when unset. Sandbox only so far |
| Memory scanner | `tools/ffb/Telemetry.ps1` (49 KB) | `ReadProcessMemory` on the entity chain `[[[0x54a264]]+0x70]` + the FFB block 0x4f2328; derives slip, jolt, understeer; `Tel-DetectShift` rpm-rate heuristic; writes `0x52bbe4 = 0` to stop the stock DLL faulting | **[live]** working, but FFB-DATA-AUDIT shows three of its beliefs wrong (hull corners != wheel contacts; orientation exists at `obj+0x18`; `+0xc8/+0xd0` are pitch/roll rates) and it does not yet read the shm (audit row 8, "Telemetry.ps1 gains a shared-memory source" is still open). Superseded as a *reader*; keep as a *finder* |
| Mac FFB shim | `ffb-shim/i7ffshim.c` (701 lines), `i7_sfrce.def`, `build.sh`, `install.sh` | Replaces `i7_sfrce.dll`; receives the 0x16c block every tick; drives XInput; UDP key=value to 127.0.0.1:17676; `C:\AutoHotkey\ffb-state.txt` | **[live]** on the Mac 2026-07-19/20, tuned by ear. Never loaded on Windows. Three fields mislabelled (`+0xfc/+0x100` are throttle sign, `+0x18` gear-changed, `+0x1c` nitrous; audit 2.3). Its data is now a subset of `i76tel_frame_t.ffb_*` |
| dsound proxy rumble | `sound-rumble/dsndrumble.c` (441 lines), `dsound.def`, `tools/gpw-fingerprints.py`, `tools/gpw-envelopes.py` | Wraps `IDirectSoundBuffer`; FNV-1a of PCM on `Unlock` -> `.gpw` name; plays RMS envelope on a pad motor | **[built-untested]** never run in-game; Windows loadability unknown; SOUND-INTERPOSER-REVIEW P9 says retire it (no player/other distinction, engine loops become a floor, pitch changes desync envelopes). **This is the "audio interposer harness paused before"**; no other audio-tap harness was found in the three repos |
| Lab dsound stub | `../<lab>/src/dsstub.c` | `DirectSoundCreate` returns `DSERR_NODRIVER` so an automated instance is silent | works (test copies only). Not an interposer; proves the app-dir `dsound.dll` *does* load ahead of System32 in the sandbox, which is the one fact dsndrumble lacked |
| Sound call-site gates | `strlkproxy.c` `frame_sound_wrap` (~line 1493), `I76_FRAMERATE_FIXES` | Wraps six `call 0x423230` sites (lock tones, tyre/surface/flat/damage) and the radar ping | **[live]** for radar ping and lock tones. The pattern (byte-verified `patch_bytes`, cdecl wrapper) is what the sound-event tap reuses |
| Joystick routing | `strlkproxy.c` `apply_joy_routing` (~line 6060) `I76_JOY_MAP` | winmm `joyGetPosEx` remap | **[static]** read 2026-10-05; unrelated to FFB output but shows the exe's input is winmm only; FFB output is DirectInput only inside `i7_sfrce.dll` (FFB-DEEP-DIVE 1) |
| Diagnostics | `tools/check-ffb.ps1`, `tools/ffb-recon.ps1`, `tools/ffb/ffb-watch-effects.ps1`, `ffb-find-*.ps1`, `ffb-telemetry-probe.ps1` | Live state of the exe's FFB (`0x52bbd0/0x52bbcc/0x52bbe4`), machine-side enumeration diff, effect-slot watcher, offset finders | working; names corrected 2026-10-02 (backlog P3-18) |

### 1.2 Middle layer (data -> forces)

| piece | path | what it does | status |
|---|---|---|---|
| Force model | `tools/ffb/FfbMixer.ps1` (63 KB) | `Mix-DefaultTune` (~130 tunables), `Mix-Update` -> wheel force + **device-independent bus** `{Steady, Tactile[], Transient, Motion{SurgeA,SwayA,HeaveA,YawRate,Pitch}, Lfe{engine, road, impulse, heave, scrub, weapon, explode}}`; `Mix-RenderWheel`, `Mix-RenderPad`; 8 wheel channels | working, 28 assertions (`ffb-mixer-test.ps1`). **Uncommitted diff** (32+/10-): explosion carrier 22->25 Hz, amp 0.44->0.58, new `LfeExplodeDuck=0.75`, and a real bug fix (blast envelope decay and `$duck` were inside the firing-edge branch, so beds were silently zeroed). Backlog P3-01. Feel tuning "not started" |
| Pad mixer (AHK) | `windows/i76-remap.ahk` lines ~586-660 | Per-event `RumblePulse(l, r, ticks)`, last-event-wins, `SetState` on change; gated off by `gShimOwnsRumble := true` | **[live]** 2026-07-18 field-proven path, but *off on Windows* because the gate ships Mac-correct (FFB-STACKS fight 2) |
| Shim rumble model | `ffb-shim/i7ffshim.c` RUMBLE TUNING block | slip-led two-motor mix with `.gpw` skid envelope as texture; the real DLL's impact magnitude formulas | **[live]** Mac only |
| Stock effect parser | `tools/ffb/parse-frc.py` | Reads the 14 RIFF `FORC` files: compositions known (`Sine+Constant+Superimpose` etc.), **parameter block not decoded** | working for type names; numbers unknown |
| Stock DLL behaviour | `docs/records/FFB-DEEP-DIVE.md` 3 | Per-event formulas from `i7_sfrce.dll` disassembly: ordnance `(40+0.6667*dmg)*100`, concussion `(35+0.6667*dmg)*100`, collision `(55+0.5625*dmg)*100`, decay by dt, stop at -1500; engine gain `0x14 - speed/2`, freq `8 - k*pitch`; flat-tyre threshold 3000; terrain table by surface id | **[static]**, the raw material for `stock-ffb-reference.json` |
| Design knowledge | `docs/engine/FFB-DESIGN-LIBRARY.md`, `docs/records/SIM-RUMBLE-RESEARCH.md` | Bands, JNDs, shaker Fs rule, ShakeIt response chain, two-motor allocation, the "floors low / transients loud" doctrine | written; the design facility encodes them as defaults and lints |
| Calibration | `tools/ffb/ffb-calibrate.ps1`, `ffb-calib.json`, `ffb-calib-test.ps1` | yaw sign + steering lock by regression | working (11 assertions); lock is superseded by live `ent+0x118` / `7.84 x sum(grip)` once read from telemetry |
| Rig response | `tools/ffb/ffb-lfe-sweep.ps1` -> `LfeRespHz/LfeRespRel` in the tune | by-body rating of felt intensity per frequency (13 Hz perceptible, peak ~35 Hz on this desk) | measured once (n = 1 rater, one rig) |

### 1.3 Outputs

| piece | path | what it does | status |
|---|---|---|---|
| Wheel | `tools/ffb/FfbCore.ps1` | Hand-walked DirectInput8 COM vtables (Add-Type C#), one infinite constant force rewritten each loop with `DIEP_TYPESPECIFICPARAMS` only, autocentre off, `Ffb-Reacquire` | **[live]** T300RS; periodic effects fail (`REGDB_E_CLASSNOTREG`); loop <= 62 Hz from `Start-Sleep` |
| Wheel coexistence | `tools/ffb/ffb-coexist-test.ps1`, `Tel-SetEngineFfb` | our exclusive acquire survives with the game focused; stock engine effects are lost and the DLL would fault at `+0x2505`, so `0x52bbe4` is zeroed and restored on exit | **[live]**; whether the game can *also* play effects while we hold the device: unknown |
| Shaker synth | `tools/ffb/LfeSynth.ps1` (`LfeCore`, `LfeLive`, `LfeOut`), `ffb-lfe-live.ps1`, `ffb-lfe.ps1`, `ffb-lfe-demo.ps1` (untracked), `ffb-lfe-probe.ps1`, `ffb-lfe-trace.ps1` | Parametric DSP (sines + noise bed, per-source rig compensation, HP 22 / LP 90, soft limiter) on a C# audio thread, waveOut to a *chosen* device index (Audient EVO 4), 16 kHz, 4 x 256-sample buffers (~64 ms queue) | **[live]** streams; `probe/*.wav` and `trace/*.wav` are its offline evidence. `ffb-lfe-demo.ps1` plays each source solo at shipped amplitude: the embryo of "live preview" |
| Pad | `Mix-RenderPad` (bus -> L/R 0..1), AHK `XInputSetState`, shim XInput | | no Windows runtime currently drives a pad from the bus (AHK gate off, shim not on Windows) |
| Motion / 3rd-party | `tools/ffb/ffb-telemetry-udp.ps1` (OutSim/OutGauge 4123/4124, 21 layout assertions), `ffb-shim` UDP 17676 key=value, `tools/ffb-udp-listen.py` | SimTools / SimHub / FlyPT consumers | working; OutSim pitch/roll/position/rpm/gear **hard-coded to zero** though all are now in the frame struct (audit row 4) |
| Visualisation | `tools/ffb/ffb-graph.ps1` + `ffb-graph.template.html`, `ffb-replay.ps1`, `ffb-interposer.ps1` panel | HTML drive report; distributions; live panel with solo/mute | working |

### 1.4 What was abandoned, and why (so it is not rebuilt)

- **dsound-proxy rumble** (`sound-rumble/`): fingerprinting PCM infers what the voice record already holds one
  `jmp` away (name, object, is_player, Hz, vol, mode, prio); no distance; loops floor the motor; breaks on any
  replaced sound. Retire per SOUND-INTERPOSER-REVIEW P9. The *idea* (sounds as inputs) survives as the P4 tap.
- **winmm proxy** (`tools/winmm-cdaudio/`): cannot load into i76.exe (AppCompat preloads System32 winmm). Irrelevant
  to haptics except as the warning that app-local DLL replacement is not guaranteed on this exe.
- **Memory-scanning telemetry as the runtime source**: replaced by the proxy export; the audit lists the rest.
- **Periodic DirectInput effects on the T300**: refused by the device; everything rides one constant force.
- **rpm-rate shift detector**: `eng+8` is the gear; the heuristic false-fires on airborne lift-off (audit 2.1).
- **Keying "explosion" on a weapon gain >= 40**: that is a heavy shot, not a blast; use `EXPLOSION` events.
- **Low-passing the game mix as the only shaker source**: sparse, music-contaminated (ffb-lfe.ps1 header).
  It returns here only as an *additive ambience layer* under the synth, with its own gain and a duck.

---

## 2. Architecture

```
 GAME PROCESS (i76.exe + Strlkup.dll proxy)                 HOST PROCESS  tools/haptics/  (one exe/script, 250 Hz loop)
 ┌───────────────────────────────────────────┐              ┌───────────────────────────────────────────────────────────┐
 │ frame hook @0x4039b8 ─► tel_frame()       │  shm         │ Transport.ShmReader ──► Core.FrameState (latest frame)     │
 │   628 B i76tel_frame_t  (v3: +2 fields)   ├─seqlock──►   │ Transport.EventRing ──► Core.EventBus  (typed events)      │
 │ SHOT      @0x4a6e90 call sites            │  + UDP 7676  │        │                                                   │
 │ EXPLOSION @0x49ead0 detour                │              │        ▼  Core.Derive   (edges: gear, landing, surface,    │
 │ IMPACT    @0x4a7c80 detour                │              │           flat, grip-limit, engine start; distance, side)  │
 │ SOUND_START @0x4220c0 detour  (v3, P4)    │              │        ▼  Core.EffectEngine                                │
 │ SOUND_STOP  @0x422d20 detour  (v3, P4)    │              │           effects/*.json  ──► per effect: input→response   │
 │ DAMAGE_SIDE @0x463a80 detour  (v3)        │              │           (gain,threshold,minforce,gamma) → envelope       │
 │                                           │              │           (attack/hold/decay) → carrier → routing          │
 │ zero cost when I76_TELEMETRY unset        │              │        ▼  Core.Bus  {Steady, Tactile[], Transient[],       │
 └───────────────────────────────────────────┘              │                      Motion, Lfe[], Pad{L,R}}             │
                                                            │        ▼  Mixer: per-group priority, MAX-per-motor,        │
      WASAPI loopback of the game's render endpoint ───────►│           headroom budget, duck, limiter                   │
      (optional ambience layer, section 5)                  │   Renderers:                                               │
                                                            │   ├ Wheel.DirectInput   (FfbCore)        ─► T300RS         │
                                                            │   ├ Pad.XInput          (new, from Mix-RenderPad) ─► pads   │
                                                            │   ├ Lfe.Synth+Loopback  (LfeCore)        ─► EVO 4 ─► shakers│
                                                            │   └ Udp.OutSim/OutGauge + i76tel passthrough ─► motion sw  │
                                                            │   Design (offline, Python): gpw_spectra, stock_reference,  │
                                                            │           replay, report, preview                          │
                                                            └───────────────────────────────────────────────────────────┘
```

### 2.1 Inputs

Two kinds, deliberately kept distinct in the schema: **continuous channels** (one value per frame, read from
`i76tel_frame_t`) and **events** (discrete, from the ring). The engine's own clock is the time base
(`sim_time`, `proxy_frame`), never the host's wall clock, so a replay is bit-identical to a live run.

**Continuous channels available today** (all `i76tel_frame_t` fields, verified live 2026-10-01 unless noted):
`speed`, `velocity[3]`, `accel[3]` (world) and `accel_body[3]` (only while `ffb_present`; otherwise rotate `accel`
by `rot`), `pitch_rate/yaw_rate/roll_rate` (rest/contact square wave, transients only), `steer`, `throttle`
(negative = brake), `gear`, `gear_lever`, `rpm` (850..7000), `drive_power`, `flags` (engine running 0x1, skid 0x2,
airborne 0x4, starting 0x8, destroyed 0x20, oil 0x400, nitrous 0x800, grip limit 0x2000, critical 0x4000, wreck
0x8000), `surface` (WRLD index; bump amplitude is WRLD row +0x08, audit 5.3), `ground_normal`, `clearance`,
`armour[4]/chassis[4]` + maxes, `wheel[6].{grip, ground_speed, susp_offset, unloaded, flat, skid_active}`,
`weapon_*`, `ffb_rpm/engine_running/starting/gear_changed/nitrous`, `mass`, `health_pct`.

**Events available today:** `SHOT` (hud row, ammo left, damage/hit, rounds; weapdef), `EXPLOSION` (x,y,z,
distance; 8-char template), `IMPACT` (impact vector; player hp lost; is-player, source class).

**Events to add (i76tel v3, all [proposed]; byte patterns from SOUND-INTERPOSER-REVIEW P4 and FFB-DATA-AUDIT 4.1):**

| type | hook | payload | why |
|---|---|---|---|
| 4 `SOUND_START` | `sound_StartVoice` 0x4220c0, 6-byte prologue `a1 e8 d7 4e 00 53`, cdecl `(voice, k)` | name (voice+4, 8 bytes), hz (+0x18), vol% (+0x1c), mode (+0x3c), prio (+0x34), is_player (`obj == *0x457530()` or `0x458c90(obj)+0x10 & 0x10`), pos (`0x458d60(obj)` 3 floats), obj | one event per *audible* start, regardless of which of the 22+23+9+14+35+4 request sites asked; carries what dsndrumble could never infer |
| 5 `SOUND_STOP` | `sound_StopVoice` 0x422d20, 5-byte prologue `56 8b 74 24 08` | voice name, obj, reason | loop ends (skid, engine) |
| 6 `DAMAGE_SIDE` | `entity_DamageAndKill` 0x463a80 (entity, record) | side 0..3, zone 0..6, amount, is_player | directional kick without guessing from yaw (audit 2.4) |
| 7 `WEAPON_UI` | block one-shots 0x4f234c/50/54 (read in `tel_frame`, edge-detect in the proxy) | cycle / link / unlink | the stock WPNCYCLE/WPNLINK/WPNUNLNK clicks |

Host-side derived events (no hook needed): `GEAR` (edge of `gear`), `LANDING` (falling edge of `flags & 4`,
with `velocity[1]` from the previous frame), `TAKEOFF`, `SURFACE` (edge of `surface`), `FLAT` (rising edge of
`wheel[i].flat`), `GRIP_LIMIT`/`SKID`/`OIL` (edges), `ENGINE_START` (`flags & 8`), `NITROUS`, `DESTROYED`.

**Sound plays as inputs: what they are good for.** The engine note is already exact from `rpm`, and the design
library's doctrine is events-over-sounds for the things telemetry knows. Sounds are the *right* input for things
that are only sounds: horn, CB, weapon timbre per `.gdf` name (the SHOT event has the weapdef index; the sound
name gives the authored character), AI weapon fire nearby (SOUND_START with `is_player = 0` and a position),
ambient (wind at speed? unknown whether such a loop exists), UI. They are also the *reference* the design facility
uses: for every event the game plays a sound, and that sound's low band is what the 1997 designers meant you to
feel.

### 2.2 Middle layer

**Event bus.** In-host, in-process: a ring of typed `HapticEvent {t_sim, frame, type, fields}` plus the latest
`FrameState`. Not a network bus; the inbound wire is the shm, the outbound wires are the renderers' own. Replays
inject into the same bus.

**Effect engine.** One `Effect` per JSON file (section 4.2). Processing chain per effect, cloned from ShakeIt's
(SIM-RUMBLE-RESEARCH Part A) because it is the one every practitioner already knows how to tune:

```
source (channel expr or event filter)
  -> input gain -> threshold (dead-band) -> min-force floor -> gamma      [response]
  -> envelope (attack / hold / decay; for events: retrigger policy)       [time]
  -> carrier (base_hz .. high_hz by level; or 'none' for kinesthetic)     [where in frequency]
  -> routing: per output {amp, hz override, motor L/R, wheel sign/axis}   [to devices]
  -> group + priority + duck                                              [mixing]
```

**Mixer rules** (all from existing docs, now made explicit per output):
- Wheel: additive into one constant force; **continuous channels budgeted to ~40-70 % of range**, transients may
  reach the ceiling; clamp 9500/10000; small-force floor (`MinForce`); loss of grip *attenuates* (`gripScale`).
- Pad: **MAX per motor, not sum**; dead-zone lift to 0.30; one `XInputSetState` per frame; longest one-shot wins;
  ERM spin-up ~20-30 ms so no pulse under ~40 ms (SIM-RUMBLE-RESEARCH Part E).
- Shaker: <= 3 continuous sources, spaced in frequency; per-source rig compensation at its own frequency
  (`LfeCore.Comp`); blast ducks beds (the uncommitted `LfeExplodeDuck`); HP 22 / LP 90; soft limiter is the
  last stage and no single source may reach it alone (ffb-lfe-live header).
- Motion: no mixing; raw SI body-frame accel and rates, declared units, never pre-filtered.

**The design facility** (`tools/haptics/design/`, offline Python + a static HTML report, section 4.3). For a
chosen event it shows side by side:
1. **Stock FFB reference**: what `i7_sfrce.dll` did (effect family, magnitude formula, decay; the `.frc`
   composition from `parse-frc.py`), from `stock/stock-ffb-reference.json`.
2. **Sound spectrum**: the stock `.gpw`/`.wav` the engine plays for it (from `I76.ZFS` via `tools/zfs_extract.py`,
   as `gpw-envelopes.py` already does): RMS envelope at 10 ms, band energies (<20, 20-40, 40-80, 80-160, 160-400,
   >400 Hz), onset time, duration, spectral centroid over time, plus a **suggested haptic** (shaker carrier near
   the dominant in-band energy or the rig peak; envelope from the RMS curve; pad motor by centroid; wheel transient
   magnitude by onset energy), each flagged "suggested" and never auto-applied.
3. **Current effect file** for that event, and the delta between suggestion and current.
4. **Preview**: renders the effect alone through the real DSP to the chosen audio device and/or wheel and/or pad
   (`ffb-lfe-demo.ps1` already does the shaker half for the mixer's sources; it becomes `preview.ps1 -Effect <id>`).
5. **Lints**: continuous-source count per shaker > 3; two continuous effects within 8 Hz; wheel continuous budget
   > 70 %; pad amplitude under dead-zone; any envelope < 40 ms on a pad; any shaker carrier < 22 or > 90 Hz;
   total shaker headroom > 0.95 at the loudest documented combination.

### 2.3 Outputs

| output | renderer | notes and the one open question each |
|---|---|---|
| DirectInput wheel | `Renderers/Wheel.DirectInput` = `FfbCore.ps1` as is | Three coexistence modes (section 3.3). Open: can the game's DLL play its effects while we hold the device (`ffb-coexist-test` only proved *our* acquire survives) |
| XInput pad L/R | `Renderers/Pad.XInput` (new, ~80 lines P/Invoke `XInputSetState`, port of `Mix-RenderPad` + AHK pulse policy) | Owner's pads: which XInput slot, and whether they expose impulse triggers (`XINPUT_VIBRATION_EX` is GameInput/Xbox-only per devdocs) is unknown; design for L/R only |
| Bass transducers | `Renderers/Lfe.Synth` = `LfeCore`/`LfeLive`, plus `Lfe.Loopback` (section 5) | Device: Audient EVO 4 index chosen at start (`-ListDevices`). Open: a second shaker channel (stereo L/R = front/rear?) is unmeasured; the sweep was one channel |
| Motion UDP | `Renderers/Udp.OutSim` = `ffb-telemetry-udp.ps1` with pitch/roll/pos/rpm/gear filled from `rot/pos/rpm/gear` (audit row 4) | D-BOX / Sigma are closed ecosystems (memory note): a custom plugin would need their SDK; OutSim/OutGauge reaches SimTools/FlyPT/SimHub today. Unknown: which rig, so emit SI and declare it |
| Raw passthrough | `i76tel` UDP 7676 as is | for anyone writing their own consumer |

---

## 3. Process and runtime model

### 3.1 What runs where, and why

**Inside the proxy (`Strlkup.dll`): capture only.** Detours and the per-frame snapshot, because that is the only
place a voice start or a damage call can be seen with its arguments, and the proxy already owns the byte-verified
patch machinery. No mixing, no device I/O, no audio in the game process: a fault there is a game crash, and a
250 Hz loop or a WASAPI client has no business on the sim thread. Gate: `I76_TELEMETRY` (existing) and a new
`I76_SOUND_EVENTS=1` for the two sound detours (P4's own switch), both off by default so the deployed binary is
unchanged in behaviour when unset.

**Outside (host): everything else.** One process reading the shm at its own rate. Reasons: the shm is a seqlock
copy with no `OpenProcess`; the host can crash, restart, and change effect files while the game runs; it can run
against a recording with the game closed; and it is where the wheel's exclusive acquisition, the audio device and
the pad all live anyway.

**Language.** Today the runtime is PowerShell dot-sourcing C# via `Add-Type` (`FfbCore`, `LfeCore`, `LfeLive`),
and the loop is PowerShell (62 Hz ceiling). The offline tools are Python (`i76tel.py`, `parse-frc.py`,
`gpw-*.py`). Decision for this plan:
- **Design tools: Python 3** (stdlib + `numpy` for FFT; whether `numpy` is installed on this machine is unknown,
  `python -c "import numpy"` settles it; `zfs_extract.py` is pure stdlib).
- **Runtime Core + Renderers: C# source files** under `tools/haptics/src/*.cs`, compiled by `Add-Type -Path` from
  a thin PowerShell launcher in phase A (no new toolchain question; same as today), and by a `.csproj` in phase B
  if `dotnet --list-sdks` shows an SDK (unknown). Moving the loop into C# removes the 62 Hz `Start-Sleep` ceiling
  (`Thread.Sleep` + `timeBeginPeriod(1)` or a multimedia timer gives ~1 ms), which is the single change that lets
  oscillators above 15 Hz and sub-10 ms transient onsets exist.
- The existing `FfbMixer.ps1` remains the **reference model**: the C# Core must reproduce its bus for the 28
  existing test drives before any effect-file behaviour is added (phase A2 exit criterion).

### 3.2 Latency budget (event -> skin)

| stage | wheel | pad | shaker | source |
|---|---|---|---|---|
| physics step (event can happen anywhere in it) | 0-42 ms (fixed step 24 Hz) / 0-50 stock | same | same | `simclock.md` via FFB-DATA-AUDIT 5 |
| publish: top of next frame | 1 frame (16.7 ms at 60 fps, 50 at 20) | same | same | `tools/telemetry/README.md` "one frame of latency by construction" |
| host poll at 250 Hz | <= 4 ms | <= 4 ms | <= 4 ms | [proposed] |
| device | USB FFB report ~1-4 ms; wheel motor rise unknown | XInput ~8 ms poll + ERM spin-up 20-30 ms | synth buffer 16 ms x 1-2 in flight + waveOut/WASAPI shared ~10 ms + amp | design library 2; SIM-RUMBLE-RESEARCH; ffb-lfe-live header |
| **typical total after the frame is drawn** | **~25-45 ms** | **~50-70 ms** | **~45-75 ms** | |

SimHub's own stated budget is 16 ms acquisition + 10-20 ms FMOD, i.e. ~36 ms before the sound card
([SimHub forum, admin reply](https://www.simhubdash.com/community-2/simhub-support/bodyshakers-lag/)), so the
shaker figure above is in the same class. The game-audio loopback layer (section 5) adds its own ~10-30 ms and
is for beds, not transients. No source in our library gives the audio-haptic asynchrony tolerance for this kind
of cue; it is measured in phase C (console test 6) rather than assumed.

### 3.3 Wheel ownership: three modes, pick per session

| mode | who holds the wheel | stock effects | our wheel feel | state |
|---|---|---|---|---|
| **A. Host owns** | host `FfbCore` | lost; `0x52bbe4` zeroed so the DLL never faults, restored on exit | yes | **[live]** today's `ffb-interposer.ps1` |
| **B. Stock owns** | `i7_sfrce.dll` | authentic | none; host drives pad + shakers + motion only | **[live]** (plain game + host without `-Wheel`) |
| **C. Shim owns** | our `i7_sfrce.dll` replacement forwards the block to the host (or the host reads `ffb_*`), host renders stock-reference effects *and* ours | re-created from `stock-ffb-reference.json` | yes | **[built-untested]** on Windows; FFB-STACKS says do not zero `0x52bbe4` in this mode |

Recommendation: A for development, C as the target because it is the only mode with one owner and both feels.
Mode C is also the only one where the "reference stock FFB" in the design facility is load-bearing rather than
documentary. The `.frc` parameter block stays undecoded; the DLL's formulas (FFB-DEEP-DIVE 3) are enough for the
impact, engine and terrain families, and the weapon families use the per-hardpoint `+0x14` gain [static].

### 3.4 Never touching the daily driver until gated

- Host default game dir resolution copies `windows/LAUNCHER.ps1`'s order (`-GameDir`, `I76_GAME_DIR`, lab sandbox,
  else stop) and **refuses** a path under `~\Downloads\Interstate76-i76-everywhere-portable-*`.
- The proxy's new events are behind `I76_SOUND_EVENTS`; the daily driver runs with every `I76_*` unset
  (AGENTS.md promotion rule), so a promoted `Strlkup.dll` carrying the code is inert there.
- No new file goes into any game folder: the host is outside, the shm is created by whichever side maps first,
  the loopback is a capture of an endpoint. Mode C is the one exception (a DLL swap) and is lab-only until the
  owner-console tests pass.
- The host writes nothing into the game process. Mode A's `0x52bbe4` write is the one existing exception, kept,
  logged, read back (`verify-the-write-landed`).
- `tools/mute.ps1` in the lab mutes the default endpoint while agents test; the shaker endpoint is a *different*
  device, so a test that drives shakers must also be gated by `-Device -1` (none) unless the owner is present.

---

## 4. Data formats

### 4.1 Event schema (i76tel v3)

Bump `I76TEL_VERSION` to 3; readers already check `version`. Widen the event to carry a name and a position:

```c
typedef struct i76tel_event_t {   /* 48 bytes in v3 (was 36) */
    uint32_t seq, frame, type;
    float    f[5];                /* per type */
    int32_t  i[4];                /* per type; i[0..1] = 8-char name where there is one */
} i76tel_event_t;
/* 4 SOUND_START : f = {hz, vol_pct, pos.x, pos.y, pos.z}; i = {name lo, name hi, (mode | prio<<8 | is_player<<16), obj}
   5 SOUND_STOP  : f = {0,0,0,0,0};                        i = {name lo, name hi, reason, obj}
   6 DAMAGE_SIDE : f = {amount, 0,0,0,0};                  i = {side 0..3, zone 0..6, is_player, source class}
   7 WEAPON_UI   : f = {};                                 i = {0 cycle / 1 link / 2 unlink} */
```

Frame struct v3 additions: `wheelbase` (`ent+0x118`), `grip_cap` (`7.84 x sum(wheel grip)`), both from
FFB-DATA-AUDIT 2.3. The ring stays 64 entries; the UDP datagram max becomes 636 + 64 x 48 = 3708 bytes (one
datagram, under the 1472-byte Ethernet payload only with <= 17 events; loopback does not fragment, so this is a
note, not a problem). `i76tel.py` parses the header, so the Python side follows automatically.

Host-side canonical event (what effects match on), JSON for logs/replays:

```json
{"t": 123.456, "frame": 2468, "type": "SOUND_START", "name": "vmgun", "hz": 11025, "vol": 100,
 "is_player": 1, "dist": 0.0, "mode": 0, "prio": 70}
```

### 4.2 Effect definition files (`tools/haptics/effects/*.json`)

One file per effect; schema in `tools/haptics/schema/effect.schema.json`. Shape borrows ShakeIt's response chain
(SIM-RUMBLE-RESEARCH) and Apple AHAP's split of *transient* vs *continuous* events with parameter curves (AHAP is
Apple's JSON pattern format for Core Haptics; the shape is what is borrowed, not the vocabulary).

```json
{
  "id": "impact.collision",
  "kind": "transient",                       // transient | continuous
  "source": {"event": "IMPACT", "where": {"is_player": 1, "source_class": [0, 1]},
             "level": "clamp(hp_lost / 60, 0, 1)"},     // or for continuous: {"channel": "speed", ...}
  "response": {"input_gain": 1.0, "threshold": 0.05, "min_force": 0.15, "gamma": 1.0},
  "envelope":  {"attack_ms": 0, "hold_ms": 40, "decay_ms": 220, "retrigger": "restart|max|ignore"},
  "carrier":   {"base_hz": 30, "high_hz": 30},      // shaker / pad hint; wheel ignores
  "routing": {
    "wheel":  {"amp": 0.9, "shape": "impulse", "direction": "from_impact_vector"},
    "pad":    {"L": 1.0, "R": 0.5},
    "lfe":    {"amp": 0.62, "hz": 30},
    "motion": null
  },
  "mix": {"group": "impact", "priority": 90, "duck": {"groups": ["engine", "road"], "depth": 0.5}},
  "reference": {"stock": "stock-ffb-reference.json#impact.collision",
                "sounds": ["vvch2", "vvcre2", "vvcbb3"], "analysis": "analysis/vvch2.json"},
  "notes": "stock: (55 + 0.5625*dmg)*100 DI units, decays by dt to -1500"
}
```

`rigs/<name>.json` carries device facts: shaker `{device_name_match, resp_hz[], resp_rel[], comp_max, hp_hz,
lp_hz, channels}`, pad `{deadzone: 0.30}`, wheel `{clamp: 9500, min_force: 900, slew_max}`. The current
`Mix-DefaultTune` + `ffb-tune.json` are migrated by a one-off script (`design/migrate_tune.py`) so no number is
retyped by hand (`diff-the-table-after-a-bulk-merge`: diff per key after the migration).

### 4.3 Design-facility outputs

- `stock/stock-ffb-reference.json`: per event id -> `{family, formula, duration, decay, frc_file, frc_composition,
  evidence}`; generated by `design/stock_reference.py` from a hand-entered table citing FFB-DEEP-DIVE 3 and
  `parse-frc.py` output. Example rows: `impact.ordnance` `(40+0.6667*dmg)*100`; `engine.vibration` gain
  `0x14 - min(speed/2, 0x14)`, freq `8 - k*pitch`; `tyre.flat` threshold 3000, `TIREBLWL/R = Sine + Constant +
  Superimpose`; `weapon.cannon` `CANNON1..4 = UserDefined` (hand-drawn, numbers unknown).
- `analysis/<sound>.json` per `.gpw`/`.wav`: `{name, rate, bits, duration_s, rms_10ms[], onset_ms, bands:
  {"0-20": e, "20-40": e, ...}, centroid_hz[], peak_hz_in_band, suggested: {lfe: {hz, env}, pad: {motor, env},
  wheel: {transient_amp}}, caveats}`. Caveat always present: stock effects are **8-bit 11,025 Hz mono**
  (`data/FORMATS.md` 8), so energy under 40 Hz is a design *intent* read through a lossy medium, not a measured
  truth; the engine also re-pitches one-shots randomly 0.80..1.16 and the engine loop continuously
  (SOUND-INTERPOSER-REVIEW 3.2), so carriers are suggestions.
- `analysis/index.html`: one static report (reuse `ffb-graph.template.html` conventions) with the per-event
  three-way view of section 2.2.
- `replays/*.i76tel`: raw UDP datagram captures (`i76tel.py --record`, to add: it already has `--csv`), the
  input to every offline test. Retain them (memory: raw captures outlive methods).

---

## 5. The audio interposer for transducers

What the owner wants: game audio's bass reaching the shakers *as well as* the synthesised channel. Options, with
the facts that decide them:

| option | mechanism | latency | state and risk | verdict |
|---|---|---|---|---|
| 1. `dsound.dll` proxy routing an LFE mix to a chosen device | app-dir DLL wraps `IDirectSoundBuffer`, taps PCM, resamples/filters, opens a second device | low (in-process) | `sound-rumble` exists but is **unverified in-game**; loadability on Windows under the AppCompat/dgVoodoo search-path hardening was unknown until the lab's `dsstub.c` showed an app-dir `dsound.dll` *is* loaded in the sandbox. Still: a file in the game dir, a second audio device opened on the game's thread, 3D buffers unwrapped, and the review's P9 retirement verdict | **no** for routing; the P4 tap gives the *events* without the PCM |
| 2. WASAPI shared-mode **loopback** of the game's render endpoint, in the host, band-limited, summed with the synth, one output stream to the shaker device | `IAudioClient::Initialize(AUDCLNT_STREAMFLAGS_LOOPBACK)` on the default render endpoint; HP 22 / LP 90; mix under `LfeCore` with its own gain and duck | ~10 ms shared-mode period + render buffer; total 20-40 ms | no game-dir file; same clock and process as the synth so the two are time-aligned; a loopback captures the *mix* (music included) so a music-aware duck is needed: the proxy knows when `MCI_PLAY` is active (`g_playingTrack`) and could publish `music_playing` in the frame struct, or the host low-passes and gates on telemetry (engine running / speed) | **recommended** |
| 3. Virtual cable (VB-Cable / VoiceMeeter) | set the game's default device to the cable, route to speakers + shaker bus | VB-Cable buffer 20-48 ms per forum arithmetic, plus output device; ASIO on the output cuts it to single digits | third-party driver, global default-device change affects every app, state lives outside the repo; VoiceMeeter latency "pending on main device latency" ([VB-Audio forum](https://forum.vb-audio.com/viewtopic.php?p=473)) | fallback if option 2 cannot open loopback (unknown edge: exclusive-mode render by dgVoodoo/the game? DirectSound on Win10 is shared-mode, so no) |
| 4. Equalizer APO on the shaker endpoint | system APO, per-channel LP/HP, copy channels | very low; cannot see exclusive-mode streams | still needs the audio *at* that endpoint, i.e. option 3 or a multi-channel device; useful as a protective crossover on the EVO 4 output regardless ([EQ APO](https://equalizerapo.sourceforge.io/)) | optional hardware-side safety net |

**Recommendation: option 2, as a renderer module `Lfe.Loopback` in the host**, under these rules from the design
library: the synthesised channel is primary; loopback is an *ambience bed* with its own gain (default 0.25),
duck-on-transient, and a telemetry gate (silent when `player_present == 0`, i.e. menus and cut-scenes, which is
also where the music is loudest); both pass the same HP/LP and the same limiter. What was *paused* (dsndrumble)
is retired for routing, and its two Python tools keep their second life in the design facility (`gpw-envelopes.py`
is 80 % of `gpw_spectra.py`).

Implementation note for the C# interop: `LfeOut` already does waveOut by device index; loopback needs
`IMMDeviceEnumerator` / `IAudioClient` / `IAudioCaptureClient` COM (the lab's `mute.ps1` already declares
`IMMDeviceEnumerator` and `IMMDevice` in C# via `Add-Type`, so the pattern exists in the repo). Whether a
NuGet-free build can stay `Add-Type`-only is the phase-B question; it can, at ~250 lines.

---

## 6. Research additions (what a deep-research team adds to the library)

Each item: finding, source, and what it changes here. Items already in `FFB-DESIGN-LIBRARY.md` are not repeated
(DirectInput effect model and USB-report trap, wheel 0-5 / 25-30 Hz measurement, shaker Fs rule, ERM constraints,
ShakeIt chain, motion washout).

1. **Audio-to-haptics is an established pipeline, and it is exactly the design facility's method.** Lofelt's
   patent application describes: dynamics processing, envelope extraction, synthesis of low-frequency signals from
   the envelope, enhancement with a resonator, and mixing with the original ([Lofelt / US11468750B2 family,
   Google Patents](https://patents.google.com/patent/US11468750); Immersion's earlier
   [US 8761915](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8761915) and
   [US 9330546](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9330546) cover automatic haptic
   events from an audio file). Meta Haptics Studio auto-generates **amplitude and frequency envelopes plus
   "emphasis" breakpoints** from audio, then expects manual refinement (gain, keyframe reduction, silence)
   ([Meta, Haptics Studio walkthrough](https://developers.meta.com/horizon/documentation/unreal/unreal-haptics-studio-feature-walkthrough/)).
   **Change:** `analysis/<sound>.json` emits amplitude envelope, frequency (centroid) envelope and emphasis
   (onset) points, and the editor workflow is "suggest, then a human trims", never auto-apply. Patents describe
   intent, not shipped code; the shape is what we take.
2. **Effect file shape: AHAP-style transient/continuous + parameter curves.** Apple's Core Haptics pattern
   format separates transient from continuous events with intensity and sharpness and attaches curves over time;
   Meta's `.haptic` is the analogous export (schema not located in this pass: unknown). **Change:** section 4.2's
   `kind`, `envelope`, `carrier` fields; a future importer from either format is cheap.
3. **Vibrotactile threshold peaks near 250 Hz (Pacinian), and below ~65 Hz a different channel mediates.**
   Makous et al. 1995 (Pacinian limb 65-400 Hz, peak ~250); Ye & Griffin 2014: at 8-31.5 Hz the Pacinian channel
   does *not* mediate near-threshold sensation ([review, PMC11814341](https://pmc.ncbi.nlm.nih.gov/articles/PMC11814341);
   [Southampton eprints](https://eprints.soton.ac.uk/354940/1/14713_NGF_MJG_MM_2012_Author_accepted_manuscript.pdf)).
   **Change:** the shaker band (20-90 Hz) and the wheel (<= 30 Hz) are both *non-Pacinian*; the only Pacinian
   actuator we have is the pad's ERM (~150-235 Hz). So fine "texture" belongs on the pad's right motor, weight on
   the shaker, force on the wheel. The lints in 2.2 encode that split.
4. **Whole-body vibration weighting (ISO 2631-1 Wk, vertical seated) is band-passed 0.4-100 Hz and peaks in the
   single-digit Hz region; Wb/Wk differ by < 6 % for seat evaluation** ([Prosig](https://blog.prosig.com/?p=4829);
   [Larson Davis](https://larsondavis.com/learn/industrial-hygiene/human-vibration-weightings); Paddan & Griffin 2002).
   **Change:** this is the standard the sweep's "rate it by body" method approximates; cite it in
   `ffb-lfe-sweep.ps1` and let `rigs/*.json` carry either a measured curve or a Wk-derived default when no sweep
   has been run. The seat-band peak also says heave *should* be amplitude-modulated onto the carrier (the library's
   existing rule), because a shaker cannot deliver 4-8 Hz directly.
5. **Pad trigger motors are console/GameInput only.** `XINPUT_VIBRATION_EX` (two trigger motors) exists in
   XInputOnGameInput for Xbox ([devdocs](https://devdocs.xbox.com/reference/input/xinputongameinput/structs/xinput_vibration_ex));
   desktop `xinput1_4` is L/R only ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/xinput/ns-xinput-xinput_vibration)).
   No measured Hz for Xbox ERMs was found in this pass (unknown; the ~150-235 Hz figure in SIM-RUMBLE-RESEARCH is
   generic ERM data). **Change:** design `Pad.XInput` for two motors; an impulse-trigger path via
   `Windows.Gaming.Input` is a later option, not planned.
6. **Latency reference points.** SimHub: 60 fps acquisition + 10-20 ms FMOD, HDMI audio adds delay
   ([forum](https://www.simhubdash.com/community-2/simhub-support/bodyshakers-lag/)); users asked for WASAPI/ASIO
   ([forum](https://www.simhubdash.com/community-2/simhub/usage-of-low-latency-audio-driver/)). ShakeIt supports
   up to 8 channels per interface, multiple interfaces, and needs the card set to the matching channel mode
   ([community wiki](https://github.com/zegreatclan/SimHub/wiki/Shake-It-for-bass-shakers)). VB-Cable adds a
   buffer users compute at 20-48 ms ([VB-Audio forum](https://forum.vb-audio.com/viewtopic.php?p=2392)).
   **Change:** section 3.2's budget; dedicated USB interface (EVO 4) not HDMI; option 2 over option 3.
7. **Equalizer APO** works only on shared-mode streams and can apply per-channel filters at an endpoint
   ([Equalizer APO](https://equalizerapo.sourceforge.io/); [overtake.gg tactile thread](https://www.overtake.gg/threads/budget-tactile-mono-simhub-profile.188695/)).
   **Change:** optional protective crossover on the shaker endpoint; not part of the signal design.
8. **Vehicle-dynamics inputs the engine really has** (from the <re-archive> specs via FFB-DATA-AUDIT, previously
   believed absent): per-wheel second-order suspension (`susp_offset`, poles 0.7), body pitch/roll rates (zeroed at
   rest by the contact model), a lateral grip cap `7.84 x sum(grip)`, a WRLD surface bump amplitude and 8x8 bump
   pattern applied per substep. **Change:** `road.texture` is `surface_bump_amp x speed` with the texture
   oscillator at its present 11 Hz on the wheel and 55-72 Hz on the shaker; `susp_offset` edges give kerb/bottom-out
   events (SIM-RUMBLE-RESEARCH 10-11) without inventing a suspension.

Not researched here and left unknown: the owner's motion rig vendor SDKs (D-BOX / Sigma, closed), whether the
T300's internal FFB update rate matters at 250 Hz host rate, and any first-party ERM frequency data for the pads.

---

## 7. Phased build plan

Each milestone names its files, its test, and whether it needs the console. Phases A-B need **no game**.
`tools/haptics/` is new; nothing under `tools/ffb/` is deleted until its replacement passes the same tests.

### Phase A: offline foundation (no game, no wheel, no shaker)

| # | milestone | files | exit test |
|---|---|---|---|
| A0 | Hygiene: resolve the uncommitted `FfbMixer.ps1` diff (keep the `$duck` fix, it is a real bug) and track `ffb-lfe-demo.ps1`; fix the four stale labels from FFB-DATA-AUDIT row 11 | `tools/ffb/FfbMixer.ps1`, `tools/ffb/README.md`, `ffb-shim/i7ffshim.c` comments | `ffb-mixer-test.ps1` 28/28 after the merge; `git status` clean for `tools/ffb` (backlog P3-01) |
| A1 | Recorder + replay: `i76tel.py --record out.i76tel` (raw datagrams with host timestamps) and `tools/haptics/replay.py` that feeds a recording or a legacy `drive*.csv` into any consumer at real or max speed | `tools/telemetry/i76tel.py`, `tools/haptics/replay.py`, `tools/haptics/replays/README.md` | a synthetic recording (generated, since no `.i76tel` exists yet) round-trips; `drive2.csv` replays into the existing mixer with identical CSV output to `ffb-replay.ps1` |
| A2 | Core in C#: `Core/FrameState.cs`, `Core/EventBus.cs`, `Core/Derive.cs` (edges of 2.1), `Core/Bus.cs` (the five bus blocks, same field names as `Mix-Update`), `Core/EffectEngine.cs`, `Core/Mixer.cs`; launcher `haptics.ps1` compiles with `Add-Type -Path`; `tests/core-test.ps1` | `tools/haptics/src/Core/*.cs`, `tools/haptics/haptics.ps1`, `tools/haptics/tests/` | reproduces `FfbMixer.ps1`'s bus on the 28 synthetic drives within 1e-6 (port test harness first); then the new assertions: every effect file validates, no NaN under zeroed frames, duck releases, retrigger policies |
| A3 | Effect files + migration: `schema/effect.schema.json`, `schema/rig.schema.json`, `design/migrate_tune.py` (from `Mix-DefaultTune` + `ffb-tune.json`), `effects/*.json` for the current 8 wheel channels + 7 LFE sources + pad set from SIM-RUMBLE-RESEARCH Part B | `tools/haptics/effects/`, `rigs/desk-evo4.json`, `tools/haptics/design/migrate_tune.py` | `migrate_tune.py --diff` shows every tune key landed in exactly one effect/rig file; lints (2.2) pass or list known violations |
| A4 | Design facility, analysis half: `design/gpw_spectra.py` over `I76.ZFS` (reads via `tools/zfs_extract.py`; input is the owner's own archive, output gitignored like `rumble-envelopes.ini`), `design/stock_reference.py` -> `stock/stock-ffb-reference.json`, `design/report.py` -> `analysis/index.html` | `tools/haptics/design/*.py`, `tools/haptics/stock/` | 123 `.gpw` + the `.wav` set analysed; a unit test on a synthetic 30 Hz burst recovers 30 +/- 1 Hz and the envelope; the report opens with the three-way view for `impact.collision`, `weapon.vmgun`, `engine.loop`, `tyre.skid` |
| A5 | Proxy v3 (build only): `SOUND_START/STOP`, `DAMAGE_SIDE`, `WEAPON_UI`, frame fields, `I76_SOUND_EVENTS`; byte patterns asserted against the pristine image (`<re-archive>/tools/disasm.py`) and the existing `patch_bytes` verify-first rule; `i76tel.h` v3; `i76tel.py --check` | `music-fix/strlkproxy.c`, `tools/telemetry/i76tel.h`, `i76tel.py` | compiles with the repo's `build.ps1` to a scratch path (never over the committed DLL); `i76tel.py --layout` regenerates; hook addresses' expected bytes match the pristine exe statically. **Not deployed** |

### Phase B: renderers offline (devices optional, game absent)

| # | milestone | files | exit test |
|---|---|---|---|
| B1 | `Renderers/Lfe.Synth.cs` (lift `LfeCore`/`LfeLive`/`LfeOut` out of `LfeSynth.ps1` unchanged), `Renderers/Lfe.Loopback.cs` (WASAPI loopback -> HP/LP -> bed), `preview.ps1 -Effect <id> [-Device n]` | `tools/haptics/src/Renderers/`, `tools/haptics/preview.ps1` | `ffb-lfe-probe.ps1` scenarios re-rendered through the new path produce WAVs whose spectra match the `probe/*.wav` baseline (RMS per band within 1 dB); loopback unit: a generated 40 Hz tone played to the default device is captured and appears in the shaker stream (desk test, no game) |
| B2 | `Renderers/Pad.XInput.cs` (MAX per motor, dead-zone 0.30, >= 40 ms pulses, one SetState per frame) | | pad connected: `preview.ps1 -Effect gear.shift -Pad` ticks once; a replayed recording with IMPACT events produces the expected L/R log |
| B3 | `Renderers/Wheel.DirectInput.cs` (= `FfbCore.ps1` body), `Renderers/Udp.OutSim.cs` with pitch/roll/pos/rpm/gear filled | | `ffb-telemetry-udp.ps1`'s 21 layout assertions ported and passing; wheel acquire/release on the desk with the game closed |
| B4 | 250 Hz host loop + shm reader + CSV/JSON logging + the live panel (port of the interposer panel, add effect solo/mute by id, hot-reload of `effects/`) | `tools/haptics/haptics.ps1`, `src/Transport/` | runs against a replay at 250 Hz for 10 minutes with no missed deadline > 8 ms (log the histogram) |

### Phase C: owner-console tests (short list; each one a sitting, lab sandbox, A/A before A/B, report n)

1. **Proxy v3 live** (`I76_TELEMETRY=1 I76_SOUND_EVENTS=1 I76MUSIC_LOG=1`): `6/6 event hooks` in `mciproxy.log`; one `SOUND_START` per audible effect, `is_player` 1 for own weapons and 0 for an AI car's; `SOUND_STOP` when a skid loop ends; counts vs the voice list (P4's acceptance).
2. **Shakers + wheel + pad together** for the first time (FFB-STACKS fight 3 / READY-TO-TEST A7): drive t01, log everything, no judgement of feel yet; the question is interference and dropouts.
3. **Latency**: fire one shot and ram one wall; compare the `IMPACT` event's `frame` time against the host's render log time stamp per output; for the shaker, a phone microphone on the shaker recording alongside the host log gives event-to-output within a few ms (crude, but no accelerometer exists here).
4. **Coexistence question** (mode A): with the host holding the wheel, pull the trigger; does the game's DLL still play anything? Answers whether mode C is required for both feels.
5. **Hardpoint `+0x10` freq-vs-direction** (FFB-STACKS pick-up 1): fire the same weapon aimed two ways with `ffb-watch-effects.ps1`.
6. **Explosion reach** (backlog P4-20): an AI car explodes nearby; `EXPLOSION` distance vs any concussion node.
7. **Mode C on Windows**: `ffb-shim` built with mingw, lab copy only, after 1-4; does it load, does the block arrive, does `0x52bbe4` stay untouched.
8. **Feel tuning session** with the design facility open on a second screen: one effect at a time, the two-lap method; each change is an edit to one JSON file, hot-reloaded, logged with the drive.

### Not in scope of this plan

Mac and Deck convergence, motion-rig vendor plugins (SDK access unknown), `.frc` parameter-block decoding (nice,
not needed while the DLL formulas exist), and anything that touches the daily driver.

---

## 8. Open questions (stated so nobody fills them with a guess)

- Whether `numpy` and a .NET SDK are installed on the host box (`python -c "import numpy"`, `dotnet --list-sdks`).
- Whether the game's DirectInput effects play while a second process holds the device exclusively (console test 4).
- Hardpoint record `+0x10`: firing frequency or direction (console test 5).
- Whether `0x4f2340` (gear-changed) is cleared on non-shift frames (audit 7); irrelevant if the host edges `gear`.
- Owner's pad model(s) and XInput slot; whether a second shaker channel exists on the rig.
- Audio-haptic asynchrony tolerance for these cues: not in the library; measured, not assumed (console test 3).
- Which motion rig, if any, and whether its software accepts OutSim or needs a vendor plugin.
- Whether `SOUND_START` should carry the camera distance (host can compute from `pos` and the frame's `pos`;
  the proxy knows the listener `[0x4c2890]`, which the host does not): decide at A5; default is host-side from the
  player position, which is wrong only under far FSM cameras (review 3.3).

---

## Sources

Repo: `docs/engine/FFB-DESIGN-LIBRARY.md`, `docs/engine/FFB-STACKS.md`, `docs/engine/FORCE-FEEDBACK-AND-VISUALS.md`,
`docs/records/FFB-DATA-AUDIT.md`, `FFB-DEEP-DIVE.md`, `FFB-LAPTOP-RECON.md`, `FFB-MORNING-TEST.md`,
`SIM-RUMBLE-RESEARCH.md`, `SOUND-INTERPOSER-REVIEW.md`, `MOTION-SIM.md`, `READY-TO-TEST.md` A7,
`BACKLOG-2026-10-02.md` (P3-01, P3-17, P3-18, P3-24, P4-20); `tools/ffb/README.md` and the scripts named in
section 1; `tools/telemetry/README.md`, `i76tel.h`, `verification-2026-10-01.txt`; `music-fix/strlkproxy.c`
(telemetry export, `frame_sound_wrap`, `apply_joy_routing`), `music-fix/README.md`; `ffb-shim/README.md`,
`i7ffshim.c`; `sound-rumble/README.md`, `dsndrumble.c`; `windows/i76-remap.ahk` rumble block; `docs/guides/WHEEL-T300.md`.
Lab: `../<lab>/src/dsstub.c`, `tools/mute.ps1`, `docs/ENGINE-REFERENCE.md` (FFB block rows).
Map: `../<re-archive>/subsystems/sound.md` (voice record, `sound_StartVoice` 0x4220c0, tyre table 0x4bd0d0, engine
loop callback 0x424ca0), `data/FORMATS.md` 8 (.gpw) and the `.frc` row.

Web (this pass): Lofelt/Immersion patents and Meta Haptics Studio docs (research item 1); Microsoft XInput and
Xbox devdocs (item 5); PMC11814341, Southampton eprints, Prosig, Larson Davis (items 3-4); SimHub forum and
community wiki, VB-Audio forum, Equalizer APO (items 6-7). URLs inline above.
