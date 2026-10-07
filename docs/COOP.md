# Co-op campaign: two players through the Interstate '76 story

*2026-10-07. Built on the game's own network code (IPX, docs/MULTIPLAYER.md) and the proxy (`music-fix/strlkproxy.c`).
Everything below was measured on a Windows 11 PC and a Mac (Wine) on one home network, on test copies, unless it says
otherwise. The development record is [COOP-SPIKE.md](COOP-SPIKE.md).*

## Play it

On **every** machine (each needs the same game data: stock GOG files, stock car):

1. IPX for LAN play: IPXWrapper, [MULTIPLAYER.md](MULTIPLAYER.md) sections 2-6.
2. With the game closed: `python3 tools/coop-install.py "<game folder>"`. It builds the 17 co-op missions from your own
   campaign files and makes the arena "The Crater" start the campaign (the original is kept;
   `--remove` puts it back).
3. Start the game with these environment switches (Windows: `PLAY-i76.ps1` / a .bat `set`; Mac: the wrapper's
   `HKCU\Environment`, as for the other `I76_*` switches):

   | switch | what it does |
   |---|---|
   | `I76_COOP_AI=1` | the host's enemies, their gunfire, kills and radio lines are shared with the buddy |
   | `I76_COOP_CHAIN=1` | won -> both go to the next mission; lost -> both retry; the host plays as the story's hero |
   | `I76_COOP_DAMAGE=0.5` *(optional)* | difficulty for two: each player's weapon damage x 0.5 (0.6 = a bit stronger) |

Then the **host**: MELEE > MULTI MELEE > HOST > IPX, pick **The Crater**, BROADCAST GAME. The **buddy**: MELEE > MULTI
MELEE > JOIN > IPX, select the game, JOIN GAME. Joining a mission already in progress works (measured: joined ~50 s
in); the buddy gets the objectives' current state on arrival, but radio lines spoken before it joined are not replayed. The host drives the story's car; the buddy drives the car picked in the
multiplayer menu, starting beside the host.

## What works (measured)

| feature | how | evidence |
|---|---|---|
| Campaign missions in a network game | co-op mission files: two spawn points beside the hero's start, intro/outro movies removed (a movie stops the network loop and the host dropped the joiner) | both players in T01, T02, T04, T05; the joiner's car moved 142 m in the host's memory while the joiner drove |
| The host is the story's hero | the host's spawn adopts the mission's own player object | label `vppirna1`, network table slot 0 and the world root are one object; enemies attack the host; failing objectives fail the mission |
| One set of enemies | the host sends every mission car's state ~10/s ('AT', 2 per packet); the buddy shows them with the game's remote-car code and runs no AI or script of its own | Taurus/the gang on the buddy's screen within metres of the host's (sampled a few tenths of a second apart); identical positions once still |
| Enemy gunfire on the buddy's screen | the AI's trigger pulls are sent with each car state and replayed | 11,729 replayed trigger pulls in one T04 run |
| Enemies go after the buddy | every AI behaviour aimed at a human (except follow) picks the nearest live human | T05: gang car's target became the buddy's car; with the Mac hosting, the PC buddy took damage (400 -> 370) |
| Kills decided once, shown on both | the buddy ignores damage to shared enemies locally; the host computes every hit (including the buddy's shots, which the game already relays) and sends the result | host's shots: bus destroyed on both screens; buddy's shots: tractor destroyed on the host and then on the buddy |
| Radio (story lines, taunts) | the host's CB lines are queued and sent ('AC'); the buddy plays them | T01: host 10 lines, buddy played 6 (the rest before it joined) |
| Objectives (notepad) | the script's success / fail / reveal actions are forwarded ('AO') and applied on the buddy; a late joiner gets every objective's flags once its car exists for 3 s | T01: host 2 objective events, buddy applied 2; late join: 4 objective states applied |
| Joining late | nothing special: the movies are out of the mission files | buddy joined ~50 s into T01 and played on |
| Next mission / retry | won -> both reload the next co-op mission in the same session; lost -> both reload the same one ('AM' + the game's Replay path, network kept up) | forced win T01 -> T02 on both; script-engine win -> T02; natural losses (host killed, objective failed) retried, several times in a row |
| The whole campaign loads | wins forced through the script engine's success path, one mission after another | all 17 co-op missions (T01..T17) on both machines, 0 crashes; T17's win ends the game normally; the whole chain at 30 s per mission, both machines in step at every mission, one reload each (16/16) |
| Buddy respawns | the buddy requests a respawn by itself 5 s after dying | two self-destructs, a new car each time |
| Difficulty | co-op damage factor | 25 -> 12 per hit at 0.5, for the host's and the buddy's shots |

## Not done / known gaps

- **On-screen text messages** from the script (if any beyond the radio and the notepad) are the host's only.
- **In the first mission of a session the host's car looks like the buddy's chosen model** on the buddy's screen
  (the mission's player object takes the local car file, and the host is not known yet while it loads). From the
  second mission on the buddy loads it from the host's own car file, which the game already received (`NVCL\nvcl0.vcf`;
  measured: buddy "GTA2", host "Jade's Car", reloads show "Jade's Car"). `I76_COOP_HOSTMODEL=0` turns this off.
  Removing the object and showing the host's own network car instead crashed the buddy (the mission code still
  refers to it).
- **Brief host hand-over during a reload:** while the host reloads (a few seconds) ANet may make the buddy host; the
  lower id (the original host) takes it back. Seen once, no harm measured.
- **Max-score option:** not tested on; leave MAX SCORE off (the default). The mission ends the mission, not a score.
  (On the buddy, every mirrored enemy used to write its score into the first free player slot, owner id 0, and in a
  team game that counted toward the max-score check; owner id 0 is now skipped there, 2026-10-07.)
- **A natural full-campaign run** (17 missions played through) has not been done; wins were forced through the
  script engine's own success path.
- **The host crash at a reload (Windows), found and fixed 2026-10-07.** Windows applies a compatibility shim
  (AcGenral) to i76.exe; it replaces the game's heaps with its own, kept in ONE list with no lock. The NVIDIA D3D11
  driver (nvwgf2um.dll, under dgVoodoo) sits in the DriverStore, so the shim treats it as part of the application too,
  and it creates and destroys heaps on its own thread. A driver destroy landing inside a game create left the list
  pointing at freed memory; the next teardown's walk (`HeapDestroy`, chunk heap 0x4a2cd0 and others) crashed (3 in
  ~100 reloads), and once the list was cut short ~40 heaps were unreachable. Evidence: a crash record on the driver's
  thread (nvwgf2um+0x94FDF7 -> AcGenral +0x98ad3) reading the same freed node the main thread's teardown hit; every
  game-side heap call measured on the main thread. Fix, in the proxy with co-op on: the shim's internal create
  (+0x9899b) and destroy (+0x98a70) run under one lock (found by their own code; no match, no patch;
  `I76_COOP_SHIMLOCK=0` off), and a guard puts any heap the list cannot reach back at its head before the destroy
  (`I76_COOP_HEAPGUARD=0` off). Not co-op specific in principle: single-player loads can race the driver the same way,
  only less often. Mac (Wine) has no such shim. (The 2026-10-07 "setup-name write" suspect was not it.)
- **The host finishing (or failing) a mission while the buddy is still loading it** left the buddy in the game's
  join handshake for good: that handshake waits for 5 s of quiet from the host, and a host already playing never
  goes quiet. After 8 s the buddy now takes the game's own timeout (as a late join does), and the held next-mission
  message brings it to the host's mission (measured: forced in T02, buddy in step one reload later).
- **The rear mirror with no car:** a buddy running frames before its own car exists crashed in the mirror (NULL car,
  0x4457f6); the mirror is skipped then.
- **If the buddy's game freezes** (rather than quits), the host waits at the next mission load until the frozen game
  is closed, then carries on alone (measured 2026-10-07). A buddy that quits normally is simply dropped.
- **A crash on the buddy at a mission load, fixed 2026-10-07:** the proxy's 60 fps radar-ping smoothing could hold a
  ping across the end of a mission and play it in the next one on a car that no longer existed (0x4250f0 -> 0x458c90
  on a freed pointer). Held pings older than 250 ms are dropped now. Not co-op specific: any Replay could hit it.
- **Back-to-back reloads** (faster than real play) once left the joiner waiting for the session group forever; it now
  reuses the last group id after 3 s, and an 'AM' that arrives during a load is applied after it. The host sends each
  'AM' three times; the spare copies could wait in the queue through the joiner's load and reload it a second time,
  which stranded it in state 7. Each 'AM' now carries the reload's number and copies are dropped (fixed and re-measured
  2026-10-07, 16/16). A third way to strand it: the host finishes a mission while the buddy is still loading it. State 5
  and a world root are already true inside the load's network wait, and an 'AM' applied there left the buddy waiting
  for good; it is now applied only once mission frames run (more than 10 since the reload, the last under 0.5 s ago)
  and held until then.

## How it fits together (for the next person)

All in `music-fix/strlkproxy.c`, sections "CO-OP DAMAGE FACTOR", "CO-OP SHARED ENEMIES", "CO-OP CAMPAIGN CHAIN":

- role: network game, host = local id equals ANet host id; else joiner.
- host: `dpReceive` hook (once+ per frame) sends 'AT' (mission car states via the game's 0x4644d0 writer, fire masks)
  and queued 'AC' (CB lines); the loop-exit hook (0x404110) turns win/loss into a Replay reload of the next/same
  mission and sends 'AM'; all 9 `ai_SetBehaviour` calls retarget to the nearest human; the 7 spawn calls adopt the
  mission player object for the host.
- joiner: `ai_FrameTick` skipped; 'AT' -> remote-car mirror 0x464890; fire masks replayed through 0x4a3560; local
  damage to shared cars blocked (5 `object_ClassDamage` sites); 'AM' -> state 7 + next name; 'AC' -> 0x423620;
  'AO' -> fsm_Success 0x45e9e0 / fsm_Fail 0x45ea90 / reveal 0x45e960;
  auto-respawn through 0x451570.
- both: the teardown's network-flag clear (0x404662) passes 1 for a chain reload, so the reload re-initialises the
  network from the open session (0x452d40).
- tools: `tools/coop-mission.py` (one mission), `tools/coop-install.py` (all 17 + The Crater, reversible).
- diagnostics: `I76_FPS_LOG=5` adds a `coop-ai:` line every 5 s (role, packets, applied, retargets, chain, radio, the
  first two mission cars and the local armour); `I76_COOP_AI_DIAG=1` counts AI behaviours per call site;
  `I76_COOP_CB=0` turns radio forwarding off; `I76_COOP_HOSTMODEL=0` keeps the buddy's model for the host's car;
  `I76_COOP_ADOPT=0` gives the host a separate network car (the script then follows a stand-in).
