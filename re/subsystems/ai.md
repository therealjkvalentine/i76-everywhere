# ai

**Contract.** Computer-driven cars are steered by writing the same three inputs the player's keys write:
entity+0xe0 steer, +0xe4 throttle, +0xe8 gear direction. Physics reads them in the next frame's substeps
(`physics.md`). All decisions run once per rendered frame from `ai_FrameTick` 0x40a320. Static reading of
md5 9a232dcc (2026-09-27), batch `ai-map-1` (46 names). It comes from a reviewed read-only draft (cluster G); the
dodge rand gate at 0x41b673 was spot-checked.

## One frame

1. WinMain calls `ai_FrameTick` 0x40a320 after the object ticks. It latches whether the AI drove the player
   (autopilot, 0x40f870). Then, for every vehicle on the 8 team lists (0x507da0, counts 0x51f5d0), it rebuilds the
   forward sweep box ai+0x9d40 (`ai_SetSweepBox` 0x40ae20).
2. **Missions:** `fsm_RunMachines` 0x4149f0 steps every script machine. Scripts loop "action goto / attack / follow
   ...; yield", so each frame every AI car's action calls `ai_SetBehaviour` 0x412830 again.
   **Melee:** `ai_MeleeFrameTick` 0x40a130 sets every live car to attack the player, or brakes them all if there is
   no player.
3. **`ai_SetBehaviour` 0x412830** runs the behaviour record (id x 0x1354; the table starts at 0x4c3e00, each record named at +0, the function pointers from +0x50):
   - exit tests, the enter function, then the update function: goto/evade/race 0x420d30, follow 0x41ef40,
     sit/guard/hide 0x40af00;
   - transitions push and pop the behaviour stack ai+0xa874 (depth ai+0xa93c);
   - attack ids 0..15 go through the selector 0x412680;
   - last, it makes the fire decisions (`ai_FireWeapons` 0x414ef0; see Fire decisions).
4. **Routing:** a shared, time-sliced path search that one car at a time may claim (0x40ad40 / 0x40ad80, step
   0x40f1e0, pool reset 0x40c1a0). It avoids blocked terrain cells (`world_IsTerrainCellBlocked` 0x4926f0; terrain bit
   0x1000 read as blocked, inferred). The update functions pick a target speed (0x40f990) and a heading.
5. **Throttle:** `ai_UpdateThrottle` 0x40f9c0.
   - The speed error x 1/sim_dt is the acceleration that would close the error in one frame.
   - Drag and rolling resistance are subtracted, and the result is divided by drive or brake capacity.
   - It is capped at 0.75 + 0.25 x skill (ai+0xa81c) and at grip (`ai_GripLimitedThrottle` 0x43c600).
   - Helpers: `ai_FullThrottle` 0x410210, `ai_FullBrake` 0x410260, `ai_ThrottleUpBySkill` 0x410170.
6. **Steering:** `ai_SteerToHeading` 0x40fe80 sets steer = gear x skill(ai+0xa820) x heading error / (sim_dt x k x v),
   clamped by grip and maximum steer. Aircraft use 0x40fd20.
7. **Avoidance:** `ai_ChooseAvoidanceControls` 0x41b6e0 searches (steer, throttle) candidates.
   `ai_TestControlCandidate` 0x41b270 predicts one step (`physics_PredictVehicleMotion` 0x43a560) and tests:
   - terrain (0x419930);
   - cars (0x41a530);
   - static colliders (0x41a040);
   - projectiles (0x41abf0), on a random gate, rand() % 1000 at 0x41b673, about 0.15 x skill per call.
8. **Perception:** `ai_CanSee` 0x417bf0 (terrain ray `world_RaycastTerrain` 0x4a7800, then a collider sweep),
   `ai_IsBlockedAhead` 0x419e20 (a 7 m probe), and event stamps against the frame counter 0x524550 (0x4155f0).

## AI block (entity+0x108)

| field | meaning |
|---|---|
| ai+0x9d40 / +0x9d48 / +0x9d4c / +0x9d54 | forward sweep box (min x / min z / max x / max z), rebuilt every frame |
| ai+0x9d28 | time to the terrain hazard ahead |
| ai+0xa818 | aggression - 1 (setAgg) |
| ai+0xa81c | drive skill, throttle: gain on a positive speed error, cap 0.75 + 0.25 x value (table 0x5fcb9c, 0x40bd90) |
| ai+0xa820 | drive skill, steering: heading gain; also the dodge chance (table 0x5fcb7c) |
| ai+0xa824 / +0xa828 | combat skill (tables 0x5fcbdc / 0x5fcbbc) |
| ai+0xa874[50] / +0xa93c | behaviour stack / depth |
| ai+0xa9b4 | current target (reference-counted) |

## Frame-rate behaviour

This corrects `framerate.md`: none of these is a derivative.

| site | reads | kind | effect |
|---|---|---|---|
| 0x40f9c0 throttle | 1/sim_dt | one-frame (dead-beat) gain | command grows with fps; dt jitter drives it into its clamps (the measured throttle chatter) |
| 0x40fe80 steering | /sim_dt | one-frame gain | same shape; saturates harder at high fps |
| 0x417bf0, 0x419e20 | 1/dt with a sim_dt sweep | cancels | neutral |
| 0x41b270 | 1/dt (cancels) + a per-call rand gate + a one-step prediction | per-call | dodge checks 3x as often per second at 60 fps |
| 0x40a320 | 1/sim_dt, nothing to pair with | box length 50/sim_dt m | broad-phase box 1000 m at 20 fps, 3000 m at 60 fps (more candidates only) |

The proxy's `I76_FRAMERATE_FIXES` pins both gains to 20 fps (throttle 0x40fa15 / 0x40fa8d, steering 0x40fed9). Measured
at 60 fps: AI throttle chatter 1.62 against 1.68 at stock 20, steering 0.67 against 0.78 (n = 3 each; capture 014).
The throttle pin alone did nothing; the steering was the cause.

## Quirks

- The projectile velocity at 0x524558, used by `ai_CheckIncomingProjectiles`, is never written, so the AI dodges
  projectiles as if they were stationary.
- 0x41b270 calls GetTickCount and discards the result.


## Behaviours (table 0x4c3e00, 34 records of 0x1354 bytes, name at record +0)

| id | name | enter | update | exits | what |
|---|---|---|---|---|---|
| 0 | tactics init | None | None | ['selector root: candidates 1,3,10,6,9,8'] | attack root: ids 0-6 and 8-15 are chosen by calc_sum 0x412680 (weighted by aggression ai+0xa818, candidates must pass preconditions) |
| 1 | road_ram | 0x416b80 | 0x416bc0 | ['0x41c2c0 rammed -> 14/11/8', '0x41cc00 time up -> 2/3/1/6/8', '0x416cd0 -> 4/5/6/13/9/8'] | ram on the road (road tactic mode 0); pre: vehicle target, 0x41c1d0, same road |
| 2 | rw_flee | 0x416be0 | 0x416cb0 | ['0x41cc00', '0x416cd0'] | road-war flee (mode 1); pre: vehicle target, same road, hurt (0x417060) |
| 3 | road_side | 0x416e50 | 0x416eb0 | ['0x41c2c0', '0x41cc00', '0x416cd0', '0x416ed0 target slow'] | side-swipe/pace on the road (mode 3) |
| 4 | dirt_ram | 0x41c210 | 0x41c2a0 | ['0x41c2c0', '0x41cc00'] | off-road ram (0x420520 mode 0) |
| 5 | dirt_brave | 0x41c830 | 0x41c8e0 | ['0x41c2c0', '0x41cc00', '0x41f860 -> 14'] | off-road attack (mode 3); may push 7 tactic_skid (0x41f590) |
| 6 | dirt_gunner | 0x41c300 | 0x41c430 | ['0x41c2c0', '0x41cc00', '0x41f860 -> 14'] | off-road gun attack (mode 1); pre: ready forward weapon (0x41c3b0) |
| 7 | tactic_skid | 0x41f750 | 0x41f7f0 | ['0x41cc40 maneuver time -> 15'] | handbrake skid turn, pushed by 0x41f590 |
| 8 | dirt_miner | 0x41c900 | 0x41c9b0 | ['0x41c2c0', '0x41cc00', '0x41f860 -> 14'] | off-road attack mode 2 |
| 9 | dirt_standoff | 0x41c5c0 | 0x41c680 | ['0x41c2c0', '0x41cc00'] | keep >= 70 m and face the target; pre: 0x41c450 |
| 10 | road_flee | 0x416f20 | 0x4171a0 | ['0x41cc00', '0x417490 far along road'] | flee along the road; pre: hurt + same road |
| 11 | r_rvs_flee | 0x41e740 | 0x41e890 | ['0x41cc00'] | reverse flee on the road; leave 0x41ee10 |
| 12 | rockford | 0x41e8b0 | 0x41e970 | ['0x41ec20 turned round -> 4/6/1/3/9', '0x41cc00'] | reverse J-turn; leave 0x41ecc0 |
| 13 | dirt_rvs | 0x41ed00 | 0x41c430 | ['0x41cc00'] | reverse attack (mode 1) when the target is slow and near (0x41edb0); leave 0x41ee10 |
| 14 | dirt_flee | 0x41c9d0 | 0x41cae0 | ['0x41cc00'] | off-road flee (mode 4) |
| 15 | dirt_circle | 0x41cb00 | 0x41cbb0 | [] | circle at 10 m/s; the selector's fallback |
| 16 | stop_sliding_backward | 0x41ce50 | 0x41cec0 | ['0x41ce30'] | interrupt (0x41cd90): brake and counter-steer |
| 17 | avoid clsn | 0x41db10 | 0x41dd80 | ['0x41cc40'] | interrupt (0x41d770/0x41d820/0x41d8b0): collision avoidance; -> 18 via 0x41d330; leave 0x41e030 |
| 18 | back_away | 0x41cf30 | 0x41cff0 | ['0x41d170', '0x41cc40'] | interrupt (0x41d240 stuck): reverse out; -> 19 via 0x41d450; leave 0x41d390 |
| 19 | just do it | 0x41d620 | 0x41d6d0 | ['0x41cc40'] | flip gear and floor it 1.5 s; leave 0x41d6f0 |
| 20 | handle too far search | 0x41e160 | 0x420d30 | ['0x41e230', '0x420e70'] | interrupt (0x41e080): path search to the target; -> 21 when found (0x420e50) |
| 21 | handle too far follow | None | 0x420ed0 | ['0x41e230', '0x420f80'] | follow the found path |
| 22 | do search | 0x420a20 | 0x420d30 | ['0x420e70'] | FSM goto: time-sliced path search; -> 23 |
| 23 | follow path | 0x420ea0 | 0x420ed0 | ['0x420f80', '0x420e70'] | drive the waypoints |
| 24 | do evade search | 0x420a20 | 0x420d30 | ['0x420e70'] | FSM evade: search; -> 25 |
| 25 | evade | 0x420ea0 | 0x420fc0 | ['0x420f80', '0x420e70'] | evade along the path |
| 26 | do race | 0x420aa0 | 0x420d30 | ['0x420e70'] | FSM race: search; -> 27 |
| 27 | race | 0x420ea0 | 0x420b30 | ['0x420f80', '0x420e70'] | race along the path |
| 28 | tactic on deck | 0x41e2b0 | 0x41e450 | ['0x41e640 slot free'] | interrupt (0x41e600): wait for an attacker slot on the player; leave 0x41e660 |
| 29 | handle los | None | 0x41cbb0 | ['0x41e720 sight regained'] | interrupt (0x41e680, jammer only): circle until the target is seen |
| 30 | handle follow leader | 0x41eef0 | 0x41ef40 | [] | FSM follow: formation slot keeping |
| 31 | sit | None | 0x40af00 | [] | FSM sit: brake |
| 32 | guard | None | 0x40af00 | [] | FSM guard: same update as sit, target kept |
| 33 | hide | 0x40af80 | 0x40af00 | [] | FSM hide: engine off; leave 0x40afa0 restarts it |

Notes (range O draft): Behaviour names come from the record name field at record-0x50 (0x4c3e00 + id*0x1354 is 'tactics init'; 0x1e is 'handle follow leader', 0x1f 'sit', 0x20 'guard', 0x21 'hide', matching the FSM ids; the string after record 33 is 'unkown turn state', which confirms the -0x50 alignment). FSM goto/evade/race enter the search records 0x16/0x18/0x1a ('do search', 'do evade search', 'do race') and move on to 0x17/0x19/0x1b when 0x420e50 sees the search done. The 'handle los' interrupt only fires while the player's radar jammer is active (0x51f5c8 from entity_IsRadarJammerActive). ai_IsClearOfTeamZero compares a dot product with 6400, not a squared distance (possible original bug; low confidence on intent). Functions 0x420xxx (the dirt tactic driver 0x420520, search update 0x420d30 etc.) are outside the range but are referenced as behaviour functions. Existing name 'astar' (0x40cc90) is really a step-direction compatibility check used by ai_PathSmoothOffroad; 'calc_sum' (0x412680) is the attack-tactic selector.

## Members

`symbols/functions.tsv` rows with prefix `ai_`, plus the `physics_Sweep*`, `physics_Collider*` and `object_*` helpers
of batch ai-map-1.

## Fire decisions (2026-09-27, verified live)

`ai_FireWeapons` 0x414ef0 runs every frame for every AI car, from its behaviour. It asks `ai_ShouldFireWeapon`
0x418200 for each mounted weapon and pulls that weapon's trigger for the frame on a yes (0x4a3560). Turrets
(`entity_TickTurretFire` 0x462a90) do the same, with skill 1.0.

- **The random gate, by weapon class** (skill = ai+0xa828):
  - class 1/2 (guns): three rand() % 1000 summed must be below 6000 x skill;
  - class 3 (mortars): two summed below 3500 x skill;
  - class 4 (rockets, missiles): rand() % 5000 < 1000 x skill^2, i.e. p = 0.2 x skill^2.
  Then aim geometry (lead, arc) decides.
- **Frame-rate dependence.** The gate is rolled once per frame, so a weapon that passes rarely fires up to 3x as
  often at 60 fps (bounded by its refire time).
- **Live** (sandbox melee, one AI car, the player teleported 30 m in front of it every 2 s, 45 s per run, n=2;
  `captures/014-framerate/aifire_*.json`):

  | config | rolls per weapon per s | yes decisions per weapon per s |
  |---|---|---|
  | stock 60 fps | 60 | 4.9, 5.2 |
  | stock 20 fps | 20 | 1.3, 2.4 |
  | 60 fps with the hold | 20 | 1.2, 1.9 |

  The yes fraction per roll is similar throughout (0.06-0.12).
- **Fix.** i76-everywhere `music-fix` (`I76_FRAMERATE_FIXES`) makes the decision on 20 Hz grid frames and holds it for
  the window, keyed by the weapon's AI record, as one 50 ms stock frame does. `I76_AI_FIRE_CACHE=0` turns only the
  hold off (for measuring).

## Path following (goto / evade / race / follow)

Static reading of md5 9a232dcc (2026-09-27, gap ai-paths), not yet checked live. Positions are world x/z. Headings are atan2(dx, dz).

### State (AI block)

| field | meaning | site |
|---|---|---|
| ai+0x80 | FSM target speed, m/s | goto 0x412eff |
| ai+0x8c | path the FSM asked for | 0x412ef1 |
| ai+0x88 / +0xa0 / +0xa4 | active path / node index / nNodes | ai_SetActivePath 0x4151fa, 0x415200, 0x41520f |
| ai+0x84 | search state: 2 pending, 1 searching, 0 done | 0x420a3f, 0x420dd8 |
| ai+0xb0 + k x 0x14 | route point k (search result): x, z at +4, cell flag at +8 | ai_AstarBuildPath 0x40e770 |
| ai+0xa8 / +0xac | route index / route count | 0x415196, 0x420d9f |
| ai+0x98 | route leg finished | 0x4150bd |
| ai+0x94 | replan request | 0x4150c3, 0x415149 |
| ai+0x9c | path end reached; isArrived reads and clears it (0x40b341) | 0x415157 |
| ai+0x9cf8 / +0x9cfc | weave timer (sim s) / weave flag | 0x42102d / 0x421021 |
| ai+0xa980 / +0xa984 / +0xa988 | follow offA / offB / at-slot flag | 0x41f0c0 |

### Behaviour machine

- Each FSM goto call writes ai+0x8c and ai+0x80, then calls ai_SetBehaviour(e, 0, 0x16) (0x412ef1, 0x412f11). Evade uses 0x18 with the threat. Race uses 0x1a with the rival.
- Same root id and same target: the stack is kept (0x41295f). While a terminator of the top fires (record+0xdc count, 0x1d8-byte entries, call 0x4129b2), the top is popped. A root that terminates is re-entered through its enter function (0x412a67).
- Then the top's update runs (0x412aa0). Transitions (record+0x88) push and enter their target (0x412af9..0x412b63).
- Search states 22/24/26 move to 23/25/27 when 0x420e50 sees ai+0x84 == 0.
- 23/25/27 terminate on ai_TestRouteLegDone 0x420f80: ai+0x98 or ai+0x94 set, or ai+0xa8 >= ai+0xac (0x420f8d, 0x420f97, 0x420fad). The pop returns to the search, which replans.
- All six also terminate on 0x420e70: ai+0x9c set, or ai+0x88 != ai+0x8c (0x420e7d, 0x420e93). This re-enters the search root, and its enter restarts the path.

### Start node

- Goto and evade enter at 0x420a20. ai_SetActivePath sets node index 0 (0x415200). There is no nearest-node search.
- Race enter 0x420aa0 keeps node 0 only if ai+0x9c was already set (0x420ab6, 0x420b1d). Otherwise ai_FindRaceStartNode 0x4208d0 picks the start:
  1. i0 = the node nearest the car by squared xz distance (strict <, so the first minimum wins; 0x420943).
  2. From i = i0: c = DirCos2D(node[i], node[i+1], car) (0x4209c7). node[n] wraps to node[0] (0x4209b6).
  3. DirCos2D(A, B, C) is the cosine of the angle at A between B-A and C-A. It is 1 when either length is < 0.01 m (0x414dd0).
  4. c > -0.1 means the car is past node i (0x4209cc), so i = (i+1) mod n (0x4209e5). Stop at c <= -0.1 or back at i0.
  5. Node index = i (0x420a06). A race never runs a path backwards.
- So Open76's "nearer end" rule is wrong for goto and evade.
- The enters release the handbrake (entity+0xf0 = 0), set gear direction +1 and set the gear lever to 3 (0x420a61..0x420a8e). The follow-path enter 0x420ea0 does the same.

### Route search (update 0x420d30, every frame in 22/24/26)

- It writes ai+0x9d00 = -10 (0x420d4e). Purpose unknown.
- Only the car holding the search claim searches (ai_MayUsePathSearch 0x40ad40). The claim holder clears ai+0x94 (0x420d6a).
- Aircraft (object type 9, 0x420d73): the route is one point, node[ai+0xa0] (0x420da9), and the search is done at once.
- Cars: ai_PathSearchStep 0x40f1e0 plans to node[ai+0xa0] (0x40f1f0). It starts from the car position snapped to a 10 m grid (0x40f256; a remainder > 5 rounds up).
  - It returns 1 until an expanded cell is within 11 m of the goal (121 at 0x40f775).
  - ai_TryRoadShortcut 0x40ee20 can finish the search at once.
  - The route is written start cell first (0x40e770).
- While ai+0x84 != 0, the car throttles to 0.25 x turn speed (0x420e1c) with the wheel centred (0x420e33). When the search is done, ai+0x98 = 0 (0x420e0a).

### Advance rule (ai_AdvanceWaypoint 0x415020, first call in every follow update)

Route level. It repeats while it advances and is skipped while ai+0x98 is set.
- k = ai+0xa8, d = route[k] - car (xz).
- Last point: arrived when |d| < 10 m (100 at 0x4150a7). Then ai+0x98 = ai+0x94 = 1.
- k = 0 (the start cell): k becomes 1 when |d| < 26.9 m (725 at 0x415181).
- Otherwise k += 1 when DirCos2D(route[k], route[k+1], car) > -0.1 (0x4151cb). That line is about 96 deg off the leg at route[k].

Path level. It runs once per call, only while ai+0x84 != 1 (0x4150de).
- |car - node[ai+0xa0]| < 40 m (1600 at 0x415130): ai+0x94 = 1 and index += 1 (0x41514f).
- When the index reaches nNodes: ai+0x9c = 1 and the index wraps to 0 (0x415157, 0x41515d).

### Path end

- The car does not stop or reverse. The index is already 0, and ai+0x94 forces a replan to node 0.
- A repeat call before isArrived consumes ai+0x9c fires 0x420e70, and the enter restarts at node 0. Race skips the nearest-node search then, because ai+0x9c is set.
- Either way the car drives the path again from node 0 until the script changes the action. isArrived sees the edge only if tested before the next goto call.

### Steering target (ai_GetWaypointHeading 0x415220: e, ai, offsetFlag, lookahead L)

- Aircraft use L = 24 m (0x415235).
- P = route[k]. With offsetFlag set: P += 5 x (-uz, ux) (0x415300, 0x415308).
  - u is the unit leg direction: the incoming leg, or the outgoing leg for k = 0.
  - A degenerate leg uses 1/|u| = 0.2 (0x4152de).
- |P - car| > L, or k is the last point (0x415369, 0x41537a): heading = atan2 toward P.
- Otherwise it is pure pursuit (0x415388..0x4154ec). Walk the route from P for the remaining L - |P - car| m and aim at that point. If the route ends first, aim at route[k].

### Speed and steering per mode

| mode | update | L | offset | speed = ai+0x80 while abs(steer) <= |
|---|---|---|---|---|
| goto (23) | 0x420ed0 | 11 m (0x420ee9) | none | 0.45 (0x420f3c) |
| evade (25) | 0x420fc0 | 11 m, 22 m weaving (0x4210da) | weave flag | 0.4 (0x42113e), 0.6 weaving (0x421166) |
| race (27) | 0x420b30 | 11 m, 22 m weaving (0x420c63) | weave flag | 0.5 (0x420cc7), 0.6 weaving (0x420cef) |

- Above the steer limit the speed is the turn speed; aircraft always use ai+0x80. Heading goes to ai_SteerToHeading 0x40fe80, speed to ai_UpdateThrottle 0x40f9c0.
- Turn speed (ai_GetTurnSpeed 0x40f990) = ai+0xa994, set by ai_ComputeTurnSpeed 0x40f8f0: sqrt(7.84 x sum of four wheel values / entity+0x110) (0x40f94f). Aircraft use 10 m/s (0x40f99a).
- Weave: when sim time passes ai+0x9cf8, the flag ai+0x9cfc toggles and the timer is set to now + 2 + rand()%4 s (0x420ff6..0x42102d). The car switches between the route line and 5 m off it.
- Evade weaves when the threat is within 90 m in 3D (8100 at 0x4210b4) and ai_IsClearOfTeamZero(car position) holds (0x4210c6).
- Race also needs a hit from an attacker in the last 20 s: now < ai+0xa6f0 + 20 (0x420c42, 0x420c48). ai_RecordDamageEvent writes ai+0xa6f0 (0x41586c).
- ai_IsClearOfTeamZero 0x40ada0 returns 0 if any team-0 vehicle (list 0x507da0) has dot(its position, car position) < 6400 (0x40adeb). That is a dot product of positions, not a distance (probably an original bug).
- SetBehaviour then fires at the target, which is the threat or the rival (0x412bb6).

### Follow (update 0x41ef40, target = leader)

- slot = leader position + offA x right + offB x forward. Right and forward are the leader's matrix rows 0 and 2 (0x41efce, 0x41eff8). Units are metres.
- d = slot - car (3D), dist = |d|. Every frame ai+0xa988 = (dist < 2.5 m) (0x41f094, 0x41f0c0). isAtFollow reads and clears it.
- heading = atan2(d.x, d.z) (0x41f0e4). The car's own travel heading is used when dist < 1e-6. The car steers to it.
- vL = leader speed. Leader stopped (vL < 1 m/s, 0x41f121):
  - Signed steer >= 0.4 (0x41f13b): turn speed. The test is signed, so a hard turn the other way does not trip it.
  - Otherwise dist < 4 m (0x41f14b) brakes fully (0x41f15c). Beyond that, speed = max(0, (dist - 1) x 0.3) (0x41f16f).
- Leader moving, abs(steer) < 0.4 (0x41f1e0):
  - dist > 150 m: speed 1000 (0x41f201), which is full drive.
  - 50 < dist <= 150: speed = vL + max(0, (dist - 2) x 0.7) (0x41f230).
  - dist <= 50: speed = vL + max(0, dist - 1) x 0.4 (0x41f2b6).
- Leader moving, abs(steer) >= 0.4:
  - dist >= 100 m or vL <= 5 m/s: turn speed (0x41f2d7, 0x41f2e8).
  - Overshoot: fwd_car . fwd_leader > 0.7 and d . fwd_car < 0 (0x41f37c, 0x41f393). The car aims at slot + fwd_leader x 4 x dist (0x41f3c3) at 0.75 x vL (0x41f4b8).
  - Otherwise t = (car - slot) . (vLvec - vcar) / |vLvec - vcar|^2 (1e7 when that is < 0.01; math_ClosestApproachTime 0x4180f0, called at 0x41f4e3). t > 0: speed = vL - 5 (0x41f501). Otherwise turn speed.
- With the follow flag ai+0xa98c set, SetBehaviour fires at the aux object ai+0xa990 instead of the leader (0x412b9f).

### Related

- The 'handle too far search' enter 0x41e160 builds a private one-node path at ai+0xc. The node is the target position. It sets ai+0x8c to that path (0x41e1ca) with speed 35 m/s (0x41e1d3), then runs the same search and follow.
- ai_ApproachTarget 0x4203a0 (manoeuvre 6 of 0x420520; args e, target, own travel heading h, ground distance D):
  - It steers along ai_RamApproachVelocity 0x419600, or along h when that is degenerate (0x420421).
  - Target slower than 1 m/s (0x42043d), and abs(wrap(h - heading)) < 0.19 rad (0x42045a): D < 60 m brakes fully (0x42047c). Otherwise speed = (D - 60) x 0.2 (0x420497). Not aligned: turn speed (0x4204c7).
  - Moving target: speed = |approach velocity| while abs(entity+0xe4 throttle) <= 0.4 (0x4204b9). Otherwise turn speed.

## Flee when hurt (stock bug, 2026-09-27)

`ai_ShouldFleeWhenHurt` 0x417060 flees when `object_HealthFraction` < 30 + 17 x ai+0xa818. Because HealthFraction
returns an unscaled 0..1 ratio once any core component is below 99.99% (`damage.md`, confirmed live), stock AI
flees at the first scratch to its engine, suspension or brakes. `I76_FIX_HEALTH_PCT=1` (proxy) restores the
percent scale.

