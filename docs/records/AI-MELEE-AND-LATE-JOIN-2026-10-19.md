# AI cars in network melee, teams, and joining a game in progress (2026-10-19, paper only)

Owner, 2026-10-19: *"i don't see why we couldn't combine the network multiplayer with the ai melee modes and add ai
players to both; shouldn't most of the code be there for that? also would be super cool if people could join games in
progress on the network without waiting for a round to start no? ... maybe a simple way to do the ai multiplayer
without ui changes would be to have all the empty player slots populated by ai cars, naming them ai cars, and kicking
them when humans join? how to handle teams though?"*

Static reading only: nothing was run. Exe addresses are the 9a232dcc Ghidra export in `<re-archive>\ghidra\export` (same
addresses in the LAN copy's 6319abf7 outside the diff clusters); shell addresses are i76shell.dll at base 0x10000000
(`<re-archive>\shell\ghidra\export`). "Measured" means a record in this repo measured it; everything else is read from code.

**Short answers.**
1. Most of the code is there, but not where the owner's idea puts it. A driver slot is an ANet player. Making a bot
   out of one means faking a second remote player on the host, and that is the expensive path. The cheap path is the
   one the co-op scenes already use. The AI cars are **objects in the arena file**. The host runs them and the
   existing 'AT' sync shows them to everyone. The only new piece is a small host tick that sends every AI car after
   the nearest human. No driver slot is used and nothing in the UI changes: the arena list gets entries like
   "Hope Springs 4 AI".
2. Teams come almost for free. A car's team is 3 bits in its object flags. AI cars take theirs from the arena file.
   Humans take theirs from their team pick. The new tick only has to attack cars of another team.
3. Yes. Stock AUTO MELEE / INSTANT MELEE spawns 1..7 computer opponents. Its spawner cannot be reused as is in a
   network game (section 3), but its rules (waves, skill, attacker cap) are the model to copy.
4. **Joining a running melee already works in the stock game**, and it has been measured here. Stock melee has no
   rounds: it runs until MAX SCORE, if that is set, and then ends the session. What could be added is a "next round
   in the same session" instead of the session ending.

## 1. AI opponents in network melee: (a) bots in driver slots vs (b) AI cars in the arena file

### What a driver slot is (the reason (a) is expensive)

- **Player table** 0x541070, 16 x 0x48 (`<re-archive>\subsystems\network.md`): dp id, name, flags +0x1c (bits 16..18 =
  team), .vcf name, vehicle object +0x28, kills / deaths +0x3c / +0x3e, score +0x40. There is one local id,
  0x541028.
- **Every other slot is a remote car.** The spawn 0x451180 flags it remote (object+0x10 0x20) and the mirror 0x464890
  drives it from that player's own 'ST' packets. Nothing in the exe runs AI on a player-table car.
- **Scores are written by the owning machine.** The victim's machine counts its own deaths (0x455130, -500 for a
  suicide) in 0x463a80. Kills and score go to the killer's own slot through 0x454ff0 (kill x victim/killer mass x
  1000). The other machines copy a remote's kills, deaths and score out of that player's 'ST' through 0x454ea0, which
  also runs the MAX SCORE test.
- **NO. DRIVERS is the session size.** The shell's count is 0x100f1f50. The + button of the entry form 0x10028610
  (case 9) caps it at 8, and the net host form defaults it to 4 (0x10027f20). A join past it gets "Game full!"
  (measured: LAN-MATRIX section 9, the 5th player).

### Comparison

| | (a) bots in empty driver slots, kicked when a human joins | (b) AI cars in the arena file, run by the host |
|---|---|---|
| spawn | needs an ANet player per bot, created on the host (the exe assumes ONE local id 0x541028); the 'SP' spawn with .vcf bytes and the NVCL car-CRC exchange per bot | **exists**: `bwd2_h_OBJ` 0x4b7ac0 builds every ODEF car when the arena loads, on every machine; label table 0x54a178 entry via 0x457610. The ODEF builder exists (`tools/coop-mission.py`, byte-exact BWD2 round trip) |
| sync to joiners | the host must send 'ST' / 'SH' **as each bot's id**, and stop its own mirror 0x464890 from overwriting the bot it is driving | **exists**: `I76_COOP_AI` 'AT' export of every label-table vehicle (~10/s, 2 per packet), fire masks replayed, local damage blocked on joiners, destroyed flag mirrored. Not gated on co-op files: it runs in any network game (`coop_ai_role` / `coop_ai_object`, strlkproxy.c ~2969) |
| AI driving | a car the exe treats as remote has no AI decisions (`ai_FrameTick` 0x40a320 walks the team lists; remote cars are mirror-driven) | **exists**: the host runs `ai_FrameTick` for mission cars (that is how co-op works) |
| targeting all humans | new | **exists**: `coop_ai_attack` sends every behaviour aimed at a human (except follow) to the nearest live human of the 16 slots, on all 9 `ai_SetBehaviour` sites including the melee tick's 0x40a232 |
| who tells the AI to attack | new | **missing, small**: an arena without a script gives the cars nothing to do. In `ai_FrameTick` the host calls its own tick in place of `fsm_RunMachines` (the branch at 0x40a320 that tests 0x401310): for every live car in the 8 team lists 0x507da0 / counts 0x51f5d0 that is not in the player table, `ai_SetBehaviour(car, nearest live car of another team, 0 = attack)`. That is `ai_MeleeFrameTick` 0x40a130 without its two flaws (next row and the "skip humans" rule) |
| host death ends the round | no | **avoided by not calling 0x40a130**: it sets outcome 0x51f5fc = 1 when the world root's object+0x10 has 0x200 (dead) and ends the mission 5 s later through 0x402620. Co-op's ending comes from the scripts and the chain, which key only on `coopNN.lvl`. A melee arena has neither, so a host death stays a stock melee death |
| AI respawn | the bot's own respawn ('SR' 0x456970, run by the host for it) | **missing**: a spawned car is NOT in the label table (0x4513c0 / 0x451180 never call 0x457610), so 'AT' cannot carry a new car. Options: (1) **wave**: when every AI is dead, reload the arena in the same session with the chain's 'AM' reload (exists, measured for co-op losses n 2+). This is the network form of the stock wave (section 3). (2) **reserve pool**: the file holds 2N cars and N are parked off-field. When an active car dies, the host moves a parked one to a free spawn point (0x451030 picks one). The label set never changes |
| scoreboard credit for AI kills | **free**: a bot victim is a player, so 0x463a80 / 0x454ff0 credit the killer | **missing**: in a network game 0x463a80 credits only player victims. Host: record the last attacker per AI car at 0x463a80, and on its death send 'AK' {killer id, mass ratio}. The killer's own proxy adds to its own slot (+0x3c, +0x40) and runs the MAX SCORE test as 0x454ff0 does. Optional chat line "AI Torque Daisy destroyed by the developer" through 0x453df0 |
| AI names on screen | free: they are players | the scoreboard 0x451f10 lists the player table only. Fake rows there are risky (retargeting, spawning and the mirror all walk it). Use chat lines or a proxy overlay |
| AI loadout | the bot's .vcf, sent like a player's | the ODEF label names the .vcf, loaded from each machine's own files. Use **mission cars in I76.ZFS only** (stock on every pack machine, md5 6dd57b16). The .lvl CRC does not cover an ADDON .vcf, and ADDON .vcf files already differ between machines (the Deck's and the M2 tester's `valepre4.vcf` 4ed297ca) |
| "kick when a human joins" | dpDestroyPlayer / 'd2' before ANet admits the joiner, or NO. DRIVERS must be raised to make room; tear-down on every machine | not needed: AI cars use no driver slot. If wanted: keep N + humans constant by **parking** one AI per joiner (no removal: removing an object breaks the 'AT' label index) |
| teams | the bot's flags +0x1c bits 16..18, so team scores (0x452930) include bots | ODEF team field -> object+0x10 bits 16..18; AI team scores are not counted (no player-table row) |
| size | **30-50 agent-hours**, mostly in protocol paths never exercised by more than one player per machine | **M1 ~8 h, everything ~20 h** (section 5) |
| risks | ANet behaviour with several players on one machine (untested); joiners' mirrors for bot ids; the 'Game full' race; host migration hands every bot to a joiner's machine | host migration (seen 2026-10-18: ANet made the Deck host): the new host's proxy turns host role and would start running mirrored copies whose state is untested. 'AT' load with more than 2-5 cars in a fight is not measured (the co-op runs had 2-10 cars). `I76_COOP_DAMAGE` scales human-vs-human damage too: leave it unset in melee |

**Recommendation: (b).** It is the co-op scenes with a melee arena in place of a campaign mission. Every network
piece is already measured across machines (joins, 'AT', fire replay, reloads, CRC check of lower-case `.lvl`). The
new code is one host tick, then kill credit, then respawn. (a) buys bots in the roster and team score, at several
times the cost, on code paths nobody has run.

## 2. Teams

**Stock team play (humans).**
- **The flag.** TEAM PLAY is bit 3 of the setup word. 0x452db0 copies it to 0x541010, read by `FUN_00452e10`.
- **Who picks.** Each player picks a team. The pick travels in that player's ANet player data: byte 1 = team + 1,
  parsed by shell 0x10015b90. The roster names the team (shell 0x10022e50) from the table at shell 0x1004b920.
- **The names** (exe table 0x4c2130): Grey Hounds, Puce Panthers, Crimson Kings, Yellow Jackets, Aqua Marines, Mauve
  Mayhem, Mr. Brown's Clowns, Men In Black, Red Dawn, Gang Green. Only 3 bits are kept, so 8 teams are usable.
- **Into the game.** The exe keeps the team in player flags +0x1c bits 16..18. The network spawn 0x451180 ORs those
  bits into the car's object+0x10 bits 16..18.
- **Scores and the win.** With team play on, the standings (0x451f10) and the MAX SCORE test (0x454ea0 /
  0x454ff0 -> 0x452930) sum the scores by team. WinMain prints "Team %s has reached the maximum score!".
- **Not read:** which form control sets the team byte, and whether team play stops friendly fire between humans.

**How mission AI decides friend or foe.**
- **The field.** It is the same 3 bits. The ODEF team field (+0x62) is copied to object+0x10 bits 16..18 (mission.md,
  `isWithinEnemy`). The T05 file has the player and Taurus on team 1 and the gang on 2. The stock multi-melee spawner
  0x4513c0 sets AI = team 2 and the player = team 1 | 0x10.
- **What reads it.** Gun fire holds only for a same-team car in the line of fire (ai.md C19, `& 0x70000`). Targets
  come from the script, or from whatever the tick hands out. The AI never picks a target by team on its own.
  `allEnemyDead` and `isWithinEnemy` are script tests.

**Smallest way to put AI on teams.** The new tick compares teams. It attacks the nearest live car whose bits 16..18
differ from its own, humans and AI alike (AI-versus-AI attacks have no attacker cap, ai.md "on deck"). So:
- **humans vs AI:** all AI cars carry one team index in the arena file (say 7, Men In Black), and the humans play
  on any other.
- **mixed teams:** AI cars carry a human team's index and fight beside the humans who picked it. The same file and
  tick cover it. The file sets the AI split, for example "Hope Springs 2+2 AI" = two on Grey Hounds, two on Puce
  Panthers.

**"3 humans vs 3 AI", concretely:**
1. An arena file with 3 AI cars on team 7, placed away from the 19 spawn and regen points. A point is blocked within
   the vehicle radius + 20 m (0x451030).
2. The host ticks TEAM PLAY, NO. DRIVERS >= 3, and all three humans pick one team other than Men In Black.
3. The host's tick sends the AI at the nearest human; the humans' guns are stock.
4. When the last AI is dead the wave reloads, or reserves come in.
5. The scoreboard shows the human team's score only. Kills of AI count once 'AK' exists (M2). Before that the AI
   kills nobody gets credit for, and MAX SCORE cannot end the game.
6. Without team play the humans can also shoot each other: that is melee as stock.

## 3. AI in single-player melee (stock): yes, and how it works

- **Shell.** MELEE > AUTO MELEE opens the entry form (play mode 3). INSTANT MELEE (button id 4) starts at once with
  the default roster: 2 drivers = you + 1 AI. The EMU records ran it as "Instant Melee, The Crater, 1 AI".
  `EntryForm_InitDriverRoster` 0x1002af00 fills each AI slot with a random name from the 53-name table 0x1004b438
  ("Torque Daisy" ...) and a random car (rand() % car count 0x100f21ac, a garage record 0x8c4 bytes). In auto-melee
  mode (0x100d217c == 0) the form's + adds one more random driver, up to 8 in all = 7 AI (`DAT_100f1f50 < 8`). On GO,
  `MultiCarDef_Save` 0x10009010 writes MULTICAR.def: u32 count + 0xEB-byte records.
- **Exe.** Mode 3 sets 0x501818 = 1 (0x401270). `net_LoadMultiCars` 0x401000 then runs these steps:
  - it reads MULTICAR.def;
  - for each record, shell callback 08 writes `NVCL\nvcl%1x.vcf`;
  - it spawns the car through **0x4513c0(0x451030() = a random free spawn point, 0, name, isPlayer 0)**. That is the
    spawn-point code network players use (0x451180 is its network twin);
  - skill 3 for everyone (0x40a270 -> ai+0xa818 = 2);
  - the player's attacker cap 8 (0x40c0a0 -> ai+0xa948).
- **Every frame.** `ai_FrameTick` sees 0x501818 and calls `ai_MeleeFrameTick` 0x40a130 in place of the script, so
  every live car attacks the world root. A kill gives the player +1 kill and + victim/player mass x 1000 (0x401280,
  called from 0x463a80). The standings are one row (0x451ac0).
- **Waves** (0x401340, an entity-removed callback registered by 0x401000 through 0x457290; disassembled for this
  note). When the last AI car is removed, the whole roster respawns at random spawn points. The skill argument drops
  by 1, floor 1, and the player's attacker cap rises by 1 each wave.
- **The player's death** ends the melee 5 s later (0x40a130, above).

**Reuse in the network game: only the rules, not the code.**
- **0x401000 sets 0x501818.** That flips the standings to the one-row single-player list (0x451ac0 / 0x451f10) and
  routes the AI tick to 0x40a130, so the host's death would end everyone's game.
- **NVCL collision.** 0x401000 unlinks `NVCL\*.vcf` and writes nvcl0..N. That is the same name space the network
  join uses for the players' cars (0x455de0 / 0x455e60 write nvclN.vcf). AI cars would overwrite joiners' car files.
- **No labels, so no sync.** The cars 0x4513c0 spawns get no label, so 'AT' cannot sync them. Joiners would need a new
  spawn packet and a new index.

Calling 0x4513c0 directly from the proxy avoids the first two problems but not the third, and that costs more than
putting the cars in the file. What carries over: the wave rule, the skill levels 1..5 (0x40a270 accepts 1..5) and the
attacker cap.

## 4. Joining a game in progress

**What the stock host does with a join while playing.**
- **There is no lobby and no session close.** The host goes straight into the arena (MULTIPLAYER.md section 5).
- **Accept or prompt.** The join request 'RE' 0x4568f0 accepts at once with 'JO' 0x455fa0 if setup bit 2 (0x541018,
  via 0x452db0) is set. If it is clear, the request is queued for the host's CTRL-Y / N prompt (0x4558c0; 3 = accept,
  else 'JD' 0x4560a0). INVITE ONLY is presumably bit 2 cleared [inferred from the form label].
- **No "in progress" refusal.** No string or test for one exists. The exe strings hold none, and the only refusals
  are ANet's session size ("Game full!") and the shell's mission checks.
- **Measured.** Three players joined the owner's running Suburbia session (LAN-MATRIX section 9, 4 players, n 1). A
  co-op buddy joined ~50 s into T01 (COOP.md). MULTIPLAYER.md section 8 already tells players "Joining while the host
  drives is fine".

**What a late joiner needs, and where it comes from.**

| state | carrier | status |
|---|---|---|
| sim time, mission file, file CRC | 'JO' (+0x32 name, +0x44 CRC 0x504a04), then 'XX' pings every 0.5 s | stock; a `.lvl` name is CRC-checked by the joiner's shell (lower case only) |
| other humans' cars, positions, damage | each player's own 'ST' (0x60 B, incl. damage levels) | stock |
| other humans' kills / deaths / score | inside 'ST', copied by 0x454ea0 | stock |
| destroyed buildings | 'SC' bitmask by load-order index | stock packet; whether the host sends it to a late joiner was not read |
| AI cars (co-op / AI arena) | 'AT' incl. the destroyed flag | proxy, measured late join in co-op |
| objectives | 'AO', replayed once the joiner's car has existed 3 s | proxy, measured (4 applied) |
| radio said before the join | none | not replayed (COOP.md) |

**What the co-op chain's late-join CRC update does.** On a host chain reload the proxy writes the next file's CRC
into 0x504a04, but only when the slot still holds the current file's CRC. Without that, a joiner arriving after a win
would be refused by its own shell's CRC check (COOP-LIST section 2). The cross-machine cell is **not run**
(LAN-MATRIX: "late join after a win: not run").

**What is left.**
- **"True mid-round join"** already exists for melee and co-op. Nothing to build; one cross-machine check for the AI
  arena once it exists, in the M1 test.
- **What the owner may be seeing as "rounds".** With MAX SCORE set, the winning message is followed 10 s later by
  game_state = 3 (WinMain 0x402b30, the `10.0 <= now - t` test after "has reached the maximum score"). The session
  ends and everyone goes back to the shell to host and join again.
- **A cheap "next round, same session".** At that point the proxy resets the slots' kills / deaths / score and
  reloads the same arena with the chain's 'AM' path, which already exists and is measured, in place of state 3.
  Joiners arriving during the reload are covered by the chain's 8 s timeout and held 'AM' (COOP.md).
  **Size ~4-6 h + a LAN test.** Not read: whether the chain reload clears the player table's scores by itself
  (0x452d40 re-initialises the network from the open session). Measure it first.

**Recommendation.** Nothing is needed for join-in-progress; tell the owner it works. If wanted, add rounds that do
not end the session (above), after the AI arena.

## 5. Order of work

| step | content | size | done when |
|---|---|---|---|
| **M1** | `tools/ai-arena.py` (fork of coop-mission.py's ODEF insert): stock arena + N class-1 car ODEFs, team 7, ZFS mission vcfs, distinct instance bits, positions clear of spawn points, title "<Arena> N AI", lower-case `ADDON\aiNN.lvl`; install like coop-install.py. Proxy `I76_AI_ARENA=1` (host, file `ai*.lvl`): the attack tick in place of `fsm_RunMachines`, skip player-table cars, skill from `I76_AI_SKILL` (1..5, default 3), attacker cap 8 on every human. First file: **Hope Springs (m07) with 2 / 4 / 6 AI** (three files; N from the file). No teams, no respawn, no credit | ~8 h (tool 2-3, tick 2-3, two-copies-on-one-PC test 2-3) | lab: host + joiner both see N AI attacking the nearer human, the host's death does not end the game, the joiner kills an AI and it wrecks on both; then an owner LAN night |
| M2 | AI respawn by wave (all dead -> chain reload, the stock rule) and 'AK' kill credit + chat line | ~6 h | AI kills appear in each killer's score on every machine; MAX SCORE reachable by AI kills |
| M3 | teams: the tick's other-team rule (already in M1 if written that way), files with AI on a human team; "3 humans vs 3 AI" | ~3 h + LAN test | TEAM PLAY session with AI allies and enemies behaving by team |
| M4 | optional: reserve pool (continuous respawn), parking one AI per joiner, rounds without ending the session (section 4) | ~4-6 h each | |

**What the owner decides:**
1. Is N set by the file (pick "Hope Springs 4 AI" from the list, no keys), or one file per arena with N from a
   switch? The first needs no setup on the joiners.
2. AI respawn: waves (stock single-player rule; everyone respawns at the reload) or continuous (reserve pool)?
3. When a human joins: keep the AI count (default), or park one AI per joiner (his "kick" idea)?
4. AI names: chat lines only, or worth a proxy overlay?
5. Which arenas besides Hope Springs (Vigilantes' Paradise and Tombstone are the other daylight-and-hills picks,
   LAN-MATRIX section 9), and which skill level to start at.
6. AI cars: which stock mission cars, e.g. the T05 gang `vfcoupe3`, and whether to mix them.
