# The proxy on Nitro: exe detection, the Gold -> Nitro site map, and the subsystems ported (2026-10-21)

Lane `nitro-port`. Plan: docs/ARSENAL-PLAN-2026-10-21.md section 1 ("Port foundations"). Owner, 2026-10-21: "understand nitro,
get the settings dialed in for gold, get nitro working as well as gold is". Background: NITRO-VS-RETAIL-2026-10-20 (Nitro =
Gold's engine relinked), NITRO-MP-DESIGN-2026-10-21 (two corrections to this map, folded in, s.1.4), NITRO-BASE-2026-10-21.

## Answer

- **The proxy now runs on GOG's `nitro.exe` (28b8ae27) as it does on Gold**, for: logging / crash log / mute / cwd / shm
  suffix, direct mission boot, multi-instance / no-minimize / keep-active, telemetry, trainer, hires clock, fps cap / log,
  **the whole-sim tick** (12 gates, display hooks, draw-side holds, cosmetic sites), far clip, terrain LOD / vertex guard /
  hysteresis, road pool, clutter, mirror far, cam-ground, hull, health %, label table, ZGLIDE TMU fix, Glide refresh, Hor+
  aspect + HUD squeeze, CD music (on Nitro's WIN32.dll imports), joystick routing, the cursor map (nitro.exe + NITSHELL).
  With the release candidate's tick19-42 switches that are ported (`nitro-tick42`, below): **117 sites patched, 0 refused**.
- **Physics under the tick: Nitro = Gold, to the bit.** The T05 canyon jump placed at 56 m/s under the 41.667 ms tick, same
  harness, same seeds (s.3.2): the first jump of every boot took off at 50.80 m/s, vy 14.22, apex 10.32 m, 166.6 m on Gold
  HEAD 565ebde, on Gold with this lane's proxy and on Nitro with it (n 3 boots each); the later jumps of a boot fall into the
  same discrete set of outcomes on all three. TICK-FINISH's Gold 41.667 row: 50.57 / 14.16 / 10.23.
- **The Gold path is unchanged**: on Gold every new helper returns its Gold argument and patch_bytes never reaches the Nitro
  code; the Gold smoke (tick19-42, t01, n 2 per build, log line sets, s.4) matched HEAD 565ebde's build at every stage, and
  the Gold T05 jumps above are identical with and without this lane's changes.
- **Not ported yet** (s.6, ordered): the shell key / popup patches (NITSHELL), the breakable-box 4 + sign sweep, sound /
  damage telemetry events, the debug tool, AI / co-op / multiplayer (another lane), the Nitro race tick under the sim tick,
  Nitro's two extra radar pings, and the renderer-dependent measurements (T05 route fps, churn census, pointer read-back) that
  waited on the console.

## 1. The site map

### 1.1 What the proxy names

`tools/nitro-sites/gen_sites.py` extracts every exe address the proxy's code uses (music-fix/*.c and u32x/u32x_full.c, comments
and strings stripped; also addresses written little-endian inside byte arrays, e.g. the IAT slot in `FF 15 40 C3 4B 00`) plus
`extra_sites.txt` (addresses the code computes, `base + 6`). **628 addresses**: 442 in code, 185 data, 1 header. (The "845" of
the plan counted comments: with comments the source names 1,001 distinct exe-range values and 84 i76shell addresses.)

### 1.2 How each is mapped

| step | what |
|---|---|
| function pairs | lab `emu/tools/memtrace/exe_diff_map.json` (Ghidra VT vt-nitro + call-graph propagation, NITRO-VS-RETAIL s.1), bounds from i76-map `ghidra/export{,-nitro}/functions.csv` |
| instruction alignment | both functions disassembled (capstone), difflib on a normalised token (mnemonic + operands; in-image addresses masked, entity fields +0x444..+0x5ff folded, relative branches as `R`); a site maps to the aligned instruction (+ the same offset inside it); a function entry maps to the paired entry |
| signature | the Gold (6319abf7) and Nitro bytes of the whole instructions from the site through >= 16 bytes; `ok` = how many bytes from the site are the same instructions up to relocation **with corresponding call / branch targets** (a call to the paired function, a branch to the aligned instruction) |
| data | votes from token-equal aligned pairs only; IAT slots by import name (Gold WINMM -> Nitro WIN32.dll, u32x -> USER32); a global with no vote of its own takes a voted neighbour's delta when the neighbours below and above agree (`bracketed`) or the one below within 0x40 (`near`) |
| use audit | every instruction in either exe that names a data site, address masked: a Nitro-only use kind is flagged `USE-DIFFERS` for a hand read (22 flagged; read: register / stack-slot variants and one real meaning change, s.1.4) |
| hand-read pairs | `manual_sites.txt` (34 rows), each with the reason; they override the generated row |

### 1.3 Coverage

| | sites | mapped | signature in the header | refused by design |
|---|---|---|---|---|
| code | 442 | 430 (exact 63, reloc 312, manual 32, voted 3, differs 20) | 427 (all 427 match the running nitro.exe at DllMain: `nitro: site table 628 rows: 427 code sites, 427 match memory`) | 12 unmapped (functions with no Nitro counterpart: coop / aimelee / CD-instrument internals, not ported) |
| data | 185 | 181 (voted 169, voted-split 4, bracketed 3, near 3, manual 2) | - (data is checked by use, not bytes) | 4 unmapped + 0x541010 refused raw (s.1.4) |

`differs` (20) are sites whose following instructions change (AiO's simclock rewrite, Nitro's own code after a call); the
proxy uses one only when its patch fits inside `ok`.

### 1.4 Corrections and hand reads (all in manual_sites.txt)

- **0x541010 (team play)** maps to no word: Nitro keeps it as bit 0x2000 of the session flags 0x53f228 (nitro-mp-design lane);
  the vote had paired it with the whole word. Refused raw (nitro 0 in the table).
- **0x452d9f (scoreboard call)** -> 0x4486ab (`push 0; call 0x449ef0`), not the generated 0x4486b3 (another callee). The generator
  now requires call targets to correspond; that check alone re-classified 0x452d9f and four main-loop calls.
- **Main loop** (WinMain frame body, read side by side): same order in both; `entity_TickAll` 0x461c80 -> 0x44f9c0 and
  `entity_PostTickAll` 0x461d50 -> 0x44fa90 (twins the exediff left unmatched); Nitro inserts `call 0x444bb0` (race checkpoints /
  laps) at 0x432e15, between RegenPointTick (b) and PostTickAll.
- Pattern-found: mission-name pre-parse clear 0x43197d (`mov [0x526758], dl`), WndProc minimise 0x433c3c, zoom 0x437bbf, radar
  pings 0x45dc20 / 0x45df2d (Nitro has two more, 0x45e0c5 / 0x45e220, for its own missiles), terrain-tex 0x497438, class table
  0x4f7f98 (8 entries compared), the 17 fov pushes (Gold + 0x2f180, same order), the label-table grow block (38 bytes, Gold +
  0x5a20), single-instance je 0x431912.
- Checked by use (uses.py): weapon instances 0x5aab08 -> 0x5b5358 and records 0x5be4d8 -> 0x5c8d28 (strides 0x4c / 0x2c8 in
  both), play flags 0x654b98 -> 0x5fb0f8, particle heads 0x65528c (stride 0xd0), aspect constant 0x4bc510 -> 0x4c2080 (3.0 in the
  camera aspect setup), throttle 0x5367cc -> 0x5348fc.
- Not yet read: 0x654b90 -> 0x5fb0f1 (a byte at an odd offset; used only by the lab av-log, not ported).

## 2. How the proxy uses the map (music-fix/nitro.c)

- **Exe detection** first in DllMain: Nitro = PE stamp 0x351c24ce **and** crc32 of .text = the generator's (so another Nitro build
  is not taken for this one); Gold = 0x34ecb06c; anything else takes the Gold path as before. Nitro runs `nitro_dllmain`: only the
  apply_* calls ported (the list is the README section "Nitro").
- **patch_bytes(gold_va, ...)** on Nitro: the site is looked up; when the caller expects Gold's pristine bytes, memory must be the
  table's Nitro bytes and the patch must fit `ok`; bytes the patch keeps come from Nitro's instruction (`74 1c -> eb 1c` becomes
  `eb 31`), a call / jmp rel32 at offset 0 is re-aimed, a changed dword that is a mapped Gold address is translated; a chained
  patch (expecting an earlier patch of ours) is relocated and compared. Anything else: `site <what> (gold .. -> nitro ..): <reason>,
  feature off`, return 0.
- `NA(gold)` for reads / calls (0 = unmapped), `nrd32`, `EF(off)` (entity fields +4 at and above +0x444), `site_is()` for the
  pre-checks, `nitro_reloc_stub()` for our naked asm stubs' exe immediates, `nitro_need()` for a feature's runtime addresses.
- Two refusal bugs found on the first boots and fixed: the multi-instance `eb 1c` jumped into Nitro's return path (the game exited)
  before kept bytes came from Nitro's instruction; a size (0x400000) and opcode bytes running into a pointer were taken for exe
  addresses.

## 3. Measurements

Lab copy `i76-uncap-lab\exp-nitro-port` = `i76-map\sandbox-gog\nitro-full\app` + dgVoodoo from the release candidate (GOG's
OpenGLide DLLs kept in `_gog-originals`); T05's mission files added for s.3.2 only (the nitro-plus-original arrangement). Gold
copy `exp-nitro-port-gold` = the release candidate's folder. Harness `tools\nitro-port\np-run.ps1` (private desktop, I76_MUTE +
mute watcher, I76_SHM_SUFFIX = the copy's name, waits on `.fps-lock` and on any i76 / nitro outside lab copies, stops only its own
game). Captures `captures\nitro-port-20261021` (np-run's .log / .txt / .json / .side.*). Until the morning's console return the session was RDP: rows
marked RDP are log / memory checks only.

### 3.1 Per subsystem

| subsystem | Gold sites -> Nitro | signatures | measurement on Nitro (n) | vs Gold | status |
|---|---|---|---|---|---|
| DllMain, logging, crash log, mute, cwd, shm suffix | - | - | log lines, `shm: suffix=exp-nitro-port`, mute read back (every boot) | same lines | **yes** |
| mission boot (I76_MISSION, I76_SKIP_MOVIES) | 0x402d33 -> 0x43197d (manual), 0x49d1e0 -> 0x49979f, movie names 0x4c25b0 / a4 -> 0x4f3540 / 34 | 4/4 | P01 and T05 boot to a live player in 1 s (n > 20) | as Gold | **yes** |
| multi-instance, no-minimize, keep-active | 0x402caf -> 0x431912, 0x404acc -> 0x433c3c | 2/2 | headless boots run (n > 20) | - | **yes** |
| telemetry (snapshot + shot / explosion / impact events) | 23 reads, 4 event sites | 4/4 | shm frame pos = the process's player position each sample; seq advances (RDP, n 1) | - | **yes** (sound / damage events: no) |
| trainer block + cheat-marker guard | 8 reads, 4 guard sites | 4/4 | heartbeat = frame; CMD_TELEPORT +5 m acked, read back dy 4.99 m (RDP, n 1); god / teleport drive s.3.2 | - | **yes** |
| hires clock, fps cap | 0x49c85d / 0x49c927 -> 0x4a2c7f / 0x4a2d49, frame hook 0x4039b8 -> 0x432805 | 3/3 | dt 41.667 ms exact at I76_FPS_CAP=24 (RDP, n 1) | - | **yes** |
| whole-sim tick (I76_SIM_TICK_MS) | 12 gates (3 manual), 4 display hooks, 16 draw-side holds, 7 cosmetic sites, class slot 0x4f7fb0 | 39/39 | 23.99 ticks / s, player 1 step x 41.67 ms per tick (RDP); the T05 jump s.3.2 (console, n 3) | identical (s.3.2) | **yes**; Nitro's race tick 0x444bb0 not gated |
| far clip | 5 pool immediates + read site | 6/6 | `far-clip: on (1200 m, pools x16, 6/6)`, 60 s P01 (n 2); P05 route fps at 1200 / 1800 / 2000 m, s.9.2 | - | **yes** (s.9) |
| terrain LOD A / B, vertex guard, hysteresis / freeze, terrain-tex, object LOD, shadow / road distances, road pool, clutter, mirror far, cam-ground, hull | 6 + 1 + 2 + ... (stubs relocated: vguard, hyst, road node) | all | every site patched, 0 refused; clutter 600-frame lines 605-873 us, 0 refused; road pool 0 refusals (n 3) | - | **yes**; churn census / T05 route fps not run |
| health %, label table | 0x40b7b8 / 0x40b6f0 (+3 stubs), 0x4ad465 (38 B, manual) | 2/2 | `fix-health-pct: on`, `fix-label-table: on`; telemetry health 100 at start (n 1) | - | **yes** (the % values not compared yet) |
| ZGLIDE TMU fix, Glide refresh 120 | Nitro ZGLIDE f28fe42b: +0x2c9a 75 26 (Gold +0x1a93 75 24) | 1/1 | `eb 26`, grSstWinOpen refresh 0 -> 120 Hz (n 1) | - | **yes** |
| aspect + HUD squeeze | 17 fov pushes (manual), hood fov, clamp, constant, 2 HUD calls | 22/22 | `aspect: D 2.389, 20/20`, `hud-squeeze 2/2` (n 1) | - | **yes** (picture not looked at) |
| CD music | WIN32.dll!mciSendCommandA / aux*; watchdog 0x42340d -> 0x418f5d | 1/1 | TOC 2..11 served; `MCI_PLAY ... run 2..2`, track 2 played (n 1) | - | **partial**: resume / gapless / true pause not exercised |
| joystick routing / tick joystick watch | WIN32.dll!joyGetPosEx / joyGetDevCapsA | - | slots hooked, watch on (n 1) | - | **yes** |
| cursor map | nitro.exe and NITSHELL.DLL USER32 slots | 4/4 + 4/4 | pointer read-back + clicks s.10 (n 3): pencil and click point within 4 px; MELEE > MULTI MELEE > JOIN | - | **yes** with I76_CURSOR_MAP_SHELL=aw (s.10) |
| u32x | - | - | not attached (Nitro imports USER32 directly; no import rename) | - | **no** |
| shell key / popup patches (NITSHELL) | - | - | - | - | **no** |
| breakable box 4 + sign sweep | 17 sites | - | not wired | - | **no** |
| debug tool | - | - | - | - | **no** |

### 3.2 The T05 jump (TWO-CLOCKS / tick-range protocol on a placed jump)

`tools\nitro-port\np_physjump.py` beside a T05 boot (console, private desktop, 41.667 ms tick; Gold: release candidate tick19-42
preset; Nitro: `nitro-tick42`): after the handover, god on; three jumps per boot, each placed 150 m before the aaramp4 foot on
its centre line (z 43910 + seeded offset +-0.5 m), heading -x, TELEPORT at 56 m/s, throttle held, 8 s recorded; metrics from
the tick lanes' code (`lip_scan.scan`, `tc_analyse.jump_extra`; `np_jump_analyse.py`). Gold boots need the lab twin's
I76_HEADLESS_ACTIVE (difficulty lane insert; `build-lab.ps1`), Nitro does not.

| arm (n 3 boots, seeds 2-4) | jump 1 of each boot: take-off m/s, vy, apex m, distance m (foot 55.82 m/s) | all 9 jumps |
|---|---|---|
| Gold, HEAD 565ebde (lab twin fd736182) | 50.80, 14.22, 10.32, 166.6 (3 of 3 identical) | 50.80 x3, 48.33 x3, 50.07 x1, lip clip 45.28 x2 |
| Gold, this lane's proxy (lab twin w13-lab 71018039) | 50.80, 14.22, 10.32, 166.6 (3 of 3) | 50.80 / 50.79 x5, 48.33 x2, 50.07 x1, clip x1 |
| **Nitro, this lane's proxy (w12 fc8e2a17)** | **50.80, 14.22, 10.32, 166.6 (3 of 3)** | 50.80 x3, 48.33 x3, 47.93 x1, 50.07 x1, clip x1 |

The second and third jump of a boot start ~43 m/s at the foot (the placement keeps state from the previous jump) and land on a
handful of discrete outcomes that depend on the tick phase at the placement; each outcome occurs on both exes. TICK-FINISH's
Gold 41.667 ms row for comparison: 50.57 / 14.16 / 10.23. **Bounce half period: not measured** (the drops from rest at the
handover spot hung in the air for ~1 s before falling, on both exes; the tick lanes used T06's drop spot).

## 4. The Gold smoke

`tools\nitro-port\gold-smoke.ps1` + `compare_logs.py`: the Gold copy, tick19-42 preset, t01, n 2 per build, normalised log line
sets against the build of HEAD 565ebde made the same way (`builds\nitro-port-20261021\base-565ebde`, 02b9bf04), 0 CRASH lines
in every run. Stages 1-5 (RDP): the same set apart from lines that only appear when a boot gets further (the CD TOC read,
auxSetVolume; they appear in base runs too). Stage 6 (console): **same line set** (129 lines, n 2 each). Under RDP no Gold boot
left the start-up wait (base and new alike); at the console Gold's t01 boots exit when the probe posts Esc on the opening (base
and new alike), so the gameplay part of the Gold check is the T05 jump table above.

Side finding, for main: while the p19 gate ran (08:30-09:30), every Gold i76.exe this lane started on a private desktop was ended
with exit code -1 after 6-37 s, nitro.exe never; with the gate idle the same boots ran. Not traced (another lane's harness ends
`i76` processes by name?).

## 5. Staged

`i76-uncap-lab\builds\nitro-port-20261021\` (MD5SUMS there): the candidate built from the committed tree, the Gold baseline,
and the lab twins used in s.3.2. Installed nowhere.

## 6. What remains, in order

1. Renderer-dependent rows at the console, outside `.fps-lock`: Nitro's own missions (P01.., N arenas): far clip / terrain fps and
   the churn census (rc-draw tools on a Nitro route), the pointer read-back of the cursor map in NITSHELL's menus.
2. Bounce half period on both exes from a flat spot (T06-style drop) and the health % values against Gold's.
3. Music: resume / true pause / gapless exercised on Nitro (Esc menu in a mission); Nitro's track numbering (music\0.mp3).
4. Nitro's race tick 0x444bb0 under the sim tick (a 13th gate, Nitro-only), Nitro's extra radar pings.
5. Shell key / popup patches on NITSHELL (no Ghidra export of either shell yet; owner note: Nitro's menu tables are fragile, every
   table edit signature-checked and refused on mismatch).
6. Breakable box 4 + sign sweep (collision lists; Nitro added collision classes 0x5a / 0x5b), sound / damage telemetry events.
7. The debug tool against Nitro (its trainer block is ported; its menu reads Gold addresses).
8. u32x for Nitro (import rename of nitro.exe / NITSHELL) only if the proxy's cursor map is not enough.
9. Multiplayer hooks (another lane): the receive path is ANET2.DLL!dpReceive at IAT 0x4c13cc from the pump 0x448d80.

## 7. Second session (2026-10-21, afternoon): the remaining list, items needing no console

### 7.1 Music on Nitro (item 3)

- **True pause / resume, measured.** A private desktop gets no keyboard (Esc posted to the game's windows is not read: the
  engine's keyboard is the input desktop's), so a lab twin (`tools\nitro-port\insert-pausetest.py`, never staged) calls the
  exe's own `sound_PauseAll` / `sound_UnpauseAll` (Gold 0x4234a0 / 0x4234e0, Nitro 0x418ff0 / 0x419030 - what the in-mission
  menu calls) at proxy frames 600 / 1080 / 1560 / 2040 in P01: `MCI_PAUSE: track 2 paused, status reads paused until
  MCI_RESUME` and `MCI_RESUME: track 2 continues`, twice each (n 1 boot, 2 cycles). The two functions also confirm the music
  byte 0x654b90 -> 0x5fb0f1 (both test it `> 1` before the CD call): s.1.4's open item is closed.
- **Nitro plays to the end of the disc.** Nitro's CD player (0x41cae0) sends MCI_PLAY with MCI_FROM alone (flags 0x4); on a CD
  that plays to the last track. The proxy now does that on Nitro (run 2..11); Gold sends FROM|TO (0xC) and is unchanged.
- **Gapless, measured** with music\2.mp3 cut to 250 KB in the lab copy (restored after): `run 2..11: track 2 ended -> 3`,
  PLAY track 3 16 ms later (n 1).

### 7.2 Nitro's race tick and radar pings (item 4)

`nitro_patch_call()` (nitro.c) repoints a call that exists only in nitro.exe after checking it targets the expected Nitro
function. Under I76_SIM_TICK_MS the race tick (0x432e15 -> 0x444bb0) runs once per tick, and Nitro's two extra radar pings
(0x45e0c5 / 0x45e220 -> 0x41da40) go through the same wrapper as the two Gold ones. Log lines only (n 2 boots): the race tick
returns at once outside race mode, and no radar missile was fired.

### 7.3 NITSHELL key / popup patches (item 5)

`tools/patch-nitshell-f7.py` and `tools/patch-nitshell-modals.py` (file patches, as Gold's are): F7 (Enter / Space close
Modal_Ok and Modal_ImageOk) and M2 (Modal_Ok's stray OK label). NITSHELL f804f50d has Gold's modal loops byte for byte apart
from addresses (Modal_Ok 0x1002257a, Modal_ImageOk 0x100226f0, Modal_VehicleRejected 0x10022847, KeyInput_Poll 0x1000ae30 on
[0x1013047c] with the same return convention). Both scripts refuse on any unexpected byte, check relocations and read the
output back. Emulation 22 / 22 (and still 22 / 22 on Gold's shell); the patched shell (3e1eb76c) booted once to the shell, 40
s, no fault. Not ported: M1 (needs a frame count in Nitro's DATABASE.TVF), K1-K4 (the other modals' keys; NITSHELL's
Modal_YesNo and team picker are there). Staged in lab `builds\nitro-port-20261021\nitshell`, installed nowhere.

### 7.4 Breakable box 4, sign sweep, sound / damage events (item 6)

Ported with the same helpers (runtime reads through NA, the bbox stub's 0x52b92c relocated, the flamer narrow-test chain's
Gold-relative bytes, `site_is` for the speed wrapper). P01 with I76_BREAKABLE_BOX=4 + I76_SOUND_EVENTS + I76_DAMAGE_EVENTS:
133 sites patched, 0 refused; breakable box 1/1, flame 1/1 + 1/1, speed 1/1; sound events 4/4 stop taps + start tap +
weapon-UI 3/3; damage entry detoured; telemetry event_seq 38 after 40 s, event_hooks 127 (every hook). The T05 barricade ram
test (the Gold gate's breakable row) was not run.

### 7.5 The debug tool (item 7)

tools/debug: the process reader lists nitro.exe and reads it with a Nitro address set (game state, pause bits, player root,
AI lists, CD state; entity fields +4). P01: state 5, CD track 2 playing, 8 / 8 AI cars, nearest 52-308 m, entity flags 0x81001.
Its trainer tab drives the proxy block (ported); its direct pokes stay Gold-only.

### 7.6 Bounce and health % (item 2)

`np_physjump.py --mode bounce` on T06 (the tick lanes' spot: (7935, 42900), identity attitude, 1 m and 3 m drops from rest,
three each per boot), then a 40 m drop at (7930, 42580) without god.

| arm | heave half period 1 m (n) | 3 m (n) | 40 m drop: health % after (n) |
|---|---|---|---|
| Nitro (w16, nitro-tick42) | 0.333 +- 0.000 (6) | 0.292 +- 0.000 (6) | 84.9 (3 of 3: chassis 580 / 720 / 720 / 569, = 28 + 72 x 569 / 720) |
| Gold (lab twin w16-lab 0a1b35a1, tick19-42) | 0.319 +- 0.022 (6: 0.292 x2, 0.333 x4) | 0.292 +- 0.000 (6) | 84.9 (2 of 2, the same part damage: chassis 580 / 720 / 720 / 569) |
| TICK-FINISH, Gold 41.667 | 0.292 | | |

The 3 m drop and the 40 m drop's damage are identical on both exes. The 1 m half period is 7 or 8 car steps (0.292 / 0.333 s)
on Gold depending on where in the tick the drop starts; Nitro gave 8 steps 6 of 6 - inside the same quantised set, the
pattern of the T05 jumps' later placements (s.3.2). Bounce on Nitro's own missions was not measured.

## 8. Third session (2026-10-21, evening): T05 rams headless, NITSHELL M1 / K1-K4

### 8.1 T05 sign and barricade rams (item 2)

Harness: lab tools/nitro-port/np_ram.py = tools/framerate/rate-ab-live.py `ram --direct` with Nitro's addresses. Two things
needed changing, and they apply to both exes:
- Rotation goes through the trainer's STORE_STATE + SET_STATE. On both exes the sim tick undoes outside writes to obj+0x18
  (np_rottest.py).
- Keys go through a lab drive block (insert-npdrive.py, I76_NP_DRIVE=1: key bytes written before input_ApplyToEntity). A
  private desktop gets no keyboard.

Builds: w17-lab-drive (lab twin) and w17 (plain).

**Finding: on Nitro the sign sweep faulted on its first knock-off.** The sweep's sign sound (polish.c, via st_sign_sound)
called Gold's 0x4231f0 with Gold's string address 0x4f1578. The fault turned the sweep off, so no post was knocked (box 4:
0 of 7; box 0: 0 of 7). Fix: NA() on 0x4231f0 / 0x4221d0 / 0x4f1578 (commit 6d20e40). Gold headless smoke w16 vs w17: same
line set, 0 crash lines (n 2 each).

| run (T05, 20 m/s, 40 m run-up) | Gold | Nitro |
|---|---|---|
| sh38 signs, BOX=4 (7 posts) | 7 / 7 knocked (n 1, w16 twin) | 7 / 7 and 7 / 7 knocked (n 2) |
| swend barricade, BOX=4 (10 approaches) | 7 knocked, 3 "?" | 7 knocked, 3 "?" (same rams) |
| swend barricade, no box (10 approaches) | 8 knocked, 2 "?" | 8 knocked, 2 "?" (same rams) |
| class-4 hits scored by breakable-speed | 10 (BOX=4) / 0 | 10 (BOX=4) / 0 |

What the table shows:
- Nitro matches Gold ram for ram, including the same lateral offsets and the same outcome per approach.
- Every sign knock-off on both exes came from the sweep, after the deferral to the drawn car. Gold's log shows the same
  thing.
- The harness's contact column reads 0 on both exes: the IMPACT / coll_events path does not fire for these victims in this
  setup. So PROMOTIONS row 17's barricade numbers (G+BOX=4 7 / 7 contacted vs control 3 / 15) are not reproduced here.
- The knocked-over count does not separate box from control at this approach set (7 vs 8 on both exes). The A/B that holds
  is Gold = Nitro.

### 8.2 NITSHELL M1 and K1-K4 (item 3)

`tools/patch-nitshell-modals.py` (commit 66bdd1a) now carries M2 + K1-K4. M1 does not apply to Nitro, so it is not ported.

**M1.** Nitro's Modal_VehicleRejected 0x10022770 draws frame 0x21 of its own modal art table: DATABASE.TVF item 0x1e, 48
frames, loaded at 0x10025a45. Gold's draws frame 0x22 of MW2 item 0x24, which has only 34 frames. Frame 0x21 is the 282 x 93
"CHEATING BASTARD ALERT! YOU CANNOT PLAY WITH A HACKED VEHICLE" panel, with OK on the hit rect (rendered:
lab captures/nitro-port-20261021/nitshell-art).

**The four K sites:**
- K1, Modal_VehicleRejected: Enter / Space close it.
- K2, Modal_CdRetry 0x10022ae0 ("SUGAR, PUT IN THE NITRO PACK CD NOW", the CD check at 0x1000899e): Enter = OK, Esc = CANCEL.
  Its no-click path 0x10022c28 (a pump call) is kept.
- K3, Modal_YesNo: Y = YES, N / Esc = NO.
- K4, the list picker 0x10022e00 (Nitro's generalised Modal_OneButton; type 0x12 = CHOOSE A TEAM): Enter = DONE (current
  selection), Esc = CANCEL (-1).

**Caves.** They sit at 0x100396c0..0x100397df, after F7's; .text VirtualSize goes to 0x38800, so F7 must run first. Each cave
saves esi, which is live in the picker.

**Checks.**
- Emulation 53 / 53, with stack, esi, ebx and ebp kept.
- The script refuses a file with one hook byte flipped.
- A second run writes nothing; --check reports all five patches present.

Staged: lab builds/nitro-port-20261021/nitshell/nitshell-f7-m2-k1234.dll (a32ffba6), installed nowhere, not booted. Not
ported: the three-button modal 0x100228c0, which has no Gold counterpart.

### 8.3 Site-table correction: function entries (nitro-mp lane report)

**The defect.** Gold 0x451570 (net_RequestRespawn) was mapped to Nitro 0x44cb06, which is inside the function. The function
starts at 0x44caf0 (the mp lane checked this with its own signature). Nitro's version gained a 0x16-byte prologue, and the
instruction aligner matched Gold's entry instruction (call ...) to the same call 0x16 bytes in. The entry rule in
gen_sites.py only applied when the entry was not aligned at all.

**The fix (gen_sites.py).** A Gold function entry now always maps to the paired Nitro entry. The signature is taken from the
entry, so a patch on the entry bytes is refused when they differ. One more generator fix: literals on `nitro_patch_call(`
lines are Nitro addresses and are no longer read as Gold sites; they had added 5 spurious rows. The table is still 628 rows.

**Census.** Every mapped code row was checked against both Ghidra function-start lists (export / export-nitro
functions.csv). 430 mapped code rows; 135 of them are Gold entries.

| | old table | new table |
|---|---|---|
| Gold entry -> Nitro not an entry | 4 | 2 |
| Gold not an entry -> Nitro entry | 0 | 0 |

The rows involved:
- **0x451570 -> 0x44caf0** (was 0x44cb06). Used by aimelee.c and coop_auto_respawn.
- **0x441930 -> 0x42d890** (was 0x42d895, 5 bytes in). renderer_QueueSmokePuff, which smoke_update_wrap calls. The old
  address skipped Nitro's first instruction, `mov al,[0x5fb0f0]`, and then tested whatever was left in al: a real bug,
  fixed by this.
- **0x406ab0 -> 0x435c30 and 0x407ad0 -> 0x436c50** (camera-mode callbacks, voted 3/3). Both are real function starts:
  `ret` / nop padding before them and the same prologue as Gold. Ghidra folded them into the functions before
  (0x435aa0 / 0x436ad0). The mapping is correct; Nitro's function list is incomplete there.

**Boot check.** w18 (8dd78b91) on Nitro P01: 120 sites patched, 0 refused. It ran past frame 600. The usual first-chance
0xC0000096 at 0x49acb7 in frame 0 appears in every Nitro log since the first boot. The Gold path never reads the table, so
the Gold smoke was not rerun.

## 9. Console rows (2026-10-21 evening / 10-22 night), Nitro's own missions

The rows ran once .gate-done and .rebase-done existed.
- **Locks.** Each boot took `.fps-lock` (np-run.ps1 -Console) and released it after. It waited while `.console-owner` existed.
- **Load.** Three other lanes ran headless games at the same time. Every boot logged the other lab games running after it.
- **Raw data.** Lab captures/nitro-port-20261021/route-*, cursor/; summary from tools/nitro-port/np_route_tab.py.
- **Builds.**
  - fps: w18-lab-drive. Its working tree held another lane's uncommitted terrainmorph.c include; that code is opt-in and never
    applied on Nitro, and no morph line appears in any log.
  - census: w19-lab-census, built from dda3bee plus the drive and census inserts.

### 9.1 Method

The route is a road leg in the cockpit, as the rc-draw lane's T05 route on Gold (RC-DRAW-FPS-2026-10-20).
- **Placement.** A trainer TELEPORT, then STORE / SET_STATE sets the heading along the road. P05's opening script hands the car
  over at the same spot every time.
- **Driving.** The drive block (W / S / A / D) and rcd_drive's road follower, at 22 m/s for 90 s, along P05's RSEG 1 (5.8 km
  paved), about 2.05 km per leg.
- **fps.** From I76_FRAME_LOG between the leg's proxy frames, with rcd_tab.py's statistics.
- **Churn.** The rc-draw leaf census, ported (insert-npcensus.py, every address through NA; terrain height 0x493160 -> 0x494fe0
  added to the site map).
- **Conditions.** I76_FAR_CLIP = I76_ROAD_DIST = I76_CLUTTER_DIST = 1200 (the preset), 1800 and 2000, interleaved; the rest is
  nitro-tick42.psd1 with its 120 fps cap.

Other Nitro missions did not give a usable leg:
- P15 stops dead at an obstacle on every road tried (290 m on RSEG 11 and 12, 800 m on RSEG 8). Its RSEG 11 legs are a second,
  short row.
- On P06 and P01 the opening holds the car.
- P19 and P03 end the mission within 15-20 s of the leg.

### 9.2 Far clip / terrain fps, and the sim clock

| mission, condition | fps n | median fps | 1 % low (sorted) | mean | lowest 1 s (sorted) | mean | sim s / wall s |
|---|---|---|---|---|---|---|---|
| P05 1200 m | 5 | 120 (cap) all | 95.2 98.0 102.8 105.6 106.8 | 101.7 | 109 118 118 119 120 | 116.8 | 1.000 |
| P05 1800 m | 6 | 120 all | 80.4 88.4 89.2 90.9 96.6 100.1 | 90.9 | 90 105 113 115 117 117 | 109.5 | 1.000 |
| P05 2000 m | 6 | 120 all | 84.3 85.1 90.4 92.9 93.6 97.9 | 90.7 | 92 105 111 114 116 118 | 109.3 | 1.000 |
| P15 1200 m (290 m legs) | 2 | 120 | 105.2 109.8 | 107.5 | 120 120 | 120 | 1.000 |
| P15 1800 m | 2 | 119.4 / 120 | 91.8 97.7 | 94.8 | 103 118 | 110.5 | 1.001 |
| P15 2000 m | 2 | 120 | 95.3 95.7 | 95.5 | 116 118 | 117.0 | 1.000 |

- **The median stays at the 120 cap at every distance.** Going from 1200 m to 1800 / 2000 m lowers the 1 % low by about
  10 fps (101.7 -> about 91) and the worst second by about 7 frames.
- **2000 m costs no more than 1800 m** on this route: 90.7 vs 90.9 mean 1 % low, 109.3 vs 109.5 worst second.
- **Every boot read back the far clip it set:** 1200 / 1800 / 2000 from the pointer at Nitro 0x434b5f, which is Gold 0x4059df.
- **Sim clock.** Every console boot advanced 0.9997-1.0006 sim seconds per wall second while it ran alone under `.fps-lock`. So the
  MP lane's 0.856 in its evening headless runs is not the clock; it is load.
- **How the sets were run.** The fps n combines queue q1 (20:54-21:40, which braked with a held S, a later fix) and q7 / c1 / c1b /
  c1c (pulsed S). The pooled rows sit in the same range.

**Void rows.** route-c1 1800-r1, 2000-r1 and 1200-r2 (23:17-23:24) were taken with the console panel asleep: dgVoodoo then
presents a flat 35-36 ms frame (27 fps). 1800-r2 began asleep and woke at 23:26 mid-leg. All four are marked VOID in route-c1.tsv
and were re-run (c1b, c1c). np-run.ps1 -Console now nudges the mouse and asserts ES_DISPLAY_REQUIRED before each boot, and
np_route.py flags a leg whose frames sit at about 36 ms.

### 9.3 Terrain churn (P05, cockpit passes, n 2 per condition)

| condition | splits + merges / s | frames changing % | changed px / s (near / mid / far) | terrain verts median |
|---|---|---|---|---|
| 1200 m | 29.8, 29.8 | 22.0, 22.0 | 376.7, 374.6 (66.3 / 235.0 / 75.4; 65.8 / 233.5 / 75.3) | 3317, 3299 |
| 1800 m | 31.9, 32.0 | 23.2, 23.4 | 396.6, 396.7 (65.9 / 235.2 / 95.5; 66.5 / 234.2 / 96.1) | 6705, 6709 |
| 2000 m | 32.1, 31.4 | 23.4, 22.9 | 398.5, 395.4 (67.0 / 235.2 / 96.4; 62.7 / 239.3 / 93.5) | 6714, 6716 |

- **The two boots of each condition agree within about 2 %.**
- **Going from 1200 m to 1800 / 2000 m doubles the drawn terrain vertices** (about 3300 -> about 6700). It adds about 7 % splits /
  merges, entirely in the far band (75 -> about 95 px/s).
- **2000 m adds nothing over 1800 m.** P05's terrain beyond 1800 m is hull-clipped or flat.

### 9.4 NITSHELL pointer read-back

Method: np-measure-cursor.ps1 (measure-cursor.ps1 on nitro.exe / NITSHELL), started as np-run's side process. Launched from a
background job, the game never got the foreground.

Getting to the menu:
- A boot with I76_SKIP_MOVIES and no mission shows a black screen that waits for a key. Esc / Enter, sent only while the game
  is foreground, reach the main menu.
- NITSHELL loads relocated (0x2fc0000 / 0x3090000, not 0x10000000).
- Its mouse object [0x10130484] is 0 until the menu is up.

**Result (map on, I76_CURSOR_MAP=1 + _DGV=aw, vs off; n 1 each): identical.**
- The OS pointer itself is held inside screen (0..639, 0..479). SetCursorPos(1720, 720) reads back (639, 479).
- The shell's UI mouse equals that screen position.
- So on this 3440x1440 display Nitro's menu pointer is confined to the top-left 640x480 pixels, and the proxy's cursor map has
  no effect on it.

Status of the cursor-map row: **no (does not work on this display)**. Next: find who clips (a ClipCursor in nitro.exe / NITSHELL /
dgVoodoo's Glide window) and route it through the cursor map, or u32x for Nitro (s.6 item 8).

### 9.5 The nitro-mac build ad904941 on the PC (coordinator item)

**Builds.** `build.ps1 -Ref 3d7c3e0` reproduces ad904941 byte for byte; the previous HEAD 610ef86 is 5caf244c. Note that
610ef86..3d7c3e0 also carries 6760b24 (nitro_form.c, MP lane), not only the three Mac fixes.

**Gold smoke (n 2 each):** same line set, 0 crash lines.

**Nitro P01 smoke (n 2 each, 60 s):**
- Both builds: 120 sites patched, 0 refused; the same first-chance 0xC0000096 in frame 0 as every Nitro boot; sim time 57.5 s in
  59 s.
- Differences, only on ad904941:
  - `nitro shell watch: on`, with no attach line, so the LoadLibraryA hook saw NITSHELL / ZGLIDE itself;
  - `pit-skip: off (Windows: the game gets past the probe)`;
  - `nitro-form: ON - 6/6 nitshell sites` (from 6760b24).
- Not differences: the GetTickCount stamps on the music lines and the per-boot terrain-hull events.

**Verdict: the PC behaviour equals the previous HEAD build's**, plus the inert Mac switches and nitro_form.

## 10. The Nitro menu pointer held in 0..639 x 0..479 (2026-10-22 night): found and fixed in the proxy

**Cause.**
- The two dgVoodoo.conf files (Gold copy and Nitro copy) are identical: CaptureMouse false, [DirectX] 1680x1050,
  stretched_ar. So the conf is not the difference.
- A boot with I76_CURSOR_LOG=1 showed no clip rectangle: GetClipCursor read (0,0)-(3440,1440), and the only ClipCursor calls
  were NULL.
- Instead every GetCursorPos passed through unmapped ("(pass)"). The proxy's cursor map looked for its window by Gold's class
  and title only (`Interstate '76 Gold Edition`). Nitro's window is `Interstate '76 Nitro Pack`, so cm_window() found
  nothing and the map stood down.
- NITSHELL then read raw screen pixels (1032, 720), clamped them to its 639 x 479 page and wrote the clamped position back
  with SetCursorPos. That holds the OS pointer in the top-left 640x480 of the screen, and is what the read-back saw.
- On Gold the same copy works because i76.exe and i76shell import USER32 through u32x.dll, which maps. Nitro imports USER32
  directly: nitro.exe and NITSHELL both import ClipCursor, GetCursorPos and SetCursorPos, with no DirectInput.

**Fix (cursormap.c, commit faff357, proxy only).**
- Nitro-only: cm_window() also looks for `Interstate '76 Nitro Pack` when g_exe is Nitro. The Gold path is untouched.
- New switch I76_CURSOR_MAP_SHELL=aw|ar|stretched (unset = as before) gives the shell module's four slots their own map.
  NITSHELL's menus are dgVoodoo's [DirectX] picture, a 16:10 fit at x 568..2871 on the 3440x1440 panel. The plain
  stretched map put clicks up to 288 px off at the sides (read-back w20). nitro.exe's own slots keep I76_CURSOR_MAP's
  stretched map, for the in-mission Glide picture.
- Nitro settings: I76_CURSOR_MAP=1, I76_CURSOR_MAP_DGV=aw, I76_CURSOR_MAP_SHELL=aw.

**Proof (w21-cm, bce843c9, console, n 3 boots).**
- At the centre, the four corners (12 % in) and 25 % / 75 % across the 16:10 picture:
  - the OS pointer is where it was set;
  - the drawn pencil is within 3 px of it;
  - the point the shell acts on (its UI mouse mapped back to the picture) is within 4 px of the pencil.
- All three boots are identical. A pointer in the side bar clamps to the picture's edge, as on Gold.
- **Clicks** (screen captures in lab captures/nitro-port-20261021/cursor/click-e*.png): MELEE at (2252,936) opened MULTI
  MELEE / INSTANT MELEE; MULTI MELEE at (2064,1056) showed HOST / JOIN; JOIN at (2144,1140) highlighted JOIN and opened the
  transport row (MODEM / IPX / INTERNET / NULLMODEM / OTHER).
- **Gold smoke** be3c60e vs w21-cm: same line set (n 2 each), 0 crash lines.
- **Not tested:** the in-mission Esc menu on Nitro with the exe now mapped (stretched, as Gold's Esc menu).

**Harness note.** Run from a background job, the game never got the foreground. A side process (np_cursorside.py) did. A
click sent from that side process once hung in mouse_event for more than 60 s (not understood). The clicks above ran from a
separate job beside a long np-run boot.

**The Macs.** Not the same confinement, but a JOIN by a person there still needs this checked:
- The Mac app does not set I76_CURSOR_MAP, and its mouse object followed the real macOS pointer (NITRO-MAC s.4).
- DxWnd scales the mouse for a non-640x480 window.
- The clamp-and-write-back only bites when the shell sees raw coordinates past 639 / 479.

## Files

- i76-everywhere: `music-fix/nitro.c`, `music-fix/sites_nitro.h` (generated), `tools/nitro-sites/{gen_sites.py, uses.py,
  manual_sites.txt, extra_sites.txt, sites_nitro.csv}`; strlkproxy.c / simtick.c / cursormap.c hunks (NA / EF / site_is).
- lab: `tools\nitro-port\` (np-run.ps1, np_probe.py, np_shm_check.py, np_threads.py, np_physjump.py, np_jump_analyse.py,
  gold-smoke.ps1, compare_logs.py, fnwrap.py, srcedit.py, edits\, nitro-tick42.psd1), `builds\nitro-port-20261021\`, copies
  `exp-nitro-port`, `exp-nitro-port-gold`.
