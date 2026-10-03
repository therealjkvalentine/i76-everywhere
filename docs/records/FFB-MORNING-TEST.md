# FFB rumble — morning field test & tuning sheet

*Everything's built, verified as far as it can be without you driving, and
deployed. This is the end-to-end test + how to dial the feel. Driving feel is
the priority. Written 2026-07-19 overnight.*

## First: relaunch the game

The latest rumble build is deployed to the prefix but the *running* game still
has the older DLL loaded. **Quit and relaunch Interstate '76** so it loads the
full mixer. (The keys-only rumble is already gated off — the shim owns the pad.)

## What's active

- **Force-feedback-data rumble** (`ffb-shim/`, i7_sfrce.dll) — ON. Drives the pad
  from the game's real physics stream: wheel slip, road, engine, weight,
  impacts, landings, tyre blowout, weapon fire. This is what you're testing.
- The **sound-based backup** (`sound-rumble/`) is built but NOT installed (the
  two would fight). To A/B it later: `ffb-shim/install.sh --revert` then
  `sound-rumble/install.sh` — see that folder's README (it's experimental).

## Watch the telemetry while you drive (optional but great for tuning)

The shim writes a live line to (Mac path):
`~/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app/Contents/SharedSupport/prefix/drive_c/AutoHotkey/ffb-state.txt`

- Quickest: `tail -f "<that path>"` in a terminal, or
- `python3 tools/ffb-udp-listen.py` on the Mac (the shim also UDP-casts to
  127.0.0.1:17676; the dashboard shows WHEEL SLIP + the effect breakdown), or
- the in-prefix overlay `tools/i76-ffb-monitor.ahk`.

Key fields: `pad=` (which controller slot — see below), and the effect
breakdown `eng road weight slip wpn jolt` + final `low100 high100` (the two
motor levels, 0-100).

## The one thing that can kill it: pad slot

If you feel **nothing at all**, check `pad=` in the telemetry. `pad=-1` means no
controller was found (connect the pad, it re-scans every ~1s). `pad=0..3` is the
slot it's driving. The shim now scans 0-3 (it used to hardcode 0), so this should
just work — but if `pad=` shows a number and you still feel nothing, that's the
thing to flag.

## Drive test — what you should feel

| Do this | Expect | Telemetry |
|---|---|---|
| Sit still, engine on | near-silent (faint idle at most) | low/high ~0 |
| Cruise straight | a light texture floor, not a constant heavy buzz | high ~14, low ~0 |
| **Corner hard until the tyres break loose** | **strong grind (left) + skid chirp (right) — the star effect** | slip jumps to ~100, low ~85 |
| Brake/accelerate hard | a subtle load swell (gentle on a pad) | weight rises |
| Hit something / get shot | a sharp jolt that then fades | jolt spikes |
| Jump and land | a thump scaled by how fast you landed | jolt spike on landing |
| Fire a weapon | a buzz on the small motor, distinct per weapon | wpn on high |
| Blow a tyre | an ongoing drag on the heavy motor | slip ~12, low ~28 |

The design (per `docs/SIM-RUMBLE-RESEARCH.md`): continuous stuff stays quiet so
**events read on top**; wheel slip is the loud one. If cruising feels too buzzy,
or skid isn't strong enough, that's tuning — below.

## Tuning — every knob is one line in `ffb-shim/i7ffshim.c`

All feel constants are in the `RUMBLE TUNING` block near the top. Edit, then
`ffb-shim/build.sh` and `cp ffb-shim/I7_SFRCE.DLL "<game dir>/i7_sfrce.dll"`
(or re-run `ffb-shim/install.sh`), relaunch.

| Symptom | Knob | Direction |
|---|---|---|
| Skid not strong enough | it's already near max; raise `R_DEADZONE`→`0.34` so it hits harder | ↑ |
| Cruise too buzzy (road) | `R_ROAD_FLOOR` (0.14) | ↓ toward 0.08, or 0 to kill road |
| Want more road connection | `R_ROAD_FLOOR` | ↑ toward 0.30 (felt buzz) |
| Engine hum too much/little | `R_ENGINE_IDLE` / `R_ENGINE_REV` | ↕ |
| Weapons too weak/strong | `R_WEAPON` (0.34) | ↕ |
| Impacts too soft | the `impacts()` divisor `R_IMPACT_NORM` (220) | ↓ = stronger |
| Landings too soft/harsh | `R_LAND_MAX` (0.85) | ↕ |
| Everything feels weak (dead-zone) | `R_DEADZONE` (0.28) — the floor events get lifted to | ↑ if your pad's motors are weak |
| Cornering-load cue too subtle | `R_WEIGHT_MAX` (0.12) | ↑ (gamepad ERM limits how subtle this can be) |
| False rumble in gentle corners | `R_TH_EVENT` (0.05) slip threshold | ↑ |

Surface-specific road feel (dirt rougher than pavement) is a known TODO — the
`surf=` id → texture mapping isn't tuned yet; the telemetry `surf=` values you
see while driving on different ground are what pins it.

## If something's wrong

- **No telemetry file** after relaunch → the game didn't load the shim. Confirm
  `i7_sfrce.dll` in the game dir is ~20KB (ours), not 82KB (original).
- **Telemetry frozen** (tick not advancing) → you're paused / in a menu; it
  resumes when driving.
- **Rumble fights itself** → the remap layer's rumble should be off
  (`gShimOwnsRumble := true` in i76-remap.ahk); it was deployed, but if you
  re-ran the input-remapper setup it may have overwritten the live copy.

Revert the whole FFB experiment anytime: `ffb-shim/install.sh --revert`.
