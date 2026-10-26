# I76 Debug (`tools/debug`) - the debug / cheat tool

**`DEBUG.bat` is the one entry** (console title "I76 Debug: debug / cheat tool"); `TRAINER.bat` is a one-line shim that
opens it on the Trainer tab, kept so old habits work. It ships in the daily driver as `DEBUG.bat` + `TRAINER.bat` at the
top and the code in `_tools\debug`, `_tools\trainer`, `_tools\telemetry`, so anyone who gets a release has it as a cheat
or debug tool.

A local web dashboard of everything the I'76 tooling knows while the game runs: frame rate and physics steps, live
telemetry charts and a map, every game event, the force-feedback wheel, pad rumble, the bass shakers (LFE), motion
output, collision and terrain counters from the proxy log, the trainer, and the log itself. It replaces the trainer
window: the trainer is the dashboard's Trainer tab.

Stdlib Python 3 (the same as the trainer needed), one HTML page with its own canvas charts (no libraries, no CDN, works
offline), dark theme. It serves `http://127.0.0.1:17690/` and nothing else.

## Launch

| how | what |
|---|---|
| `tools\debug\DEBUG.bat` | the dashboard; opens the browser on the Overview tab |
| `tools\trainer\TRAINER.bat` | `DEBUG.bat --tab trainer` (since 2026-10-20 a one-line shim; the old habit still works) |
| `DEBUG.bat --haptics` | also starts the haptics host so the Force feedback / Rumble / LFE / Motion tabs fill in (see "With the haptics host") |
| `python tools\trainer\i76trainer_gui.py` | the old tkinter trainer window, unchanged (`TRAINER.bat --classic` until 2026-10-20) |
| `python tools\debug\i76debug.py --help` | every option |

Options worth knowing:

* `--any` - the trainer may attach to a game that is not the lab sandbox copy (`<lab>\game`), as
  `TRAINER.bat --any` did. The tab's "allow non-sandbox game" box does the same while running.
* `--no-attach` - never open the game process: all the read-only panels work (they come from UDP, the log and the
  haptics host), the trainer is disabled.
* `--tab <name>` - open on `overview telemetry events ffb rumble lfe motion collision terrain trainer log`.
* `--log PATH` / `--game-dir DIR` - which `mciproxy.log` to follow. Default: beside the attached game, else beside any
  running `i76*.exe` (read-only), else the lab copy.
* `?poll=1` in the page URL polls `/api/state` instead of the event stream (for a proxy or a headless capture).

### Without the haptics host

Start the game with telemetry on (`I76_TELEMETRY=1`; `I76_SOUND_EVENTS=1` and `I76_DAMAGE_EVENTS=1` for the sound and
damage events), then `DEBUG.bat`. Overview, Telemetry, Events, Collision, Terrain / render, Trainer and Log fill in. The
Force feedback, Rumble, LFE and Motion tabs have no data of their own: their numbers only exist inside the haptics host
(`tools\haptics`), which `PLAY.bat` does not start. Since 2026-10-20 (owner: "not sure why no haptics host data in debug")
those tabs say exactly that and what to do (`debug_haptics.py`):

| what the tab finds | what it says / offers |
|---|---|
| the host is not found (a shipped folder has no `tools\haptics`; the owner's checkout `` is looked for, or `I76_HAPTICS_HOST`) | where it lives; Start |
| no wheel or pad (winmm joysticks - what the game reads - that answer `joyGetPosEx`, and XInput pads) | "nothing for the host to drive"; **Start anyway (dry run)** |
| a wheel / pad (listed by name) | **Start haptics host**, and a "drive the devices (--live)" box (asks first) |
| the host was started here | its pid, dry run or live, uptime, the last log lines while it waits for its first datagram; **Stop it** |
| it exited | the exit code and the last log lines |
| no telemetry from the game | a note: start the game with `I76_TELEMETRY=1`, else the host has nothing to work on |

Start runs `i76haptics.exe live --source udp --port 17676 --debug-udp 127.0.0.1:<--haptics-port>` (or `haptics.ps1 live
...`, which builds it, when the exe is not built), and the dashboard starts forwarding every telemetry datagram to 17676
at that moment. **Dry run by default**: the host computes everything the tabs show and drives nothing (its file outputs
go to `%TEMP%\i76debug-haptics`, overwritten at every start), because a wheel must not get two force sources (the game's
own force feedback, or a host started by hand). `--live` is added only by the "drive the devices" box or
`DEBUG.bat --haptics-live`. The host runs in a kill-on-close job: Stop, Ctrl+C or closing the dashboard's window ends it,
and the dashboard never stops a host it did not start. `DEBUG.bat --haptics` = Start at launch (refused, with the reason
on the console, when no wheel or pad is found).

### With the haptics host started by hand

Only one program can own the telemetry port, so the dashboard owns it and forwards (tees) every datagram:

```bat
tools\debug\DEBUG.bat --tee 17676
tools\haptics\haptics.ps1 live --source udp --port 17676 --debug-udp
```

`--debug-udp` makes the host publish its bus, every effect contribution and its outputs to `127.0.0.1:17680`, where the
dashboard listens. Add `--live` to the host line for the real devices as usual; without it the host writes files only.
`--debug-udp` also works on `replay` (with `--realtime` to watch at game speed) and `motion`.

If the haptics host was started first on port 7676, the dashboard cannot bind it and falls back to reading
`Local\I76Telemetry` (see below); the haptics tabs then still work as long as the host has `--debug-udp`.

## Ports and safety

| port | who binds it | what |
|---|---|---|
| UDP 7676 | I76 Debug (`--tel-port`) | the proxy's telemetry (`I76_TELEMETRY`), bound exclusively (never `SO_REUSEADDR`, which on Windows could steal the port from the haptics host) |
| UDP 17676 (or any `--tee`) | the haptics host | datagram-for-datagram copies of 7676 |
| UDP 17680 | I76 Debug (`--haptics-port`) | the host's `--debug-udp` JSON datagrams |
| TCP 17690 | I76 Debug (`--http-port`) | the dashboard (127.0.0.1 only) |

* **Shared memory is opened EXISTING-only, never created.** `Local\I76Telemetry` is read through `OpenFileMappingW` at
  whatever size the proxy made it (VirtualQuery), and only when the UDP port is taken. The old trainer window mapped it
  at the v2 size, which, when the window started before the game, stopped a v3 proxy from mapping it ("shm view
  refused" in the log). This tool cannot cause that. `Local\I76Trainer` is also opened existing-only: with no proxy
  block the trainer uses direct pokes, and a proxy started later is picked up on the next attach.
* Everything sent goes to 127.0.0.1. The dashboard opens no device and plays nothing; the haptics host opens devices
  only with its own `--live`.
* Entering proxy mode the trainer shows the holds already in the control block instead of clearing them (another
  trainer window may have set them); at exit it clears only the holds it set itself.

## The tabs

| tab | shows | from |
|---|---|---|
| **Overview** | fps (telemetry arrival rate and the proxy log's `fps:` line with work / cap wait), frame time p50 / p99, physics steps per frame (and the fixed-step rate), player state, speed, rpm / gear, health, selected weapon and ammo; armour / chassis per side, engine / suspension / brake hp, wheels, flags; sources (telemetry mode, haptics host, game folder, `STRLKUP.DLL` md5, log); a frame-time chart; every proxy feature line of this proxy start (applied / partly / NO) and the `I76_*` switches they imply | telemetry, log, the DLL file |
| **Telemetry** | strip charts (10-120 s window, hover for values): speed, rpm, throttle / steer, body-frame acceleration, pitch / roll, pitch / yaw / roll rate, suspension offset per wheel, grip sum / cap / ground g / clearance, steps per frame and sim dt; a top-down map with the trail, heading and the last minute's explosions and positioned sounds; car facts (mass, wheelbase, track, steer gain) | telemetry frames (decimated to 60 Hz) |
| **Events** | per-type counters; damage to the player by side (a car diagram shaded by hp lost) and zone, other targets hit / killed; impacts by source class; rounds per weapon row (named when that row was selected); explosions with distance; sounds started and sounds playing now (Hz, volume, mode); weapon UI clicks; a filterable live feed; the haptics host's own derived events (LANDING, TAKEOFF, SKID, GEAR, SURFACE, GRIP_LIMIT) | i76tel v3 events; host `--debug-udp` |
| **Force feedback** | the wheel force over time - reference model, effect-file voices, and the device value after gate / clamp; the contributions stacked (centre, corner, oversteer, brake, texture, scrub, judder, impact, weapon, shift, plus each effect voice); a bar per channel now; the voices sounding | host `--debug-udp` |
| **Rumble** | pad L (heavy) / R (texture) motor levels with peak hold, over time; the bus signals and effect voices that drive them (with no pad sink open: the reference down-mix the pad would get) | host |
| **LFE / transducers** | shaker output RMS (dBFS) and peak; a live spectrum 10-120 Hz (Goertzel on the last 4096 output samples, Hann window); the Lfe.Synth sources (engine, road, impulse, heave, weapon, scrub, explode with their frequencies) and effect voices on the shaker; the HD-pack stems playing with their gains (or why stems are off) | host (a tap on Lfe.Synth's output samples) |
| **Motion** | a small rig preview posed by roll / pitch with heave and surge offsets (a preview, not the rig software's washout); the six channels (surge / sway / heave with cues, roll / pitch / yaw rates and angles) and the fail-to-neutral gain; the status word decoded (live, airborne, skid, destroyed, paused, neutral, interpolated, cues, shutting down, surface, gear); cue counts; packets, packets per second and errors per target | host (Motion.Udp's MotionFrame) |
| **Collision** | the `coll-window when=stepframe` counters of the last 30 s report (pair tests, widened, stock window, no pair window) and their history; the v3 sphere-to-slab counts; the `breakable-box` status and parts report; recent contacts (IMPACT events). Misses are not logged by the proxy: the stock-window share is the closest measure | log, telemetry |
| **Terrain / render** | the I76_DRAW_PROBE terrain draw census (TERRAIN-LOSS / TRIANGLE-LOSS events, the 600-swap summary); TERRAIN-DROP events (frame, terrain vertices vs the previous scene, eye height above the terrain, camera mode, camera position) and the flash-probe summary; camera lifts and COCKPIT-UNDER; the texture census (downloads, flushes, NO-SLOT, resident / peak KB); road-pool and clutter stats; fixed step, render interpolation, fps; the start-position lines; CRASH lines | log |
| **Trainer** | everything the trainer window had - attach and the non-sandbox gate, status, the five holds, repair / stop / refill / slot ammo, teleport with "use current", three waypoints (the same `tools\trainer\waypoints.json`; since 2026-10-20 they hold the **full car state**, see below), the quick slot (Store now / Restore / Restore stopped; Ctrl+9 / Ctrl+0 in the game), Play Options set / clear with the cheater-options confirmation, "Turn off cheater options", the campaign line, the log of every write and its read-back - plus a **T05 hill top** preset (7972, 102.3, 44035: the crest above the barricades, lab `docs/COLL-TIMING-2026-10-12.md` section 4; the teleport keeps your heading, turn west down the hill) | `i76trainer.py` / `i76trainer_gui.py` code, imported (`debug_trainer.py`) |
| **Log** | the tail of `mciproxy.log` from the last proxy start, with a text filter and quick filters (fps, coll-window, breakable, cam-ground, TERRAIN-DROP, tex-census, start-pos, not applied, telemetry, trainer, CRASH), follow on / off | log |

`README-GUI.md` (tools/trainer) still documents every trainer control, the proxy / direct modes and the campaign rules;
they apply to the Trainer tab unchanged.

### Full car state: store and restore (2026-10-20)

Owner: "the teleport capability in the trainer should also teleport 6 axis position and speed when stored". With a proxy
built from i76-everywhere `2d6e7e8` or later (the trainer block carries `i76trn_ext_t`, `tools\trainer\i76trn.h`), a
store captures on the game thread, at the top of a frame before the tick, everything the car step carries from one step
to the next, and a restore writes all of it back and reads it back:

| part | fields |
|---|---|
| pose | rotation rows right / up / forward (heading, pitch, roll) obj+0x18, position obj+0x40 |
| motion | world velocity ent+0xbc, \|v\| and 1/\|v\| ent+0xac / +0xb0, body rates pitch / yaw / roll ent+0xc8, last acceleration ent+0xd4 |
| contact | the skid / airborne / contact-latched bits of ent+0x454, surface, probe normal, ground g, clearance, the fall-kill reference height ent+0x474 |
| wheels | per wheel: spin speed, suspension offset and its filter history, ground heights, unloaded flag, local y |
| engine | gear, drive power, rpm, speedo |

Not carried: the camera (it swings back in over a moment), AI cars, scripts, damage, ammo, and your input (hold the same
throttle). A restore onto a different car (another mass) puts back pose, motion and contact only.

| control | does |
|---|---|
| **Store now** / Ctrl+9 in the game | the quick slot; the page shows its position, km/h, heading, pitch, roll and "airborne" |
| **Restore** / Ctrl+0 in the game | the quick slot (or the last waypoint gone to) back, moving exactly as stored - replay a jump run-up |
| **Restore stopped** | the pose back with zero motion |
| waypoint **Save here** | the full state into that slot of `waypoints.json` |
| waypoint **Go** / **Go stopped** | as Restore / Restore stopped; **<- quick** copies the quick slot into the waypoint |
| "in-game keys" box | Ctrl+9 / Ctrl+0 on (default) or off. The proxy watches them only while this tool has them on and only while the game window has the focus; 9 and 0 are bound nowhere in the game (every F key is a camera). Let go of Ctrl after a restore: Ctrl+key is not a drive key |

`waypoints.json` keeps `x`, `y`, `z` and `saved` at the top (the classic window and old readers use them) and adds `how`,
`summary` and `state`. An old position-only waypoint still loads and Go teleports the position as before; with a proxy
older than `2d6e7e8` the page says "full state: no: this proxy predates it" and Save / Go are position-only. Without a
proxy (direct mode) Store / Restore carry the pose and the motion through WriteProcessMemory. Measured round trip (lab,
headless): `docs/records/DEBUG-TOOL-2026-10-20.md`.

## Physics / memory logger (`debug_logger.py`, 2026-10-17)

The emulator logger I76MEM's output, for the modern port: start / stop / mark from the **Log** and **Mark** buttons in
the header (every tab), the logger card on the Trainer tab, two global hotkeys, or automatically per mission.

- **Files.** `<log-dir>\<date-time>-<label>\sNN\mem.phys.csv`, `mem.frames.csv`, `mem.music.csv` with mem2csv.py's
  columns in mem2csv.py's order (lab `emu\tools\memtrace`), plus `marks.csv` and `meta.json`; `raw\SNN.LOG` and, after
  each stop, `summary.md` / `summary.json` from the lab's `owner_log.py summary`. So `fingerprint.py`, `analyse.py`,
  `owner_log.py` and `music.py` read a dashboard log as they read an 86Box I76MEM log. Three columns of our own come
  after mem2csv's: `health_pct` (the proxy's HealthFraction call), `tel_music_track` (the proxy's playing track), `mark`.
- **Sources.** Per frame, the proxy telemetry (needs `I76_TELEMETRY=1`): frame-consistent, taken on the game thread, so
  `verify` is 1 on every row. At 8 Hz, a read-only `ReadProcessMemory` reader for what telemetry lacks (game state, the
  player object's flags, AI alive / total and the nearest car, CD music intent) at I76MEM's addresses; its player object
  is checked against the telemetry's `obj_addr` (meta.json `reader_check`). On a mismatch those columns stay 0 and
  `game_state` is inferred from player presence (meta.json says which).
- **Marks.** Each mark writes a `marks.csv` row and switches `phase` to `markNN` (the I76DRV `log MARK` rule).
- **Options.** `--log-dir`, `--log-auto` (start when the player appears, stop 3 s after it is gone), `--log-start`,
  `--log-label`, `--hotkeys` (`--hotkey-mark`, default Scroll Lock; `--hotkey-toggle`, default Shift+Scroll Lock;
  RegisterHotKey, so they work while the game has the focus), `--log-pid`, `--no-logger`, `--no-summary`.
  `--no-attach` also turns the reader off. API: `GET /api/logger`, `POST /api/logger {op: start|stop|toggle|mark|auto}`.
- **One click.** `PLAY-LOGGED.bat [preset] [game folder]` starts the dashboard with `--log-auto --hotkeys` and the lab
  twin (default) with `I76_TELEMETRY=1`; the twin's `TEST-logged-play.bat` calls it.
- **Cost and limits:** `docs/records/TRAINER-LOGGER.md`.

## Files

| file | what |
|---|---|
| `i76debug.py` | the server: sources, the trainer thread, HTTP (`/`, `/api/state`, `/api/stream` server-sent events, `/api/log`, `/api/trainer`) |
| `debug_core.py` | telemetry source (UDP + tee, or existing shm), haptics source, the `mciproxy.log` parser, the Hub (history the panels draw from) |
| `debug_trainer.py` | the trainer without tkinter (same writes, imported from tools/trainer), the full-state store / restore |
| `debug_haptics.py` | the haptics tabs' starter: finds the host and the wheel / pads, starts / stops its own host (dry run or `--live`) |
| `debug_logger.py` | the physics / memory logger (I76MEM's CSV files from telemetry + an 8 Hz read-only reader), global hotkeys |
| `PLAY-LOGGED.bat` | one click: the dashboard with the logger armed + the lab twin with telemetry |
| `tests/test_logger.py` | the logger: mem2csv columns, gaps, marks, auto start / stop, owner_log.py + fingerprint.py read it, HTTP end to end |
| `static/` | `index.html`, `app.js`, `charts.js` (strip / bar charts with hover tooltips), `app.css` |
| `tests/test_fullstate.py` | the full-state layout and (de)serialisation, store / restore / waypoints against a fake proxy block, the old-proxy fallback, the haptics starter's refusal / dry-run / port paths |
| `tests/test_debug.py` | unit tests and the end-to-end smoke test; `tests/fixtures/mciproxy-sample.log` is real proxy log lines (the overnight t05 start plus one real example of each periodic line from lab logs) |

## Haptics debug datagram (`--debug-udp`, schema 1)

One JSON object per published core update (`DebugPublisher.cs`), at most 60 per second of core time, loopback only:
`schema`, `kind` ("i76haptics"), `src` (replay / live / motion), `seq`, `t` (core time), `wall`, `steps`;
`state` {present, speed, rpm, gear, airborne}; `wheel` {model, voice, total, device, peak (since the last datagram),
steady, osc, ramp, duck, rough, channels {grip%, center, corner, oversteer, brake, texture, scrub, judder, impact, weapon,
shift}, notes}; `bus` {steady, osc, transient, impact, weapon, shift, tactile [{name, hz, amp}], lfe {engine, engine_hz,
road, road_hz, impulse, impulse_hz, heave, carrier_hz, weapon, weapon_hz, scrub, explode}, motion {surge, sway, heave,
yaw_rate, pitch}}; `voices` [{id, group, kind, prio, level, wheel, lfe, lfe_hz, pad_l, pad_r, transient, age_ms}];
`duck`; `pad` {open, l, r, peak_l, peak_r}; `lfe` {open, rms, peak, samples, rate, spectrum_hz, spectrum, synth_gain,
stems {on, voices [{name, cls, gain}], started, missed, dropped, stolen, stopped, mix_gain | why}}; `motion_out` {open,
frames, sending, seq, status, gain, clock, race_on, surge, sway, heave, cue_surge, cue_sway, cue_heave, roll, pitch,
heading, roll_rate, pitch_rate, yaw_rate, ticks, neutral_ticks, cues {kind: n}, targets [{name, packets, bytes, errors,
rate, streams, error}]}; `ev_count` (since the last datagram), `ev_total`, `events` [{t, type, name, f {...}}] (the last 24).

With the flag absent nothing is created: `Pipeline.Debug` and `LfeSynthRenderer.Tap` stay null (one test per update).
The C# tests (`haptics.ps1 test`, section "debug publisher") check that the wheel / pad / shaker files are byte-identical
with and without it.

## Tests

```bat
python tools\debug\tests\test_debug.py          :: unit tests + end-to-end, about 25 s
python tools\debug\tests\test_debug.py --unit   :: unit tests only
python tools\debug\tests\test_logger.py         :: the logger, about 10 s
python tools\debug\tests\test_fullstate.py      :: full-state store / restore + the haptics starter, about 1 s
tools\haptics\haptics.ps1 test                  :: includes the publisher's C# tests
```

The end-to-end test is the offline replay of a real session: the debug server on free ports with the log fixture, the
haptics host `live --source udp --port <tee> --debug-udp <port>` (file sinks, no `--live`), and `i76haptics play
<t05.i76rec> --port <tel>` standing in for the game (the overnight P2 t05 recording in the lab, else the host's scripted
session). A Python client reads `/api/state` and the `/api/stream` feed and asserts every tab has its data. Ports are
chosen free at run time, never 7676 (a running game may be sending there). No browser: the page itself was checked with
headless Edge captures of every tab during development.

## Not verified yet (needs the console)

* Nothing here has run beside the real game. The live parts were exercised with `i76haptics play` of a real recording.
* The trainer tab's writes are the trainer window's code, but this front end has not been clicked against a game.
* `accel_body` in the telemetry is the FFB block's copy, 0 when `ffb_present` is 0 (the whole overnight t05 run): the
  Telemetry tab then shows rot x `accel` (the engine's ent+0xd4, gravity convention unverified live).
* Owner test item 33 in `docs/process/OWNER-TEST-LIST.md`.
* Deployment: promotion 16 (2026-10-12) put I76 Debug in the daily driver (`_tools\debug`, `DEBUG.bat`, `TRAINER.bat` on
  its Trainer tab). The 2026-10-20 set (full state, haptics starter, the TRAINER.bat shim) is staged in the lab,
  `builds\debug-tool-20261020` (record `docs/records/DEBUG-TOOL-2026-10-20.md`), not installed.
* The in-game keys Ctrl+9 / Ctrl+0 have not been pressed at a console (the lab runs on a private desktop).
