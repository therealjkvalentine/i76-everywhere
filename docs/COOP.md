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
- **The host's car looks like the buddy's chosen model** on the buddy's screen (the mission's player object takes the
  local car file). Position, damage and gunfire are right.
- **Brief host hand-over during a reload:** while the host reloads (a few seconds) ANet may make the buddy host; the
  lower id (the original host) takes it back. Seen once, no harm measured.
- **Max-score option:** AI cars carry owner id 0 into the game's score code; harmless with MAX SCORE off (the default),
  not tested on.
- **A natural full-campaign run** (17 missions played through) has not been done; wins were forced through the
  script engine's own success path.
- **A rare host crash at a reload:** Windows' compatibility shim (AcGenral, applied to i76.exe by Windows' own database)
  crashed in `HeapDestroy` of the weapon-debris heap during the teardown (0x4a2cd0), twice in about 50 reloads, both
  with a joiner present. Not reproduced without co-op; cause not found. Suspect fixed 2026-10-07: the next-mission name
  was written as 16 bytes into WinMain's setup block (now exactly its length). Mac (Wine) never showed it.
- **Back-to-back reloads** (faster than real play) once left the joiner waiting for the session group forever; it now
  reuses the last group id after 3 s, and an 'AM' that arrives during a load is applied after it. The host sends each
  'AM' three times; the spare copies could wait in the queue through the joiner's load and reload it a second time,
  which stranded it in state 7. Each 'AM' now carries the reload's number and copies are dropped (fixed and re-measured
  2026-10-07, 16/16).

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
  `I76_COOP_CB=0` turns radio forwarding off.
