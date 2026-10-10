# tools/haptics/motion - motion simulator output and its desk bench

The motion half of the haptics host ([docs/MOTION-OUTPUT.md](../../../docs/MOTION-OUTPUT.md), phases M0-M3). The host turns
the game's telemetry into the UDP formats motion software already reads, so FlyPT Mover, SimHub or SimTools can drive a
virtual (and later a real) rig from Interstate '76. Nothing here installs anything, launches the game or drives an
actuator: the host only sends UDP to software on this PC, and only when you ask it to (`--send` / `--live`).

```
 i76tel (UDP 7676 / shm / .i76rec)  ->  core (VehicleState)  ->  Motion.Udp renderer                 ->  127.0.0.1
                                                                  MotionCore: derive once per physics      flypt   LFS OutSimPack2 :4123 (ID 1) + OutGauge :4124
                                                                  state, cues, 24 Hz -> 100 Hz,            simhub  LFS OutSimPack2 :63393 + OutGauge :63392
                                                                  fail-to-neutral, status word             simtools LFS OutSim classic :4123 (ID 0)  [off]
                                                                                                           simhub-forza Forza Dash 311 B :5300       [off]
                                                                                                           native  i76motion 144 B :7677
```

## Files

| file | what |
|---|---|
| `targets.json` | where each format goes (port, ID, frame world / body); `enabled: false` targets are sent only when named with `--targets` |
| `make_synthetic.py` | writes `replays/synth-<scenario>.i76rec` (i76tel v3 frames: 24 Hz fixed-step physics rendered at 60 fps) + `synth-<scenario>.expect.json` |
| `i76motion.py` | validator: `--decode`, `--check` (conformance + a scenario's expected table), `--plot` (static HTML), `--preview`, `--sniff` |
| `motion_preview.html` | three.js (r128, cdnjs) view of a packet log: the car posed by the packets, and a generic platform with a preview washout |
| `plot.template.html` | the `--plot` page |
| `test_motion.py` | Python tests (run by `haptics.ps1 test`) |
| `../schema/i76motion.json`, `../schema/motion-wire.json` | byte layouts of all six formats; the C# tests assert the encoders against them, the validator decodes with them |
| `../src/Haptics/Core/Motion/` | MotionCore: `MotionDerive`, `Resample`, `Cues`, `Safety`, `MotionConfig` |
| `../src/Haptics/Renderers/` | `Udp.OutSim.cs`, `Udp.Forza.cs`, `Udp.I76Motion.cs`, `MotionUdpRenderer.cs` (`Motion.Udp`) |
| `../rigs/desk-t300-evo4.json` | `motion` section (cues, safety, surfaces) and the `motion_udp` output |

## Commands

```powershell
tools\haptics\haptics.ps1 motion braking --check            # one scenario -> packet logs in tools\haptics\out\motion, checked
tools\haptics\haptics.ps1 motion all --check                # all seven scenarios
tools\haptics\haptics.ps1 motion braking --targets flypt --send                # real time, UDP to FlyPT Mover's LFS source
tools\haptics\haptics.ps1 motion all --targets flypt,native --send             # every scenario back to back
tools\haptics\haptics.ps1 motion jump --targets simhub --send --repeat 5        # loop 5 times (1.5 s of silence between passes:
                                                                                #  the rig ramps toward neutral at each seam)
tools\haptics\haptics.ps1 motion replays\t01-c1.i76rec --targets flypt --send  # a recorded session (owner test 8 records one)
tools\haptics\haptics.ps1 motion synthetic --targets native                     # the 20 s haptics demo session
tools\haptics\haptics.ps1 live --source udp --sinks motion-udp --live           # the running game -> the enabled targets
python tools\haptics\motion\i76motion.py --plot tools\haptics\out\motion\synth-braking.native.i76motion.i76rec braking.html
python tools\haptics\motion\i76motion.py --preview tools\haptics\out\motion\synth-jump.native.i76motion.i76rec jump.html
python tools\haptics\motion\i76motion.py --sniff --port 7677 --seconds 30       # only when nothing else holds the port
```

Scenarios (`python make_synthetic.py --list`); the host holds every channel at neutral for 2 s after the first data and
ramps in over 1 s, so motion starts at t = 3 s:

| scenario | script | what the outputs must do |
|---|---|---|
| `braking` | 25 m/s at heading 30 deg, full brake from 5.0 s to a stop at ~7.6 s | surge -9.5 m/s^2, pitch -3.2 deg (nose down) during the stop; no sway / heave; both back to 0 after |
| `accelerating` | parked, +4 m/s^2 from 4 to 9 s | surge +4, pitch +1.35 deg (squat), throttle 1 |
| `turn` | 20 m/s, right turn 4.5-7 s (0.4 rad/s), left 7.5-10 s | sway +8 then -8 (toward the turn centre), yaw rate +0.4 / -0.4, roll -4.6 deg then +4.6 (body leans out) |
| `crest` | 20 m/s, light hop at 5.0 s (~0.4 s airborne) | physics channels 0 while airborne, a ~1.6 m/s^2 heave cue at touchdown |
| `jump` | 25 m/s, 1.2 s airborne from 5.0 s, lands at v_y -5.9 m/s | nothing in flight (free flight is flat), nose drops toward -9 deg, one ~6 m/s^2 heave cue at 6.2 s |
| `impact` | 15 m/s into a wall at 5.0 s, explosion 6 m to the right at 7.5 s | surge cue ~-50..-60 m/s^2 decaying in ~0.2 s; then a small heave cue and a push to the left |
| `dropout` | steady right turn, telemetry silent 5-7 s | full output to 5.25 s, then a 1 s ramp to neutral (status bit 5), ramp back up after 7 s |

## Sign conventions (all formats derive from these)

i76motion, schema/i76motion.json: surge + forward, sway + right, heave + up, m/s^2, **gravity excluded** (a parked car
reads 0; a slope reaches the rig through pitch / roll); roll + right side down, pitch + nose up, yaw + turning right
(aerospace body convention); heading clockwise from above. Physics and **cue** channels are separate (cues = impacts,
landings, explosions only).

* **LFS OutSim / OutSimPack2**: X right, Y forward, Z up. Accel = (sway, surge, heave) incl. cues; AngVel = (pitch rate,
  roll rate, -yaw rate) and Heading = -heading, because LFS angles are anticlockwise-positive. `frame: world` (default)
  rotates Accel / Vel / AngVel into LFS world axes, `frame: body` leaves them car-local (see M0 below).
* **Forza Data Out**: car-local X right, Y up, Z forward. Acceleration = (sway, heave, surge) incl. cues, AngularVelocity
  = (pitch, yaw, roll) rates, Yaw / Pitch / Roll = heading / pitch / roll, with the i76motion signs. Forza's own sign
  convention is not documented anywhere reachable: owner test T3 checks it in SimHub. IsRaceOn = 0 while neutral.
* **OutGauge**: speed, rpm, gear (LFS encoding = i76tel's: 0 R, 1 N, 2 = 1st), pedals, `I76 ` car tag, the weapon name
  in Display1; lights: shift > 6000 rpm, neutral, engine damage < 50 %.

Honest accounting (the rule of the old ffb-telemetry-udp.ps1, kept): what the engine does not have is zero - tyre forces,
temperatures, clutch, fuel, lap data, steer torque. Wheel slip is 0 / 1.5 from the skid flags (no tyre model).

**M0 (2026-10-10).** `LFS\docs\OutSimPack.txt` could not be fetched (not on the LFS manual wiki, the forum threads are
login-gated). The InSim.txt mirror gives the classic field list but says nothing about frames. A search summary of
the LFS developer's answer in the U9 OutSimPack thread says OutSim velocities and accelerations are **world** frame
(rotate with the Euler angles for car frame); no statement on AngVel. So `frame` stays a per-target option, default
`world`, and owner test T2 (braking must pitch the virtual rig nose-down at any heading) decides. Forza's official
page still returns 403: Forza signs and gear encoding stay unverified (T3).

## Desk bench 1: FlyPT Mover (free, the primary bench)

Owner installs; the agents do not. No hardware, no game, nothing in the game folder.

1. Download FlyPT Mover 3.5 (stable) or 3.7 beta from <https://www.flyptmover.com/> (downloads page; free for personal
   home use, no account). Unzip it anywhere outside the game folders and run `Mover.exe`.
2. **Source**: add the **Live For Speed** game source (Sources > Games > Live For Speed). Settings: OutSim port **4123**,
   ID **1**, OutGauge port **4124** (Mover's defaults for this source; it expects LFS `OutSim Mode 2, Delay 1,
   IP 127.0.0.1, Port 4123, ID 1, Opts 1ff`, i.e. OutSimPack2, which is what the `flypt` target sends).
3. Start the bench stream in a console:
   `tools\haptics\haptics.ps1 motion all --targets flypt --send` (all scenarios, ~70 s), or one scenario on repeat:
   `tools\haptics\haptics.ps1 motion braking --targets flypt --send --repeat 10`.
   The source should go green / connected while packets arrive (yellow = port open, no data: check the ID is 1 and that
   no other program, e.g. SimTools, holds 4123; red = not running).
4. **Rig**: add a rig of type **6DOF / linear hexapod** (any actuator lengths, e.g. stroke 100 mm). No output module is
   needed. Open its **3D view** (it moves with nothing connected).
5. **Pose**: in the rig's pose / motion setup map surge <- the source's longitudinal acceleration (LFS Y), sway <-
   lateral (X), heave <- vertical (Z), yaw <- angular velocity Z, pitch / roll <- the pitch / roll angles (and / or
   angular velocity X / Y). Leave Mover's default filters: they are the cueing. Write down the exact names Mover uses
   for these outputs (an open question of the design, section 9).
6. Watch the 3D rig through the scenarios (times from the start of each scenario; neutral for the first 3 s):
   * braking 5.0-7.6 s: the platform pitches **nose-down** (and surges forward if mapped), returns when stopped;
   * accelerating 4-9 s: nose-up;
   * turn: 4.5-7 s leans so you are pushed **left** (outward of a right turn), 7.5-10 s the other way, with yaw;
   * crest ~5.4 s: a small heave kick; jump: **still** in flight (5-6.2 s), one heave kick on landing;
   * impact 5.0 s: one sharp surge jolt; 7.5 s a small kick from the explosion;
   * dropout: settles to neutral smoothly over 1 s at ~5.3 s and comes back after 7 s (no jump).
7. If the braking pitch is nose-up, or changes with the car's heading (the braking scenario runs at heading 30 deg; a
   world/body mix-up shows as pitch AND roll during straight-line braking), set `"frame": "body"` on the `flypt` target
   in `targets.json` and repeat. Record which setting worked (owner test T2).
8. Optional, if your Mover build has a custom / generic UDP source (offset + float32 per field): point it at port 7677
   and enter the i76motion offsets from `schema/i76motion.json` (surge +20, sway +24, heave +28, roll rate +32, pitch rate
   +36, yaw rate +40, roll +44, pitch +48, heading +52, cue surge / sway / heave +116 / +120 / +124), then
   `haptics.ps1 motion all --targets native --send`.

## Desk bench 2: SimHub (free core; motion add-on runs time-limited sessions without a licence)

1. Install SimHub from <https://www.simhubdash.com/> (the owner does this).
2. Game: **Live for Speed**. SimHub's LFS page asks for OutSim on **63393** and OutGauge on **63392**, Opts 1ff: the
   `simhub` target sends exactly that. Run `tools\haptics\haptics.ps1 motion all --targets simhub --send`.
3. Check the telemetry: speed, rpm, gear (gear 2 = 1st in LFS encoding should show as 1st), pedals, and the
   acceleration / orientation properties (Settings / *Available properties*, or a telemetry dashboard in Dash Studio).
4. **Motion** tab (motion add-on): add a generic 6DOF or 2DOF profile, open the **3D preview**, play the scenarios; the
   expectations are the same as Mover's step 6. The effect analyzer records the telemetry SimHub received.
5. **ShakeIt** (optional): preview RPM / speed / gear-shift / wheel-slip / road effects with **no audio device** selected,
   or the EVO 4 only when you are at the desk (audio may be muted by the agents: `i76-uncap-lab\tools\mute.ps1 -Off`).
6. **Forza check**: switch the game to **Forza Motorsport 7**, read the UDP port SimHub shows for it (5300 assumed in
   `targets.json`; change `simhub-forza.port` if different) and run
   `tools\haptics\haptics.ps1 motion all --targets simhub-forza --send`. Gear / speed / rpm must match the scenario
   (gear byte uses the i76tel encoding: 2 = 1st; if SimHub shows one gear too many, note it - owner test T3), and
   braking must show as deceleration.

## Desk bench 3: SimTools (only if licensed)

SimTools v3 still reads LFS natively, but **its free DIY licence was discontinued in May 2026** (xsimulator.net), so it
needs a paid licence (simtools.us). If the owner has one: Game Engine > Interface Settings, add a **Network** interface
to 127.0.0.1:6123 (any unused port; the game plugin is not called without an interface); fill the **Default** Axis
Assignments profile; Output Testing > Virtual Axis while `tools\haptics\haptics.ps1 motion all --targets simtools --send`
sends OutSim classic 64 B to 4123, ID 0. FlyPT and SimTools share 4123 in different formats: close Mover first. The
Tuning Center min / max per DOF is a second check of our ranges. Known pitfall: Virtual Axis sliders that do not move
with the plugin "running" [forum, no fix documented].

## Our own checks (no third-party software)

```powershell
tools\haptics\haptics.ps1 motion all --check                       # every scenario's expected table, files only
python tools\haptics\motion\i76motion.py --check tools\haptics\out\motion\synth-braking.*.i76rec   # conformance of every stream
```
`--sniff` proves what actually goes over the wire: it binds the ports itself, so run it **instead of** the consumer, e.g.
`python tools\haptics\motion\i76motion.py --sniff --port 4123 --port 4124 --seconds 20 --then-check` in one console and
`haptics.ps1 motion braking --targets flypt --send` in another. Measured here (2026-10-10, n = 1, desktop busy):
1000 i76motion packets at 100.3 Hz, interval p50 10.0 / p95 10.1 ms, no seq gaps; the sniffed braking log passes the
braking table.

## Safety (docs/MOTION-OUTPUT.md 6) - what is enforced now

* **Fail-to-neutral**: no new physics state for 250 ms (or player absent / destroyed, or the 2 s startup hold) ramps every
  kinematic channel to 0 over 1 s, never a step; status bit 5 set; recovery ramps back. Live, the stale clock is the
  host's stopwatch, so a crashed or paused game still ramps.
* **Status word** on every i76motion packet; Forza IsRaceOn = 0 while neutral; LFS has no flag (it carries the ramp).
  A last packet with bit 31 (shutdown) and zero motion is sent on exit / Ctrl+C.
* **Clamp / slew**: implemented (3 g steady, 6 g cues, 2 rad/s, 0.35 rad; 400 m/s^3, 20 rad/s^2) but **off** for software
  targets (`"clamp": true` / `"slew": true` per target, or `safety.clamp_udp`). A rig file may tighten, never widen
  (lint error).
* **Loopback only**: a target host other than 127.x needs `"allow_remote": true` (lint error otherwise).
* **No actuator path exists.** A real rig is driven by Mover / SimHub outputs from these packets; a hardware E-stop on the
  controller comes first.

Live-loop note: `haptics.ps1 live` runs its loop every 4 ms, so 100 Hz motion packets leave on a 4 ms grid there
(8 / 12 ms spacing, 100 Hz on average). The replay `motion` command uses a 1 kHz grid (even 10 ms). If a consumer minds,
set `output_hz` to 125 in `targets.json` for live use.

## Stubbed / not built (and why)

* **M4** SimHub `.simdef`, Sim Commander Open Game Telemetry (260 B), a SimTools plugin: optional consumers; the
  `.simdef` contract is beta and its port / header exist only in SimHub's generated code. Not started.
* **M5** proxy v3 motion fields (`step_total`, `wheel_radius`, `surface_bump_amp`, ...): proxy work, out of this
  host's scope. Until then wheel radius (0.35 m), suspension travel and the surface texture table are rig constants.
* **M6** `Motion.Washout` and `Actuator.Direct`: only for a direct actuator path, which does not exist; every target is
  software with its own cueing. `washout.enabled: true` fails the lint instead of silently doing nothing.
* **Engine unknowns** the host works around: whether the airborne branch writes gravity into ent+0xd4 (physics channels
  are zeroed in flight); the contact impulse record (the a_diff residual becomes the impulse cue instead); the sign of
  the FFB block's accel_body and of yaw_rate (owner test T1).
* The landing cue uses the vertical speed of the **last airborne physics state**, which under-reads the touchdown speed
  by up to g x 1/24 s = 0.4 m/s.
