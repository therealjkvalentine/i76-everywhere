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

About that marker (cheats.md section 1): the Play Options *menus* set it, and at mission end a set marker turns
a success into outcome 0xb ("Turn off Cheater Options", no salvage, no scene advance). Nothing this window does
sets it - neither the pokes nor the proxy touch `0x535f78` - which is why the value is shown: if it reads 1 the
menus were used, and the mission result will reflect that regardless of this tool.

## Holds (checkbuttons -> `i76trn_ctl_t.flags`, held every frame)

| control | proxy flag | what the game thread does (i76trn.h) | direct-mode equivalent |
|---|---|---|---|
| God mode | `I76TRN_F_GOD` 0x01 | armour + chassis (`+0x138/+0x148` and the HUD copies `+0x178/+0x18c`) at max, every component at max, flats cleared, and Play Options bits 0x18 forced on (`entity_ApplyDamage` 0x465620 zeroes the amount) | `cmd_repair` every 200 ms + bits 0x18 set once (restored when unticked) |
| Unlimited ammo | `I76TRN_F_AMMO` 0x02 | bit 0x04 forced on (`weapon_Update` 0x4a418b copies it, the offline fire paths test it), every live slot's ammo = 0x0fffffff | `cmd_ammo` every 200 ms + bit 0x04 (restored when unticked) |
| No flats | `I76TRN_F_NOFLATS` 0x04 | wheel flat flag `+0x44` cleared, radius `+0x1c` restored (undoing 0x46ddd0's x0.688) | same, every 200 ms |
| Components invulnerable | `I76TRN_F_COMPONENTS` 0x08 | every component's health = its max (`entity_ComponentHealth` 0x466ac0 offsets by type) | same, every 200 ms |
| Freeze position | `I76TRN_F_FREEZE_POS` 0x10 | the car held at `pos[]` with zero velocity | `obj+0x40` and `ent+0xbc` rewritten every 200 ms |

Freeze seeds `pos[]` from where the car is at the moment you tick it (the teleport entries are overwritten with
it); it refuses when there is no player. Unticking a hold releases it; the proxy restores the Play Options bits
it forced (`play_flags_saved`) when the forcing flag clears, and the direct mode restores the bits it saw before.
Closing the window writes `flags = 0`.

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
amount). These are the game's own switches - the least invasive route - and offline only.

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
