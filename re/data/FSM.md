# The I'76 mission scripting language (FSM)

Every mission's behaviour (objectives, AI orders, radio chatter, cameras, win and lose) is a small bytecode program in the
mission file's `ADEF/FSM` chunk. This document is the complete language: file layout, virtual machine, the 14 opcodes,
the 96 engine actions, what the compiler emitted, and how to read and rewrite any script.

- Exe: GOG Gold `i76.exe`, md5 9a232dcc2c164648cff20c414c1f9698. Every claim cites instruction addresses.
- Corpus: the 40 missions in `miss16\` (miss8 holds byte-identical copies). 25 carry scripts (A01, S01-S07, T01-T17).
  The 15 multiplayer `M*.MSN` have a 0-byte FSM chunk.
- Tools: `data\fmt\fsm.py` (parse / serialise / disassemble / assemble), `data\fmt\fsmtool.py` (CLI),
  `data\fmt\fsm_protos.py` (action signatures). Every script is dumped, annotated, in `data\out\fsm\*.fsm`.
- Round trip: all 40 FSM chunks go bytes -> values -> bytes **and** bytes -> text -> bytes identically
  (`data\tests\test_fsm_roundtrip.py`). The FSM chunk is 100% `cited` in `data\roundtrip.json`.
- Detail notes behind this page: `data\notes\fsm-actions.md` (per-action tracing).

## 1. Chunk layout

The loader `bwd2_h_FSM` 0x409740 creates a heap (0x409779) and calls `fsm_LoadChunk` 0x410720. It reads the body as a
dword cursor (base 0x5244d0, index 0x5244d4), so every field is 4-byte aligned. Names are copied a dword at a time.

| order | field | layout | reader |
|---|---|---|---|
| 1 | actions | u32 n; n x char[40] | 0x410743 count, 0x4107a3 name copy; records of 0x54 with the prototype id at +0x50 |
| 2 | entities | u32 n; n x {char[40] label, char[8] instance} | 0x4105a0; alloc (n+200) x 0x60 |
| 3 | strings ("sounds") | u32 n; n x char[40] | 0x410843 |
| 4 | paths | u32 n; n x {char[40] name, u32 nNodes, nNodes x f32[3]} | 0x4102d0; records of 0x58 |
| 5 | machines | u32 n; n x {u32 startIP, u32 nArgs, u32 slot[40]} (168 B) | 0x410490; one 0x10bc-byte VM state each |
| 6 | globals | u32 n; n x i32 | 0x41094b |
| 7 | code | u32 n; n x {u32 opcode, i32 operand} | 0x4109ad |

Byte-exactness detail: all 40 `slot` words of a machine record are copied to the VM stack (0x410559..0x410577), not
only the first nArgs. The words past nArgs are dead (the stack pointer starts above them), but the parser keeps them
verbatim (`pad=[...]` in the text form when non-zero).

### Linking (fsm_Link 0x4125c0)

1. Each action name is matched to one of 96 engine prototypes by `match_prototype` 0x410a10. The match is an exact,
   case-sensitive strcmp chain. An unknown name logs `Uknown FSM prototype in match_prototype: %s` and **aborts the
   game** (0x4122b4..0x4122c1).
2. Entities resolve (0x412400). The 8-byte instance name is a 64-bit key looked up in the object-name registry
   0x54a178 (0x457630 -> 0x4ad5b0). The key is the ODEF OBJ label, bytes copied raw. A miss logs
   `FSM - instance id for %s does not exist in mission file` and leaves the entity NULL. A label equal to `taurus`
   (case-insensitive, 0x4124bb) is also stored as the special Taurus object (0x40aeb0).
3. Strings are validated by extension (0x4122d0): `.wav` must exist in the project file, `.smk` on the CD or in the smk
   directory. The result is a valid flag at +0x50 that only `cb` and `playMovie` check.
4. Machines initialise (0x412500). Each argument slot, which holds a **global index**, becomes a pointer
   `&globals[slot]` (0x41252f). Then `0` (old BP) and the return IP are pushed and BP points at the return slot.

## 2. The virtual machine

One VM state per machine (0x10bc bytes, linked at +0x10b8):

| offset | meaning |
|---|---|
| +0x0000..+0x0fff | value stack, grows up, 4-byte slots |
| +0x1000..+0x109f | argument queue for the next ACTION (40 slots) |
| +0x10a0 | result flag (set by condition actions, tested by `jz`) |
| +0x10a4 | code base |
| +0x10a8 | IP (pointer to the current 8-byte instruction) |
| +0x10ac | BP (frame pointer) |
| +0x10b0 | SP |
| +0x10b4 | argument-queue pointer |
| +0x10b8 | next machine |

Scheduling: `fsm_RunMachines` 0x4149f0 runs once per sim frame (from `ai_FrameTick` 0x40a320). It steps every machine
through `fsm_OpcodeSwitch` 0x414670 until the machine yields (opcode 10) or finishes (opcode 12 at the stack base). A
machine that finishes is freed (0x414a86). Inside one slice the interpreter executes at most 1000 instructions
(0x414965); past 800 it sets a warning flag (0x4146b2 -> 0x5244dc), and at 1000 it calls `exit(0)` (0x414976). A
script loop without a `yield` therefore quits the game.

### Frames

At machine start the stack holds `[arg0 .. argN-1][old BP = 0][return IP]` and BP points at the return-IP slot. So:

- `BP[k]` for k < 0 addresses parameters. Parameter i is `BP[i - nArgs - 1]`. Each holds a pointer into the globals.
- `BP[k]` for k >= 1 addresses locals (reserved with `alloc`, filled with `push`).

`CALL` (opcode 11) builds the same frame for a subroutine. `RET n` (12) pops n arguments. The shipped missions never use
CALL, PUSH-address or PUSH-value (opcodes 2, 3, 11). The compiler inlined everything.

### Opcodes (switch table 0x4149b8, handlers cited)

| op | mnemonic | semantics | handler | uses |
|---|---|---|---|---|
| 1 | `push imm` | *SP = imm; SP += 1 | 0x4146d5 | 15009 |
| 2 | `pusha k` | *SP = &BP[k]; SP += 1 | 0x414701 | 0 |
| 3 | `pushv k` | *SP = BP[k]; SP += 1 | 0x414736 | 0 |
| 4 | `arga k` | queue &BP[k] (the address of a frame slot) | 0x41476b | 19869 |
| 5 | `argv k` | queue BP[k] (the slot's content, itself a pointer) | 0x4147a0 | 8661 |
| 6 | `alloc n` | SP += n | 0x4147d5 | 513 |
| 7 | `drop n` | SP -= n | 0x4147f7 | 10839 |
| 8 | `jmp L` | IP = L | 0x41481b | 5233 |
| 9 | `jz L` | if result == 0: IP = L | 0x414832 | 7487 |
| 10 | `yield L` | IP = L; end this machine's slice for the frame | 0x414989 | 2704 |
| 11 | `call L` | push BP; BP = SP; push return IP; IP = L | 0x414874 | 0 |
| 12 | `ret n` | IP = [BP]; SP = BP - (n+1); BP = [BP-1]; machine ends if SP reaches the base | 0x4148c7 | 2700 |
| 13 | `action a` | result = fsm_ActionDispatch(state, a, tables...) | 0x4148fe -> 0x412ce0 | 17584 |
| 14 | `not` | result = !result | 0x414853 | 324 |

Any other opcode logs `Unknown fsm assembler instuction` (0x414953) and continues.

**Model check** (`data	ests	est_fsm_stack.py`): walking every path of all 797 machines in the 25 scripts under
this model gives 0 contradictions over 114,397 instruction visits:

- every instruction is reached with a single stack depth;
- every `arga`/`argv` slot lies inside the live frame (locals 1..depth-1, or parameters -(nArgs+1)..-2);
- `drop` never goes below the frame;
- every `ret n` has n equal to its machine's nArgs.

### Arguments and globals

Every argument an action receives is an `int*`. Nothing is popped: the action reads fixed queue slots, and the common
epilogue (0x4144c2..0x4144d7) resets the queue and advances IP. The compiler emitted exactly two argument forms:

- `argv -k`: pass a **machine parameter**, a pointer into the globals. Entities, paths and shared variables travel this way.
- `push imm` / `arga k` / `action` / `drop 1`: pass a **literal** through a temporary local.

Because parameters point into one shared array, the "constants" block of the file is really the mission's **global
variable store**. `set`, `inc` and `dec` on a parameter write it. Across the missions, 729 of 774 such writes hit a
global that at least one other machine also takes as a parameter. That shared array is how the machines of a mission
talk to each other (fsm-actions.md section 8).

Hazards visible in the code:
- No action checks an index against its table size: the counts are passed and never read.
- `who*` and `nearest*` append `NoLabel%d` entities into the 200 spare slots without a capacity check.
- `playScene` (prototype 22) has no case. Its jump-table entry is the default, which logs and **aborts**. No shipped
  mission names it.

## 3. The 96 actions

Kinds: entity = index into the entity table (the case resolves it to a live object, or NULL once the object is being
deleted); path = path-table index; sound = string-table index; int = value; out = variable the action writes;
objective = 1-based objective number; (ignored) = queued by the missions but not read.
Result: `-` leaves the result flag alone; `bool` sets it. Uses = ACTION count over the 40 missions.

| # | action | arguments | result | what it does | case | uses |
|---|---|---|---|---|---|---|
| 0 | `null` | - | - | no-op | 0x4144c2 | 1746 |
| 1 | `behave` | entity | - | stub (logs 'not implimented') | 0x412d10 | 0 |
| 2 | `attack` | entity, entity, (ignored) | - | attacker attacks target (behaviour 0) | 0x412d4f | 171 |
| 3 | `sit` | entity | - | stop and wait (behaviour 0x1f) | 0x412db9 | 227 |
| 4 | `goto` | entity, path, int | - | drive path at speed (behaviour 0x16) | 0x412ea9 | 324 |
| 5 | `guard` | entity, entity | - | guard target (behaviour 0x20) | 0x412e3f | 16 |
| 6 | `do` | entity | - | stub | 0x413354 | 0 |
| 7 | `set` | out, int | - | *a = b | 0x413f16 | 313 |
| 8 | `inc` | out | - | ++*a | 0x413393 | 460 |
| 9 | `dec` | out | - | --*a | 0x4133a0 | 0 |
| 10 | `rand` | out, int | - | *a = rand() % n | 0x4133ad | 330 |
| 11 | `whoRammed` | entity, out | - | out = entity index of last rammer | 0x4133c9 | 0 |
| 12 | `whoShot` | entity, out | - | out = entity index of last shooter | 0x41340e | 5 |
| 13 | `startTimer` | out | - | *t = mission clock (s) | 0x41368b | 579 |
| 14 | `success` | objective | - | objective n succeeded | 0x4136a8 | 87 |
| 15 | `successAll` | int | - | win the mission after delay | 0x4136d4 | 34 |
| 16 | `fail` | objective | - | objective n failed | 0x4136be | 2 |
| 17 | `failAll` | int | - | lose the mission after delay | 0x413700 | 0 |
| 18 | `failAllObj` | int, objective | - | lose after delay, blaming objective n | 0x41372c | 182 |
| 19 | `cb` | sound | - | CB radio line (prio 3, needs valid file) | 0x413453 | 225 |
| 20 | `cbPrior` | sound, int | - | CB radio line with priority | 0x4134ee | 3001 |
| 21 | `cbFromPrior` | sound, entity, int | - | CB radio line from speaker with priority | 0x41351c | 648 |
| 22 | `playScene` | - | - | UNIMPLEMENTED: default case aborts the game | 0x4144ae | 0 |
| 23 | `nearestEnemy` | entity, out | - | out = nearest live enemy vehicle | 0x41375f | 40 |
| 24 | `nearestBlg` | entity, out | - | out = nearest standing building | 0x4137a4 | 15 |
| 25 | `true` | - | 1 | result = 1 | 0x41399f | 740 |
| 26 | `false` | - | 0 | result = 0 | 0x4139ae | 0 |
| 27 | `isEqual` | int, int | bool | a == b | 0x4139bd | 3293 |
| 28 | `isGreater` | int, int | bool | a > b | 0x4139df | 25 |
| 29 | `isLesser` | int, int | bool | a < b | 0x413a01 | 15 |
| 30 | `test` | entity | 0 | stub | 0x413a23 | 0 |
| 31 | `isWithin` | entity, entity, int | bool | 3D distance(a,b) < r | 0x413a68 | 287 |
| 32 | `isShot` | entity | bool | shot this/last frame (consumed) | 0x413ada | 17 |
| 33 | `hpLesser` | entity, (ignored), int | bool | health % < n | 0x413b18 | 68 |
| 34 | `ammoLesser` | entity, int, int | bool | ammo of hardpoint id < n | 0x413b64 | 0 |
| 35 | `isRammed` | entity | bool | rammed this/last frame (consumed) | 0x413bee | 1 |
| 36 | `isDead` | entity | bool | destroyed (0 once the object is deleted) | 0x413c2c | 1043 |
| 37 | `isLit` | entity | 0 | stub | 0x413ca8 | 0 |
| 38 | `timeGreater` | int, int | bool | now >= t0 + secs | 0x413941 | 418 |
| 39 | `timeLesser` | int, int | bool | now < t0 + secs | 0x4138f0 | 1 |
| 40 | `isArrived` | entity | bool | reached end of path (consumed) | 0x413c6a | 250 |
| 41 | `isEqualId` | entity, entity | bool | same object | 0x413ce6 | 98 |
| 42 | `isWithinNav` | path, entity, int | bool | 2D distance(path node 0, obj) < r | 0x413d4a | 136 |
| 43 | `isWithinSqNav` | path, entity, int | bool | |dx|<r and |dz|<r from path node 0 | 0x413da5 | 485 |
| 44 | `isWithinEnemy` | entity, int | bool | any enemy within 2D r | 0x413e00 | 18 |
| 45 | `isAttacked` | entity | bool | attacked this/last frame (consumed) | 0x413e45 | 300 |
| 46 | `whoAttacked` | entity, out | - | out = entity index of last attacker | 0x413ed1 | 95 |
| 47 | `setId` | out, int | - | same code as set | 0x413f16 | 0 |
| 48 | `follow` | entity, entity, entity, int, int, int | - | follow leader (aux target, flag, offsets) | 0x413f63 | 24 |
| 49 | `teleport` | entity, path, int, int | - | place at path node 0 with speed and heading (deg) | 0x4137e9 | 108 |
| 50 | `destroy` | entity | - | destroy object | 0x4138b8 | 30 |
| 51 | `playMovie` | sound | - | queue .smk | 0x4135d3 | 2 |
| 52 | `pushCam` | - | - | save camera, scripted camera mode | 0x413056 | 91 |
| 53 | `popCam` | - | - | restore camera | 0x41308d | 118 |
| 54 | `camObjObj` | entity, int, int, int, entity | - | camera at obj + offset(cm) looking at target | 0x413097 | 18 |
| 55 | `camObjDir` | entity, int, int, int, int, int, int | - | camera at obj + offset(cm), angles 1/100 deg | 0x413125 | 3 |
| 56 | `camPosObj` | path, int, entity | - | camera on path at height(cm) looking at target | 0x4131a7 | 72 |
| 57 | `camPosDir` | path, int, int, int, int | - | camera on path, fixed angles | 0x4131fe | 12 |
| 58 | `camTransObj` | path, int, int, entity | - | camera travels path (height, speed) looking at target | 0x413217 | 4 |
| 59 | `camF12` | entity, entity, int, int | - | chase camera behind subject toward target | 0x4132b9 | 14 |
| 60 | `camTransDir` | path, int, int, int, int, int | - | moving path camera, fixed angles | 0x413273 | 0 |
| 61 | `camIsArrived` | - | bool | camera reached path end (consumed) | 0x413334 | 3 |
| 62 | `isKeypress` | - | bool | skip key pressed | 0x413344 | 121 |
| 63 | `triggerGate` | entity | - | open gate | 0x413f2b | 17 |
| 64 | `evade` | entity, path, int, entity | - | evade threat along path (behaviour 0x18) | 0x412f1e | 32 |
| 65 | `toggleAvoid` | entity | - | toggle obstacle avoidance | 0x414091 | 7 |
| 66 | `allBlgDead` | - | bool | every building destroyed | 0x413e83 | 0 |
| 67 | `allEnemyDead` | entity | bool | every enemy of obj's team dead | 0x413e93 | 25 |
| 68 | `setHeliHeight` | entity, int | - | helicopter cruise height | 0x413606 | 22 |
| 69 | `setSkill` | entity, int, int | - | AI skill levels 1..5 (two tables) | 0x413645 | 235 |
| 70 | `isAtFollow` | entity | bool | in follow position (consumed) | 0x414053 | 8 |
| 71 | `control` | entity, int, int | - | queue control step (accel/brake, steer) | 0x4140c9 | 40 |
| 72 | `controlAll` | entity, int, int, int, int, int, int | - | queue full control step | 0x41410f | 0 |
| 73 | `driveControl` | entity | - | apply next queued control | 0x414191 | 1 |
| 74 | `controlDone` | entity | bool | control queue drained | 0x4141c9 | 1 |
| 75 | `reveal` | objective | - | show hidden objective n | 0x414207 | 82 |
| 76 | `isCBEmpty` | - | bool | CB queue empty | 0x413575 | 53 |
| 77 | `setAgg` | entity, int | - | AI aggression level | 0x413594 | 222 |
| 78 | `setUserRadar` | int | - | player radar on/off | 0x41421b | 0 |
| 79 | `cbFrom` | sound, entity | - | CB line from speaker | 0x41349c | 0 |
| 80 | `killCB` | - | - | flush CB queue | 0x413585 | 72 |
| 81 | `salvage` | sound | - | award salvage part by file name | 0x41422f | 0 |
| 82 | `setSiren` | entity, int | - | siren on/off | 0x414256 | 21 |
| 83 | `setAvoid` | entity, int | - | obstacle avoidance on/off | 0x414295 | 37 |
| 84 | `setMaxAttackers` | entity, int | - | max simultaneous attackers | 0x4142d4 | 40 |
| 85 | `canSee` | entity, entity | bool | line of sight | 0x414313 | 0 |
| 86 | `isAirborne` | entity | bool | wheels off the ground | 0x41437a | 24 |
| 87 | `teleportOffset` | entity, path, int, int, int, int | - | teleport to path node 0 + (dx,dz) cm | 0x413836 | 17 |
| 88 | `isGroovesFault` | entity | bool | returns ai+0xa6e0 | 0x413bb0 | 57 |
| 89 | `hide` | entity | - | hide (behaviour 0x21) | 0x412dfc | 25 |
| 90 | `startCar` | entity | - | start engine | 0x4143b8 | 53 |
| 91 | `setLights` | entity, int | - | headlights on/off | 0x4143f0 | 6 |
| 92 | `race` | entity, path, int, entity | - | race rival along path (behaviour 0x1a) | 0x412fba | 19 |
| 93 | `setArtillery` | entity, int | - | artillery on/off | 0x41442f | 9 |
| 94 | `setArtilleryRate` | entity, int | - | artillery rate | 0x41446b | 3 |
| 95 | `stopCB` | - | - | block all further CB lines | 0x4144a7 | 141 |

AI behaviour ids used by the movement actions (`ai_SetBehaviour` 0x412830, state records of 0x1354 bytes at
0x4c3e50): 0 attack, 0x16 goto, 0x18 evade, 0x1a race, 0x1e follow, 0x1f sit, 0x20 guard, 0x21 hide.

## 4. Reading a script

`python data\fmt\fsmtool.py dis miss16\T01.MSN` prints the text form, in the syntax that `assemble()` reads back:

```
section entities       ; label = placed-object instance name
    1 "groove" "vppirna1"
    2 "taurus" "t01js01"
section machines       ; start label, n_args, arg slots (global-pool indices)
    0 m0 5 [0 1 12 13 29]   ; p0=g0=1=groove/E, p1=g1=2=taurus/E, p2=g12=0/O, p3=g13=0, p4=g29=0/I
section code
m0:
  alloc 1                                  ; 0
L2:
  argv -4                                  ; 2
  argv -5                                  ; 3
  push 275                                 ; 4
  arga 2                                   ; 5
  action isWithinSqNav                     ; 6  (P:p2, E:p1, I:275)
```

- Machine lines show each parameter as `p<i>=g<global>=<initial value>`. When static dataflow finds the argument kind
  (`/E`, `/P`, `/S`, `/I`, `/O`), the value is resolved to a name.
- Every `action` line carries its resolved arguments, e.g. `(P:p2, E:p1, I:275)`: path parameter 2, entity parameter 1,
  literal 275.
- Code that no machine reaches shows no annotation. Some missions carry routines that no machine starts.

## 5. Changing a script

1. `python data\fmt\fsmtool.py dis <mission.msn> data\out\mine.fsm`
2. Edit the text. Change a literal (`push 275` -> `push 600` widens a trigger box), swap an action name for another from
   the actions section, retarget a jump label, or change a machine's parameter binding.
3. `python data\fmt\fsmtool.py asm data\out\mine.fsm <mission.msn> data\out\T01.MSN`. The tool refuses any game folder,
   reads the result back and re-parses it.
4. For single values without text editing: `python data\mod\i76mod.py set <msn> ADEF/FSM consts[12]=5` (a global's
   initial value) or `ADEF/FSM code[4].arg=600` (an operand).

Rules the engine enforces: action names must be in the prototype list (else abort). Keep every loop yielding (else
`exit(0)` after 1000 instructions). Entity labels must name ODEF OBJ instances of the same mission.

Loose-file override: the loader tries `addon\%s` before the archive for terrain (0x4939f2). Missions ship loose in
`miss8\` and `miss16\`, so an edited .msn replaces the file there, in a test copy only (see LIVE-TESTS.md).
