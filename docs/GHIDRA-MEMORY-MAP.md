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
