# AI and damage metrics from memory (2026-10-17)

Lane `ai-damage-metrics-design`. Goal: make AI behaviour and damage balance measurable from game memory, so that exes,
emulated hardware and frame rates can be compared on difficulty. Owner question: "AI behavior is key for difficulty
balance, net damage rates in both directions, etc."

What exists now:
- **I76AIM.EXE**, a companion logger to I76MEM. It runs in the emulated Windows 95 guest, or on the host against our
  exe. It is read-only and recognises three builds: retail 1.0, Gold CD / GOG 2017, and GOG AiO / our exe.
- **`ai_damage.py`**, the host-side analysis.
- **`gen_aidmg.py`**, which writes the scripts. Validation runs: P166, Instant Melee, retail 1.0 (simulation DEF) and
  Gold.

Lab commits `c3d1b44`, `6a241f8`, `2c39bf8` (I76AIM build 2026-10-17c). Code paths: lab `emu\probe\i76aim.c`,
`emu\tools\memtrace\ai_damage.py`, `emu\tools\memtrace\gen_aidmg.py`, `emu\tools\par\scripts\aidmg-*.txt`.

## 0. Answers first

1. **Every metric asked for has a memory source in all three exes.** No hook is needed (section 1):
   - AI position and velocity;
   - target, and behaviour (the exes differ here);
   - rounds fired per weapon;
   - damage taken and dealt, attributed per source;
   - AI deaths, with who killed them;
   - time-to-kill and time-to-die.

   The attribution comes from a structure the engine already keeps. The AI damage-event recorder (Gold `0x4157a0`,
   retail `0x40fc80`, same offsets) writes into **every vehicle's** AI block, the player's included:
   - who shot it, who rammed it, who attacked it last;
   - when (sim time);
   - whether the player killed it.
2. **Cost.** I76AIM's reads took 0.35-0.86 % of guest time on the P166 with one AI car. The figure comes from its own
   timer, n = 3 blocks per exe (section 3).
   - **Retail:** the in-boot frame-rate A/B shows no cost. On minus off: +0.10, +0.18, -0.20 fps. For scale, the off
     blocks alone drifted over 1.65 fps.
   - **Gold:** -2.30, -0.16, +0.45 fps (mean -0.67 = -2.1 %; A/A range 0.55 fps). This is not a clean null. The -2.3
     block contains the logger's 44 ms start-up sample.
   - **Use I76AIM in combat runs, not in physics-reference runs.**
3. **First measurements** (n = 1-2 per exe: demonstrations, not results):
   - **T13, player parked (n = 2 each).**
     - Time-to-die from first damage: retail 42.5 / 42.9 s, Gold 29.7 / 38.0 s.
     - Damage per hit event: Gold 82 / 111, retail 59 / 86 (overlapping; loadouts differ through the Gold data
       retune).
     - About 3 attackers at once in both exes.
     - The mission's AI settings are identical in both exes (section 5.2).
   - **Melee, player parked at the spawn.** Retail's AI car stalled about 90 m short and wrecked itself three times,
     never firing. Gold's reached 6-12 m.
   - **Melee2, player driven to the reference park position.** The retail AI attacked from 47-161 m, landed 98 hit
     events and killed the player. Gold at Champ: 38 events in twice the time, and the player survived.
   - Spawn position and route decide melee outcomes. Use T13-type missions and n >= 5 for real comparisons.
4. **The Gold par runs were all on difficulty Wimp.** The par base's `<gold game folder>\I76PLYR.DEF` has difficulty byte
   +0x5c = 0. Gold multiplies player-fired bullet and flame damage by 2.0 at 0, 1.0 at 1 and 0.75 at 2:
   - bullets 0x4a76e7, flame 0x4443a8;
   - the levels are Wimp / Champ / Badass in the Gold manual;
   - retail 1.0 has no difficulty option and no factor (I76-VERSIONS.md 4.3; retail's damage builder 0x45ced0 checked
     here).

   This changes no physics. It does change every damage-balance comparison: retail vs Gold must use Champ.
   `aidmg-melee2-champ-gold.txt` sets it. The daily driver's DEF also holds 0 (FIX-INVENTORY-2026-10-17.md section 9).

   **Note 2026-10-20 night (DIFFICULTY-OPTION-2026-10-20.md):** "retail 1.0" in this record means the emulated 1997 retail disc
   (`6cc509ad`). The exe we ship (`6319abf7`, AiO) is in the Gold column of section 1.1: it has the Difficulty Level option
   (shell a300db63 Play Options row 7, pause menu handler 0x495e40, the same byte 0x654b9c / DEF +0x5c) and the factor.
   It was measured on T13, player damage per hit 50 / 25 / 18 at Wimp / Champ / Badass (n 3 / 2 / 2 runs). The factor is
   offline only (`net_IsNetworkGame` 0x452d20 gates both sites). The driver, the LAN copy and the release candidate hold 0 =
   Wimp, so the owner's offline play doubles his own damage.
5. **pd+0x10 is identified, and retail sides with Gold CD.** This answers FIX-INVENTORY's RE-CHECK items 4 and (a).
   - **Retail's recorder** 0x40fc80 tests `[pd+0x44]` (`cmp [eax+0x44],1; sbb; neg` at 0x40fcfb), as the Gold CD exe
     does. **Our exe (AiO)** tests `[pd+0x10]`.
   - **What pd+0x10 is:** the **projectile's target**. weapon_FireShot 0x4a6e90 stores the chosen target at
     request+0x28 (`[esp+0x34]` after the radar / arc / heat searches 0x4613f0 / 0x461570 / 0x4a82c0, request at
     esp+0xc). weapon_ProjectileInit 0x4a0ae0 copies request+0x28 to pd+0x10 (0x4a0b3b) and request+4 (the shooter) to
     pd+0xc.
   - **Effect.** A hit by a projectile with no target sets only the "attacked" stamp. It does not set the "shot" stamp
     and shooter in our exe. In Gold CD and retail that happens only for a zero-damage projectile.
   - **Consequence.** In our exe, an AI car hit by a projectile that had no target does not see `isShot`. In the Gold
     run every one of the 13 player hits on the AI car set its shot stamp (section 4.3).
   - **Rams.** For a ram, the recorder's arg4 is the ramming vehicle, and the test reads its entity +0x44 (Gold CD,
     retail) or +0x10 (AiO). Neither field is identified, so the effect on ram stamps is open.
   - **Test.** The same melee with I76AIM on our exe. Section 6 gives the steps.

## 1. The memory map (static; confirmed live where marked)

All three exes keep the same object / entity layout (addrmap-retail.md):
- **Object:** `+0x10` flags (0x10 the local player, 0x20 destroyed, 0x200 dead / wreck), `+0x40` double[3] position.
- **Entity** (`[obj+0x70]`): `+0xac` speed, `+0xbc` velocity, `+0x138` armour int[4], `+0x148` chassis int[4], maxima
  `+0x158` / `+0x168`, `+0x454` flags (0x20 dead, 0x8000 wreck, 0x10000 Arcade Phys.), `+0x108` the AI block.

### 1.1 Per-exe addresses

| item | Gold CD / GOG 2017 / AiO (our exe) | retail 1.0 | how found / checked |
|---|---|---|---|
| AI team lists / counts | 0x507da0 / 0x51f5d0 | 0x4edc30 / 0x505460 | EMU-MEMTRACE; live in all runs here |
| player root | 0x54a264 | 0x4d3b64 | addrmap-retail |
| damage-event recorder | 0x4157a0 (callers 0x4a821c collision / projectile, 0x4a8298 flame) | **0x40fc80** (callers 0x45db22, 0x45db97) | same stores (+0xa6d4..+0xa6f0), same tail (+0xa6e0 = 1 if the dead car's attacker is the player root object) |
| AI event frame counter | 0x524550 | **0x505518** | read by both recorders |
| SetBehaviour | 0x412830 (stack ai+0xa874[ai+0xa93c]) | **0x40cc10** (single slot: ai+0xa82c+0x48 = ai+0xa874) | retail has no reference to +0xa93c or +0xa944; its +0xa82c behaviour block has +0x48 / +0x110 / +0x118 where Gold has the stack |
| target (ref-counted) | ai+0xa9b4 | ai+0xa9b4 | 16 references in each exe |
| counts-as-attacker-of | ai+0xa998 | ai+0xa998 | 23 references each |
| aggression / skills | ai+0xa818 / +0xa81c..+0xa828 | same offsets | writers 0x40bd53.. / 0x40b445..; default init writes aggression 4 (retail 0x40fb85) |
| weapon instance table | **0x5aab08**, stride 0x4c, count [0x5da750] (cap 0x41a) | **0x55f9c0**, stride **0x50**, count [0x570a64] | init Gold 0x4a52e0, retail 0x4571f0 |
| instance: vehicle record / slot / ammo / weapon def | +0x18 / +0x1c / **+0x20** / +0x30 | +0x10 / +0x14 / **+0x18** / +0x28 | ammo -= count in FireShot: Gold 0x4a6f64, retail 0x45880d (clamped at 0); init ammo = min(GDFC 94, loadout): Gold 0x4a53ab, retail 0x45724b |
| instance: name | weapon definition 0x5d88d8 + def x 0xd8, +0 | **copied into the instance at +0x2c** (retail copies the def's +0x88 string, which is the fire sound: `wlmgun.wav` = light MG) | live: Gold `30cal MG`, `7.62mm MG`, ...; retail `wlmgun.wav`, `whmgun.wav`, `wmflame.wav`, ... |
| vehicle weapon record | 0x5be4d8, stride 0x2c8, count [0x5da78c]; +0 = vehicle object | 0x566950, stride 0x2c8, count [0x570aa0] | loops 0x4a5315 / 0x454c2f |
| difficulty | byte 0x654b9c (I76PLYR.DEF +0x5c) | none | Gold option handler 0x495e40; no "Difficulty Level" string in retail |
| identifying bytes (I76AIM) | 0x415806: `8b 44 24 24 85 c0 74 15 8b 40 70 85 c0 74 0e 8b 50` **44** (Gold CD) / **10** (AiO) `33 c9` | 0x40fcec: `8b 44 24 28 85 c0 74 11 8b 40 70 85 c0 74 0a 83 78 44 01 1b` | checked against e1dca993, 6319abf7 (daily driver), 9a232dcc, 6cc509ad, and live in all three |

The AI block's event fields: these offsets are the same in all three exes, and they are written for any vehicle
target that has an AI block (the player has one; live).

| offset | field | written |
|---|---|---|
| ai+0xa6d4 | shot stamp (event frame counter) | event type & 0x18 (projectile / explosion), unless the skip test (above) holds |
| ai+0xa6d8 | ram stamp | other event types (collisions), same skip test |
| ai+0xa6dc | attack stamp | every recorded event |
| ai+0xa6e0 | 1 = the car died with the player as its last attacker | recorder tail, when entity +0x454 has 0x20 |
| ai+0xa6e4 / +0xa6e8 / +0xa6ec | who rammed / who shot / who attacked (object pointers, never cleared) | as the stamps |
| ai+0xa6f0 | sim time of the last event | every recorded event (FSM reads never clear it) |

FSM reads (isShot / isRammed / isAttacked) reset the stamps to -10 (<re-archive> ai.md M44a). The logger therefore uses the
sim time +0xa6f0 to detect new events, and the stamps only to label a new event "shot" or "ram".

What the recorder does **not** see: an attacker that is not a vehicle (class 1 / 8 / 9: the attacker test 0x458a90),
terrain, and landings. Health lost without a new event is reported as `unattributed`.

## 2. The logger and the analysis

### 2.1 I76AIM

`I76AIM.EXE [seconds] [out] [/exe=] [/p=MS] [/slow=N] [/wevery=N] [/notimer]`. Defaults: 200 ms, slow 2, weapons 5.
- **Every sample, for the player and each car on the team lists (up to 24):** object flags and position, the entity
  speed..armour span, and the AI event block (3 reads per car).
- **Every 2nd sample:** entity flags, behaviour, target and attacker-of (2 reads per car).
- **Every 5th sample (about 1 s):** the whole weapon instance table in one read. Ammo is a counter, so a low rate loses
  no rounds.
- **Every 25th sample:** a re-walk of the team lists. An `ACAR` record (name, team, aggression, skills, maxima) is
  written for each new car, and again whenever these change (build 2026-10-17c). First-sight values predate the
  mission script and the save's loadout:
  - T13 AI: aggression 4 and skills 0.4 / 0.4 / 0.2 / 0.6 at first sight, 1 and 1.0 / 1.0 / 0.8 / 0.9 once the
    mission runs (the same in both exes);
  - the T13 player's maxima: 2800 + 2000 at first sight, 5600 + 4000 in the mission (I76DRV `ent` agrees).
- **The difficulty byte.**

The records are documented in the source header. Validated:
- Win95-clean and P54C-safe (build.ps1);
- in the guest on retail 1.0 and Gold;
- on the host against our exe (a 9-sample read of the envelope lane's running T05 copy, `game-envrb`, 6319abf7;
  `/notimer`, read-only).

### 2.2 ai_damage.py

`python -I emu\tools\memtrace\ai_damage.py RUN... [--phases ai,fire] [--json] [--md] [--dump]`.
- Phases come from I76DRV's `log MARK` lines (the mem2csv rule).
- Rates are per minute of **sim time**, so frame rate and VM speed cancel.

| metric | definition | caveat |
|---|---|---|
| damage taken / dealt | armour + chassis drop between samples. The source is the AI block's attacker if its event time changed in that window. Kind = shot / ram from the stamps, else `unattributed` | Two sources within one 200 ms window are credited to the later one. Component damage (engine, weapons) is not in armour + chassis |
| hit events | new event times on the target | At most one per window, so a lower bound. MG rounds are batched per frame (weapons.md) |
| rounds fired | ammo drops per mount (owner, slot, weapon def), summed per owner | Unlimited-ammo weapons (0x0FFFFFFF) still count down. A death or respawn compacts the instance and record tables; scans in which the instance count changed are skipped and counted (`skipped_scans`). Before build 2026-10-17b, owners were cached between rescans, and retail run 054109 credited the AI's guns to the dead player |
| hit rate | hit events on the player / rounds the car fired | Event level |
| dmg per round | damage the car did to the player / its rounds | |
| engagement distance | ground distance car -> player at each of the car's hit events on the player (p10 / p50 / p90); also the time-weighted distance while the car's target is the player | |
| attackers | cars whose target is the player: mean and max at once | |
| AI deaths, killer | transition to dead (object 0x20 or entity 0x20, the latter carried between slow samples). Killer: `player` (+0xa6e0), `self` (attacker = the car), or the attacking car | `self` covers the rollover rule and crash damage the car recorded against itself |
| time-to-kill | from the player's first damage on a car to its death, for player kills | |
| time-to-die | player's first damage taken to the player's dead flag; and health at phase start / damage-taken rate | |
| behaviour | time share per behaviour id per car | Gold = top of the stack, retail = its single slot. **The id tables are not shown to match** (retail has a different machine) |

## 3. Cost

In-boot A/B: script `aidmg-cost-<exe>`, Instant Melee, player parked.
- I76MEM runs throughout and gives the frame counts.
- Blocks of 15 s alternate off1 / on1 / off2 / on2 / off3 / on3, and I76AIM runs only in the "on" blocks.
- n = 3 blocks each per exe. Runs: `20261017-053547-aidmgcost-r166-1`, `20261017-053607-aidmgcost-g166-1`.

| exe | off1 | on1 | off2 | on2 | off3 | on3 | on - preceding off | I76AIM's own read time |
|---|---|---|---|---|---|---|---|---|
| retail 1.0 | 35.13 | 35.23 | 35.82 | 36.00 | 36.78 | 36.58 | +0.10 / +0.18 / -0.20 fps | 0.35 / 0.62 / 0.37 % |
| Gold | 32.10 | 29.80 | 31.55 | 31.39 | 31.76 | 32.21 | -2.30 / -0.16 / +0.45 fps | 0.86 / 0.55 / 0.58 % |

Each block's median step was 27-28 ms (retail) and 31-32 ms (Gold).
- Per sample: about 13 reads and 0.7-1.7 ms with one AI car. A mission with 8 cars costs about 3-4x that.
- The full-run self-reports, with I76MEM also running: retail 0.47 %, Gold 0.49 %.
- **Reading.** The cost is below the run-to-run noise in retail. Gold's first "on" block lost 2.3 fps against 0.55 fps
  of A/A spread. That block holds the 44 ms start-up sample (all ACAR / ANAM reads at once).
- **Rule.** Physics references stay I76MEM-only. Combat runs add I76AIM, or use `/p=400` for missions with many cars.

## 4. Validation runs (P166, software, lowest detail, simulation physics)

| run | exe / DEF | script |
|---|---|---|
| `20261017-052641-aidmg-r166-1` | retail 1.0, RPLYR.DEF via filehex (option flags 0, Arcade off: 0 of 1100 samples with 0x10000) | aidmg-melee-retail: spawn, settle 5 s, **ai** 60 s parked, **fire** 40 s parked holding Space 3 s / 1 s |
| `20261017-052706-aidmg-g166-1` | Gold, base DEF (**difficulty 0 = Wimp**) | aidmg-melee-gold, same |

### 4.1 Results (n = 1 per exe, rates per sim minute)

| run | phase | exe | dur s | fps | taken /min | dealt /min | AI rounds /min | player rounds /min | hit events on player | AI deaths /min | attackers mean | engage p50 m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aidmg-r166 | ai | retail | 60.2 | 36.3 | 0 | 0 | 0 | 0 | 0 | 1.0 (self) | 0.78 | - |
| aidmg-r166 | fire | retail | 41.8 | 34.8 | 0 | 0 | 0 | 406 (2 scans skipped) | 0 | 1.4 (self) | 0.74 | - |
| aidmg-g166 | ai | Gold | 60.2 | 31.5 | 24 | 0 | 18 | 0 | 1 | 0 | 1 | 31 |
| aidmg-g166 | fire | Gold | 42.0 | 29.8 | 494 | 908 | 64 | 434 | 10 | 0 | 1 | 12 |

### 4.2 Per car

- **Retail `nvcl0`** (3 objects in turn).
  - Armour 3200 + chassis 3200 (Gold: 2400 + 2400; the Gold data retune, I76-VERSIONS.md).
  - Targeted the player for 47 of 60 s (mean 186 m) and 31 of 42 s (148 m). Behaviour slot 6 the whole time.
  - Each object drove toward the player and stopped about 90 m short, near (2510, 49835); the player was at (2612,
    49882). It sat there with entity flags toggling 0x10 / 0x200 and took 11-16 chassis.
  - About 10 s later it became a wreck: flags 0x80089024 (0x8000 + 0x20). Its event fields then name itself as
    attacker. The game respawned it.
  - Wrecked (flags 0x8000 + 0x20) at sim 44.5, 92.1 and 128.9 s; the last at the mission's end.
  - Not one round fired.
- **Gold `nvcl0`.**
  - Aggression 2, skills 0.6 / 0.6 / 0.6 / 0.8 (retail's car read the same in melee2).
  - Behaviour shares (stack top): 17 42 %, 18 21 %, 21 18 %, 8 11 %, 6 7 %, 7 1 %.
  - Fired 18 rounds in the ai phase (30cal 10, 7.62 mm 8) and 45 in the fire phase (21 + 24).
  - Hit events on the player: 1, then 10. Event hit rate 0.06 / 0.22. Damage per round 1.3 / 7.7.
  - Engagement p50 12.1 m (p10 6.3, p90 54.4, n 10) in the fire phase.
- **Player.**
  - 1600 + 1600 at the start, 1 + 10 events, 370 damage taken.
  - Fired 283 rounds in retail (2 scans skipped at AI respawns) and 304 in Gold, in 40 s with the trigger held 30 s.
    That is about 10 rounds per second held.
  - Gold: 636 damage dealt on 13 events, about 30 / 60 armour per sample. That is 2.09 per round **at Wimp x2.0**.
- **Not shown by these two runs.** That retail's AI is weaker in general. The retail car got stuck at one place on the
  way, and with the player parked at the spawn point that decided everything. The reference melee run
  `20261017-011503-r166-meleeai-1` (player driven first) logged 16 hits on the player in 30 s in retail.
- **Retracted: "retail's melee AI gets different settings".** The first draft said so: aggression 0 and skills 1.0 in
  retail run 052641, against 2 and 0.6 / 0.6 / 0.6 / 0.8 in Gold. In melee2, retail's car read 2 and
  0.6 / 0.6 / 0.6 / 0.8. The values were first-sight snapshots taken before the melee set them (section 2.1).

### 4.3 Event attribution checks

- **Gold, player hits on the AI car.** All 13 events have shot stamp = attack stamp, shooter = the player object, and
  an armour drop of 30-60 per window.
- **Gold, AI hits on the player.** All 11 are kind `shot`, from `nvcl0`.
- **Retail.** No event on the player. The AI's own events after the wreck name itself.
- **The player's `ent` lines in I76DRV.LOG** (armour / chassis at ai-start, fire-start and end) agree with I76AIM's
  sums: Gold end armour 127 + 361 + 385 + 376 and chassis 387 + 400 + 400 + 394, i.e. 2830 = 3200 - 370. The first
  analysis lost 15 of these in the window straddling the ai / fire boundary. Such windows now go to the later phase.

## 5. Melee2 and T13 (P166, simulation)

### 5.1 Melee2: player driven to the reference park position

Script `aidmg-melee2-<exe>`: the reference melee's driving phases (settle, accel, brake, steer R / L, cruise, park),
then ai 60 s and fire 40 s.

Runs:
- `20261017-054109-aidmg2-r166-1`: retail, RPLYR.DEF;
- `20261017-054129-aidmg2champ-g166-1`: Gold, with the DEF difficulty byte written to 1 = **Champ** (filehex, read
  back identical).

n = 1 each. The whole mission, phases summed:

| exe | sim s logged | hit events on player | damage taken | AI rounds | engagement (p50, by phase) | outcome |
|---|---|---|---|---|---|---|
| retail | 74.6 | 98 | 978 | 323 (light MG 129 + rockets 15 + light cannon 47 in the ai phase) | settle 47 m, cruise 161 m, ai 63 m | **player killed** 18.0 s into the ai phase; fire phase never reached |
| Gold, Champ | 153.0 | 38 | 1207 | 722 (30cal + 7.62 mm; Oil Slick 3, BloxDropper 2) | ai 14 m, fire 44 m | survived; the player dealt 4 |

Why the retail player died:
- The retail AI hit the player from the start (settle: 7 events, 315 damage) and during the cruise (29 events, 464).
- At ai-start the player's armour read 128 / 400 / 293 / **0** (I76DRV `ent`). With one side at 0, hits reach the
  components, and a hit on a destroyed component can roll a kill (<re-archive> damage.md).
- So the player died with about 2200 armour + chassis left. **Armour + chassis alone does not predict death.** The
  extrapolated time-to-die is a rate, not a forecast.

### 5.2 T13: several AI cars

Script `aidmg-t13-<exe>`: the "T13 start (emu)" bookmark, opening skipped, player parked 90 s, then fire 40 s (never
reached: the player died in every run).
- **Runs:** retail `20261017-055125-aidmgt13-r166-1` and `-055828-aidmgt13b-r166-1`; Gold `-055145-aidmgt13-g166-1`
  and `-055848-aidmgt13b-g166-1`.
- **Difficulty.** Gold is on the base's difficulty 0. That does not matter here, because the player never fires.
- **Settings.** 11 cars on the lists. The mission's AI settings (aggression 1, skills 1.0 / 1.0 / 0.8 / 0.9) and the
  player's maxima (5600 + 4000) are the same in both exes.

The ai phase (parked), n = 2 per exe:

| metric | retail run 1 | retail run 2 | Gold run 1 | Gold run 2 |
|---|---|---|---|---|
| fps | 29.1 | 28.5 | 25.5 | 25.3 |
| first damage, s into the phase | 18.4 | 18.3 | 18.2 | 17.9 |
| **player dead at, s** | 60.9 | 61.2 | 47.9 | 56.0 |
| **time-to-die from first damage, s** | **42.5** | **42.9** | **29.7** | **38.0** |
| damage taken before death | 1835 | 2230 | 2203 | 4234 |
| hit events on the player | 31 | 26 | 27 | 38 |
| AI rounds / min | 128 | 80 | 126 | 152 |
| attackers on the player, mean (max) | 2.8 (4) | 3.3 (4) | 3.4 (4) | 3.3 (4) |
| main damage source | t13pp02 1812 (85 m) | t13pp02 1401 (138 m), t13cg02 824 | t13pp02 1536 (100 m), t13cg02 576 | t13pp02 3556 (81 m), t13cg02 618 |
| AI-vs-AI damage | 0 | 225 | 159 | 102 |
| I76AIM reads per sample / cost | 35 / 1.02 % | 37 / 1.04 % | 36 / 1.36 % | 37 / 1.51 % |

Reading:
- **Retail kept the player alive longer in both runs.** Time-to-die 42.5 / 42.9 s against 29.7 / 38.0 s. This is
  not a result: n = 2 vs 2, so the exact two-sided rank test can do no better than p = 0.33.
- **Retail's two runs agree within 0.4 s, Gold's differ by 8 s.**
- **Damage per hit event:** Gold 82 / 111 (2203 / 27, 4234 / 38), retail 59 / 86 (1835 / 31, 2230 / 26). The ranges
  overlap.
- **The loadouts differ by exe** (the Gold data retune, I76-VERSIONS.md):
  - t13pp02: retail heavy cannon + rockets (`whcan`, `wrhm`), Gold 30 mm cannon + DrRadar missiles;
  - vfratlr1: retail light / medium MG, Gold 30cal turret + 50cal.
- **First damage arrives at 18 s in all four runs.** This is the mission's own timing.
- **Kinds.** Much of the damage is kind `event` (attack stamp set, shot / ram stamps not equal to it) rather than
  `shot`. It comes from cannon shells and missiles. Whether those record as type 0x18 or whether an FSM read reset the
  shot stamp first is not resolved. The source car is attributed either way.

## 6. What it is for, and what is next

**How to measure difficulty across exes, hardware and frame rate.**
1. Run the same script with I76AIM on each condition: retail P166 / P133, Gold, and the lab exe on the host at stock20
   / best-wide.
2. Compare, n >= 5 per condition, A/A first:
   - damage taken and dealt per sim minute;
   - AI rounds per minute and event hit rate;
   - engagement distance;
   - attackers at once;
   - time-to-die.
3. The rates are per sim time, so a slower machine's lower fps is not mistaken for a gentler AI.

**Missions.** Melee has one AI car. The lab's combat-parity campaign used t05 / t13 / t15 / t17, where the AI attacks
an idle player (lab AI-COMBAT-PARITY-2026-10-13.md s.2). The retail par saves have T04 / T05 / T13 bookmarks
(gen_scripts.py `ROWS`). `aidmg-t13-<exe>` (section 5.2) is the multi-car test. A T04 / T05 version is the same
three lines in gen_aidmg.py.

**Our exe on the host.**
- I76AIM runs there unchanged: `I76AIM.EXE 0 out.bin /exe=i76.exe /notimer`. It reads the same fields as the proxy's
  in-process `I76_COMBAT_LOG`, so the two can be cross-checked.
- Headless lab runs cannot enter Instant Melee (LAB-FRAME-REPLAY.md). A combat mission by direct boot (`I76_MISSION`
  t13) under the lab console lock is the way.
- **This is the test of the pd+0x10 difference:** count AI shot stamps on player hits, AiO vs Gold CD.

**Static items left open.**
- The behaviour id tables of retail vs Gold.
- The `event` damage kind (section 5.2).
- Which death rule killed the T13 player (a component kill roll, the at-rest rollover rule, or a script). The entity
  flags carry it.
- Retail's weapon definition table base (names here come from the instance copy, a sound name).
