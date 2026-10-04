# .vdf: vehicle definition (BWD2 rev 8), byte-exact layout

Sources: the pristine exe (`ghidra/i76_ref.exe`, disassembled with `tools/disasm.py` or raw capstone), and the corpus
`recon-2026-09-04/recon/formats/zfs_out/*.vdf` (48 files).
Every citation below is an instruction I read in the disassembly. Anything I could not tie to an instruction is marked **inferred**.
Open76 `VdfParser.cs` was used only as a checklist. Where it disagrees with the exe, that is called out.

## 0. How chunks reach the handlers (walker 0x4b3db0 `bwd2_Parse`)

- **Entry point:** `bwd2_LoadDef(file, table, count, ctx)` at 0x4b41e0. It parses the BWD2 header, then calls
  `bwd2_Parse(data, table, count, ctx, filename, 1, end)` (0x4b4250..0x4b426a).
- **Handler call site:** 0x4b4025..0x4b4046:
  ```
  0x4b4025 mov eax,[edi+8]            ; handler ptr from 16-byte table entry {tag[4], ?, handler, flags}
  0x4b403a mov ecx,[edx+0xc]          ; edx = table base (arg2): flags of table[0]
  0x4b403d shr ecx,1 / and ecx,1
  0x4b4042 lea edx,[ebx+ecx*8]        ; ebx = current chunk header
  0x4b4045 push edx / call eax        ; handler(chunk_ptr, ctx_arg, end)   (cdecl, 3 args)
  ```
- **Argument 1:** the chunk header pointer plus 8 x bit 1 of table[0].flags. All three VDF tables (0x4feff0, 0x4ff0b0,
  0x500090) have table[0].flags = 0x0800, so bit 1 is 0 and **handlers get the chunk HEADER**: tag at +0, size at +4,
  body at +8.
  - So `[hdr+N]` in a handler is **body offset N-8**. Every citation below is converted to body offsets.
- **Argument 2 (context):** chosen by the entry's flags.
  - `flags & 0x0800` passes arg4, the caller's ctx (0x4b3fd3/0x4b3fe9).
  - `flags & 0x1000` passes the table entry itself (0x4b4006).
  - `flags & 0x2000` passes arg5 (0x4b4021).
  - Every VDF entry that has a handler uses 0x0800.
- **Argument 3:** the end-of-buffer limit (arg7).
- **Return value:** 0 means failure. If `flags & 4`, the walker logs "Error - reading of %s chunk failed" (0x4b4066).
  A null handler means the chunk is skipped.

### The three VDF handler tables and who drives them

| table | loaded by | ctx | purpose |
|---|---|---|---|
| 0x4feff0 (12 entries) | `bwd2_h_VCFC_4ad950` 0x4ad96e, reached from `vcf_LoadForObject` 0x4ad6f0, reached from `bwd2_h_OBJ_4b7ac0` 0x4b7bdc and 0x4512e5/0x45148b | 0x54-byte ctx on the caller's stack (0x4b7b6d zeroes 0x15 dwords). Fields: ctx[0]=vehicle object; ctx[1]=0xaa8-byte VCF scratch buffer (0x4ad6f6 `mov ecx,0x2aa`, 0x4ad71b `mov [ebx+4],eax`); ctx+8 = COLP valid; ctx+0xc..+0x3b = COLP; ctx+0x3c..+0x4f = LOD[5]; ctx+0x50 = LOD valid | spawn an in-game vehicle |
| 0x4ff0b0 (13 entries, includes ETBL) | `bwd2_h_VCFC_4adb90` 0x4adc7c, reached from `vcf_LoadInfo` 0x4ad8c0 (called from 0x4b58c2) | ctx[1] = caller's VCF info struct (0x4adba6 `mov ebx,[eax+4]`) | VCF info: name, mass total, shell, hardpoints, UI positions |
| 0x500090 (13 entries) | `bwd2_h_VCFC_4b3650` 0x4b3856 | ctx = a counter dword (0x4b385c) | VCF legality check: armor/chassis budget and weapon-to-hardpoint match |

Chunk order is identical in all 48 files:
`REV VDFC [SOBJ] VSHL VLOC{2..5} EXIT VGEO VCHK{0..7} EXIT [LOBJ] EXIT COLP WLOC HLOC{0..5} EXIT SPCS EXIT`.
- SOBJ is absent in 2 files. LOBJ is present in 38.
- ETBL never appears, and every ETBL table entry has handler 0, so **the exe never parses ETBL** from a .vdf.
- Open76's ETBL branch is unreachable for this corpus. It uses the VDFC ELT name instead.

---

## 1. VDFC: 77 bytes (48/48)

Handlers:
- A = 0x4adee0 (spawn, table 0x4feff0). ebx = hdr, ebp = ctx.
- B = 0x4adf70 (VCF info, table 0x4ff0b0). ebx = hdr+8 = body, edx = ctx[1].
- C = 0x4b3cb0 (validation, table 0x500090). eax = hdr.

| off | width | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0x00 | 20 | char[20], NUL-terminated only if shorter | name | Display name. Not NUL-terminated when it is exactly 20 chars. | B: `0x4adf7e lea ebx,[ecx+8]`; strlen `0x4adf8f repne scasb`; copied with `rep movsd/movsb` 0x4adf9e/0x4adfaa to ctx[1]+0xa0. A and C do not read it. | 48 distinct. 2 names are exactly 20 bytes with no NUL ("AH-1 Cobra Helicopte", "Sandbagged emplaceme"), so B's strlen/strcpy runs on into 0x14 and copies the class byte (0x09 / 0x08) as a 21st character. Bytes after the NUL are always 0. |
| 0x14 | 4 | u32 | class | Object class id passed to obj_SetClass. Selects the class descriptor in table 0x4f76e0: 1 = car (ctor 0x462d90), 8 = emplacement/turret (ctor 0x462580), 9 = aircraft (ctor 0x46b780). | A: `0x4adeea mov ecx,[ebx+0x1c]` → `call 0x461970(obj, class)`. 0x461970 does `0x46197b mov [edi+0x6c],esi` and allocates classdata into obj+0x70 (0x4619c3). | {1:40, 8:3, 9:5} |
| 0x18 | 4 | u32 | size | Weight class. The validator's armor+chassis point budget is `1600*s` total, with each of the 8 values required to be ≥ `50*s`, where s = size (size 6 → 10, size 5 → 4). | A: `0x4adf28 mov edx,[ebx+0x20]` → classdata+0x47c (0x4adf2b; no reader found by offset scan). C: `0x4b3cb4 mov ecx,[eax+0x20]` → global 0x5db958, read at `0x4b3896` in bwd2_h_VCFC_4b3650. Special cases at 0x4b389e/0x4b38af; `lea`/`shl 6`/`sar 5` at 0x4b38b9..0x4b38ce; comparisons at 0x4b38da/0x4b38fe/0x4b3919. | 1..9: {1:9, 2:8, 3:10, 4:5, 5:6, 6:1, 7:5, 8:3, 9:1} |
| 0x1c | 4 | f32 | lod[0] | LOD threshold 0 | A: `0x4adf41 lea esi,[ebx+0x24]` / `0x4adf47 mov ecx,5` / `0x4adf4c rep movsd` → ctx+0x3c; `0x4adf54 mov [ebp+0x50],1` (LOD valid). Then `bwd2_h_OBJ` passes &ctx+0x3c to `entity_Register` 0x4572b0 (0x4b7d5c..0x4b7d6d), which copies it to entity+0x1c..0x2f and sets entity+0x30 = 1 (0x457350..0x45735a). The runtime reader was not traced. | {70:41, 160:3, 120:2, 100:1, 10:1} |
| 0x20 | 4 | f32 | lod[1] | LOD threshold 1 | same rep movsd | {45:38, 35:3, 100:3, 50, 80, 90, 5} |
| 0x24 | 4 | f32 | lod[2] | LOD threshold 2 | same | {30:40, 70:3, 50:2, 15, 2, 20} |
| 0x28 | 4 | f32 | lod[3] | LOD threshold 3 | same | {25:40, 30:4, 5:2, 1, 20} |
| 0x2c | 4 | f32 | lod[4] | LOD threshold 4 (sentinel) | same | always 100000 |
| 0x30 | 4 | f32 | mass | **Mass.** A → classdata+0xa4 (`0x4adf0d mov ecx,[ebx+0x38]` / `0x4adf10 mov [eax+0xa4],ecx`, only if classdata exists). Confirmed consumer: `0x438f3b mov ecx,[esi+0xa4]` feeds `rigidbody_SetMass` 0x438340, which stores m (0x438352) and 1/m when m > 1e-4 (`0x43835b fld 1.0 / 0x438361 fdiv [esp+8] / 0x438365 fstp [ecx+4]`). Kill-score code multiplies victim.classdata+0xa4 by killer.classdata+0xa8 (1/m) (0x40129c/0x4012a2, 0x455079/0x45507f). B: `0x4adfb7 fld [ebx+0x30]` → ctx[1]+0xaa4 (base mass) and +0xaa0 (running total). 0x4adb90 then adds engine/suspension/brake masses into +0xaa0 (0x4add19..0x4ade01). | see left | 50 .. 30000, 33 distinct (car 400..2800, trucks 5455..22500, tank 30000) |
| 0x34 | 4 | f32 | collisionMult | Stored in classdata+0x124. **No reader found** by a whole-.text offset scan (writes only: 0x462fae ctor, 0x4adf19). The name "collision multiplier" comes from Open76 and is **inferred**. | A: `0x4adf16 mov edx,[ebx+0x3c]` / `0x4adf19 mov [eax+0x124],edx` | always 1.0 |
| 0x38 | 4 | f32 | drag | **Aerodynamic drag coefficient.** Consumers compute `k*v^2*C`: `0x43ad93 fld [esi+0xac]` / `0x43ad99 fld [esi+0x120]` / `0x43ad9f fmul st1` / `0x43ada2 fmul st1`, and similarly at 0x40fb01/0x40fb07. In both functions esi = obj_GetClassData(obj) (0x43acf9/0x43acfe, 0x40fa83/0x40fa8b). That +0xac is speed is **inferred**. | A: `0x4adf1f mov ecx,[ebx+0x40]` / `0x4adf22 mov [eax+0x120],ecx` | 0.0001..0.01, 8 distinct (0.0008 x19) |
| 0x3c | 4 | u32 | hardpointCount | Number of HLOC chunks. Equals the HLOC chunk count in 48/48 files. | A: `0x4adf57 mov ecx,[ebx+0x44]` → ctx[1]+0xa5c (0x4adf5c). B: `0x4adfac mov ecx,[ebx+0x3c]` (ebx = body) → ctx[1]+0xa5c (0x4adfb0). C: `0x4b3cbd mov edx,[eax+0x44]` → 0x5db7c4. It is the loop bound for weapon-to-hardpoint matching in bwd2_h_WEPN (0x4b3aa1..0x4b3ad1 over 0x5db190 with stride 0xfc) and in 0x4aec49..0x4aec6f. | 0..5: {0:4, 1:5, 2:7, 3:8, 4:14, 5:10} |
| 0x40 | 13 | char[13] | eltFile | Sprite/element table file (HUD). | A: `0x4adf31 lea eax,[ebx+0x48]` / `call 0x448010`, only if classdata exists. 0x448010 does `strncpy(buf,name,0x10)`, then `_strlwr` (0x44805f), checks the loaded-list at 0x531d18 (0x44809a..0x4480b9), then loads the file (0x448079 `call 0x46ffc0`). | always "vpit_1.elt", padded with zeros |

Unread bytes:
- Only padding after string NULs.
- A does not read `name`. B does not read 0x14..0x2f or 0x34..0x38. C reads only 0x18 and 0x3c.

---

## 2. SOBJ: 100 bytes (46/48)

This is one 100-byte part record (layout in section 5). The handler (0x4b8470, spawn table only) reads **only the name**:
- `0x4b8479 mov ecx,[eax+0xc]` / `0x4b847c mov edx,[eax+8]` read body 0..7.
- These go to `geo_MakeFileName(name8, ".geo")` 0x4ad640, then `0x4b848a call 0x4469a0` (geometry load).
- The result is stored in vehicle obj+0x5c (`0x4b8496 mov edx,[ecx]` / `0x4b8498 mov [edx+0x5c],eax`).

| off | width | type | name | citation | corpus |
|---|---|---|---|---|---|
| 0x00 | 8 | char[8] | geo name | 0x4b8479/0x4b847c | 43 distinct, always `XX1_SOR` form (e.g. AG1_SOR). The "_SOR" suffix suggests a shadow or simple outline mesh (**inferred**). |
| 0x08..0x63 | 92 | part record | unread | the handler reads nothing past 0x4b8479 | identity matrix, zero position, parent "WORLD", 0x40..0x58 bbox, class 0x5c = 54, flags 0x60 = 0 in all 46 files |

---

## 3. VSHL: 45 bytes (48/48)

- The spawn table entry has handler = 0 (skipped).
- Handler 0x4adfd0 (VCF info table) copies the whole body opaquely: `0x4adfdd lea esi,[eax+8]` / `0x4adfe0 add edi,0x10a` /
  `0x4adfe6 mov ecx,0xb` / `rep movsd` + `0x4adfed movsb` = 45 bytes → ctx[1]+0x10a. No offset-scan reader of +0x10a was
  found, so the sub-field meanings below are **inferred** from the values.

| off | width | type | name | corpus |
|---|---|---|---|---|
| 0x00 | 13 | char[13] | smk video file | "scarcon1.smk" (all 48) |
| 0x0d | 2+2 | u16,u16 | screen x,y (inferred) | 325,112 |
| 0x11 | 2+2 | u16,u16 | screen x,y (inferred) | 307,298 |
| 0x15 | 20 | 5 x u32 | unknown | all 0 |
| 0x29 | 2+2 | u16,u16 | screen x,y (inferred) | 283,174 |

---

## 4. VLOC: 52 bytes (224 chunks, 2..5 per file), handler 0x4ae000 (spawn table only)

ebx = hdr and ebp = classdata (`0x4ae00f mov ebp,[ecx+0x70]`). The handler dispatches on `body+0 - 0x23` via the jump table at
0x4ae2b4 (0x4ae013..0x4ae027).

| off | width | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0x00 | 4 | u32 | class | Locator kind and object class id (see the table below) | `0x4ae013 mov eax,[ebx+8]`; generic path `0x4ae249 mov ecx,[ebx+8]` → obj_SetClass(child). Needle and hdlt paths copy it into the synthesized part record's +0x5c (0x4ae091/0x4ae0b3, 0x4ae192/0x4ae1ab). | {35:45, 36:45, 38:39, 40:48, 42:47} |
| 0x04 | 36 | f32[9] | rotation 3x3 (right, up, forward) | child transform | generic: `0x4ae253`..`0x4ae289` (`mov edx,[ebx+0xc]`..`mov ecx,[ebx+0x2c]`) → child+0x18..+0x38. Needle/hdlt: `lea esi,[ebx+0xc]`, `mov ecx,0xc`, `rep movsd` (0x4ae094..0x4ae0a0, 0x4ae181..0x4ae190) → part record +0x08..+0x37 | unit-ish components −1..1 |
| 0x28 | 12 | f32[3] | position | child translation, widened to doubles | generic: `0x4ae28c fld [ebx+0x30]`/`fstp qword [esi+0x40]`, 0x4ae292 → +0x48, 0x4ae298 → +0x50. Class 42: `0x4ae02e mov ecx,[ebx+0x30]` → classdata+0x12c, 0x4ae037 → +0x130, 0x4ae040 → +0x134 | x −0.82..0.69, y −0.005..9.44, z −2.24..6.01 |

Per-class behavior:

| class | path | effect | consumer / evidence |
|---|---|---|---|
| 0x23 (35) | 0x4ae072 | Synthesizes a part record {name "needle", parent "null"} (0x4ae085, 0x4ae0cf `0x6c6c756e`) and builds it with `geo_BuildPartTree(&rec, vehicle, 1,1,1, NULL)` (0x4ae0e2). Then `needle.geo` is set for LOD slots 1..4 (0x4ae0ff..0x4ae127). The result goes to classdata+0x3f8 (0x4ae130). | read at 0x45a011 in 0x459fa0 and driven from `0x46a7b0(engine data)` (0x45a034). **Inferred: tachometer needle.** |
| 0x24 (36) | 0x4ae072 | same as 0x23, stored to classdata+0x3fc (0x4ae13b) | read at 0x45a1cd in 0x459fa0 using engine-data+0x1c (0x45a1ff). **Inferred: speedometer needle.** |
| 0x26 (38) | 0x4ae146 | If `0x477ac0()==1` (graphics-detail table 0x4fa0b0[0x58db00*5]), sets classdata+0x440 = 0 and stops (0x4ae150). Otherwise builds part "hdlt_msk" (0x4ae175), tags the vehicle "hlight" (0x4ae1e8/0x4ae1f0), and sets geometry "hdlv_msk.geo" at damage 0 / LOD slot 4 (0x4ae205..0x4ae216). Result in classdata+0x440 (0x4ae209). | headlight mask. Readers of +0x440: 0x4585f6, 0x458611, 0x458722, 0x458742, 0x46755f, 0x467572 |
| 0x28 (40) | 0x4ae056 | Only if `0x458bf0(vehicle)` (obj+0x10 & 0x10) is true; else no object (0x4ae061). Then the generic child (class 0x28) goes to classdata+0x398 (0x4ae067). | read at 0x406b02 in `camera_CockpitLook` 0x406ab0, and 0x4457fb (its matrix feeds a view matrix), 0x46ece9. **Cockpit camera mount.** |
| 0x2a (42) | 0x4ae02e | Position only → classdata+0x12c..0x134. The rotation (0x04..0x27) is **not read**. | no reader found (only ctor 0x462fbf and 0x47263f also touch it) |
| other | 0x4ae227 | generic child object, not stored (edi = 0) | none in corpus |

---

## 5. The 100-byte part record (VGEO, VCHK and SOBJ entries)

The record is consumed by `obj_CreateFromPartRecord` 0x4b8230 (ebx = record) and `geo_BuildPartTree` 0x4b75a0
(esi = record).

| off | width | type | name | meaning | citation |
|---|---|---|---|---|---|
| 0x00 | 8 | char[8] | name | Part name. Also the geometry file stem: `geo_MakeFileName` masks each byte with 0x7f (0x4ad689..0x4ad69d), treats "null" as no geometry (0x4ad677/0x4ad682), and appends ".geo". | `0x4b770a mov edx,[esi]` / `0x4b7707 mov ecx,[esi+4]` → 0x4ad640. `0x4b823c call 0x4b47c0(parent,name)`, which copies the name into obj+0/+4 (0x4b47de..0x4b47e5) |
| 0x08 | 36 | f32[9] | rotation | right, up, forward rows | `0x4b8256 mov ecx,[ebx+8]` .. `0x4b8285 mov eax,[ebx+0x28]` → obj+0x18..+0x38. If the name is "null" and the first three matrix floats are 0.0, identity is copied from 0x4faed8 instead (0x4b82c5..0x4b8314) |
| 0x2c | 12 | f32[3] | position | local translation | `0x4b828f fld [ebx+0x2c]`/`fstp qword [edi+0x28]` (obj+0x40), 0x4b8297 → +0x48, 0x4b829d → +0x50 |
| 0x38 | 8 | char[8] | parent | "WORLD" or "NULL" attaches to the owning object. Otherwise it is looked up by name in the owner's tree (`obj_FindByName` 0x4b47f0). A miss logs "Can't find parent %s for object %s" and attaches to the owner. | `0x4b7633 lea edi,[esi+0x38]`, `_strnicmp` "world"/5 (0x4b7640), "null"/4 (0x4b7655), `0x4b7662 mov eax,[edi+4]` / `0x4b7665 mov ecx,[edi]` → 0x4b47f0 |
| 0x40 | 12 | f32[3] | bboxCenter | local bounding-box centre | `0x4b8340 lea edx,[ebx+0x40]`, copied 0x4b834b..0x4b8358 → obj+0x84..0x8c |
| 0x4c | 4 | f32 | radius | bounding-sphere radius (**inferred** from 0.61 ≤ radius/|halfExtent| ≤ 1.0 over 468 parts) | `0x4b8337 mov ecx,[ebx+0x4c]` / `0x4b8343 mov [ebp+0x90],ecx` |
| 0x50 | 12 | f32[3] | halfExtent | AABB half size: obj+0x94.. = centre − h, obj+0xa0.. = centre + h | `0x4b835d fsub [ebx+0x50]`, `0x4b8368 fadd [ebx+0x50]`, `0x4b8377 fsub [ebx+0x54]`, `0x4b8380 fld [ebx+0x54]`, `0x4b8395 fsub [ebx+0x58]`, `0x4b839e fld [ebx+0x58]` |
| 0x5c | 4 | u32 | class | Object class. Goes to obj_SetClass (0x4b831e/0x4b8323, only when arg5 = 1) and drives the switch at 0x4b83ad (types 2..12 call 0x46b200/0x46d6f0/0x46f8f0 and read **past** 0x64: +0x64..+0x77, 0x4b83cb..0x4b8421). The VGEO callback 0x4ae2e0 dispatches on it (section 6). | `0x4b831e mov eax,[ebx+0x5c]`; `0x4b83ad mov eax,[ebx+0x5c]` |
| 0x60 | 4 | u32 | objFlags | Stored verbatim as obj+0x10 (the flag word; e.g. bit 0x10 is tested by 0x458bf0) | `0x4b82c0 mov edx,[ebx+0x60]` / `0x4b82cb mov [ebp+0x10],edx` |

**Answer to the "36 trailing bytes" question:** the bytes at 0x40..0x63 are:
- bbox centre (12 bytes)
- sphere radius (4)
- AABB half-extents (12)
- class id (4)
- object flags (4)

That totals 36 bytes. Open76 skips them (`br.Position += 36`).

In VDF files the class values are all ≥ 27, so the 0x64+ over-read in the switch is never taken. That case exists for longer
records in other formats (SDF records are 120 bytes).

---

## 6. VGEO: 4 + 2800·n bytes (48/48; n = 4..42), handler 0x4ae3a0 (spawn table only)

```
0x4ae3b6 mov eax,[esi+8]          ; body+0 = n (parts per row)
0x4ae3c0 lea edx,[esi+0xc]        ; body+4 = first record
0x4ae3c5 call 0x4b7570(body+4, ptrs[28], 0x1c, n)   ; ptrs[r] = body+4 + r*n*100   (0x4b7587..0x4b7596: n*25*4)
0x4ae3e9 call 0x4b75a0(ptrs, vehicle, 7, 4, n, cb=0x4ae2e0)
```

In `geo_BuildPartTree` 0x4b75a0:
- The outer loop `o` runs 0..6 (arg3 = 7; ebp, 0x4b77b6).
- The middle loop `m` runs 0..3 (arg4 = 4; ebx, 0x4b779a). The row pointer advances by 4 per m and is never reset
  (0x4b7793..0x4b77a0), so **row = o*4 + m**.
- The inner loop `i` runs 0..n−1 (0x4b7771..0x4b7786, record stride 0x64).
- Layout: `record(o,m,i) = body + 4 + ((o*4+m)*n + i)*100`, so 28·n records in total (2800·n bytes). Checked:
  `len == 4+2800n` in 48/48.

What each loop index means:

| index | meaning | exe evidence | corpus evidence |
|---|---|---|---|
| **o = LOD slot 0..6** | `geocache_SetGeoName(obj, name, m, o)` 0x4461e0 stores the name at `node + o*16` (0x44630e `shl ebp,4`, strncpy 15). A node holds 7 slots (0x70 bytes) plus a next pointer at +0x70 (0x74-byte HeapAlloc at 0x446275/0x4462ea). | the first name digit = o+1 in every non-NULL name; rows o = 5, 6 are all "NULL" in the corpus |
| **o = 4 (inferred: cockpit set)** | the headlight mask uses LOD slot 4 for "hdlv_msk.geo" (0x4ae205) | names like xx51DASH/SEAT/SWHL/GUNL/RADR/MIRI and 1122 non-NULL records |
| **m = damage state 0..3** | selects the m-th node in the chain (0x4462d1..0x446303 walks +0x70 m−1 times) | the second name digit ≤ m+1 (undamaged geometry reused). m = 3 has only BDYM-type parts (45 records): **inferred: wrecked** |
| **i = part index** | one object per i, created from **row 0 only** | |

Row (o, m) = (0, 0) versus the other 27 rows:
- **Row (0, 0)** is the only full read. It runs `obj_CreateFromPartRecord(parentObj, rec, rec, 0, 1)` (0x4b76cb..0x4b76d2),
  then the callback `0x4ae2e0(obj, vehicle)` (0x4b76fc..0x4b76fe), then `SetGeoName(obj, name.geo, 0, 0)`.
- **Rows (o, m) ≠ (0, 0):** `ebx|ebp != 0` jumps to 0x4b77ee, which reuses the row-0 object for part i. **Only the 8-byte
  name** is read (0x4b7707/0x4b770a → `SetGeoName(obj, name.geo, m, o)`).
  - Bytes 0x08..0x63 of these 27·n records are **never read**, even though 38905 of 39393 of them differ from row 0.
- **Special case:** at o = 2, if the owner's class is 0x32, the same name is also written to slot o = 3 (0x4b7727..0x4b775b).
  Vehicles are class 1/8/9, so this never fires for VDF.

**Open76 is wrong here.** It reads rows 0..3 as "4 damage states" and row 16 as "first person". The exe's order is
7 LOD slots × 4 damage states, and Open76's reads land on rows (0,0), (0,1), (0,2), (0,3) and (4,0).

**VGEO record class values (row 0) and the callback 0x4ae2e0:**
- The callback switches on `obj+0x6c − 0x26` (0x4ae2e9..0x4ae2ff; jump tables 0x4ae378 / 0x4ae350).
- It stores the part object into classdata (`0x4ae2ec mov eax,[eax+0x70]`).

| class | part (name suffix) | classdata slot | count |
|---|---|---|---|
| 0x26 | (headlight mask) | +0x440 (0x4ae336) | – |
| 0x41 = 65 | BDYF | +0x408 (0x4ae306) | 47 |
| 0x42 = 66 | BDYM | +0x40c (0x4ae30e) | 48 |
| 0x43 = 67 | BDYB | +0x410 (0x4ae316) | 48 |
| 0x44 = 68 | BDYT | +0x414 (0x4ae31e) | 48 |
| 0x45 = 69 | BMPF | +0x418 (0x4ae326) | 5 |
| 0x46 = 70 | BMPB | +0x41c (0x4ae32e) | 4 |
| 0x47 = 71 | HLGT | +0x3a0 (0x4ae33e) | 37 |
| 0x48 = 72 | BLGT | +0x3a4 (0x4ae346) | 37 |
| 60 | generic part (AXLF, ENGN, DRVR, DASH, …) | none | 859 |
| 27 / 28 | MIRR / MIRL (mirrors) | none | 2 / 5 |
| 29, 31, 32, 33, 34, 43, 44 | always name "NULL" (placeholder slots) | none | 42..47 each |

Row-0 objFlags (0x60) is 0 in all 1459 records.

---

## 7. VCHK: 12 + 100·k bytes (k = 1..4; 132 chunks), handler 0x4ae400 (spawn table only)

esi = hdr and ebp = parent part.

| off | width | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0x00 | 8 | char[8] | parent | Part in the vehicle tree that owns the chunks. A miss logs "Chunk's parent object %s not found." and returns 1. | `0x4ae412 mov eax,[esi+0xc]` / `0x4ae415 mov ecx,[esi+8]` → `obj_FindByName` 0x4b47f0 | BDYF 37, BDYM 33, BDYB 33, others (PIPR, GASL, …) |
| 0x08 | 4 | u32 | k | record count | `0x4ae45e mov eax,[esi+0x10]`, loop bound `0x4ae558 cmp ebx,[eax+0x10]` | {1:85, 2:33, 3:7, 4:7}; `len == 12+100k` in all |
| 0x0c | 100·k | part record[k] | chunks | see section 5. Read: name 0x00..0x07 (0x4ae525/0x4ae51d), rotation 0x08..0x2b (0x4ae47b..0x4ae4bc), position 0x2c..0x37 as doubles (0x4ae478/0x4ae485/0x4ae499), radius 0x4c (0x4ae4de), halfExtent 0x50..0x58 as +h (0x4ae4e5/0x4ae4ec/0x4ae4f3) and −h (0x4ae4c3/0x4ae500/0x4ae509 `fchs`). **Not read:** parent 0x38, centre 0x40..0x48 (zeros used instead: 0x4ae469..0x4ae471), class 0x5c, flags 0x60. | `0x4ae531 call 0x4a0ff0(part, name_lo, name_hi, &xform, &sphere, &aabb)`; failure logs "Unable to add chunk" | chunk names have the LOD digit replaced by "C" (AGC1BDYM under AG11BDYM); class 60; parent "WORLD"; centre ≈ 0 |

The parent also gets `obj+0x10 |= 0x100000` (0x4ae44d..0x4ae45b). Break-off debris pieces (**inferred** from the "chunk" strings
and the "C" names).

---

## 8. LOBJ: 72 bytes (38/48), handler 0x4b8ed0 (spawn table and 0x500b58)

eax = hdr. The handler calls `light_Add(vehicle, type, range, cone, &dir, &pos)` 0x477c20 (0x4b8f0e..0x4b8f1f), then sets
`vehicle+0x10 |= 0x800` (0x4b8f29..0x4b8f30).

| off | width | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0x00 | 4 | u32 | type | Light type. 0 or 1 is stored in light-table flags (0x477d29..0x477d42) with `|8`. Type 1 uses −dir, or the negated object forward if dir is NULL (0x477d59..0x477ddd). | `0x4b8f16 mov eax,[eax+8]` | always 1 |
| 0x04 | 24 | f32[6] | right, up | **not read** | – | ≈ (1,0,−0.001), (−0,1,0) |
| 0x1c | 12 | f32[3] | forward = direction | light direction (stored negated at 0x58db98..) | `0x4b8edc mov ecx,[eax+0x24]`, `0x4b8edf [eax+0x28]`, `0x4b8ee6 [eax+0x2c]` | (0..0.0012, 0, ≈1) in 37 files; (0, −1, 0), pointing down, in 1 file |
| 0x28 | 12 | f32[3] | position | light position → 0x58dba4 | `0x4b8eed [eax+0x30]`, `0x4b8ef4 [eax+0x34]`, `0x4b8efb [eax+0x38]` | x ≈ 0.00106; y −2.43..1.19; z 0.0003..4.36 |
| 0x34 | 4 | f32 | unknown | **not read** | – | −1.70..2.11, 31 distinct |
| 0x38 | 4 | f32 | unknown | **not read** | – | 0 |
| 0x3c | 4 | f32 | coneAngle (rad) | Clamped to [10°, 90°] (0x4be618 = 0.1745, 0x4be61c = 1.5708). Converted to a spot exponent `floor(−ln2 / ln((1+cos a)/2))` (0x477ce6..0x477d06). | `0x4b8f0f mov ecx,[eax+0x44]` | 0.38397 (22°) |
| 0x40 | 4 | f32 | range | Clamped to ≥ 20.0 (0x477c9f..0x477cb0). Stored raw at +0x58db94 and 1/r² at +0x58db90 (0x477d48..0x477d78). The corpus value 10 therefore becomes 20. | `0x4b8f13 mov edx,[eax+0x48]` | 10.0 |
| 0x44 | 4 | u32 | unknown | **not read** | – | 0 |

light_Add returns without adding anything when:
- `0x4fa0b0[0x58db00*5] == 1` (lights disabled by the detail setting; 0x477c20..0x477c39)
- 0x200 lights already exist
- this object already has a light

---

## 9. COLP: 48 bytes (48/48), handler 0x4ae570 (spawn table only)

- If `vehicle.class == 8` (emplacements), the chunk is ignored (`0x4ae57f cmp [ecx+0x6c],8`).
- Otherwise the 12 floats are copied to ctx+0xc (`0x4ae576 lea esi,[eax+8]`, `0x4ae588 mov ecx,0xc`, `rep movsd`) and
  ctx+8 = 1 (0x4ae58f).
- `bwd2_h_OBJ` then calls `colp_BuildBox` 0x4b81c0(&ctx+0xc) (0x4b7d47..0x4b7d4c). That builds
  `{4,4,4, X[4], Y[4], Z[4]}` with each group **reversed** into ascending order, and passes it to `entity_Register` (entity+0x18).

| off | width | type | name (Open76) | destination in the 0x3c-byte box | citation | corpus (all 48 strictly descending per group) |
|---|---|---|---|---|---|---|
| 0x00 | 4 | f32 | zMaxOuter | +0x38 | `0x4b8221 mov ecx,[ecx]` | 0..9.65 |
| 0x04 | 4 | f32 | zMaxInner | +0x34 | `0x4b821b mov edx,[ecx+4]` | 0..3.56 |
| 0x08 | 4 | f32 | zMinInner | +0x30 | `0x4b8215 mov edx,[ecx+8]` | −4.88..0 |
| 0x0c | 4 | f32 | zMinOuter | +0x2c | `0x4b820f mov edx,[ecx+0xc]` | −11.73..0 |
| 0x10 | 4 | f32 | xMaxOuter | +0x18 | `0x4b81f1 mov edx,[ecx+0x10]` | 0..7.43 |
| 0x14 | 4 | f32 | xMaxInner | +0x14 | `0x4b81eb` | 0..3.84 |
| 0x18 | 4 | f32 | xMinInner | +0x10 | `0x4b81e5` | −3.84..0 |
| 0x1c | 4 | f32 | xMinOuter | +0x0c | `0x4b81df mov edx,[ecx+0x1c]` | −7.45..0 |
| 0x20 | 4 | f32 | yMaxOuter | +0x28 | `0x4b8209 mov edx,[ecx+0x20]` | 0..19.23 |
| 0x24 | 4 | f32 | yMaxInner | +0x24 | `0x4b8203` | 0..17.17 |
| 0x28 | 4 | f32 | yMinInner | +0x20 | `0x4b81fd` | 0..0.69 |
| 0x2c | 4 | f32 | yMinOuter | +0x1c | `0x4b81f7 mov edx,[ecx+0x2c]` | 0 (47), −0.40 (1) |

The box order is X, Y, Z, so the file order is Z, X, Y. That the Y group is height comes from the values (ground at 0) and
Open76, so it is **inferred**. All three axes have 4 planes (0x4b81ce..0x4b81d9).

---

## 10. WLOC: 336 = 6 × 56 bytes (48/48), handler 0x4ae5a0 (spawn and VCF-info tables)

The handler copies `6 × 14 dwords` opaquely (`0x4ae5b1 mov ebx,6`, `0x4ae5c0 mov ecx,0xe`, `rep movsd`, stride 0x38) →
ctx[1]+0x168 + w·0x38. No offset-scan reader of the VCF struct +0x168 was found, so the field meanings are from the values
and Open76 (**inferred**).

| off (within wheel w) | width | type | name | corpus |
|---|---|---|---|---|
| 0x00 | 4 | u32 | present | Slots 0, 1, 4, 5 = 1 in 40 files. Slots 2, 3 = 1 in 2 files. Slot 5 holds 0x000FE088 (garbage) in 8 files, and absent slots are not zeroed. |
| 0x04 | 36 | f32[9] | rotation | ≈ identity; element 0x0c ranges −1.93..0 |
| 0x28 | 12 | f32[3] | position | x −1.43..1.35, y −0.001..0.88, z −5.75..3.23 |
| 0x34 | 2+2 | u16,u16 | UI x,y (inferred) | Constant per slot: w0 (408,119), w1 (270,119), w2/w3 (0,0), w4 (408,312), w5 (270,312). This field is an f32 "unk2" in Open76. |

---

## 11. HLOC: 80 bytes (149 chunks, 0..5 per file). Three handlers, each capped at 7 per vehicle (return 0 = error at ≥ 7)

- **A = 0x4aea00** (spawn). Slot = ctx[1] + 0x378 + n·0xfc, n = ctx[1]+0xa60 (0x4aea0b, 0x4aea11 `cmp edx,7`).
- **B = 0x4aea90** (VCF info), same slot layout.
- **C = 0x4b3cd0** (validate). Global array 0x5db190 + n·0xfc; n = ctx[0].

| off | width | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0x00 | 16 | char[16] | label | hardpoint label | B: `0x4aea9c lea ebx,[ecx+8]`, strcpy 0x4aeac6..0x4aeadd → slot+0 | 143 distinct, e.g. "AG1_GIB1" |
| 0x10 | 4 | u32 | index | Hardpoint/mount index. Matched against VCF WEPN mount ids (0x4aec5f `cmp [eax+0xb0],esi`; 0x4b3ac4 `cmp [ecx],esi`). | A: `0x4aea22 mov edx,[ecx+0x18]` → +0xb0. B: `0x4aeaee mov eax,[ebx+0x10]` → +0xb0. C: `0x4b3cea mov ecx,[edx+0x18]` → 0x5db190 | 0..4 |
| 0x14 | 4 | u32 | facing (Open76 name) | | A: `0x4aea50 mov edx,[ecx+0x1c]` → +0xb4. B: `0x4aeb05` → +0xb4. C: `0x4b3cfd mov ecx,[edx+0x1c]` → 0x5db194 | {1:98, 2:51} |
| 0x18 | 4 | u32 | meshType (Open76 name) | | A: `0x4aea39 mov edx,[ecx+0x20]` → +0xb8. B: `0x4aeb1c` → +0xb8. C: `0x4b3d09 mov edx,[edx+0x20]` → 0x5db1d4 (+0x44) | {1:51, 2:31, 4:31, 5:36} |
| 0x1c | 48 | f32[12] | rotation[9] + position[3] | mount transform | A only: `0x4aea5a lea esi,[ecx+0x24]`, `0x4aea6a mov ecx,0xc`, `rep movsd` → slot+0xbc..0xeb | pos x −2.44..2.42, y 0..3.05, z −6.82..3.54 |
| 0x4c | 4 | f32/u32 | unknown | | B only: `0x4aeb33 mov eax,[ebx+0x4c]` → slot+0xec | always 0 |

A does not read the label or 0x4c. B does not read the transform. C reads only 0x10, 0x14 and 0x18.

---

## 12. SPCS: 12 bytes (48/48), handler 0x4aeb60 (VCF info table only)

The handler copies 3 dwords opaquely: `0x4aeb68 add eax,8`, then 0x4aeb6e/0x4aeb78/0x4aeb7e → ctx[1]+0xa64..0xa6f
(0x4aeb70 `add edx,0xa64`). No reader was found.

| off | width | type | name (inferred) | corpus |
|---|---|---|---|---|
| 0x00 | 2+2 | u16,u16 | UI x,y #0 | 403,191 |
| 0x04 | 2+2 | u16,u16 | UI x,y #1 | 403,226 |
| 0x08 | 2+2 | u16,u16 | UI x,y #2 | 403,260 |

The same value in all 48 files: 3 icons in a column at x = 403. "Specials" positions is **inferred**.

---

## 13. Proposed exe function names

| address | proposed name | evidence |
|---|---|---|
| 0x4adee0 | bwd2_h_VDFC_Spawn | 0x4adefb obj_SetClass(obj, body+0x14); mass/drag/collision into classdata 0x4adf10..0x4adf22; LOD rep movsd 0x4adf4c |
| 0x4adf70 | bwd2_h_VDFC_VcfInfo | name strcpy → ctx[1]+0xa0 (0x4adf9e); mass → +0xaa0/+0xaa4 (0x4adfbc/0x4adfc2) |
| 0x4b3cb0 | bwd2_h_VDFC_VcfValidate | body+0x18 → 0x5db958 (0x4b3cb7), used in the armor budget at 0x4b3896; body+0x3c → 0x5db7c4 (0x4b3cc0) |
| 0x4adfd0 | bwd2_h_VSHL_VcfInfo | 45-byte copy to ctx[1]+0x10a (0x4adfe0..0x4adfed) |
| 0x4ae000 | bwd2_h_VLOC | jump on body+0 − 0x23 (0x4ae017..0x4ae027); "needle" 0x4ae085, "hdlt_msk" 0x4ae175 |
| 0x4ae2e0 | vdf_VgeoPartSlotCb | callback passed at 0x4ae3d9; switch on obj+0x6c−0x26 → classdata+0x3a0..0x440 (0x4ae306..0x4ae346). No Ghidra function exists here. |
| 0x4ae3a0 | bwd2_h_VGEO | 0x4ae3c5 geo_SetRowPointers(…, 0x1c, n); 0x4ae3e9 geo_BuildPartTree(…, 7, 4, n, 0x4ae2e0) |
| 0x4ae400 | bwd2_h_VCHK | "Chunk's parent object %s not found." 0x4ae433; 0x4ae531 call 0x4a0ff0; "Unable to add chunk" 0x4ae53d |
| 0x4ae570 | bwd2_h_COLP | class-8 skip 0x4ae57f; 12-dword copy to ctx+0xc 0x4ae58d |
| 0x4ae5a0 | bwd2_h_WLOC | 6 × 14-dword copy to ctx[1]+0x168 (0x4ae5b1..0x4ae5ce) |
| 0x4aea00 | bwd2_h_HLOC_Spawn | 7-cap 0x4aea11; fields → slot+0xb0/0xb4/0xb8/0xbc (0x4aea25..0x4aea76) |
| 0x4aea90 | bwd2_h_HLOC_VcfInfo | label strcpy → slot+0 (0x4aeac6); 0x4c → slot+0xec (0x4aeb37) |
| 0x4b3cd0 | bwd2_h_HLOC_VcfValidate | → 0x5db190/0x5db194/0x5db1d4 (0x4b3ced/0x4b3d00/0x4b3d13) |
| 0x4aeb60 | bwd2_h_SPCS_VcfInfo | 3-dword copy to ctx[1]+0xa64 (0x4aeb70..0x4aeb81) |
| 0x4b7570 | geo_SetRowPointers | `ptrs[i] = base + i*n*100` (0x4b7587..0x4b7596) |
| 0x4b75a0 | geo_BuildPartTree(ptrs, owner, nLod, nDmg, nParts, cb) | loops 0x4b77b6/0x4b779a/0x4b7771; "world"/"null" parent 0x4b7638/0x4b764f; 0x4b76d2 call 0x4b8230; 0x4b771f call 0x4461e0 |
| 0x4b8230 | obj_CreateFromPartRecord(parent, rec, name, calcLen, setClass) | 0x4b823c obj_CreateChild; transform 0x4b8256..0x4b82a0; flags 0x4b82cb; class 0x4b8323; bbox 0x4b8337..0x4b83a7 |
| 0x4461e0 | geocache_SetGeoName(obj, name, dmg, lod) | 0x3c-byte cache entry (0x446201); 0x74-byte LOD node chain via +0x70 (0x4462d8, 0x4462fe); strncpy to node + lod*16 (0x44630e..0x446317) |
| 0x4ad640 | geo_MakeFileName(name8, ext) → static 0x5dabb0 | strncpy 8 (0x4ad664); "null" → NULL (0x4ad677); `and dl,0x7f` (0x4ad691); strcat ext (0x4ad6c1..0x4ad6e2) |
| 0x461970 | obj_SetClass(obj, cls) | `mov [edi+0x6c],esi` 0x46197b; class table scan 0x4f76e0 stride 0x34 (0x46199b..0x4619a8); classdata ctor → obj+0x70 (0x4619c3) |
| 0x467440 | obj_GetClassData | `mov eax,[eax+0x70]` 0x467444 |
| 0x4b47c0 | obj_CreateChild(parent, name8) | "wrldr" 0x4b47c4; name copy 0x4b47de..0x4b47e5 |
| 0x4b47f0 | obj_FindByName(tree, lo, hi) | compares [esi]/[esi+4] (0x4b4805/0x4b480c); recurses into child +0x64 (0x4b4816) and sibling +0x60 (0x4b4822) |
| 0x438340 | rigidbody_SetMass(rb, m, m2) | stores m (0x438352); 1/m if m > 1e-4 (0x43835b..0x438365); called with classdata+0xa4 and VDFC mass (0x438f3b..0x438f57) |
| 0x477c20 | light_Add(obj, type, range, cone, dir, pos) | range clamp 20.0 0x477cb0; cone clamp 0x477cbc..0x477ce0; fcos/log exponent 0x477ce6..0x477d06; table 0x58db84 stride 0x6c, cap 0x200 (0x477c45) |
| 0x477ac0 | gfx_GetLightDetailFlag (inferred name) | returns `[0x4fa0b0 + 20*[0x58db00]]` (0x477ac0..0x477ac8); ==1 disables headlight mask (0x4ae14b) and lights (0x477c36) |
| 0x448010 | elt_Load(name) | strncpy 16, `_strlwr` 0x44805f, loaded-list 0x531d18 (13-byte names, count 0x531e1c), file load 0x448079, `strpbrk` parse 0x448101 |
| 0x4ad6f0 | vcf_LoadForObject(file, ctx) | 0xaa8-byte scratch (0x4ad6f6..0x4ad71b); "VCFC" LoadDef 0x4ad7c7; ".vsf" and VCST 0x4ad808/0x4ad877 |
| 0x4ad8c0 | vcf_LoadInfo(file, info) | 0x54-byte ctx with ctx[1] = info (0x4ad8e6); LoadDef table 0x4fefb0 (0x4ad8e0) |
| 0x4b81c0 | colp_BuildBox(colp12) | 0x3c alloc 0x4b81c2; {4,4,4} 0x4b81ce..0x4b81d9; reversed copy 0x4b81df..0x4b8223 |
| 0x4572b0 | entity_Register(obj, colBox, lod5) | table 0x542830 stride 0x78 (0x4572c5..0x4572df); box → +0x18 (0x457345); LOD → +0x1c..0x2f, flag +0x30 (0x457350..0x45735a) |
| 0x4a0ff0 | obj_AddChunk(part, name_lo, name_hi, xform, sphere, aabb) | caller 0x4ae531 with "Unable to add chunk" |
| 0x458bf0 | obj_TestFlag10 | `test byte [eax+0x10],0x10` 0x458bf8; gates the cockpit-camera VLOC 0x4ae057 and the flag at 0x438f10 |

## 14. Where Open76 differs from the exe

- **VGEO:** 7 LOD slots × 4 damage states, not "4 damage + skip 12 + first-person". Only row 0 carries live transforms.
- **VDFC:** "VehicleType" is the object class id (1/8/9). "Unknown" at 0x3c is the hardpoint count. The ELT name is always
  present (77 bytes in all files).
- **ETBL:** never present, and has no handler in any VDF table.
- **WLOC:** the trailing "unk2" float is two u16 values (UI coordinates, inferred).
- **LOBJ, SPCS, VSHL, VCHK, SOBJ:** not decoded by Open76. See sections 2, 3, 7, 8 and 12.
