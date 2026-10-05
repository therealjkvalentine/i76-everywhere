# Interstate '76 trainer window (`i76trainer_gui.py`)

A player-facing front end over the trainer pieces that already exist in this folder: the pokes of
`i76trainer.py`, the Strlkup proxy's control block (`i76trn.h`), and the telemetry export
(`..\telemetry\i76tel.h`). Stdlib Python 3 with tkinter, nothing to install. Double-click `TRAINER.bat`,
or `python i76trainer_gui.py` (`--selftest` parses the headers and round-trips a request without a game;
`--any` starts with the non-sandbox box ticked).

Every address below is from `C:\Users\james\i76-map\subsystems\cheats.md` (static reading of the pristine 2017
exe, md5 9a232dcc; the ammo table is **[lab]**, measured on the AiO build and re-verified live on the sandbox for
reads, writes and read-back). Section numbers refer to that file.

## Attaching, and the sandbox gate

The window looks for a running `i76*.exe` every 2 s with `i76trainer.find_game`, which refuses any process that
is not the sandbox copy (`C:\Users\james\i76-uncap-lab\game`) - AGENTS.md: experiments never touch the install
James plays on. Tick **allow non-sandbox game** to override; the window then re-attaches. The path it attached
to is shown at the top, with NOT THE SANDBOX in the log when the override was used. Nothing is written - not
even the shared control block - while the gate refuses, because that block is session-global and would drive
whichever game owns it.

`find_game` returns the first matching process it enumerates: with the sandbox and the daily driver both
running it may pick the daily driver and refuse. Close one of them.

## Two modes, chosen automatically

| mode | when | how a cheat is applied |
|---|---|---|
| **proxy** (preferred) | `Local\I76Trainer` carries `I76TRN_MAGIC` with the header's version and size **and its heartbeat advanced within the last 0.5 s** | The window writes the control block; the proxy reads it at the top of every frame **on the game's thread** and holds the flags / runs the commands there, before `simclock_Update`, the physics tick and the render. The status line shows the proxy's heartbeat (its frame counter, with an fps estimate), `applied` (the flags it actually applied last frame; 0 outside a mission), `faults` (SEH faults it swallowed), and its last message. |
| **direct pokes** (fallback) | no proxy block (the game runs without the Strlkup proxy, or an older build) | `WriteProcessMemory` through `i76trainer.Game`, every write read back and logged, the holds re-asserted on a **5 Hz timer**. Caveats, from cheats.md section 2: a position write that lands inside the render window is undone once by the proxy's `I76_RENDER_INTERP` restore (so teleport writes twice, a frame apart), and a hit can register in the same frame as a repair, so under fire the HUD may dip for up to 200 ms before the next re-assert. The window names the mode in the status line and the log whenever it changes. |

The mode is re-evaluated every tick; switching clears every hold.

**Stale mappings (measured 2026-10-02):** a `Local\I76Trainer` or `Local\I76Telemetry` mapping survives the game
process for as long as any other process holds it open - this window, the selftest, a test script - and it keeps
the last magic and the last frames. Magic alone therefore proves nothing. "Present" means magic **and** a
heartbeat that moved within 0.5 s; "telemetry live" means its `seq` moved within 0.5 s. Otherwise the status
line says `proxy: stale` / `telemetry stale` and the block is not driven (direct mode takes over). The one
exception is a block that was seen live for the process the window is attached to, while that process is still
running: a frozen heartbeat then reads `proxy paused` (pause menu, options screen) and the mode is kept, so a
pause does not drop god mode.

For tests: `I76TRAINER_SHM_SUFFIX=<anything>` is appended to both tagnames so a fake proxy never shares the
game's mappings. (Without it, a test's fake proxy and the real one answer the same block, and the test's
requests run on the real car - this happened during development.)

## Status panel (10 Hz)

Fed by the telemetry block `Local\I76Telemetry` (`i76tel_frame_t`, seq-even / unchanged torn-read rule from
`i76tel.py`) when the game publishes it, by direct reads otherwise ("source" line says which). Fields: player
present, position (`obj+0x40` doubles, y up), speed (`ent+0xac`), armour and chassis per side current/max
(`ent+0x138/+0x158`, `+0x148/+0x168`; in direct mode also the HUD copies `+0x178/+0x18c` and their side-4
percentage), engine / suspension / brake hp (`[[ent+0x3c4|0x3c8|0x3cc]+0x70]`), the six wheel slots with FLAT
(`wheel+0x44`), the selected weapon and its ammo (telemetry only), the live weapon slot list (always direct:
table `0x5aab08`, stride `0x4c`, count `0x5da750`, name from `[inst+0x08]` -> 8-char `.gdf` name, ammo
`inst+0x20`), Play Options (`0x654b98`, from the proxy's `play_flags_now` when it is live) and the **cheats-used
marker `0x535f78`**.

About that marker: see **Campaign progress** below. If it reads 1, no mission won in this game process will
advance the campaign; the status line says so.

## Campaign progress: what blocks the next mission, and what to do (corrected 2026-10-04)

Owner report, daily driver, 2026-10-04: "using the trainer seems to trigger the cheating flag because it won't
progress to the next level". The earlier claim here ("nothing this window does sets the marker") was wrong. Static
reading of md5 9a232dcc, the same bytes in the AiO 6319abf7 the driver runs:

- At mission end WinMain turns a success (0x4c2164 = 1) into **0xb** when the cheats-used marker `0x535f78` is set
  (0x40412f). 0xb is handled like a failure: the mission-over menu offers 'Turn off Cheater Options', there is no
  salvage, no `vehscn.vsf`, and the shell DLL does not advance the trip scene (it advances only on 1).
- The marker is set by the **game**, from the Play Options dword `0x654b98`, whenever bits **0x04 / 0x08 / 0x10**
  (unlimited ammo / armour / chassis) are set at one of three moments:
  1. closing the in-mission options menu (Esc menu) - 0x495170 also writes `I76PLYR.DEF` (0x495226);
  2. `player_SaveDef` 0x497290 at mission end (0x4040f7) and on the video-mode key (0x44e3a1) writes them to
     `I76PLYR.DEF`, and after every return to the shell 0x4970f0 reads the file back and sets the marker (0x497241).
  (Ticking them in the game's Play Options menu goes through the "I'm a cheater" page, then route 1.)
- **Only 'Turn off Cheater Options' (0x4976a0) clears it.** Once set, every later win in the same game process is
  refused, with or without the trainer, and if `I76PLYR.DEF` holds the bits the next game start sets it again.
- The campaign saves (`savegame.dir`, `saveNNN.cmp`) do not carry the marker or the bits: a refused win simply
  writes no new save. The state lives in game memory and in `I76PLYR.DEF` (+0x58).

Which trainer actions trip it:

| action | touches 0x654b98? | campaign |
|---|---|---|
| God mode hold | forces 0x18 while held | **trips it** on an old proxy (no guard): Esc-menu close or mission end while ticked. Safe with the guarded proxy (below) |
| Unlimited ammo hold | forces 0x04 while held | same as God mode |
| Play Options Set (ammo / armour / chassis) | sets the bits for real | **always trips it** (that is the game's own cheat switch); the window now asks first |
| Play Options Set (arcade / no-salvage) | 0x01 / 0x02 | not a cheat bit (no marker); no-salvage of course means no salvage |
| Repair now, Stop car, Refill ammo, Set slot ammo, Teleport, waypoints | no | safe |
| No flats, Components, Freeze position holds | no | safe |
| CLI `i76trainer.py flags ammo/armour/chassis` | sets the bits | **trips it** |

The fixes:

- **Proxy cheat-marker guard** (music-fix/strlkproxy.c, part of the trainer block, built 2026-10-04, lab only): the
  two `player_SaveDef` calls and both routes into the options-menu close (the call at 0x44e0c1 and the close
  callback pushed at 0x495120) go through wrappers that put the bits God / Ammo forced back to the user's baseline
  before the game's code runs. The log line `trainer: cheat-marker guard 4/4 sites` confirms it; the window reads
  `mciproxy.log` beside the game and says in red under the holds whether the running proxy has it.
- **Direct mode** (no proxy) no longer forces any Play Options bits; God / Ammo hold by the 5 Hz repair and ammo
  writes alone (a big hit between two repairs can kill).
- **'Turn off cheater options (campaign fix)'** button: clears bits 0x1c (in the proxy's baseline too, and releases
  the God / Ammo holds) and writes the marker to 0, read back. CLI: `i76trainer.py --any uncheat`. Then win the
  mission again; the game rewrites `I76PLYR.DEF` clean at the next Esc-menu close or mission end.
- **Offline**: `python i76-save-editor.py --dir "<game>\Interstate 76" --check` reports the play options stored in
  `I76PLYR.DEF`; `--clear-cheat-options` (game closed) clears bits 0x1c there, keeping `I76PLYR.DEF.pre-uncheat`.

If a won mission did not advance: choose **Turn off Cheater Options** in the mission-over menu (the game's own
recovery), then **Replay** and win it again with God / Ammo unticked (or with the guarded proxy). Or quit the game,
run the save-editor check above (clear the bits if it reports any), restart, load the last bookmark and replay.

## Holds (checkbuttons -> `i76trn_ctl_t.flags`, held every frame)

| control | proxy flag | what the game thread does (i76trn.h) | direct-mode equivalent |
|---|---|---|---|
| God mode | `I76TRN_F_GOD` 0x01 | armour + chassis (`+0x138/+0x148` and the HUD copies `+0x178/+0x18c`) at max, every component at max, flats cleared, and Play Options bits 0x18 forced on (`entity_ApplyDamage` 0x465620 zeroes the amount; hidden from the cheat check by the guard - Campaign progress) | `cmd_repair` every 200 ms (no play bits since 2026-10-04) |
| Unlimited ammo | `I76TRN_F_AMMO` 0x02 | bit 0x04 forced on (`weapon_Update` 0x4a418b copies it, the offline fire paths test it), every live slot's ammo = 0x0fffffff | `cmd_ammo` every 200 ms (no play bits since 2026-10-04) |
| No flats | `I76TRN_F_NOFLATS` 0x04 | wheel flat flag `+0x44` cleared, radius `+0x1c` restored (undoing 0x46ddd0's x0.688) | same, every 200 ms |
| Components invulnerable | `I76TRN_F_COMPONENTS` 0x08 | every component's health = its max (`entity_ComponentHealth` 0x466ac0 offsets by type) | same, every 200 ms |
| Freeze position | `I76TRN_F_FREEZE_POS` 0x10 | the car held at `pos[]` with zero velocity | `obj+0x40` and `ent+0xbc` rewritten every 200 ms |

Freeze seeds `pos[]` from where the car is at the moment you tick it (the teleport entries are overwritten with
it); it refuses when there is no player. Unticking a hold releases it; the proxy restores the Play Options bits
it forced (`play_flags_saved`) when the forcing flag clears. Closing the window writes `flags = 0`.

## One-shots (`cmd` + `req_seq`, acked by `ack_seq`)

The window fills the operands, sets `cmd`, increments `req_seq`, then watches for `ack_seq == req_seq` for up
to 1 s and logs `cmd_result` (0 ok, 1 no player, 2 unknown cmd, 3 bad slot) and `msg`. One request at a time;
with no ack in 1 s (paused, in a menu) the request stays in the block and the proxy runs it on its next frame.
Every one-shot that touches the car is refused unless a player vehicle is present (the proxy's
`player_present`, or `[[0x54a264]]` -> `obj+0x70` readable). Play Options set/clear is the exception: it is a
global options dword, not vehicle state, and works between missions like the CLI's `flags` command.

| control | proxy command | direct-mode equivalent |
|---|---|---|
| Repair now | `I76TRN_CMD_REPAIR` 1 | `cmd_repair` (sides, HUD copies, components, flats) |
| Stop car | `I76TRN_CMD_STOP` 6: `ent+0xbc` velocity and the body rates `+0xc8..+0xd0` = 0 | the same six floats |
| Refill ammo (entry: `unlimited` or a number) | `I76TRN_CMD_AMMO` 3 with `ammo_value` | `cmd_ammo` for unlimited, else `inst+0x20` per live slot |
| Set slot ammo (pick a live slot) | `I76TRN_CMD_SLOT_AMMO` 4 with `slot_index`, `ammo_value` | `inst+0x20` |
| Teleport x y z / Use current / waypoints 1-3 | `I76TRN_CMD_TELEPORT` 2: `obj+0x40 = pos[]`, `ent+0xbc = vel[]` (0) | `cmd_teleport` (written twice, 40 ms apart, because of the render-interp restore) |
| Play Options: Set / Clear ticked bits | `I76TRN_CMD_PLAYFLAGS` 5: `flags = (flags & ~play_clear) \| play_set` | `0x654b98` read-modify-write |

Waypoints persist in `tools\trainer\waypoints.json` (three slots, position + save time). y is up: keep a
teleport target above the ground, and prefer a saved waypoint over typed numbers.

Play Options bits (cheats.md section 1): 0x01 arcade physics, 0x02 no salvage management, 0x04 unlimited ammo
(offline), 0x08 unlimited armour and 0x10 unlimited chassis (player, offline: `entity_ApplyDamage` zeroes the
amount). These are the game's own switches and offline only. 0x04 / 0x08 / 0x10 are its **cheater options**:
setting them here is the same as ticking them in the game's menu and stops the campaign advancing (Campaign
progress). 'Turn off cheater options (campaign fix)' clears them and the marker.

## Layout safety

`i76trn.h` is parsed at start-up with the `Header` class from `..\telemetry\i76tel.py` (subclassed, not copied),
so the Python side cannot drift from what the proxy compiles: `sizeof(i76trn_ctl_t)` is 168 bytes
(`--selftest` prints the field table and fails on anything else). The proxy writes its `version` and `size`
into the block; a mismatch with the parsed header is reported and the block is not driven. The mapping is opened
with `mmap.mmap(-1, size, tagname=...)`, which attaches to the proxy's block when it exists and otherwise creates
a zeroed one that the proxy adopts when the game starts later (magic 0 = no proxy).

## Known caveats

- The proxy side is live-verified on the sandbox (2026-10-02, `tests\trainer_live_test.py`): god mode blocks a
  40 m drop entirely (-156 armour+chassis with god off, 0 on), holding GOD|AMMO forces the play flags to 0x1c and
  releasing restores them, repair and teleport one-shots ack. The window itself has run only against a fake
  proxy that acks requests and publishes telemetry (`--selftest` covers the layout); its first session against
  the real game is still to come.
- The selected-weapon line needs telemetry; without it the slot list still shows every weapon's ammo.
- Direct mode and the status reads both use `ReadProcessMemory`; the window needs the same privileges as the
  game (run both as the same user).
- `find_game` picks the first `i76*.exe` it finds (see above).
- The game grabs the mouse and keyboard; alt-tab out to reach the window, or put it on a second monitor.

## Verified against the game (2026-10-02, sandbox t01)

Launched while the sandbox ran with the new proxy: attached to the sandbox pid, `mode proxy`, `proxy live,
heartbeat ... (60 fps)`, telemetry live, the status panel showed armour 800/800 x4, chassis 720/720 x4, engine
1200/1200, wheels 400/400, the selected weapon and the live instance slots. Flipping god through the control block
showed `applied 0x0001` and `play 0x18: armour, chassis` in the panel within a second. The toggles and one-shots
themselves were exercised through the same block by `tests/trainer_live_test.py` (13/13). Not yet: a person
clicking through every control.
