# Mount validation: what decides whether an equipped item stays mounted when a save loads

Static reverse-engineering, 2026-10-02. Targets: pristine GOG `i76shell.dll` (md5 `deb41008…`, VAs at base
0x10000000, capstone via `..\i76-map\shell\tools\sdis.py fn <va>`) and `i76.exe` (md5 `9a232dcc`, Ghidra
decompilation `..\i76-map\ghidra\export\functions\004b58a0.c` etc.). No game was run. Closes BACKLOG P1-12 /
SAVES-STATE H10 on the static side; section 6 is the sandbox test that settles the two field claims.

Tags: **[static]** = read from an instruction or a decompiled body at the cited address; **[inferred]** = the meaning
I attach to it, not yet observed live.

## 0. The short answer

1. **There is no "mount class" field in the save and no class check at load time.** The 14 names at `.cmp` offset
   1024 (`GarageRec+0x400`, stride 0x1e) are only *labels*. Every garage and mission path rebuilds the loadout by
   **matching those labels against part records by display name**; a label with no matching record is treated as
   `EMPTY`. That is the whole "silent unmount" mechanism. [static]
2. **The only fit rule is for turret-class weapons** (any `t*.gdf`, GDFC `sub >= 100`): such a weapon may sit only on a
   hardpoint whose VDF HLOC `meshType == 1`, and the car may carry **at most one**. The garage enforces it on
   **DONE** (`Garage_ValidateCar` 0x10007340) with an error popup and refuses to leave; the exe enforces the same rule
   on a multiplayer join (0x4b3aa0, flag 0x8000). Neither strips the part; the garage refuses, the join is rejected.
   [static]
3. **Failed labels are not moved anywhere.** The part record stays in section A of the `.cmp` with whatever state it
   had, and still lists under (C) in the inventory (if its state is not 4) or under the van/salvage pane (state 4).
   Only the hardpoint row loses it; on DONE the slot label is rewritten to `EMPTY`, and `vehscn.vcf` (the car the
   mission actually loads) simply has no WEPN for it. [static]
4. **The "13 small u32s @2148" are the hardpoint table**: `+0x864` = hardpoint count, then `{HLOC index, facing,
   meshType}` per hardpoint from `+0x868` (4 × 3 + 1 = 13 for the Piranha). This is the table the turret rule reads.
   [static]
5. **Slot order is HLOC order, and for the Piranha the first weapon slot is the dropper.** Piranha hardpoints:
   0 = dropper (meshType 4), 1 = "Top" (meshType 5), 2 and 3 = "Fwd" (meshType 1, the only turret-legal mounts).
   So editor "weapon 1" (slot k=7) is a type-8 dropper slot, not a gun slot. [static, from `vppirnha.vdf`]

## 1. Where the equipped names come from (exe callback slot 05, `LoadVcfIntoGarage` 0x4b58a0)

The 0x8c4-byte GarageRec that heads every `.cmp` is built by the exe from a `.vcf`/`.vdf` pair
(`shell\work\exe-callbacks.md` slot 05; decompilation `ghidra\export\functions\004b58a0.c`). The parts that matter
here [static, decomp]:

| GarageRec field | written as | from |
|---|---|---|
| `+0x3c` | slot count (3 components + wheels + hardpoints + non-zero specials) | |
| `+0x40 + k*0x20` | slot record `{type u32, label char[16], ui_x u32, ui_y u32, 0}` | |
| slot type for k = 0,1,2 | 2 ENGINE, 3 SUSP, 4 BRAKE | fixed |
| slot type for wheels | 5, label "WHL FR/FL/MR/ML/RR/RL", only where the VCF names a wheel pair | VCFC +0x36/+0x43/+0x50 |
| **slot type for hardpoint i** | `meshType 4 -> 8` (dropper mount); `meshType 6 -> facing 3 ? 10 : facing 4 ? 9 : exit(0)`; `meshType 3 -> 0xb`; **anything else (1, 2, 5) -> 7** (gun mount) | HLOC +0x18 meshType, +0x14 facing (R+0x378+i*0xfc +0xb8/+0xb4) |
| `+0x400 + k*0x1e` name for hardpoint i | `StrLookup(gdf name)` = the weapon's display name, or `"EMPTY"` when the WEPN name at R+0x3c8+i*0xfc is empty | the VCF WEPN whose hardpoint id matched HLOC index (0x4af250, scan at 0x4af296) |
| `+0x784 + k*4` for hardpoint i | **HLOC index** (R+0x378+i*0xfc+0xb0) | the id the WEPN chunk must carry |
| `+0x864` | hardpoint count | VDFC +0x3c |
| `+0x868 + 12*i` | `{HLOC index, facing, meshType}` | HLOC +0x10/+0x14/+0x18 |
| specials k | type 0xc + string-table name, or type 0 / "" for an empty SPEC | VCF SPEC |

Stock corpus: meshType ∈ {1, 2, 4, 5}, facing ∈ {1, 2} (`..\i76-map\data\notes\vdf.md` §11), so the only slot types
that occur in stock data are 7 and 8; types 9/10/11 are reachable in code but never produced. [static]

Catalogue side (exe slot 00 `BuildPartsCatalogue` 0x4b4c10 -> weapon entry 0x4b5470): each weapon PartRec (0x54 bytes,
`parts_catalog` 0x100c6288) gets `+0x1e type` from GDFC class — 1 handgun -> 9, 2/3/4/5 (slug/mortar/SPP/flame) -> 7,
6 dropper -> 8, else `exit(0)` — and **`+0x22 = 0xb` when GDFC `sub >= 100`** (turret variant), 0 otherwise.
`+0x00` = display name (StrLookup), `+0x2e` = class id ("slg02"), `+0x3b` = gdf file, `+0x4c` = max HP, `+0x50` = mass.
EMPTY placeholders are one per type {2,3,4,5,7,8,9,10,0xb,0xd} (0x4b62b0). [static, decomp]

## 2. The rule table

| slot type (GarageRec+0x40) | what is compared | left side (save) | right side (data / runtime) | failure outcome |
|---|---|---|---|---|
| 7 gun mount, 8 dropper mount — garage rows | slot name vs part display name, **and part record state == 1** | `GarageRec+0x400+k*0x1e` | (C) weapon list `0x100d1db4` = section-A records of type 7/8 with state != 4 (`Inventory_ClassifyParts` 0x1001991c..0x10019960, cap 11); match `_stricmp` 0x1001adbb (gun rows) / `strcmp` 0x1001af2b (dropper rows); state test `cmp [node+0x10],1` 0x1001add3 / 0x1001af6b | row shows the EMPTY placeholder 0x100432c0 (0x1001ae69 / 0x1001afa3); on DONE `GarageRec_InstallPartLists` 0x1002d650 writes the row set back: the slot name becomes `"EMPTY"` (0x1002d7c1.., 0x1002c906). Record untouched. [static] |
| 7 gun mount, turret-class part (`PartRec+0x22 == 0xb`) | hardpoint meshType must be 1; at most one turret | mount-row index -> hardpoint id (`0x10052018` table, built by `Garage_BuildMountLabels` 0x10006280 from `+0x868+12i`) | `GarageRec+0x870+12*hp` (`cmp [..0x10058a10],1` at 0x10007535) | DONE refused: `Modal_ImageOk` art 0x1c at 0x1000757b (wrong mount) or 0x1a at 0x1000755f (second turret); garage stays open. [static] |
| 7/8 — mission car | slot name vs part display name (`strcmp`, exact) | `+0x400` names of slots whose type ∈ {6,7,8,0xb} (`FUN_100342f0`) | the same list `0x100d1db4` (ring-derived in the garage path; **catalogue-derived** on the bookmark-load branch that writes the vcf before any screen: `PartPool_BuildFromCatalogue` at 0x1001347f) | no WEPN chunk written for that slot (`GarageRec_CollectInstalledParts` 0x100338d0 inserts nothing; `Vehicle_WriteVcf` 0x10035250 loops the collected list only). Hardpoint id written = `+0x784[slot]` found by name (0x100356b0, 0x1003591c); a name found in the list but in no slot gets hardpoint 0 (0x100356d1). [static] |
| 7/8 — in-game spawn | WEPN hardpoint id vs VDF HLOC index | WEPN +0 | HLOC +0x10, scan 0x4aec5f | weapon skipped (0x4af21f returns 0); no class check in the spawn path beyond forcing turret geometry to location 3 (0x4aec96). [static, `data\VEHICLES.md`] |
| 7/8 — multiplayer join | gdf name; `sub >= 100` needs meshType == 1; no two turrets; forbidden gtktank/gtptank/tthowitz | WEPN | global HLOC copy 0x5db190 (+0x44 meshType) | flags 0x2000 / 0x4000 / 0x8000, "hacked vehicle", player dropped (0x4b3aa0). Same turret rule as the garage. [static] |
| 2/3/4 engine/susp/brake | slot name vs component PartRec name; file must not be "null" | `+0x400` | lists `0x100d1dac/dc0/dbc`; `GarageRec_FindInstalledPart` 0x100337b0 | DONE refused with popup 0x15/0x16/0x17 (0x10007364..0x100073c7); vcf gets component id `atoi(PartRec+0x31)-1` (0x1003533e) — an unmatched name yields the EMPTY placeholder and id -1. [static] |
| 5 wheels | rows 3..4 and 5..6 non-null and same `.wdf` within a pair | `+0x400`, `+0x83a/+0x847/+0x854` | list `0x100d1db8` | DONE refused with popup 0x18 (missing) / 0x1b (pair mismatch), 0x10007406..0x100074df. [static] |
| 0xc specials | slot name vs special PartRec name | `+0x400` | list `0x100d1db0`, predicate `FUN_10034380` (type ∈ {0,0xc,0xd}) | `GarageRec_InstallPartLists` 0x1002d8d4.. rewrites; vcf SPEC = `atoi` of the record's file digits (0x10035842). [static] |

Mount-row labels, so a screenshot can be read against the table [static, jump table bytes at 0x100064cc]:
meshType 1 or 3 -> "Fwd #n" (0x10006302); meshType 2 or 5 -> facing 1 "Rear #n" (0x100063f2) / facing 2 "Top #n"
(0x1000639b); meshType 4 -> "Dropper #n" (0x10006358). Mount table order: Rear rows, then Fwd rows, then Top rows
(0x1000648b..0x100064bd). **Only "Fwd" rows born from meshType 1 accept a turret.**

Part record states (PartNode +0x10), as the garage writes them [static]: 1 = mounted (`Garage_WeaponPickerClose`
sets 1 at 0x10006772 on install), 2 = owned, not mounted (set at 0x100067c6 on uninstall), 3 = in the repair list,
4 = van/salvage pane (`Inventory_ClassifyParts` sends state 4 to the `0x100d1df0..` lists and demotes the 12th and later
(C) weapons to 4 at 0x10019952). `cmp-layout.md`'s "loc flag" at record +100 is this field (the record is written
node-first; the editor's framing is 0x20 bytes late).

## 3. The load paths, with what each one does to the names

`Screen_LoadBookmark` 0x10013380 [static]:

1. `[player+0x38]=0`, `RepairOrder_Delete`, `PartPool_Free`, `Inventory_ResetState`, then `Cmp_Read` 0x10032bf0:
   the 0x8c4 GarageRec is `fread` verbatim into slot 0 (names, slot types, `+0x784`, `+0x864..` all come from the
   file, nothing is recomputed), section A becomes the ring `0x100cc500`, section C the repair list.
2. Branch on the restored scene and the dir entry's flag word `[0x10057a20]`:
   - scene 16 with `+0x34 == 1` -> 0xC00D (end of trip).
   - **flag bit 2 set** (0x1001345d; it is the Play-Options mask bit 2 saved at bookmark time, SAVE.md §1) ->
     `BuildPartsCatalogue`, `PartPool_BuildFromCatalogue` (**six lists = every catalogue part, fresh, state 1**),
     `Vehicle_WriteVcf("addon\vehscn.vcf")`, `Vehicle_WriteVehState`, set `[0x100cc858] |= 2`, post **0xC015**
     (post-mission form). On that form's GO (`PostMission_Frame` 0x100246e0 region 0, 0x10024753): with bit 2 set the
     GarageRec is **reloaded from the stock scene car `vppt%02d.vcf`** (slot 05 at 0x100247b2, scene = stored scene,
     +1 when `+0x34 == 1`), the vcf is rewritten from it, `Garage_LoadWorkingCar`, then 0xC010 = start the mission.
   - scene 12 -> 0xC015 as well; its GO uses the current GarageRec only if the category lists exist (0x10024812),
     otherwise the vppt reload again.
   - **anything else -> 0xC017 `Inventory_Open`** (the ordinary garage bookmark). `Inventory_BuildLists` ->
     `Inventory_ClassifyParts` buckets the ring into the six (C) lists and six van lists by type and state. The garage
     (0xC00F `Garage_Open` -> `Garage_InitLists` -> `Garage_RefreshLists` 0x10005310 -> `Garage_BuildMountLabels`; row
     hooks `InvHook_RebuildMountLists` 0x1001ac80 / `InvHook_FillMountLists` 0x1001a810) fills each hardpoint row from
     the first **state-1** (C) record whose display name equals the slot label. DONE -> `Garage_ValidateCar` ->
     `GarageRec_InstallPartLists` (rows -> `+0x400`) -> `Cmp_Write("reconfig.spc")` / `Vehicle_WriteVcf`.

Post-mission return (`Screen_EnterReconfig` 0x10002750) [static]: `Cmp_Read("reconfig.spc")`, then slot 05 reloads
`vehscn.vcf` (the shell's own pre-mission write) into the GarageRec at 0x1000296e, slot 06 reads `vehscn.vsf` with the
salvage callback, `Garage_LoadWorkingCar` 0x10002130 pairs each slot name with the first catalogue entry matching its
first 15 chars (`strncmp(...,0xf)` 0x10002264; **no match leaves the node pointing one past the catalogue**, a latent
bug for unknown names), `VehState_ApplyToWorkingCar` applies the per-weapon states. A weapon that never got a WEPN
(name unmatched before the mission) is therefore absent after it too.

**Where the two field observations most likely come from** [inferred]:

- "turret-class guns on the Piranha are unmounted to Empty": the garage path cannot strip by class — it would show the
  turret on the row and refuse DONE with popup 0x1c. An EMPTY row means the **name/state match failed**: the label at
  `+0x400` was not byte-equal (`_stricmp` for gun rows, so case is forgiven but spelling and padding are not) to a
  section-A record's display name whose state was 1 — e.g. the editor's catalogue spelling differs from the game's
  string-table name, or the record was written with state 2/3/4. The record then still lists under (C), which is exactly
  the "(C) rows for records the equipped block doesn't name" seen on 2026-07-14.
- "pool weapons auto-mounted into empty validated hardpoints": that is the `vppt%02d.vcf` reload. Stock
  `vppt01..17.vcf` carry a scripted Piranha loadout per scene (vppt16 = `gfirdrop, gcmedium, tmheavy, gcluster`;
  vppt17 = `gfirdrop, gmheavy, tmheavy, gsradar`; parsed from the recon corpus), which matches "7.62 / cluster showed
  up uninvited" and also puts the turret `tmheavy` on hardpoint 2 (meshType 1), consistent with the rule. It
  runs when the bookmark's dir flag bit 2 is set or when the load goes through the post-mission form.

## 4. What a save editor must check before writing an equipped name

Checks, in the order the game applies them [static unless marked]:

1. **Slot type first.** Read `GarageRec+0x40+k*0x20`. Write a gun (`g*.gdf`, class 2..5) only into type 7, a dropper
   (class 6) only into type 8, components/wheels/specials only into 2/3/4/5/0xc. The editor's "weapons x4" are
   slots 7..10 in HLOC order; on the Piranha slot 7 is the type-8 dropper mount.
2. **Turret rule.** If the gdf's GDFC `sub` (body +0x14) >= 100: hardpoint `h = GarageRec+0x784+k*4`; require
   `GarageRec+0x870+12*j == 1` where `j` is the triple with `+0x868+12*j == h`; and no other slot may already hold a
   turret. Piranha: only slots 9 and 10 (hardpoints 2, 3).
3. **The label must be the game's display name**, byte-exact up to case. Take it from a game-written save (the editor's
   "seen" names) or from the string table, never from a hand-typed variant. 30 bytes, NUL-padded.
4. **A section-A record must exist with the same display name and state 1**, otherwise the row is EMPTY and the name is
   lost on the first DONE. Keep the non-state-4 weapon count <= 11 (0x10019945) or the extras drop to state 4.
5. The record's `+0x3b` file must be the real gdf (it is what `Vehicle_WriteVcf` copies into the WEPN), and the WEPN
   hardpoint id comes from `+0x784[k]` — do not touch `+0x784` or `+0x864..` unless the chassis changes.
6. [inferred] If the dir entry's `+0x38` has bit 2 set, warn: the load will go through the post-mission form and the
   scene's `vppt` car can replace the loadout.

Python sketch (reads the same bytes the game reads; `GDFC` offsets per `..\i76-map\data\notes\gdf-wdf-xdf-vtf.md`):

```python
import struct

def chunks(b):                      # BWD2: tag[4], u32 size (incl. header), body at +8
    i = 0
    while i + 8 <= len(b):
        tag, size = b[i:i+4], struct.unpack_from('<I', b, i+4)[0]
        yield tag, b[i+8:i+size]
        i += size if size >= 8 else 8

def gdf_class_sub(gdf_bytes):
    for tag, body in chunks(gdf_bytes):
        if tag == b'GDFC':
            return struct.unpack_from('<ii', body, 0x10)   # class, sub
    raise ValueError('no GDFC')

def hardpoints(cmp):                # GarageRec+0x864: count, then {hloc_index, facing, meshType}
    n = struct.unpack_from('<I', cmp, 0x864)[0]
    return {struct.unpack_from('<III', cmp, 0x868 + 12*i)[0]: struct.unpack_from('<III', cmp, 0x868 + 12*i)[1:]
            for i in range(n)}

def can_mount(cmp, k, gdf_bytes, name, records):
    """k = slot index (0-based into the 14 x 0x1e names); records = [(display_name, state), ...] from section A."""
    slot_type = struct.unpack_from('<I', cmp, 0x40 + k*0x20)[0]
    cls, sub = gdf_class_sub(gdf_bytes)
    want = 8 if cls == 6 else 7
    if slot_type != want:
        return False, f'slot {k} is type {slot_type}, part needs {want}'
    if sub >= 100:
        hp = struct.unpack_from('<I', cmp, 0x784 + k*4)[0]
        facing, mesh = hardpoints(cmp)[hp]
        if mesh != 1:
            return False, f'turret on hardpoint {hp} (meshType {mesh}); needs meshType 1 (Garage_ValidateCar 0x10007535)'
    if not any(n.lower() == name.lower() and st == 1 for n, st in records):
        return False, 'no section-A record with this display name and state 1: the row will read EMPTY'
    return True, 'ok'
```

The turret-count rule (one per car) and the 11-weapon (C) cap are one-liners over the same inputs and are left out
for brevity.

## 5. Does the garage's own UI use the same rule?

Partly [static]:

- The weapon picker (`Garage_OpenMountPicker` 0x10006b70 kind 1 -> `Garage_WeaponPickerDrawRows` 0x10006810) lists the
  whole available-gun list `0x100520b0` for every gun row; it does **not** filter turrets by the row's meshType. The
  dropper picker (kind 2, list `0x100520b4`) is the type-8 list, so type is enforced by construction.
- The fit rule is applied once, on DONE, by `Garage_ValidateCar`, and the only failures it knows are: no engine /
  suspension / brakes (0x15/0x16/0x17), a missing or mismatched wheel pair (0x18/0x1b), a turret on a non-meshType-1
  mount (0x1c), two turrets (0x1a). It never checks a name against a slot type: that is done by which list a row draws
  from.
- So the garage and the loader agree on the *turret* rule and both resolve parts by display name; the loader is simply
  more permissive in that it will accept any label and let the garage discover the mismatch.

## 6. Live verification plan (sandbox `..\i76-uncap-lab\game`, console session only)

Use a garage bookmark (state 8, loads straight into 0xC017) from the lab set, copied, with a `savegame.dir` entry whose
`+0x38` flag word has bit 2 **clear**. Prepare two variants with the editor or a 20-line struct patch:

1. **Edit.** Variant A: slot k=8 (hardpoint 1, "Top", meshType 5) name = the game's display name of `tcmedium.gdf`
   ("25mm Turret" per the editor catalogue — confirm against the string table before writing), plus a section-A record
   `{name, type 7, +0x22 ignored on disk, file tcmedium.gdf, state 1}`. Variant B: the same turret in slot k=9
   (hardpoint 2, meshType 1). Record `+0x400` names, `+0x40` types, `+0x784` ids and the `+0x864` table of both files
   (expected unchanged from the source save), and re-pad the dir.
2. **Load and read back.** Boot the sandbox at the console (`query session` shows `>console`), Load Bookmark -> the
   inventory -> garage. Capture the Build & Repair form (`Capture-UI`) and read, with `memlib.ps1`: the live GarageRec
   (`i76shell.dll` base + 0x581a0: names at +0x400), the mount-row list `0x100520a4` (each entry -> PartRec name at +0,
   node state at +0x10), and `[0x100520a4]` indices against the mount table `0x10052018`. Expected: A and B both show
   the turret on its row (name match, state 1). Click DONE: A must raise popup art 0x1c and stay in the garage; B must
   leave the garage. A row reading EMPTY on either variant means the name/state match failed, which is the editor-side
   bug of section 3 — fix the spelling or state and repeat before concluding anything about classes.
3. **Diff the outputs.** For B: Save Bookmark, parse `ADDON\vehscn.vcf` (`..\i76-map\data\mod\i76mod.py show`) and expect
   `WEPN{2, tcmedium.gdf}`; diff the new `.cmp` against the input (names unchanged, record state 1). For A: uninstall
   the turret on the row, DONE, Save Bookmark; expect `+0x400[8] == "EMPTY"`, the record still in section A with
   state 2, and the (C) pane still listing it. Then the auto-mount check: load the same bookmark with dir `+0x38` bit 2
   **set**, GO on the post-mission form, open the garage, and compare the (C) weapons with
   `vppt<scene>.vcf`'s WEPN list — a match confirms the vppt reload as the "uninvited weapons" source.

## 7. What is missing from the exports, and the best inference where it matters

- The shell Ghidra export has decompiled bodies for only 14 functions; everything above in `i76shell.dll` was read
  from capstone listings (`sdis.py fn`), so the instruction addresses are exact but no decompiler cross-check exists.
- The exe side (0x4b58a0, 0x4b5470, 0x4b62b0, 0x4af250) was read from Ghidra C; the `.pcode` export carries no per-op
  addresses, so the meshType -> slot-type switch and the `+0x864` store are cited by function, not by instruction.
- `0x10051e94` (gun-row count used as a loop bound at 0x1001ad03 / 0x1001a863) has no symbol row; it is read as
  "number of gun rows" from its use beside `0x10051e64` (dropper rows, set in `Garage_BuildMountLabels`). [inferred]
- The semantic names Fwd/Top/Rear/Dropper per case come from the string-pointer sites in `symbols\functions.tsv`
  (0x10006302 / 0x1000639b / 0x100063f2 / 0x1000635d); I did not re-read the string bytes. [static, second-hand]
- Not traced: whether a gun written into a type-8 (dropper) slot survives (the dropper row would accept it by name;
  in-game it would get location code 4 = no mount geometry). Treat as unsupported.
