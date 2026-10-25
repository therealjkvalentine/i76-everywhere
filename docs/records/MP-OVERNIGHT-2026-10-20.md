# Multiplayer overnight: join / leave anytime, AI fill, co-op scaling (2026-10-19 night to 2026-10-20)

Owner, 2026-10-19 (verbatim): *"make sure everyone can join or leave a lan game anytime and the open slots will be
replaced with ai bots and that the coop missions will spawn additional enemies per human joiner and test the shit out
of it overnight please so I can play with them fam anytime."*

Everything here was measured on the PC with several lab game copies on one machine (IPX through IPXWrapper on
loopback), headless on private desktops. Nothing was run between machines tonight (family asleep; no game was
started on any family machine). "n" is the number of sessions per cell.

**Verdict.** A (join / leave anytime) passes every cell; B (AI fill) and C (co-op scaling) are built and pass every
cell; the soak ran 60 cycles over 3 h 40 min with **0 crashes**; the pack went to **the PC LAN copy, the M2 tester Mac,
The M4 Max tester Mac and the developer's laptop** (section 8). **The Steam Deck does not run it yet** (asleep all night): its step is
one prepared command, the first item of OWNER-TEST-LIST "Morning 2026-10-20".


## 1. Harness (how the numbers were taken)

- Copies `<lab>\game-mpo-a .. -d` (copies of `game-aimelee`: LAN exe 6319abf7, i76shell a300db63) with the
  ADDON files of this night's `tools/coop-install.py`; `-e`, `-f` for the DOSBox test.
- **Each copy has its own IPXWrapper instance**: `ipxwrapper.dll` with the mutex / registry letter changed to E, F,
  G, H (I, J for e, f), the instance-B patch of lab MULTIPLAYER-LOCAL-TEST 8.4 with other letters, so no copy shares
  the stock instance with the owner's LAN copy. **The headless join stall of TICK-FINISH s.16.2 was this:** `game-sp`
  and `game-sp-b` both carried the stock `ipxwrapper.dll` (md5 06a01d0f), i.e. the same socket mutex and the same
  IPX node. With distinct instances every headless join went through (all cells below).
- Driver: lab `tools\mp-overnight\` (`mpo.py`, `mx.py`, `scenarios.py`, `soak.py`), on the sp-fix lane's lab-twin
  shell clicks (`I76_LAB_SHELLCLICK`); each game on its own desktop `I76Lab-mpo-<x>-<pid>`, `I76_MUTE=1` + a per-pid
  mute watcher, `I76_SHM_SUFFIX=game-mpo-<x>`, env = the `best-wide` preset PLAY-LAN.bat uses + `I76_COOP_AI=1
  I76_COOP_CHAIN=1 I76_MP_MENU=1` + the two-copies-on-one-PC keys. Arena picked by writing the host form's selected
  index `[i76shell 0x100d4474]` (read by EntryForm_DrawArenaList 0x1002b372), checked by the mission name loaded.
- **Leaving** is the stock end-of-session exit: the harness writes game state `0x4c2164 = 3` (what WinMain does 10 s
  after MAX SCORE), the game tears the network down and shows the standings, then the entry form, then the main menu.
  The in-game Esc menu ("Abort Mission") is the exe's own sim menu, which the lab click route cannot press; a person
  at the keyboard uses Esc. A **hard exit** is TerminateProcess of the joiner (the harness only ever stops processes
  it started, checked by pid and exe path).
- Positions: the proxy's new 5 s status line (`mpfill:`, all copies on the same wall-clock grid; `I76_MPF_LOG=1` adds
  every AI and every human car) and direct reads of the player table 0x541070.
- Proxy: lab twins `Strlkup-m2` (60dce76 + shellclick) for A and B, `m4` (e3934e3 + shellclick) for C, E and the soak.
  Evidence: `<lab>\captures\mp-overnight-20261020\<tag>\` (results.jsonl, run.log, each copy's log slice).

## 2. A - join and leave anytime (stock code + the proxy as it was; nothing needed fixing)

| cell | arena | result | n |
|---|---|---|---|
| late join into a running melee (host alone 25 s, then B, then C) | Suburbia | **pass**: every copy lists all 3 players at the same positions (0.0 m between copies), held 20 s | 3 |
| late join into a running co-op scene (same steps) | Scene 1 (Co-op) | **pass**: all 3 listed, positions within 0.02 m, held 20 s; the mission cars and the 9 parked copies at the same places on all three | 3 |
| a joiner leaves (stock exit) | Suburbia | **pass**: host and the other joiner drop him at once (0-1 s), both play on (20 s held) | 2 |
| the same player re-joins after leaving | Suburbia | **pass**: back in, 3 players on every copy | 2 |
| a joiner's process dies (hard exit) | Suburbia | **pass**: host and the other joiner play on; his slot disappears after **47.5 s** (ANet's time-out; both runs) | 2 |
| he starts the game again and re-joins | Suburbia | **pass** | 2 |
| **the host leaves** | Suburbia | **the game goes on**: ANet makes a joiner the host at once (B's table: host = B's own id), B and C stay in the arena with 2 players for the 60 s watched; nobody is sent to the menu | 2 |
| + AI arena: joiner hard exit / leave (section 3) | Hope Springs (4 AI) | slot gone after 41-42 s, AI brought back (section 3) | 3 |
| crashes in all A cells | | 0 | |

Answer to "can the host leave": yes, the session survives (host migration, stock ANet). Not measured: what the
new host does in an AI arena or a co-op scene (it then runs the AI and, in co-op, the mission script from the start
state of its own copy, design note AI-MELEE-AND-LATE-JOIN section 1); a clean "host left" return to the menu was not
built because nothing hangs or ends.

## 3. B - open slots filled by AI cars (`I76_AIMELEE_FILL`, default on)

**Mechanism: a pre-spawned pool, parked.** No car is created after the mission loads (the "create car" message of
the design note was not needed): every car is an ODEF object of the arena file, so the stock load gives it to every
joiner and the 'AT' sync moves it. `tools/mp_pool.py` tags each AI car of `ai_hs2/4/6.lvl` in the ODEF record's 36
unused bytes ("I76P", kind, parking spot). The host's proxy (`music-fix/mpfill.c`):

- **park**: the FSM's own teleport (`fsm_TeleportOffset` 0x414bc0, speed 0) to a parking spot ~8 km from the
  arena on an empty terrain tile, then the FSM 'hide' (`ai_SetBehaviour(car, 0, 0x21)`: engine off, which also takes
  it off the radar, `object_IsRadarVisible` 0x466de0). An empty tile is flat ground at height 0: `0x493080` points
  every tile slot the mission's ZMAP leaves empty at one shared tile. Far beyond every draw distance and the 600 m
  radar. No damage, no kill, no score.
- **bring back**: teleport to the spawn point farthest from every car (spawn table 0x53fd88, as 0x451030 reads it)
  + `startCar` 0x467400; the AI melee tick then sends it after the nearest human.
- **rule**: target combatants N = `I76_AIMELEE_FILL` (default = the arena's AI count + 1); AI in play =
  N - humans (player-table slots), between 0 and the AI count. **Hope Springs (4 AI): alone you meet 4 AI, with
  2 humans 3, 3 humans 2, 4 humans 1, 5+ humans 0.** (The brief's alternative "N = 4 for the 4-AI entry" would give a
  lone host only 3 AI and break the title; it is `I76_AIMELEE_FILL=4`. Owner's choice.) Humans are counted after
  1.5 s without change. Parked cars go into 'AT' every 2 s, not 10 times a second. Waves count only cars in play.

Hope Springs (4 AI), host + up to 2 joiners (`b_fill`):

| step | host: in play / parked | joiners: same cars at the same places, parked ones at the parking spot | n |
|---|---|---|---|
| lone host | 4 / 0 | - | 3 |
| B joins | 3 / 1 | yes (0 cars off by more than 60 m; the parked car within 100 m of the spot on B) | 3 |
| C joins | 2 / 2 | yes, on B and on C | 3 |
| C's process dies (slot gone after 41-42 s) | 3 / 1 | yes, on B | 3 |
| B's process dies | 4 / 0 (once 3 + 1 dead: an AI had been killed) | - | 3 |
| crashes | 0 | | 3 |

The host log names each move, e.g. `parked 'vfpalmn3' (label 13, live) at 3508,41932 - 2 humans, 3 of 4 AI wanted`
and `'vpjrabt2' (label 12) into the game at 857.5,50672.5 heading 41 - 2 humans, 3 of 4 AI wanted (spawn point 8)`.

## 4. C - co-op scenes: more enemies per joiner (`I76_COOP_SCALE`, default on)

**The owner's question, answered by the code and a measurement: the mission scripts never create a car.** The FSM
has 96 actions (<re-archive> data/FSM.md) and none creates an object: the "reinforcements" of the campaign are cars that
are in the mission file from the start, sitting or hidden, and the script `teleport`s / `startCar`s them (108 / 53
uses). Every such car is in the label table from the load, so the proxy's 'AT' sync already carries it to joiners.
Measured: in the late-join runs (section 2) and the scaling runs below, every mission car the host had was at the
same place on each joiner. Human respawn is different: a player's car is re-created by its own machine and announced
with 'SR'; mission cars never need that.

**Mechanism: the same pool.** `coop-install.py` now builds each `coopNN.lvl` with `coop-mission.py --count 3
--copies 3`: 3 joiner start points (was 2) and **3 parked copies of every enemy car** (class 1, team neither 0 nor
the player's, not a trailer): the same record with the next free instance number, team 0 in the file, tagged with
its original's label and a parking spot ~8 km away (Scene 1: 3 enemies -> 9 copies; Scene 5: 13 -> 39; Scene 13: 9
-> 27). Host rule: copy j of an enemy comes in when that enemy first turns on a human (any behaviour aimed at a human
except follow, seen in `coop_ai_attack`) and at least j joiners are present; it appears beside its original (12 + 8 j
m behind, 6 m to a side), moves from team list 0 to its original's list (so it fights and counts for the script's
`allEnemyDead` like any enemy) and attacks the nearest live human until it dies. A joiner arriving later brings the
next copy of every engaged live enemy. **Parked copies are on team 0, which `allEnemyDead` / `isWithinEnemy` never
walk** (0x40aa90 / 0x40ab30 start at team 1), so a lone host's mission and its win / loss logic are the stock ones.

Bug found and fixed on the way: the first build only changed the copy's team bits; the engine removes a dying object
from the list of its flags' team, so a handle stayed behind in list 0 and the host crashed at the next mission
teardown (0xC0000005 at 0x4099af, reading the dead object, n 1). Fixed by moving the handle between lists (e3934e3).

| cell | result | n |
|---|---|---|
| lone host, Scene 5 (39 copies) and Scene 1 (9), held 90 s | no copy came in, the mission ran (Scene 1 failed and reloaded at ~75 s as stock does when nobody follows Taurus), no crash | 3 + 3 |
| Scene 5, host + 2 joiners, natural play (host in god mode, 2 min) | `t05fp03` engaged the host; **its 2 copies came in beside it** (one per joiner) and circled the host 30-100 m away with the original; every AI car at the same place on both joiners; no crash | 3 |
| Scene 1, host + 2 joiners, every original forced engaged (lab `I76_COOP_SCALE_TEST=1`) | 6 copies in (2 per enemy), joiners agree, the mission's fail-reload brought them back again, no crash (after the fix) | 1 |
| copies killed by a human, credited | **not measured** (the scripted players do not aim) | 0 |

## 5. E - internet play without Tailscale: IPXWrapper's DOSBox mode

IPXWrapper 0.7.2 (the pack's) has a DOSBox-server mode (`ipxwrapper.ini`: `dosbox server address = <host>`,
`dosbox server port = <port>`). Tested: DOSBox Staging 0.82.2 (`downloads\dosbox-staging-0.82.2`, started with
`-set ipx=true -c "ipxnet startserver 19900"` on a private desktop), two copies with that ini.

**Result: does not work with I'76 (n 2).** IPXWrapper connects to the server (`Connected to DOSBox server`), the game
then sends its 4-byte start-up broadcast and waits for its own copy, which a DOSBox server never sends back to the
sender (predicted from dosbox-x ipxserver.cpp in lab MULTIPLAYER-LOCAL-TEST 8.4); WIPX's IPX init fails and HOST
never reaches the host form. MULTIPLAYER.md's answer stays: direct IP (unverified) or a virtual LAN that carries
broadcast (ZeroTier / Radmin VPN).

## 6. D - soak (lab `tools\mp-overnight\soak.py`, 23:48 - 03:30, proxy lab twin m4)

60 cycles of about 3.7 minutes, each with fresh boots of 3 copies: host A, then B and C join late (10 s after the
host is in), 60 s of play, C's process killed, 25 s, C restarts and re-joins, 60 s. Kinds in turn: Suburbia; Hope
Springs (4 AI) with AI fill; a co-op scene with scaling (Scenes 1, 4, 5, 8, 13 in turn, host in god mode, natural
engagement only); Pretty Bus (Scenario). Logged per cycle (`captures\mp-overnight-20261020\soak1\soak.jsonl`): crash
lines, copies leaving the game, car counts on host and joiners, positions of every AI and human car on host and
joiners at the same 5 s stamps, scores. Table from lab `soaksum.py`:

| kind | arenas | cycles | first - last start | crashes | out-of-game events | AI samples | AI median / p99 / max (m) | without the first stamp after a join or a park / bring-in: p99 / max / samples > 20 m | human median / max (m) | copies in | fill parks / brings | waves |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arena | suburbia | 10 | 23:48:39 - 03:08:30 | 0 | 0 | 0 | - / - / - | - / - / 0 of 0 | 0.0 / 0.0 | 0 | 0 / 0 | 0 |
| fill | hs4 | 20 | 23:52:24 - 03:23:16 | 0 | 2 | 3668 | 0.0 / 705.1 / 9457.6 | 1.4 / 7.1 / 0 of 3474 | 0.0 / 0.6 | 0 | 43 / 1 | 1 |
| coop | coop01, coop04, coop05, coop08, coop13 | 20 | 23:56:10 - 03:27:03 | 0 | 0 | 26479 | 0.0 / 1.2 / 12771.8 | 1.0 / 85.7 / 25 of 25312 | 0.0 / 7.1 | 56 | 0 / 0 | 0 |
| scen | auto04 | 10 | 23:59:50 - 03:19:38 | 0 | 9 | 3737 | 0.0 / 176.4 / 1921.3 | 1.8 / 5.7 / 0 of 3572 | 0.0 / 7.4 | 0 | 0 / 0 | 0 |

- **0 crash lines in 60 cycles (180 game sessions, 60 hard exits, 60 re-joins).** Every join of the soak succeeded.
- "Out-of-game events" were all recoveries, not hangs: 1 AI-fill wave (both in-play AI cars dead, the arena reloaded for
  everybody, cycle 4) and 8 lost-scenario reloads in Pretty Bus (the bus dies when nobody defends it, state 7); every
  copy was back in the game at the end of its cycle.
- Desync: AI cars median 0.0 m. The large values are the first status stamp after a (re)join (the joiner still shows
  the file's start or parking positions) and the stamp of a park / bring-in on the host; each agreed within 2 m at the
  next stamp. Without those, p99 1.0-1.8 m; in co-op 25 of 25 312 samples over 20 m (max 85.7 m). Humans: median 0.0,
  max 7.4 m.
- Co-op scaling in the soak: 56 copies came in by natural engagement over 20 co-op cycles.
- After the soak, **4 humans** (A hosts Hope Springs (4 AI), B, C, D join late): all 4 listed on every copy, positions
  within 0.27 m; AI fill 1 in play / 3 parked, joiners agree; held 30 s (n 1) / the one AI car died and the wave
  reloaded for all 4 (n 1); 0 crashes (n 2).


## 7. What is not measured

- Anything between two machines tonight (no game was started on a family machine).
- A human killing an AI copy in co-op and its credit; copies hitting a human (the host ran in god mode).
- The new host's behaviour after a host migration in an AI arena or a co-op scene.
- A joiner leaving through the in-game Esc menu (the harness used the same end-of-session exit the game uses after
  MAX SCORE).
- 5 or more humans; 4 humans in a co-op scene (4 measured in the AI arena only).

## 8. F - pack and where each machine stands (2026-10-20 03:35)

Pack `<lab>\builds\mp-pack-20261020-overnight\` (README.md there): `mp-pack-20261019-final` with 21 files
replaced (STRLKUP.DLL 07975706 -> **533ab67c** = e3934e3, clean `git archive`, built twice byte-identical; ai_hs2/4/6.lvl;
coop01..17.lvl). Against the deployed 2026-10-18 pack: 20 changed + 20 new files. The ADDON files are byte-identical to
the ones every test ran with; the proxy is the tested lab twin minus the lab click block (the candidate itself was not
booted: headless driving needs the lab block).

| machine | state | how | rollback |
|---|---|---|---|
| PC LAN copy `<games>\Interstate76-LAN-2026-10-17\Interstate 76` | **new pack** | `deploy-pc.ps1`: 40 files replaced / added (md5-driven; game-written NSCR.DAT, user.mel, NVCL\, ADDON\vehscn.* left alone), each replaced file saved first to the pack's `rollback\pc\` (20 saved; 20 new ones listed in NEW.txt); verified 0 mismatches; STRLKUP 533ab67c | `rollback-pc.ps1` (one step) |
| The M2 tester Mac | **new pack** | new folder inside the same app bundle (same wine: no new firewall / microphone question): `GOG Games/Interstate 76` copied, 38 files applied, 408 files verified 0 mismatches, then the old folder renamed `Interstate 76-pre-20261020` (kept, untouched inside) and the new one named `Interstate 76`, because the bundle's launcher (i76-launch-stub) and DxWnd's dxwnd.ini have that folder name built in. Desktop link unchanged | `bash ~/i76-overnight-20261020/mac-rollback-20261020.sh "<game folder>"` (swaps the names back) |
| The M4 Max tester Mac | **new pack** | the same | the same |
| The developer's laptop (`I76 MP GATE.app`) | **new pack** | the same | the same |
| Steam Deck | **old files (2026-10-18 + its own proxy)**: asleep all night (ssh time-out 23:52; retries in section 9) | prepared: `<lab>\builds\mp-pack-20261020-overnight\deploy\deck\DECK-DEPLOY.sh` (copies the 37 new ADDON arena files, makes the new game folder with the old kept as `game-pre-20261020`, md5-verifies) | `mac-rollback-20261020.sh ~/Games/Interstate76/game` on the Deck |

**Until the Deck step runs, the Deck cannot join the co-op scenes, scenarios or AI arenas of the other machines**
(CRC check: "does not match the host's"); the 15 stock arenas still mix. The Deck runs its own proxy without the co-op
switches, so even after the step it sees the AI arenas' computer cars standing still (not mirrored); that was already so.

No game was started on any family machine; nothing outside those folders (and `~/i76-overnight-20261020/`) was written.

## 9. Deck retries (04:05-04:30, once per 10 minutes)

04:05 ssh time-out, 04:15 connection refused (the network answered, sshd did not: waking or suspended), 04:25 time-out.
**The Deck still runs the 2026-10-18 files; its step is OWNER-TEST-LIST "Morning 2026-10-20" item 0.**

## 10. Rollback, all machines together (the co-op and AI arena files must match everywhere)

- PC: `powershell -ExecutionPolicy Bypass -File <lab>\builds\mp-pack-20261020-overnight\rollback-pc.ps1`
- The M2 tester / the M4 Max tester: `bash ~/i76-overnight-20261020/mac-rollback-20261020.sh "$HOME/Games/Interstate76-MP/Interstate 76.app/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76"`
- Laptop: the same script with `"$HOME/Applications/Sikarugir/I76 MP GATE.app/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76"`
- Deck (only if its step ran): `bash ~/i76-overnight-20261020/mac-rollback-20261020.sh ~/Games/Interstate76/game`
