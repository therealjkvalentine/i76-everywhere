# Frame-bound systems: what ran at 1997's frame rate, and what 33 / 66 / promotion 18 do with it (2026-10-19)

The owner's question (verbatim): "in comparing 33 to 66 it would be good to know what ran at half speed in 1997 retail;
like maybe damage is too fast in 33, could have seemed like that, so a specific list would be helpful."

**Short answer.** Gun damage is not too fast at 33. The player's guns fire on a clock in every build, and every round
does the same fixed damage. Measured on a parked car (n 3 per arm), damage per second is 255 at tick33 against 248 at
the 1997 coupling: 1.03x. AI incoming damage over the same window of T13 is also the same: 4 870 against 5 250
damage asked per minute. Ram damage at tick33 is lower than the 1997 coupling, not higher (30 against 53 hp per ram,
n 3, noisy).

What does run faster at 33 is everything the engine counts per frame. In 1997 that ran about 24 times a second; at
tick33 it runs 30 times (x1.25), and at tick66 15 times (x0.63). In damage terms that means:
- the Fire-Dropper's ground fire;
- sustained scraping contact;
- the wreck's secondary blasts.

The flamer is the one damage source that is too *slow* at 33 (x0.75), and another lane is calibrating it now. The
rest of the per-frame list is AI tempo and visuals, not damage. "Half speed in 1997" against 33 is never the case: 1997
at the owner's settings counted about 24 per second and 33 counts 30.

Lab only. The daily driver, the golden copy and the Downloads portable were not touched. Harness: lab copy `game-fbs`
(a copy of `game-wst`: i76.exe 6319abf7, null renderers, private desktop, i76 audio sessions muted by the watcher, no
host mute). The lab twin is `builds\tick-fix2-20261018\Strlkup-fx1-lab.dll` 435cc5be (i76-everywhere 2743ceb + the
drive block). It has the tick19c candidate's defaults (flame factor 1, i.e. before the flame lane's calibration).
Tools: lab `tools\frame-bound\` (`fb-run.ps1`, `fb-queue.ps1`, `fb_live.py`, `fb_tab.py`, `fire_timer_sim.py`). Tables:
lab `emu\results\frame-bound-20261019\fb-tables.md`. Captures: lab `captures\frame-bound-20261019` (gitignored), 53
boots in all.

## How to read the rates

- **The reference is "1997" = retail 1.0 as played: P166, software, 640x480, mirror on.**
  - The engine's step is the frame time, so anything counted per engine frame (or per render pass) ran at the frame
    rate.
  - The emulator cells nearest the owner's settings ran 20.8 fps (r166m5: 640x480, low detail, no mirror) and 21.8 fps
    (r166m6mir: 480x360 low, mirror). HARDWARE-MATRIX, n 1 each.
  - The developers' full-detail 640x480 preset ran about 10 fps, at 2-3 substeps of about 40 ms (r166p3).
  - The brief's ~42 ms per engine frame is used below: **24 per second**. "1997 x" factors are against 24. Against
    the 20.8 fps cell they would be 1.2x larger for every faster-than-1997 row.
  - Below 50 ms a frame is exactly one physics substep. So at 42 ms per-substep and per-frame counts are the same.
- **The measured 1997 stand-in is `e24`: our exe's stock frame loop capped at 24 fps on a 1 ms tick.**
  - It ran 41.67 ms frames (41 / 42 ms, read from the frame log).
  - It is the lab-step-33 preset minus every timing patch, as tick-finish's e30k and tick-fix2's e20ks.
  - Why not the emulator: these measurements need the proxy's drive block, trainer freeze and damage-event telemetry,
    which retail 1.0 cannot load.
  - AI-DAMAGE-BALANCE s.0 item 4 found the stock loop on our exe indistinguishable from retail P166 in T13 combat.
- **tick33 / tick66** (`tick19-33` / `tick19-66`, PLAY-TICK / PLAY-TICK-66) run the whole sim block once per tick:
  30 / 15 per second.
  - The sim block covers input, collision, every entity tick, AI and the script VM, turrets, projectiles and weapons.
  - Draw-code sim (flamer, smoke, trails, radar ping) is held to the tick (WHOLE-SIM-TICK s.2).
  - At tick66 vehicles take 2 substeps of 33.3 ms per tick.
- **Promotion 18 (`p18`, the daily driver, PLAY-balanced)** is a mix:
  - vehicle physics on a fixed 41.67 ms step (24 / s);
  - the `I76_FRAMERATE_FIXES` items on a 20 Hz grid (20 / s);
  - everything else in the sim block once per **display** frame (120 / s).
- **"Matches"** means within 10 % of the 1997 rate, or measured inside the 1997 arm's spread.
  - Spreads are 95 % t intervals over boots (boot = unit).
  - Several headless arms repeat to the digit, so their spread is 0.

## Summary table

Rate = the system's count per second while it is active. Factor = against 1997 at 24 / s. Rows marked **M** were
measured in this lane (n 3 per arm unless stated). Rows marked **R** come from an earlier record. All others are
static reading, with the address given in the detail sections.

| # | system | counted per | 1997 (~42 ms) | tick33 | tick66 | promotion 18 | tick normalises? | verdict tick33 / tick66 |
|---|---|---|---|---|---|---|---|---|
| 1 | player gun / cannon / rocket fire rate **M** | clock (dt timers, carry) | 50cal 9.6 /s (10 nominal) | 10.0 (1.04x) | 10.1 (1.05x) | 9.5 (0.99x) | n/a (clock) | **matches** / matches |
| 2 | damage per round (guns, cannons, rockets, missiles, mines) **M** | per hit, no dt | 25 (50cal), 60 (25mm) | same | same | same | n/a | **matches** |
| 3 | gun damage per second on a parked car **M** | (1) x (2) | 50cal 248 /s, 25mm 192 /s | 255 (1.03x), 193 (1.00x) | 260 (1.05x), 190 (0.99x) | 243 (0.98x), 188 (0.98x) | n/a | **matches** / matches |
| 4 | flamer damage **R** | per render pass, main + mirror | bar 668 /s (20 fps) | 500 (0.75x) | 500 (0.75x) | 328 (0.49x) | held per tick; **factor being calibrated** (flame lane) | too slow x0.75 (both) |
| 5 | Fire-Dropper ground fire, oil-slick contact | per projectile step (frame) | 24 hits /s, full per-shot damage each | 30 (1.25x) | 15 (0.63x) | 20 (0.83x, grid) | no: per tick | **too fast x1.25** / too slow x0.63 |
| 6 | dropper and mine cadence | clock (dt timer) | 60 /s at speed, 1 /s mines | same (within 10 %) | same | same | n/a | matches |
| 7 | collision damage, one impact **M** | per contact per collision pass, amount from impact speed | 53 hp per 20 m/s ram, 7 records | 30 hp, 3.6 records | 24 hp, 2.2 records | 48 hp, 2.5 records | n/a | not faster; lower, noisy (n 3) |
| 8 | collision damage, sustained contact (scrape, pinned) | per collision pass | 24 records /s | 30 (1.25x) | 15 (0.63x) | 24 (dedupe, per step) | no | **too fast x1.25** / too slow x0.63 |
| 9 | landing, explosion blast, mine, surface (terrain) damage | event / dt | - | same | same | same | n/a | matches |
| 10 | wreck debris and secondary blasts (2 dmg over 10 m, knocks breakables off) | per vehicle substep | 24 rolls /s | 30 (1.25x) | 30 (2 substeps x 15; 1.25x) | 24 | no | **too fast x1.25** (both) |
| 11 | burning damage over time | - | none exists (only rows 4 and 5) | - | - | - | - | n/a |
| 12 | AI fire decision gate (`ai_ShouldFireWeapon`), turrets' outer roll | per frame | 24 rolls /s | 30 (1.25x) | 15 (0.63x) | 20 (grid, 0.83x) | no | rolls x1.25 / x0.63; **incoming damage measured equal (M)** |
| 13 | AI incoming fire on the player, T13 20..43 s **M** | (12) x refire | 56 shots, 26 hits, 5 250 dmg /min | 64 / 24 / 4 870 | 60 / 28 / 5 360 | 68 / 20 / 3 920 | - | **matches** (all inside spread) |
| 14 | AI sight ray (one per frame across all cars), route search (100 cells / frame), dodge roll | per frame | 24 /s | 30 (1.25x) | 15 (0.63x) | 120 (5x) | no | faster / slower AI awareness (feel) |
| 15 | AI handbrake-skid roll, horn roll | per frame | 24 rolls /s | 30 (1.25x) | 15 (0.63x) | 120 (5x: `I76_AI_ROLL_HOLD=0`) | no | x1.25 / x0.63 (feel) |
| 16 | AI stuck test (4-frame grip ring), rammed / attacked stamps (1-2 frames) | frames | 167 ms window | 133 ms (0.8x) | 267 ms (1.6x) | 200 ms (grid) | no | feel |
| 17 | AI behaviour timers, script (FSM) waits, regen 30 s, wreck 10 s | clock (sim time) | - | same | same | same | n/a | matches |
| 18 | AI throttle / steer one-frame gains (1 / sim_dt) | per frame, dead-beat | 1 / 0.042 | 1 / 0.033 | 1 / 0.067 | pinned to 1 / 0.05 | consistent at a constant step | matches by construction |
| 19 | projectile speed, life, ballistics, rocket ease, bomblet fuses | clock (dt) | - | same | same | same | n/a | matches |
| 20 | radar-missile turn (DrRadar, Cherub) | per projectile step, no dt | 24 steps /s | 30 (1.25x) | 15 (0.63x) | scaled to 20 /s (0.83x) | no | turns x1.25 / x0.63 |
| 21 | heat missile (Aim-Nein) | snaps to target each step | - | same | same | same | n/a | matches |
| 22 | tracer streak length | one projectile step of travel | 8.3 m at 200 m/s | 6.7 m (0.8x) | 13.3 m (1.6x) | 1.7 m (0.2x) | streak drawn per tick (s.10.2) | shorter / longer (look) |
| 23 | explosion and impact sprites, texture animations, skid-mark expiry | clock (sim time) | - | same | same | same | n/a | matches |
| 24 | flame hit-explosion spawns **R** | per hitting segment per update | 668 /s (bar) | 500 | 250 | 328 | held per tick | at or below 1997 |
| 25 | smoke puffs (exhaust, damage smoke): spawn and 20-call life | per render pass | 24 /s, life 0.83 s | 30 /s, life 0.67 s | 15 /s, life 1.33 s | 20 /s, life 1.0 s | held per tick | shorter / longer trails (look) |
| 26 | missile smoke trails: 4 segments lost per call in the last 2 s | per render pass | 24 /s | 30 | 15 | 20 | held per tick | look |
| 27 | flamer stream length (ageing) **R** | per render pass vs 20 /s emit | ~19 segments | 18.6 | 18.6 | 18.5 | aged per 50 ms (tick-gaps) | matches |
| 28 | radar sweep, contact age, blip repaint | clock (0.2 s steps, +3 /s) | - | same | same | same | n/a | matches |
| 29 | locked-on radar ping | per render pass | 24 /s | 30 | 15 | 20 (grid) | held per tick | x1.25 / x0.63 (ear) |
| 30 | HUD ammo-digit roll | per weapon update | 24 steps /s | 30 | 15 | 20 (grid) | per tick | cosmetic |
| 31 | camera chase lag, cockpit sway, screen shake, look easing | dt, display side | - | same (display dt) | same | same | n/a | matches |
| 32 | free-look / orbit keys, death spin (8 deg per call), clouds, map zoom | per call constants | 24 /s | 30 (cosmetic sites scaled to the tick rate) | 15 | 20 (scaled) | scaled to the tick, not to 1997 | x1.25 / x0.63 (look) |
| 33 | rear-mirror refresh (every 2nd frame) | display frames | 12 /s | 60 /s | 60 /s | 60 /s | n/a | smoother (cost only) |
| 34 | sustained sound loops, vehicle sound starts **R** | per frame request | 0.89 starts /s (30 fps stock) | 0.85 | (fixed the same way) | 0.80 | keep-alive held between ticks | matches |
| 35 | WMISS click, lock tones, impact sounds | per frame / per contact | 24 /s | 30 | 15 | 20 (grid) | per tick | x1.25 / x0.63 (ear) |
| 36 | music (CD audio / MCI), script music cues | wall clock / events | - | same | same | same | n/a | matches |
| 37 | keyboard throttle notch ramp | per input pass | 24 steps /s | 30 (1.25x) | 15 (0.63x) | dt-scaled to 20 /s | no | feel |
| 38 | engine RPM / torque smoothing (whole-frame dt per substep) | per substep x frame dt | 1 substep: correct | correct | **2x per tick** (2 substeps x 66.7 ms) | `I76_ENGINE_DT_FIX` | no | matches / engine settles 2x fast (T06 accel rows still pass) |
| 39 | vehicle physics step (the step-length study) | per substep | 42 ms | 33.3 ms | 2 x 33.3 ms | 41.7 ms | - | out of scope: STEP-LENGTH-CURVE, TICK-FINISH s.4.4 |

## 1. Weapons: fire rate, damage per hit, damage per second (measured)

**Static.** `weapon_UpdateInstanceFiring` 0x4a6470 runs every frame, for every instance, AI included (i76-map
ghidra export `004a6470.c`). The cooldown (+0x24) and interval (+0x28) timers run against the frame's dt. The loop
fires as many shots as fit in the frame, and the remainder carries to the next frame. MG and handgun rounds are
batched into one `weapon_FireShot` call per frame, so the round count is right.

The one frame-bound part: after a timer is spent, a remainder below 0.01 s is dropped (`if (dt_left < 0.01)
dt_left = 0`), so the next shot waits for the next frame. At 41 / 42 ms frames a 10 /s gun loses 4 % to this. At the
tick's exact 33.3 / 66.7 ms the remainder lands on 0 and nothing is lost. At 120 fps (promotion 18) every remainder is
under 10 ms.

`fire_timer_sim.py` replays the loop in float32; it predicted the 50cal's 9.60 /s at e24 to the digit.

Damage per hit is the GDFC damage times the difficulty factor (`weapon_BuildImpactDamage` 0x4a76a0), with no dt. The
lab copy's data is the owner's modded set: the 50cal reads rate 10 /s and damage 25; the 25mm reads 3 /s and 60.

**Measured** (fb-run `gun50` / `gun25`). Setup:
- T05 after the hand-over;
- the player frozen 12 m from the nearest car (t05cm03, about 500 m away at the hand-over), nose on it, trainer god;
- the weapon's key held for 20 s or until the kill;
- SHOT events (rounds) and DAMAGE_SIDE events (records on the target) from the proxy telemetry, stamped with sim time.

| weapon | arm | rounds / sim s | hits / rounds | damage per hit (record) | damage dealt / sim s | first hit -> kill, s | hp lost / sim s (incl. components) |
|---|---|---|---|---|---|---|---|
| 50cal | e24 (1997) | 9.61 +- 0.05 | 0.99 | 25 | **248 +- 6** | 3.9 +- 2.1 | 328 +- 210 |
| 50cal | tick33 | 10.00 +- 0 | 1.00 | 25 | **255 +- 2** | 4.9 +- 1.6 | 252 +- 59 |
| 50cal | tick66 | 10.07 +- 0.03 | 1.00 | 25 | **260 +- 5** | 3.6 +- 2.0 | 373 +- 210 |
| 50cal | p18 | 9.52 +- 0.06 | 1.00 | 25 | **243 +- 3** | 5.4 +- 1.0 | 231 +- 43 |
| 25mm | e24 (1997) | 3.000 | 1.00 | 60 | **192 +- 7** | 5.1 +- 2.5 | 252 +- 170 |
| 25mm | tick33 | 3.000 | 1.00 | 60 | **193 +- 10** | 5.1 +- 4.8 | 267 +- 200 |
| 25mm | tick66 | 2.84 +- 0.08 | 1.06 | 60 | **190 +- 6** | 6.2 +- 3.3 | 205 +- 79 |
| 25mm | p18 | 2.95 +- 0.02 | 1.00 | 60 | **188 +- 5** | 5.8 +- 2.3 | 226 +- 110 |

- **Damage per second from the player's guns is the same in every arm.** It runs from 0.98x (p18) to 1.05x (tick66)
  of the 1997 coupling. tick33 is +3 % on the MG, all of it from the 10 ms remainder that 41 / 42 ms frames lose.
- The 25mm at tick66 fires 2.84-2.86 /s (-5 %). Its 0.333 s interval lands on the 66.7 ms grid and loses the
  remainder on some shots. Not material.
- Time to kill varies more between boots of one arm than between arms (3-7 s).
  - The cause is where the rounds land. Hits that reach a component (engine, suspension) take more hp than the
    record carries: 24-101 hp lost per 25- or 60-damage hit.
  - The record damage per second is the clean comparison.
- AI weapons use the same timer. The AI only pulls the trigger on frames where its fire roll passes (row 12).

## 2. Collisions and other damage

**Static** (PER-FRAME-AUDIT s.1 C1 / U4, damage.md M47).
- `physics_CollideAll` 0x4349c0 runs once per frame, in the tick's sim block. Each contact record is applied whole,
  with an amount from the impact vector and no dt (`physics_ApplyCollisionDamage` 0x4a7c80).
- So a single impact is an event. Contact that persists into the next pass is applied again. A scrape or a car pinned
  against another therefore takes damage per collision pass: 24 /s in 1997, 30 at tick33, 15 at tick66.
- Promotion 18's `I76_COLL_DEDUPE` counts once per 41.7 ms step: 24 /s.
- Landing damage (1.001e-4 x m x (n.v)^2 per landing), explosion blasts (once at spawn), mines (once on the hit) and
  terrain surface damage (rate x step dt) are events or dt-scaled.

**Measured** (fb-run `ram`). Setup:
- the same T05 car;
- 6 rams per boot: the player repaired, turned to face it and teleported 25 m out with 20 m/s toward it; no throttle,
  no god;
- only collision records counted: player records with no shooter, target records whose shooter is the player. The
  target car fires at the player during the rams.

| arm | closing m/s | player hp lost per ram | target hp lost per ram | collision records per ram (player) | their spread in sim s |
|---|---|---|---|---|---|
| e24 (1997) | 20.8 | 53 +- 34 | 4.6 +- 6 | 7.1 | 0.91 |
| tick33 | 21.1 | 30 +- 16 | 1.5 +- 3.7 | 3.6 | 0.51 |
| tick66 | 21.1 | 24 +- 37 | 10 +- 22 | 2.2 | 0.37 |
| p18 | 20.7 | 48 +- 49 | 1.6 +- 2.1 | 2.5 | 0.36 |

- **Ram damage is not faster at 33. It is lower** than the 1997 coupling (0.57x, inside the noise at n 3).
  - At 24 fps the contact repeats over about 0.9 s: 7 records per ram against 3.6.
  - This fits row 8: the 1997 frame re-applies a lingering contact on every pass.
- Weak measurement:
  - the target is an armed AI car, not a fixed object, and it moves under the hits;
  - the impact geometry varies (some first contacts are nearly vertical: the car rides onto the target);
  - two e24 boots repeated to the digit, so their n is not independent.

  The verdict above rests on the mechanism, and the numbers only bound it.
- The parked target takes little ram damage in every arm (1.5-10 hp per ram).

## 3. AI (row 12-18)

**Fire.** `ai_FireWeapons` 0x414ef0 runs every frame and asks `ai_ShouldFireWeapon` 0x418200 for each weapon slot. A
pass pulls the trigger for that frame, and the weapon's own timer (section 1) then decides whether a round leaves.
Turrets (`entity_TickTurretFire` 0x462a90) add an outer `rand() % (2N - 2)` roll per frame. So decisions per second
follow the frame rate: x1.25 at tick33, x0.63 at tick66, and the 20 Hz grid under promotion 18.

**Measured** (T13 idle + god, 90 s, combat-live, 10 s snapshots).
- e24 (n 5) and a tick33 control (n 2) were run in this lane on fx1.
- tick33 / tick66 / p18 / e30k (n 5 each) are the tick-finish lane's boots (TICK-FINISH s.4.3).
- The god-held player **is killed at 43-46 s sim in 4 of 5 e24 boots**. So the common window is 20..43 s (snapshots
  22..42):

| arm | boots | hostile shots / min | hits on the player / min | damage asked / min |
|---|---|---|---|---|
| e24 (1997 coupling) | 5 | 56 +- 12 | 26 +- 3 | 5 250 +- 470 |
| tick33 (tick-finish) | 5 | 64 +- 9 | 24 +- 0 | 4 870 +- 0 |
| tick33 (this lane, fx1) | 2 | 75 +- 56 | 24 +- 0 | 4 860 +- 0 |
| tick66 | 5 | 60 +- 25 | 28 +- 20 | 5 360 +- 3 100 |
| p18 | 5 | 68 +- 14 | 20 +- 4 | 3 920 +- 900 |
| e30k (stock 30 fps) | 5 | 63 +- 21 | 21 +- 7 | 4 150 +- 1 400 |

- **Incoming fire and damage at tick33 match the 1997 coupling** over the window where every arm is alive. The roll
  rate is x1.25, but the rounds that hit and the damage asked do not rise. AI-DAMAGE-BALANCE item 5 saw the same: the
  extra rounds miss.
- Over each arm's own longer window, tick33's 151 shots /min against e24's 81 is a window artefact. e24's window ends
  at the death, before the fight's peak. The tick-finish lane saw the same with promotion 18.
- **New: the "player killed despite god" event is not promotion 18's alone.** The stock loop at 24 fps kills the
  god-held T13 player at 43-46 s (4 / 5). Promotion 18 does it at 53.6 s (5 / 5). tick33 does it at 77 s in 1 of 7
  boots, and tick66 in 0 / 5. Its cause (the god flag does not cover it) is not traced. It looks step- or
  frame-coupled, since it shows in the 41.7 ms arms.

**Other per-frame AI** (ai.md, PER-FRAME-AUDIT s.1 A1 / A2):
- **The sight-ray token:** one terrain ray per frame across all AI cars, round-robin. With 5 attackers each car gets a
  ray every 6 frames: 0.25 s in 1997, 0.2 s at tick33, 0.4 s at tick66, 0.05 s under promotion 18 (120 Hz).
- **The route search:** 100 cells per frame, time-sliced. The dodge check `ai_TestControlCandidate` 0x41b270 rolls a
  rand gate per call.
- **Handbrake-skid and horn rolls** (`ai_ShouldSkid` 0x41f590, `ai_WillCollideOnPath` 0x41d8b0):
  - one roll per frame: 24 /s in 1997, 30 / 15 under the ticks;
  - **120 /s under promotion 18**, whose preset sets `I76_AI_ROLL_HOLD=0` (count only). So the driver's AI pulls
    handbrake turns about 5x as often as in 1997. Static, not measured here.
- **Frame windows:**
  - the back_away stuck test needs 4 consecutive frames of low grip: 167 ms in 1997, 133 / 267 ms at tick33 / 66,
    and 200 ms under promotion 18 (`I76_AI_BACKAWAY_GRID`);
  - isRammed / isAttacked are true in the frame of the event and the next one.
- **On sim time, so clock-based:** behaviour time-ups, the manoeuvre timer, the 5 s line-of-sight loss, just-do-it's
  1.5 s, and the FSM script's waits (`timeGreater` / `timeLesser`; framerate.md: no stock machine counts passes).
- **The throttle / steering one-frame gains** (0x40f9c0, 0x40fe80) divide by sim_dt. That is a dead-beat controller,
  consistent at any constant step. Its 1997 trouble was dt jitter, which the tick does not have.

## 4. Projectiles and effects (rows 19-33)

- **Flight:** life -= dt (0x4a0990), displacement and gravity by dt, the rocket's speed easing at 0.5 x dt, mortar
  ballistics, bomblet fuses. All clock-based (PER-FRAME-AUDIT s.2).
- **The radar missile's turn** (0x4aa9f0) is a fixed angle per step. So it turns x1.25 as fast at tick33 and x0.63 at
  tick66. Promotion 18 scales it to the 20 fps rate (F2).
- **The heat missile** snaps to its target every step, which is rate-free.
- **Tracers:** the drawn streak is one projectile step of travel (the 2-slot ring 0x52ba48, TICK-FINISH s.10.2). At
  200 m/s that is 8.3 m in 1997, 6.7 m at tick33, 13.3 m at tick66 and 1.7 m under promotion 18. Tracer life is the
  round's life: clock.
- **Explosions and impact sprites** expire on sim time (template duration, texture animation 0.1 s per frame on the
  sim clock; TICK-FINISH s.11.4). Skid marks expire on time.
- **Smoke puffs** live 20 render calls and spawn per call (`renderer_UpdateSmoke` 0x4414a0). Under the tick both
  happen per tick. So a smoke trail is 0.8x as long-lived at tick33 (0.67 s against 0.83 s) with 1.25x the puffs:
  about the same count on screen, a shorter trail. This covers the damage-smoke emitter (`entity_UpdateDamageSmoke`
  0x466ca0) too.
- **Missile trails** lose 4 segments per call in their last 2 s. The **locked-on radar ping** plays per render pass.
  The **HUD ammo digits** roll one step per call. All are per tick under the tick, and on the 20 Hz grid under
  promotion 18.
- **Per-call camera constants:** the free-look / orbit keys at 1 deg per call, the end-of-match spin at 8 deg per
  call, cloud scroll and map zoom. The tick scales them to the *tick's* per-second rate (`I76_SIM_TICK_COSMETIC`):
  x1.25 at tick33. Promotion 18 scales them to 20 fps.
- **Camera chase lag, cockpit sway, screen shake** (2 x dt easing) and the radar sweep (0.2 s steps on sim time) are
  clock-based.

## 5. Damage states, sound, music, input (rows 9-11, 34-38)

- **Damage states:**
  - the health fraction, the damage-smoke levels and part break-off follow hp (events);
  - the wreck's 10 s timer and regen points (30 s) run on sim time;
  - repair happens only in the garage or by the trainer.
  - **The wreck debris roll** (`entity_Wreck(obj, 0)`, rand() & 15 per `entity_UpdateState` call, at the start of
    every substep) is per substep. 1997 at 42 ms: 24 /s. tick33: 30. tick66: 2 x 15 = 30. Promotion 18: 24.
  - 2 of 16 rolls spawn the X1_CARS1 secondary blast: 2 damage to every car within 10 m, and it knocks off every
    class-4 breakable in the circle.
- **No burning state:** a vehicle has no damage over time. The only lasting fire is the Fire-Dropper patch (row 5),
  and the flamers.
- **Sound:**
  - Sustained loops and vehicle sound starts were fixed under the tick: 0.85 starts /s against 0.89 for the stock
    30 fps loop (TICK-FINISH s.10.3).
  - The WMISS click, the lock tones and impact sounds follow the pass rate: x1.25 at tick33.
- **Music:** it plays through MCI / CD audio on the wall clock. Its cues come from script events. Clock-based.
- **The keyboard throttle notch** ramps a fixed step per input pass (0x44f306 / 0x44f366): 1.25x faster at tick33.
  Steering is an absolute function of a dt hold timer, so it is clock-based.
- **Engine smoothing:** `physics_UpdateEngine` 0x46a320 reads the whole-frame dt in every substep. At tick66, 2
  substeps x 66.7 ms make the engine's RPM / torque smoothing run 2x per tick. That is the stock bug of > 50 ms
  frames, which 1997 at 42 ms did not hit. tick33 and 1997 take 1 substep. The T06 acceleration rows still pass at
  tick66 (TICK-FINISH s.4.4).

## Recommendations

**Scale to the 1997 value by default** (a per-tick factor, the way flame damage is being done; factor = 24 / tick
rate, or the 20.8 fps cell's 21 / tick rate if the owner prefers it):

| system | where | tick33 factor | tick66 factor | note |
|---|---|---|---|---|
| flamer damage | `flame_damage_wrap` (in progress, flame lane) | 1.34 (668 / 500) | 1.34 | the only damage source too slow |
| Fire-Dropper patch damage, oil-slick contact | hazard steps 0x4aa450 / 0x4aa150 -> sweep 0x435830 | 0.8 | 1.6 | hold every 1.25th tick at 33 (as F1 holds to 20 Hz); at 66 two sweeps per tick |
| sustained collision re-application | `coll_damage_wrap` sites 0x4644bc / 0x46f8d4 | 0.8 on repeats only | 1.6 on repeats only | the first impact stays whole |
| wreck debris / secondary blast roll | `entity_Wreck(obj, 0)` roll 0x4664ed | 0.8 | 0.8 | gate the roll; the blast knocks breakables off |
| radar-missile turn per step | 0x4aaca0 / 0x4ab400 (`radar_turn_wrap`, F2) | 0.8 | 1.6 | reuse F2 with a 24 Hz reference |

**Already matches 1997 (leave alone):**
- gun, cannon, rocket and missile fire rates, and damage per round;
- gun damage per second (measured 1.00-1.05x);
- dropper and mine cadence, projectile flight and life, heat missiles;
- landing, blast, mine and terrain damage;
- AI incoming damage (measured);
- AI timers and script waits, explosions and sprites, the radar sweep;
- sustained sounds, music, camera easing;
- flamer stream length.

**Owner judges by feel** (the per-frame AI tempo and looks; 1.25x at tick33, 0.63x at tick66):
- AI awareness (the sight ray, the route search, the dodge rolls);
- AI handbrake-skid and horn rolls. **Under promotion 18 these run 5x the 1997 rate**, which may be part of how the
  driver's AI feels;
- the AI stuck window;
- the tracer streak length (shorter at 33, longer at 66);
- smoke-trail length and missile-trail fade;
- the locked-on radar ping, the WMISS click, lock tones;
- the keyboard throttle notch ramp;
- free-look / orbit / death-spin speed;
- at tick66, the engine's doubled smoothing.

If the owner wants "exactly 1997" for these too, the same per-tick factor approach applies. None of them changes
damage.

## Not measured, and why

- **The emulator (retail 1.0) itself.** The guns / ram / T13 drivers need the proxy's drive block, trainer and
  damage-event telemetry. e24 stands in, on the strength of AI-DAMAGE-BALANCE item 4. The owner's exact 1997 settings
  (640x480, mirror on, his detail) have no emulator cell: the nearest are n 1 at 20.8 / 21.8 fps.
- **Fire-Dropper / oil-slick damage per second under the tick.** No dropper-armed AI car was staged. The rate is from
  the code (one sweep per projectile step) and PER-FRAME-AUDIT's F1 measurement (20 contacts /s at 20 fps).
- **Sustained scrape damage** (row 8). From the code and the ram records only.
- **Wreck debris roll rate, AI sight-ray / skid / horn rates, radar-missile turn, smoke and tracer looks.** Static only.
- **Flamer damage after the flame lane's factor** (its own record, TICK-FINISH s.12 when written).
- **Why the god-held T13 player dies at 43-46 s at e24** (and 53.6 s under promotion 18). Not traced.
- **The ram measurement's target is an armed, moving AI car.** A fixed-object ram (a T01 building) would be cleaner.
  Not run.
