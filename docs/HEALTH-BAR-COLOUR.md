# Target health bar colour under I76_FIX_HEALTH_PCT: the fixed value forgot the armour

**2026-10-02, static trace only** (i76-map ghidra exports of the pristine i76.exe, md5 9a232dcc; nothing was run). Field
report, sandbox run with every opt-in switch on including `I76_FIX_HEALTH_PCT=1`: *"when enemy health is going down and
the bar is changing colors, the enemy health bar switches to WRONG colors as they take damage. The actual damage count
(number) seems fine. Depends on the AI car: one was actually correct but mostly not; maybe some offset thing?"*

## Result in one paragraph

The target bar's colour and length are **pure functions of `object_HealthFraction` 0x40b450** (thresholds 33.3 / 66.7 /
== 100, length 30 x sqrt(v/100) px; no compensation, no second colour source). The 2026-09-27 fix multiplied the stock
function's component branch by 100, which turned "worst core component ratio, unscaled" into "worst core component ratio
in percent" - and that value **ignores the armour**. A car worn down to 30% armour reads 28 + 72 x 0.3 = 49.6 (yellow)
until its engine takes its first scratch, then 100 x 0.98 = 98 (green, nearly full): the bar got longer and greener as the
car was shot. Stock shows the same car as a 3-pixel red stub (0.98 "percent"), which looks like "nearly dead" and is at
least not rising. A car whose engine, suspension and brakes were never touched takes the armour branch in every build
and reads correctly - that is the "one was actually correct". The fix is now `health = min(28 + 72 x r, 100 x c)`:
monotone in every kind of damage, equal to stock while the core is intact, and it reproduces both measured results of
the x100 version (99% engine: no smoke; 50% engine: smoke) because those runs had near-full armour. Not yet run live.

## 1. The trace

### 1.1 The one HUD consumer: renderer_DrawTargetBrackets 0x45af10

Called from both scene drawers (software 0x401cc0, hardware 0x401fa0; `i76-map/subsystems/renderer.md` lines 33-34) with
`(camera, mirror)`. For the player's radar target (`0x4613f0(player root)`) it projects the aim point, draws the four
corner bitmaps (0x45b087..0x45b1d8) and then the health bar. Disassembly (`i76-map/tools/disasm.py 0x45af10`):

| site | instruction | meaning |
|---|---|---|
| 0x45b1e5 | `call 0x40b450` | **the only call** that feeds the bar; `fst [slot]` at 0x45b1ea |
| 0x45b1ee | `fcomp [0x4bdfdc]` (100.0) | v > 100 -> v = 100 (0x45b1fe) |
| 0x45b20a | `fcomp [0x4be02c]` (0.1) | v < 0.1 -> v = 0.1 (0x45b21d, `0x3dcccccd`) |
| 0x45b229 | `fcomp [0x4bdfdc]` | v == 100 -> colour index 3 (0x45b238) |
| 0x45b243 | `fcomp [0x4be030]` (33.333) | v <= 33.3 -> index 0 |
| 0x45b252..0x45b273 | loop, step `[0x4be034]` = -33.333 | v > 66.7 -> index 2, else index 1 (at most 2 steps) |
| 0x45b27e | `fmul [0x4be038]` (0.01), `fsqrt` | sqrt(v / 100) |
| 0x45b291 | software: `fmul [0x4be040]` (-15), `fsub [0x4be048]` (0.5), `_ftol` | half-width = round(15 sqrt(v/100)); bar x = 15 - h .. 15 + h in the 30 x 5 bitmap 0x54a378 (created 0x459550: 0x1e x 5) |
| 0x45b2e1..0x45b36e | software: `0x474ea0` fill 0xff, rect in colour 0x54a450 (= 0xfe, the outline, set at 0x459550), inner rect in colour `0x54a440[index]` | the bitmap is rebuilt only when x-extent or colour changes (0x45b2bb..0x45b2db cache in 0x4f70fc / 0x4f7100 / 0x4f67f0) |
| 0x45b3df | hardware: `fmul [0x4be050]` (-30), `fsubr [0x4be048]`, `_ftol` | width w = round(30 sqrt(v/100)) |
| 0x45b419 / 0x45b438 | hardware: `0x45b8c0` screen rects (x - w/2, y - 5, w - 1, 4) in 0xfe, then (x - w/2 + 1, y - 4, w - 2, 3) in `0x54a440[index]` | this is the path the sandbox uses (dgVoodoo / plugin renderer) |

**The colour table** `0x54a440[4]` is BSS, filled once by the HUD initialiser 0x459910 (0x459c7f..0x459ce3) through the
palette matcher 0x479600 (r, g, b floats 0..1 -> nearest palette index via 0x4796a0):

| index | condition | (r, g, b) pushed | colour |
|---|---|---|---|
| 0 | v <= 33.3 | (0.82, 0.00, 0.16) | red |
| 1 | 33.3 < v <= 66.7 | (0.80, 0.78, 0.13) | yellow |
| 2 | 66.7 < v < 100 | (0.32, 0.61, 0.32) | green |
| 3 | v == 100 | (1, 1, 1) | white |

So there is nothing in the bracket code that could compensate for a 0..1 value, nothing tuned to the buggy range, and no
per-side colour source. **Colour = f(v), length = g(v), and v comes from 0x40b450 and nowhere else.** The task's three
alternative hypotheses (a < 1 heuristic, thresholds tuned to the bug, a separate per-side colour) are all ruled out by
the listing above.

No number is drawn here: the function draws four bitmaps, one bar (bitmap or two rects) and, off-screen, an edge arrow
(0x54a2b0). Per the call graph the only callers of 0x40b450 are 0x45af10, the network state packers 0x4644d0 / 0x46cc50,
`entity_DamageAndKill` 0x463a80, 0x4641e0, `fsm_HpLesser` 0x40b7d0 and `ai_ShouldFleeWhenHurt` 0x417060 - no text
drawer. Whatever "damage count (number)" the player watched is therefore **not derived from this value**; the live plan
below asks which readout it was (candidates: the telemetry's `health_pct`, which is the *player's own* car, or a cockpit
readout of the entity's own armour / component fields). "Depends on the AI car ... some offset thing" is not an offset:
it is which branch of 0x40b450 the car's damage history put it on (section 2).

### 1.2 The value: object_HealthFraction 0x40b450, vehicle case (type 1, 0x40b4e8)

From `i76-map/subsystems/damage.md` ("Damage smoke") and the disassembly:

- engine / suspension / brakes ratios from entity +0x3c4 / +0x3c8 / +0x3cc (0x40b50f..0x40b5d8); a ratio < 0.02 counts
  as dead (ebx), otherwise it is clamped to 0..1 and the minimum is kept in st0 (c);
- 0x40b5da: if c >= 0.9999 (`0x4bc62c`) and none dead -> 0x40b5f3 pops c and the **side loop** 0x40b5f5..0x40b6a5 takes
  r = min over the four sides of min(armour +0x138/+0x158, chassis +0x148/+0x168), clamped 0..1 (locals [esp+0xc] and
  [esp+0x10], FLT_MAX from the prologue 0x40b45c / 0x40b467); 0x40b6ba..0x40b6dc: st0 = 72 r + 28 (`0x4bc630`,
  `0x4bc634`), `jmp short 0x40b6f0`;
- otherwise 0x40b6de: `jmp [ebx*4 + 0x40b7b8]`, a 4-entry table that is **all 0x40b6f0** - the clamp - with c still in
  st0. That is the stock bug: 0.99 "percent" for a 99% engine. (All three dead leaves c = FLT_MAX, clamped to 100: a
  dead core reads full.)
- 0x40b6f0..0x40b714: clamp to [0, 100] (`0x4bc620` / `0x4bc61c`), epilogue, `ret` at 0x40b720.

The 2026-09-27 fix (`music-fix/strlkproxy.c`, "STOCK BUG: HEALTH PERCENT") repointed the four table entries at a stub
`fmul [0x4bc620]; jmp 0x40b6f0`. Correct for the smoke case it was built on (`captures/014-framerate/hfrac_*.json`:
99% engine, chassis 92-100% per side), wrong as a health readout: once any core component is below 99.99% the value is
100 c and **r is never computed**.

### 1.3 The same thresholds elsewhere

The network packers 0x4644d0 (call at 0x46467b) and 0x46cc50 classify the same value with the same constants (<= 33.33
-> bit 0x40000000, <= 66.67 -> 0x80000000, else 0xc0000000), so a remote player's brackets follow it too. The other
consumers (smoke < 75 / 60 / 40, `entity_DamageAndKill`'s < 33 at 0x463db4, AI flee below 30 + 17 x skill, script
`hpLesser`) all want a monotone percent as well; none of them wants "forget the armour".

## 2. Why the colours looked wrong, and why one car looked right

v for a car with worst side ratio r and worst live core ratio c, and the bar it draws (colour / hardware width):

| r | c | stock | x100 fix (now `=2`) | min fix (`=1`) |
|---|---|---|---|---|
| 1.0 | 1.0 | 100 white 30 px | 100 white 30 px | 100 white 30 px |
| 0.5 | 1.0 | 64 yellow 24 px | 64 yellow 24 px | 64 yellow 24 px |
| 0.5 | **0.99** | 0.99 **red 3 px** | **99 green 30 px** | 64 yellow 24 px |
| 0.3 | 1.0 | 49.6 yellow 21 px | 49.6 yellow 21 px | 49.6 yellow 21 px |
| 0.3 | **0.98** | 0.98 red 3 px | **98 green 30 px** | 49.6 yellow 21 px |
| 0.3 | 0.5 | 0.5 red 2 px | 50 yellow 21 px | 49.6 yellow 21 px |
| 0.3 | 0.2 | 0.2 red 1 px | 20 red 13 px | 20 red 13 px |
| 1.0 | 0.5 | 0.5 red 2 px | 50 yellow 21 px | 50 yellow 21 px |
| 0.0 | 1.0 | 28 red 16 px | 28 red 16 px | 28 red 16 px |
| any | all dead | 100 white | 100 white | 28 + 72 r |

Rows 3 and 5 are the report. Under the x100 reading a car the player has been wearing down (yellow) gets its engine
scratched and the bar **jumps up to a long green bar**; as the engine is chewed further it steps green -> yellow -> red
while the armour it already lost counts for nothing. In stock the same moment collapses the bar to a red stub, which the
player reads as "nearly dead" - wrong too, but it never goes up, so it never looked like a *colour* bug. The player
compared the fixed build with the stock look and saw the colours go the wrong way.

"One was actually correct": a car whose engine, suspension and brakes stayed above 99.99% (hits on the sides and rear
wear armour and chassis first) takes the side branch in all three builds and reads 28 + 72 r throughout. Every car that
took an engine, suspension or brake scratch took the x100 branch and the jump. Per-car, not per-offset.

## 3. The fix (implemented, not built)

`music-fix/strlkproxy.c`, same section, `I76_FIX_HEALTH_PCT=1` only:

health = **min(28 + 72 x r, 100 x c)**. Monotone in armour, chassis and core damage; identical to stock while the
core is intact (100 c >= 99.99 there, so the min picks the side value); never rises on a scratch; a car with all three
core components dead reads by its sides instead of 100.

Two patch sites, both byte-verified before either is written (`patch_bytes` refuses on a mismatch, and the pre-check
covers all four addresses so a partial apply cannot happen):

1. the four table entries at **0x40b7b8** (stock `F0 B6 40 00` x4) -> `hf_comp_stub`: `fmul [0x4bc620]` (100 c),
   `fstp [esp+0x14]`, `jmp 0x40b5f5`. The slot is the frame's `local_3c`: set to FLT_MAX by the prologue at 0x40b470
   and otherwise used only by the multi-part cases 2/3/0xb/0xc (0x40b75c..0x40b776), which return through their own
   epilogue at 0x40b780 and never reach 0x40b6f0. It lives in the caller's frame, so the fix is re-entrant with no
   global. The `fstp` pops c exactly as the stock `fstp st(0)` at 0x40b5f3 did, so the side loop sees the FPU stack it
   expects; it reads only edi (the entity) and the frame.
2. the clamp entry **0x40b6f0** (`D8 15 20 C6 4B 00` = `fcom dword ptr [0x4bc620]`) -> `jmp hf_min_stub; nop`:
   `fcom [esp+0x14]; fnstsw ax; test ah,1; jne keep; fstp st(0); fld [esp+0x14]; keep: fcom [0x4bc620]; jmp 0x40b6f6`.
   eax is dead at 0x40b6f6 (the stock instruction there is `fnstsw ax`). The intact-core paths (`jmp short` from
   0x40b6ca / 0x40b6dc) and the impossible dead-count > 3 default (0x40b6ec) still hold FLT_MAX in the slot and are
   unchanged. The two short jumps could not be hooked themselves (2 bytes each), which is why the hook sits at the
   clamp every vehicle path shares.

`I76_FIX_HEALTH_PCT=2` keeps the x100-only reading (table patch only, `hf_scale_stub`) for A/B runs. Log lines:
`fix-health-pct: on (health = min(...); sites 0x40b7b8, 0x40b6f0)` / `on (component branch x100 only - A/B reading ...)` /
`bytes differ at ... - not applied`.

Consistency with the live evidence (`i76-map/captures/014-framerate`, chassis 1394/1510 on side 0 -> r = 0.923,
28 + 72 r = 94.5): `hfrac_eng99_fix` c = 0.99 -> min(94.5, 99) = 94.5, no smoke (smoke needs < 75) - matches;
`hfrac_eng50_fix` -> min(94.5, 50) = 50, smoke - matches. Stock runs are untouched (the switch is off). The verify
oracle `i76-map/verify/oracles/health_fraction.py` (`FIX_X100` variant) describes the x100 reading and should become
min() when its `=1` runs are taken; it is in the read-only sibling, so that is flagged, not done.

Also updated: `music-fix/README.md` switch table, `docs/MODDING-GUIDE.md`, `docs/RELEASE-PLAN.md`, the
`health_pct` comment in `tools/telemetry/i76tel.h`.

## 4. Live verification, 5 minutes, sandbox only

Sandbox `C:\Users\james\i76-uncap-lab\game`, at the console (not RDP), one game at a time, proxy rebuilt first (MSVC x86
per `music-fix/README.md` Build) and the sandbox copy restored afterwards. Three arms, same mission, same enemy:
**A** `I76_FIX_HEALTH_PCT` unset (stock), **B** `=2` (x100 only, the reported build), **C** `=1` (this fix).

1. **Boot check (10 s per arm).** `mciproxy.log` must show `fix-health-pct: on (health = min(...` for C, `... x100 only ...`
   for B, nothing for A. Verify the write landed: byte at 0x40b6f0 is `E9` under C, `D8` under A and B; dword at
   0x40b7b8 is `0x0040b6f0` under A only.
2. **Deterministic bar (1 screenshot per arm, the discriminator).** Enter a mission with an enemy (t01 via
   `I76_MISSION=t01.msn`, or a melee), target it (radar target = `0x4613f0(player)`; entity = object + 0x70). With
   `i76-map/verify/poke.py` or `autotest/lib/memlib.ps1`, set the target's four armour sides to 30% of their max
   (`ent+0x138[i] = 0.3 x ent+0x158[i]`) and leave the core intact; then set its engine to 99% (`*(ent+0x3c4)` -> hp at
   +0, max at +4; the same poke `captures/014-framerate` used). Expected bar at the second step:
   A red 3 px (v 0.99), B green 30 px (v 99), C **yellow 21 px (v 49.6)**. Then engine to 20%: A red 1 px, B red 13 px,
   C red 13 px. Then repair the engine to 100%: A yellow 21 px again, B yellow 21 px, C yellow 21 px (C never moved up
   while the engine was damaged; B did).
3. **Observational (2 minutes).** Fresh enemy, fire a sustained burst into its front until the bar changes. A: the bar
   collapses to a red stub the moment any core component is scratched. B: the bar jumps longer and green at that
   moment, then walks green -> yellow -> red. C: the bar only ever shrinks and only steps white -> green -> yellow -> red.
4. **The number.** Ask the player which number they watched. If it was the telemetry `health_pct`, note that it is the
   player's own car, not the target; under C it must equal min(28 + 72 r, 100 c) frame for frame on the player's car,
   which the same two pokes on the player's entity (`captures/014-framerate` procedure) check in one run.
5. **Smoke regression (optional, 1 minute).** Repeat `hfrac_eng99_fix` / `hfrac_eng50_fix` under C: 99% engine no
   smoke, 50% engine smoke (both predicted above).

Pass: C is monotone in step 2 and 3 and reproduces step 5; B shows the rise (confirms the diagnosis); A shows stock.

## Verified live (2026-10-02, sandbox t01, `tools/trainer/tests/health_pct_live_test.py`)

The value the bar is a function of, read through telemetry `health_pct` on the player's car after direct pokes
(armour sides to 30 % of max, then the engine to 99 % and 20 % of its 1200), n = 1 run per variant, every row exact:

| state | stock | `I76_FIX_HEALTH_PCT=2` (x100 only) | `I76_FIX_HEALTH_PCT=1` (min) |
|---|---|---|---|
| armour 30 %, core intact | 49.6 | 49.6 | 49.6 |
| + engine 99 % | **0.99** | **99.0** (the bar jumps to green / full) | 49.6 |
| + engine 20 % | 0.20 | 20.0 | 20.0 |
| repair | 100 | 100 | 100 |

So the field report (bar goes to the wrong colour as a car takes damage, one car correct) is the `=2` column; `=1` is
monotone. The proxy log line names the variant: `fix-health-pct: on (health = min(...); sites 0x40b7b8, 0x40b6f0)`.
Still to do by eye: the bracket itself on an enemy (colour and width per the table above).
