# GHIDRA-MEMORY-MAP — mining Roanish/i76 ("Vigalante '76") for i76-everywhere targets

Date: 2026-07-18. Source repo cloned at
`scratchpad/roanish-i76` (github.com/Roanish/i76, 8 commits, 2026-06-05 → 2026-06-14).
Primary evidence: `docs/REVERSING.md` (1282 lines, read in full) + all source comments
(grepped for every `FUN_00xxxxxx` / `DAT_00xxxxxx` annotation — the source adds NO
addresses beyond REVERSING.md). Supplemented with web checks (Shane Peelar /
inbetweennames.net, piranha76, localditch, netcode-patch pages).

## Confidence vocabulary used below

- **DIRECT** — stated in the decompile's own notes (REVERSING.md), with the repo's
  own "CONFIRMED" status (they distinguish CONFIRMED vs `???` guesses rigorously).
- **DIRECT-GUESS** — in the decompile's notes but flagged `???` by its author.
- **INFERRED** — my synthesis from the decompile + our repo's field data; not in any source.
- **ABSENT** — the target is simply not covered by this decompile yet.

---

## 0. Repo assessment: what this decompile is, and how faithful

**Structure.** ~5,300 lines of clean-room C (SDL2 + Vulkan) in `src/`, three asset
tools in `tools/`, and one long RE dossier `docs/REVERSING.md`. The C code is a
*rewrite*, not a decompile dump — the reverse-engineering payload lives almost
entirely in REVERSING.md.

**Fidelity: high, but narrow.** REVERSING.md preserves:
- Original Ghidra symbols verbatim (`FUN_00431760`, `DAT_004f30cc`, `LAB_...`),
  with a renamed-name column and an explicit CONFIRMED / `???` status per entry,
  including "WHY GUESSED" and "CONFIRM BY" notes. This is unusually honest RE work.
- Full struct layouts with byte offsets (ZFS entries, VFS sources, cache nodes,
  PakEntry, OEG mesh format, .fnt format).
- Hash constants, heap-sizing logic, call graphs, a 32-entry ShellMain callback
  table at stack `&local_80`.

**⚠ CRITICAL CAVEAT — wrong binary for direct address reuse.** The decompile
targets the **Nitro Pack** executable (GOG Nitro release, Win32 MSVC), *not* our
GOG **Gold `i76.exe`**. Every `0x004xxxxx`/`0x005xxxxx`/`0x006xxxxx` address below
is a **Nitro address** and will NOT line up with Gold. The two exes are the same
engine lineage (modified MechWarrior 2 engine per Peelar), so *struct layouts,
string literals, table-driven parser shapes, and function bodies* should transfer
well — the addresses won't. Treat everything here as (a) a name/shape map to
re-anchor in a Ghidra session on the Gold exe via string xrefs, and (b) direct
format knowledge where the data lives in files (which is binary-independent).

**Coverage summary.** What the decompile HAS reversed: startup/WinMain, game-state
machine, window proc + input dispatch skeleton, ZFS/VFS/file-cache, GEO mesh cache
+ OEG mesh format, PIX/PAK LOD system, mission-file → object-placement → entity-spawn
chain, ShellMain (NITSHELL.DLL) interface, fonts, DirectSound sample loader,
session-end flags. What it has NOT touched: **camera, vehicle physics/state, damage,
collision, save writer, input.map parser, force feedback** — i.e. *all six of our
priority targets have no direct coverage*. The README's own status table says it
plainly: Vehicles/physics "Not started", AI/combat "Not started", Audio "Not started".

Web supplement: Peelar's writeups (netcode patch, framerate/physics coupling, fast
rsqrt) contain no memory maps for our targets either; piranha76 and Open76 are
asset-format reimplementations. No public cheat table with i76 Gold addresses was
found. **Conclusion: for targets 1–6, first-party Ghidra work on the Gold exe is
required; this repo gives us the map to do it fast.**

---

## 1. CAMERA (yaw/pitch write path) — **ABSENT**, but strong leads

Nothing in the decompile touches the camera, `track_yaw_*`, `track_pitch_*`, or
`pilot_glance_target`. No camera struct, no orientation globals.

What IS there that helps:

- **Game-object transform block** (DIRECT, partial): the live game-object struct
  (the pointer hashed into `g_objmodel_registry` @ `0x00529bf0` [Nitro]) has
  `+0x5c` = cached mesh ptr, `+0x84..+0x93` = 4-dword block, and
  `+0x94..+0xab` = **6-dword block "likely a transform/orientation"**
  (DIRECT-GUESS on the interpretation). Entities are spawned with a **48-byte
  3×4 float matrix** (12 floats) built by `FUN_004b3db0` ("transform_build")
  and passed to `FUN_00453d50` ("entity_spawn", anchored by the fatal string
  `"I'76 Nitro Pack cannot create entity"`). So world orientation in this engine
  is matrix-form (3×4), at least at spawn. Expect the camera to also carry a
  3×4 or basis-vector form, possibly alongside yaw/pitch scalars for the
  tracked-camera modes. Confidence: DIRECT for the 48-byte spawn transform;
  INFERRED for camera representation.

- **Table-driven dispatch is this engine's house style** (DIRECT): the chunk
  parser `chunk_table_parse` (`FUN_004bccb0` [Nitro]) uses descriptor tables of
  `{FourCC tag, handler fn ptr, flags}` × N. INFERRED: the input.map action
  parser almost certainly uses the same pattern — a static table of
  `{action-name string, handler/param}` — which is why every action token
  (`track_yaw_delta` etc.) appears in the exe string table (our lint tool
  already dumps it).

**Recipe for the Gold exe (the actionable output):**
1. In Ghidra on Gold `i76.exe`, find the string literals `track_yaw_delta`,
   `track_pitch_delta`, `pilot_glance_target` (we know they exist — the lint
   tool validates against the exe string table).
2. Xref each string → it will sit in a static action-descriptor table (stride
   likely 8–16 bytes: name ptr + handler/enum). The table gives the full
   bindable-action vocabulary in one place (also answers target 5's "any more
   analog channels?").
3. Follow the `*_delta` handlers: they will add a scaled input value to one or
   two float (or fixed-point) globals/struct fields per frame — those fields ARE
   the write path for head tracking. `pilot_glance_target` is the best single
   thread: it must compute a yaw/pitch (or basis) toward the target each frame
   and store it into the same camera fields, proving continuous orientation and
   pointing straight at them.
4. For the external writer: expect either camera globals (MW2-era engines often
   keep the active camera as a global singleton) or `g_camera_ptr -> +off`.
   Confidence that this recipe lands quickly: high — string-anchored, single hop.

---

## 2. PLAYER VEHICLE STATE — **ABSENT** in-memory; entity-store entry points located

No vehicle struct, no armor/health/RPM/gear/velocity fields in the decompile.
The repo explicitly notes the game-object struct "is allocated outside the
mesh-acquire call graph" and lists finding it as future work.

What IS there (all Nitro addresses):

| Item | Symbol | Confidence |
|---|---|---|
| Entity allocator | `FUN_004b3e20` ("object_alloc") | DIRECT (proposed name) |
| Entity spawn/world-insert | `FUN_00453d50` ("entity_spawn"; fatal `"cannot create entity"`) | DIRECT (string-anchored) |
| Entity link/register | `FUN_004540b0` ("entity_register") | DIRECT-GUESS |
| Per-object type code | OBJ record `+0x64` switch in `FUN_004b3660` | DIRECT |
| Object struct fields | `+0x5c` mesh ptr; `+0x84..+0xab` transform-ish blocks | DIRECT / DIRECT-GUESS |
| Object→model registry | `g_objmodel_registry` @ `0x00529bf0`, 2029 buckets keyed by object ptr, hash `(ptr*0x6cd+0xaab)%0x7ed` | DIRECT |
| Model record damage-state hook | 0x3c record: `+0x08` variant idx / `+0x0c` slot idx select a 16-byte mesh name from a 7-slot × N-node grid — the repo reads this as "LOD / **damage state** / part swap" | DIRECT (mechanism), DIRECT-GUESS (damage-state meaning) |

**Static pointer chain: not derivable from this source.** No global holding
"player entity" is identified. INFERRED leads for our own Gold RE:
- `g_objmodel_registry`-equivalent in Gold is easy to find (2029-bucket table,
  hash constants 0x6cd/0xaab/0x7ed are distinctive immediates — search for
  `imul reg, 0x6cd`), and every live object passes through it. But it's keyed
  by pointer, so it doesn't give "the player" directly.
- Better: our save editor proves the `.cmp` writer dumps **live component
  records** — the 116-byte inventory record carries *saved runtime pointers*
  at `+84` (three dwords of garbage that differ between twin saves; see
  `i76-save-editor.py` docstring). That means the in-memory component struct is
  ~the same 116-byte layout (name[30] @+0, type u32 @+30, class id @+46,
  def file @+59, max durability @+76, weight f32 @+80, live ptrs @+84,
  condition @+96, location @+100). **A memory scanner can signature-scan the
  Wine process for a known component name string with `type` dword at +30 and
  plausible condition at +96, then walk ±116 to map the component array** —
  no Ghidra needed for a first working reader. Armor @2044 in the save
  (8×u32, tenths of the DEFENSE panel) is likewise probably a straight dump of
  an in-memory 8×u32 armor/chassis block — scan for the known 8-value tuple
  while in-game. Confidence: INFERRED, but grounded in the runtime-pointer
  evidence (the writer is a memcpy-style dump, so layouts match).
- RPM/gear/velocity: nothing anywhere; Gold-exe RE or value-scan required.

## 3. DAMAGE / COLLISION — **ABSENT**

Zero coverage: no damage-apply, no collision functions, no combat. Closest
adjacent facts (all DIRECT, Nitro):
- The model-registry variant/slot mechanism (see above) is how a component's
  *visual* damage state swaps meshes — `obj_model_set_variant`
  (`FUN_00438d00`) / `obj_model_set_slot` (`FUN_00438e10`) →
  `FUN_0043ce90` (render-state rebuild, "likely recomputes bounding box /
  collision / render state"). INFERRED: in Gold, xrefs TO the
  set_variant/set_slot equivalents from combat code would be one route into
  the damage-apply path (damage → pick new damage-state mesh).
- Session-end flags bitmask (`FUN_00448820`: 0x100 time / 0x200 points /
  0x400 kills / 0x800 laps / 0x1000 capture) — multiplayer scoring, not damage.

For our rumble goal, the save/in-memory component `condition` field (+96 of the
116-byte record, per §2) is the practical watch target: poll it and the armor
block; deltas = got hit / component degraded. Collision-as-event (no damage)
won't fall out of this source at all. Confidence: INFERRED.

## 4. SAVE SYSTEM — **ABSENT** except one path-builder

- `FUN_004bc730` = `save_path_build(scenario_name)` — "builds save file path"
  (DIRECT, one line; body not documented). That is the entire save-system
  coverage. No `savegame.dir` writer, no `saveNNN.cmp` writer, no truncation
  root cause.
- Our own field data (repo docstring) remains the best source: the engine bug
  where a fresh-slot save writes the dir entry as `saveNNN` but the file as
  `save-01.cmp` (`sprintf("save%03d", -1)` — slot allocator returned
  not-found) is *our* finding and explains the observed "dir entry without
  .cmp" case exactly. The newest-entry tail truncation root cause still needs
  Gold-exe RE. Recipe: in Gold Ghidra, find the format string `save%03d`
  (or `savegame.dir` literal) → the writer cluster is one xref away; the
  truncation will be visible as a short write / off-by-one length computation
  in the dir-append path. Confidence in recipe: high (string-anchored).

## 5. INPUT SYSTEM (input.map parser) — **ABSENT**; only the Win32 layer is mapped

Not covered: input.map parsing, device tokens, axis vocabulary, why bare
`Joystick` parses-but-binds-nothing. The repo's input work is a clean-room
snapshot layer; its only note is that "The original polled Win32 keyboard state
(and DirectInput for the joystick)" (DIRECT-GUESS, comment in `src/engine/input.h`).

What IS mapped (Nitro addresses, all DIRECT):
- `g_input_mode` @ `0x00503e94` — mode selector gating all input dispatch in
  window_proc: 0x01 normal, 0x02 keyboard-only, 0x10 full mouse+KB, 0x20 video
  playback; `& 0x3e` = any active mode.
- `g_keymap` @ `0x004f72c0` — `short[VK_code]` Windows-VK → game-key-code
  table (0x1b = ESC, 0x1ff = special).
- `input_dispatch` = `FUN_00442c20(msg, wParam, lParam)` — general input
  handler for non-video modes; `mouse_input` = `FUN_0049e470`.
- INFERRED: keyboard input is Win32-message/keymap based; the joystick is a
  separate (DirectInput or winmm) poll path not yet found. Our field result
  (`joystick1` works, bare `Joystick` parses but binds nothing) is consistent
  with a device-name table where `joystick%d` entries are registered devices
  and bare `Joystick` matches a parse rule but resolves to no device slot —
  but that is conjecture; the parser needs Gold-exe RE. Recipe: xref the
  literal `joystick1` / `Left/Right` / `Down/Up` / `Throttle` / `Rudder`
  strings in Gold — the axis-vocabulary table they sit in IS the complete
  analog channel list (answers "any more bindable analog channels" by
  enumeration), and the device-token comparison right next to it will show the
  bare-`Joystick` behavior.

## 6. FORCE FEEDBACK — **ABSENT**

No DirectInput effect code anywhere; audio itself is "Not started" (only the
DirectSound *sample loader* `FUN_0041b3c0` is reversed, via vtable offsets
+0x0c CreateSoundBuffer / +0x2c Lock / +0x4c Unlock). Nothing on FF effects,
FRC-edition code, or `IDirectInputEffect`. Gold/FRC FF must be reversed from
our own binary (search Gold exe imports for `DirectInputCreate` and effect-GUID
byte patterns), or intercepted at the dinput.dll boundary in the Wine prefix —
the proxy-shim route needs no RE at all and is probably faster. Confidence:
ABSENT is certain (grepped repo).

---

## Bonus: DIRECT material worth keeping even though off-target

- **Game state machine** `g_gamestate` @ `0x004f30cc` [Nitro]: 5=gameplay,
  1=frontend, 0=lobby, 3=end-session, 7=mission-end, 8=mp-followon,
  0xb=lobby-alt, 6=shell-active. A one-dword "is the player actually driving"
  probe — worth re-anchoring in Gold (it's written right before the
  `while(state==5)` hot loop; findable from the WinMain shape). Useful to gate
  our AHK layer (e.g., only rumble/head-track in state 5).
- **Mission format**: mission file = BWD2-family tagged chunks; body table
  WDEF/TDEF/RDEF/ODEF/LDEF/ADEF/EXIT; ODEF → OREV/OBJ; each OBJ = geometry
  name + 48-byte 3×4 transform (+ type code @+0x64) → entity spawn. (DIRECT)
- **ZFS/VFS/PIX-PAK/OEG formats**: fully documented with struct layouts in
  REVERSING.md §§ "ZFS Archive Format", "VFS Layer", "PIX/PAK", "GEO/OEG" —
  binary-independent file-format knowledge, applies to our Gold install's
  archives directly (Gold uses I76.ZFS; entry/flag semantics should match:
  36-byte entries, flags bit0 deleted / bits1-2 LZO1X/LZO1Y / bits8-31
  uncompressed size, optional per-archive u32 XOR key in header bytes 20–23).
- **Fatal-string anchor list for Gold Ghidra work** (strings → functions):
  `"cannot create entity"` → entity_spawn; `"Cannot locate Mission file %s"`
  → mission_file_load; `"Could not load pack %s"` → vfs_lod_pak;
  `"new geometry: couldn't make room"` → geo_build_mesh;
  `"Cannot allocate space for %s"` → vfs_lod_cached; `"Init Graphic Sys"` →
  gfx-init failure path; `SCRDUMP.BMP` → screenshot_save; `save%03d` /
  `savegame.dir` → save writer cluster; `track_yaw_delta` etc. → input action
  table → camera fields. Hash immediates `0x6cd/0xaab/0x7ed` (mesh cache,
  model registry) and `%2009` (VFS cache) are distinctive re-anchoring
  fingerprints too.

## Bottom line per target

| # | Target | In decompile? | Best next step |
|---|---|---|---|
| 1 | Camera yaw/pitch write path | No | Gold Ghidra: xref `track_yaw_delta`/`pilot_glance_target` strings → action table → camera fields. High success odds. |
| 2 | Player vehicle struct + pointer chain | No (entity-spawn entry points only) | Signature-scan Wine process for the 116-byte component records + 8×u32 armor tuple (save format ≈ memory layout, proven by leaked runtime pointers in saves). |
| 3 | Damage/collision events | No | Watch component `condition`/armor addresses from #2 for deltas; real damage-apply fn needs Gold RE (route: xrefs to damage-state mesh-swap fns). |
| 4 | savegame.dir / .cmp writer bug | No (`save_path_build` name only) | Gold Ghidra: xref `savegame.dir` / `save%03d` strings. Our `sprintf("save%03d",-1)` orphan-file theory already explains the missing-.cmp case. |
| 5 | input.map parser / axis vocabulary | No | Gold Ghidra: xref `joystick1` / `Throttle` / `Rudder` strings → device+axis tables = complete enumeration. |
| 6 | Force feedback effects | No | Skip RE; shim dinput.dll in the Wine prefix (proxy → rumble), or RE Gold imports later. |

---

# PART 2 — First-party findings on OUR GOLD i76.exe (2026-07-18, tools/exe-xref.py)

The Roanish anchor-string recipe, executed against the actual GOG Gold binary
with `tools/exe-xref.py` (string VA → embedded-pointer xref scan, no Ghidra
needed). Everything below is DIRECT from our own exe.

## The input-action table — FOUND and decoded (VA 0x4f2840..0x4f3000+, .data)

32 bytes per entry: `[name_ptr][state_VA][type][?][min][max][step?][flags]`.
`type 0` = analog channel (has min/max), `type 1` = held button, `type 2` =
press/toggle. **Column 2 is a static address holding the action's LIVE value**
— the entire input state lives in a fixed block at ~0x536770..0x536818,
readable AND writable by an external process (Cheat Engine / a future shim).

Highlights (full dump reproducible via the tool):

| action | state VA | type | notes |
|---|---|---|---|
| throttle | 0x5367cc | analog | |
| steer | 0x5367d4 | analog | |
| weapon_fire | 0x5367db | button | |
| **pilot_yaw_delta** | 0x536770 | **analog** | **UNDOCUMENTED — analog cockpit look!** min/max ±(0xa6/0xaa-ish) |
| **pilot_pitch** | 0x536778 | **analog** | undocumented, with `_plus/_minus/_reset` variants |
| **pilot_roll** | 0x536780 | **analog** | MW2 torso-twist heritage |
| pilot_glance_left..target | 0x536787–8b | button | the known digital glance |
| track_pitch_delta | 0x536794 | analog | min -10 max 10 |
| track_yaw_delta | 0x53679c | analog | ditto |
| **menu_item / menu_value** | 0x536808/0x53680c | **analog** | **native menu scroll channels** |
| **menu_enter / menu_abort** | 0x536816/17 | press | **native menu OK/back** |

Immediate consequences (experiments staged in the live input.map,
`input.map.pre-ghidra-experiments` backup):
- `pilot_yaw_delta { + mouse Left/Right }` + `pilot_pitch { + mouse Down/Up }`
  → if live, ANALOG COCKPIT HEAD-LOOK with zero memory hacking — the original
  head-tracking dream becomes an input.map two-liner + opentrack-to-vJoy later.
- `menu_item { + joystick1 Rudder }`, `menu_enter/abort { Button1/2 }` → native
  pad menu control, no AHK emulation tier needed for menus.
- Even if the parser refuses to bind them, the state VAs are direct write
  targets for an external feeder.

## Function anchors in Gold i76.exe (xref VAs, .text)

| subsystem | anchor string(s) | code VAs |
|---|---|---|
| input.map load/save | "input.map" | 0x44c2e6, 0x44cc1c, 0x44cc47, 0x44d194–0x44d22e cluster |
| device+axis parser | "Joystick", "Down/Up", "Left/Right", "Throttle", "Rudder" | 0x45019e, 0x4501e8, 0x4501fd, 0x45023b, 0x450257 (one function) |
| force feedback init | "FRC" | 0x446025 |

Note: `joystick1` is NOT a stored string — the parser stores bare `"Joystick"`
and must parse the digit suffix separately (VA 0x45019e neighborhood). The
bare-token-dead mystery is answerable by disassembling that one function.

## The save system is NOT in i76.exe

`savegame`, `save%`, `.dir` appear only in **i76shell.dll** (and
I76SHELL_1083.DLL). The savegame.dir truncation bug, the save-writer, and the
save/load boards all live in the shell module — future Ghidra session on the
DLL, not the exe. (Also neatly explains the shell-vs-sim input split that
keeps appearing in field tests.)

## Tooling

`python3 tools/exe-xref.py <exe> [anchors...]` reproduces all of this and
detects string-pointer tables at constant stride. Works on any of the era's
PE binaries (i76.exe, nitro.exe, i76shell.dll).

---

# PART 4 — First-party DISASSEMBLY of Gold i76.exe (2026-07-18, tools/exe-disasm.py)

Hands-on with capstone against our actual Gold binary. Anchor strings (PART 2)
→ xref to code → disassemble → read the memory operands. All DIRECT from our
exe. New tool: `tools/exe-disasm.py <exe> <VA> [count]`.

## CAMERA — full subsystem map, and the head-tracking write path CONFIRMED

**Cockpit look apply** (fn at ~0x406b00, reads the input-state block, writes camera):
```
fild [0x536770]   ; pilot_yaw_delta  (int input)
fild [0x536778]   ; pilot_pitch      (int input)
fild [0x536780]   ; pilot_roll       (int input)
... scale by consts at 0x4bc50c/0x4bc52c, clamp against 0x4bc548/50/80 ...
fstp [0x4c2964]   ; -> camera angle floats (the LIVE view orientation)
fstp [0x4c296c]
fstp [0x4c2970]
fstp [0x4c2974]
```
**Two head-tracking write targets, both external-writable, NO code patch:**
1. the integer inputs `0x536770` (yaw) / `0x536778` (pitch) / `0x536780` (roll)
   — exactly what an `input.map` analog binding feeds (experiments staged);
2. the computed float angles `0x4c2964 / 0x4c296c / 0x4c2970 / 0x4c2974`.
A feeder (opentrack→UDP→poke, or our AHK layer) writing these = head look.

**Camera state block** (from the init fn at 0x405a3f, which zeroes/defaults it):
| VA | meaning (inferred) |
|---|---|
| 0x4c2724 | camera active flag (set 1) |
| 0x4c2728 | **camera FSM mode** (int; switch values 2/5/9/0x1a) — which of F1..F11 view |
| 0x4c2908.. | camera struct region base |
| 0x4c2918 / 0x4c2928 | 0x3f060a92 ≈ 0.5236 (30° — default FOV/angle) |
| 0x4c2924 / 0x4c2934 | 0x40b00000 = 5.5 (default distance?) |
| 0x4c2964/68/6c/70/74/80 | **live camera angles/offsets** (yaw/pitch/roll + extras) |
| 0x4c2990..0x4c2a10 | camera-mode jump table, 8-byte entries [tag][fnptr], `call [edx*8+0x4c2994]` |

**Screen shake (target: vehicle impact shakes the view):** not yet pinned to a
writer, but the TARGET is now known — a damage/impact handler perturbing
0x4c2964..0x4c2974. A memory watcher can DETECT shake (and thus "I got hit")
by watching those floats jump, which directly drives impact rumble even before
we find the writer. The `pilot_glance_target` ("watch your target") path shares
this block — it's what proves continuous orientation exists.

## PLAYER CAR STRUCT — partial layout (from weapon-info fn ~0x409e40)

The car struct is large (>0xa738 bytes). Weapon layout within it:
- `car + 0xa71c` — array of weapon-instance POINTERS, stride 4
- `car + 0xa738` — array of 32-byte (0x20) weapon-instance RECORDS
The loop reads count from the struct, iterates both arrays in lockstep. Finding
the global **player-car pointer** is the remaining pointer-chain root (the
Roanish region agent is hunting the entity table; failing that, the .cmp save
layout ≈ in-memory layout gives a signature-scan path per PART 1 §4).

## FORCE FEEDBACK — state globals (from Forcefeed fn ~0x445ad3)

| VA | meaning |
|---|---|
| 0x52bbd0 | **FFB-present flag** — set to 1 when the SideWinder ("SWForce") object opens |
| 0x52bbcc | FFB object pointer (result of the create call via import [0x4bc110]) |
| 0x4f2314 | effect handle sentinel (init -1) |

Confirms the game only emits DirectInput FFB when it detects an FFB device — so
on Mac/Wine (no such device) the game-native FFB path stays dormant, which is
exactly why our SYNTHETIC XInput rumble (AHK, device-agnostic) was the right
call. A dinput-proxy shim could set 0x52bbd0 and harvest effects, but the
synthetic path already works.

## Scripting VM

`ammoLesser` etc. are I76 mission-SCRIPT opcodes (string→bytecode table near
0x4c316c; opcodes 0x21/0x22...), not C functions. The engine has a mission
scripting language — noted for completeness, not a memory target.

## Tools added
- `tools/exe-xref.py`  — string-VA → embedded-pointer xref + table detection
- `tools/exe-disasm.py` — capstone x86-32 disasm with .data/.rdata operand
  string-annotation. Both work on i76.exe, nitro.exe, i76shell.dll.

---

# PART 5 — Deep static map of Gold i76.exe (2026-07-18, autonomous session)

Systematic anchor→xref→disasm across gameplay systems. Confidence tags as before.

## VEHICLE component list — the spine (DIRECT, from component-finder ~0x4b6900)

The generic "find component of type N in vehicle" fn (shared by the
`Engine/Brake/Suspension %d not found in %s` errors) walks a per-vehicle
component array:
- `vehicle + 0x3c` = component COUNT (int)
- `vehicle + 0x40` = component ARRAY, **stride 0x20 (32 bytes)**, each record's
  **type-tag at +0x00** (engine/brake/tire/suspension/armor... are type codes)
Component records carry condition/health — the dashboard gauge color states
(`3engine_grn/ylw/red`, `3tire_grn/ylw/red`, `3brakes_*`) are driven by reading
a component's health and thresholding. So armor/engine/tire/brake STATE all
live in these 32-byte records; the exact health offset within a record is the
next runtime-scan target (trainer §scanner).

Component-access function cluster (callable / breakpointable):
`0x4b6900` engine, `0x4b6c98` rear tires, `0x4ada72`+`0x4b108b` generic-by-index.

## FORCE FEEDBACK — full chain (DIRECT, ~0x446040)

- The game loads FFB effect entry points BY NAME from an external effect module
  ("SWForce"): globals `0x52bbdc / 0x52bbe0 / 0x52bbe4` = cached effect fn
  pointers (I7FF_* names at 0x4f24d0/e0/f0).
- `0x52bbd0` = FFB-present flag (1 when device+module present), `0x52bbcc` =
  FFB object ptr (PART 4).
- **`0x4f2328` = the live effect PARAMETER block (0x16c = 364 bytes)** the game
  fills each update and passes to `I7FF_SIM_Effect`. Its first dword is set to
  0x16c (struct size). **Reading this block live = the game's own computed
  force stream (magnitude/direction/spring) — the ideal source to MIRROR into
  our synthetic XInput rumble** (real physics-driven FFB feel on a pad that has
  no DirectInput FFB). This supersedes guessing rumble from inputs.
- On Mac/Wine the SWForce module/device is absent so the flag stays 0 and this
  block isn't filled — but on Windows/Deck it is, and the mirror idea is live
  there; on Mac we keep the input-driven synthetic map.

## PLAYER → VEHICLE (DIRECT, ~0x4511a0)

Player→vehicle is a LOOKUP FN `0x4547c0(playerIndex)`, not a bare global; the
local-player index is the pointer-chain root to find at runtime. `0x455e60`,
`0x454750` are sibling player/vehicle helpers. dpDestroyPlayer / DirectPlay
confirm the player table is multiplayer-style indexed.

## RADAR / JAMMER / TARGET (function locations, DIRECT)

- `setUserRadar` fn @ `0x411da0` — radar range/mode state.
- `termJam` (ECM/jammer teardown) reached via table (no direct xref) — jammer
  state is table-driven.
- Target actions: `next_target/prev_target/frontal_target/target_nearest_enemy/
  reset_target/KILL_TARGET` all in the action table (PART 2 neighborhood); the
  current-target pointer is a per-vehicle field (runtime-scan target).

## WEAPON DEFINITIONS (DIRECT anchor)

`.45 Handgun` @ 0x4f8a30, referenced from `0x46ea35` — the weapon-definition
table (name → class/type/damage). `hardpointN_fire` actions map to the car's
weapon-instance arrays at `car+0xa71c` (ptrs) / `car+0xa738` (32B records,
PART 4). Hardpoint CONTENTS = walking those arrays once the car ptr is known.

## Mission SCRIPT VM

`ammoLesser`, `termJam`, `setUserRadar`, `SET_SPEED_*`, `KILL_TARGET`,
`DAMAGE_DEBUG_*` are mission-script opcodes (string→bytecode table ~0x4c316c).
The engine runs a scripting VM for mission logic — a whole subsystem, not a
memory target, but documents the full verb set.

## CONFIRMED external read/write targets (static, no code patch, ASLR-free 1997 PE)

| VA | type | meaning | use |
|---|---|---|---|
| 0x536770 | int | pilot_yaw_delta input | head-look (write) |
| 0x536778 | int | pilot_pitch input | head-look (write) |
| 0x536780 | int | pilot_roll input | head-look (write) |
| 0x4c2964/6c/70/74 | float | live camera Euler angles | head-look / read view |
| 0x4c2728 | int | camera view-mode (F1..F11) | read/set view |
| 0x52bbd0 | int | FFB present flag | read |
| 0x4f2328 | 364B | live FFB effect params | mirror→rumble (Win/Deck) |
| 0x536770..818 | block | full live INPUT state (every action's value) | read all controls |

NOTE (field 2026-07-18): binding `pilot_yaw_delta` to the mouse in input.map did
NOT visibly turn the head — the analog pilot_* actions appear NOT wired to the
file-binding parser (they're internal/script-driven). So head-look is a
MEMORY-WRITE feature (write 0x536770/78 or the angle floats), which is exactly
what the trainer does. The staged input.map experiment is left as documentation
but is inert; real path = trainer.

---

# PART 6 — Nitro Pack (nitro.exe) parallel map + machine-readable table

Same engine, shifted addresses. Verified structurally identical (the cockpit-
look function at Nitro 0x435c93 is byte-for-byte the Gold 0x406b00 logic):

| meaning | Gold i76.exe | Nitro nitro.exe |
|---|---|---|
| input-state block base | 0x536770 | 0x5348a0 |
| pilot_yaw / pitch / roll | 0x536770/78/80 | 0x5348a0/a8/b0 |
| throttle / steer input | 0x5367cc / 0x5367d4 | 0x5348fc / 0x534904 |
| cam_yaw (float) | 0x4c2964 | 0x4f38fc |
| cam pitch (float) | 0x4c2970 | 0x4f3908 |
| cockpit-look apply fn | 0x406b00 | 0x435c93 |
| action table | 0x4f2840 | 0x4f3d10 |

Full machine-readable map: **tools/i76-addresses.json** (both exes, globals /
functions / struct offsets, each tagged confirmed/struct/runtime). The trainer
(tools/i76-trainer.ahk) auto-selects the set by which exe is running.

## What is CONFIRMED vs what needs the runtime scanner

**Confirmed (static, ready to use):** the entire input-state block, all camera
angle floats + view mode, the FFB flag/object/param-block, and the vehicle
component-list + weapon-array *offsets*. These are usable the moment the game
runs.

**Needs the trainer scanner (runtime — a dynamic struct with no fixed global):**
the live player-vehicle base pointer (reached via lookup fn 0x4547c0), and thus
the absolute addresses of armor-per-facet, chassis integrity, gear, RPM, speed,
current-target, jammer state, and per-hardpoint contents. The offsets *within*
the vehicle/component structs are partly known (component array +0x40 stride
0x20; weapons +0xa71c/+0xa738); the scanner pins the base, then base+offset
gives the rest. Recipe: F9 first-scan the on-screen value (armor 100) →
take a hit → F10 next-scan (80) → repeat to 1-3 candidates.

## Head-tracking: the definitive path

The mouse-in-cockpit input.map binding is inert (analog pilot_* actions aren't
wired to the file parser). The working path is a memory feeder writing either
the int inputs (0x536770/78) or the camera angle floats (0x4c2964/0x4c2970).
The trainer's F7 test sweeps cam_yaw to demonstrate it live; production
head-tracking = opentrack/webcam → UDP → a writer poking those addresses at
frame rate. All addresses are in hand; only live validation + the feeder remain.

---

# PART 7 — LIVE validation + autonomous testing (2026-07-18)

Read/write against the running game (pid 316) via ReadProcessMemory across the
Wine boundary. All CONFIRMED live.

## Read validated
| field | addr | live value | note |
|---|---|---|---|
| PE header | 0x400000 | 0x5a4d 'MZ' | RPM works across Wine |
| view mode | 0x4c2728 | 7 | chase/track view |
| camera yaw | 0x4c2964 | −0.227 | real angle; head-track target |
| 50cal ammo | 0x25b0728 | 2000 | **matches HUD** |
| 7.62 turret | 0x25b0760 | 4000 | **matches HUD** |
| nitrous | 0x25b0bc0 | 3 | **matches HUD** |
| FFB flag | 0x52bbd0 | 0 | no DI device on Mac (expected) |

## Write validated (EDITABILITY)
Wrote 9999 to the 50cal ammo (0x25b0728) → read back 9999 → restored to 2000.
Memory writes hold. **Trainer editability confirmed.** Caveat: writing the
input-state weapon_fire (0x5367db) is overwritten by the game's per-frame input
poll, so you can't inject fire that way — direct value writes are the path.
NOTE: heap addresses (0x25bxxxx) are stable within a game run but re-allocate
on relaunch — scan (i76-mem-scan) each session or build a pointer chain.

## Save editor cross-validation → the armor encoding
`i76-save-editor.py --dump` on save015 reads armor exactly matching the DEFENSE
screenshot: front 91.0 / right 57.0 / left 57.0 / rear 70.0, chassis
70/40/40/55. Crucially it notes **"game shows tenths"** — armor is stored as an
integer scaled ×10 (91.0 = 910 internally in the SAVE). But scanning live memory
for 910/570/700 (int or float) found nothing, so the LIVE in-mission armor is
either a different encoding or the struct wasn't populated at dump time.
**Armor needs a damage differential** (below) — the one thing that needs the
player: dump, take a hit, dump, diff → the address that dropped is live armor.

## Music timing (lead, not yet pinned)
Music is **MCI-driven** (`mciSendCommandA`) triggered by the mission SCRIPT's
`playScene`/`playMovie` opcodes (script-VM handlers at 0x410ee6 / 0x4116c5).
`Music Level` (0x497fbe menu code) is the volume setting. To know live "is
music playing / which track", trace the `mciSendCommandA` IAT call sites for a
"current track" global — next dig. (This would replace inferring music state
with reading it, and let the trainer set music volume directly instead of
re-encoding the mp3s.)

## The differential recipe (to finish armor/live-ammo/speed)
```
1. i76-mem-dump.ahk            -> A.bin/A.idx   (dump now)
2. change the value in-game    (take a hit / fire / accelerate)
3. i76-mem-dump.ahk            -> B.bin/B.idx
4. i76-mem-scan.py A B <int|float>  -> the addresses that changed by the delta
```
Reliable, encoding-agnostic. The only step needing the player is #2.

## Efficiency note
dump(AHK, ~113MB in ~90s) + scan(Python, instant) is the right split — AHK's
interpreted per-offset scan was 50× too slow; the raw memcpy + Python pattern
match is fast. A compiled Win32 scanner would be marginally faster but the
bottleneck is now the differential (needs gameplay), not scan speed.

---

# PART 8 — Methodology: how to CONFIRM the map (and why single matches lie)

## The trap (demonstrated live 2026-07-18)
The HUD showed 7.62T ammo = 3739, 50cal = 1970 (distinctive numbers). A value
scan found each at exactly ONE address — looks definitive. It is NOT: both sit
inside a resource cache, bracketed by filenames (`sh82e_1m.pix`, `gtktank.gdf`)
and SEQUENTIAL ids (3737,3738,3739,3740,3741 at 40-byte stride). They are cache
entry indices that merely PASS THROUGH the ammo value. A single value match is
a coincidence generator, not proof. The earlier "capacity" table (0x25b0728 =
2000) matched max ammo but never depletes — also not the live count.

## The confirmation protocol (each hit must pass ALL)
1. **Progressive differential** — the core. Scan value N -> make a KNOWN change
   (fire exactly K rounds) -> re-scan the SAME candidate set for N-K (intersect,
   don't re-dump) -> repeat 3+ times. Only an address that tracks EVERY change
   survives. Re-reading candidates (not re-dumping) kills the heap-shift noise
   that ruined the two-far-apart-dumps attempt.
2. **Delta check** — the survivor moves by EXACTLY the action magnitude (fire 30
   -> −30; take a hit -> armor −(damage)). A coincidental id won't.
3. **Context filter** — reject candidates adjacent to ASCII/filenames/pointers
   (resource caches). Real gameplay scalars sit among other gameplay scalars.
4. **Write-back proof** — writing it changes the HUD (we proved writes hold).
5. **Pointer chain** — find a dword equal to the struct base, walk up to a
   STATIC global (0x4xxxxx/.data). static base + offset = a map that survives
   relaunch (heap addresses don't).
6. **Watchpoint (what-writes-this)** — winedbg/Cheat Engine hardware bp on the
   address; the writing function names the field and ties it to the static map.

## Completing the map = systematic coverage
Enumerate every KNOWN value (each weapon's ammo, the 8 armor/chassis facets,
speed, gear, RPM, current target, nitrous) as a differential target. Pin each
via 1-4, record its offset from the shared vehicle base (found via 5). When
every known lands in one struct at stable offsets, the vehicle map is complete;
repeat for camera (already static) and the entity table (for world objects).

## Why the tight loop needs one action from the player
Ammo/armor only change on fire/damage, and writing the input-state to
self-fire is overwritten by the game's per-frame poll. So the ONE human step is
making the known change between two scans. Everything else (scan, intersect,
delta-check, write-test) is automatable. The trainer's F9/F10 does this
interactively; `i76-mem-scan.py diff` does it from two dumps taken CLOSE together
(one small change between) — not the hours-apart dumps that produced noise here.

---

# PART 9 — Cheat Engine method + why static dumps hit their limit (2026-07-18)

Read the CE wikis (unknown-value scan; find-what-writes). Two things I'd skipped:

## The canonical method (encoding-agnostic)
1. **First scan = "Unknown initial value", type "All" (4-byte + Float + Double)** —
   never assume the encoding. (I had only tried 4-byte int + float; the CE
   tutorial stresses Double, and "display floats of value 1 are just the meter",
   confirming the display-vs-internal split.)
2. **Successive scans = decreased / increased / unchanged / changed** — purely
   relational, no value needed. Fire -> "decreased"; refill -> "increased"; idle
   -> "unchanged". Each pass intersects; converges in 4-6 rounds.
3. **Multiple survivors -> freeze one at a time**; the one whose change actually
   affects the game (not just the HUD) is the authoritative value.
4. **"Find out what writes this address"** (debugger data breakpoint) -> the
   writing instruction names the field and gives the pointer base. THIS is the
   definitive display-vs-internal disambiguator.

## Why our headless dump-diff stalled on live ammo
Tested B->C (7.62T fired 18, HUD 3739->3721) at every stable VA: NO 4-byte int,
float, integral-float, x10-scaled, OR double carries a 3739->3721 (or +18
counter) transition. Ruled-out cleanly. Two structural reasons static dumps
can't finish this target:
- **Relocation**: dumps B and C are separate processes minutes apart with heavy
  gameplay between; the weapon/vehicle struct re-allocates, so cross-dump VA
  matching breaks (the cache-index coincidences at 0x04b1xxxx were the only
  "stable" 3739s, and they're not ammo). CE avoids this by doing rapid
  successive scans in ONE attached session before anything relocates.
- **No debugger**: static dumps CANNOT do "find what writes this address" — the
  single most reliable technique, and the only airtight way to separate the
  authoritative ammo from its display copy. That needs a live debugger.

## Verdict: the right tool for the LIVE dynamic values is Cheat Engine under Wine
Our static/dump toolkit already NAILED everything that IS static (camera,
input block, view mode, FFB flag, struct offsets — all live-validated). The
remaining targets (live ammo/armor/gear/speed) are dynamic heap values that
want CE's live successive-scan + find-what-writes. Recommended workflow:
1. Install Cheat Engine into the prefix (`drive_c`), launch under the same Wine.
2. Attach to i76.exe. First scan: Unknown initial value, type All.
3. Fire a known burst -> Next scan: Decreased value. Idle -> Unchanged.
   Repeat 4-6x until <10 addresses.
4. Freeze each; the one that changes GAMEPLAY (not just the dial) is real.
5. Right-click -> "Find out what writes this address" -> the instruction +
   register/base gives the pointer chain; cross-ref to our static function map
   (weapon_info_in_car 0x409e40, component finder 0x4b6900) to name the field
   and anchor it to a static global for a relaunch-proof map.

(We do NOT auto-download/run CE here — that's the user's call; the workflow and
the static anchor map to tie results back to are in this repo.)

---

# PART 10 — winedbg attaches on Mac Wine; live vehicle base resists static methods

## winedbg IS available and attaches (2026-07-18)
`winedbg.exe` ships in the prefix (and fuller copies in the other Sikarugir
game bundles). `printf 'info process\nquit\n' | wine winedbg` cleanly lists
i76.exe (pid 0x13c, 8 threads) — the debugger connects to the game's wineserver
and the game survives attach/detach. BUT: memory reads fault under this Wine's
**wow64** mode (`x/4xw 0x4c2964` -> "page fault ... in wow64 32-bit code") —
winedbg attaches in the 64-bit host context and doesn't cleanly resolve the
32-bit game VAs. So its one unique value over our AHK reader (breakpoints /
find-what-writes) is blocked here without a non-wow64 (pure 32-bit) Wine build.
Our AHK ReadProcessMemory already reads 32-bit game memory perfectly, so reads
are covered; the debugger unlock would need a wow64-capable winedbg invocation
(`--32` / a 32-bit wine) — an open lead, not a dead end.

## Refined vehicle offsets (static, confirmed)
- weapon COUNT: `vehicle+0xa718` (was noted 0xa71c; +0xa718 is the count,
  +0xa71c the ptr array, +0xa738 the 32-byte records)
- component list: count `+0x3c`, array `+0x40` (stride 0x20)

## The live vehicle base pointer: honest status
Tried, autonomously, all of: value scan (coincidental resource-cache IDs),
cross-dump differential at every encoding int/float/double/scaled/counter
(RELOCATION — no stable VA carries the transition), static pointer chain (the
0x541070 table is DirectPlay/multiplayer, empty in single-player; weapon fns
receive the vehicle as a parameter, not from a global), structural signature
(false positives — matched a float/transform struct), and winedbg (wow64
read fault). **The single-player local-vehicle base is not reachable by these
static/headless means without more work.**

Two paths actually finish it, both standard practice:
1. **Live differential with one human action** (the CE method): while playing,
   fire a KNOWN burst / take a hit between two scans; the value that moves by
   the exact delta is real. Our tools/i76-trainer.ahk F9/F10 (in-process, so no
   relocation between scans) is built for this — it just needs the player to
   make the change. This is not a tooling gap; the CE health tutorial itself
   requires the player to change the value.
2. **A pure-32-bit winedbg or Cheat Engine session** for find-what-writes /
   pointer-scan, tied back to the static function map (weapon_info 0x409e40,
   component finder 0x4b6900, player-table +0x28).

Everything STATIC is done and live-validated (camera, input block, view mode,
FFB, all struct offsets). The remaining live scalars are, by the nature of the
problem, a human-in-the-loop differential — exactly what the wikis describe.

---

# PART 11 — DEBUGGER SOLVED: launch-under-winedbg works (attach doesn't)

The find-what-writes blocker is cracked. The distinction is attach vs launch:

## Attach to a running process = DENIED (macOS)
`wine winedbg <pid>` or `winedbg 0xNNN` on the already-running game returns
**"Can't attach process: error 5"** (ACCESS_DENIED) — macOS blocks debugger
attach (task_for_pid / ptrace) to a process the debugger didn't create, without
special entitlements. Memory *reads* via attach also page-fault under wow64.
(Our AHK ReadProcessMemory works because it uses wineserver-mediated reads, not
debug control — no ptrace needed.)

## Launch the game UNDER winedbg = FULL DEBUG CONTROL ✓ (verified 2026-07-18)
```
wine winedbg "C:\GOG Games\Interstate 76\i76.exe"
```
The debugger CREATES the process, so it has debug rights from the start. Verified:
- stops at the ntdll entry stub before the game runs
- `break *0x406b7c` -> "Breakpoint 1 at 0x00000000406b7c i76+0x6b7c"  ← accepted
- `info reg` -> clean 32-bit registers (EIP/ESP/EBP/EAX...), NO wow64 fault
- use `cont` (not `run` — launch already attached)
So breakpoints + 32-bit registers + memory all work in launch mode. This is the
find-what-writes / watch-the-write capability, working on macOS Wine.

## The find-what-writes workflow (to get the vehicle base + offsets)
1. Launch i76.exe under winedbg (ideally in a throwaway prefix copy, or coordinate
   so it doesn't fight the user's DxWnd display — a 2nd raw instance tries its own
   DirectDraw; it won't crash the user's game but won't render cleanly either).
2. Get into a mission (vehicle exists).
3. Find a live vehicle field once (differential in THIS instance), then:
   `watch *0x<ammoaddr>`  -> `cont`  -> on write, `info reg` + `bt`.
   The writing instruction's base register = the vehicle base; the displacement
   = the field's offset within the vehicle struct. That OFFSET is identical in
   every instance (same code), so it maps the user's live instance too.
4. Or break at weapon-access fn 0x414ef0 (vehicle in [esp+0x68]) / cockpit-look
   0x406b00, read the vehicle base live, then dissect base+offsets.
5. Trace the base register back up the call chain (or `watch` the global that
   holds it) to a STATIC global -> relaunch-proof static->offset map into
   tools/i76-addresses.json.

## Safe-execution note
A debug instance in the SHARED prefix coexists with the user's game (different
wineserver pids) but competes for the display; run the live watch either when the
user's session is paused or from a cloned prefix. The CAPABILITY is proven; the
live watch is a coordinated step, not a blocker.

---

# PART 10 — Player table + pointer-chain progress (fable session, 2026-07-18)

Static disassembly of `player_vehicle_lookup` (0x4547c0) revealed a **static
player-record table** and its shape:
```
mov  eax, 0x541070          ; table base
cmp  word ptr [eax], dx     ; entry+0x00 = player id (WORD), matched vs arg
add  eax, 0x48              ; stride 0x48, 16 entries (ends 0x5414f0)
...
mov  eax, [ecx*0x48 + 0x541098]  ; vehicle POINTER = table + slot*0x48 + 0x28
```
**Table: base 0x541070, 16 records x 0x48 bytes; per record: player id WORD @+0,
vehicle pointer @+0x28** (i.e. the pointer array starts at 0x541098). So in
theory the local car pointer is `[0x541070 + slot*0x48 + 0x28]`.

**BUT live read shows this table is entirely ZERO in single-player** — it is the
**DirectPlay / multiplayer** player table (cf. dpGetPlayerData / dpEnumPlayers /
"No vehicle sent for player %d" at 0x4511a0, which calls this lookup). In SP the
local car is reached by a different root, still to be found. This is a genuine
find (the MP record shape) and a documented dead-end for the SP pointer chain.

**Live-ammo lead (reconfirmed dynamic):** `0x25b0760` read 4000 earlier and
**3976 now** — it CHANGES, so it is not static capacity; it is a live-decreasing
value (candidate live ammo / a per-weapon counter). `0x25b0728` held 2000 across
both reads. These two are NOT both capacity; at least one tracks live state.
Correlating them to the exact HUD numbers (needs the current on-screen values)
will confirm which weapon each is — the cleanest remaining single-player hook.

**Next step (highest yield):** find the SP local-car global. Two routes:
(a) pointer-scan a fresh dump for a static (.data, 0x4xxxxx/0x5xxxxx) dword that
points into the car/ammo heap region (~0x25b0xxx) — that dword is the root; or
(b) the conclusive one — CE/x64dbg **inside the wineprefix**, set "find what
accesses 0x25b0760", and the accessing instruction's base register + the call
stack give the car struct and its static root in one shot.

---

# PART 11 — THE LINK: entity → vehicle-logic object (cross-thread handoff)

Connects the live-verified player-entity chain (`player_entity =
[[[0x54a264]]+0x70]`, with +0xe0 steer / +0xe4 throttle) to the weapon/component
data by reading `ammoLesser`'s accessor calls (static, i76.exe):

- `0x467440(obj)` returns **`[obj+0x70]`** — the entity (same +0x70 as the
  entity chain; confirms it).
- `0x466e30(entity)` does `fld [entity+0xe0]` — reads the **steer** float,
  confirming the entity's +0xe0 = steer label.
- `0x466e20(entity)` returns **`[entity+0x108]`** — **the vehicle-LOGIC object.**

ammoLesser then reads, off that logic object:
`[logic+0xa718]` = weapon count, `[logic+0xa71c + i*4]` = weapon[i] pointer.

### Full chain to ammo / armor / components (single-player)
```
world_ctx   = [[0x54a264]]                 (0x457530 returns [0x54a264]; also used by camera-init 0x405a3f)
player_ent  = [world_ctx + 0x70]           (main-thread live-verified; +0xe0 steer, +0xe4 throttle, +0x08 transform)
logic_obj   = [player_ent + 0x108]         (THIS PART — the "car" with weapons+components)
  weapon_count   = [logic_obj + 0xa718]
  weapon[i] ptr  = [logic_obj + 0xa71c + i*4]      -> ammo is a field INSIDE weapon[i]
  component_cnt  = [logic_obj + 0x3c]
  component[k]   =  logic_obj + 0x40 + k*0x20       (type-tag @+0; armor/chassis/engine/tire health here)
```
Remaining unknowns (one watchpoint each, or a scan now that the base is a fixed
pointer walk): the **ammo offset inside weapon[i]** (plain int32 countdown per
Open76) and the **health offset inside a component record** (int tenths per the
save editor). With `logic_obj` reachable by pointer walk, these are stable
base+offset reads — no more wandering-address scans.

**For the live thread:** verify `[[[0x54a264]]+0x70]+0x108` points to a struct
whose +0xa718 is a small int (weapon count ~4-6) and +0xa71c is a heap pointer;
then dump weapon[0] and diff a one-shot fire for the −1 to fix the ammo offset.
