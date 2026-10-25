# Player-count spike: where the 8-player limit lives, and what 12 or 16 would take (2026-10-25)

Owner's question: *"What would a max game size / player count look like for multiplayer melee before we hit performance
issues? Could we double to 16 safely?"*

Design / RE spike (Fable), no implementation. Every address below was re-read in the pristine GOG binaries
(`<re-archive>\sandbox-gog\main\app\i76.exe` 9a232dcc, `i76shell.dll`, `nitro-full\app\nitro.exe`, `nitshell.dll`) with
capstone this session, or comes from a cited record / RE note. Nothing was run in a game. The one measurement quoted
for "many cars" is an existing lab capture (section 2).

## Verdict (short)

| question | answer | evidence |
|---|---|---|
| Where is "8"? | **Not in the exe.** The exe's player table has **16 slots** and every loop over it walks 16. The 8 is the host form's NO. DRIVERS clamp in the **shell** (`cmp ecx, 8` Gold, `cmp [max], 8` Nitro), which becomes the ANet session's maxPlayers (a **16-bit** field); joiners refuse when current == max. Plus three cosmetic 8s: the Tab scoreboard box (9 lines), the end-of-match NSCR.DAT (8 records), and the stock arenas' 8 spawn points. | section 1 |
| Practical ceiling with stock structures | **16 humans** (the table), **15** if one AI row is wanted. A 16-slot table also caps humans + AI cars at 16. | 1.1, 1.3 |
| Can we double to 16? | **Structurally yes, host-side only.** No wire format carries a player count, the maxPlayers field is 16 bits wide, and a **stock joiner's shell accepts any max the host announces** (it only compares current < max). What has to change: 1 byte in each shell (the clamp), the scoreboard line count (already done for AI arenas), and 8 more spawn points per arena (runtime injection, as the AI pool does). | 1.2, 3 |
| Performance at 16 | **Not the limit on the PC.** T05 runs 15 vehicles (14 AI mission cars + player) at 117-120 fps with 7-8 ms of work per frame (120 fps cap); 16 remote humans cost less than 14 AI (dead reckoning, no driver brain). Network at 16: ~1 KB/s up, ~15 KB/s down per player, ~150 packets/s into each pump. The Macs under Wine and the Deck are unmeasured with more than 4 cars. | section 2 |
| Effort | **2-3 lane-days** for 16 (patch + spawn injection + a 9-copy lab test of ANet's own cap), plus one LAN night with real joiners. +1 day if the standings file must list more than 8. | section 3 |
| Risks | ANet's internal per-session cap is **unverified** (the one real unknown; a cheap lab test answers it); spawn stalls at match start with 8 points; stock joiners see 8 scoreboard rows (cosmetic); NSCR.DAT must stay capped at 8 unless the shell array is relocated (overflow = corruption). No desync or save/replay exposure: multiplayer has no saves, no packet changes. Activision's lobby is dead anyway; we play IPX. | section 3 |
| Cheaper path to 16 cars | **Already there for 15:** `I76_AIMELEE_FILL=15` on the host gives humans + up to 7 AI (pool 7). 16 cars = pool 7 -> 8 (one constant) plus the same NO. DRIVERS clamp byte. | section 4 |

## 1. Where the 8-player limit lives

### 1.1 Gold (i76.exe 9a232dcc + i76shell.dll)

| site | address | structure / size | what it limits | kind |
|---|---|---|---|---|
| Player table | `0x541070`, **16 x 0x48** (end `0x5414f0`) | id, name[24], flags (team bits 16..18), car object, latency, kills, deaths, score | humans + AI rows (our AI build gives each AI car a row) | fixed array; 16 is the hard ceiling without relocating it |
| Table clear | `0x4540a7..0x4540b2`: `add eax,0x48; cmp eax,0x5414f0` | walks 16 | - | loop bound = table end (would move with a relocation) |
| Slot allocator `player_AddOrFind` | `0x4541b0`: two scans to `0x5414f0`, `cmp ecx,0x10` / `cmp esi,0x10` -> none free returns 0 | 16 | a 17th player gets no slot (the host's 'RE' handler calls it at `0x45691f` with no count test of its own) | same |
| Player count | `[0x541068]` (inc at `0x45432d`) | int | scoreboard rows, NSCR.DAT; **never compared with the max** | - |
| Max players from the setup block | `net_ApplySessionOptions` `0x452db0`: `[block+0x90] -> [0x540ff4]` (and `+0x94 -> [0x540ff8]`, the limit) | dword | **written and never read** in 0x401000-0x4c0000 (byte scan) | the exe does not enforce a maximum |
| Join prompt ring | `0x541528`, 32 x 12 B (reader `& 0x3f`, `0x4558c0`) | | queued CTRL-Y/N prompts, not players | fine for 16 |
| Scoreboard box (Tab) | `0x451ac0`: descriptor `{x 0x32, y 0x96, w 0x50, lines 9 at 0x451afb, ..., 8 at 0x451b1f}`; row loops `cmp ebx,0x10` / `cmp ebp,0x10` (0x451cd7, 0x451dd1) | 9 text lines = title + **8 rows**; the loops walk all 16 | rows beyond 8 are not drawn | **constant** (4-byte imm); our AI build already makes a 15-line box in AI arenas (AI-MELEE-RESPAWN s.3) |
| Standings rows `0x451f10` | loops `cmp ebx,0x10`, `cmp ebp,0x10` | 16 | - | fine |
| End-of-match file NSCR.DAT | `0x4524e0`: walks 16 (`cmp edi,0x10` 0x45277f) but writes while `cmp ebp,8; jb` (0x45278d) | **8 records** x 0x54 | the shell's standings screen reads them into a static **array of 8** at `0x100f5778` (`Standings_LoadScores` 0x1003fb40, unbounded count: a 9th record overwrites the team headers, shell/FIXES.md) | exe cap = constant; shell array = relocation. Patch both or neither |
| Host form NO. DRIVERS (Gold shell) | global `0x100f1f50`; default 4 (`0x1002832c`, `0x10028379`) or 2 (`0x1002af4e`); **"+" clamp `0x1002978a` `cmp ecx, 8; jge`** (bytes `83 f9 08`), "-" clamp `0x1002952c` `cmp ecx, 1; jle`; drawn with `%2.2d` | 2..8 | the session's maxPlayers | **one byte** |
| ANet session descriptor | Gold enum callback `0x10022d50`: `movsx ecx, word ptr [desc+0x11]` -> list record `+0x7c` (max), `+0x78` (current) | **16-bit** maxPlayers | the wire field holds up to 32767 | wire format already wide enough |
| Joiner's "Game full!" | `0x1002e547`: `cmp [rec+0x78],[rec+0x7c]; jne` -> `0x1002e557` push "Game full!"; also join state 3 (`0x1002e902`) and the 'JD' reason switch (`0x10030100`, case 4) | current == max | a **stock joiner accepts whatever max the host announces** | no joiner patch needed for a bigger max (to be tested) |
| "Max No Players Reached .... Player Space is full" | `0x10017360` (fopen/fwrite/rand), `cmp eax, 0x1f4` at `0x10017497` | 500 | the **single-player profile** directory, not multiplayer | ignore |
| Spawn points | mission ODEF label `spawn` -> table `0x53fd88`, **64 x 64 B** (`spawn_AddPoint` 0x450f90 `cmp edx,0x40`); regen `0x53ecb0`, 64 | every stock arena m01-m15 ships **8 spawn** + 1-3 regen points (census below) | a point is blocked within vehicle radius + 20 m; with 16 cars and 8 points the picker (`0x451540`) waits | table fine; the arenas need 8 more points (mission edit or runtime injection through the ODEF handler, as `aim_odef` injects the AI pool) |
| World records | table `0x542830`, 0x78 B, cleared to `0x54a030` (`0x457100`) = **256 records**, count `[0x54a25c]`; "world is full" from `entity_Create` 0x4572b0 | every object (cars, scenery, structures) | T15 (the busiest mission) uses 169 ODEF objects + terrain pieces; an arena + 16 cars is far below 256 | fine |
| Teams | flags bits 16..18 (3 bits), team count table `0x51f5d0` | 8 teams | - | fine |
| Packets | 'ST' 0x60 B body, 'SH' fire mask + 3 target ids, 'SC' structure bitmask, 'SP' id + point + .vcf; ids are ANet u16; ANet 1 unreliable packet max 255 B (len+6) | per-car packets, **no field counts players** | - | **no protocol change for 16** |
| Join-ring queue `0x541830` | 32 entries | | | fine |

Census of the stock arenas (`<re-archive>\data\fmt\bwd2x` over `miss16\m01..m15.msn`, ODEF class-1 records by label):
every one has **8 `spawn`** points; regen 1-3; other class-1 cars (parked scenery) 0-9. Busiest missions overall (class-1
cars / class 8-9 vehicles): T15 27 / 16, M01 19 / 0, M15 17 / 0, T06 17 / 0, M10 16 / 0, T05 15 / 2, T11 15 / 24.

### 1.2 Nitro (nitro.exe 28b8ae27 + nitshell.dll f804f50d)

| site | address | note |
|---|---|---|
| Player table | `0x53ed08`, **16 x 0x50**, count `0x53ed00` (nitro-net/README.md s.1) | same 16 ceiling |
| Max players | setup block `[0x24]` -> `net_ApplySessionOptions` `0x4486d0`; session record `+0x11` max players (host create `0x1002f3c0`) | same field; width not re-read for ANet 2 (same descriptor family) |
| NO. DRIVERS clamp | nitshell `0x10032f1f` **`cmp dword ptr [0x1017a070], 8; jae`** ("+"), `0x10032e3b..` ("-", floor 2) | one byte |
| Scoreboard | `0x449ef0` box, 8 rows (NITRO-MP-DESIGN "the scoreboard box size (8 rows ...)") | constant, as Gold |
| Packets | 'ST' 0x68 B, 'FL' per team (4), same two-letter dispatch; unknown types dropped | no player count on the wire |

### 1.3 So the ceiling is

- **16** = the exe's player table, on both games. Beyond 16 means relocating a 16 x 0x48 (0x50) table that about 60
  functions index by absolute address (every `cmp eax,0x5414f0` loop, `0x4541b0`, the scoreboard, NSCR, the mirror,
  our proxy's aimelee.c / mpfill.c, which hard-code `0x541070 + k*0x48`). That is a different project (days, and every
  proxy file), not a patch.
- Below 16 nothing in the exe needs to change. The limit is three bytes of shell (`83 f9 08` -> `83 f9 10` in Gold,
  the `8` in nitshell) and two cosmetic constants.

## 2. Performance: what the sim and renderer already handle

| measure | value | source |
|---|---|---|
| Most vehicles in one stock mission | **T15: 27 class-1 cars + 16 class 8/9 vehicles** (169 ODEF objects); T11 15 + 24 | census above |
| 15 vehicles live, PC, 120 fps cap | **T05 (14 AI mission cars + player): 117-120 fps, work 5.4-9.0 ms avg per frame, 11-32 ms max** (n 12 ten-second windows, headless lab copy, tick 41.667) | `<lab>\captures\airespawn-20261020\sp-crash\desc-t41.667-base-1-1.log` ("mission cars alive 14 dead 0") |
| AI-fill arenas | Hope Springs (6 AI) + 2 humans, 7-car pool in every stock arena: 271 pooled boots, 30 respawns, sync median 0.00 m; fps not logged in those runs (the fps lock was held by another lane) | AI-MELEE-RESPAWN-2026-10-20 s.4, s.5.1 |
| 4 humans + AI on the LAN | PC host + two Macs + laptop, join / leave / migrate, 0 crashes; fps on the Macs **not measured** | LAN-MATRIX-2026-10-20 |
| Network, measured | 2 players: **~10 packets/s and ~1.0 KB/s up per player** (Gold host 1420 packets / 142 KB in 140 s; Nitro 1814 / 181 KB in 201 s), each player receives (players - 1) x that | INTERNET-RELAY-SPIKE-2026-10-25 s.4 |
| 'ST' rate | send interval = mean latency / 3, clamped **0.2-0.5 s** (2-5 'ST'/s per car); 'XX' ping 2/s from the host; our 'AT' 10/s (2 cars per 208 B packet) | subsystems/network.md, AI-MELEE-RESPAWN |
| Per-frame cost model | the AI driver block (0xa9d8 B) runs for every vehicle each frame (ARCHITECTURE.md); a **remote human's car is mirrored and dead-reckoned (0x464890)**, no brain | ARCHITECTURE.md, network.md |

Extrapolation to 16 (not measured):

- **Sim + render, PC:** 16 cars is one more than T05's 15, and remote humans are cheaper than AI. Expect the same
  117-120 fps at the cap on the PC; at the owner's 24 fps sim tick the budget is 41.7 ms against 7-9 ms of work.
  8 humans + 8 AI is the T05 case almost exactly. The Macs (Wine) and the Deck are the unknown: measure them at 8 AI
  before promising 16 there.
- **Network, 16 players:** each player still sends ~1 KB/s (~10 packets/s); each receives ~15 KB/s and ~150
  packets/s; a relay forwards ~240 KB/s (2 Mbit/s). LAN: nothing. Internet: a 16-player room needs ~120 kbit/s down per
  player, any home line. The pump (`net_Pump` 0x4532c0) drains `dpReceive` until empty each frame with a 0x200 B
  buffer; 150 packets/s is ~6 per frame at 24 fps, each a short handler ('ST' -> mirror). Not a cost.
- **Host's per-player work:** the host answers 'RE' (auto-accept or prompt), re-validates each joiner's .vcf once
  (NVCL exchange + checksum), spawns on 'SR', sends 'XX' pings (2/s each), and in our build runs the AI brains and
  the 'AT' stream (10/s, 2 cars per packet: 8 AI = 4 packets per tick = 40 packets/s). At 16 the host's extra load
  over 8 is ~16 pings/s and the validation of 8 more .vcf files at join. Nothing per frame scales with humans except
  the mirror applies.

## 3. What 12 or 16 would take

| step | change | kind | effort |
|---|---|---|---|
| 1. Raise NO. DRIVERS to 16 | Gold shell `0x1002978a` `83 f9 08` -> `83 f9 10`; nitshell `0x10032f1f` imm `8` -> `0x10`. Deck Kit / Mac Kit `make-deck-patches.py` style, or a proxy write at load | 1 byte each, host only | 0.25 day |
| 2. Scoreboard lines | `0x451afb` 9 -> 17 (box height) on every machine that should see all rows; stock joiners see the top 8 | 4-byte imm (proxy already does 15 for AI arenas) | 0.25 day |
| 3. Spawn points | inject 8 more `spawn` records per arena at ODEF time (the `aim_odef` path at `0x4b45bf` already injects 7 pool cars; `spawn_AddPoint` takes 64) placed by the AI-MELEE-M1 rule (road centre, >= 80 m from other points); or ship edited arenas (then the mission CRC changes and stock joiners cannot join) | proxy code, host + joiners must agree on the point list ('SP' carries a point index -> **every machine must inject the same list**) | 0.5-1 day |
| 4. ANet's own cap | unverified: ANet may clamp maxPlayers or the session table. Test: one PC, host NO. DRIVERS 16, 9+ headless joiners (the lab already runs 3 copies with instance letters; 9 need 9 letters / ports) | lab run | 0.5 day |
| 5. NSCR.DAT beyond 8 | leave the exe's `cmp ebp,8` (top 8 standings) **or** patch it and relocate the shell's 8 x 0x54 array at `0x100f5778` (+ the team headers that follow it) | constant + relocation | 0 or +1 day |
| 6. LAN night | 9+ real joiners (we have 5 machines; two copies per PC for the rest) | owner's time | 1 evening |

Total: **2-3 lane-days** plus the evening. 12 costs the same as 16 (same sites, smaller spawn injection).

Risks:

- **ANet session cap (the real unknown).** Everything else is read; this one is not. If ANet refuses a 9th player the
  fix is inside anet2 / anetdll (unpacked exports exist for ANet 2), which is harder. Run step 4 first.
- **Spawn stalls.** With 8 points and 16 cars spawning at once, the picker finds every point blocked (radius + 20 m)
  and waits; the 5 s respawn delay then serialises spawns. Step 3 removes it; without step 3 a 16-player start is a
  queue.
- **Joiner compatibility is kept, not lost.** The join check is current < max from the host's descriptor; no
  version string or CRC changes. A stock joiner in a 16 game sees 8 scoreboard rows and top-8 standings (cosmetic)
  and, with step 3 as injection, **must run our proxy for the spawn list** (otherwise its 'SP' point index 8..15 has no
  point). Shipping edited arena files instead keeps stock joiners out by the CRC check. Either way "every peer must run
  our build" is true only for the spawn list, not for the wire.
- **Activision lobby** (`dpSetGameServer`, `internet.lst`) is dead; nothing lost. IPXWrapper / the relay carry any count.
- **Desync / saves / replays.** No packet changes; the 'ST' interval adapts to latency per peer. Multiplayer has no
  save or replay files; NSCR.DAT and victory.rec (already broken: shell/FIXES.md) are the only outputs.
- **Our own proxy** hard-codes 16 (`aimelee.c`, `mpfill.c` loops `k < 16`, `I76_AIMELEE_FILL` 1..15): fine up to 16;
  the AI pool (7) + 16 humans would want 23 rows, so AI fill goes to 0 as humans approach 16 (fill = NO. DRIVERS -
  humans, so that is the design anyway).

## 4. The cheaper alternative: 8 humans + AI fill to 16 cars

- **Today, host-side env only:** `I76_AIMELEE_FILL=15` gives N = 15 combatants: 8 humans + 7 AI (the pool is 7 cars
  per arena, `aim_odef`), scoreboard box 15 lines in AI arenas (AI-MELEE-RESPAWN s.3). That is 15 cars, which is the
  T05 load the PC runs at 117-120 fps. A human leaving brings an AI back; joining parks one.
- **16 cars** = pool 7 -> 8 (one constant in `aimelee.c` `aim_odef`, 8 parking spots), plus the NO. DRIVERS clamp byte if
  the host form rather than the env should set it (fill N = NO. DRIVERS in stock arenas). Rows: 8 + 8 = 16 = the table,
  so a 9th human cannot join (ANet refuses at max 8, or the fill drops an AI if the max is raised).
- What it looks like: the host's NO. DRIVERS (or env) sets the car count; humans take AI places as they join; the
  Tab board lists humans and AI together with kills / deaths / score; AI respawn in 5 s like humans; team sums include
  AI; MAX SCORE can be won by an AI. Measured on Gold (AI-MELEE-RESPAWN: 21 respawns, 271 pooled boots, 0 crashes) and
  ported to Nitro (NITRO-MP-DESIGN 0.5.x). The difficulty knob is `--ai-skill` / the menu's Difficulty Level.
- Not covered by it: 9+ humans. For that only section 3 helps, and the first thing to spend on is step 4.

## 5. Method and files

- Disassembly: capstone 5.0.7 over the pristine GOG binaries, PE sections mapped by hand (`/tmp/pcs/pcsdis.py`,
  session scratch, not kept); `xref` = byte scan for the absolute address, the holding instruction decoded.
- Shell string sites from `<re-archive>\shell\ghidra\export\strings_xrefs.csv` ("Game full!" 0x1002e487 / 0x1002fcd8 /
  0x1002e487; "Max No Players Reached" 0x10017360) and `imports_xrefs.csv` (dpOpen sites 0x1002e612, 0x1002f14e,
  0x1002f4ad; dpEnumSessions callback 0x10022d50).
- Census: `<re-archive>\data\fmt\bwd2x.decode` over `sandbox-gog\main\app\miss16\*.msn`, `chunks(doc, "OBJ", "ODEF")`,
  `class_id` and `label`.
- Prior records used: `docs/records/AI-MELEE-RESPAWN-2026-10-20.md` (s.3 slot limit), `NITRO-MP-DESIGN-2026-10-21.md`,
  `INTERNET-RELAY-SPIKE-2026-10-25.md` (traffic), `LAN-MATRIX-2026-10-20.md`, `<re-archive>\subsystems\network.md`,
  `<re-archive>\nitro-net\README.md`, `<re-archive>\shell\FIXES.md`, `<re-archive>\functions\00454090.md`, `<re-archive>\ARCHITECTURE.md`.
- Not done: no game was booted; no Mac / Deck fps with 8+ cars; ANet's internal cap not read (anet2 unpacked export
  exists at `<re-archive>\nitro-net\ghidra\export-anet2-unpacked`, Gold's anetdll has no export).
