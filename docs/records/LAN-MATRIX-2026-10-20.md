# LAN matrix 2026-10-20: the overnight multiplayer features between real machines

Owner (verbatim): *"Should probably test between machines more before handing off to me no? ... All of the computers and
steam deck are now on for you to complete the multiplayer tests and test matrix comprehensively so we don't have any
problems when we start to play with friends and family!"*

Machines: PC LAN copy `<games>\Interstate76-LAN-2026-10-17\Interstate 76` (the deployed pack, proxy 533ab67c),
The M2 tester Mac, the M4 Max tester Mac and the developer's laptop (`I76 MP GATE.app`), all on pack `mp-pack-20261020-overnight` (STRLKUP.DLL
533ab67c on all four, read 05:16). The Steam Deck did not answer all morning (section 4). Times CDT. "n" = sessions (joins) per
cell. Evidence: `<lab>\captures\lan-matrix-20261020\<cell>\` (each machine's proxy-log slice
`pc.log`, `A.log`, `M.log`, `L.log`), `<cell>.txt` (the driver's output: join state, the host's AI counts, slot time-outs),
`<cell>.cmp.txt` (position comparison).

## 0. Result

**Every cell that could run passed, 0 crashes on any machine** (crash lines in the proxy logs: 0 of 4 machines, 14 cells).
Nothing on the PC side (proxy, pack files) needed fixing; the pack is unchanged. What failed was my automation (the Mac
Esc menu, section 3) and the Deck (asleep, section 4).

| cell (PC hosts unless stated) | The M2 tester Mac | The M4 Max tester Mac | laptop | evidence | position check (same car on host and joiner) |
|---|---|---|---|---|---|
| **Suburbia** join, play, hard exit, re-join | join n 3 + re-join n 1 | join n 1 + re-join n 1 | join n 1 + re-join n 1 | `c01b-sub-A`, `c02-sub-MLA` | humans median 0.0 m, p90 0.2-10 m, max 84 m (the M4 Max tester driving; Wi-Fi lag) |
| hard exit: slot gone on the host after | 41 s | 41 s | 42 s | `c02-sub-MLA.txt` | - |
| **4 players** PC + the M4 Max tester + laptop + the M2 tester, Suburbia, all 3 driving at once | in | in | in | `c02-sub-MLA` | all four tables list ids 3, 16, 20, 22; humans median 0.0 m (n 1) |
| **host (PC) quits** (Esc > Exit Game) with the 3 Macs in Suburbia | stays in | **becomes host** (id 16) | stays in | `c03-hostquit-sub` | the PC's slot gone on all three at once; same tables on all three for 40 s (n 1) |
| **Hope Springs (4 AI)**, AI fill: join, hard exit, re-join | n 2 | n 2 | n 2 | `c04-hs4` | AI settled p99 4.3 / 44.9 / 17.5 m (A / M / L), humans median 0.0 |
| AI on the host as humans come and go (in play / parked) | 4/0 -> 3/1 -> 4/0 -> 3/1 | -> 2/2 -> 3/1 -> 2/2 | -> 1/3 -> 2/2 -> 1/3 | `c04-hs4.txt` | the parked cars sit at the parking spot ~8.4 km away on every joiner (e.g. label 14 at 3532.5, 41932.5 on host and joiners) |
| **host (PC) quits** Hope Springs (4 AI) with the 3 Macs in | **becomes host** | stays in | stays in | `c05-hs4-migr` | The M2 tester's proxy takes over the AI: role host, 3 humans -> 2 in play, 2 parked (it parked 2 itself), AI orders and 'AT' sends running; joiners agree: AI median 0.3-1.5 m, max 54 m (n 1) |
| **Scene 5 (Co-op)** lone host | - | - | - | `c06-coop05.txt` | 0 copies in for 40 s, mission as stock (n 1 here; n 3 overnight) |
| Scene 5, co-op scaling: join, hard exit, re-join | n 2 | n 2 | n 2 | `c06-coop05` | `t05fp03` engaged: copies in 1 -> 2 -> 3 as the joiners came (host log: "copy 1 / 2 / 3 of 't05fp03', N joiner(s)"); copies stay in when a joiner leaves (by design: until they die). All 53 AI cars at the same places: settled p99 1.4 / 10.5 / 11.5 m |
| **host (PC) quits** Scene 5 with the 3 Macs in | **becomes host** | stays in | stays in | `c07-coop05-migr` | The M2 tester's proxy: co-op role host, 'AT' sends, objectives; it brings copies for its 2 joiners (copies 1, 2 of `t05fp03` beside it); joiners agree p99 8-18 m (n 1). Leftover: the old host's copy 3 is not re-parked (section 2) |
| **Pretty Bus (Scenario)**: join, hard exit, re-join | n 2 | n 2 | n 2 | `c08-bus` | AI settled p99 8.1 / 32.9 m; 2 lost-scenario reloads (the bus died) with all joiners following, no crash |
| **The M2 tester hosts Suburbia, the PC joins** | host | - | - | `c09-Ahost-sub` | PC joins n 2; humans median 0.0, max 16 m |
| **leave by the in-game Esc menu** | n 1 (05:34) | not run | not run | `c01-sub-A-leave` (PC log), `c09-Ahost-sub.txt` | PC as joiner of the M2 tester: Esc > Abort Mission > Abort Mission > "Are you gonna leave me, Sweetheart?" Yes: out after 2 s, the host drops the slot at once (n 2). The M2 tester as joiner of the PC: out, the PC dropped him at once (n 1) |
| joiner kills an AI car / a co-op copy, credit on every screen | **not measured** | | | `c10-jkill` | The M2 tester held fire (Enter, weapons linked) 5.5 min in Hope Springs (4 AI): AI cars damaged (98 -> 28 %, 100 -> 28 %, 100 -> 40 %) but none died, so no kill line |
| **Steam Deck**: deploy, joins, 5 players | **not run**: unreachable 05:16-07:30 (section 4) | | | `deck-deploy.log` | - |

Joins: 29 cross-machine joins counted, all in (net 1, both cars in both tables). Hard exits: 12, every slot gone on the host
after 39-43 s and the session went on. Host quits: 3 (melee, AI arena, co-op), the game went on every time.

## 1. How the cells were driven

- PC: `tools/lan-test/pcnav.sh` (now sets `I76_SHM_SUFFIX=Interstate76-LAN-2026-10-17`, `I76_MUTE=1`, `I76_MPF_LOG=1` and
  starts the lab's per-pid mute watcher; new `arena IDX`: MULTI MELEE > HOST, the host form's selected index
  `[i76shell+0xd4474]` written (PC only), BROADCAST GAME; `jform`: MULTI MELEE > JOIN). Console lock held from 05:19.
- Macs: `tools/lan-test/macnav.sh` with its paths moved to `~/i76-overnight-20261020/lan/` (nothing in /tmp this time), started
  by a new `start-mac.sh` (`open --env I76_MUTE=1 --env I76_MPF_LOG=1`: The M2 tester's and the M4 Max tester's proxies logged
  `mute: session muted = 1`; the laptop has no audio endpoint) and ended by `stop-mac.sh`, which refuses a game the lane did
  not start. No osascript, no poke on a Mac (the arena of a Mac host is picked by clicking its row).
- Driver and analysis: lab `tools/lan-matrix/` (`lm.sh`: join / hard exit / re-join cycles, log slices per machine;
  `cmp.py`: pairs the proxy's 5 s `mpfill:` census lines of two machines. Each machine stamps its own tick count, so the
  offset is fitted per joiner session to 0.1 s by interpolating the host's positions; the first 8 s of a joiner session are
  "join stamps", when the joiner still shows the file's start positions. `hl.py` reads which row of the sim menu is lit).
- A joiner's own census counts every tagged car "in play" (only the host knows what is parked); positions are the evidence.

## 2. Findings

1. **New host after a migration, AI arena: the pool moves with the host** (n 1). The new host's proxy (role host) applies the
   rule to its own humans count at once (3 humans -> 2 AI in play), parks with the same spots, and its AI orders and 'AT' go out.
2. **New host after a migration, co-op: the scaling moves with the host, with one leftover** (n 1). The new host brings copies
   for its own joiners (here 2 for 2), but the old host's third copy (label 109, the copy for the joiner who became host) is
   neither counted nor re-parked: on the new host it is a team-0 car at 14382, 43598 (~5 km from the fight, outside
   `allEnemyDead`, so it cannot block the mission). Harmless for the win / loss logic; a stray car on the map. Fix (not
   made, proxy change): when a proxy turns host in a co-op scene, re-park every tagged copy that is not at its parking spot.
3. **I76_MP_MENU does not take effect on the Macs.** The proxy logs `mp-menu: mode 1 armed ... LoadLibraryA hooked` but never
   `mp-menu: skip ... patched` or `arena-fit:` (The M2 tester, the M4 Max tester, laptop: 9 launches each; the PC: patched). So on a Mac,
   MULTI MELEE > HOST / JOIN still shows the stock MODEM / IPX / INTERNET / NULLMODEM row: click **IPX**. The arena titles are
   not shortened on the Macs either. [inferred] DxWnd hooks i76.exe's imports after the proxy, so the proxy's LoadLibraryA hook
   never sees i76shell load. Fix proposal (not made): attach from a short polling thread once `GetModuleHandleA("i76shell.dll")`
   answers. Everything else in the proxy works on the Macs (fill, scaling, AI sync, mute).
4. **The in-game Esc menu highlights the row under the mouse pointer**, and its default row changes between visits (Replay,
   Cancel or Abort Mission seen). "Abort Mission" there asks "Are you gonna leave me, Sweetheart?" (Yes / No). With a mouse
   this is natural; my key-only route on a Mac picked other rows (once Exit Game: The M2 tester's game closed cleanly, no crash
   line). The game side is fine (n 3 Esc leaves measured).
5. **Positions agree across machines**: settled AI p99 1.4-45 m, humans median 0.0-0.7 m. The largest values (45-84 m) are
   on the M4 Max tester Mac while cars drive (latency); the overnight one-PC figures were 1-2 m.
6. Joiners show the arena file's start positions for the first one or two status stamps (up to ~8 s) after a join; they
   match from then on (as overnight).
7. Two Windows Firewall alerts sat on the PC console during the run (DOSBox from the overnight lane; the teams lane's
   `game-mpo-b\i76.exe`), not answered by me. One stole the keyboard focus once; a click into the game window fixed it.
8. At 05:35 a teams-lane lab copy joined the PC's session for ~10 s (main's note); the cell at that time (`c01-sub-A`) was
   re-run as `c01b-sub-A` and only the re-run is counted.

## 3. What is not measured

- A joiner's kill of an AI car or a co-op copy, and its score line on every screen (section 0 last rows).
- The Steam Deck: deploy, any Deck cell, 5 players.
- 3 or 4 humans across machines in a co-op scene beyond Scene 5 (4 humans measured in Scene 5, Hope Springs (4 AI),
  Pretty Bus and Suburbia).
- The Esc-menu leave from the M4 Max tester Mac and the laptop (the game behaviour is the same code; n 3 on the PC and the M2 tester).
- Feel: whether the AI fill count and the extra co-op enemies are fun (owner).

## 4. Steam Deck

`DECK-DEPLOY.sh` retried every 5 minutes 05:16-05:47 (7 tries, `ssh: connect ... port 22: Connection timed out`), again at
07:03 and 07:30: no answer (`captures\lan-matrix-20261020\deck-deploy.log`). **The Deck still runs the 2026-10-18 files and its
own proxy** (no co-op switches, so even after the step it does not mirror AI cars). Until its step runs it can only play the
15 stock arenas with the others. Its step is one command (OWNER-TEST-LIST "Morning 2026-10-20").

## 5. Machine state at the end of the matrix (07:35)

| machine | pack | STRLKUP.DLL | games | helpers |
|---|---|---|---|---|
| PC LAN copy | mp-pack-20261020-overnight | 533ab67c | ours (pid 41348) running | console lock held (released 07:48) |
| The M2 tester Mac | same | 533ab67c | ours running | caffeinate (ours), `~/i76-overnight-20261020/lan/` |
| The M4 Max tester Mac | same | 533ab67c | ours running | the same |
| laptop | same | 533ab67c | ours running | the same |
| Deck | 2026-10-18 + own proxy | own | - | unreachable |

(Superseded by section 6: every reachable machine now runs proxy 31efcf7a.)

## 6. Teams pack redeployed (07:20-07:47) and its cross-machine smoke

Main asked for it after the matrix: the teams lane's proxy (b462a08 + 8315de9, record MP-TEAMS-2026-10-20) on every machine.

**Pack `<lab>\builds\mp-pack-20261020-teams\`** = `mp-pack-20261020-overnight` with exactly one file changed:
`common/STRLKUP.DLL` 533ab67c -> **31efcf7a**, built from i76-everywhere HEAD 5eea548 (clean `git archive`, MSVC x86 /MT /O2
/Brepro, built twice byte-identical, `builds\teams-pack-20261020\b1|b2`; HEAD's music-fix differs from 8315de9 in README.md only,
so the hash equals the teams lane's). `common.md5` has that one hash changed; `deploy\` holds `STRLKUP.DLL`, `common.md5`,
`mac-deploy-teams.sh`, `mac-rollback-teams.sh`. No ADDON file changed, so arena CRCs are as overnight (titles match the 533ab67c machines; only the proxy behaviour differs).

| machine | how | verify | STRLKUP.DLL now | rollback |
|---|---|---|---|---|
| PC LAN copy | `deploy-pc.ps1` of the new pack (game stopped first) | 1 file updated, 0 mismatches; 533ab67c saved in the pack's `rollback\pc\` | **31efcf7a** | `mp-pack-20261020-teams\rollback-pc.ps1` |
| laptop (`I76 MP GATE.app`) | `mac-deploy-teams.sh <game folder> ~/i76-overnight-20261020/teams --swap`: copy of the folder + the DLL, then swap | 408 files, 0 mismatches | **31efcf7a** | `bash ~/i76-overnight-20261020/teams/mac-rollback-teams.sh "<game folder>"` (the 533ab67c folder is kept as `Interstate 76-pre-teams-20261020`; the 2026-10-18 one still as `Interstate 76-pre-20261020`) |
| The M2 tester Mac | the same | 408 files, 0 mismatches | **31efcf7a** | the same |
| The M4 Max tester Mac | the same | 408 files, 0 mismatches | **31efcf7a** | the same |
| Steam Deck | not reached (ssh time-out / one "refused" at 07:44, then time-outs to 07:47) | - | its own proxy (2026-10-18 pack) | - |

The Deck runs its own proxy in any case (no co-op / fill switches); after its overnight step (`DECK-DEPLOY.sh`) it would
match the arena files; the teams proxy does not apply to it.

**Smoke, PC host + the M2 tester Mac, proxy 31efcf7a on both** (`captures\lan-matrix-20261020\c11-teams.txt`, proxy logs):

| step | PC (host) census | The M2 tester's census | n |
|---|---|---|---|
| PC hosts Hope Springs (4 AI), TEAM PLAY on (form flag written on the PC), picks Grey Hounds | teams rule 1, exe team play 1; AI 11-14 all t7 (Men In Black), PC t0 | - | 1 |
| The M2 tester joins, picks Puce Panthers in the popup (real-pointer clicks) | 3 in play + 1 parked, all AI t7; humans 3/t0, 6/t1 | the same teams: AI t7, 3/t0, 6/t1; the parked car at the parking spot | 2 |
| The M2 tester leaves (hard exit; slot gone after 41 s) | `'vpjrabt2' (label 12) into the game ... team 1`: the returning AI plays on the M2 tester's team | - | **2** |
| The M2 tester re-joins on Puce Panthers | his team's AI (label 12) parks first and is t7 again in the pool | agrees | 1 |
| teams off: PC hosts Suburbia, the M2 tester joins | teams rule 0, no popup; stock teams: each machine itself t0, the other t1 | the same | 1 |

0 crash lines. Not measured here: a third team, kills / scoring by team (as in the teams record).

## 7. Polish (08:00-10:20): the Mac shortcut and the stray co-op copy fixed, pack redeployed

Both leftovers of section 2 (findings 2 and 3) are fixed in proxy **cf4f81da** (i76-everywhere d249380, `music-fix/mpmenu.c`,
`music-fix/mpfill.c`), measured, and deployed to every reachable machine as pack `<lab>\builds\mp-pack-20261020-polish\`.
Lab tools: `<lab>\tools\mp-polish\` (lab commit cda2460); evidence `<lab>\captures\mp-polish-20261020\`.

### 7.1 MULTI MELEE shortcut on the Macs (finding 3)

**Cause (measured, no longer inferred):** DxWnd takes i76.exe's `KERNEL32!LoadLibraryA` import slot after the proxy's DllMain,
as it does with the WINMM slots (music-guard). The new log line on the M2 tester Mac reads `the exe's LoadLibraryA slot is NOT ours,
held by dxwnd.dll` (4 of 4 launches). So `hook_LoadLibraryA` never saw i76shell load and nothing was patched.

**Fix:** a watch thread (`mpm_watch`) polls `GetModuleHandleA("i76shell.dll")` every 50 ms. Once the module has been loaded
for 750 ms and nothing has patched it yet, the thread patches it. The patch runs once (`g_mpm_done`, interlocked). On the PC
the LoadLibraryA hook gets there first, as before, and the thread just ends. The log says which path did the patching.

| check | result | n |
|---|---|---|
| The M2 tester Mac, test proxy aca78c93 (working-tree build of d249380): `mp-menu: skip ... patched, read back OK` + `arena-fit ... read back OK`, via the watch thread | every launch | 4 launches |
| The M2 tester Mac: MULTI MELEE > HOST lands on the IPX host form (shell sfn 0x10028610, screen 0xc026; the shell back buffer reads "NET MELEE HOST EVENT FORM", `A-host1_1.png`) | yes | 3 |
| The M2 tester Mac: MULTI MELEE > JOIN lands on the IPX join list ("NET MELEE ENTRY ROSTER", `A-join4_1.png`) | yes | 1 (+2 in the smoke, 7.3) |
| PC lab copies (game-mpo-a..c, fixed lab twin 4528785c): patched through the LoadLibraryA hook, watch thread never used | yes | 21 launches |
| PC LAN copy with cf4f81da: patched through the hook | yes | 1 |
| The M2 tester Mac with the deployed cf4f81da (smoke): patched via the watch thread, JOIN straight to the list | yes | 2 launches |

### 7.2 The stray co-op copy after a host migration (finding 2)

**Cause:** only the host moves tagged cars and keeps their state. A joiner's table keeps the file's state: co-op copies stay
"parked" and fill cars stay "in play", while 'AT' moves the cars around. A joiner that became host therefore believed every copy
was parked, so a copy beyond its own joiner count never got touched again. That copy was the stray. The same mismatch hit the
AI fill: a car the old host had parked counted as "in play" for the new host, so it could field fewer AI than the rule says.

**Fix (`mpf_migr_pending`, mpfill.c):** a proxy that was a joiner in the current mission load and now acts as host waits until
its humans count is stable and 3 s have passed. Then it reconciles its table against the map once, by position (300 m from
each car's parking spot):
- A fill car sitting at its spot is counted as parked.
- A live co-op copy away from its spot stays in the game (moved to its original's team, with the attack tick) if its copy
  number is within the new joiner count.
- Any other live copy away from its spot is re-parked (teleported to its spot, engine off, team 0).
- Wrecks are left alone.

A host that never was a joiner in the mission never runs this.

Lab route: game-mpo-a..c on private desktops, isolated IPX instances (UDP 54800, wildcard off: read back before the runs),
I76_MUTE=1 + per-pid watcher, god mode on all three. A hosts Scene 5 (Co-op), B and C join, and copies 1 and 2 of `t05fp03`
come in. Then A exits hard (killed), and B becomes host after 42 s (the slot time-out). The first runs used the game-state-3
exit instead, which the new host reads as a mission loss; that route was dropped.

| run | new host's actions | census at the first stamp after the reconcile, new host + joiner (same 5 s stamp) | n |
|---|---|---|---|
| **fixed** (lab twin 4528785c) | `copy 1 ... stays in the game (1 joiner(s)), team 2`; `parked 't05fp03' (label 96) ... host migration: copy 2, 1 joiner(s) here` | away from their spots: label 83 on both screens, counted in by the host; **stray 0 on both** | 3 reconciles (stamp pair caught before the restart below in 2 of 3) |
| **baseline** (lab twin 8dc04f03 = HEAD c82c9d2) | none | labels 83 and 96 away from their spots on both screens, the host counts **0** copies in: **2 strays** | 1 |
| no migration, fixed: joiner B leaves, A stays host | no `host migration` line on any copy; copies in 2, both away from their spots on A and C; no park | (as before) | 2 |
| AI fill, Hope Springs (4 AI), fixed: A + B + C (2 AI in play, 2 parked), A exits hard | `'vpjrabt2' (label 12) is at its parking spot: counted parked`, the same for label 13; then 12 brought in (2 humans, 3 of 4 wanted) | **3 AI fighting** (11, 12, 14), 1 parked = the rule | 1 |
| AI fill, baseline | parked label 12 again (already at its spot) | table "3 in play" but only **1 AI fighting** (14 sat at its spot as "in play", 13 a wreck) | 1 |

0 crash lines across all runs.

**Finding (new, not fixed): when the co-op host leaves, the new host restarts the scene.** The new host logs `coop-chain: host
lost 'coop05.lvl' -> loading 'coop05.lvl'` about 10-20 s after the old host's slot goes. This happened in every lab run
(fixed and baseline, n 6) and on the M2 tester Mac in the smoke (n 1), so it predates this fix. Likely cause: the scene's script
watches the old host's car, the mission's player object. The matrix's c07 slice (2 min) did not show it. After the restart
every copy is at its parking spot anyway; the reconcile covers the time before the restart, and any case where no restart
comes. Whether a host change should restart the scene is the owner's call (proxy change if not).

### 7.3 Build, deployment and cross-machine smoke

**Proxy cf4f81da:** clean `git archive d249380`, MSVC x86 /MT /O2 /Brepro, built twice byte-identical
(`builds\polish-pack-20261020\b1|b2`, `tools\mp-polish\build-final.sh`). **Pack `mp-pack-20261020-polish`** = the teams pack
with only `common/STRLKUP.DLL` changed (`common.md5`: that one line differs). No ADDON file changed, so arena CRCs and titles
are the same as on the teams pack.

| machine | how | verify | STRLKUP.DLL now | rollback |
|---|---|---|---|---|
| PC LAN copy | `deploy-pc.ps1` (game stopped) | 1 file updated, 0 mismatches; 31efcf7a saved in the pack's `rollback\pc\` | **cf4f81da** | `mp-pack-20261020-polish\rollback-pc.ps1` |
| laptop (`I76 MP GATE.app`) | `mac-deploy-polish.sh <game folder> ~/i76-overnight-20261020/polish --swap` | 408 files, 0 mismatches | **cf4f81da** | `bash ~/i76-overnight-20261020/polish/mac-rollback-polish.sh "<game folder>"` (31efcf7a folder kept as `Interstate 76-pre-polish-20261020`) |
| The M2 tester Mac | the same | 408 files, 0 mismatches | **cf4f81da** | the same |
| The M4 Max tester Mac | the same | 408 files, 0 mismatches | **cf4f81da** | the same |
| Steam Deck | not reached (unreachable all day) | - | its own proxy | - |

The M2 tester Mac carried the test proxy aca78c93 only during 7.1. The deployed 31efcf7a was put back right after, then replaced by
the pack.

**Smoke, PC LAN copy host + the M2 tester Mac, both on cf4f81da** (console lock held 09:55-10:16; evidence `smoke-hs4\`, `smoke-coop05\`):

| step | result | n |
|---|---|---|
| PC hosts Hope Springs (4 AI); the M2 tester: MULTI MELEE > JOIN goes straight to the IPX list (watch thread), joins | in; PC: 2 humans, 3 AI in play, 1 parked; the M2 tester's screen shows the parked car (label 14) at the same spot 3532.5, 41932.5 and the other three in the fight | 1 |
| PC hosts Scene 5 (Co-op), the M2 tester joins via the shortcut | copy 1 of `t05fp03` comes in (1 joiner) | 1 |
| PC (host) leaves by the Esc menu | The M2 tester becomes host: `parked 't05fp03' (label 83) ... host migration: copy 1, 0 joiner(s) here`, census 39 / 39 parked; **no stray**. Then the scene restart above | 1 |

0 crash lines on both. The M2 tester's game closed cleanly once between the cells: the key-only Esc-menu leave picked Exit Game (finding
4; no crash line), and it was restarted. All games ended by this lane were ones it had started. Persisted mutes were cleared for
the LAN copy and game-mpo-a..c (one left on game-mpo-a was cleared by hand).

## 8. Steam Deck onto the polish pack (15:20-, Deck lane)

The Deck answered at <LAN-IP> from 15:16 (main's `DECK-DEPLOY.sh` at 15:10 put the 37 overnight arena files in place).
This section brings its proxy and switches onto the pack the other machines run, as new files beside the old ones.
Scripts: lab `builds\mp-pack-20261020-polish\deploy\deck\` (lab 91d62ff); Deck test helpers: lab `tools\lan-matrix\deck\`.
Evidence: lab `captures\deck-polish-20261020\`.

### 8.1 What was installed (15:25, `DECK-DEPLOY-POLISH.sh apply`, no sudo)

| path on the Deck (`~/Games/Interstate76/`) | before | after |
|---|---|---|
| `game/Strlkup.dll` (the proxy; lower-case name kept) | 8bc52939 (pad-menu v3 build) | **cf4f81da** (= the pack's `common/STRLKUP.DLL`) |
| `game/Strlkup.dll.8bc52939-pre-mp-20261020` | absent | 8bc52939 (the old proxy, kept) |
| `game/ADDON/vppirna4.vcf` | absent | 0e096056 (the pack's stock GOG file; the Deck had none) |
| `i76-env-mp.sh` | absent | 8a2d6b8a (new; 8.2) |
| `i76-deck-launch-mp.sh` | absent | c73fc913 (new; 8.2) |
| `i76-env.sh`, `i76-deck-launch.sh`, everything else in `game/` | - | unchanged |

- **Verified against the pack's `common.md5`:** the 61 files a network game compares or loads (STRLKUP.DLL, `ipxwrapper.dll`
  06a01d0f, `wsock32.dll` 70e4a652, `mswsock.dll` c18759b2, `ANETDLL.DLL`, `DLL/WINET.DLL`, `ADDON/ai_*`, `auto*`, `coop*`,
  `vppirna4.vcf`): **0 mismatches**. IPXWrapper was already on the Deck, byte-identical to the pack's (since 2026-10-07), and
  `i76-env.sh` already sets `WINEDLLOVERRIDES=ddraw,d3dimm,wsock32,mswsock=n,b`. The pack's Mac / Windows parts add nothing a
  Wine copy needs for the network (OpenGLide, DxWnd, dgVoodoo and the pad layer are per machine; the Deck has its own).
- **Kept as the Deck's own (not network files):** `i76.exe` f92b8a7e (AiO lineage + a 1-byte stack-reserve change; the pack's
  6319abf7 imports `u32x.dll`, which the Deck does not have), `i76shell.dll` 8960fa16 (the pack's a300db63 is this shell + 590
  bytes: u32x rename, text-entry, F7 / modal keys), `ADDON/valepre4.vcf` 4ed297ca (non-stock: **Jade's Car is refused by a stock
  host; pick another car**, as since 2026-10-18), `ADDON/a2fnsg1m.cbk` not added (the Deck's ADDON was cleared of texture files on
  2026-10-14 and its launcher warns on any `.cbk`). This exe and shell joined PC games on 2026-10-18. Static check: the 590
  differing shell bytes lie outside every site the proxy patches (mp-menu 0x10025f82 / 0x100260b2, arena-fit 0x1002b3af /
  0x1002b421). Live, the Deck's proxy log reads `mp-menu: skip ... patched, read back OK`, `arena-fit ... 2 / 2 text calls
  repointed, read back OK`, `coop-ai: 27/27 ... repointed`, `coop-chain: 7/7`, `aimelee: on (2/2 sites)`, `mpfill: AI fill auto
  ... co-op scaling on ... fill teams on`, `mute: session muted = 1` (8.3).
- **Rollback tested (15:27):** `DECK-DEPLOY-POLISH.sh rollback` put 8bc52939 back and removed the three added files; its check
  of `state/before.md5` (every file of `game/` except logs, plus the two launcher paths: 498 paths) found **0 differences**, the
  only extra file being the kept backup. Re-applied at 15:28 (0 mismatches again). Rollback by hand on the Deck:
  `bash ~/i76-overnight-20261020/polish-deck/deck-rollback-polish.sh` (refuses while i76.exe runs). Every launch, through either
  launcher, rewrites `game/dgVoodoo.conf` (resolution per display) and `game/input.map` (from the pad profile), as before, so
  after a game has run the rollback check lists those two as differences.

### 8.2 The switches: the Deck keeps its own set and adds the three LAN switches

`i76-env-mp.sh` sources `i76-env.sh` unchanged, then exports `I76_COOP_AI=1`, `I76_COOP_CHAIN=1`, `I76_MP_MENU=1` (the three
`PLAY-LAN.bat` sets and `mp-mac-install.sh` writes into the Macs' `[Environment]`); `I76_AIMELEE_FILL`, `I76_COOP_SCALE` and
`I76_AIMELEE_TEAMS` stay at the proxy defaults, as on every machine. `i76-deck-launch-mp.sh` runs the unchanged
`i76-deck-launch.sh` with `I76_ENV_FILE=i76-env-mp.sh` and `I76_LAUNCH_LOG=deck-launch-mp.log` (the launcher already reads
both). Steam launch options: `"/home/deck/Games/Interstate76/i76-deck-launch-mp.sh" %command% -glide`.

**Why not the Macs' set.** The Macs run (the M2 tester's `user.reg`, read 15:22): `I76_HIRES_CLOCK=1 I76_FIXED_STEP=24
I76_FRAMERATE_FIXES=1 I76_ENGINE_DT_FIX=1 I76_RENDER_INTERP=1 I76_FIX_HEALTH_PCT=1 I76_FIX_LABEL_TABLE=1 I76_AI_ROLL_HOLD=0
I76_COLL_DEDUPE=0 I76_FPS_CAP=120 I76_FPS_LOG=5 I76_MUSIC_THREAD=1`, plus the LAN switches and OpenGLide `OGL_*`. The Deck's
`i76-env.sh` already has every one of those sim switches with the same value (the step is 24 ms on all three platforms),
except `I76_COLL_DEDUPE` (Deck 1, Macs 0). On top of that the Deck has the PC host's own preset (`best-wide`: collision G
`I76_COLL_WINDOW=2` / `stepframe`, `I76_BREAKABLE_BOX`, `I76_INPUT_LATCH`, `I76_AI_BACKAWAY_GRID`, `I76_CAM_GROUND_FIX`, the
draw distances) and what its renderer needs (`I76_ZGLIDE_TMUFIX` is required by its dgVoodoo `MemorySizeOfTMU 8192`;
`I76_CURSOR_MAP` / `I76_PAD_MENU` run its menu pointer). Each machine simulates its own car (GAME-NIGHT-ROLLOUT 2026-10-17), so
these extras change how the Deck feels, not the network game. The Macs lack them only because they were never run under Wine
there. Taking the Macs' set would drop switches the owner plays the Deck with, and that its renderer needs, with no network
gain: the step, the fixes and the LAN switches already match. `I76_MUSIC_THREAD` (a Mac boot-hang workaround) was not added,
because the Deck boots without it.

### 8.3 Measured

| check | result | n |
|---|---|---|
| Deck boots through `i76-deck-launch-mp.sh` (started over SSH outside Steam, 8.4) | `deck-launch-mp.log`: switches from `i76-env-mp.sh` (all of `i76-env.sh` + the three), md5 lines Strlkup cf4f81da / i76.exe f92b8a7e / i76shell 8960fa16, display profile tv (the Deck is docked: DP-1 3840x2160, game screen 1280x720); proxy init lines as in 8.1 | 1 |
| Deck: MULTI MELEE > JOIN with the shortcut | lands on the network entry form (shell sfn 0x10028610) straight from the main menu, no MODEM / IPX row | 1 |
| PC LAN copy hosts headless (8.4): MULTI MELEE > HOST straight to the IPX host form, Suburbia, BROADCAST GAME | in mission `m04.msn` as host (me 3) after 20 s; `mp-menu ... patched`, `mute: session muted = 1`, 49 census lines, 0 crash lines | 1 |
| **Deck joins the PC's Suburbia / Hope Springs (4 AI) / a co-op scene** | **not measured**: the Deck stopped answering at 15:34, two minutes after the PC began hosting (SSH refused, then ping and SSH time out; a Wake-on-LAN packet did nothing). Polled until 16:10 | 0 |

### 8.4 How the live cells are driven (for whoever finishes them)

- **Deck, from SSH, with no Steam change:** lab `tools\lan-matrix\deck\push.sh` copies the helpers and the probe to
  `~/i76-overnight-20261020/polish-deck/lan/` on the Deck. `start-deck-mp.sh` starts the new launcher with the proton line
  Steam's shortcut uses (`GE-Proton10-12/proton waitforexitandrun .../game/i76.exe -glide`, `DISPLAY=:1`), plus `I76_MUTE=1
  I76_MPF_LOG=1 I76_SKIP_MOVIES=1`, **as a transient `systemd-run --user` unit**. SteamOS sets `KillUserProcesses=True`
  (`/etc/systemd/logind.conf.d/killuserprocesses.conf`), so the first try, started with `setsid nohup`, was killed (rc 143) one
  second after the SSH session closed. `decknav.sh top | jform | joingo | joinname NAME | leave | pos` drives the game through
  the probe (stretched pointer map). `stop-deck-mp.sh` ends only the game it started.
- **PC host without the console:** only the LAN copy's `i76.exe` has inbound allow rules in the Windows Firewall ("Interstate
  76 LAN (i76.exe TCP/UDP)", Private). The lab `game-mpo-a..d` copies have **Block** rules for inbound, which is why another
  machine cannot reach them. The deployed cf4f81da has no headless click path. So for the run, `deckhost.py prep` saves the whole
  LAN copy (`captures\deck-polish-20261020\lan-copy-before`, 479 files) and `cell` puts the lab twin of the same source into it
  (`builds\mp-polish-20261020\Strlkup-pol1lab.dll` 4528785c = d249380 + the `I76_LAB_SHELLCLICK` block, the proxy behind every
  polish-lane measurement). It boots the copy on a private desktop through the mpo harness (`I76_MUTE=1` + per-pid mute
  watcher, `I76_MPF_LOG=1`, `I76_SHM_SUFFIX=Interstate76-LAN-2026-10-17`) and hosts by poking the arena index. `restore` puts
  every file back. Restored at 15:40: STRLKUP.DLL and `user.mel` copied back, `labclick.done` removed, **479 files checked, 0
  differ** (STRLKUP.DLL cf4f81da), persisted mute cleared (it was not muted). No i76.exe of the owner's was running at the boot
  (checked first).

### 8.5 Open

- **The Deck's join on the new pack** (Suburbia, Hope Springs (4 AI) with the AI count on both screens, Scene 5 (Co-op) with a
  copy for the Deck): n 0. Either the owner's step (OWNER-TEST-LIST "Morning 2026-10-20" item 0) or 8.4 once the Deck is awake
  and kept awake.
- **Steam's shortcut still starts the old launcher.** Changing the launch options to `i76-deck-launch-mp.sh` (or adding a second
  shortcut) edits Steam's config, which this lane left to the owner. Until then the Deck runs cf4f81da without the LAN switches:
  stock arenas mix; in the AI and co-op arenas it does not mirror the host's AI cars (no `I76_COOP_AI`).
- **The lane's test game may still be on the sleeping Deck** (started 15:32 outside Steam, unit `i76-deck-mp-153209`, muted).
  A loop on the developer's laptop (`~/i76-overnight-20261020/deck-polish/deck-stop-loop.sh`, every 60 s for 14 h, log beside it) stops
  exactly that game when the Deck answers. If the log has no DONE line, run `bash
  ~/i76-overnight-20261020/polish-deck/lan/stop-deck-mp.sh` on the Deck before starting the game from Steam (both would share
  one Proton prefix).
- The Deck's exe / shell stay its own (8.1); not a network difference measured so far, but the PC's shell fixes (F7, modal keys)
  are not on the Deck.
