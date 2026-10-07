# Co-op spike: a campaign mission as a network game (2026-10-06)

*Development record. The feature as it stands, and how to play it: [COOP.md](COOP.md).*

**Question:** can two players be in a campaign (TRIP) mission together, using the game's own network code?
**Answer from this spike: they can be in it together, today, with a data-only change. It is not co-op yet:** the
mission script and the AI still run separately on each machine, and the script follows a car of its own rather
than either human.

Setup: the Windows 11 PC (lab test copy `i76-uncap-lab\game`, stock car data) hosted over IPX (IPXWrapper 0.7.2), and
the Mac (`I76 IPX TEST.app`, Wine, DxWnd + OpenGLide) joined, as in [MULTIPLAYER.md](MULTIPLAYER.md). Both test copies
were restored afterwards, with every hash checked. n = 1 per row.

## What was changed

[`tools/coop-mission.py`](../tools/coop-mission.py) `T01.MSN M01.MSN` builds the file. Install it in place of
`miss8\M01.MSN` and `miss16\M01.MSN` ("The Crater") on both machines; the originals are identical on the PC and the
Mac (f00bad90 / abb41681). Two changes to mission T01 ("keep up with Taurus"):

1. **Two `spawn` objects** (class 1, the record the arenas use) 30 and 60 m beside the mission's player start. Arenas
   carry 19 spawn and regen points; campaign missions have none, and a network player is placed at a spawn point.
2. **The intro and outro movie names blanked** (WRLD body offsets 4 and 17).

## What happened

| step | result [measured] |
|---|---|
| PC hosts "The Crater" (now T01) over IPX | the mission loads in a network game: T01's terrain and convoy, cockpit HUD, `net_IsNetworkGame` = 1, game state 5 |
| ... with the intro movie still in (version A) | the PC sat in play mode 0x20 (movie) until Esc. The Mac joined the session (PC player table slot 1 = dp id 6) but was still in its movie with no mission frames, and the PC dropped it (slot 1 back to 0). **An in-mission movie stops the network pump** |
| version A, the PC's car left idle | about 1-2 min later the PC's game state was 0 (mission failed) and play mode 0x10 (mission-over menu). The script runs and judges, in a network game |
| version B (movies blanked), Mac waiting on the JOIN > IPX list, PC broadcasts, Mac joins at once | **both in the mission.** PC player table: slot 0 = PC (car 0x134732F0), slot 1 = Mac (dp id 6, car 0x13476B30). Mac at ~90 fps in mission frames |
| the Mac holds W for 8 s | in the **PC's** memory, the Mac's car moved 142 m north from its spawn point. Two other cars moved ~350 m in the same 8 s (the convoy, driven by the PC's own AI and script) |
| two minutes in, version B | still game state 5 on the PC; no failure while the Mac was driving |

**Second correction (2026-10-07): the first reading was right.** A same-day "correction" here said the host *was*
the mission's player because table slot 0 carried the player bit (0x810) and its entity was the world root. Both
objects carry that bit: the mission's player object (label `vppirna1`, flags 0x10810) and the host's network-spawned car
(0x810) are different objects (T05: 3 km apart). The script watched the stand-in, which the opening sequence drives and
then leaves. Fixed in the proxy: with `I76_COOP_CHAIN` the host's spawn adopts the mission player object
([COOP.md](COOP.md)).

## What this means for real co-op

Working already: loading, spawning both humans, seeing each other drive, the host's script and AI running.

Still to build, in order (the plan from the co-op discussion, now with evidence):

1. ~~Make the script's player a human~~: it already is the host (correction above). Left: stop the spare car at the
   host's spawn point (or use it for the joiner).
2. **One copy of the enemies.** The host runs the script and AI. The joiner skips both and shows the host's AI cars,
   sent as extra network players through the existing 'ST'/'SH' packets (16 player slots, remote-car smoothing at
   0x464890 already there).
3. **Shared outcome:** mission success or failure, radio and objectives sent from the host. Kills and wrecks are
   probably already consistent once there is only one copy of each enemy.
4. **Skip, not blank, the movies:** play them on both machines while keeping the network alive, or skip them in
   network games only.
5. **Difficulty: `I76_COOP_DAMAGE=<factor>`** (proxy, 2026-10-06) scales every human's weapon and flame damage in
   network games, the remote player's too (owner's choice over tougher enemies). 0.5 = two players as strong as one
   on Normal. **Measured**, see the next section.
6. The joiner must be on the JOIN list when the host broadcasts (the host goes straight into the mission and there is
   no lobby). A lobby wait is a later nicety.

## Measured: the co-op damage factor (2026-10-06)

Target range: arena M01 cut to two spawn points with a parked tractor (`vxktrac1`) and bus (`vxbus1`) 20 m ahead of
each, placed on the car's measured aim line (cars land exactly on the spawn point, nose up 13 degrees, facing the
spawn record's forward row; ODEF rotation rows are right, up, forward). IPX game, PC hosts, Mac joins, each fires the
50 cal (hardpoint 1) for 3 s at its target. Armour read from the host's memory (object -> entity +0x70, armour +0x138).

| shooter | `I76_COOP_DAMAGE` on the host | hits | armour lost | per hit |
|---|---|---|---|---|
| host (local), host alone | unset | 29 | 725 | 25.0 (twice, identical) |
| host (local), host alone | 0.5 | 29 | 348 | 12.0 (twice, identical) |
| host (local), Mac in the game | 0.5 | 29 | 348 | 12.0 |
| Mac (remote), hit computed on the host | 0.5 | 43 | 516 | 12.0; all 43 counted "by a remote player's car" |
| Mac (remote), hit computed on the host | unset | ? | 800 (armour emptied) | at least 18.6 |

25 x 0.5 = 12.5 is truncated to 12 per hit, so 0.5 gives 0.48 of the damage. The host computes the damage of the
joiner's shots on its own copy of the world, and the factor applies to them. In the unset two-player run both cars
were listed at the same spawn point and the host's burst only grazed the bus (2 + 52), so that row is not used.

## Shared enemies: `I76_COOP_AI=1` on both machines (2026-10-06)

The host's mission cars are the real ones; the joiner shows them. How (proxy comment "CO-OP SHARED ENEMIES"): the host
exports every mission vehicle with the game's own state writer (the record the 'ST' packet carries) about 10 times a
second and sends it as a new packet type 'AT', 2 cars per packet; the joiner catches 'AT' after `dpReceive` and drives
each car with the game's remote-player mirror, skips its own `ai_FrameTick` (AI and script), replays the host's AI
trigger pulls, and blocks local damage to those cars so kills are the host's.

| run | result [measured] |
|---|---|
| T01, 5 cars per packet (508 B) | host sent, joiner received nothing, no send error: ANet drops packets that size |
| T01, 2 per packet | joiner applied 1,625 records in 40 s; Taurus 3562.8,36242.0 (host) vs 3559.4,36236.1 (joiner), samples ~0.3 s apart at ~25 m/s; with its AI off the joiner's Taurus only moves by the host's records |
| T01, longer | after ~2 min T01 failed on the idle host (mission-over menu stops the network loop) and the Mac promoted itself to host: a test-design limit, not a sync fault |
| T04, host start moved 80 m from the gang | gang at rest: 1210.0,50265.0 on both machines; host AI fire replayed on the joiner from t+125 s (11,729 trigger pulls by t+250 s); when the host's mission ended, both gang cars' last positions identical on both machines |
| hits / kills | not observed: the gang patrolled and never closed in; nobody took damage |

Open: see the proxy comment (mission outcome on the joiner, radio and objectives, owner id 0 in the score code), and a
run where the gang actually engages, to watch a kill arrive on the joiner.

## Files

- Object -> entity: `object + 0x70`; armour at entity +0x138 (4 sides) and chassis +0x148, integer tenths (Taurus
  3000, the tractor 800, the host's Piranha 400 / 360). Label table 0x54a178: {heap, table, count, cap}, entries of
  16 bytes = label[8], object pointer, 0.
- Builder: `tools/coop-mission.py` (its output for T01 is byte-identical to the file tested here, miss8 and miss16).
- Logs: PC `i76-uncap-lab\autotest\runs\mp\ipx\` (IPXWrapper), Mac session scratchpad (`coop-mac-*.log`).
