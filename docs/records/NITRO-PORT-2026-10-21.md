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
| far clip | 5 pool immediates + read site | 6/6 | `far-clip: on (1200 m, pools x16, 6/6)`, 60 s P01 (n 2) | - | **yes**; fps not measured |
| terrain LOD A / B, vertex guard, hysteresis / freeze, terrain-tex, object LOD, shadow / road distances, road pool, clutter, mirror far, cam-ground, hull | 6 + 1 + 2 + ... (stubs relocated: vguard, hyst, road node) | all | every site patched, 0 refused; clutter 600-frame lines 605-873 us, 0 refused; road pool 0 refusals (n 3) | - | **yes**; churn census / T05 route fps not run |
| health %, label table | 0x40b7b8 / 0x40b6f0 (+3 stubs), 0x4ad465 (38 B, manual) | 2/2 | `fix-health-pct: on`, `fix-label-table: on`; telemetry health 100 at start (n 1) | - | **yes** (the % values not compared yet) |
| ZGLIDE TMU fix, Glide refresh 120 | Nitro ZGLIDE f28fe42b: +0x2c9a 75 26 (Gold +0x1a93 75 24) | 1/1 | `eb 26`, grSstWinOpen refresh 0 -> 120 Hz (n 1) | - | **yes** |
| aspect + HUD squeeze | 17 fov pushes (manual), hood fov, clamp, constant, 2 HUD calls | 22/22 | `aspect: D 2.389, 20/20`, `hud-squeeze 2/2` (n 1) | - | **yes** (picture not looked at) |
| CD music | WIN32.dll!mciSendCommandA / aux*; watchdog 0x42340d -> 0x418f5d | 1/1 | TOC 2..11 served; `MCI_PLAY ... run 2..2`, track 2 played (n 1) | - | **partial**: resume / gapless / true pause not exercised |
| joystick routing / tick joystick watch | WIN32.dll!joyGetPosEx / joyGetDevCapsA | - | slots hooked, watch on (n 1) | - | **yes** |
| cursor map | nitro.exe and NITSHELL.DLL USER32 slots | 4/4 + 4/4 | log only (n 1) | - | **partial**: pointer read-back not run |
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

## Files

- i76-everywhere: `music-fix/nitro.c`, `music-fix/sites_nitro.h` (generated), `tools/nitro-sites/{gen_sites.py, uses.py,
  manual_sites.txt, extra_sites.txt, sites_nitro.csv}`; strlkproxy.c / simtick.c / cursormap.c hunks (NA / EF / site_is).
- lab: `tools\nitro-port\` (np-run.ps1, np_probe.py, np_shm_check.py, np_threads.py, np_physjump.py, np_jump_analyse.py,
  gold-smoke.ps1, compare_logs.py, fnwrap.py, srcedit.py, edits\, nitro-tick42.psd1), `builds\nitro-port-20261021\`, copies
  `exp-nitro-port`, `exp-nitro-port-gold`.
