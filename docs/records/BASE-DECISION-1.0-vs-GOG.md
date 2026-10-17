# Base decision: retail 1.0 or the GOG / Gold exe for the modern port (2026-10-17)

Lane `base-decision`. Paper decision only: no game, no VM, no rebuild. Inputs are the records written earlier today
plus one new static count (section 4.1). Nothing in any game folder was read or written.

**The question.** Should the modern port be built on retail 1.0 (`6cc509ad`, March 1997, the gold standard's exe) or
on the GOG / Gold exe (`9a232dcc`, Gold 1.2, February 1998; our driver runs its AiO descendant `6319abf7`), or on a
hybrid?

## Recommendation

**Hybrid: keep the Gold / GOG exe as the code base, and play it with retail 1.0's rules.** Concretely:

1. **Code base: the GOG Gold exe**, as now. The proxy (`Strlkup.dll`), the whole-sim tick, the renderers and every
   tool stay where they are.
2. **Simulation reference: retail 1.0 with simulation physics** (unchanged: the gold standard). The port is judged
   against it, not against Gold's defaults.
3. **A short "retail rules" set on top of Gold**, each switchable for A/B (section 5): difficulty byte 1, the
   retail health-% formula, the 1-byte `ai_RecordDamageEvent` revert, retail turret slew and heat-seeker cone, and
   (optional, data) the few Gold retunes the owner wants undone.
4. **No 1.0 rebuild now.** Revisit only on the trigger in section 6.

### Why, in one paragraph per reason

- **The physics is the same code.** `physics_StepVehicle`, `simclock_Update`, `simclock_StepperBegin`, CheckImpact,
  the attitude solver, suspension, wheel creation, engine curves, ground height and body-pair collision are the same
  algorithm with the same constants in retail and Gold (EXE-DIFF-MAP s.3, read side by side in disassembly; same 75
  float constants in the call tree to depth 2). The only Gold-only physics code is the both-front-wheels-damaged steer
  pull and a collision-arm guard; neither acts in the air (EXE-DIFF-MAP s.3, RETAIL-HANDLING-DIFF s.6). No 1997 patch
  changed driving physics either (I76-VERSIONS short answer 2). A 1.0 base buys no physics fidelity that a Gold base
  lacks.
- **Measured, not only read.** Our Gold-lineage exe with the stock stepper at a 30 ms step is indistinguishable from
  retail 1.0 at the P166 on every T13 combat metric (n 8 vs 10, all p >= 0.07; AI-DAMAGE-BALANCE s.0 item 4). Gold
  Arcade = retail Arcade on the measured handling metrics (ARCADE-PHYSICS summary: same five code sites, K 22.7 vs
  23.5 at 12 m/s, p 0.4). What made our driver differ from retail was **our timing scheme** (best-wide: -38 % damage
  taken, -58 % AI rounds, p 0.012 / 0.004; AI-DAMAGE-BALANCE item 6), not the exe.
- **What does differ is short and known** (EXE-DIFF-MAP s.5-6, s.10): Gold's difficulty multiplier (x2.0 / x1.0 /
  x0.75; a fresh Gold install sits at byte 0 = double player damage; retail = byte 1), Gold's broken
  `object_HealthFraction`, turret slew 1.7 vs 1.5 rad/s (aircraft 6.8 vs 6.0) and its hp factor, heat-seeker cone
  0.94 vs 0.84, an AI behaviour stack vs a single slot, a rewritten `weapon_SpawnProjectile` (particle angles,
  ordnance switch). Each of the first five is a config byte or a few constants on the Gold exe. The last two are
  open (section 7).
- **Gold's data retune is the larger balance gap, and it is data.** Gold CD at Champ (x1.0) took +38 % damage per
  minute against retail at the same P166 (n 6 vs 10, p 0.007), and step length does not explain it (retail P133 vs
  P166 showed no difference); the exe and its data, including different T13 loadouts, remain as the candidates
  (AI-DAMAGE-BALANCE item 3, an inference). The data changes are listed field by field in I76-VERSIONS s.2.6: bus
  mass 9,000 -> 12,730, Gas blast 500 -> 100, armour / chassis on a few variants, weapons swapped on 19 configs, 56
  configs pointing at new vdfs. Weapon and ordnance numbers themselves are identical. A hybrid can patch the ones that
  matter in `I76.ZFS` with the existing `data\mod` tools (zfspatch.py) instead of changing exe.
- **The whole-sim tick removes the frame-rate argument for 1.0.** The one thing retail on a P166 has that our driver
  lacks is "everything runs once per ~30 ms frame". The tick (WHOLE-SIM-TICK-2026-10-17.md, `I76_SIM_TICK_MS`) gives
  the Gold exe exactly that at the owner's 33.3 ms baseline (PHYSICS-STEP-STUDY-DESIGN amendment; DEV-GAME-CLUB-I76:
  15 fps design, everything in the same loop), and retires the per-frame patch pile (FRAMERATE_FIXES' 48 sites,
  COLL_WINDOW, INPUT_LATCH, the AI grids, ENGINE_DT_FIX, REF_FPS). It is written against Gold addresses (section 4.1).
- **Distribution.** The project ships no game files; users bring their own copy, and the GOG *Arsenal / Gold* release
  is the tested and only sold source (THIRD-PARTY.md, SCOPE-AND-LEGITIMACY.md). GOG has sold it since 2010-02-18;
  there is no Steam release (I76-VERSIONS s.1, 4-5). Retail 1.0 exists only on 1997 discs (we use an archive.org
  ISO for the emulator rig). The official RTPatch only goes forward, 1.0 -> 1.2; nothing turns a GOG install into
  1.0. A 1.0-based port would therefore be unusable by almost every user who legitimately owns the game.
- **The features the port exists for need Gold.** Retail draws software only (320x240 / 480x360 / 640x480), has no
  D3D or Glide, and clamps the far distance to [100, 1000] m with a 1500 viewport cap; our 1,200-1,800 m far clips
  depend on Gold's raised cap (EXE-DIFF-MAP s.7). Retail imports no `Strlkup.dll`, so **our proxy's injection point
  does not exist in 1.0** (EXE-DIFF-MAP s.1). Retail asks for disc 2 at mission load (WHAT-IS-STOCK, via EXE-DIFF-MAP
  s.7). Nitro Pack is Gold's engine five weeks later (1,781 of 1,997 pairs equal once normalised; EXE-DIFF-MAP s.8),
  so a Gold base keeps Nitro reachable; a 1.0 base does not.

## 1. What each base gives

| | retail 1.0 (`6cc509ad`) | Gold / GOG (`9a232dcc`, AiO `60abf7bc`, ours `6319abf7`) | source |
|---|---|---|---|
| vehicle physics | the reference | same code and constants | EXE-DIFF-MAP s.3 |
| clock and stepper | float32 seconds, `floor(sim_dt x 20) + 1` substeps | same; AiO masks the tick (no uptime quantisation) | EXE-DIFF-MAP s.3, s.9 |
| Arcade Phys. | five sites | the same five sites, same arithmetic | EXE-DIFF-MAP s.4, ARCADE-PHYSICS |
| difficulty | none (= Gold byte 1) | x2.0 / x1.0 / x0.75, default byte 0 | EXE-DIFF-MAP s.5 |
| health % | banded formula, wheels count as core | broken (raw 0..1 ratio); `I76_FIX_HEALTH_PCT=1` is neither | EXE-DIFF-MAP s.5 |
| turret slew / heat cone | 1.5 rad/s x hp, cos 0.84 | 1.7 rad/s x (0.75 + 0.25 hp), cos 0.94 | EXE-DIFF-MAP s.6 |
| data | 1.0 / 1.06 ZFS | retuned (bus, Gas, armour, loadouts, 56 vdf pointers) | I76-VERSIONS s.2.6 |
| renderers | software only, 640x480 max, far clip <= 1-1.5 km | D3D (DX5), Glide, Rendition, PowerVR, software; far cap 100,000 | EXE-DIFF-MAP s.7 |
| options file | `I76PLYR.DEF` 88 bytes | 96 bytes (+ difficulty at +0x5c, 2 detail bytes) | EXE-DIFF-MAP s.7; never cross-copy (EMU-OWNER-LOGGING) |
| proxy host | no `Strlkup` import | `Strlkup.dll` (our proxy) | EXE-DIFF-MAP s.1 |
| force feedback | Immersion `iforce.dll` | `i7_sfrce` path | EXE-DIFF-MAP s.7 |
| bug fixes after 1.0 | none (1.05 fixed MP bugs, Mission 12 save crash, landing-wreck guard) | Gold is the end of that line; AiO adds overrun fixes, `entity_Register` 256 bound | I76-VERSIONS s.2.2; FIX-INVENTORY s.2 |
| how a user gets it | 1997 disc only | GOG, sold today | THIRD-PARTY.md, I76-VERSIONS s.1 |
| our tooling | addrmap-retail, the emulator rig | everything: proxy, i76-map symbols, FORMATS.md parsers, trainer, tick | FIX-INVENTORY s.1; data\FORMATS.md (written for `9a232dcc`) |

## 2. Saves

- **Not measured** whether a retail TRIP save loads in Gold or the reverse. Nobody has tried it, and this lane did
  not.
- What is known points against mixing them: the options file differs in size (88 vs 96 bytes; a Gold file in a
  retail folder turns Arcade on, EMU-OWNER-LOGGING), and Gold's VCF / VDF tables were
  renumbered and repointed (I76-VERSIONS s.2.6), so a car stored by config id may resolve to a different car.
- Our save tooling (save editor, FORMATS.md, leg-a / leg-b trip tests) is all on Gold. A Gold base keeps every
  existing save and the owner's bookmarks; a 1.0 base would start saves from scratch.

## 3. Our patches and which exe they assume

- **All of them assume Gold addresses.** FIX-INVENTORY s.1-5: the driver is the Gold link (1998-02-19) + AiO's 45
  clusters + our import rename + the proxy's runtime hooks; i76-map's symbol table and `data\FORMATS.md` are for
  `9a232dcc`.
- **The physics itself is untouched by any patch** (FIX-INVENTORY summary 2): we change physics only through time
  (clock, step length, dt). That is exactly the part the tick replaces.
- **AiO-only changes that 1.0 lacks** (FIX-INVENTORY s.2, EXE-DIFF-MAP s.9): masked clock, terrain bounds checks,
  `entity_Register` stops at 256 (both originals overflow), CD prompt skip, CPU-probe skip (needed on NT), heap and
  D3D cache fixes. A 1.0 base would need these re-done.
- **AiO-only change that differs from both originals:** `ai_RecordDamageEvent` reads projectile +0x10 instead of
  +0x44. A 1-byte revert at 0x415817 restores 1997 and 1998 behaviour (EXE-DIFF-MAP s.10 item 3).

## 4. What a 1.0 rebuild would cost, if chosen later

### 4.1 The proxy's address surface (new count, this lane)

Script: scratch `addrcov.py`, over `music-fix/*.c` at i76-everywhere HEAD, against lab
`emu\tools\memtrace\exe_diff_map.json` (2,217 Gold functions, 1,334 with a retail match). Code addresses only
(0x401000-0x4bc000); data addresses (0x5xxxxx / 0x6xxxxx globals, roughly 170 more distinct literals) not mapped.

| source | distinct code addresses | function entries | sites inside a function | containing function has a retail match |
|---|---|---|---|---|
| `strlkproxy.c` | 539 | 202 | 337 | 411 (76 %) |
| `simtick.c` (the tick) | 42 | 22 | 20 | 39 (93 %) |
| `replay.c` | 6 | 3 | 3 | 6 |
| `padmenu.c` | 1 | 1 | 0 | 0 |

- A function match gives the retail entry address only. **Every in-function site has to be found again by hand:**
  retail is VC4.2 and Gold VC5, and their instruction streams never match byte for byte (Version Tracking paired 5.8
  %; EXE-DIFF-MAP s.2). That is about 360 hand-located call sites and patch points, plus the ~170 globals, plus 128
  sites whose containing function has no retail match (mostly renderer code that 1.0 does not have).
- Struct offsets are the same in the physics (same offsets through 1.083 and in Gold's physics tree, I76-VERSIONS
  s.3), so entity field reads mostly carry over.

### 4.2 The rest of a 1.0 rebuild

1. **A new injection point.** 1.0 imports no `Strlkup.dll`; the proxy would need another host (a renamed import such
   as `WINMM` / `DDRAW`, or a loader). Rework of the proxy's startup and the music path.
2. **The renderer.** Software only, 640x480, far clip <= 1-1.5 km. Wide / high-res, dgVoodoo / Glide, the far-clip
   work and the HD-texture plans would all need a new renderer path or a DirectDraw-level wrapper. This is the
   largest item and has no estimate; it is a project of its own.
3. **Re-doing AiO's fixes** (section 3) and the CD-2 check.
4. **Tooling:** a new symbol table (start: `addrmap-retail.md` and the 1,334 matched pairs), the trainer / logger
   offsets, FORMATS.md checks against the 1.0 ZFS and DEF, the save editor, the deck scripts.
5. **Distribution:** users cannot obtain 1.0 legally today, so the port would need a 1.2 -> 1.0 downgrade path
   that does not exist and would mean shipping or diffing Activision binaries (ruled out by THIRD-PARTY.md).
6. **Validation:** every proxy feature re-tested on the new exe (the proxy-run harness and the trip tests assume
   Gold).

Order of magnitude (estimate, not measured): items 1, 3, 4 and the 4.1 re-location are weeks of RE; item 2 is
open-ended; item 5 has no solution inside the project's rules. Against that, the hybrid's retail-rules set is about
ten bytes / constants plus one hook value (section 5).

## 5. The hybrid's "retail rules" set (proposals; nothing changed here)

Each as a proxy switch or config value, default chosen by A/B against the retail reference, old behaviour kept for
A/B. Sources: EXE-DIFF-MAP s.10, I76-VERSIONS s.2.6.

| rule | how | kind |
|---|---|---|
| difficulty = retail | `I76PLYR.DEF` +0x5c = 1 (x1.0) | config |
| health % = retail | banded formula over 7 core parts as a new `I76_FIX_HEALTH_PCT` value (e.g. `=3`) | proxy hook (exists) |
| AI damage stamp | 0x415817 `0x10` -> `0x44` | 1 byte |
| turret slew | 1.7 -> 1.5, 6.8 -> 6.0, hp factor (0.75 + 0.25 r) -> r | constants |
| heat-seeker cone | 0.94 -> 0.84 (and the Gold class-1 target guard: keep or drop by A/B) | constant |
| Arcade off | Arcade Phys. unticked (the gold standard is simulation) | config |
| data retunes | bus mass, Gas blast, armour / loadouts only where the owner wants 1997 balance back | `I76.ZFS` field patch (data\mod) |
| timing | whole-sim tick at 33.3 ms | proxy (`I76_SIM_TICK_MS`, being built) |
| Gold-only steer pull, arm guard | leave (no in-air effect; a damaged-car feel item at most) | none |

## 6. When to revisit

Rebuild on 1.0 only if, after the tick exists and the retail-rules set is on, a **measured** difference against the
retail reference remains that (a) the owner can feel, (b) survives an A/A of the same size, and (c) traces to Gold
code outside this list (the AI behaviour stack and `weapon_SpawnProjectile` are the two candidates). Even then the
cheaper fix is to port that one function's behaviour onto Gold, not the port onto 1.0.

## 7. Open, not done here

- **AI behaviour stack** (Gold ai+0xa874 indexed by ai+0xa93c vs retail's single slot): what it changes in behaviour
  was not traced (EXE-DIFF-MAP s.6). Measured indirectly: our Gold-lineage exe at 30 ms = retail on T13 (n 8 vs 10),
  which bounds its effect in that mission only.
- **`weapon_SpawnProjectile`** rewrite and the unmatched Gold ordnance step functions: retail counterparts not
  located (EXE-DIFF-MAP s.6).
- **Gold 1.2 = GOG `9a232dcc`** is not byte-verified against an applied RTPatch (I76-VERSIONS s.7 step 1).
- **Retail / Gold save interchange** untested (section 2).
- **Data-retune share of the +38 %** Gold-vs-retail damage gap is inferred, not tested (AI-DAMAGE-BALANCE item 3). A
  Gold-exe run with retail's T13 loadouts patched in would split exe from data; deferred with the other AI runs until
  the tick exists.
