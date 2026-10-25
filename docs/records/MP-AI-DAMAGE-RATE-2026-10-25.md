# MP with AI cars: who simulates, the 'AT' rate, the damage visuals, the Esc menu's keys (2026-10-25, investigation + plan)

Owner's live report (PC + the M2 tester's Mac over Wi-Fi, Gold, melee arenas with AI fill): (1) "I'm not seeing damage change on AI
cars when I shoot them, although they do take damage"; (2) "the location update rate is not super great - like 0.5-1.0 s per car
sometimes; could be because he's on Wi-Fi"; (3) as the joiner, the Esc menu did not answer the arrow keys or Enter (the mouse
worked). Investigation lane (Fable), read-only on both machines; nothing launched, nothing changed on the PC or the Macs.
Evidence copied to lab `captures\mp-ai-damage-20261025\` (`pc-mciproxy-2.log` = the PC's whole proxy log of the day, both
sessions; `mac-m2-mciproxy.log` + `mac-m2-mciproxy-tail2.log` = the Mac's; `atrate.py` = the rate script; `ping-mac-to-pc.txt`).

## 0. Answers in five lines

- **The host simulates every AI car.** Session 1 (11:01-11:19, m01.msn "The Crater") the **Mac hosted, the PC joined**; session 2
  (11:24-11:29, m11.msn) the **PC hosted, the Mac joined**. Both are in the logs ("role host / joiner" + the aimelee lines).
- **The rate is at design and the link is clean:** the Mac host sent one update per live AI car every **98 ms** (10.2 rounds/s, n 17
  windows), the Mac joiner received **19.2 packets/s in every one of 34 windows** and applied 9.7 updates per car per second (103 ms);
  pings both ways have no loss and no spikes. The 0.5-1 s the owner sees is **not the mean rate**: it is either sub-second clumping
  (no per-packet timing exists on either machine yet) or the joiner's motion **between** records (mirrored AI cars get no stock dead
  reckoning; they move by local physics with the host's controls and snap at each record). Section 2 says how to tell in one run.
- **Damage visuals:** stock replicates them **inside the state record** (no separate damage packet): the packer 0x4644d0 writes a 2-bit
  level per body side at record +0x58 and the mirror 0x464890 (the function our 'AT' apply calls) sets the panels' VGEO row and TMT
  frame from it on every record. So the path exists for 'AT' cars; what breaks it was not found statically (section 3 ranks three
  places) - the first Opus step is the instrumented pair run in section 5, P2.
- **Esc-menu keys: found, certain.** `I76_MENU_KEYS` (polish.c, default on since 10-20) zeroes the control block 0x5367c8.. while the
  menu is up; the menu's key handler 0x496e10 **reads its key from the first dword of that block** (`DAT_005367c8`: Enter 0xd, Tab 9,
  Space 0x20, Esc 0x1b, arrows 0xc6..0xc9). Single player never runs the clear (the sim block is skipped under the menu), a network
  game runs it every frame: the menu sees 0. Host and joiner alike. Fix + test in section 5, P1.
- Neither live build carries the per-frame 'AT' cap (ea0d483): the PC's proxy and the Macs' 5d6f9828 both log the old
  "coop-ai: dpReceive hooked ..." line without "host 'AT' rounds ...". At 35-66 host fps the cap would not change the rate.

## 1. Who simulates the AI cars (code + logs)

Code (`music-fix/strlkproxy.c` "CO-OP SHARED ENEMIES", `aimelee.c`, `mpfill.c`): with `I76_COOP_AI` the host runs ai_FrameTick (AI
decisions + mission script) and, from the dpReceive hook (= inside net_Pump 0x4532c0, once per frame), `coop_ai_host_send` every
>= 100 ms of wall time: every vehicle of the label table 0x54a178 that no player drives, packed by the game's own state writer
0x4644d0 (0x60 bytes: time, transform, velocity, spin, controls, flags incl. destroyed, **damage levels**, target) into
'AT' = `{u16 'AT', u8 0, u8 n, f32 time, n x {u16 label, u8 fire mask, u8 team, record[0x60]}}`, n <= 2 (208 B; ANet drops larger).
Parked cars (8 km away, engine off) go every 2 s. The joiner skips ai_FrameTick (chained through the tick), catches 'AT' after
dpReceive and hands each record to the remote-car mirror 0x464890 (the 'ST' path), dropping records older than the last applied;
between records local physics drives the car with the host's controls (the record's throttle / steer). Damage: the joiner's shots hit
the mirrored car locally but object_ClassDamage (5 sites) is skipped for mirrored cars; the host computes the real damage from the
joiner's 'SH' fire replay; a kill arrives in the record's destroyed flag. The AI-fill cars are in the arena file (no car is created
after load, mpfill.c); a respawned AI is rebuilt with the stock melee spawner 0x4513c0 on host and joiner.

Logs: PC `mciproxy.log` (appended, both sessions) `aimelee: t ..., joiner, m01.msn` (session 1) then `..., host, m11.msn`
(session 2); Mac `aimelee: t ..., host, m01.msn` with `coop-ai: role host, sent N` (session 1) then `role joiner, packets in N,
applied N` (session 2). Session 1 NO. DRIVERS 4 (2 humans + 2 AI in play, 5 parked); session 2 three AI in play. The PC's preset
(OWNER-2300-ALL) has no `I76_FPS_LOG`, so the PC side has no counters; the Mac's prefix preset logs fps every 5 s.

## 2. The rate: measured, and where the gaps can come from

| side | role | fps | 'AT' records | per live car | n |
|---|---|---|---|---|---|
| Mac M2 (Wi-Fi), session 1 | host | 35-66 (median 48) | sent 19.2-22.2 /s (median 20.4), 2 live AI | **10.2 rounds/s, one update per 98 ms** | 17 windows x 5 s |
| Mac M2, session 2 | joiner | 30-61 (median 41) | packets in **19.2 /s in 34 of 34 windows** (min 18.8, max 21.2); applied 29.2 /s (28.6-36.4), 3 live AI | **9.7 /s, one per 103 ms** | 34 windows (the last 5 are the session's end) |
| PC (Ethernet), both | - | ~90 (600-frame clutter lines: 70 of 94 windows carry one) | no counters (no I76_FPS_LOG) | - | - |

- The host's 100 ms gate is the rate (10/s); net_Pump is reached every frame (at 48 fps a 1-per-frame cap would still give 10/s).
- Loss: 19.2 packets/s is 9.6 rounds x 2 packets with no window short, so the PC -> AP -> Mac direction lost at most ~2 % in any
  5 s window. Mac -> PC (session 1, the owner joining) was sent steadily; the PC's receive side is unmeasured (no counters).
- Link: the Mac is on 802.11ax 5 GHz ch 161 / 40 MHz, -50 dBm / -96 dBm, 412 Mb/s (system_profiler, read-only); the PC on Ethernet
  192.168.1.81. Pings while nobody played: PC -> Mac 60 / 60, avg 5 ms, max 93 ms; Mac -> PC 300 / 300 at 0.2 s, avg 5.1 ms,
  max 24.3 ms, stddev 1.9 ms. 'AT' is **unicast** UDP (lab IPXWrapper log hs-ipx-c: the 214-byte 'AT' payloads go to the peer's IPX
  address, not FF:FF:FF:FF:FF:FF), so Wi-Fi's DTIM buffering of broadcasts does not apply.
- Neither machine's IPXWrapper logs per packet (both at INFO), so **no inter-arrival distribution exists** for the live session.
- Where 0.5-1 s can still come from, ranked: (a) **the joiner's motion between records**: AI cars are not in the player table 0x541070,
  so the stock dead reckoning (+0x34 / +0x38 per player) never runs for them; they move by the local vehicle step with the host's
  controls and are snapped by the mirror at each record - a diverging extrapolation (different terrain contact, a wreck, the
  respawn rebuild, a stale-filtered run of records) looks like a car that stands or drifts and then jumps; (b) sub-second clumping
  on the Wi-Fi hop (Mac power save / AWDL hops are 100-500 ms events) - invisible in 5 s counters; (c) if the owner was watching the
  **other human's** car: stock ANet sends 'ST' at an interval of latency / 3 clamped to **0.2-0.5 s** (network.md) and dead-reckons
  between - that one is stock and separate from 'AT'. Same on host and joiner? The host sees its AI locally (no 'AT'); the joiner
  sees the mirrored cars. The owner was joiner in session 1 and host in session 2, so the report is about the joiner's view.

## 3. The damage visuals: the stock path, and where it can break

- **Who sets the levels (stock).** 11 damage parts per car (5 body sides, 6 wheels), level 0..4; `entity_SetSideDamageLevel` 0x466010
  picks the VGEO row (0,1 -> 0; 2 -> 1; 3 -> 2; 4 -> 3) and `entity_SetSideDamageTextures` 0x4660d0 the TMT frame; locally
  entity_DamageAndKill sets a side's level after each hit from min(armour copy +0x178 / max +0x158, chassis copy +0x18c / max +0x168)
  (> 0.75 -> 0, > 0.5 -> 1, > 0.25 -> 2, else 3) (subsystems/damage.md "Damage visuals").
- **How a remote car gets them (stock, read from the Ghidra export):** the packer 0x4644d0 (our 'AT' uses it) writes, for a car not yet
  dead, the same per-side level as 2 bits x 5 sides into record **+0x58** (from +0x178/+0x158 and +0x18c/+0x168), a blown-wheel mask
  (wheel hp ratio <= 0.25) at +0x5d, the health byte (0x40b450 x 255) at +0x5c, and the quantised health 100/66/33 in bits 30-31 of
  the flags +0x48. The mirror 0x464890 (our `coop_ai_apply` calls it for every record) for a car not dead: per side sets +0x158,
  +0x168, +0x178 := 100 and +0x18c := (4 - level) x 25, recomputes the level and calls 0x466010 + the TMT frames (0x44a150 per face
  name), then per wheel 0x46da30 (hp 25 or 100) -> 0x466010(part 5+i), then 0x466ca0 with the health byte. **So visible damage on a
  remote car is re-applied from the owner's record at every 'ST' / 'AT', 10 times a second; there is no damage packet.**
- **The joiner's HUD readout:** object_HealthFraction returns +0x484 (the packet's 100/66/33) only for objects with +0x10 bit 0x20 (a
  remote player's car); a mirrored AI car has no such bit, so on the joiner the bracket reads its local components, which the proxy
  never damages (the Mac joiner's `local damage blocked` ran 13 -> 74 in session 2) - **expected 100 % on the joiner** while the host's
  copy drops (the Mac host's aimelee lines: vcroyal1 97 -> 48 -> 36 -> 28 -> 20 % -> dead). "They do take damage" on the joiner can
  only be seen by kills (session 1: 4 AI kills credited to the PC through 'AK'; session 2 as host: 6).
- **What the joiner's local hit does:** entity_ApplyDamage still runs (only ClassDamage is blocked): the mirrored car's real armour
  +0x138 (never touched by the mirror) and the copy +0x178 (reset to 100 by every record) drop, and DamageAndKill sets a local level
  - so a joiner should see damage appear at once and be **re-set to the host's level 100 ms later**. Not seeing any change therefore
  means one of: **(A) the host's level bits stay 0** although health drops (the packer's inputs: if +0x158 / +0x168 were 0 for AI cars
  the ratio is copy x 0.01 and the level stays 0 until the copy is below 75 - single player uses the same ratio for AI cars, which
  argues against it, but it was never read live); **(B) the apply lands but nothing is drawn** (0x466010 on the panel objects
  +0x408+4*slot, 0x4620a0's reset of +0x68/+0x70, or the sim tick's draw-side holds keeping the old variant: the tick runs on both
  machines); **(C) the record's word never reaches the mirror** (layout: our entry is `label u16, mask u8, team u8, record[0x60]` at
  100-byte stride - +0x58 of the record is inside the entry, no overlap found; or the stale filter). Nothing in the lab ever checked
  a damage visual in MP (COOP-SPIKE: "NOT observed yet: a hit, a kill"; later records measured kills only). As HOST the owner's AI
  cars are local, i.e. the single-player path; if he saw no damage as host too (session 2), the break is in (A)/(B) under this build,
  not in 'AT'.

## 4. The Esc menu's keys (certain)

- `I76_MENU_KEYS` (polish.c, `menu_keys_wrap` at the input_ProcessFrame call 0x403a1c): while [0x4fe534] == 0x10 it zeroes the 15
  dwords 0x5367c8..0x536803 before input_ProcessFrame, so the car gets no key / axis under the menu. Its comment and the record
  (MENU-SOUND-POLISH s.F) assume "the menu's own keys arrive through the window procedure (0x496e10) and are untouched"; the
  measurement only checked that the car no longer steers.
- Ghidra export `functions/00496e10.c` (the Esc / mission-over menu's key step, called from the menu-mode frame routine 0x49d000 at
  0x49d020, which the main loop calls at 0x403f00 / 0x404037): `if (DAT_005367c8 != 0) { key = DAT_005367c8; accept 0xd, 9, 0x20,
  0x1b, 0xc6..0xc9, 0x209; DAT_005367c8 = 0; ... }` then moves the row `[[0x654a20] + 0x20]` and sets the redraw flags
  0x536812 / 0x536815. 0x44d9e0 (input_UpdateControls) and 0x44dec0 write the same dword. **The menu reads its key from the first
  dword of the block the wrap clears.** Single player: the frame loop skips the sim block under the menu (0x4039e4..0x4039fc), the
  wrap never runs, the menu works. Network game: the sim block runs every frame, the wrap zeroes the key before 0x49d000 reads it.
  Host and joiner, Gold and Nitro (NA-mapped), the Macs too (they run the same default). The PC log has `menu-keys: on`; no pad
  layer, no head-look / AHK helper ran (play-i76.log: "head look: skipped - opentrack is not running"; cursormap's PeekMessageA hook
  touches mouse messages only).

## 5. Plan for Opus (ranked)

**P1. Esc-menu keys in network games** (certain cause; one function; 1 h + test).
Fix in `menu_keys_wrap`: keep the menu's key word through the clear - `DWORD key = blk[0]; memset(blk, 0, 60); next(); if (!blk[0])
blk[0] = key;` (the car's input_ProcessFrame saw zeros; the menu's reader 0x49d000, later in the frame, gets the key; on the next
frame the wrap hides it from the car again until the menu consumes it). Alternative if the order turns out reversed: skip the clear of
blk[0] only when it holds one of the menu's codes (0xd, 9, 0x20, 0x1b, 0xc6..0xc9, 0x209). Keep `I76_MENU_KEYS_LOG` and add one line
per preserved key. Nitro: the same wrap through NA(). Test (lab PC pair game-mpo-c host + game-mpo-d joiner, the lanfix mpo harness,
ef.py's WM_KEYDOWN posting with scan codes, private desktops, I76_SKIP_MOVIES + CUTSCENES, -NoFfb): on the **joiner**, then the
**host**: post Esc, then Down, Down, Up at 300 ms, reading `[[0x654a20]+0x20]` after each (expect 0 -> 1 -> 2 -> 1), then Enter on
the row that leaves the menu (expect [0x4fe534] != 0x10 within 500 ms); **n 2 per role**; controls: A held 1.5 s with the menu up ->
player entity steer +0xe0 stays 0 (n 2, the 10-20 fix still holds); single player t01 unchanged (n 1). Metric: 4 / 4 key sequences
move the row, 4 / 4 Enters leave, 0 steer. Risk: a menu key that is also a gamekey (Space / Enter on the owner's map) now reaches the
menu but still not the car; the stock mouse path is untouched. Rollback: `I76_MENU_KEYS=0` (stock: keys work and also drive the
car) or the previous proxy.

**P2. Damage visuals on AI cars** (cause not determined; instrument first, 2-3 h, then the fix of the branch).
Step 1, instrumentation (lab-only switch `I76_COOP_DMG_LOG=1`): host - per AI car, log when the packed level word (record +0x58) or
the wheel byte (+0x5d) changes: `coop-ai: dmg #i <label> word 0x%04x -> 0x%04x (sides f l r b t) health %d`, with +0x178/+0x158
and +0x18c/+0x168 of each side; joiner - at apply, log the same word when it changes and, after 0x464890, read back +0x18c of the
side and the panel object's current geometry (the LOD-slot name the variant walk set, 0x446635..) so "applied" and "drawn" are
separate columns. Step 2, runs: (i) **single-player control** on the lab twin (m01, NO. DRIVERS 4, LAB shooter: `I76_AIMELEE`'s
g_aim_test_shoot / the lanfix "LAB shooter" wrapper, or tools\ai-damage-runs if it already shoots an AI - survey first): the local
level word of the hit car changes within 1 s of the first hit (n 2); if it does not, the break is in (A)/(B) under this build (sim
tick) and MP is not the cause; (ii) **laptop pair** (C:\i76-bench, IPXWrapper G/H at log_level 4): the joiner shoots one AI car for
10 s; metric: the host's word changes (A), the joiner's applied word matches within 200 ms (C), the joiner's drawn variant changes
by level 2 and a window capture of the car differs (B); n 2 each, then the same with the PC as host and the Mac as joiner once
hands are at the Mac. Step 3, the fix per branch: (A) compute the packed levels from the live armour +0x138 / chassis +0x148 (or
call entity_SideHealthRatio 0x466c20) in a proxy-side packer wrapper; (B) after the apply, force the variant refresh (0x4620a0 on
the entity / exclude the damage panels from the tick's draw-side hold); (C) fix the layout / filter. Risk: the packer wrapper runs
for remote players' 'ST' too - gate it to 'AT' cars. Rollback: the switch / the previous proxy. Secondary (after the above): the
joiner's bracket reads 100 % for AI cars - have object_HealthFraction return +0x484 for `coop_ai_is_mirrored` cars (the mirror
already writes it when 0x458a90 agrees) so the joiner's HUD shows the host's health; test: the readout follows the host's %.

**P3. The 0.5-1 s gaps** (measure first; the rate itself is at design).
Step 1, diagnostics in the proxy (always on with I76_COOP_AI, one line per 5 s): per-car inter-arrival of applied records - median,
90th percentile, max, count of gaps > 250 ms - and the **snap distance** at each apply (|pose before - record pose|, median / max per
window); the host side logs the same for its rounds (gap between rounds). Step 2: the owner's next session with `I76_FPS_LOG=5` on
the PC preset too (it only adds the counters) and the diagnostics on both machines; read both logs. Step 3 by branch: gaps > 250 ms
clustered on the joiner but not on the host's sends -> the hop (on the Mac: AirDrop / AWDL off, Bluetooth off for one session,
n 2 sessions each, metric the gap count); gaps fine but snap distance > 1 m -> the joiner's between-record motion: apply the
record's velocity to the local step properly or **interpolate** (hold the last two records per car and place the car at t - 100 ms
between them; one record of latency, no snaps; the classic fix); both fine -> the owner was watching the human car (stock 'ST' at
0.2-0.5 s) - then raise the proxy's own 'ST' cadence is a separate item. Step 4, cheap and independent: deploy the per-frame cap
ea0d483 (COOP-HOST-STALL) to the PC and the Macs with the next pack - it does not change this rate but removes the pump stall on a
slow host; and consider a 50 ms gate (20 rounds/s, ~4 KB/s for 6 cars) only once Step 1 shows the arrival is not the problem.
Test for any rate change: laptop pair, n 3 x 2 min, the Step 1 numbers before / after; the Mac over Wi-Fi once reachable.

## 6. Evidence files

- `captures\mp-ai-damage-20261025\pc-mciproxy-2.log` (PC, both sessions; ends in the exit-path CRASH at ntdll+0x5FB03 both times,
  state 10 after MCI_CLOSE - exit code -1073740771 in play-i76.log; not part of this report), `mac-m2-mciproxy.log` (Mac, to 11:21),
  `mac-m2-mciproxy-tail2.log` (Mac, session 2), `mac-s1-host.log` (the Mac's session-1 slice), `atrate.py` (the table in s.2:
  `python -I atrate.py <log>`), `ping-mac-to-pc.txt`.
- Ghidra export: `i76-map\ghidra\export\functions\004644d0.c` (packer), `00464890.c` (mirror), `00496e10.c` (menu keys),
  `00466010.c`, `0046da30.c`; `flows.csv` for the call sites quoted.
- Lab IPXWrapper log for the unicast check: `captures\coop-host-stall-20261025\hs-ipx-c.log`.

## 7. Results (Opus lane, 2026-10-25 afternoon)

Rig: the lab PC pair (game-mpo-c host, game-mpo-d joiner, the RC's OWNER-2300-ALL preset, IPXWrapper G / H set to log_level 4
for each run and put back to 2), lanfix harness + lab `tools\mp-ai-damage\mad.py` (`menu`, `dmg`, `rate`; `mad-pc.ps1` = the run
with the IPX level, `madrun.sh` / `mad-job.ps1` = the same on the laptop bench). The laptop was held by the analog-driver,
skip-cutscenes and terrain-pass lanes the whole afternoon, so every run here is the PC pair (the console was free; RDP checked: no).
Every boot `I76_SKIP_MOVIES` + `I76_SKIP_CUTSCENES` + `I76_FFB_OFF`; The Crater (m01) hosted through MELEE > MULTI MELEE > HOST.
Lab twins = main + this lane's hunks + shellclick + the cruise block + `skey` (WM_KEYDOWN / UP with the real scan code and the
extended bit) + (dmg) the joiner-side lab shooter (`insert-jshoot.py`: the I76_AIMELEE_TEST_SHOOT shooter skipped every target on
a joiner, whose fill census calls all mirrored cars parked). Evidence: lab `captures\mp-ai-damage-20261025\<tag>\`.

### P1 Esc-menu keys: cause confirmed, fixed (57f17f4)

Fix as planned in `menu_keys_wrap` (polish.c): `key = blk[0]; memset(blk, 0, 60); input_ProcessFrame(); if (!blk[0]) blk[0] = key;`.
The order is the one the plan assumed: the kept key reaches the menu's key step in the same frame (`kept the menu's key` lines:
0xc6 Up, 0xd Enter, 0x1b Esc, and 0x61 'A', which the menu ignores).

| run (lab twin dbc1ac69) | role | Esc opens | Down, Down, Up: row | steer with the menu up ('A' tapped 1.5 s) | Enter |
|---|---|---|---|---|---|
| pc-m1, rounds 1-2 | joiner | 2 / 2 | 0 -> 1 -> 2 -> 1 (2 / 2) | 0.000 (2 / 2) | on row 0 "Abort Mission": its confirm page opens (2 / 2) |
| pc-m1, rounds 1-2 | host | 2 / 2 | 0 -> 1 -> 2 -> 1 (2 / 2) | 0.000 (2 / 2) | as above (2 / 2) |
| pc-m2, rounds 1-2 | joiner | 2 / 2 | 0-1-2-1, then 4-0-1-0 (wraps) | 0.000 (2 / 2) | on row 4 "Exit": menu left at once, mode 0x10 -> 1 (2 / 2) |
| pc-m2, rounds 1-2 | host | 2 / 2 | 0-1-2-1, then 4-0-1-0 | 0.000 (2 / 2) | on row 4 "Exit": left (2 / 2) |

- **8 / 8 key sequences moved the row, 4 / 4 Enters on Exit left the menu, 4 / 4 Enters on Abort opened its page, 8 / 8 menu-up
  steer reads 0.** The Esc menu's rows: Abort Mission, Play Options, Graphic Detail, Audio Control, Exit (no "resume" row; Exit
  and Esc both run 0x497a30 = close).
- Instrument control: the same 'A' taps while driving steered in 5 of 8 rounds (max |steer| 0.20-0.24); 3 host rounds read 0.001
  (the sampler reads after each key-up; the injection itself is shown by the 0.2+ rounds and the logged key codes).
- Not run: the single-player t01 control (the wrap never runs in single player: the frame loop skips the sim block under the
  menu, 0x4039e4..; that path is unchanged). Rollback: `I76_MENU_KEYS=0` or the previous proxy.

### P2 AI damage visuals: the lab chain works end to end, none of A / B / C reproduces; the HUD readout fixed (66f0781)

| run | who shoots | host: packed word changes (A) | joiner: word applied (C) | joiner: drawn panel rows change (B) |
|---|---|---|---|---|
| pc-d1 (n 2, host alone = the control) | host | yes: 0 -> 0x040 -> 0x080 -> 0x0c0 per car; rows 0 -> 1 -> 2 within the 100 ms watch | - | - |
| pc-d3 (n 2) | joiner (lab shooter) | yes, 4 cars | yes, every change | yes: rows 0x0100, 0x0200, 0x1100, 0x2210 ... right after the mirror |
| pc-d5 (n 2, window captures) | joiner | yes | yes | yes |

- **Host's word change -> the joiner's drawn row change: median 0 ms, max 93 ms (n 22 row changes, 4 pair runs;** one PC clock;
  the host side is sampled every 100 ms, so hit -> drawn is <= ~0.2 s). **Capture** (pc-d5 run 0, the joiner's window, grabbed
  every ~0.7 s): `pc-d5\z-2423288937.png` (bullet sparks on the van's back, panels straight) and `z-2423289640.png` (the next grab,
  +0.7 s; the joiner applied row 2 at +0.58 s): back and side visibly crumpled. Run 1's change came with the van at the frame's
  edge (smoking, `r1-post.png`): log only. So **the shooter's screen shows the damage within 1 s of the hit: n 2 by log (22
  changes), n 1 by capture.**
- Also seen: the joiner's local hits never touch the mirrored car (its live armour stays at max: ClassDamage is skipped); the look
  comes only from the host's word, and the mirror maps level 1 to row 0 (only the TMT frame), so a side has to be at <= 50 %
  before the geometry changes (about 63 % health in the control).
- **Not reproduced: the owner's "no damage change".** The lab ran main + this lane on the RC preset; the owner's machines ran
  older proxies (PC: the RC 53944fb2 line; Macs: 5d6f9828). Next: the owner's next LAN session with `I76_COOP_DMG_LOG=1` on both
  machines (it logs which column fails), or a lab pair on the old md5. No A / B / C fix was made: nothing failed.
- **HUD (secondary): fixed.** `I76_COOP_AI_HEALTH` (default 1): on a joiner, object_HealthFraction 0x40b450 returns the host's
  health for cars the host drives ('AT' record +0x5c, a 0..254 byte = health x 2.55; the mirror reads it as / 255). Joiner readout
  vs the host's at the same moment: within 1-4 points (n 16 damaged readings, pc-d5 runs 0 and 1); control `I76_COOP_AI_HEALTH=0`
  (pc-d6-hpoff): 100 while the host read 42-81 (n 6). Detour at 0x40b450 (5 bytes `sub esp,0x44; push ebx; push esi`), Gold only.

### P3 rate: diagnostics in, measured; interpolation built and NOT shipped on (66f0781)

`coop-ai-rate:` lines (every I76_FPS_LOG window; joiner: per-car inter-arrival of applied records and the snap at each apply,
|position before the mirror - after|; host: the gap between rounds) and a per-step jump line (second difference of each moving
mirrored car's position per sim step). PC pair, The Crater, both humans parked, 2 live AI driving at them, 60 s, n 2 per row:

| runs | gap ms median | gap p90 | gaps > 250 ms | snap at apply: window medians | snap p90 (median window) | snaps > 1 m |
|---|---|---|---|---|---|---|
| pc-r1 (lab3, before the interp code) | 109 | 125-141 | 2 of 2186 (a car's entry) | 0.08 / 0.27 m | 1.27 / 0.68 m | 307 of 2240 (14 %) |
| pc-r4-off (lab7, switch 0) | 109-110 | 125-219 | 15 of 2157 | 0.15 / 0.51 m | 0.80 / 1.44 m | 461 of 2224 (21 %) |

Host side (all runs): one round per 109 ms, p90 110-125, none > 250 ms. A per-tick trace (pc-t1, `I76_COOP_AI_TRACE`) shows the
mechanism: under the 41.667 ms tick a mirrored car moves by its local physics ~0.5 m a tick at 12 m/s, and each record moves it
another 0.4-0.55 m forward or back: a ~9 Hz wobble of about one tick's travel, larger on fast cars (snap max 1.5-4 m). Arrival is
clean on this wired pair (no clumping; the Wi-Fi hop is still unmeasured). So the branch is "gaps fine, snap > 1 m", and
interpolation was built (`I76_COOP_AI_INTERP`: at the first pump of each sim step the car is placed between its last two records,
spacing from the host's record times; the apply leaves the drawn position):

| per-step jump of moving cars (n 2 x 60 s each) | window medians | p90 (median window) | steps > 0.5 m |
|---|---|---|---|
| off (pc-r4-off) | 0.053 / 0.037 m | 0.77 / 1.31 m | 24 % / 31 % |
| on, arrival-time spacing (pc-r4-on) | 0.313 / 0.314 m | 0.86 / 0.81 m | 32 % / 29 % |
| on, record-time spacing (pc-r5-on) | 0.188 / 0.351 m | 0.54 / 1.12 m | 16 % / 35 % |

**Interpolation does not smooth it:** the median step jump gets 4-8 x worse and the tail is not reliably better (n 2): the local
vehicle step still integrates the record's velocity after every placement and fights it. Shipped **off** (`I76_COOP_AI_INTERP`
default 0, a lab switch), against the brief's "default on if built", because the measurement says it is worse. The next attempt
has to own the car's motion: skip the local vehicle step for an interpolated car, or blend in the tick's draw layer. The per-frame
'AT' cap (ea0d483, `I76_COOP_AT_PER_FRAME`) is in this build (it was already in main).

### Build, install, issues

- Commits: **57f17f4** (P1, polish.c), **66f0781** (P2 log + HUD health, P3 diagnostics + the interp switch, strlkproxy.c).
- Product build `builds\nitro-port-20261021\build.ps1 -Ref 66f0781`, twice: **045f4e0562864ab60723920ce2cf0927** both times.
- Installed in lab **test-gold** `Interstate 76\STRLKUP.DLL` (was dba46ea2 = fe7468c, kept in `_rollback\mp-ai-damage-20261025\`),
  md5 read back; VERSION.md updated. Not in main / the daily driver, not on the Macs: the next family rollout (same md5 on every
  machine).
- Lab twins `builds\mp-ai-damage-20261025\Strlkup-lab1..9.dll`; lab9 (1edea828) = 66f0781 + the lab blocks, smoke pair pc-final-d:
  damage applied and drawn, HUD on, interp off. 0 CRASH lines in the 58 proxy-log slices of this lane (18 runs; d4 died on a harness bug before its slices were saved).
- Issues: #93 Esc menu keys (fixed, 57f17f4), #94 damage visuals (HUD fixed; the owner's report not reproduced, open for the
  owner-session log), #95 rate (measured; interpolation tried and kept off; open for the next approach).
