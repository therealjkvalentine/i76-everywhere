# Interstate '76 → home motion sim + wheel FFB

*The goal: I'76 in a 6DOF motion rig with wheel force feedback. This doc maps
our force-feedback tap ([FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md), `../ffb-shim/`) onto
the standard home-sim receiver stack, and states honestly what's built vs what a
rig run still needs. Written 2026-07-19; nothing here is hardware-verified yet.*

## The three consumers (they want different data)

A driving sim setup is really three independent effect systems. Conflating them
is the usual beginner trap:

| System | What it does | What it needs |
|---|---|---|
| **Motion platform (6DOF)** | tilts/heaves the whole rig | vehicle **acceleration + orientation** → surge/sway/heave/roll/pitch/yaw, via washout ("motion cueing") filters |
| **Wheel FFB** | torque on the steering wheel | the game's **steering force** (centering, road feel, kicks) |
| **Tactile / bass shakers** | buzz from events | discrete **events**: RPM, impacts, gear, road surface, wheelspin |

Our i7_SFRCE.dll stream feeds all three *partially* — see the mapping below.

## The industry-standard receivers (their testers ARE the visualizer)

- **SimTools** (xsimulator.net) — the de-facto DIY 6DOF standard. A *game plugin*
  extracts telemetry; SimTools converts it to your actuator axes and ships an
  **Output Testing / axis monitor** — move each DOF, set min/max/smoothing live.
  Old/obscure games are supported by writing a plugin; I'76 would be one.
- **SimHub** — dashboards + **ShakeIt bass-shakers** (tactile) + some motion,
  with a big plugin SDK and many live gauges that double as a test harness.
  ShakeIt's "effect from game event" model is conceptually identical to what our
  shim already does for pad rumble.
- Both ingest **UDP**; both have built-in visualizers. So the right architecture
  is *emit standard UDP telemetry and let their tools be the visualizer* — which
  is exactly what the shim now does (see below), rather than a bespoke window.

6DOF vocabulary everything speaks: **surge / sway / heave** (linear) +
**roll / pitch / yaw** (angular).

## What our tap provides today (the shim UDP stream)

`../ffb-shim/` sends one key=value datagram per sim tick to `127.0.0.1:17676`
(and writes the same line to `C:\AutoHotkey\ffb-state.txt`). Fields and their
motion-sim role:

| field | source | feeds |
|---|---|---|
| `fx1000` | body-frame force X ÷1000 | **surge** (longitudinal G proxy) + wheel FFB longitudinal |
| `fy1000` / `fy2_1000` | body-frame force Y ÷1000 | **sway** (lateral G proxy) + wheel FFB centering/kick |
| `spd10` | speed ÷10 (mph) | scales road/engine tactile; a surge reference |
| `surf` | terrain id (+1) | road-texture tactile (ROCKY/DIRT/PAVED…) |
| `run` / `pitch` | engine running + pitch | engine-rumble tactile |
| `skid`/`slide`/`air`/`oil` | vehicle state bits | traction-loss / airborne motion + tactile cues |
| `tires` | 4× tire status | flat-tire/blowout tactile |
| `fire` / `gain` | per-hardpoint weapon fire | weapon-recoil tactile |
| impact events (`ffb-events.txt`) | ordnance/collision/concussion, **direction + damage** | impact jolts (both motion and tactile), directional |
| `low100`/`high100` | our mixed rumble output | the pad-rumble result (for reference) |

**Good enough right now for:** wheel-ish centering/kick, all tactile/bass-shaker
effects, and a *2-axis* motion tease (surge+sway from the force vector).

**Not in the stream — needed for true 6DOF:** heave, roll, pitch, yaw come from
the vehicle's **orientation matrix + vertical**, which we already located in
memory: the entity transform at `entity+0x08` and speed candidate `entity+0x94`
([MEMORY-MAP-INDEX.md](MEMORY-MAP-INDEX.md) Tier 2). A small memory reader
(build on `i76-worldscan.ahk`) can emit those on the same UDP wire to complete
the DOF set. That's the next RE step for full motion.

## What's built (this session)

- **`../ffb-shim/`** — the tap. Activates FFB with no DirectInput device,
  drives XInput pad rumble, writes telemetry files, **and sends the UDP stream**.
- **`tools/ffb-udp-listen.py`** — a UDP listener: live text dashboard, `--raw`
  dump, or `--csv` recorder. Proves the wire with no rig, and stands in for
  SimHub until a plugin exists. (Wire verified loopback; not yet vs the game.)
- **`tools/i76-ffb-monitor.ahk`** — an in-prefix overlay reading the telemetry
  files: motor bars, force channels, state flags, last impact. The "watch it
  while you drive" tool; also the instant "is the shim even receiving?" check.

## What a rig run still needs (honest gaps)

1. **Field-run the shim** — confirm it loads and the stream is non-zero in a
   real mission (everything above is static-RE + loopback-verified only).
2. **A SimTools game plugin (or SimHub UDP plugin)** mapping our fields to axes.
   SimTools plugins are small .NET DLLs implementing its game interface; the
   parse is trivial (our format is plain key=value). Not built — it wants the
   real receiver installed to test against.
3. **The memory reader** for heave/roll/pitch/yaw (see above) if you want more
   than 2-axis motion.
4. **Platform reality:** wheel-FFB torque and motion realistically live on the
   **Windows box** — Wine-on-Mac has no DirectInput FFB backend, and rigs are
   driven by their own controller over UDP from a Windows host. Mac gets pad
   rumble + the monitor; the full 6DOF-plus-wheel endpoint is Windows.

## Wheel FFB, specifically

The shim receives the game's real steering force (`fx`/`fy` and the per-tick
force vector). To put actual **torque on a wheel**, that force has to reach a
DirectInput/wheel-driver effect — which means either (a) on Windows, keep the
*real* `i7_sfrce.dll` + an FFB wheel (authentic, already works — the shim is for
rumble/telemetry, not a replacement there), or (b) have a Windows build of the
shim re-emit the force as a DirectInput constant/spring effect to the wheel
while also sending telemetry. (b) is unbuilt and Windows-only. On the Mac, wheel
torque is not deliverable; pad rumble is the ceiling.
