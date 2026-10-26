# Motion simulator output: research, formats, cueing pipeline, hardware-free testing

*Design and research pass, 2026-10-10. Read-only: nothing was run, no game folder or code was touched, nothing was
installed. This is the plan the implementation agent builds the `Udp.*` motion renderers and the `Motion` core
module from, inside the haptics host of `docs/engine/HAPTICS-ARCHITECTURE.md`. It is not a record of anything built.*

*Implementation status (2026-10-10): phases M0-M3 are built in `tools/haptics` (`src/Haptics/Core/Motion/`, the
`Motion.Udp` renderer, `haptics.ps1 motion`, the validator and the desk-bench instructions in
`tools/haptics/motion/README.md`); M4-M6 are not. Where the build departs from this plan: synthetic replays are
`.i76rec` (the host's recording container), not `.i76tel`; the cue list adds the a_diff residual as an "impulse" cue
and an `impact_peak` gain; i76motion rotations are pinned to the aerospace body convention (the "right-handed" wording
in 3.3 is not self-consistent for forward / right / up); the M0 result is recorded in the 3.1 note below. Owner tests
are items 17-25 of docs/process/OWNER-TEST-LIST.md.*

**Owner's request.** "Add motion simulator output to the force feedback stuff, and a way to test it with whatever
motion simulator software people use." Owner context: sim cockpit first, four actuators later; D-BOX and Sigma are
closed ecosystems for a custom feed.

Evidence legend: **[live]** measured in a running game and cited; **[static]** a cited instruction or source line;
**[web]** a cited external page read in this pass; **[forum]** a community post, not vendor documentation;
**[calc]** arithmetic done here from a cited field list; **[proposed]** this document. Where a fact is not known it
says **unknown**.

---

## 0. Short version

1. **Emit three wire formats, all plain UDP, no handshake, from one `Motion` state:** (A) **LFS OutSim / OutGauge**
   (already written by `tools/ffb/ffb-telemetry-udp.ps1`, 21 layout assertions, but with pitch / roll / position /
   rpm / gear hard-coded to zero); (B) **Forza "Data Out" Sled (+ Dash)**, the other format every consumer parses;
   (C) **`i76motion` v1**, our own documented 144-byte float array, for FlyPT Mover's byte-offset "custom UDP"
   source, for Lua / Python scripts, and for our own validator. Byte layouts in section 3.
2. **The hardware-free test bench is FlyPT Mover** (free for home use, built-in Live For Speed source on
   4123 / 4124, 3D rig preview that moves with no hardware attached [forum]). SimHub is second (free core, native
   LFS on 63393 / 63392, motion add-on works in time-limited sessions without a licence, 3D Stewart preview).
   SimTools is third because **its free DIY licence was discontinued in May 2026** [web]; it still ships LFS support
   built in, so format A reaches it if the owner buys a licence.
3. **The host sends raw body-frame SI data to third-party software and does its own washout only for the direct
   actuator path** (design-library rule: the rig's software owns the cueing). Section 4 specifies both halves.
4. **The engine really has** body-frame acceleration, a 3x3 pose, yaw rate, per-wheel suspension offsets, surface
   id, airborne / skid flags, impacts with a vector, explosions with a distance. **It does not have** usable pitch
   and roll *rates* (the contact model's lift targets, a square wave), a tyre model, or a continuous physics
   state between its 24 Hz steps. Section 4.1 says how each channel is derived and what the proxy must add.
5. **Safety for real actuators later** (section 6): clamp, slew-limit, fail-to-neutral on stale telemetry with a
   ramp not a step, a status word every consumer must check, a kill switch that is a hardware E-stop first and a
   software command second.

---

## 1. Research: what motion users run and what each accepts

### 1.1 Software, licence, input routes

| software | cost | how a game feeds it | what fits us | sources |
|---|---|---|---|---|
| **FlyPT Mover** 3.5 / 3.7 beta (Windows, DIY 2-6 DOF, Thanos / SMC3 / ODrive / serial / UDP / shm outputs) | free for personal home use, donations | game sources by protocol (UDP, shared memory, DLL hooks); **Live For Speed source** expects `OutSim Mode 2, Delay 1, IP 127.0.0.1, Port 4123, ID 1, Opts 1ff` and OutGauge on 4124, LFS >= 0.6V; Codemasters UDP 20777; BeamNG; SimTools can be a source; "customizable sources to add compatibility with other games" (a custom UDP source with per-field byte offsets and 4-byte floats is described by users and the developer [forum]); plugins / API promised for 4.0 (not shipped) | **format A reaches it today.** 3D rig preview and pose graphs exist and move without hardware [forum]. **Forza is not in Mover 3.5's games list** [web]; custom UDP source UI specifics unverified here | [flyptmover.com](https://www.flyptmover.com/), [games sources](https://www.flyptmover.com/mover-3-5/sources/games), [FAQ](https://www.xsimulator.net/community/faq/flypt-mover.29/category), forum: [custom UDP floats at offsets](https://xsimulator.net/community/goto/post?id=216401), [generic source WIP](https://xsimulator.net/community/goto/post?id=207567), [3D viewer moves with nothing connected](https://xsimulator.net/community/goto/post?id=215734) |
| **SimHub** (dash, ShakeIt tactile, motion add-on) | core free; **motion add-on fully functional in time-limited sessions without a licence**, 34.99 EUR one-time + SimHub licence for unlimited | native game list includes LFS (in-app instructions: OutSim 63393 / OutGauge 63392, Opts 1ff, per the existing script header); **External Sim Integration** (beta, >= 9.11.5): a `*.simdef` definition + a binary UDP feed at **>= 60 Hz** whose struct is generated by SimHub's editor ("copy demo code" C# / C++); Telemetry Receiver Tester; UDP Relay plugin to re-forward a stream | **format A reaches it today.** 3D Stewart preview; effect analyzer on real telemetry; Dash Studio property viewer. A `.simdef` would be the long-term "first-class" route but the contract is unstable (page says breaking changes possible) and its port / layout are only in generated code: **unknown** here | [SimHub motion](https://www.simhubdash.com/?p=2326), [External sim integration](https://manual.simhubdash.com/external-sim-integration) |
| **SimTools** v3 (xsimulator.net; the DIY standard; DOF Reality, Yaw and many Arduino rigs use it) | **"Free DIY licences were discontinued in May and are no longer available"**; licence via simtools.us; plugin plans 59 EUR unlimited / 29 EUR per year; LFS support included, 80+ plugins | game plugins (.NET) per game; LFS plugin = **OutSim classic 64 bytes on 4123, ID 0** (the repo's `simtools` target); Output Testing uses the **Default** Axis Assignments profile; the game plugin is **not called unless an interface is configured** (workaround: a Network interface to 127.0.0.1:6123) [forum]; Virtual Axis sliders can stay still even when the plugin reports running [forum]; **"Game Dash"** = dash outputs of the plugin API (112 dash outputs), **not** a generic UDP input: no generic UDP game plugin found: unknown | **format A reaches it if licensed.** A SimTools plugin for `i76motion` is a later option (LFS_V3_Source_Dash example zip is the template) | [xsimulator SimTools page](https://www.xsimulator.net/simtools/), forum: [plugin API v3](https://xsimulator.net/community/goto/post?id=234974), [no interface = plugin not called](https://www.xsimulator.net/community/goto/post?id=111288), [free version restricted to LFS (older)](https://xsimulator.net/community/goto/post?id=245545) |
| **SimXperience Sim Commander** (Stage / GS-5 seats, SimVibe) | with hardware | **Open Game Telemetry**: 260 bytes = 65 float32 on **UDP 10001**, 60-400 Hz, `total_time` must be accurate; yaw/pitch/roll rad, rates rad/s, g-forces in G, local velocity m/s, speed m/s, gear -1/0/n, engine_rate rad/s, suspension m (x1000 scale note) | a documented generic format; cheap to add later as format D | [Sim Commander API](https://www.simxperience.com/slides/slide/sim-commander-api-sdk-open-game-telemetry-100) |
| **Simucube Tuner** (ActivePedal / wheelbase telemetry effects) | with hardware | LFS: `OutSim Mode 1 ... Port 63393 Opts 1ff`, `OutGauge Mode 2 ... Port 63392` (same ports as SimHub; one listener per port) | format A | [docs.simucube.com LFS](https://docs.simucube.com/TunerSoftware/games/LFS.html) |
| **D-BOX** (HaptiSync Hub, Motion Codes) | closed | per-game integration through the D-BOX SDK (Star Citizen built on it); BeamNG via the game's OutGauge 4444 + MotionSim with HaptiSync Center launching the game; Condor 2 via the game's UDP.ini; the **HaptiSync API is a control API** (levels, profiles), not a telemetry input | **no public custom-game telemetry route found**: a D-BOX feed needs their SDK (developer contact). Out of scope | [HaptiSync API](https://support.d-box.com/en/knowledge/d-box-haptisync-api), [BeamNG](https://support.d-box.com/knowledge/how-to-activate-d-box-haptic-in-beamng), [Condor 2](https://support.d-box.com/knowledge/activate-haptics-condor-2), [Star Citizen SDK post](https://robertsspaceindustries.com/spectrum/community/SC/forum/1/thread/wip-star-citizen-haptic-system-support-experimenta) |
| **Sigma Integrale** DK2 / DK6 (SigmaSimulation software) | closed | telemetry only, per-game (iRacing, rFactor, BeamNG named); a review lists "does not yet support older games (SimHub integration coming)"; no UDP / SimTools input documented | **unknown**; if SimHub integration ships, format A via SimHub is the route | [review](https://overclocking.com/test-sigma-integrale-dk6-et-dk2-le-tueur-de-d-box/3/), [overtake thread](https://overtake.gg/threads/dk-sigma-motion-system-usa-made.219697/page-5) |
| **Qubic System** (QS-220 etc., Qubic Manager) | with hardware | pre-built profiles per game; **ForceSeatMI** API for a sim to push telemetry; UDP forwarding added 2.173 | a ForceSeatMI client is a possible later renderer; SDK terms unknown | [Qubic Manager docs](https://docs.qubicsystem.com/docs/software/qubic-manager/), [2.173 notes](https://qubicsystem.com/2025/12/qubic-manager-new-version-2-173/) |
| **Next Level Racing** Platform Manager | with hardware | per-game profiles; **no public API found**: unknown | via SimTools / SimHub plugins only, if those exist for NLR (unknown) | [Platform Manager onboarding](https://support.nextlevelracing.com/hc/en-us/articles/16165035123471-Platform-Manager-Onboarding) |
| **Yaw VR** (Yaw2 / Yaw3, Yaw Game Engine) | with hardware | own Game Engine (per-game, joystick-input mode reported) or SimTools; no generic UDP found: unknown | via SimTools (format A) | [forum](https://www.xsimulator.net/community/posts/237658), [Unreal plugin thread](https://forums.unrealengine.com/t/yaw-vr-plugin/1922894) |
| **DOF Reality** | with hardware | SimTools (bundled) or SimHub | format A via either | [forum](https://xsimulator.net/community/goto/post?id=142842) |
| **Thanos AMC-AASD15A, SMC3, ODrive, BFF 6DOF, SimFeedback SFX-100** | controller / actuator side | fed by Mover / SimTools / SimHub outputs, not by games; "same data format as all my AMC controllers", compatible with SimTools, FlyPT and BFF | not game formats; relevant only for the owner's own actuators later (section 4.3) | [Tindie AMC](https://www.tindie.com/products/Tronicgr/amc-aasd15a-servo-motion-controller/), [overtake thread](https://www.overtake.gg/threads/thanos-amc-aasd15a-6axis-servo-motion-controller.168360/) |

### 1.2 Game-side formats that the consumers parse (the candidates for our wire)

| format | who reads it natively | shape | frame / units | notes |
|---|---|---|---|---|
| **LFS OutSim** (classic 64 B; OutSimPack2 280 B with `Opts 1ff`) + **OutGauge** (92 B, +4 with ID) | FlyPT, SimHub, SimTools (built in), Simucube Tuner, Sim Racing Studio and SIMRIG (ports 30000 / 30001 per the existing script), BeamNG emits it, D-BOX reads BeamNG's | fixed little-endian structs, no header on classic; `LFST` header on pack2 | X right, Y forward, Z up; Heading anticlockwise from above, Pitch anticlockwise from the right, Roll anticlockwise from the front; m/s, m/s^2, rad/s; Pos fixed-point 1 m = 65536. **World vs car-local for Accel / AngVel is disputed on the LFS forum** and the doc text (`LFS\docs\OutSimPack.txt`) could not be fetched here: the repo script says world frame, written from the doc; **verify against the doc file before the first live test** | [en.lfsmanual OutSim](https://en.lfsmanual.net/wiki/OutSim), [OutGauge](https://en.lfsmanual.net/wiki/OutGauge), [InSim.txt mirror](https://en.lfsmanual.net/wiki/InSim.txt); forum [frame question](https://lfs.net/forum/post/2119803) (login-gated, summary via search) |
| **Forza Data Out** "Sled" 232 B / "Dash" 311 B (FM7, FM 2023 +20 B extras = 331; FH4 / FH5 insert 12 B after the Sled block = 324; FH6 names them CarGroup, SmashableVelDiff, SmashableMass) | SimHub, SimTools (plugin), Sim Racing Studio, many phone dashes; FlyPT: not listed | fixed little-endian struct, no header; 60 packets/s | **car-local**: X right, Y up, Z forward; angular velocity X pitch, Y yaw, Z roll; yaw / pitch / roll angles; m/s^2, m/s, rad/s, rad per community consensus (official page returned 403 here; FH6 page confirms the three inserted fields) | [Forza FM doc (403)](https://support.forza.net/hc/en-us/articles/21742934024211-Forza-Motorsport-Data-Out-Documentation), [FH6 doc](https://support.forza.net/hc/en-us/articles/51744149102611-Forza-Horizon-6-Data-Out-Documentation), [geeooff/forza-data-web structs](https://github.com/geeooff/forza-data-web) |
| **Codemasters F1 UDP** (2018+; header 24 B + 22 x 60 B CarMotionData + 120 B player data = 1464 B motion packet) | SimHub, SimTools, FlyPT (port 20777), D-BOX for F1 titles | versioned header (`m_packetFormat`, `m_packetId` 0 = motion); little-endian packed | world position / velocity, normalised direction int16 / 32767, g-forces in **G** (lateral, longitudinal, vertical), yaw / pitch / roll rad; player-only suspension / wheel slip / local velocity / angular velocity; "rate as specified in menus" (10-60 Hz in-game) | heavy (22 cars) and versioned per year; **not recommended** as our wire | [F1 2020 spec](https://f1-2020-telemetry.readthedocs.io/en/stable/telemetry-specification.html) |
| **BeamNG MotionSim** (`BNG1` tag + floats: pos, vel, acc gravity-excluded, up vector, roll / pitch / yaw angles and rates, newer versions + angular accelerations) | FlyPT, SimTools, SimHub, D-BOX (via HaptiSync) | fixed struct, two documented variants | gravity excluded; size / endianness not confirmed here | a fourth candidate; not adopted (two struct variants, no size confirmed) | [BeamNG protocols](https://docs.beamng.com/modding/protocols/) |
| **rFactor 2 / AMS2 / ACC shared memory** | everything | a plugin DLL inside the game writes a memory-mapped file | n/a | **not applicable**: needs a plugin in the game, and consumers key on the game process name | [FlyPT games page](https://www.flyptmover.com/mover-3-5/sources/games) |
| **Sim Commander Open Game Telemetry** (260 B, 65 floats, UDP 10001) | SimXperience only | plain floats | rad, rad/s, G, m/s, m | documented, generic, SimXperience-only | [spec](https://www.simxperience.com/slides/slide/sim-commander-api-sdk-open-game-telemetry-100) |

**Conclusion.** Every consumer that matters parses LFS OutSim/OutGauge; most also parse Forza Sled; FlyPT additionally
takes an arbitrary float array by byte offset. So: A + B + C below. One listener per UDP port is the rule in this
ecosystem (SimHub relay exists for the reverse case); since **we are the sender** we send a copy to every configured
target and the problem disappears, as the existing script already notes.

---

## 2. Where this sits in the haptics host

```
 Core.FrameState (i76tel frame, physics pose)            Motion.Derive  ──► Motion.State (SI, body frame, per physics step)
 Core.EventBus (IMPACT / EXPLOSION / LANDING / ...)  ──► Motion.Cues    ──► cue spikes (separate channels)
                                                          Motion.Resample (24 Hz step -> 60/100 Hz output, interpolate or hold)
                                                          Motion.Safety  (clamp, slew, stale -> neutral, status word)
                                                            ├─ Renderers/Udp.OutSim.cs     (A: classic 64 / pack2 280 / OutGauge 92-96)
                                                            ├─ Renderers/Udp.Forza.cs      (B: Sled 232 / Dash 311)
                                                            ├─ Renderers/Udp.I76Motion.cs  (C: native 144 B, also the validator's input)
                                                            ├─ Renderers/Udp.OpenGameTelemetry.cs  (D, later, 260 B)
                                                            └─ Renderers/Actuator.Direct.cs (later: Motion.Washout -> 4 actuators)
```

- `Motion.*` is a **pure-function module** under `tools/haptics/src/Core/Motion/` with no device or socket code, so
  the replay harness tests it bit-exactly. The `FfbMixer.ps1` bus already carries `Motion {SurgeA, SwayA, HeaveA,
  YawRate, Pitch, Speed}`; the C# `Motion.State` is its superset and the A2 port test maps those six fields 1:1.
- The time base is the engine's (`sim_time`, `frame`, `step_count`), never wall clock, so a `.i76tel` replay produces
  the same packets as the live run (architecture doc 2.1).
- The architecture doc's `Udp.OutSim` renderer row is this document; its B3 milestone ("pitch / roll / pos / rpm /
  gear filled") becomes phase M1 below.

---

## 3. The three wire formats, byte-exact

All little-endian, naturally aligned, no padding; `f32` = IEEE single. Offsets are bytes from the start of the
datagram. Axis maps are from I'76 world `(x, y_up, z)` / body rows `right, up, forward` (`i76tel.h` `rot`).

### 3.1 Format A: LFS OutSim / OutGauge (existing, to be completed)

**OutSim classic, 64 bytes (+4 with ID != 0).** Consumers: SimTools (4123, ID 0), SRS / SIMRIG (30000).

| off | type | field | our value |
|---:|---|---|---|
| 0 | u32 | Time ms | `sim_time x 1000` (wraps) |
| 4 | f32 | AngVel X (rotation about LFS X = right, i.e. pitch rate; see the labelling note below) | `pitch_rate_derived` |
| 8 | f32 | AngVel Y (about LFS Y = forward, i.e. roll rate) | `roll_rate_derived` |
| 12 | f32 | AngVel Z (about up) | `yaw_rate` (ent+0xcc) [live] |
| 16 | f32 | Heading rad, anticlockwise from above | `atan2(rot[6], rot[8])` with sign per LFS (anticlockwise positive); calibrate sign in M1 test |
| 20 | f32 | Pitch rad | `asin(rot[7])` |
| 24 | f32 | Roll rad | `asin(rot[1])` |
| 28 | f32 | Accel X (right) | `a.x` |
| 32 | f32 | Accel Y (forward) | `a.z` (I'76 z) |
| 36 | f32 | Accel Z (up) | `a.y` (I'76 y) |
| 40 | f32 | Vel X | `velocity[0]` |
| 44 | f32 | Vel Y | `velocity[2]` |
| 48 | f32 | Vel Z | `velocity[1]` |
| 52 | i32 | Pos X (1 m = 65536) | `pos[0] x 65536` |
| 56 | i32 | Pos Y | `pos[2] x 65536` |
| 60 | i32 | Pos Z | `pos[1] x 65536` |
| 64 | i32 | ID (only if configured non-zero) | per target |

Note on LFS AngVel axis labelling: the doc text was not fetched; the LFS convention (X right, Y forward, Z up) makes
AngVel X a rotation about right = pitch rate, Y about forward = roll rate, Z = yaw rate. The existing script's
comments label them the other way round; **check `LFS\docs\OutSimPack.txt` and fix the comments in M1** (the
value it sends in X and Y is zero today, so nothing is wrong on the wire yet). Whether Accel / Vel / AngVel are
world or car-local in LFS is **unknown** (disputed, section 1.2); the host offers both via `frame: "world" | "body"`
per target, default `world` as the script has it, and the FlyPT test in section 5.1 settles which one makes the
rig behave (brake: the rig should pitch nose-down regardless of heading; if it depends on heading, the frame is wrong).

**M0 result (2026-10-10, implementation agent).** `OutSimPack.txt` / `OutSimPack.h` could still not be read: not on the
LFS manual wiki ([OutSim](https://en.lfsmanual.net/wiki/OutSim) only points at the file), and the lfs.net forum threads are
login-gated. The [InSim.txt mirror](https://en.lfsmanual.net/wiki/InSim.txt) gives the classic field list and the angle
conventions (Heading anticlockwise from above (Z), Pitch anticlockwise from right (X), Roll anticlockwise from front
(Y); "X and Y axes are on the ground, Z is up") and nothing on frames. A web-search summary of the LFS developer's reply in
the U9 OutSimPack thread ([lfs.net/forum/post/2066823](https://www.lfs.net/forum/post/2066823)) says positions,
velocities and accelerations are **world** coordinates (convert with the Euler angles); AngVel is not addressed
[forum, via search summary, not read first-hand]. The implementation: `frame` per target, default `world`, AngVel
rotated with the same matrix; AngVel X = pitch rate (about right), Y = roll rate (about forward), Z = rotation about up,
anticlockwise-positive (so a right turn sends a negative Z, and the heading is sent negated). The existing script's
X/Y labels were indeed swapped and its heading sign was clockwise; both are superseded by the host. T2 still decides.

**OutSimPack2, 280 bytes (`Opts 1ff`).** Consumers: FlyPT (4123, ID 1), SimHub (63393, ID 0), Simucube Tuner (63393).
Layout as the existing builder: `0 'LFST'`, `4 i32 ID`, `8 u32 Time`, `12..71 OutSimMain` (the 60 bytes = classic
offsets 4..63 shifted by +8), `72..91 Inputs {Throttle, Brake, InputSteer rad, Clutch, Handbrake}`,
`92..103 Drive {u8 Gear (0 R, 1 N, 2 = 1st), 3 x u8 spare, f32 EngineAngVel rad/s, f32 MaxTorqueAtVel}`,
`104..111 Distance {CurrentLapDist, IndexedDistance}`, `112..271 4 x 40-byte OutSimWheel {SuspDeflect, Steer, XForce,
YForce, VerticalLoad, AngVel, LeanRelToRoad, u8 AirTemp, u8 SlipFraction, u8 Touching, u8 spare, SlipRatio,
TanSlipAngle}`, `272..279 Extra1 {SteerTorque, spare}`. Fill in M1: `Gear` = `gear` mapped (I'76 0 R -> 0, 1 N -> 1,
2/3/4 -> 2/3/4); `EngineAngVel` = `rpm x 2 pi / 60`; `InputSteer` = `steer x lock` (lock from `ffb-calib.json` until
`ent+0x118` wheelbase / lock is in the frame); wheels: `SuspDeflect` = `-susp_offset` of slots 0 1 4 5 (LFS order
unknown: assume RL RR FL FR as Codemasters, mark and verify in SimHub's wheel display), `VerticalLoad` = `mass x
9.8 / 4` while grounded else 0, `Touching` = `!unloaded && !airborne`, `SlipFraction` = 255 x `skid_active`; rest 0.
Honest accounting rule stays: zero rather than invent.

**OutGauge, 92 bytes (+4 ID).** Fill in M1: `Gear` as above, `RPM` = `rpm` (850..7000 [live]), `Car` = `'I76 '`,
`Throttle` / `Brake` split from the signed `throttle`, `DashLights` bit 2 handbrake available, `ShowLights` bit 2 =
`handbrake`, bit 17 neutral = `gear == 1`, bit 11 engine damage = `engine_hp / engine_hp_max < 0.5`, bit 0 shift
light = `rpm > 6000`; `Display1` = the weapon name (8 chars) so a SimHub dash shows it.

### 3.2 Format B: Forza Data Out, Sled 232 bytes and Dash 311 bytes [calc from the community struct]

Frame: **car-local**, X right, Y up, Z forward: exactly `rot`'s row order, so `AccelerationX/Y/Z = (sway, heave,
surge)`, `VelocityX/Y/Z = body velocity`, `AngularVelocityX/Y/Z = (pitch, yaw, roll) rates`. Units m/s^2, m/s,
rad/s, rad (community consensus; official page unreachable here). Rate 60 Hz. Wheel order FL FR RL RR.

| off | type | field | our value |
|---:|---|---|---|
| 0 | s32 | IsRaceOn | `player_present && !(flags & 0x20)` ? 1 : 0 (0 in menus; consumers park) |
| 4 | u32 | TimestampMS | `sim_time x 1000` |
| 8 / 12 / 16 | f32 | EngineMaxRpm / EngineIdleRpm / CurrentEngineRpm | 7000 / 850 / `rpm` |
| 20 / 24 / 28 | f32 | AccelerationX / Y / Z | sway / heave / surge (gravity excluded, section 4.1) |
| 32 / 36 / 40 | f32 | VelocityX / Y / Z | body velocity (`rot` rows dot `velocity`) |
| 44 / 48 / 52 | f32 | AngularVelocityX (pitch) / Y (yaw) / Z (roll) | derived pitch rate / `yaw_rate` / derived roll rate |
| 56 / 60 / 64 | f32 | Yaw / Pitch / Roll | heading / `asin(rot[7])` / `asin(rot[1])` |
| 68..80 | 4 x f32 | NormalizedSuspensionTravel FL FR RL RR (0 stretch .. 1 compressed) | `0.5 - susp_offset / (2 x 0.25 r)` clamped (travel is +-0.25 x tyre radius [static]; radius unknown in the frame: use 0.5 +- `susp_offset / 0.25` scaled by a rig constant until `wheel radius` is exported) |
| 84..96 | 4 x f32 | TireSlipRatio (|x| > 1 = grip loss) | `skid_active ? 1.5 : 0` per wheel; or `flags & 0x2000` ? 1.5 |
| 100..112 | 4 x f32 | WheelRotationSpeed rad/s | `ground_speed / r` (r unknown: 0.35 m default in `rigs`) |
| 116..128 | 4 x s32 | WheelOnRumbleStrip | 0 |
| 132..144 | 4 x f32 | WheelInPuddleDepth | 0 (oil flag could map here: `flags & 0x400 ? 1 : 0`, flagged "approximation") |
| 148..160 | 4 x f32 | SurfaceRumble (non-dimensional) | `surface_bump_amp x speed` normalised (section 4.1 texture) |
| 164..176 | 4 x f32 | TireSlipAngle | `skid ? 1.5 : 0` |
| 180..192 | 4 x f32 | TireCombinedSlip | max of the two |
| 196..208 | 4 x f32 | SuspensionTravelMeters | `susp_offset` |
| 212 / 216 / 220 / 224 / 228 | s32 | CarOrdinal / CarClass / CarPerformanceIndex / DrivetrainType / NumCylinders | 1976 / 3 / 500 / 1 (RWD) / 8 |
| **= 232** | | **end of Sled** | |
| 232 / 236 / 240 | f32 | PositionX / Y / Z m | `pos[0] / pos[1] / pos[2]` (Forza Y up matches I'76) |
| 244 | f32 | Speed m/s | `speed` |
| 248 / 252 | f32 | Power W / Torque Nm | `drive_power x mass x speed`? unknown scaling: 0 |
| 256..268 | 4 x f32 | TireTemp | 0 |
| 272 / 276 / 280 | f32 | Boost / Fuel / DistanceTraveled | `flags & 0x800` (nitrous) ? 1 : 0 / 1 / integrated `speed x dt` |
| 284 / 288 / 292 / 296 | f32 | BestLap / LastLap / CurrentLap / CurrentRaceTime | 0 / 0 / 0 / `sim_time` |
| 300 | u16 | LapNumber | 0 |
| 302 | u8 | RacePosition | 1 |
| 303 / 304 / 305 / 306 | u8 | Accel / Brake / Clutch / HandBrake (0..255) | `max(0, throttle) x 255` / `max(0, -throttle) x 255` / 0 / `handbrake x 255` |
| 307 | u8 | Gear (0 = R, 1 = N, 2.. forward, Forza convention 0 R 1 N? community says 0 = reverse) | I'76 `gear` directly (0 R, 1 N, 2..4) **after** checking a consumer's gear display |
| 308 | s8 | Steer (-127..127) | `steer x 127` |
| 309 / 310 | s8 | NormalizedDrivingLine / NormalizedAIBrakeDifference | 0 |
| **= 311** | | **end of Dash (FM7 / FM 2023 without extras)** | |

Sizes: Sled 232 and Dash 311 are the FM7 figures users report; FM 2023 adds 20 bytes (331, tyre wear x4 + track
ordinal per the geeooff README footnote); FH4 / FH5 are 324 (12 bytes inserted at 232). **Send 311** (FM7 Dash),
which SimHub's "Forza Motorsport 7" game entry accepts [forum], and keep `format: "sled"` for a 232-only consumer.
Verify once in SimHub's Forza telemetry view that gear and speed read right (section 5.2).

### 3.3 Format C: `i76motion` v1, 144 bytes [proposed]

Plain float array after a 16-byte header, so FlyPT's custom UDP source (offset + float32 per field), a Lua or
Python script, SimTools' GenericUDP-style plugin template, and our validator all read it. Body frame, right-handed:
+surge forward, +sway right, +heave up (gravity excluded); roll about forward, pitch about right, yaw about up;
positive = right-hand rule. Rate = the output rate (60-100 Hz). One datagram per output tick, default port
**7677** (7676 is the raw `i76tel` passthrough).

| off | type | field | notes |
|---:|---|---|---|
| 0 | char[4] | magic `'I76M'` | |
| 4 | u16 | version = 1 | |
| 6 | u16 | size = 144 | |
| 8 | u32 | seq | output tick counter |
| 12 | u32 | status | bit0 live (player present, in play loop), bit1 airborne, bit2 skid, bit3 destroyed/wreck, bit4 paused/menu (telemetry stopped but host alive), bit5 **fail-to-neutral active** (stale), bit6 sample is interpolated, bit7 cues present this tick, bits 8-15 surface id, bits 16-23 gear (0 R, 1 N, 2-4), bit 31 host shutting down |
| 16 | f32 | t_sim s | engine time |
| 20 / 24 / 28 | f32 | surge / sway / heave m/s^2 | physics acceleration, body frame, gravity excluded |
| 32 / 36 / 40 | f32 | roll_rate / pitch_rate / yaw_rate rad/s | derived / derived / `yaw_rate` |
| 44 / 48 / 52 | f32 | roll / pitch / heading rad | from `rot` |
| 56 | f32 | speed m/s | |
| 60 | f32 | rpm | |
| 64 | f32 | gear | -1 R, 0 N, 1..3 (float for Lua consumers) |
| 68 / 72 / 76 | f32 | throttle / brake / steer | 0..1, 0..1, -1..1 |
| 80..92 | 4 x f32 | susp FL FR RL RR m | `susp_offset` slots 0 1 4 5 |
| 96..108 | 4 x f32 | wheel_skid FL FR RL RR | 0 / 1 |
| 112 | f32 | texture 0..1 | `surface_bump_amp x speed`, for a rig's own road-noise effect |
| 116 / 120 / 124 | f32 | cue_surge / cue_sway / cue_heave m/s^2 | **event spikes only** (impact, explosion, landing), kept out of the physics channels so a consumer can scale or drop them |
| 128 / 132 / 136 | f32 | vel_body x / y / z m/s | right / up / forward |
| 140 | u32 | reserved (0) | |

`tools/haptics/schema/i76motion.json` carries this table as data; `i76motion.py` (validator) and the C# renderer
both read it, like `i76tel.h` / `i76tel.py` today, so the layout cannot drift.

---

## 4. The motion pipeline inside the host

### 4.1 Deriving the channels from `i76tel_frame_t`

| channel | source | derivation | confidence / caveat |
|---|---|---|---|
| **surge / sway / heave** (steady) | `accel_body[3]` (FFB block 0x4f2418, `math_Mat3MulVec3(ent+0xd4, obj+0x18)`) while `ffb_present`; else `accel[3]` (ent+0xd4, world) rotated: `sway = dot(rot[0..2], a)`, `heave = dot(rot[3..5], a)`, `surge = dot(rot[6..8], a)` (row-vector convention `world = local x R` => `local_i = row_i . world`) | ent+0xd4 is the integrator's commanded acceleration (drive / brake / resistance / side / slope pull) [static, FFB-DATA-AUDIT row 5]; it is **gravity-free in the grounded branch** (9.51 m/s^2 at full brake near rest [live, physics.md]); **whether the airborne branch writes -9.8 into it is unknown** (gate: zero the physics channels while `flags & 4` unless a live jump capture shows otherwise); it **omits** the brake-dive projection loss (-0.37 m/s^2 [live]) and **omits contact impulses** (velocity is changed directly in step 2) | sign convention of `accel_body` is inferred, one braking test settles it (audit row 5): **M1 test 2** |
| **a_diff** (transient) | `(velocity_n - velocity_{n-1}) / sim_dt`, only across frames where a physics step ran (`step_count > 0`, or `frame` advanced and `pos` changed) | catches the impulses the integrator vector misses (wall hits, car-car, landings) | at 24 Hz steps a 1-step impulse of dv = 5 m/s reads 120 m/s^2: feed it to `Motion.Cues`, never raw to the steady channel |
| mode | `rigs/<rig>.json: motion.accel_source = "integrator" | "differentiated" | "blend"` | blend = integrator for < 2 Hz, high-passed a_diff for the rest | default `blend` once M1 test 2 proves the sign; `integrator` until then |
| **pitch / roll / heading** | `rot`: `pitch = asin(rot[7])`, `roll = asin(rot[1])`, `heading = atan2(rot[6], rot[8])` [live for rot] | real: the body sits on the offset wheels, `sin p = 2 x 0.008 x a_long / L` (Piranha 1 g = 3.3 deg nose-down [live]) plus terrain slope; roll by the same rule laterally | sign of pitch (nose-down negative?) and LFS / Forza sign expectations: **M1 test 3** |
| **pitch_rate / roll_rate** | **derive by differentiating the angles across physics steps**, low-passed one step | `pitch_rate` / `roll_rate` (ent+0xc8 / +0xd0) are the contact model's **lift-target rates** (+-pi, +-pi/2, eased with a 0.5 s lag, snapped to 0 when settled) [static, physics.md "attitude model"]: a rest/contact square wave, not body motion. Airborne they are real (pitch eases to -pi/20, roll constant) | use the engine's rates only as **event detectors** (a wheel lifted) and while airborne |
| **yaw_rate** | `yaw_rate` (ent+0xcc) | fitted to steering at R^2 0.9997 [live] | real |
| **body velocity** | `rot` rows dot `velocity` | | |
| **speed, rpm, gear, throttle / brake / steer** | `speed`, `rpm`, `gear`, `throttle` sign-split, `steer` | all [live] | |
| **suspension** | `wheel[i].susp_offset` (+-0.25 r, 2nd-order IIR, pole 0.7) [static] | slots 0 1 4 5 = FL FR RL RR | the "filter" settles in ~0.3 s: a real dive / squat trace, step-rate dependent |
| **wheel slip** | `wheel[i].skid_active`, `flags & 0x2` / `0x2000` / `0x400` | binary; there is no tyre model | emit 0 / 1.5 in Forza slip fields, 0 / 1 in `i76motion` |
| **texture** | `surface` -> WRLD row +0x08 bump amplitude (audit 5.3) x `speed`, normalised to the loudest surface | the engine applies an 8x8 bump pattern per substep [static] | a per-surface table in `rigs/surfaces.json` until the WRLD amplitude is exported (**proxy v3 addition below**) |
| **airborne / landing** | `flags & 4` edges; `velocity[1]` of the previous frame at the falling edge | LANDING cue = `heave -= k x |v_y_prev|`, decayed | k in `rigs`; default 1.0 m/s -> 1 m/s^2 over 80 ms |
| **impact** | `IMPACT` event: `f[0..2]` impact vector (world), `f[3]` hp lost, `i[0]` is-player | rotate the vector into the body frame, cue = unit vector x `min(hp_lost / 60, 1) x cue_gain`, exponential decay tau 60 ms | only `i[0] == 1`; source class 0x33 ordnance gets half gain (recoil-sized) |
| **explosion** | `EXPLOSION` event `f[3]` distance (-1 none) | `cue_heave += gain / max(d, 3)^2`, capped, tau 120 ms; direction from `f[0..2] - pos` into the body frame as a small sway / surge | distance from the player object; a far FSM camera does not matter here |
| **shot** | `SHOT` `f[2]` damage per hit x `i[1]` rounds | optional recoil `cue_surge -= small`; default off (`motion.shot_recoil = 0`) | weapons already drive the wheel / pad; rigs that want it set the gain |
| **destroyed / menu** | `flags & 0x20 / 0x8000`, `player_present == 0` | status bits; all physics channels 0, cues 0; `IsRaceOn = 0` | consumers park |

**Physics step cadence.** Under `I76_FIXED_STEP=24` the state advances every 41.7 ms; stock 20 fps steps 46.9 /
31.2 ms (framerate.md). At 60-120 fps most rendered frames carry the **same** physics pose (the telemetry publishes
the physics pose, `I76_RENDER_INTERP` only changes what is drawn). `Motion.Derive` therefore runs **once per new
physics state**, detected as `step_count > 0` (under the fixed step) or a change in `pos` / `velocity` / `frame`
otherwise, and never differentiates across a repeated pose (that would read 0 then 2x).

**Resampling to the output rate** (`Motion.Resample`). Output 100 Hz default (60 Hz minimum; "a rock-steady 60 beats
an unstable 100", design library 6). Two modes in `rigs`:
- `interp` (default): linear interpolation between the last two physics samples; angles interpolated as angles
  (they are small); costs one physics step of latency (+42 ms) but removes the 24 Hz staircase that a rig would
  otherwise reproduce as a buzz (the architecture's shaker work found the stock 24 Hz cadence "as calm as stock 20"
  for the car body; a hexapod will show a staircase at 24 Hz if we hold).
- `hold`: zero-order hold + first-order low-pass (`motion.hold_lp_hz`, default 8 Hz) for latency-sensitive rigs.
- Cues are **not** resampled: they are generated at output rate from their own envelopes, so an impact never lands
  late by a step.

**Latency budget (motion).** physics step 0-42 ms + publish 1 frame (8-17 ms at 60-120 fps) + host poll <= 4 ms +
`interp` 42 ms (or 0 in `hold`) + UDP loopback < 1 ms + the consumer's own filters (Mover / SimHub typically 10-30 ms)
+ actuator response (unknown, rig-specific). ~60-110 ms to the actuator command in `interp`; cues ~20-65 ms.
Measured, not assumed, in owner test T5.

**Gravity.** LFS and BeamNG MotionSim both declare gravity-excluded acceleration (a parked car reads 0); Forza
behaviour is unknown but every consumer applies its own tilt coordination from the *angles*, so the physics channels
are gravity-free and slope reaches the rig through pitch / roll. The rig's software adds gravity back as tilt.

### 4.2 What the proxy must add (i76tel v3, alongside the architecture's sound events) [proposed]

| field | source | why | confidence |
|---|---|---|---|
| `uint32_t step_total` | the proxy's fixed-step accumulator count (it already computes `step_count`) | a monotonic substep counter so the host detects "new physics state" without comparing `pos` | proxy-side only, no new engine address |
| `float wheelbase`, `float track` | `ent+0x118` wheelbase (FFB-DATA-AUDIT 2.3); track: the lift-pivot table is built from +-0.5 x track at init 0x438d7e..0x438eb4 (physics.md), the stored value's offset is **unknown** | pitch model check `sin p = 2 x 0.008 x a_long / L`; OutSimPack2 geometry | wheelbase [static]; track unknown: omit until read |
| `float ground_height` | `veh+0x474` ground height at the last grounded substep [static, physics.md row B] | height above ground during flight = `pos[1] - ground_height` for a landing-severity predictor | B |
| `float gravity_normal` | `veh+0x46c` = 9.8 n.y^3 [static] | tells whether the slope pull is in `accel`; lets the host remove it if a consumer wants pure driver acceleration | B |
| `float contact_impulse[3]` | the car's contact record copied to `entity+0x38` and consumed next substep (physics.md "Cars (0x4643c0) copy the record into entity+0x38") | the impulse the integrator vector omits, with direction | address of the record known, **its field layout is not in the notes read here: unknown**; `a_diff` covers it meanwhile |
| `float surface_bump_amp` | WRLD row +0x08 for `surface` (audit 5.3) | texture channel without a hand table | [static] per the audit; row base address: check `renderer.md` / FORMATS before coding |
| `float wheel_radius` | WDFC data per wheel (the suspension travel clamp is +-0.25 x radius at 0x46d820) | normalised suspension travel and wheel angular speed for Forza | address of the radius field in the wheel object: unknown |
| `uint32_t in_play_loop` | the proxy knows it (telemetry already stops outside the play loop) | explicit menu / mission-over flag for `paused` rather than inferring from silence | proxy-side |

Nothing here is required for M1-M3; all are `v3` nice-to-haves ordered by value: `step_total`, `wheelbase`,
`surface_bump_amp`, then the rest. Each follows the existing rule: byte patterns asserted against the pristine image,
`i76tel.py --layout` regenerated, never deployed to the daily driver.

### 4.3 Washout for the direct actuator path (later; off for every UDP format)

Classical washout (Reid & Nahon; design library 6) as `Motion.Washout`, applied **only** by `Actuator.Direct`:

```
specific force f = a_body + g_body (g rotated into the body by rot; adds gravity back)
translational:  f_hp  = HP2(f, f_c = 0.3..0.5 Hz, zeta 0.7)  -> scale K_t -> double-integrate -> position, with
                washout return HP1 (tau 2-3 s) on the position
tilt coord.:    f_lp  = LP1(f, f_c = 0.3 Hz) -> tilt = asin(clamp(f_lp / g, +-0.25)) ; rate-limit 3 deg/s
                (2-4 deg/s production range), add to the rotational command
rotational:     w_hp  = HP1(body rates, tau 1-2 s) -> scale K_r -> integrate -> angle ; plus the slow terrain
                angles LP'd (pitch / roll from rot, LP 0.5 Hz) as a posing term
limits:         per-axis position / velocity / acceleration clamps from rigs/<rig>.json actuator geometry
cues:           added to f before the HP stage, so they are rendered as real translation
```

Parameters live in `rigs/<rig>.json: washout {...}` with the defaults above; a `--washout-plot` validator mode
(section 5.4) renders the step and sine responses so the owner tunes by picture before any actuator moves. For
the four-actuator rig the inverse kinematics are the rig vendor's or Mover's job: the planned first direct
target is **FlyPT Mover's own pose input** or **SimHub's motion output**, i.e. we keep sending raw data and let
Mover drive the controllers (Thanos / SMC3 / ODrive are all Mover outputs), and `Actuator.Direct` exists only if
the owner's controller has no Mover output. Unknown until the hardware is chosen.

---

## 5. Testing without hardware

### 5.1 FlyPT Mover (primary bench)

Install: download Mover 3.7 beta (or 3.5 stable) from flyptmover.com (`/mover-3-7/downloads`); free, no account.
Nothing in the game folder; nothing on the daily driver.

1. Start the host in replay mode: `haptics.ps1 -Replay replays\brake-corner-jump.i76tel -Motion flypt` (sends
   OutSimPack2 to 127.0.0.1:4123 with ID 1 and OutGauge to 4124; no wheel, no shaker, no pad).
2. In Mover: **Sources > Games > Live For Speed**; set OutSim port 4123, ID 1, OutGauge 4124 (Mover's defaults for
   this source per its own page). The source goes green / "connected" when packets arrive (yellow = port open, no
   data; red = disconnected [forum]). If yellow: another listener holds 4123 (SimTools?), or the ID differs.
3. **Rig**: add a "Linear hexapod" (6DOF) or "2DOF" rig; set actuator min / max (any numbers; e.g. +-100 mm). No
   output module needed. Open its **3D view**. [forum: the 3D viewer shows pitch / roll with nothing connected.]
4. **Pose > Pose from motion**: map Surge <- source "Acceleration longitudinal" (the LFS source's Y / forward),
   Sway <- lateral, Heave <- vertical, Yaw <- "Angular velocity Z", Pitch / Roll <- the angles (posing) and / or
   the angular velocities (transients). Leave Mover's default filters (its low-pass / high-pass are the cueing).
5. Expectations with the synthetic replay (section 5.4): braking segment: rig pitches **nose-down** then washes
   back; corner: rolls outward (sway) with yaw; jump: heave spike on landing only (free flight is flat, correct);
   wall hit: surge spike opposite to travel. If the braking pitch changes with heading, format A's frame setting
   is wrong (section 3.1 note): switch `frame: body`.
6. Record the Mover source graphs (Mover has graph visualisation modules) and compare against our validator plot
   of the same replay: same shape, same timing within one physics step.

Unknowns to resolve at the desk: the exact names Mover gives the LFS source's outputs; whether 3.7 beta's LFS
source needs `Opts 1ff` (pack2) or also accepts classic 64 (the host can send either per target); whether the
custom UDP source exists in the installed version (if yes, repeat with `i76motion` on 7677, entering offsets from
section 3.3).

### 5.2 SimHub (second bench; also the Forza check)

Install SimHub (free). **Games > Live for Speed** (SimHub expects OutSim 63393 / OutGauge 63392, Opts 1ff). Run
`haptics.ps1 -Replay ... -Motion simhub`. Checks:
- Dash Studio > the built-in "telemetry" dashboards or Settings > *Available properties*: `Speed`, `Rpms`, `Gear`,
  `AccelerationSurge/Sway/Heave` (SimHub names them `GlobalAccelerationG`-style; names unknown here, read the list),
  `OrientationPitch/Roll/Yaw`.
- **Motion add-on** (time-limited sessions without a licence): add a "Generic 6DOF" or 2DOF profile, open the 3D
  preview, play the replay; the **effect analyzer** records real telemetry.
- **ShakeIt** effects preview (RPM, speed, gear shift, wheel slip from our 0 / 1.5 slip, road texture) with no audio
  device selected, or routed to the EVO 4 only when the owner is present (architecture 3.4 mute rule).
- **Forza**: select **Forza Motorsport 7** in SimHub, run `-Motion simhub-forza` (Dash 311 to the port SimHub shows,
  default 5300 per SimHub's own page: unknown, read it in the UI), confirm gear / speed / rpm / accelerations read
  right. This is the only Forza consumer check we have at the desk.
- Optional later: a `.simdef` for `i76motion` through SimHub's definition editor (its Telemetry Receiver Tester then
  validates our packets); contract marked beta by SimHub, so phase M4 not M1.

### 5.3 SimTools (only if the owner licenses it)

SimTools v3 with the built-in LFS support: Game Engine > Interface Settings: add a **Network** interface to
127.0.0.1:6123 (any unused port) so the game plugin is called [forum]; Axis Assignments: fill the **Default**
profile (Output Testing uses it); Output Testing > Virtual Axis while the host sends classic OutSim 64 to 4123 with
ID 0 (`-Motion simtools`); Tuning Center shows min / max per DOF, which is a second validator of our ranges. Known
pitfall: Virtual Axis sliders not moving even with the plugin "running" [forum]; no fix documented.

### 5.4 Our own validator (`tools/haptics/motion/`, Python 3, offline)

| tool | does | why |
|---|---|---|
| `i76motion.py --sniff [--port N]` | binds the consumer ports we send to (when no consumer runs), **auto-detects the format by size / magic** (64 / 68 / 280 classic-pack2, 92 / 96 OutGauge, 232 / 311 Forza, 144 `I76M`), decodes every field with its name and unit, prints rate (Hz, jitter histogram), seq gaps, stale periods | proves our own wire before any third-party tool, the way `ffb-udp-listen.py` did for the shim |
| `i76motion.py --check` | conformance: sizes exact; magic; monotonic time; NaN / inf; angles within +-pi; accelerations within +-40 m/s^2 steady and +-200 cue; status bits consistent (airborne -> physics channels 0 unless configured); gear in range; packet rate within +-5 % of the configured output rate | the 21 existing layout assertions ported plus value ranges |
| `i76motion.py --plot run.i76motion out.html` | six DOF traces (surge / sway / heave, roll / pitch / yaw rate), angles, speed / rpm / gear, cue channels, event markers; HTML with the `ffb-graph.template.html` conventions (static, no server) | offline eyeball check; attach to owner reports |
| `motion_preview.html` (+ `i76motion.py --ws`) | a 3D car body (three.js from cdnjs, pinned version) that tilts by pitch / roll / heading and translates by the double-integrated high-passed accelerations with a visible washout, fed over a local websocket bridge from the sniffer at 60 Hz; DOF bars and the status word | a Mover-independent "does the car do what the game did" view; also the visual for `Motion.Washout` tuning (`--washout-plot`: step and sine responses) |
| `make_synthetic.py` | writes `replays/synth-*.i76tel` from scripted scenarios using the real `i76tel.h` layout: (1) 0 -> 30 m/s launch, full brake to 0 (expect surge -9.5, pitch -3.3 deg via the dive rule, susp FL/FR + / RL/RR -), (2) 90 deg corner at 20 m/s (sway +-, yaw_rate 0.4, roll), (3) ramp jump: airborne 1.2 s, landing with v_y = -6 m/s (LANDING cue), (4) wall hit at 15 m/s (IMPACT event, a_diff spike), (5) explosion at 8 m then 40 m, (6) 24 Hz steps rendered at 120 fps (same pose 5 frames in a row) to prove the dedupe and the resampler | tests exist before the first live `.i76tel` capture; each scenario has an expected-values table the `--check` compares |
| `replay.py` (architecture A1) | plays `.i76tel` at real or max speed into the host | the recordings are retained raw (memory: raw captures outlive methods) |

Golden tests (`tests/motion-test.ps1`): layout sizes; axis maps (a synthetic world acceleration of (1.5, 0.2, -4.0)
lands in OutSim X / Z / Y = 1.5 / 0.2 / -4.0 and in Forza as sway / heave / surge given an identity `rot`); rotation
(heading 90 deg: world +x becomes body forward); gravity exclusion (parked on a 10 deg slope: steady channels 0,
pitch 0.1745); dedupe (5 repeated poses -> one derive); resampler (24 -> 100 Hz, interpolation error < 1e-6 on a
linear ramp); fail-to-neutral timing (section 6); status bits.

---

## 6. Safety for real actuators (designed now, enforced in `Motion.Safety`, inert for UDP-to-software)

1. **Clamp** every physics channel at the source of truth for actuators: +-3 g steady (real telemetry spans ~+-3 g,
   design library 6), cues +-6 g, rates +-2 rad/s, angles +-0.35 rad; `rigs/<rig>.json` may tighten, never widen.
   For UDP-to-software targets the clamp defaults **off** (the library: "don't clamp at the source; rig software
   crops") and is a per-target switch.
2. **Slew limit** per channel (`max_jerk` m/s^3, `max_rate_change` rad/s^2) applied after resampling, so a single
   corrupt frame cannot command a step.
3. **Fail-to-neutral on stale telemetry**: no new physics state for `stale_ms` (default 250 ms: 6 physics steps)
   or `player_present == 0` or shm `seq` not advancing (memory: a named shm block outlives the game; liveness is an
   advancing heartbeat, never magic) -> set status bit5 and **ramp** every channel to 0 over `neutral_ramp_ms`
   (default 1000 ms), never a step to zero, which on a rig is itself a jolt. Recovery ramps back over the same time.
4. **Status word is mandatory**: `i76motion.status` bit5 (neutral), bit4 (paused); Forza `IsRaceOn = 0`; LFS has no
   flag so the LFS stream carries zeros. A direct actuator consumer **must** treat a missing heartbeat (no packet
   for 500 ms) as E-stop; the host also sends an explicit "shutting down" tick (bit 31) on exit.
5. **Kill switch**: hardware first (the actuator controller's E-stop; Thanos / SMC3 park on data loss [forum], which
   is exactly the behaviour to rely on), software second: a host hotkey (`Pause`) and a UDP command on the control
   port that forces neutral and stops sending; the pause key is also the test for the ramp.
6. **Startup**: the host sends neutral for 2 s before live data; the first live second is scaled 0 -> 1.
7. **Cue caps** (explosion 1/d^2 is unbounded at d -> 0: cap at `cue_max`), and a **cue budget**: at most one
   impact cue per 150 ms, max of overlapping cues, not sum (pad rule from the architecture, reused).
8. **Config lints** on load: a rig file that widens a clamp, a target with `frame` unknown, a port collision between
   two targets with different formats (4123 is shared by SimTools-classic and FlyPT-pack2: only one can listen; the
   script already warns), `interp` with an output rate below 2x the step rate.
9. **Never on the daily driver**: the host's game-dir resolution and refusal rule from the architecture (3.4) apply;
   motion tests use the lab sandbox or replays.

---

## 7. Config: `rigs/*.json` and `motion/targets.json`

```json
// tools/haptics/motion/targets.json
{ "output_hz": 100, "resample": "interp",
  "targets": [
    {"name": "flypt",   "format": "lfs-pack2", "host": "127.0.0.1", "port": 4123,  "id": 1, "frame": "world", "gauge_port": 4124},
    {"name": "simtools","format": "lfs-classic","host": "127.0.0.1","port": 4123,  "id": 0, "frame": "world", "gauge_port": 4124, "enabled": false},
    {"name": "simhub",  "format": "lfs-pack2", "host": "127.0.0.1", "port": 63393, "id": 0, "frame": "world", "gauge_port": 63392},
    {"name": "simhub-forza", "format": "forza-dash", "host": "127.0.0.1", "port": 5300, "enabled": false},
    {"name": "native",  "format": "i76motion", "host": "127.0.0.1", "port": 7677}
  ] }
```

```json
// tools/haptics/rigs/desk-virtual.json  (motion section; the shaker / pad / wheel sections are the architecture's)
{ "motion": {
    "accel_source": "integrator", "airborne_zero_physics": true, "hold_lp_hz": 8,
    "cues": {"impact_gain": 1.0, "impact_tau_ms": 60, "explosion_gain": 40.0, "explosion_tau_ms": 120,
             "landing_k": 1.0, "landing_tau_ms": 80, "shot_recoil": 0.0, "cue_max": 60.0, "min_gap_ms": 150},
    "surfaces": {"0": 0.0, "2": 0.1, "default": 0.3},
    "safety": {"clamp_udp": false, "stale_ms": 250, "neutral_ramp_ms": 1000, "max_jerk": 400, "cue_budget": "max"},
    "washout": {"enabled": false, "hp_hz": 0.4, "zeta": 0.7, "tilt_lp_hz": 0.3, "tilt_rate_dps": 3.0,
                "tilt_max_rad": 0.25, "rot_hp_tau_s": 1.5, "k_t": 0.3, "k_r": 0.5} } }
```

Migration rule from the architecture (diff after a bulk merge): the five `Motion` fields of `Mix-Update` and the
port map of `ffb-telemetry-udp.ps1` are carried into these files by `design/migrate_tune.py --motion`, and the
diff is printed per key.

---

## 8. Phased build plan (for the implementation agent) and owner test list

Phases M0-M3 need no game and no hardware; `tools/ffb/ffb-telemetry-udp.ps1` stays until M1 passes its ported
assertions. Each milestone: files, exit test.

| # | milestone | files | exit test |
|---|---|---|---|
| M0 | Research sanity: fetch `LFS\docs\OutSimPack.txt` (install LFS demo or read a mirror) and record the AngVel axis labels and the world / body statement in this doc's 3.1 note; read the Forza official doc when reachable; nothing else | this file | the two "unknown" notes in 3.1 / 3.2 become cited facts or stay marked |
| M1 | `Core/Motion/Derive.cs`, `Resample.cs`, `Cues.cs`, `Safety.cs`; `Renderers/Udp.OutSim.cs` with pitch / roll / position / rpm / gear / inputs / wheels filled (3.1); `motion/targets.json`; `tests/motion-test.ps1` | `tools/haptics/src/Core/Motion/*.cs`, `src/Renderers/Udp.OutSim.cs` | the 21 ported layout assertions + the golden tests of 5.4 pass; `make_synthetic.py` scenarios 1-6 produce the expected tables; `i76motion.py --sniff` decodes the stream |
| M2 | `Renderers/Udp.Forza.cs` (Sled 232 / Dash 311), `Renderers/Udp.I76Motion.cs` (144), `schema/i76motion.json`, `i76motion.py --check/--plot`, `motion_preview.html` | | sizes 232 / 311 / 144 exact; field offsets asserted from the schema; `--plot` of scenario 1 shows surge -9.5 and pitch -3.3 deg; preview tilts nose-down |
| M3 | Desk benches: FlyPT 5.1 and SimHub 5.2 against the synthetic replays; write `docs/records/MOTION-BENCH-<date>.md` with screenshots and the Mover source names | | Mover source green, 3D rig pitches on braking, heave on landing only; SimHub Forza entry reads gear / speed / rpm right; one frame setting (world / body) chosen with the evidence written down |
| M4 | Optional consumers: SimHub `.simdef` for `i76motion`; `Udp.OpenGameTelemetry.cs` (260 B); SimTools plugin from the LFS_V3 template if licensed | | SimHub Telemetry Receiver Tester accepts; OGT sniffed at 260 B |
| M5 | Proxy v3 motion fields of 4.2 (`step_total`, `wheelbase`, `surface_bump_amp` first), build to a scratch path, not deployed | `music-fix/strlkproxy.c`, `tools/telemetry/i76tel.h`, `i76tel.py` | `i76tel.py --layout` regenerates; pristine byte patterns match statically |
| M6 | `Motion.Washout` + `--washout-plot`; `Actuator.Direct` skeleton that drives **nothing** (logs commands) | | step / sine response plots match the configured corner frequencies; neutral ramp timing test; E-stop command test |

**Owner console tests** (lab sandbox, `I76_TELEMETRY=1`; A/A before A/B; report n):

| # | what to install / do | what to look at | settles |
|---|---|---|---|
| T1 | nothing new: `haptics.ps1 -Motion native` + `i76motion.py --sniff --plot` while driving t01: launch, full brake, a corner, the T06 ramp (aaramp5), a wall | the plot: surge negative under braking (~-9.5), pitch nose-down (~-3 deg), heave spike only at landing, impact spike on the wall; the status bits; packet rate steady | sign conventions of `accel_body` (audit row 5) and of pitch / roll; whether airborne writes gravity into `accel` |
| T2 | FlyPT Mover installed (free); LFS source; 6DOF virtual rig; 3D view on the second screen | the virtual rig while driving the same route; does braking pitch nose-down independent of heading | frame setting world / body for format A |
| T3 | SimHub installed; LFS game selected; motion 3D preview; then switch to Forza Motorsport 7 + `-Motion simhub-forza` | gauges: speed / rpm / gear match the HUD; preview motion sensible; ShakeIt preview with audio muted | Forza gear encoding, SimHub port, pack2 wheel order |
| T4 | A/A: two identical braking runs, then A/B `interp` vs `hold` | Mover graphs: staircase vs smooth; felt nothing (no hardware); latency of the pitch onset in the plot | resample default for this rig class |
| T5 | latency: fire one shot and ram one wall with `i76motion.py --sniff` logging host receive times; compare the IMPACT event frame time against the cue packet time | event-to-packet ms | the motion row of the latency budget |
| T6 | explosion reach: an AI car blows up near and far (backlog P4-20 shares the sitting) | cue_heave vs distance | `explosion_gain`, `cue_max` |
| T7 | (hardware later) the owner's controller: Mover output module for it, host still only sending raw UDP; E-stop in reach; `stale_ms` test by killing the host mid-drive | the rig ramps to neutral over 1 s, not a step | the safety section works on the real thing |

---

## 9. Open questions (stated so nobody fills them with a guess)

- LFS OutSim: world or car-local vectors; AngVel axis labels (M0).
- Forza: official units and gear encoding (official doc returned 403); SimHub's Forza port.
- FlyPT Mover 3.7: exact LFS source output names; whether a custom UDP source (offset + float) exists in the shipped
  build; whether it accepts classic 64 as well as pack2.
- SimHub `.simdef` port and binary header (only in generated code).
- Which motion rig and controller the owner will buy (memory: ASR Pro / TR160 V5 / Sim-Lab cockpit first); whether
  its controller has a Mover output (Thanos / SMC3 / ODrive do) or needs `Actuator.Direct`.
- Engine: does the airborne branch write gravity into `ent+0xd4`; the field layout of the contact record at
  `entity+0x38`; the wheel radius field; the WRLD bump amplitude row base.
- Sigma / D-BOX: no custom telemetry route without a vendor SDK; nothing to build until a contact says otherwise.
- Pitch / roll sign expectations of each consumer (settled by the braking test, T1-T3).

---

## Sources

Repo: `docs/engine/HAPTICS-ARCHITECTURE.md` (host, renderers, event schema, phases), `docs/engine/FFB-DESIGN-LIBRARY.md` 6
(washout, tilt 3 deg/s, raw SI, 60 Hz baseline), `docs/records/MOTION-SIM.md` (2026-07 note, superseded parts
marked in FFB-DATA-AUDIT row 11), `docs/records/FFB-DATA-AUDIT.md` rows 4-5 (orientation, body-frame acceleration),
`docs/records/FFB-DEEP-DIVE.md` (block +0xf0 force vector), `tools/telemetry/i76tel.h`, `README.md`,
`verification-2026-10-01.txt`, `tools/ffb/ffb-telemetry-udp.ps1` (port map, OutSim / OutGauge builders, 21
assertions), `tools/ffb/FfbMixer.ps1` (`Motion` bus), `tools/ffb-udp-listen.py`, `music-fix/README.md`
(`I76_FIXED_STEP`, `I76_RENDER_INTERP`). Map: `<re-archive>\subsystems\physics.md` (substep pipeline,
`ent+0xd4` integrator acceleration and the 9.51 m/s^2 brake figure, angular rates +0xc8/+0xcc/+0xd0 and the
attitude model's lift targets and 0.5 s easing, weight-transfer 0.008 m per m/s^2 and the dive pitch, suspension
IIR pole 0.7 / travel +-0.25 r, airborne pitch -pi/20, `veh+0x474`, `veh+0x46c`, contact record at entity+0x38),
`framerate.md` (stock 46.9 / 31.2 ms steps).

Web, this pass: FlyPT Mover [site](https://www.flyptmover.com/), [games sources](https://www.flyptmover.com/mover-3-5/sources/games),
[FAQ category](https://www.xsimulator.net/community/faq/flypt-mover.29/category), forum posts
[216401](https://xsimulator.net/community/goto/post?id=216401), [207567](https://xsimulator.net/community/goto/post?id=207567),
[215734](https://xsimulator.net/community/goto/post?id=215734), [247687](https://www.xsimulator.net/community/goto/post?id=247687);
SimHub [motion](https://www.simhubdash.com/?p=2326), [external sim integration](https://manual.simhubdash.com/external-sim-integration);
SimTools [page](https://www.xsimulator.net/simtools/), forum [234974](https://xsimulator.net/community/goto/post?id=234974),
[111288](https://www.xsimulator.net/community/goto/post?id=111288), [245545](https://xsimulator.net/community/goto/post?id=245545);
LFS [OutSim](https://en.lfsmanual.net/wiki/OutSim), [OutGauge](https://en.lfsmanual.net/wiki/OutGauge),
[InSim.txt](https://en.lfsmanual.net/wiki/InSim.txt); Forza [FM Data Out (403 here)](https://support.forza.net/hc/en-us/articles/21742934024211-Forza-Motorsport-Data-Out-Documentation),
[FH6 Data Out](https://support.forza.net/hc/en-us/articles/51744149102611-Forza-Horizon-6-Data-Out-Documentation),
[geeooff/forza-data-web](https://github.com/geeooff/forza-data-web) (`Core/ForzaSledDataStruct.cs`, `Core/ForzaCarDashDataStruct.cs`);
Codemasters [F1 2020 spec](https://f1-2020-telemetry.readthedocs.io/en/stable/telemetry-specification.html);
BeamNG [protocols](https://docs.beamng.com/modding/protocols/); SimXperience [Open Game Telemetry](https://www.simxperience.com/slides/slide/sim-commander-api-sdk-open-game-telemetry-100);
Simucube [Tuner LFS](https://docs.simucube.com/TunerSoftware/games/LFS.html); D-BOX [HaptiSync API](https://support.d-box.com/en/knowledge/d-box-haptisync-api),
[BeamNG](https://support.d-box.com/knowledge/how-to-activate-d-box-haptic-in-beamng), [Condor 2](https://support.d-box.com/knowledge/activate-haptics-condor-2);
Sigma [review](https://overclocking.com/test-sigma-integrale-dk6-et-dk2-le-tueur-de-d-box/3/); Qubic [docs](https://docs.qubicsystem.com/docs/software/qubic-manager/),
[2.173](https://qubicsystem.com/2025/12/qubic-manager-new-version-2-173/); NLR [Platform Manager](https://support.nextlevelracing.com/hc/en-us/articles/16165035123471-Platform-Manager-Onboarding);
Thanos [Tindie](https://www.tindie.com/products/Tronicgr/amc-aasd15a-servo-motion-controller/), [overtake](https://www.overtake.gg/threads/thanos-amc-aasd15a-6axis-servo-motion-controller.168360/);
Yaw [forum](https://www.xsimulator.net/community/posts/237658).
