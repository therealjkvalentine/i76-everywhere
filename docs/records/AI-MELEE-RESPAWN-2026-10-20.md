# AI melee: computer cars respawn and score like players, in every arena (2026-10-20 night)

Owner rulings (verbatim):

1. *"On Andrew's computer the game restarts when I play the (6ai) version of multi melee and the ai players are dead, but
   shouldn't they be respawned instead and the points tallied like they were players?"*
2. *"Instead of special levels for ai players, shouldn't there be ai cars for all player slots not occupied by a human for
   all levels?"* and *"I don't think the cars need to exist in the file, or at least they do not need to be triggered or
   spawned, because of how they work in the missions."*
3. *"Is the difficulty of the ai cars correct or is it tuned to the difficulty of the game menu setting or perhaps the dps
   of my weapons or something? Seem to be spanking all these guys."*

Code: i76-everywhere `b273777` (respawn, rows, pool injection), `4341d06` (launcher `-AiSkill` / `--ai-skill`), `ec59784`
(respawn timer fix, LAB fire keys), `cdd69f7` (second-session crash, AI numbers per load), `32a5b04` (`I76_COOP_AI=1` inert in
single player). Files: `music-fix/aimelee.c` sections 6, 7, 8 and the LAB
block, `music-fix/mpfill.c` (AI rows are not humans; wreck-first parking; the injected pool), one line in
`music-fix/strlkproxy.c` (`coop_ai_apply` -> `aim_at_revive`). The difficulty lane's hook line in `aim_tick`
(`difficulty_ai_skill`) is kept. Lab: `i76-uncap-lab\tools\airespawn\` (`airespawn.py` on the mpo harness, build scripts);
evidence `i76-uncap-lab\captures\airespawn-20261020\<tag>\`. Pack: section 9.

**Verdict.** Phase 1 (respawn + score rows) and phase 2 (AI in every stock arena, no special files) both pass every cell
measured on the PC (two to three headless lab copies, IPX on one machine). Nothing was run between machines and nothing was
deployed. The AI skill question has an answer from the code and a noisy measurement (section 7). Measured on `ec59784` / `cdd69f7`;
after the soak, three bugs were found and fixed (section 6), and the staged build `491f8db` plus the remaining runs wait for
a console session: the PC was on RDP on 2026-10-21, where every boot hangs.

## 1. Design in five lines

1. **Respawn:** 5 s after an AI car dies, the HOST builds a fresh car of the same `.vcf` at the free spawn point with the
   stock melee spawner `0x4513c0`, puts it into the wreck's label-table entry, gives it the wreck's team, and removes the
   wreck as the human respawn does (`0x4575d0` + `0x465310`). No wave reload any more.
2. **Joiners** need no packet: when the host's 'AT' record for a label says "alive" and the local copy is a wreck, the joiner
   rebuilds its copy the same way, and the mirror snaps it to the host's place. Late joins, lost packets and a new host all
   heal from the next 'AT'.
3. **Score rows:** every AI car in play holds a row of the stock player table on every machine (id `0x7E00 + n`, its AUTO
   MELEE name, team, no car pointer, latency -1 so it can never become host). Its owner id (`entity+0x480`) is the row id,
   so the stock code does the rest: kill messages with the AI's name, a human's death without the -500 when an AI killed
   him, the 'AT' record carries the row's kills / deaths / score, every joiner's mirror writes them into its own row through
   `0x454ea0`, and that call runs the MAX SCORE test. Team sums walk all 16 slots, so they include the AI.
4. **The host keeps the AI rows:** AI kills of humans (own car `entity+0x482`; a remote human from the killer id in the 'ST'
   record that wrecks him, hook at `0x456c78`) and of AI (kill hook) add the stock score (victim mass x killer 1/mass x 1000).
   Every AI death adds a death, and -500 (floor 0) when nobody gets the kill. A host migration keeps the rows, because every
   joiner already holds them.
5. **Every arena:** when a network game loads one of the 15 stock arenas, every machine adds 7 parked AI cars to the arena's
   object list right after the stock walk. The loader's own OBJ handler `0x4b7ac0` builds them, so the indices are the
   same everywhere. The AI fill brings in NO. DRIVERS minus humans of them. The files on disk stay stock.

## 2. How it works, in detail

| piece | what | where |
|---|---|---|
| respawn timer | host, from the pump (the network pump is where the stock 'SR' handler spawns human cars), one respawn per call; a car is dead from the first pump that sees it dead; spawn point = the one farthest from every live car, at least 30 m clear, else wait | `aim_respawn_tick` |
| rebuild | `0x4513c0(spawn point, 0, label lo, hi, isPlayer 0)` (the label is the `.vcf` stem with instance bits; `0x4ad640` strips them), label-table entry := new car, wreck removed (`0x4575d0` -> `0x465310`), team list via `mpf_move_team`, owner id := row id, the aimelee per-car slot reused (skill and the LAB HP cut are applied again) | `aim_recreate` |
| joiner | in `coop_ai_apply`, before the mirror: host record "alive" (flags bit 8 clear) and local copy dead -> `aim_recreate` at the spawn point nearest the wreck | `aim_at_revive` |
| AI fill + respawn | a human joining parks a WRECK first (it is out of play anyway), else the live AI farthest from humans; a human leaving brings back a live parked car, else rebuilds a parked wreck at the spawn point | `mpfill.c` `mpf_fill_tick` |
| rows | built from slot 15 down (`0x4541b0` gives humans the lowest free slot), `[0x541068]` counted (the scoreboard `0x451f10` prints that many rows; the end-of-match file `0x4524e0` uses it too), flags = team << 16 \| 2 (bit 1 = "team read", so `0x455230` never asks ANet for a fake id), last-heard = now (so `0x454e60` does not wait), latency -1 (so `0x454340` never elects one host) | `aim_rows_tick` |
| row presence | host: car not parked. Joiner: 'AT' byte 3 = 0x80 \| team \| 0x40 when parked (the byte carried the team since MP-TEAMS; older proxies only read the team) | `aim_at_team` |
| scoreboard box | `0x451ac0` makes a 9-line text box (header + 8 rows); in an AI arena it is made with 15 lines (`I76_AIMELEE_BOX_LINES`, the immediate at `0x451b02`, from the call at `0x452d9f`) | `aim_box_create` |
| pool injection | after `0x4b7a90` returns (call at `0x4b45bf` in the ODEF handler), 7 records `{label, identity rotation, (-9000 + 25 i, 0, -9000 + 25 j), mp_pool tag kind 1 + parking spot, class 1, team 7}` go through `0x4b7ac0`. Only in a network melee (`[0x541030]` set and `[0x501818]` clear, as measured at parse time) and only m01..m15.msn. The cars are a fixed pick per arena from the 66 ZFS multiplayer variants | `aim_odef` |
| injected tags | `mpf_load` takes them from memory, starts them PARKED and hides them once (engine off); fill N = the host's NO. DRIVERS (shell `0x100f1f50`) | `mpfill.c` |
| mismatch report | joiners send 'AV' {id, pool size} every 5 s; the host prints "<name> has no AI pack: no computer cars on his screen" once for a human silent for 15 s | `aim_av_tick` |

Not changed: lock targets on AI cars are still not carried across machines. 'SH' / 'ST' name a target by owner id, and
`player_LookupById` of an AI row id gives no car (before, id 0 gave a free slot's stale pointer). The HUD target label now
shows the AI's name (`0x45bc20` reads the owner id).

## 3. The slot limit

- **Player table: 16 slots.** ANet's session holds at most 8 humans (NO. DRIVERS 8, "Game full!" beyond), and the
  AI cars are at most 7 (pool). So humans + AI <= 15 always fits, and no AI row is ever dropped for lack of a slot (the code
  logs it if it ever happens).
- **Scoreboard box: 8 rows in stock** (`0x451ac0`: 9 lines). With the default fill (N = NO. DRIVERS in the stock arenas,
  pool + 1 in `ai_*.lvl`) humans + AI in play never exceed 8, so every row shows. With `I76_AIMELEE_FILL` set higher, the
  box is made with 15 lines in AI arenas.
- A parked AI (the fill gave its place to a human) gives its row back; its numbers are kept and come back with it.

## 4. Phase 1 measurements (PC, headless lab copies)

**Harness.** `i76-uncap-lab\tools\airespawn\airespawn.py` on the overnight lane's `mpo.py` / `mx.py`: lab copies
`game-mpo-c` (host), `game-mpo-d` (joiner), `exp-airespawn` (third, made for this lane from game-mpo-d with its own IPXWrapper
instance K), private desktops, `I76_MUTE=1` + per-pid mute watcher, `I76_SHM_SUFFIX` per copy. Lab twin proxy
`builds\airespawn-20261020\Strlkup-r5.dll` (02ebb30c = the working tree of this lane at `747609a` + the lab click block).
Test switches (LAB only, never in a pack): `I76_AIMELEE_TEST_HP=1` (AI at 1 % chassis), `I76_AIMELEE_TEST=1` with a per-copy
control file `aimelee-test.txt` "shoot S ownhp N" (every S s the local car is put 14 m behind the nearest live AI and holds
its fire keys for 1.5 s through the exe's GetAsyncKeyState slot; N cuts the local car to N % at each spawn),
`I76_AIMELEE_TEST_SPLIT=1` + `I76_AIMELEE_TEAMS=1` (AI #1 on team 6, so AI also fight AI).

**Isolation (found on the way).** The first session's joiner joined ANOTHER lane's session (`exp-difficulty`, m04) for
about 40 s: `exp-difficulty` / `exp-difficulty-b` carry the IPXWrapper instances E / F of game-mpo-a / -b (same DLL md5), and
all four instances used UDP 54800 on the Hyper-V adapter. Since then this lane uses only G / H / K, moved to UDP 54810
(`HKCU\Software\IPXWrappeG|H|K` port; G / H before: `tools\airespawn\state\*.reg`), and every join checks the session (same
mission, same host id) and leaves at once if it is another one (it did, 3 times, all against this lane's own copy k).

| check | result | n |
|---|---|---|
| (a) a dead AI is back after ~5 s at a spawn point on both screens, no reload | **21 respawns** (2 sessions, Hope Springs (6 AI)): host respawn 5.0-5.1 s after the death, at a spawn point; the joiner's copy rebuilt 0.03-0.20 s after the host's; at the next 5 s status stamp the car was live on both screens, 0.0-3.0 m apart (median 0.2), 1-74 m from the spawn point it started at (it drives off). No wave line, no reload line on either copy. Killed by: host shots, joiner shots, other AI, collisions | 21 deaths |
| (b) rows agree: host's and joiner's tables, AI rows with kills / deaths / score | **every phase end: identical** (id, kills, deaths, score) on host and joiner. Sampled every 3 s during play: 246 of 248 samples identical at once (the 2 others were a kill read between the host's write and the next 'AT', 100 ms) | 2 sessions |
| (b) kinds of kill | host kills an AI: 3 ("... was destroyed by Unnamed", host +1 kill and the stock score on both screens); joiner kills an AI: 3 (credited on the joiner's own slot via 'AK', the AI row +1 death on both); AI kills the joiner: 5 (AI row +1 kill and the score, the joiner +1 death, no -500); AI kills the host: 5; AI kills AI: 6 (killer row +1 kill, victim row +1 death); AI dies with no killer: 7 (+1 death, -500, floor 0) | 3-7 per kind |
| (c) a human joining takes an AI's place, leaving gives it back | Hope Springs (6 AI): host alone 1 human + 6 AI rows; B joins 2 + 5 (the farthest AI parked and its row gone on BOTH screens); C joins 3 + 4 on all three; C leaves 2 + 5 again, rows identical on every copy each time | 2 sessions |
| (d) host hard-killed: the new host continues respawns and rows | A (host) killed by TerminateProcess after kills; B became host (reconcile: the 2 parked fill cars counted parked), B and C kept every row's numbers (no row lost a kill or a death), the new host respawned 2 AI each time and C rebuilt them (6 and 3 revives), rows identical on B and C afterwards | 2 sessions |
| (e) TEAM PLAY on (A Grey Hounds, B Puce Panthers) | AI rows on team 7 = Men In Black on both screens, exe team play 1 on both; the team sums (rows of each team added) identical on both screens: Grey Hounds 1287 (the host's AI kill), Men In Black 0, Puce Panthers 0. No AI kill of a human happened in that session, so an AI team sum above 0 was not seen in team play (the rows that build it were seen in (b)) | 1 |
| (f) MAX SCORE reached by a human | limit 1500 poked; the host's 2nd AI kill: winner id = the host on host and joiner, both left the arena 10 s later (stock end) | 1 |
| (f) MAX SCORE reached by an AI | limit 400; AI #5 killed the host (+955): winner = the AI row id 32260 on host AND joiner ("... has reached the maximum score" with the AI's name), both copies ended the match (game state 3). A first try with the host alone gave the same | 1 (+1 host only) |
| crashes in all of the above | 0 crash lines, 0 Windows error reports from these copies | 13 sessions |
| (g) soak | section 6 | |

## 5. Phase 2: AI in every arena

**Options weighed.** (a) Generate AI versions of the 15 arena files: works the way `ai_hs*.lvl` does, but a stock file name
overridden by the pack is what broke a Deck joiner on 2026-10-18 (MULTIPLAYER.md), and new names would double the list.
(b) Cars made the way a human's car is made (a fake ANet player per AI): needs a second local player id on the host, the
NVCL `.vcf` exchange and 'ST' / 'SH' sent per bot. The design note AI-MELEE-AND-LATE-JOIN section 1 sized it at 30-50 h on
untried paths. Rejected. (c) **The owner's point taken literally:** the cars do not need to be in the file, because every
car is built at load from a record. So the proxy appends the records itself, on every machine, at the same point of the
load. Chosen: no file changes, the stock list stays, and a legacy host (`--legacy-multiplayer` sets
`I76_AIMELEE_ARENAS=0`) gets the stock game that a stock joiner can play.

| check | result | n |
|---|---|---|
| all 15 stock arenas boot with the pool | host alone, NO. DRIVERS 4: **14 of 15** "7 of 7 AI pool cars built after the arena's objects", 3 AI rows + the host, the 3 AI live at spawn points (not at the parking ground), 4 parked; m01-m07, m09-m15. **m08 (Creeper Canyon) not measured:** with or without the pool, the headless host in m08 runs no mission frames (no status line at all in 60 s, n 2 + 1 with `I76_AIMELEE_ARENAS=0`); the AI-MELEE-M1 stock-arena check had the same gap for m08 | 15 + 3 |
| AI count = NO. DRIVERS minus humans, on both screens | section 5.1 table | 2 per cell |
| the injected objects get the same indices on host and joiner | label table m04: host 34 = joiner 34 (27 stock + 7); every row id / 'AT' label agreed on both screens in every 5.1 cell | 18 sessions |
| a joiner without the pool | **an older proxy** (the teams lab twin 8dc04f03) or this proxy with `I76_AIMELEE_ARENAS=0` joins a pooled host: he gets in (same file, the CRC check passes), his label table is 27, he sees no AI cars and no AI rows, and **the host's message line says "Unnamed has no AI pack: no computer cars on his screen"** after 15 s. A legacy host (ARENAS=0) with a pooled joiner: no AI anywhere, the joiner's 7 cars sit parked at -9000,-9000, nothing shown | 1 each (3) |

### 5.1 Three arenas x three NO. DRIVERS (host + joiner)

Host `game-mpo-c` hosts with NO. DRIVERS poked into the host form (the value its + / - buttons set), `game-mpo-d` joins and
then leaves by the stock end-of-session exit. Census = humans + AI rows in the player table of each copy (the scoreboard's
rows), checked against max(0, min(7, D - humans)); rows compared id by id between the two copies.

| arena | NO. DRIVERS | host alone: AI rows (want) | B joined: host / joiner (want) | B left: host (want) | n |
|---|---|---|---|---|---|
| Suburbia (m04, town) | 2 | 1 (1) | 0 / 0 (0) | 1 (1) | 2 of 2 |
| Suburbia | 4 | 3 (3) | 2 / 2 (2) | 3 (3) | 2 of 2 |
| Suburbia | 8 | 7 (7) | 6 / 6 (6) | 7 (7) | 2 of 2 |
| The Crater (m01, desert) | 2 | 1 | 0 / 0 | 1 | 2 of 2 |
| The Crater | 4 | 3 | 2 / 2 | 3 | 2 of 2 |
| The Crater | 8 | 7 | 6 / 6 | 7 | 2 of 2 |
| Hope Springs (m07, roads and hills) | 2 | 1 | 0 / 0 | 1 | 2 of 2 |
| Hope Springs | 4 | 3 | 2 / 2 | 3 | 2 of 2 |
| Hope Springs | 8 | 7 | 6 / 6 | 7 | 2 of 2 |

18 sessions, every step as wanted, the AI rows identical on host and joiner at every "B joined" step, 0 crash lines. The
joiner's own log: "7 of 7 AI pool cars built" with the same label-table size as the host's in every session.

**Boots during another lane's fps lock.** From 23:21 to 00:02 this lane booted copies while the rc-draw lane held
`.fps-lock` (all15, the skill-2 study, the mismatch cases, the arena cells). Those runs used CPU on the PC during rc-draw's
fps measurement, and its fps runs of that window are contaminated (reported to main). The lane's harness now waits for the
lock before every boot.


## 6. Soak, and three bugs found after it (2026-10-21)

**Soak 1** (`airespawn.py soak`, lab twin `Strlkup-f1lab.dll` = `ec59784`, 20 cycles 00:39-01:45, the harness waiting for the
fps lock first): each cycle boots host + joiner, 60 s with the scripted shooters and both cars cut, the joiner killed hard,
10 s, re-boot and re-join, 30 s more; arenas in turn Hope Springs (6 AI), Suburbia, The Crater, Hope Springs (stock + pool).

| | result |
|---|---|
| boots, joins, re-joins | 20 / 20 / 20 |
| crash lines | **0** (40 game sessions, 20 hard exits, 20 re-joins) |
| AI respawns (host) / joiner rebuilds | 134 / 20 |
| wave or reload lines | 0 |
| AI rows identical on host and joiner at the end | **19 of 20.** Cycle 19 (Hope Springs with the pool, after the re-join): the joiner showed the right numbers under the next car's id |

**Bug 1, found by the soak: an AI's number drifted on a joiner.** Row ids and names came from a live count of the AI cars
in the label table. On the joiner, a parked wreck stopped counting as a car, every later car's number moved down by one,
and its row took the next car's id (and name). Fix (`cdd69f7`): the numbers are counted once per mission load, when every
AI car is whole on every machine.

**Bug 2, a second hosted session in the same game process crashed** (found by the polish lane). Reproduced: Suburbia
(pool), leave by the stock exit, host Hope Springs (6 AI) from the same process: `0xC0000005` at `Strlkup+0x240e7` reading
`0x0DFC0258`, 2 s into the second session (n 1 of 1; the orders Hope Springs (6) -> Suburbia, (6) -> (4) and a
migrate-then-rehost did not crash, n 1 each). Cause: the AI fill kept the first load's label-table pointer with its tags.
`mpf_obj` / `mpf_near_car` read it during the second load, before the tags were reloaded. Phase 1 made it reachable on
every 'AT' round, because the parked flag in 'AT' byte 3 asks `mpf_parked_obj`. Fix (`cdd69f7`): `mpf_obj` returns
nothing unless the tags belong to the current table, and the free-spawn search reads the current table. Measured on the
fixed twin before the session problem below: Suburbia -> Hope Springs (6 AI) 3 of 3 without a crash (6 AI rows after the
second load), migrate-then-rehost 1 of 1. Every soak cycle now ends with a second hosted session (A leaves and hosts the
next arena, B joins it, 20 s).

**Bug 3, `I76_COOP_AI=1` crashed a single-player game on a re-placed car** (found by the jump lane, TICK-FINISH s.20.7:
direct T05 boot with the RC presets, the second trainer re-placement, every boot). `coop_ai_log` (after each fps line) walked
the label table and read an object the game had freed when it rebuilt the car. Fix (`32a5b04`): `coop_ai_log` does
nothing outside a network game, and `coop_ai_object` skips a label whose object or entity cannot be read. **Not yet
measured** (next paragraph).

**Why the 2026-10-21 runs stopped.** From 06:42 every boot of every lab copy hung before the first mission frame. The main
thread waited in `MMDevApi.dll` / `AUDIOSES.DLL` (resolved with `tools\airespawn\mods.py`), because the PC's session was
**RDP** (`rdp-tcp#14`, TerminalServerSession True, the only working audio endpoint "Remote Audio"). AGENTS.md: no launch
result is valid under RDP. The harness now waits while the session is RDP. The runs after 06:42 (second sessions on the
fixed build, migrate-then-rehost, soak 2) did not run and are not counted. `tools\airespawn\chain7.sh` holds the rest, for a
console session: the single-player crash on the build before the fix (n 1) and on the staged build (n 5 with the 3
re-placements, n 3 plain mission boots), 5 second sessions, 2 migrate-then-rehost, and the 20-cycle soak with a second
session per cycle.

## 7. AI difficulty: what the skill does, what was measured, what the owner drives

**What nothing touches.** Before tonight the AI skill was `I76_AIMELEE_SKILL` = 3 for every AI car, untied to the options
menu or the player's weapons. The difficulty lane (DIFFICULTY-OPTION-2026-10-20) now ties the host's Play Options difficulty
to it: Wimp 4, Champ 3, Badass 1. `I76_AIMELEE_SKILL`, and so `--ai-skill`, overrides that.

**What the scale changes** (stock tables at `0x40bc70`, read through `0x40bd90`; i76-map `subsystems/ai.md` "Skill values";
**1 is the best, 5 the weakest**):

| skill | steering gain | throttle gain (cap 0.75 + 0.25 x) | aim (projectile lead jitter (1 - aim) x 1.1 x U) | fire gate (guns: 3 x rand%1000 < 6000 x fire) | aggression level (= skill - 1): flees when hurt below |
|---|---|---|---|---|---|
| 1 | 1.0 | 1.0 | 1.0 (no jitter) | 1.0 | 30 % health (level 0) |
| 2 | 0.8 | 0.8 | 0.8 | 0.9 | 47 % |
| 3 (default) | 0.6 | 0.6 | 0.6 | 0.8 | 64 % |
| 4 | 0.5 | 0.5 | 0.4 | 0.7 | 81 % |
| 5 | 0.4 | 0.4 | 0.2 | 0.6 | 98 % |

The aggression level also picks the row of tactic weights in the attack selector (ai.md M17).

**Measured** (`airespawn.py skill`, copy exp-airespawn, Hope Springs (2 AI): the fill gives 2 AI against 1 human; A = the
human sits still at full strength for up to 180 s; B = god mode, the LAB shoot test every 5 s at full-strength AI):

| skill | hits on the human / min (each run) | human killed after (s) | B: first AI kill (s) | B: AI kills in 180 s |
|---|---|---|---|---|
| 1 | 11.4, 1.0, 6.7 | 111, -, - | 43, 17, 8 | 11, 10, 9 |
| 2 | 3.7, 14.4, 0.0 | -, 113, - | 36, 8, 17 | 8, 9, 8 |
| 3 | 22.5, 18.9, 0.0 | 83, 95, - | 17, 14, 8 | 8, 12, 5 |
| 5 | 0.3, 0.0, 1.3 | -, -, - | 7, 7, 17 | 7, 9, 8 |

n 3 per skill. Two skill-5 runs had a lab joiner wander into the session for a few seconds (the isolation note in section 4).
**Reading:** skill 5 is clearly weak (about 1 hit a minute, no kill). Between 1, 2 and 3 the spread inside a skill is larger
than the difference between skills: what decides a session is whether the AI close in at all. They often hold 150-190 m
off (AI-MELEE-M1) and then hit nothing. The B column measures the scripted shooter, not the AI. This harness cannot drive
a car like a person, so "time for a human to kill an AI" in real play is not measured.

**What the owner drives vs what the AI draw.** The AI cars are the stock AUTO MELEE pick: a random multiplayer car variant
from I76.ZFS, 66 cars. Their points split 18 x 1600, 18 x 3200, 18 x 4800 and 12 x 6400; their armour totals run 640-3200,
median 1640. The owner's car (his garage car `ADDON\vehscn.vcf`, the same in the daily driver and the LAN copy) is a
**Piranha with 4800 points: armour 900/600/600/700 = 2800, chassis 2000**, two 50 cal, FireRite rockets and an oil slick. Only
12 of the 66 AI cars have that much armour. With the stand-off and skill 3 that explains "spanking", and the respawn now
brings every beaten AI back.

**Recommendation:** keep skill 3 as the default. Say Champ in the menu, or `--ai-skill 3`. Note that the owner's copies are
on Wimp, which the difficulty lane maps to 4, which is easier. For a harder game use `PLAY-LAN.bat --ai-skill 2` or Badass
(= 1). The stand-off, not the aim, is what limits the AI. If 1 is still easy, the next lever is the tactic choice (a closer,
ramming behaviour), not the skill number.

**Controls.** `PLAY-LAN.bat --ai-skill N` (pack generator `tools/mp-pack.py`) / `PLAY-i76.ps1 -AiSkill N` set
`I76_AIMELEE_SKILL` for that launch; only the host's value counts. On a Mac the game's environment comes from the app
prefix's `user.reg` `[Environment]` (where `I76_COOP_AI` is): add `"I76_AIMELEE_SKILL"="N"` there. The pack in section 9
carries the proxy only, so on the machines today the host's Difficulty Level decides (Champ = 3), or a
`set I76_AIMELEE_SKILL=N` line in PLAY-LAN.bat.

## 8. Switches (rows in `music-fix/README.md`)

| switch | default | meaning |
|---|---|---|
| `I76_AIMELEE_RESPAWN_AI` | 1 | dead AI cars respawn after `I76_AIMELEE_RESPAWN_AI_S` (5) s; `0` = the M1 behaviour (waves) |
| `I76_AIMELEE_WAVE` | 0 when respawn is on, else 1 | the old wave reload (all AI dead for 8 s -> the arena reloads) |
| `I76_AIMELEE_SCORE_ROWS` | 1 | AI rows in the player table / scoreboard; `0` = names only in the kill message |
| `I76_AIMELEE_BOX_LINES` | 15 | scoreboard box lines in AI arenas (stock 9) |
| `I76_AIMELEE_ARENAS` | 1 | the AI pool in the 15 stock arenas in a network melee; `0` = stock arenas (also set by `--legacy-multiplayer`); `I76_AIMELEE_FILL=0` also skips it |
| `I76_AIMELEE_TEST`, `_TEST_SHOOT`, `_TEST_OWN_HP`, `_TEST_SPLIT` | off | LAB ONLY (section 4 harness) |

## 9. Pack

`i76-uncap-lab\builds\mp-pack-20261020-airespawn\` (README.md there), **staged, deployed nowhere**:

- `payload/STRLKUP.DLL` **8f8da929** = HEAD `491f8db` (clean `git archive`, MSVC x86 /MT /O2 /Brepro, built twice
  byte-identical, `builds\airespawn-20261020\final3\b1|b2`). It holds this lane's work with the three fixes
  of section 6, the Macs' 0ce90a90 change (`I76_MENU_PTR`), and every lane's later commits: the difficulty mapping
  (Wimp 4 / Champ 3 / Badass 1; the owner's copies are on Wimp), the menu-sound-polish switches, the rc-draw terrain
  switches (default off), and the nitro-port lane's stage 1 (exe detection). **This exact build is not measured
  yet:** the lab numbers above ran on `ec59784` / `cdd69f7`; `chain7.sh` runs on its lab twins (`Strlkup-f3lab.dll` ccbe3694
  for multiplayer, `jfstyle\Strlkup-head-lab.dll` 850e16ef for single player).
- The ADDON files `ai_hs2/4/6.lvl` (+ markers) are moved out (no special AI entries any more).
- `deploy-pc.ps1` / `rollback-pc.ps1` (PC LAN copy), `apply-airespawn.sh` / `rollback-airespawn.sh` (laptop, Andrew's and
  Michael's Macs, the Deck; the game folder is the argument). Everything is saved to `<game>/_rollback/airespawn-20261020/`.
  Both pairs were tested on a dummy folder: apply, apply again (verify only), rollback, and every file md5-identical
  afterwards (the Deck's lower-case `Strlkup.dll` too).
- `MD5SUMS` lists every file of the pack.
- Every machine at once (arena list + pool). No launcher changes: `--ai-skill` and `--legacy-multiplayer` reach the machines
  with the next launcher set.

## 10. Open

- **The staged build 491f8db is unmeasured**, and so are the single-player crash fix, the second-session fix beyond
  n 3 + 1, and the soak with second sessions. `chain7.sh` covers them; it needs a console session (no RDP) and no
  `.fps-lock`.
- Nothing between two machines; the pack is staged, not deployed.
- m08 (Creeper Canyon; headless: no mission frames with or without the pool) is not measured.
- Lock targets on AI cars across machines (owner id lookup gives no car).
- AI team sum above 0 in team play not seen (no AI kill of a human in that session).
- Skill: real-play kill times need a person; the stand-off behaviour is the bigger lever.
- The skill-5 runs 0 and 1 had a few seconds of a stray lab joiner.
- Boots during the rc-draw lane's fps lock (2026-10-20 23:21-00:02, section 5.1) contaminated its fps runs of that window.
