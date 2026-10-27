# Memory Reverse-Engineering Methodology

*A practical reference for cracking live-memory values in Interstate '76 (1997, Win32)
running under Wine on macOS, read/written via AutoHotkey `ReadProcessMemory` /
`WriteProcessMemory`. Non-ASLR, image base `0x400000`.*

This document distills the authoritative reverse-engineering literature (Cheat Engine
official wiki + help, ReClass.NET, game-hacking guides, general RE writeups) into a
methodology tuned to our specific problem: the HUD reads **ammo = 3721** but no stable
4-byte int or float at that literal value tracks the fired count.

Every technique below is cited to its source. Read the ranked recommendations at the
bottom first if you just want the fastest path.

---

## 0. Our situation in one paragraph

We already have the two hardest prerequisites solved: the image loads at a **fixed base**
(`0x400000`, no ASLR — a 1997 exe predates it), and we can **read and write arbitrary
process memory live** through AHK's RPM/WPM. What we lack is the standard game-hacking
*discovery* toolchain — value scanning, pointer scanning, watchpoints — because AHK is a
poking tool, not a scanner or debugger. The methodology below is mostly about **borrowing
those discovery techniques**, either by scripting them in AHK or by attaching a real tool
(Cheat Engine / x64dbg) to the same process, then baking the *result* (a static pointer
path or a code patch) back into our AHK trainer.

The core hypothesis to disprove: the displayed 3721 is not stored verbatim as an int32 or
float32. Likely encodings, in rough order of probability for a 1997 title:

1. **Display value ≠ internal value.** The HUD computes `displayed = f(internal)` each
   frame from a different field (e.g. remaining rounds derived from a magazine struct, or
   a count that is `max - fired`).
2. **Scaled / fixed-point.** Old engines store quantities as fixed-point (e.g. 16.16, scale
   `65536`) or as a scaled integer. The literal 3721 never appears; `3721 * 65536` or
   `3721 * someScale` does. [hugi fixed-point]
3. **Non-dword width.** Stored as int16 (word) or even a byte pair, so a 4-byte scan for
   3721 straddles the boundary and misses. [shikadi/starcube]
4. **Relocating struct.** The ammo lives in a heap-allocated weapon/vehicle struct that is
   re-allocated on level load or vehicle spawn, so any address you find dies on relaunch —
   solved only by a **pointer path**, not a raw address.
5. **"Shots fired" counter**, i.e. a monotonically *increasing* value, where the HUD shows
   `capacity - fired`. Then an exact scan for 3721 is looking for the wrong number entirely.

Sections 1–5 give the technique for each; Section 6 covers the Wine/1997 specifics.

---

## 1. Value scanning: exact value vs unknown-initial-value

**Source of truth:** Cheat Engine's own tutorial defines the two scan families and the
increased/decreased/changed/unchanged refinement loop.
[CE Tutorial Guide], [CE unknown-value issue], [lonami woce-3]

### 1a. Exact-value scan (when you know the number)

Standard first move: scan for `3721` as an exact value, act in-game so the number changes,
then **Next Scan** for the new exact value, and repeat until the candidate set collapses to
a handful. Each scan is a set intersection: survivors are addresses matching *every* value
you've entered over time. [CE Tutorial Guide, Step 2]

Critical variation for our case — **run the exact scan across every type and width, not just
int32**:

- int32, int16, int8, and **float** and **double** at 3721.0. (CE Tutorial Step 4 explicitly
  scans health as `float` and ammo as `double`; do not assume int.) [CE Tutorial Guide, Step 4]
- Also scan the **scaled** candidates: `3721 * 65536 = 243,859,456` (16.16 fixed-point) and,
  if the HUD ever shows fractional-looking behavior, other scale factors. [hugi fixed-point]

If *none* of these hit, that itself is strong evidence for hypothesis 1 or 5 (display ≠
internal), which is exactly where the unknown-value scan takes over.

### 1b. Unknown-initial-value scan (when you can't name the number)

This is the technique for a value you cannot express as a literal — a "shots fired" counter,
a derived display, or a fixed-point blob you can't predict. The workflow:
[CE Tutorial Guide, Step 3], [lonami woce-3]

1. **New Scan → scan type "Unknown initial value"**, value type 4-bytes (then repeat the
   whole procedure for 2-byte and float). This snapshots *all* of memory as the baseline.
2. Perform an action whose effect on the hidden value you can *predict directionally* even
   if you don't know the magnitude:
   - **Fire one round** → the ammo field either **decreased** (remaining) or **increased**
     (shots-fired counter). You don't need to know which yet.
3. **Next Scan** with the matching operator:
   - `Decreased value` — keeps addresses whose value went down.
   - `Increased value` — keeps addresses whose value went up.
   - `Changed value` / `Unchanged value` — for the "I only know it moved / didn't move"
     case. Do an **Unchanged value** scan while idling to kill the huge churn of unrelated
     counters, then a **Decreased/Increased** scan on the frame you fire. [lonami woce-3]
4. Repeat the fire-then-scan loop. Each pass is a set intersection; the candidate list drops
   from millions to dozens in ~6–10 iterations. [lonami woce-3]

**Why this cracks the "shots fired" hypothesis:** you never had to know the number. If firing
consistently produces `Increased value` survivors and reloading produces `Decreased`/reset
survivors, you have found the internal counter regardless of what the HUD prints.
[CE Tutorial Guide, Step 3]

**Doing this without Cheat Engine, in pure AHK:** the unknown-value scan is just bookkeeping
you can script. Snapshot a memory region with RPM into a buffer; after the in-game action,
RPM again and keep only offsets where `new < old` (decreased) etc.; intersect across passes.
This is exactly what a "writing our own Cheat Engine" implementation does. [lonami woce-3]
It is tedious but entirely within RPM's capabilities and avoids the Wine-attach problem
(Section 6). Scan a bounded region first (the exe's static `.data`, roughly `0x400000`
through the end of the image) before scanning the full heap.

---

## 2. Display value vs internal value (the base + delta / float / fixed-point split)

This is the heart of our problem. Games routinely keep two representations: an **authoritative
internal field** the simulation mutates, and a **display value** derived from it each frame.
The displayed 3721 may be `capacity - fired`, a float rounded to int for rendering, or a
fixed-point value scaled for the HUD. [starcube RE-GBA], [shikadi], [hugi fixed-point]

### How to conclusively identify the authoritative copy

The definitive test is **mutual causation — change one, watch the other**:

1. Find *any* address that holds 3721 (or the scaled/derived variant) via Section 1.
2. With our AHK WPM, **write a new value into it** (e.g. 9999) and observe the HUD:
   - **HUD changes to match, and stays changed / behaves correctly when firing** → you found
     the authoritative field. Done.
   - **HUD flickers back to the old value within a frame** → you edited a *display cache*;
     the engine overwrote it from the real field next frame. The authoritative copy is
     elsewhere. This flicker is itself the tell.
   - **HUD is unaffected** → you edited an unrelated copy (or a stale mirror).
3. To find the real field from a display cache, use **"find out what writes to this
   address"** on the display copy (Section 5): the instruction that writes it will read from
   the authoritative field, whose address is `baseRegister + offset` at that instruction.
   [CE find-out-what-writes]

### Recognizing the encoding

- **Fixed-point (16.16, scale 65536):** the internal dword equals `displayed * 65536`
  (= 243,859,456 for 3721). Scan for that. More generally, if the stored value is a
  suspiciously large multiple of the display, divide and check for a power-of-two or round
  scale factor. [hugi fixed-point], [circuitcellar]
- **Float32:** 3721.0 has IEEE-754 bytes `00 90 68 45` (little-endian) — scan as float, not
  int, or scan those raw bytes. CE Tutorial Step 4 exists precisely because ammo/health are
  often floats/doubles. [CE Tutorial Guide, Step 4]
- **Word vs dword:** if a 4-byte scan finds nothing but a 2-byte scan for 3721 hits, the
  field is int16 and the upper two bytes belong to an adjacent field. A telltale: sequential
  struct fields are usually similar in magnitude, so a "huge upper half, tiny lower half"
  dword is really two words. [starcube RE-GBA], [shikadi]
- **Base + delta:** displayed = `base - fired` or `base + bonus`. Firing changes the delta,
  not the base; the unknown-value scan (Section 1b) finds whichever field actually moves.

---

## 3. Pointer scanning: a static path that survives relocation

If the ammo lives in a heap struct that is re-allocated on level load, vehicle spawn, or
relaunch, a raw address is worthless next session. You need a **pointer path**: a chain of
dereferences that starts at a **static global in the exe's `.data`** (fixed at
`0x400000 + k` for us) and walks `[[[base]+o1]+o2]+o3 = &ammo`. Because the globals never
move (no ASLR) and the engine's own pointers are rebuilt to the new struct each load, the
*path* stays valid even though the *destination* address changes.
[CE Help:Pointer_scan], [CE pointer-scan help], [Multi-level pointers]

### The concept

A multi-level pointer is `finalAddress = [ [ [staticBase] + off1 ] + off2 ] + off3`. The
static base is a green (module-relative, non-moving) address; each offset is a field within
the struct at that level. Freezing/reading through the path always lands on the live struct.
[Multi-level pointers], [CE Tutorial Guide, Step 8]

### Method by hand (works with CE, and the logic is reproducible in AHK)

**Bottom-up, using the code finder (most reliable):** [CE Tutorial Guide, Step 8]

1. Get the current ammo address (Section 1).
2. **"Find out what accesses this address"** (Section 5). Note the instruction, e.g.
   `mov eax,[esi+18]`. The struct base is in `esi`; the field offset is `0x18`.
3. The value now in `esi` is the **struct base address**. Search memory (4-byte, hex, exact)
   for a pointer *holding that base value* — those are pointers into your struct.
4. Repeat: "find what accesses" one of those pointer addresses to get the next base register
   + offset, and search for *its* value. Walk up level by level.
5. Stop when a search returns a **green/static address** (inside the `0x400000` image, in
   `.data`). That is the root. The offsets you collected on the way down form the path.
   [CE Tutorial Guide, Step 8]

**Automatic pointer scan (CE's Pointer Scanner):** [CE Help:Pointer_scan], [CE pointer-scan help]

1. Right-click the found ammo address → **Pointer scan for this address**. Choose "find
   pointers for an address" (faster than by value).
2. Set **Max level** (chain depth, default 5 — increase if nothing static is found, "some
   programs use even longer paths") and **Maximum offset** (default 2048, rarely needs
   raising). Save the resulting pointer list.
3. **Validate against relocation — the essential step:** change the value's location (die,
   reload level, respawn vehicle, or fully relaunch the game so the struct re-allocates),
   find the ammo address again, then **Pointer scanner → Rescan memory** with the new
   address. CE filters out every pointer that no longer resolves correctly.
   [CE Help:Pointer_scan]
4. Repeat rescans across several relocations until only a handful of paths survive. Those are
   the stable ones. Prefer the **shortest** path with a static root and small offsets.
   [CE Help:Pointer_scan]

For our trainer: once you have `base(0x400000+k) → +o1 → +o2 → +ammoOff`, encode that chain
in AHK — RPM the static global, add offset, RPM again, etc. — and you get a reader/writer that
survives every relaunch without re-scanning.

---

## 4. Struct dissection (ReClass-style): map the whole struct once you have a base

Once "find what accesses" (Section 5) hands you a **struct base register value**, treat that
base as the anchor of an unknown struct and **map every field by walking offsets and
correlating each to something on screen**. This is what ReClass.NET automates, but the method
is the point and works with plain RPM. [ReClass.NET GitHub], [guidedhacking ReClass]

### The workflow

1. Point a struct viewer (ReClass.NET, or CE's "Dissect data/structures", or a scripted AHK
   hex dump) at the base address. In ReClass you anchor with a formula like
   `i76.exe + 0x1234` or a literal pointer. [ReClass.NET GitHub]
2. Lay out a row of nodes (Hex32 by default) covering the first few hundred bytes of the
   struct. [ReClass.NET GitHub], [guidedhacking ReClass]
3. **Correlate offsets to known on-screen values by causing change:**
   - Fire, reload, take damage, change gear — and use **Highlight Changed Memory** (ReClass
     flashes bytes that changed since last refresh) to see which offset moves with which
     action. [ReClass.NET GitHub]
   - The offset that ticks with firing is your ammo/shots field; adjacent offsets are often
     magazine capacity, weapon id, cooldown, etc.
4. Re-type each identified node to its true type (Int16/Int32/Float/Pointer). ReClass's
   **Pointer preview** dereferences pointer fields inline so you can follow sub-structs, and
   **Automatic Node Dissection** guesses field boundaries. [ReClass.NET GitHub]
5. When done, ReClass **generates C/C++/C# struct code** — a permanent, documented map of the
   struct you can transcribe into offset constants for the AHK trainer.
   [ReClass.NET GitHub], [guidedhacking ReClass]

ReClass.NET has **Linux support** (tested on Ubuntu 18.04), which matters for the Wine case
(Section 6). [ReClass.NET GitHub]

The payoff: even if the literal 3721 is hidden, once you can see the *whole* struct changing
in real time, the ammo field is usually obvious — it's the one that decrements per shot and
resets on reload, sitting next to a constant that equals magazine capacity.

---

## 5. "Find what writes/accesses this address" — the watchpoint that names the field

This is the single most conclusive technique and the one AHK alone cannot do (it needs a
hardware/debug breakpoint, i.e. a debugger). It sets a **breakpoint on the address** and logs
**every instruction that touches it**, with register values. [CE find-out-what-writes]

### What it gives you

- The exact assembly instruction that writes (or reads) the value, e.g. `mov [esi+18],eax`,
  plus a hit counter and the **register values at the moment of access**. [CE find-out-what-writes]
- From `[esi+18]` you learn **the struct base (`esi`) and the field offset (`0x18`)** — the
  two inputs Section 3 (pointer path) and Section 4 (struct map) both need. [CE find-out-what-writes],
  [CE Tutorial Guide, Step 8]
- **"Find out what writes"** on a *display cache* points you at the code that refreshes it,
  which reads from the authoritative field — resolving the display-vs-internal split
  (Section 2) directly. [CE find-out-what-writes]

### Why it's decisive for our problem

If we suspect a "shots fired" counter or a derived display, watchpoints end the guessing: set
"find what writes" on the display copy, fire once, and read the instruction. If it's
`mov [display], eax` preceded by `mov eax,[capacity]; sub eax,[fired]`, you have literally
read the encoding — `displayed = capacity - fired` — off the disassembly. No more scanning.
[CE find-out-what-writes], [lonami woce-5 code finder]

### How to run it against our target

AHK can't set debug breakpoints. Options, best first:

- **x64dbg** (its 32-bit `x32dbg`) attached to the Wine process, or **Cheat Engine's
  debugger**, using a **hardware breakpoint** on the ammo address (memory access breakpoint).
  Same information as CE's "find what writes." Under Wine this is the reliable path when it
  attaches (Section 6).
- **CE inside the same wineprefix** (Section 6) — its "find out what accesses this address"
  is the turnkey version. [CE Tutorial Guide, Step 5]

---

## 6. Wine / macOS / 1997-era specifics

### Does Cheat Engine work under Wine on macOS?

Partially, and the *how* matters:

- **Running native CE (Linux/Mac build) and attaching to a Wine process via ceserver is
  flaky** — reports of CE hanging on attach, and of ptrace not reaching across the Wine
  boundary cleanly. On Linux you often need `setcap cap_sys_ptrace=eip` on `wineserver`
  and/or a relaxed `ptrace_scope`, and even then it's unreliable. [CE Wine/Proton thread],
  [CE ceserver hang], [winehq inject-into-wine]
- **The approach that actually works: run the Windows `cheatengine.exe` *inside the same
  Wineskin/wineprefix* as the game.** From Wine's perspective both are Windows processes in
  one prefix, so CE's normal `ReadProcessMemory`/debugger path applies and the ptrace/ceserver
  boundary never comes up. This is the documented Mac/Wineskin route. [CE Wineskin/Mac thread],
  [CE Wine/Proton thread]
  - Practically: drop `cheatengine.exe` (a portable/older 6.x build is friendliest to old
    Wine) into the game's prefix and launch it with the same `wine`/wrapper that runs the
    game. Since our prefix lives under the Sikarugir wrapper
    (`…/Contents/SharedSupport/prefix/…`), install CE there.
- **x64dbg/x32dbg** can likewise run inside the prefix and attach to the game as a normal
  Windows debugger; hardware breakpoints (the "what writes" watchpoint) generally work under
  modern Wine.
- **ReClass.NET** has native Linux support and can also be run as the Windows build inside the
  prefix for struct dissection. [ReClass.NET GitHub]

### 1997 / winmm-era gotchas

- **No ASLR** (confirmed — base `0x400000`). Statics are truly static, which makes the
  pointer-path root (Section 3) trivially reproducible and makes AHK-baked static offsets
  durable across launches. This is a big advantage over modern targets.
- **Values are often int16, byte, or fixed-point**, not int32/float — a 32-bit x86 title from
  1997 predates the float-everywhere convention of later engines. Always scan multiple widths
  and the fixed-point scale (Section 1a, 2). [shikadi], [starcube RE-GBA], [hugi fixed-point]
- **Struct relocation on level/vehicle load is common**; budget for a pointer path (Section 3)
  rather than trusting a bare address across a mission boundary.
- `winmm` (MCI) is the audio/timer layer and is unrelated to the ammo field — don't chase it
  for gameplay values; it's a red herring for this problem.

---

## Ranked: the techniques most likely to crack our ammo encoding

1. **Unknown-initial-value scan driven by firing (increased/decreased/changed).** This is the
   highest-probability first move because it makes zero assumptions about the encoding — it
   finds whatever field actually moves when you fire, whether that's a "shots fired" counter
   going *up*, a remaining-rounds field going *down*, or a fixed-point blob. It directly
   defeats hypotheses 1 and 5, the two the exact-value scan already failed on. Scriptable in
   pure AHK RPM (snapshot → act → intersect), so no Wine-attach dependency. [CE Tutorial Guide,
   Step 3], [lonami woce-3]

2. **"Find out what writes to this address" (watchpoint) on any copy we can find — including a
   display cache.** The single most conclusive technique: it reads the encoding off the
   disassembly (`sub eax,[fired]` etc.) and simultaneously hands us the struct base register +
   offset needed for the pointer path and struct map. Requires a debugger (CE or x32dbg)
   running *inside the wineprefix*, not AHK. Do this the moment step 1 or an exact scan yields
   even one address. [CE find-out-what-writes], [CE Tutorial Guide, Step 5], [lonami woce-5]

3. **Multi-width + fixed-point + float exact scans.** Cheap, fast, and directly tests the
   "stored ≠ displayed literal" encodings: scan 3721 as int16, as float (`00 90 68 45`), and
   scan `3721 × 65536` as int32 for 16.16 fixed-point. If any hits, the problem collapses to a
   value we can read/write immediately. Runs in AHK or CE. [CE Tutorial Guide, Step 4],
   [hugi fixed-point], [starcube RE-GBA]

4. **Struct dissection with highlight-changed-memory, once we have a base.** After step 1/2
   gives a struct base, dump the surrounding bytes and watch which offset ticks per shot and
   resets on reload. The ammo field is almost always visually obvious next to a constant equal
   to magazine capacity — and this also reveals the capacity/fired pair behind a derived
   display. [ReClass.NET GitHub], [guidedhacking ReClass]

5. **Pointer scan to a static root, then bake the path into the AHK trainer.** Not for
   *finding* the value but for making it *durable*: once identified, derive
   `[[0x400000+k]+o1]+o2 = &ammo` so the trainer survives relocation and relaunch without
   rescanning. Highest long-term payoff, lowest discovery value — do it last. [CE
   Help:Pointer_scan], [CE Tutorial Guide, Step 8]

---

## Sources

- Cheat Engine — Help File: Pointer scan: <https://wiki.cheatengine.org/index.php?title=Help_File:Pointer_scan>
- Cheat Engine — pointer-scan help: <https://cheatengine.org/help/pointer-scan.htm>
- Cheat Engine — Help File: Find out what writes/accesses this address: <https://wiki.cheatengine.org/index.php?title=Help_File:Find_out_what_writes/accesses_this_address>
- Cheat Engine — Find out what writes/accesses (help): <https://www.cheatengine.org/help/find-out-what-writesaccesses-this-address.htm>
- Cheat Engine — Tutorial Guide (x64), Steps 2–8 (exact/unknown/float/code-finder/multilevel-pointer): <https://wiki.cheatengine.org/index.php?title=Tutorials:Cheat_Engine_Tutorial_Guide_x64>
- Cheat Engine — "Missing Unknown initial value" (tutorial issue): <https://github.com/cheat-engine/cheat-engine/issues/2837>
- Cheat Engine Wikia (restored) — Multi-level Pointers and Base Addresses: <https://cheat-engine-restored.fandom.com/wiki/Multi-level_Pointers_and_Base_Addresses>
- Lonami — "Writing our own Cheat Engine: Unknown initial value": <https://lonami.dev/blog/woce-3/>
- Lonami — "Writing our own Cheat Engine: Code finder": <https://lonami.dev/blog/woce-5/>
- ReClass.NET — official repository (feature list, node types, Linux support, code gen): <https://github.com/ReClassNET/ReClass.NET>
- GuidedHacking — ReClass.NET tutorial (how to reverse structures): <https://guidedhacking.com/threads/reclass-tutorial-reclass-net-how-to-reverse-structures.7823/>
- Cheat Engine forum — "How to use Cheat Engine with games running under WINE?": <https://www.cheatengine.org/forum/viewtopic.php?t=611026>
- Cheat Engine forum — "CE Wineskin and Mac": <https://www.cheatengine.org/forum/viewtopic.php?t=578191>
- Cheat Engine — ceserver/CE hang on Linux (issue #2161): <https://github.com/cheat-engine/cheat-engine/issues/2161>
- WineHQ forum — injecting code into a Windows process running under Wine: <https://forum.winehq.org/viewtopic.php?t=37212>
- Hugi — Fixed Point Maths (16.16, scale 65536): <https://www.hugi.scene.org/online/coding/hugi%2015%20-%20cmtadfix.htm>
- Circuit Cellar — Integer & Fixed Point Representation: <https://circuitcellar.com/resources/quickbits/integer-fixed-point-representation/>
- Starcube Labs — Reverse Engineering a GBA Game (word vs dword, display vs internal): <https://www.starcubelabs.com/reverse-engineering-gba/>
- Shikadi ModdingWiki — Reverse engineering guide (old-game data widths/encoding): <https://shikadi.net/moddingwiki/Reverse_engineering_guide>
