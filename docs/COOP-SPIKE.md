# Co-op spike: a campaign mission as a network game (2026-10-06)

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

**Correction (same day, later runs): the host IS the mission's player.** The first reading below the table said the
script followed "a third car". Re-measured: the host's network vehicle (player table slot 0) is an object with the
player flag (`+0x10` = 0x810), its entity (`object + 0x70`) is the world root, and the host's view opens at T01's
normal start behind Taurus, not at a spawn point. The car that "moved with the convoy" while the host was idle was the
host's own: T01 opens with a scripted stretch that drives the player's car and locks the controls (the fire key did
nothing for the first ~20 s in every run). The car created at the host's spawn point is a spare that just sits there.
So the script judges the host, as in single player. The joiner's car is the one placed at a spawn point.

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
   on Normal. Live: 4/4 sites patched in the PC lab process and the mission ran; the hit counter it logs (with
   `I76_FPS_LOG`) has not seen a hit yet, because no clean shot was set up (see the proxy comment).
6. The joiner must be on the JOIN list when the host broadcasts (the host goes straight into the mission and there is
   no lobby). A lobby wait is a later nicety.

## Files

- Object -> entity: `object + 0x70`; armour at entity +0x138 (4 sides) and chassis +0x148, integer tenths (Taurus
  3000, the tractor 800, the host's Piranha 400 / 360). Label table 0x54a178: {heap, table, count, cap}, entries of
  16 bytes = label[8], object pointer, 0.
- Builder: `tools/coop-mission.py` (its output for T01 is byte-identical to the file tested here, miss8 and miss16).
- Logs: PC `i76-uncap-lab\autotest\runs\mp\ipx\` (IPXWrapper), Mac session scratchpad (`coop-mac-*.log`).
