# I'76 mission-script (FSM) actions: prototypes, dispatch, arguments, usage

Source: pristine exe (md5 9a232dcc) through `tools/disasm.py`, `gen_tables.Image` and the Ghidra export `.c` files.
Missions: the 40 `.MSN` files in `sandbox-gog/main/app/miss16`, parsed with `tools/i76fmt/bwd2.py` plus a
scratch FSM parser that follows the layout below. Every FSM chunk parsed to exactly 0 leftover bytes, which checks the layout.
Labels: plain statements come from code at the cited addresses. `inferred` marks my reading of intent.
Related existing work: `tools/fsm_actions.py` (output `foldin/fsm-actions.tsv`) already joins name -> index -> case -> first handler.
This note adds argument, return and semantic detail plus usage counts. I did not modify that tool.

## 0. Corrections and additions to the established model

- **ACTION operand indexes the mission's action table, not the prototype table.** At 0x412ce0-0x412d09 the operand is
  multiplied by 0x54 (`lea eax,[eax+eax*2]` on arg*7, then `[ecx+eax*4]`) and added to param_3 (the action table), and
  the switch value is `record+0x50`. Every mission action table has the same 95 names in the same order, and that order
  is not the prototype order (for example slot 5 is `follow`, prototype 48).
- **Every argument in the queue is an `int*`.** The dispatcher always dereferences a queue slot (`**(int**)(state+0x1000+4k)`).
  Opcode 4 queues `&BP[k]`, the address of a stack slot: `lea edx,[ecx+eax*4]` at 0x41476e-0x41477d.
  Opcode 5 queues the slot's contents: `mov eax,[ecx+eax*4]` at 0x4147a3-0x4147b2.
  A machine's parameter slots already hold pointers into the constant pool (0x412500), so opcode 5 on a parameter passes a
  pointer into `consts[]`. Compiled code uses exactly two forms (counted across all missions below):
  - `5 k<0` (valParam): pass a machine parameter by reference into the constant pool.
  - `1 imm; 4 k>=0; 13 act; 7 1` (refLocal): push a literal temporary, pass its address, pop it.
  So `set`/`inc` on a parameter write into the shared constant pool. Two machines given the same constant index share that
  variable (inferred: this is how the FSMs communicate).
- **Nothing is popped.** A handler reads fixed slots +0x1000, +0x1004, ... Then the common epilogue at 0x4144c2-0x4144d7
  resets the queue pointer (`lea ecx,[esi+0x1000]` then `mov [esi+0x10b4],ecx`) and advances IP by 8. Extra queued args are
  ignored. A missing arg would read the stale pointer from an earlier action (inferred hazard).
- **The dispatcher never bounds-checks** entity, path or string indices. It receives the counts (param_4/6/8) but never reads them.
- **The 8-byte entity "instance name" is copied raw.** The shifts in 0x4105a0 (0x410688-0x41070c) reassemble the bytes
  unchanged: hi dword = B through `cdq` and `__allshl(32)` at 0x4106f2-0x4106f8, so no flag bits are extracted.
  In all 25 scripted missions the field is an 8-character object name, for example T01 `taurus` -> `t01js01\0` and
  `barn` -> `bhbarn1\0`. It is looked up as a 64-bit key (see section 4).
- **VM detail:** BP points at the return-IP slot and BP[-1] is the saved BP. Parameters sit at negative offsets and locals at
  offsets >= 0 (0x412500; CALL at 0x414874-0x4148a3).
- **Opcodes seen across all missions:** 1 (15009), 4 (19869), 5 (8661), 6 (513), 7 (10839), 8 (5233), 9 (7487), 10 (2704),
  12 (2700), 13 (17584), 14 (324). Opcodes 2, 3 and 11 (PUSH &BP, PUSH BP, CALL) never occur in the shipped missions.

## 1. Prototype table: match_prototype 0x410a10

- **Matching is an unrolled chain of exact, case-sensitive C string compares.** Each block is `mov esi,<literal>`, an inline
  2-bytes-per-step strcmp with NUL included, and on equality `mov eax,<index>; ret`. No prefix matching.
- **No argument signature is encoded anywhere.** The table is name -> index only. Arity is implicit in each dispatch case.
- **Unknown name:** 0x4122b4 pushes 'Uknown FSM prototype in match_prototype: %s\n', calls the logger 0x42d5d0, then
  `call [abort]` at 0x4122c1.
- **Size:** 97 compares and 96 distinct names (indices 0..95), not 82. The string literals run from 0x4c3280 (`null`) down to
  0x4c2e8c (`stopCB`).
- **Dead duplicate:** `isArrived` is compared twice (0x411377 and 0x4113b8), both returning 40.
- **`null` (0):** the compare result itself is returned (`xor eax,eax` path, ret at 0x410a52).
- **Caller:** 0x4125c0 stores the result at action_record+0x50 for every action (record stride 0x54).

| idx | name | cmp block | | idx | name | cmp block |
|---|---|---|---|---|---|---|
| 0 | null | 0x410a17 | | 48 | follow | 0x4115c0 |
| 1 | behave | 0x410a53 | | 49 | teleport | 0x411642 |
| 2 | attack | 0x410a94 | | 50 | destroy | 0x411683 |
| 3 | sit | 0x410ad5 | | 51 | playMovie | 0x4116c4 |
| 4 | goto | 0x410b16 | | 52 | pushCam | 0x411705 |
| 5 | guard | 0x411601 | | 53 | popCam | 0x411746 |
| 6 | do | 0x410b57 | | 54 | camObjObj | 0x411787 |
| 7 | set | 0x410b98 | | 55 | camObjDir | 0x4117c8 |
| 8 | inc | 0x410bd9 | | 56 | camPosObj | 0x411809 |
| 9 | dec | 0x410c1a | | 57 | camPosDir | 0x41184a |
| 10 | rand | 0x410c5b | | 58 | camTransObj | 0x41188b |
| 11 | whoRammed | 0x410c9c | | 59 | camF12 | 0x41194e |
| 12 | whoShot | 0x410cdd | | 60 | camTransDir | 0x4118cc |
| 13 | startTimer | 0x410d1e | | 61 | camIsArrived | 0x41190d |
| 14 | success | 0x410d5f | | 62 | isKeypress | 0x41198f |
| 15 | successAll | 0x410da0 | | 63 | triggerGate | 0x4119d0 |
| 16 | fail | 0x410de1 | | 64 | evade | 0x411a11 |
| 17 | failAll | 0x410e22 | | 65 | toggleAvoid | 0x411a52 |
| 18 | failAllObj | 0x410e63 | | 66 | allBlgDead | 0x411a93 |
| 19 | cb | 0x410ea4 | | 67 | allEnemyDead | 0x411ad4 |
| 20 | cbPrior | 0x411e21 | | 68 | setHeliHeight | 0x411b15 |
| 21 | cbFromPrior | 0x411e62 | | 69 | setSkill | 0x411b56 |
| 22 | playScene | 0x410ee5 | | 70 | isAtFollow | 0x411b97 |
| 23 | nearestEnemy | 0x410f26 | | 71 | control | 0x411bd8 |
| 24 | nearestBlg | 0x410f67 | | 72 | controlAll | 0x411c19 |
| 25 | true | 0x410fa8 | | 73 | driveControl | 0x411c5a |
| 26 | false | 0x410fe9 | | 74 | controlDone | 0x411c9b |
| 27 | isEqual | 0x41102a | | 75 | reveal | 0x411cdc |
| 28 | isGreater | 0x41106b | | 76 | isCBEmpty | 0x411d1d |
| 29 | isLesser | 0x4110ac | | 77 | setAgg | 0x411d5e |
| 30 | test | 0x4110ed | | 78 | setUserRadar | 0x411d9f |
| 31 | isWithin | 0x41112e | | 79 | cbFrom | 0x411de0 |
| 32 | isShot | 0x41116f | | 80 | killCB | 0x41206a |
| 33 | hpLesser | 0x4111b0 | | 81 | salvage | 0x411ea3 |
| 34 | ammoLesser | 0x4111f1 | | 82 | setSiren | 0x411ee4 |
| 35 | isRammed | 0x411232 | | 83 | setAvoid | 0x411f25 |
| 36 | isDead | 0x411273 | | 84 | setMaxAttackers | 0x411f66 |
| 37 | isLit | 0x4112b4 | | 85 | canSee | 0x411fa7 |
| 38 | timeGreater | 0x4112f5 | | 86 | isAirborne | 0x411fe8 |
| 39 | timeLesser | 0x411336 | | 87 | teleportOffset | 0x412029 |
| 40 | isArrived | 0x411377 / 0x4113b8 | | 88 | isGroovesFault | 0x4120ab |
| 41 | isEqualId | 0x4113f9 | | 89 | hide | 0x4120ec |
| 42 | isWithinNav | 0x41143a | | 90 | startCar | 0x41212d |
| 43 | isWithinSqNav | 0x41147b | | 91 | setLights | 0x41216e |
| 44 | isWithinEnemy | 0x4114bc | | 92 | race | 0x4121af |
| 45 | isAttacked | 0x4114fd | | 93 | setArtillery | 0x4121f0 |
| 46 | whoAttacked | 0x41153e | | 94 | setArtilleryRate | 0x412231 |
| 47 | setId | 0x41157f | | 95 | stopCB | 0x412272 |

## 2. Dispatch table: fsm_ActionDispatch 0x412ce0

The switch is at 0x412d00-0x412d09 (`cmp eax,0x5f; ja 0x4144ae; jmp [eax*4+0x4144e4]`) and covers 96 entries.
- Case 0 (`null`) jumps straight to the epilogue 0x4144c2.
- Case 22 (`playScene`) points at the default 0x4144ae, which logs 'Uknown fsm prototype - %s\n' and aborts (0x4144bc).
  playScene is therefore a named but unimplemented prototype that crashes the game if used. It is absent from every mission's action table.
- Cases 7 (`set`) and 47 (`setId`) share the code at 0x413f16.

**Argument kinds.** Every queue slot is an `int*`. `qN` is slot +0x1000+4N.
- **E**: entity index. The case reads `ent[idx*0x60+0x58]`, passes it through 0x45f0f0 (the 'ai' ref check, which returns NULL
  for a dying object and releases the ref) and writes the result back into the table. The resulting object pointer is what the callee gets.
- **P**: path index (`paths + idx*0x58`).
- **S**: string-table index. This is the "sound" table (`strs + idx*0x54`) and its name is passed.
- **I**: int by value.
- **O**: out var (the int is written).
- **N**: objective number, 1-based.
- **x**: queued by the missions but not read by the 1998 dispatcher.

"arity" is the number of queued args observed in the missions (always a single value per action).
**Result column:** "-" means +0x10a0 is left untouched.
"uses" = ACTION count / number of missions that use it (out of 25 scripted missions).

| idx | name | args (kind) | result 0x10a0 | semantic | case | callee | uses |
|---|---|---|---|---|---|---|---|
| 0 | null | - | - | no-op | 0x4144c2 | - | 1746/25 |
| 1 | behave | E | - | stub: logs 'FSM: behave is not implimented' once (flag 0x4c2aa0) | 0x412d10 | 0x40aed0 | 0 |
| 2 | attack | E attacker, E target, x | - | set AI behaviour 0 (combat selector via 0x412680) with target. 3rd arg (usually 1) ignored | 0x412d4f | 0x412830(a,t,0) | 171/23 |
| 3 | sit | E | - | behaviour 0x1f, no target | 0x412db9 | 0x412830(e,0,0x1f) | 227/25 |
| 4 | goto | E, P, I speed | - | ai+0x8c = path, ai+0x80 = (float)speed (literals 5..60, mostly 45; inferred target speed), behaviour 0x16 | 0x412ea9 | 0x412830(e,0,0x16) | 324/25 |
| 5 | guard | E, E target | - | behaviour 0x20 with target | 0x412e3f | 0x412830(e,t,0x20) | 16/8 |
| 6 | do | E | - | stub: 'FSM: do is not implimented' | 0x413354 | 0x40afc0 | 0 |
| 7 | set | O var, I val | - | `*q0 = *q1` | 0x413f16 | inline | 313/23 |
| 8 | inc | O var | - | `++*q0` | 0x413393 | inline | 460/24 |
| 9 | dec | O var | - | `--*q0` | 0x4133a0 | inline | 0 |
| 10 | rand | O out, I n | - | `*out = rand() % n` | 0x4133ad | CRT rand | 330/25 |
| 11 | whoRammed | E, O out | - | out = entity-table index of ai+0xa6e4 (last rammer). Appends a 'NoLabel%d' entity if the object is not in the table | 0x4133c9 | 0x40aff0 | 0 |
| 12 | whoShot | E, O out | - | same for ai+0xa6e8 (last shooter) | 0x41340e | 0x40b0f0 | 5/3 |
| 13 | startTimer | O t | - | `*t = ftol(simclock_GetAccumDt())` (whole seconds, inferred) | 0x41368b | 0x49c7e0, 0x4ba090 | 579/25 |
| 14 | success | N | - | objective n: set bit 2 (succeeded), play cnote.wav. Logs if missing / already failed / hidden | 0x4136a8 | 0x45e9e0 | 87/24 |
| 15 | successAll | I delay | - | 0x5244e4 = 1, 0x5244e0 = now+delay, 0x609438 = -2. When now >= 0x5244e0, 0x4149f0 sets game_state = 1 (mission won, inferred) | 0x4136d4 | 0x45eb30(-1) | 34/25 |
| 16 | fail | N | - | objective n: set bit 4 (failed) | 0x4136be | 0x45ea90 | 2/2 |
| 17 | failAll | I delay | - | like successAll with end state 0 (mission failed, inferred) | 0x413700 | 0x45eb30(-1) | 0 |
| 18 | failAllObj | I delay, N obj | - | like failAll and 0x609438 = obj-1 (records the failing objective, inferred) | 0x41372c | 0x45eb30(n) | 182/25 |
| 19 | cb | S | - | if string+0x50 (file-valid flag) is set: CB queue (name, speaker=NULL, prio 3) | 0x413453 | 0x423620 | 225/25 |
| 20 | cbPrior | S, I prio | - | CB queue (name, NULL, prio). No valid-flag check | 0x4134ee | 0x40bfe0 -> 0x423620 | 3001/25 |
| 21 | cbFromPrior | S, E speaker, I prio | - | CB queue (name, speaker obj, prio) | 0x41351c | 0x40c000 -> 0x423620 | 648/25 |
| 22 | playScene | - | - | no case: default logs and aborts | 0x4144ae | abort | 0 (absent) |
| 23 | nearestEnemy | E, O out | - | nearest (2D) live vehicle on another team (team lists 0x507da0/0x51f5d0; team 0 only when 0x452d20() or 0x401310()). Writes its entity index, appending if needed. If none: slot n gets NULL and out = n, count not bumped | 0x41375f | 0x40a8a0 | 40/4 |
| 24 | nearestBlg | E, O out | - | nearest undestroyed building (list 0x436750/0x436790) -> entity index. Logs (mislabelled 'nearestEnemy could not find any buildings') | 0x4137a4 | 0x40ba60 | 15/2 |
| 25 | true | - | 1 | result = 1 | 0x41399f | inline | 740/25 |
| 26 | false | - | 0 | result = 0 | 0x4139ae | inline | 0 |
| 27 | isEqual | I a, I b | a==b | | 0x4139bd | inline | 3293/25 |
| 28 | isGreater | I a, I b | a>b | `*q1 < *q0` | 0x4139df | inline | 25/9 |
| 29 | isLesser | I a, I b | a<b | | 0x413a01 | inline | 15/6 |
| 30 | test | E | 0 | stub: 'FSM:test is not implimented' | 0x413a23 | 0x40b2f0 | 0 |
| 31 | isWithin | E a, E b, I r | 3D dist < r | squared 3D distance of object positions < r*r | 0x413a68 | 0x40b360 | 287/22 |
| 32 | isShot | E | edge | ai+0xa6d4 == frame (0x415600()) or frame-1, then consumed (set -10) | 0x413ada | 0x40b410 | 17/8 |
| 33 | hpLesser | E, x (0/1), I pct | hp<pct | 0x40b450(obj) health metric 0..100 < pct. 2nd arg passed but unused by 0x40b7d0 | 0x413b18 | 0x40b7d0 | 68/25 |
| 34 | ammoLesser | E, I hardpointId, I n | ammo<n | find hardpoint whose id == q1 (via 0x4a3400), compare ammo < n | 0x413b64 | 0x40be60 | 0 |
| 35 | isRammed | E | edge | ai+0xa6d8 this/last frame, consumed | 0x413bee | 0x40b800 | 1/1 |
| 36 | isDead | E | flag | obj != NULL && obj+0x10 & 0x200 (destroyed) | 0x413c2c | 0x40b840 | 1043/25 |
| 37 | isLit | E | 0 | stub: 'isLit is not implimented' | 0x413ca8 | 0x40b8b0 | 0 |
| 38 | timeGreater | I t0, I secs | now>=t0+secs | `(float)(t0+secs) < (float)ftol(now) + 0.5` | 0x413941 | 0x49c7e0 | 418/25 |
| 39 | timeLesser | I t0, I secs | now<t0+secs | the mirror compare | 0x4138f0 | 0x49c7e0 | 1/1 |
| 40 | isArrived | E | edge | ai+0x9c == 1, then clears it (path end reached, inferred) | 0x413c6a | 0x40b320 | 250/25 |
| 41 | isEqualId | E a, E b | same obj | compares the resolved object pointers | 0x413ce6 | inline | 98/25 |
| 42 | isWithinNav | P, E, I r | 2D dist<r | path node[0] (x,z) to obj (+0x40,+0x50) | 0x413d4a | 0x40b8e0 | 136/22 |
| 43 | isWithinSqNav | P, E, I r | box | abs(dx)<r && abs(dz)<r against node[0] | 0x413da5 | 0x40b940 | 485/25 |
| 44 | isWithinEnemy | E, I r | any | any object on teams 1..7 (not own team) with obj+0x11 & 2 clear inside 2D r | 0x413e00 | 0x40ab30 | 18/6 |
| 45 | isAttacked | E | edge | ai+0xa6dc this/last frame, then clears the a6d4/a6d8/a6dc triple | 0x413e45 | 0x40b990 | 300/25 |
| 46 | whoAttacked | E, O out | - | like whoRammed on ai+0xa6ec | 0x413ed1 | 0x40b1f0 | 95/25 |
| 47 | setId | O, I | - | same code as set | 0x413f16 | inline | 0 |
| 48 | follow | E follower, E leader, E aux, I flag, I offA, I offB | - | ai+0xa990 = aux obj, +0xa98c = flag, +0xa980 = (float)offA, +0xa984 = (float)offB, behaviour 0x1e toward leader. If the flag is set, the steering target is aux (0x412b79 path into 0x414ef0) | 0x413f63 | 0x412830(f,l,0x1e) | 24/11 |
| 49 | teleport | E, P, I speed, I heading(0..360) | - | place obj at node[0]. node[0].y is overwritten with terrain height (0x493550). Yaw = heading deg, velocity = speed * forward. Logs 'teleport angle out of bounds' outside 0..360 | 0x4137e9 | 0x414bc0(o,p,sp,hd,0,0) | 108/23 |
| 50 | destroy | E | - | vehicle: kill (0x4652b0) and throttle -1. Building: 0x46aa80. Logs if already dead | 0x4138b8 | 0x40b9e0 | 30/9 |
| 51 | playMovie | S | - | if valid: 0x5a7cd0 = &string record (queued .smk, inferred) | 0x4135d3 | 0x49aec0 | 2/2 |
| 52 | pushCam | - | - | if 0x54b67c: 0x44dff0(0), 0x44e000(13), 0x4096c0(root,13). Then save camera state (0x4058b0) and camera_mode = 5 (scripted) | 0x413056 | 0x49d420 | 91/25 |
| 53 | popCam | - | - | restore saved camera state (0x405910) | 0x41308d | 0x49d470 | 118/25 |
| 54 | camObjObj | E eye, I dx, I dy, I dz (cm), E target | - | camera at eye + local offset/100, looking at target | 0x413097 | 0x49d5f0 | 18/11 |
| 55 | camObjDir | E, I dx, I dy, I dz (cm), I a, I b, I c (1/100 deg) | - | camera at obj-local offset with Euler angles. Passed to 0x493e60 as (a, c, b): c is yaw (literals 14500/18000), a is inferred pitch | 0x413125 | 0x49d4a0 | 3/3 |
| 56 | camPosObj | P, I height(cm), E target | - | camera on path (speed NULL = stationary at the start, inferred), looking at target | 0x4131a7 | 0x49d740(p,h,NULL,t) | 72/25 |
| 57 | camPosDir | P, I height, I a, I b, I c (1/100 deg) | - | camera on path with fixed angles (c is yaw) | 0x4131fe | 0x49dac0(p,h,NULL,a,b,c) | 12/7 |
| 58 | camTransObj | P, I height, I speed, E target | - | camera travels along path at speed, looking at target. Sets the camIsArrived flag at the path end | 0x413217 | 0x49d740 | 4/4 |
| 59 | camF12 | E subj, E target, I dist, I height (cm) | - | camera behind subj on the subj->target line, raised by height (chase view) | 0x4132b9 | 0x49dda0 | 14/5 |
| 60 | camTransDir | P, I height, I speed, I a, I b, I c | - | moving path camera with fixed angles | 0x413273 | 0x49dac0 | 0 |
| 61 | camIsArrived | - | flag | returns and clears 0x5a7ed8 | 0x413334 | 0x49d730 | 3/3 |
| 62 | isKeypress | - | flag | 0 while render_gate_flags & 0x3e. Otherwise a pending key whose map char (0x53db30) is '"' returns 1. '3' calls 0x49d140. Exact key identity inferred | 0x413344 | 0x44de40 | 121/24 |
| 63 | triggerGate | E | - | find descendant node with type +0x6c == 7 and zero its +0x70->+0x90 (open gate, inferred) | 0x413f2b | 0x40bf20 | 17/5 |
| 64 | evade | E, P, I speed, E threat | - | path+speed as goto, behaviour 0x18 vs threat | 0x412f1e | 0x412830(e,t,0x18) | 32/11 |
| 65 | toggleAvoid | E | - | ai+0x9d14 = !ai+0x9d14 | 0x414091 | 0x40bc10 | 7/6 |
| 66 | allBlgDead | - | flag | 1 if every building is destroyed (0x200) | 0x413e83 | 0x40bbc0 | 0 |
| 67 | allEnemyDead | E | flag | 1 if every object on teams 1..7 other than own has dead bit (0x454 & 0x20) | 0x413e93 | 0x40aa90 | 25/3 |
| 68 | setHeliHeight | E, I h | - | class 9 only, else logs. Heli cruise height = h | 0x413606 | 0x40bc40 -> 0x46c870 | 22/8 |
| 69 | setSkill | E, I a, I b (1..5) | - | ai+0xa820/0xa81c from tables 0x5fcb7c/0x5fcb9c[a], ai+0xa824/0xa828 from 0x5fcbdc/0x5fcbbc[b] (inferred driving/gunnery skill) | 0x413645 | 0x40bd90 | 235/25 |
| 70 | isAtFollow | E | edge | ai+0xa988, cleared on read. Logs for non-vehicle | 0x414053 | 0x40bdf0 | 8/6 |
| 71 | control | E, I braccel, I steer (-100..100) | - | enqueue control step, reusing the last queued e-brake/reverse values | 0x4140c9 | 0x41fb90 -> 0x41f9c0 | 40/1 |
| 72 | controlAll | E, I braccel, I steer, I ebrake(0/1), I reverse(+-1), I u5, I u6 (0..10) | - | enqueue into ai ring buffer 0x9d68 (100 x 0x18). Clears controlDone. Logs on overflow | 0x41410f | 0x41f9c0 | 0 |
| 73 | driveControl | E | - | apply next queued control to the vehicle, or zero controls and 0x467370(o,3) when empty | 0x414191 | 0x41fc40 | 1/1 |
| 74 | controlDone | E | flag | returns ai+0xa6d0 | 0x4141c9 | 0x41fce0 | 1/1 |
| 75 | reveal | N | - | clear objective hidden bit 1, play cnote.wav | 0x414207 | 0x40be50 -> 0x45e960 | 82/19 |
| 76 | isCBEmpty | - | flag | CB queue head 0x52457c == NULL | 0x413575 | 0x40bf50 -> 0x423a80 | 53/18 |
| 77 | setAgg | E, I level | - | ai+0xa818 = level-1, then 0x412630(level-1, ai+0xa82c) | 0x413594 | 0x40bf60 | 222/24 |
| 78 | setUserRadar | I on | - | if it differs from the cache 0x4c2ab0, toggle the player radar (0x460ea0) | 0x41421b | 0x40bf90 | 0 |
| 79 | cbFrom | S, E speaker | - | CB queue (name, speaker, prio 3) | 0x41349c | 0x40bfc0 | 0 |
| 80 | killCB | - | - | flush the whole CB queue | 0x413585 | 0x423a10(0) | 72/22 |
| 81 | salvage | S | - | 0x4b16e0(name,-1,1): add a salvage part named by a .wdf/.gdf/... string (inferred) | 0x41422f | 0x40c040 | 0 |
| 82 | setSiren | E, I on | - | start/stop the vehicle siren sound (0x424e30) | 0x414256 | 0x40c060 | 21/4 |
| 83 | setAvoid | E, I v | - | ai+0x9d14 = v | 0x414295 | 0x40c080 | 37/10 |
| 84 | setMaxAttackers | E, I n | - | ai+0xa948 = n | 0x4142d4 | 0x40c0a0 | 40/23 |
| 85 | canSee | E a, E b | LOS | ray test (0x4a7800) then building occlusion loop | 0x414313 | 0x417bf0 | 0 |
| 86 | isAirborne | E | flag | obj+0x70 -> 0x454 & 4 | 0x41437a | 0x40c0c0 | 24/8 |
| 87 | teleportOffset | E, P, I speed, I heading, I dx, I dz (cm) | - | teleport with node[0] + (dx,dz)/100 | 0x413836 | 0x414bc0 | 17/7 |
| 88 | isGroovesFault | E | value | returns ai+0xa6e0 (vehicle only, logs otherwise) | 0x413bb0 | 0x40b860 | 57/25 |
| 89 | hide | E | - | behaviour 0x21 | 0x412dfc | 0x412830(e,0,0x21) | 25/11 |
| 90 | startCar | E | - | if !(0x454 & 9): +0x450 = 0x424fd0(o), set 0x80000008 (start engine, inferred) | 0x4143b8 | 0x467400 | 53/10 |
| 91 | setLights | E, I on | - | toggle headlights if bit 6 != on | 0x4143f0 | 0x40c0e0 | 6/2 |
| 92 | race | E, P, I speed, E rival | - | path+speed as goto, behaviour 0x1a vs rival | 0x412fba | 0x412830(e,r,0x1a) | 19/6 |
| 93 | setArtillery | E, I v | - | (obj+0x70)->0x508 -> +0x4c = v | 0x41442f | 0x462c80 | 9/3 |
| 94 | setArtilleryRate | E, I v | - | ...->+0x50 = v | 0x41446b | 0x462ca0 | 3/3 |
| 95 | stopCB | - | - | queue 'STOPCBXX'. 0x423620 then sets 0x524580 = 1, which blocks all later CB | 0x4144a7 | 0x40c020 | 141/25 |

**Behaviour-id space of 0x412830 (AI "ptable" state machine).** Entries are 0x1354-byte records at 0x4c3e50. The ids used by FSM actions are:
0 attack (ids 0-6 and 8-15 are routed through the selector 0x412680), 0x16 goto, 0x18 evade, 0x1a race, 0x1e follow,
0x1f sit, 0x20 guard, 0x21 hide. Behaviour state is pushed on a stack at ai+0xa874, with the depth at ai+0xa93c capped at
0x31 ('Ptable stack overflow' at 0x412b0b).

**Arity check.** For every action, the missions' queued-arg count (always constant per action) equals the number of slots
the case reads. There are two exceptions where a slot is queued but ignored: attack's 3rd arg and hpLesser's 2nd.

## 3. Calling convention of 0x412ce0 (as called at 0x414949)

**Full call chain.** 0x402b30 calls `0x40a320(0x5dcec0)` (push at 0x403dda). 0x40a320 calls 0x4149f0 with 16 args
(0x40a5f0-0x40a644, `add esp,0x40`):
`([ebp+8]=0x5dcec0, heap 0x51f5b4, nConsts 0x51f634, consts 0x51f630, &nMachines 0x51f62c, &machineHead 0x51f628,
&nEntities 0x51f624, entities 0x51f620, nPaths, paths, nStrings 0x51f614, strings 0x51f610, nActions 0x51f60c,
actions 0x51f608, code 0x51f638, nCode 0x51f63c)`, pushed in reverse. As params:
p1 nCode, p2 code, p3 actions, p4 nActions, p5 strings, p6 nStrings, p7 paths, p8 nPaths, p9 entities, p10 &nEntities,
p11 &machineHead, p12 &nMachines, p13 consts, p14 nConsts, p15 heap, p16 0x5dcec0.

**0x4149f0 -> fsm_OpcodeSwitch 0x414670** (0x414a34-0x414a58, 12 pushes). The pushed values are
`(state, code, actions, nActions, strings, nStrings, paths, nPaths, entities, &nEntities, p16=0x5dcec0, esi)`.
`esi` is 0 before the call and incremented after it (0x414a62).

**fsm_OpcodeSwitch -> 0x412ce0** (0x4148fe-0x414949, `add esp,0x30`). The frame is `sub esp,0x54` plus 4 register pushes,
so the switch's own p_n sits at [esp+0x64+4n] at entry. Reading the interleaved loads against the running push count:

| dispatcher param | value | source |
|---|---|---|
| p1 | state (VM object) | esi (= [esp+0x68]) |
| p2 | ACTION operand = index into the mission action table | [eax+4] of the current instruction |
| p3 | actions (stride 0x54, prototype at +0x50) | switch p3 |
| p4 | nActions (unused) | switch p4 |
| p5 | string/sound table (stride 0x54) | switch p5 |
| p6 | nStrings (unused) | switch p6 |
| p7 | path table (stride 0x58) | switch p7 |
| p8 | nPaths (unused) | switch p8 |
| p9 | entity table (stride 0x60) | switch p9 |
| p10 | &nEntities (who*/nearest* append and bump it) | switch p10 |
| p11 | 0x5dcec0 (0x40a320's argument, forwarded) | ebp = [esp+0x90] = switch p11 |
| p12 | &char[80] local of the switch | `lea ecx,[esp+0x14]` |

- **The "extra params from [esp+0x8c..]"** are the switch's own params p10..p3 re-pushed as the table pointers and counts.
- **p12 buffer:** zero-filled at 0x41467c-0x41469f (`rep stosd` of 0x13 dwords + stosw + stosb), with byte 0 copied from 0x504c28.
- **p11 and p12 are unused.** Ghidra's parameter ID gives 0x412ce0 only 10 used params, so the dispatcher never reads them (inferred).
- **cdecl:** the caller cleans up 0x30 bytes and the dispatcher returns nothing meaningful. The epilogue 0x4144c2-0x4144d7
  resets the arg queue and advances IP.

## 4. Entity, string ("sound") and path tables

**Entity table** (loader 0x4105a0; resolver 0x412400; referenced as `param_9 + idx*0x60`).
- **Allocation:** `(n + 200) * 0x60` bytes (HeapAlloc in 0x4105a0). The 200 spare records hold dynamically discovered objects.
- **Record layout:**
  - +0x00 char[40] label (FSM-side name). The loader copies 40 bytes, so +0x28..+0x4f is unused.
  - +0x50 u32 lo and +0x54 u32 hi: the 8-byte instance name from the file, for example `t01js01\0`.
  - +0x58 object pointer holding an 'ai' reference.
- **Resolution (0x412400):** `obj = 0x457630(lo,hi)`, which is `0x4ad5b0(0x54a178,lo,hi)`: a backward linear search of 16-byte
  entries {lo,hi,obj,?} in the object-name registry.
  - Not found: logs 'FSM - instance id for %s does not exist in mission file\n' (push at 0x412435). The slot stays NULL.
  - Found: `0x45ed00(obj,"ai")` adds a ref (recursive refcount at +0xc).
  - Two records with the same 8-byte id but different labels log 'FSM - duplicate instance id for %s and %s' (0x4124a2).
  - A label equal to `taurus` (`_stricmp`, string at 0x4124bb) calls 0x40aeb0, which stores the object in 0x51f5c4.
- **At use:** every E-arg read goes through `0x45f0f0(ptr,"ai")`. If the object's state word +8 == 1 (being deleted), it drops
  the ref, possibly frees the object, and returns NULL. That NULL is written back into the table.
  Consequence: `isDead` on an object that has already been deleted returns 0, not 1 (inferred from 0x40b840 testing obj != NULL first).
- **Dynamic entries:** whoRammed/whoShot/whoAttacked/nearestEnemy/nearestBlg first search +0x58 for the object.
  If it is absent, they write `NoLabel%d` (with the current count) into record[count], store and ref the object, set out = count and `++*p10`.
  There is no capacity check against the +200 spare slots (inferred overflow risk).

**String ("sound") table** (loaded in 0x410720 as the 3rd list; validated by 0x4122d0; referenced as `param_5 + idx*0x54`).
- **Record:** +0 char[40] name, +0x50 valid flag.
- **Validation by the last 3 characters:**
  - `wav`: 0x470340(name) checks that the file exists. On failure the flag is 0 and '%s does not exists in in the project file' is logged.
  - `smk`: 0x49a4c0(name,0). On failure it logs '...does not exists on the cd or the smk directory'.
  - anything else: logs '%s does not have the wav or smk file extension' and leaves the flag unwritten.
- **Who checks the flag:** only `cb` (0x413453) and `playMovie` (0x4135d3). cbPrior/cbFromPrior/cbFrom/salvage pass the name regardless.
- **Contents in practice:** 3367 `.wav` and 2 `.smk` names across all missions, with no other extensions. The table is really a
  general string table: `salvage` would take a part-file name.

**Path table** (0x4102d0; referenced as `param_7 + idx*0x58`).
- **Record:** +0 char[40] name, +0x50 nNodes, +0x54 pointer to nNodes x vec3f (allocated with 0x499ce0).
- **Names are not unique** (T01 has `panpath` three times). Paths are addressed only by index.
- **Consumers:**
  - goto/evade/race store the path pointer at ai+0x8c.
  - isWithinNav/isWithinSqNav read only node[0].x/.z.
  - teleport/teleportOffset read node[0] and overwrite node[0].y with the terrain height.
  - Path cameras walk the nodes, and 0x49d740/0x49dac0 set the camIsArrived flag when node index + 2 >= nNodes.

**CB radio queue** (0x423620 `cb_Enqueue(name, speaker, prio)`):
- **Blocked or dropped:** returns immediately once 0x524580 is set (by STOPCBXX). A dead speaker (flags 0x200) is dropped.
- **Busy queue (non-empty):** prio 5 is dropped. Prio 6 is dropped if the head's prio is < 5.
- **Flush before queueing:** prio 1, or prio < 5 when the head's prio > 4, flushes the queue first.
- **Node:** 0x24 bytes: name (16 chars), +0x10 speaker, +0x18 prio, +0x1c GetTickCount.
- **Priorities in use:** cbPrior 1..5 (5: 994, 1: 946, 3: 573, 4: 376, 2: 112). cb uses 3.

**Objectives** (0x45e9e0 / 0x45ea90 / 0x45e960):
- **Indexing:** 1-based n -> index n-1 < 0x6093c0, exists if 0x6093c8[i] is set.
- **Flag word 0x609420[i]:** bit 1 hidden (reveal clears it), bit 2 succeeded, bit 4 failed.

## 5. Usage across the 40 miss16 missions

- **Which missions have scripts:** 25 missions carry a non-empty FSM: A01, S01-S07, T01-T17. All 15 M*.MSN (multiplayer)
  have a 0-byte FSM chunk. The loader then substitutes zeroed locals (0x409740).
- **Action tables:** all 25 action tables are identical: the 95 prototype names except `playScene`.
- **Totals:** 17584 ACTION opcodes.
- **Names without a dispatch case:** none in the files. The only case-less prototype is `playScene` (default -> abort), and no mission names it.
- **Stubs:** behave, do, test and isLit are logging stubs, and no mission uses them.

**Unused by every mission (18):** behave, do, dec, whoRammed, failAll, playScene, false, test, ammoLesser, isLit, setId,
camTransDir, allBlgDead, controlAll, setUserRadar, cbFrom, salvage, canSee.

**Most used:** isEqual 3293, cbPrior 3001, null 1746, isDead 1043, true 740, cbFromPrior 648, startTimer 579,
isWithinSqNav 485, inc 460, timeGreater 418, rand 330, goto 324, set 313, isAttacked 300, isWithin 287, isArrived 250,
setSkill 235, sit 227, cb 225, setAgg 222, failAllObj 182, attack 171. The full per-action counts are in the "uses" column above.

**Argument passing form per slot** (valParam = machine parameter by reference; refLocal = literal temporary):
- E and P args are almost always valParam, so entity/path indices are bound at machine creation from the constant pool.
- I args are refLocal literals.
- S args of cbPrior/cbFromPrior are refLocal literals: sound indices 53..168.
- cb's S arg is refLocal in 75 uses (literals 0, 1, 2) and valParam in 150.

## 6. Differences from Open76's FSMActionDelegator.cs (checked against the exe)

- **teleport's 4th arg** is a heading in degrees (0..360, 'FSM - teleport angle out of bounds %d' at 0x414bd9;
  0x493e60 yaw slot). It is not a height. Literals: 90, 0, 180, 270, ...
- **camTransObj order** is (path, height, speed, target). 0x413217 passes q1 as 0x49d740's height and q2 as its speed.
  Open76 reads speed first.
- **camObjDir angles:** q6 goes into 0x493e60's yaw slot (literals 14500/18000). Open76 calls q4 yaw and q6 pitch.
- **follow:** q2 is an entity (the aux target at ai+0xa990) and q3 a flag. q4/q5 become floats at ai+0xa980/0xa984.
  Open76's "targetSpeed" for q5 is not supported by the code. q4/q5 are inferred to be offsets.
- **attack's 3rd arg and hpLesser's 2nd arg** are ignored by the exe.

## 7. Proposed function names

| addr | proposed name | evidence |
|---|---|---|
| 0x410720 | fsm_LoadChunk | called from bwd2_h_FSM 0x409740 with 16 out-pointers 0x51f608..0x51f63c; reads the lists in the order actions, entities (0x4105a0), strings, paths (0x4102d0), machines (0x410490), consts, code |
| 0x4105a0 | fsm_LoadEntities | HeapAlloc (n+200)*0x60, 40-byte label + 8-byte id at +0x50 (0x4106ab-0x41070c) |
| 0x4102d0 | fsm_LoadPaths | 0x58 records, +0x50 nNodes, +0x54 = 0x499ce0(n*12) |
| 0x410490 | fsm_LoadMachines | HeapAlloc 0x10bc per machine, linked through +0x10b8 |
| 0x410a10 | fsm_MatchPrototype | strcmp chain -> 0..95; abort message at 0x4122b4 |
| 0x4125c0 | fsm_Link | stores MatchPrototype at +0x50 per action, then 0x412400, 0x4122d0, 0x412500 |
| 0x412400 | fsm_ResolveEntities | 'FSM - instance id for %s does not exist in mission file' (0x412435), duplicate check (0x4124a2), taurus (0x4124bb) |
| 0x4122d0 | fsm_ValidateStrings | wav/smk checks, messages at 0x41236b/0x4123ba/0x4123cb |
| 0x412500 | fsm_InitMachines | slot = consts + slot*4; pushes 0 and code+startIP*8; BP = SP |
| 0x4149f0 | fsm_RunMachines | end-of-mission timer check 0x4149f6-0x414a0e (game_state = 0x5244e4); steps each machine, frees finished ones (HeapFree 0x414a86) |
| 0x40a320 | ai_FrameTick (inferred) | per-team vehicle loop, then fsm_RunMachines (0x40a644) |
| 0x457630 | obj_FindByName8 | `0x4ad5b0(0x54a178, lo, hi)` |
| 0x4ad5b0 | idmap_Find64 | backward search of {lo,hi,val,?} 16-byte entries |
| 0x45ed00 | obj_AddRef | ++[obj+0xc], recursing into the child list +100 / sibling +0x60 |
| 0x45f0f0 | obj_CheckRef | returns NULL and releases when [obj+8] == 1, else returns obj |
| 0x412830 | ai_SetBehaviour | (obj, target, id); 'Ptable stack overflow' at 0x412b0b; state tables at 0x4c3e50 + id*0x1354 |
| 0x40aed0 / 0x40afc0 / 0x40b2f0 / 0x40b8b0 | fsm_behave_stub / fsm_do_stub / fsm_test_stub / fsm_isLit_stub | strings pushed at 0x40aed9 / 0x40afc9 / 0x40b2f9 / 0x40b8b9 |
| 0x40aff0 / 0x40b0f0 / 0x40b1f0 | fsm_whoRammed / fsm_whoShot / fsm_whoAttacked | ai+0xa6e4/a6e8/a6ec; 'whoRammed ... nobody has rammed yet' at 0x40b01d; 'NoLabel%d' at 0x40b058 |
| 0x40a8a0 | fsm_nearestEnemy | case 0x41375f; team scan 0x507da0/0x51f5d0 |
| 0x40ba60 | fsm_nearestBlg | case 0x4137a4; building iterator 0x436750/0x436790; string at 0x40bb0e |
| 0x40b360 | fsm_isWithin | case 0x413a68 |
| 0x40b410 / 0x40b800 / 0x40b990 | fsm_isShot / fsm_isRammed / fsm_isAttacked | cases 0x413ada / 0x413bee / 0x413e45; frame compare against 0x415600 |
| 0x40b7d0 | fsm_hpLesser | case 0x413b18 |
| 0x40b450 | obj_GetHealthPct (inferred) | returns a clamped 0..100 metric |
| 0x40b840 | fsm_isDead | case 0x413c2c |
| 0x40b320 | fsm_isArrived | case 0x413c6a |
| 0x40b8e0 / 0x40b940 | fsm_isWithinNav / fsm_isWithinSqNav | cases 0x413d4a / 0x413da5 |
| 0x40ab30 | fsm_isWithinEnemy | case 0x413e00 |
| 0x40aa90 | fsm_allEnemyDead | case 0x413e93 |
| 0x40bbc0 | fsm_allBlgDead | case 0x413e83 |
| 0x40b9e0 | fsm_destroy | strings at 0x40ba07 / 0x40ba41 |
| 0x40bf20 | fsm_triggerGate | case 0x413f2b |
| 0x40bc10 / 0x40c080 | fsm_toggleAvoid / fsm_setAvoid | both write ai+0x9d14 |
| 0x40bd90 | fsm_setSkill | case 0x413645 |
| 0x40bf60 | fsm_setAgg | case 0x413594 |
| 0x40bf90 | fsm_setUserRadar | case 0x41421b |
| 0x40c060 | fsm_setSiren | case 0x414256; 0x424e30 = vehicle_SetSiren (inferred) |
| 0x40c0a0 | fsm_setMaxAttackers | case 0x4142d4 |
| 0x40c0c0 | fsm_isAirborne | case 0x41437a |
| 0x40c040 | fsm_salvage | case 0x41422f; 0x4b16e0 = salvage_AddPart (inferred; .wdf/.gdf/eng/sus/bra/spc parse) |
| 0x414bc0 | fsm_teleport | 'FSM - teleport angle out of bounds %d' at 0x414bd9 |
| 0x417bf0 | ai_CanSee (inferred) | case 0x414313 |
| 0x41f9c0 | fsm_EnqueueControl | strings at 0x41fa0d..0x41fb6b |
| 0x41fb90 | fsm_control | case 0x4140c9 |
| 0x41fc40 | fsm_driveControl | case 0x414191 |
| 0x41fce0 | fsm_controlDone | case 0x4141c9 |
| 0x423620 | cb_Enqueue | 'STOPCBXX' compare at 0x42363e; 0x24-byte node |
| 0x423a10 | cb_Flush | case 0x413585 |
| 0x423a80 | cb_IsEmpty | via thunk 0x40bf50 at case 0x413575 |
| 0x40bfe0 / 0x40c000 / 0x40bfc0 / 0x40c020 | fsm_cbPrior / fsm_cbFromPrior / fsm_cbFrom / fsm_stopCB | thin wrappers around 0x423620; STOPCBXX pushed at 0x40c024 |
| 0x45e9e0 / 0x45ea90 / 0x45e960 | objective_Succeed / objective_Fail / objective_Reveal | 'succeed' 0x45e9fe, 'fail' 0x45eaae, 'reveal' 0x45e97e with 'Objective %d ...' messages |
| 0x45eb30 | objective_SetFailedIndex (inferred) | 0x609438 = n-1 |
| 0x40be50 | fsm_reveal | case 0x414207 |
| 0x402620 | game_SetState | writes game_state; called from fsm_RunMachines 0x414a0e |
| 0x49aec0 | movie_SetPending (inferred) | case 0x4135d3 |
| 0x49d420 / 0x49d470 | cam_Push / cam_Pop | 'Camera Stack Underfow' 0x49d429 / '0verfow' 0x49d479. The stack at 0x5dbb20 grows down from 8 (0x4c2988 = 8), so the message names are inverted relative to push/pop |
| 0x4058b0 / 0x405910 | cam_StackSave / cam_StackRestore | copies 0x9a dwords from/to &camera_look_callback |
| 0x49d5f0 | cam_ObjObj | case 0x413097 |
| 0x49d4a0 | cam_ObjDir | case 0x413125 |
| 0x49d740 | cam_PathLookAtObj | camPosObj 0x4131a7 / camTransObj 0x413217 |
| 0x49dac0 | cam_PathDir | camPosDir 0x4131fe / camTransDir 0x413273 |
| 0x49dda0 | cam_F12Chase | case 0x4132b9 |
| 0x49d730 | cam_TakeArrived | case 0x413334 |
| 0x44de40 | input_IsKeypress (inferred) | case 0x413344 |
| 0x467400 | vehicle_StartEngine (inferred) | case 0x4143b8 |
| 0x462c80 / 0x462ca0 | fsm_setArtillery / fsm_setArtilleryRate | cases 0x41442f / 0x41446b |
| 0x40aeb0 | fsm_SetTaurus | called for the label 'taurus' in 0x412400 |
| already named | ammoLesser 0x40be60, setHeliHeight 0x40bc40, isAtFollow 0x40bdf0, isGroovesFault 0x40b860, fsm_SetLights 0x40c0e0 | consistent with the cases above |

## 8. Addendum: cross-check with the main-session join, and which actions write their arguments

**Join cross-check.** `status/tasks/fsm-actions.json` (read-only) has 58 dispatch-case evidence rows. Every index -> case
matches the jump table 0x4144e4 as dumped here (0 mismatches). Two naming notes:
- **0x45eb30 is named `fsm_SetAllObjectivesStatus` there.** From its body it only writes `0x609438 = n-1`, and it is called
  with -1 by successAll/failAll and with n by failAllObj. The success/fail end state comes from the cases themselves
  (0x5244e4 = 1 or 0, plus the deadline 0x5244e0), which 0x4149f0 applies to game_state. A narrower name such as
  `objective_SetFailedIndex` fits the body better (inferred meaning of 0x609438).
- **0x414bc0 is labelled `fsm_TeleportOffset`,** but it is also the tail of `teleport` (case 0x4137e9 jumps to 0x41389b with
  offsets NULL). `fsm_Teleport` covers both.

**The constant pool is the mission's global variable store.**
- **Mechanism:** 0x412500 turns each machine parameter slot into `&consts[i]`. The compiled code passes parameters by that pointer (opcode 5, k<0).
- **Parameter layout check:** mapping each written parameter back to its constant index with `i = k + nArgs + 1` (BP -> ret
  slot, BP[-1] = saved BP, args below) lands inside the machine's arg list in all 774 cases (0 unmapped).
- **Shared writes:** 729 of those 774 parameter writes target a constant index that at least one other machine also takes
  as a parameter. 176 distinct (mission, constant) cells are written in total.
- **Conclusion:** `consts[]` holds both true constants (entity/path indices, handed to machines as params) and shared globals.
  Counts come from splitting code by machine start IP, so a few actions in shared tails are not attributed: n = 1769 of the 1869 writer uses.

**Actions that write through an argument pointer** (all others only read their args):

| action | written slot | how | form in missions (n) |
|---|---|---|---|
| set / setId | q0 | `*q0 = *q1` (0x413f16) | valParam 313: a global |
| inc | q0 | `++*q0` (0x413393) | valParam 460: a global |
| dec | q0 | `--*q0` (0x4133a0) | unused |
| rand | q0 | `*q0 = rand() % *q1` (0x4133ad) | refLocal 306 |
| startTimer | q0 | `*q0 = ftol(accum time)` (0x41368b) | refLocal 538, valParam 1 |
| whoRammed / whoShot / whoAttacked | q1 | `*q1 = entity index` (0x40aff0 / 0x40b0f0 / 0x40b1f0) | whoShot refLocal 5, whoAttacked refLocal 91 |
| nearestEnemy / nearestBlg | q1 | `*q1 = entity index` (0x40a8a0 / 0x40ba60) | refLocal 40 / 15 |

**Side writes that are not through arguments:**
- Every E-arg rewrites the entity table's +0x58 with the result of 0x45f0f0.
- who*/nearest* append entity records and bump `*p10`.
- teleport/teleportOffset overwrite path node[0].y with terrain height.
