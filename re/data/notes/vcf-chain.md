# Vehicle configuration chain: .vcf, .vsf, compnent.cdf

Pristine exe: `ghidra/i76_ref.exe`. Every instruction cited below was read with `tools/disasm.py`, or with a raw capstone decode where a function was not in Ghidra's list. Labels mean:
- **inferred**: the meaning is my reading of how the value is used. The code does not name it.
- **Open76**: the name comes from the Open76 C# parser and the exe does not confirm it.

Corpus:
- `recon-2026-09-04/recon/formats/zfs_out`: 293 `.vcf` files and 1 `compnent.cdf`. It holds no `.vsf`.
- `sandbox-gog/main/app/ADDON/vehscn.vsf`: the only `.vsf` found. It is a single sample, so the .vsf numbers below have n=1.

Naming: `veh` means the vehicle class-data block `[obj+0x70]`. The brief calls this block "entity", and `data/notes/vdf.md` calls it "classdata". `veh+0xa4` is mass: it feeds `rigidbody_SetMass` at `0x438f3b mov ecx,[esi+0xa4]` → `0x438f57 call 0x438340`, which I re-checked.

---

## 0. The walker and the handler calling convention

`bwd2_LoadDef(name, table, count, ctx)` at 0x4b41e0 works in these steps:
1. If `name` starts with "null", it returns 1 without parsing anything (`0x4b41f5 _strnicmp`, 0x4b4202).
2. Otherwise it loads the file (0x4b420a, 0x4b421c).
3. It parses the file header with the `BWD2` table 0x500328 (0x4b4234..0x4b423f).
4. It parses the body with `bwd2_Parse(p, table, count, ctx, name, 1, end)` (0x4b4250..0x4b426a).

`bwd2_Parse` is at 0x4b3db0:
- **Table entry**: 16 bytes. `+0` is the tag (compared with `cmp ecx,[edi]` at 0x4b3e47/0x4b3e94), `+8` is the handler (`0x4b4025 mov eax,[edi+8]`), and `+0xc` holds the flags.
- **Handler call**: `cdecl int handler(u8 *chunk, void *ctx, u8 *end)` (0x4b4030..0x4b4046).
  - The first argument is `ebx + ((table[0].flags>>1)&1)*8` (0x4b403a..0x4b4042).
  - No table in this family sets bit 1 in its first entry, so every handler gets a pointer to the chunk header: `chunk+0` is the tag, `chunk+4` is the size including the 8-byte header, and **`chunk+8` is the body**. The size includes the header because the walker advances with `0x4b3e14 mov esi,[ebx+4]` / `0x4b3e17 add ebx,esi`; for example, VCFC has size 0x89 for a 129-byte body. **All body offsets below are therefore "`chunk` displacement minus 8".**
- **ctx selection by flags**:
  - 0x800: the caller's ctx, from `0x4b3fe9 mov ebp,[esp+0x48]`.
  - 0x1000: the table entry itself (0x4b4006).
  - 0x2000: the file name (0x4b4021).
  - 0x100: the address of a local count (0x4b3f51).
- **Return value**: 0 means failure (0x4b404b). On failure, an entry with flag 0x20 aborts the whole parse and returns 0 (`0x4b40c9 test al,0x20` → 0x4b4148). Without 0x20, parsing continues.
- **Diagnostics are dead**: every "Error/Warning" string goes to 0x42d5d0 `dbg_LogStub`, which is 1 byte long. None of these messages are ever emitted.

## 1. The three .vcf contexts (who calls bwd2_LoadDef with each VCFC table)

| table | push site | loader fn | who calls the loader | context |
|---|---|---|---|---|
| 0x4fef70 (VCFC 0x4ad950 flags 0x820, SPEC 0x4ade50, WEPN 0x4aeb90) | 0x4ad7c7 | 0x4ad6f0 | 0x4512e5 in 0x451180 ("No vehicle sent for player %d", "cannot load vehicle %s"); 0x45148b in 0x4513c0; 0x4b7bdc in `bwd2_h_OBJ_4b7ac0` | **In-game spawn** of a network player car or a mission/world object. Writes into the live `veh` block. Then loads `<name>.vsf` with table 0x4ff330 (0x4ad877). That happens only when `[0x6562c4]==2` (0x4ad7dd) and the file exists (`0x4ad864 call 0x470340`). |
| 0x4fefb0 (VCFC 0x4adb90, SPEC 0x4adea0, WEPN 0x4af250) | 0x4ad8e0 | 0x4ad8c0 | 0x4b58c2 in `shell_cb_05` ("Error loading shell vehicle %s", ENGINE/SUSP/BRAKE/WHL labels) | **Shell/garage display record.** Fills a flat record R = `ctx[1]`, where ctx is 0x54 bytes on the stack (0x4ad8c8..0x4ad8e6). No object is created. |
| 0x500050 (VCFC 0x4b3650, SPEC 0x4b3a10, WEPN 0x4b3aa0) | 0x4b360d | 0x4b35a0 (`shell_cb_26`) | 0x457072 in 0x456fb0 (dpGetPlayerData, then "*** %s has tried to join with a hacked vehicle!", dpDestroyPlayer) | **Multiplayer join legality check + CRC32.** Builds the CRC table (poly 0x04c11db7) at 0x4b35d2..0x4b3604. Result goes to `out[0]` (violation bits) and `out[1]` (CRC, seeded with -1 at 0x4b3613 and inverted at 0x4b3637/0x4b3644). Returns 1 only if the parse succeeded and `0x5dacd0` (legal) is still 1. |

The .vsf has two contexts:
- **In-game**: 0x4ad6f0 with table 0x4ff330, using VCST 0x4b0350, WLST 0x4b0540 and WPST 0x4b0610. SALV has no handler here.
- **Shell**: 0x4ad900 with table 0x4ff180, using VCST 0x4b0520, WLST 0x4b05e0, WPST 0x4b0640 and SALV 0x4b0680. It is called from `shell_cb_06` at 0x4b71c0 and `shell_cb_04` at 0x4b73ca. Before loading it zeroes the WPST count at `V+0xbc` (0x4ad91d).

compnent.cdf has two contexts:
- **In-game**: table 0x4ff380 with 13 entries, pushed at 0x4ada45 from the VCFC handler 0x4ad950. It has handlers only for ENGN, BRAK and SUSP (all 0x4b0d00).
- **Shell**: table 0x4ff450, pushed at 0x4add3c from 0x4adb90 and at 0x4b1063 from `cdf_LookupComponent` 0x4b1010. Handlers: ENGN/BRAK/SUSP 0x4b0e70, NTBL 0x4b0f50, BTBL 0x4b0f90, STBL 0x4b0fd0.

---

## 2. .vcf (BWD2 REV = 3 in 293/293 files)

Chunk census: REV(4 bytes) ×293, VCFC(129) ×293, SPEC(4) ×112, WEPN(17) ×881, EXIT(0) ×586.
- SPEC per file: 0:211, 1:62, 2:10, 3:10.
- WEPN per file: 0:16, 1:27, 2:61, 3:73, 4:67, 5:49.

### 2.1 VCFC body (129 bytes)

The three handlers are:
- **A** = 0x4ad950: in-game. Here `ebx` = chunk, so the body is at `ebx+8`.
- **B** = 0x4adb90: shell. Here `ebp` = chunk+8 = the body (`0x4adba9 lea ebp,[ecx+8]`).
- **C** = 0x4b3650: validator. Here `ebx`/`esi`/`edi` = chunk.

| off | width | type | name | meaning | citation | corpus values (n=293) |
|---|---|---|---|---|---|---|
| 0x00 | 16 | char[16] | variantName | Display name of the variant. Read by B only. A and C never touch 0x00..0x0f. | B: `0x4adbb1 mov edi,ebp` / strcpy `0x4adbca rep movsd` → R+0x50 | 170 distinct; top "Stock" 20, "Stock (Orange)" 18, "Pole Turret" 16 |
| 0x10 | 13 | char[13] | vdfFile | Chassis .vdf, loaded with the VDFC tables. | A: `0x4ad96b lea eax,[ebx+0x18]` → LoadDef(0x4feff0, 12) at 0x4ad974. B: `0x4adbc7 lea edx,[ebp+0x10]` → strcpy to R+0xf0 (0x4adbf5), then LoadDef(0x4ff0b0, 13) at 0x4adc82. C: `0x4b36c3 add ecx,0x18` is stricmp'd against the truck list 0x5001e8..0x500200 (0x4b36d2); `0x4b3853 lea eax,[esi+0x18]` → LoadDef(0x500090, 13) at 0x4b3868; CRC32 of the file at 0x4b3938..0x4b3974 | 34 distinct; vppirnha 24, vccavera 23, vcpolice 19. 102 files have junk bytes after the NUL, which nothing reads (all readers stop at the NUL). |
| 0x1d | 13 | char[13] | vtfFile | Texture/skin .vtf. C does not read it. | A: `0x4ad98e lea ecx,[ebx+0x25]` → LoadDef(0x4ff1d0 'VTFC', 2) at 0x4ad997. B: `0x4adc00 lea edi,[ebp+0x1d]` → strcpy to R+0xfd (0x4adc21) | 85 distinct; piranha1 19, turret1 16. 97 files have junk after the NUL. |
| 0x2a | 4 | u32 | engineId | Engine **number** in `engsnd.dat` (column "ENG NUM"). It is not a cdf index; see §4.4. | A: `0x4ada12 mov ebp,[ebx+0x32]` → cdf ctx L+4 (0x4ada3b). B: `0x4add25 mov ecx,[ebp+0x2a]` → L+4 (0x4add31). C: not read. | 0..99, 9 distinct {0:109, 1:47, 2:54, 3:41, 4:3, 5:12, 10:3, 20:6, 99:18}. All of them exist in engsnd.dat. |
| 0x2e | 4 | u32 | suspensionId | Direct ordinal of the SUSP record and the STBL row. | A: `0x4ada08 mov eax,[ebx+0x36]` → L+0x74 (0x4ada30 `mov [esp+0x8c],ecx`). B: `0x4add2b mov eax,[ebp+0x2e]` → L+0x74 (0x4add4a). C: not read. | 0..3 {0:141, 1:47, 2:54, 3:51} |
| 0x32 | 4 | u32 | brakeId | Direct ordinal of the BRAK record and the BTBL row. | A: `0x4ada0b mov edx,[ebx+0x3a]` → L+0x3c (0x4ada2a `mov [esp+0x54],edx`). B: `0x4add28 mov edx,[ebp+0x32]` → L+0x3c (0x4add46). C: not read. | 0..3 {0:139, 1:51, 2:47, 3:56} |
| 0x36 | 13 | char[13] | wdfFront | Front wheel .wdf (slot 0). | A: `0x4ad9b0 lea edx,[ebx+0x3e]` → `0x4ae5e0(name, ctx, 0)` at 0x4ad9b5. B: `0x4adca2 lea ecx,[ebp+0x36]` → `0x4ae780(name, ctx, 0)` at 0x4adca7. C: `0x4b3696 add ebx,0x3e` is checked against the forbidden list 0x5001c0..0x5001dc (0x4b36a2) and, for non-trucks, against the truck wheels 0x5001e0/0x5001e4 (0x4b36f8); CRC32 of the file at 0x4b3983..0x4b39c3 | 21 distinct; wauto_3a 41, wauto_1a 38, "null" 33 |
| 0x43 | 13 | char[13] | wdfMid | Mid wheels (slot 2). "null" means the vehicle has none. | A: `0x4ad9ce lea eax,[ebx+0x4b]` → 0x4ae5e0(…, 2) at 0x4ad9d3. B: `0x4adcc0 lea edx,[ebp+0x43]` → 0x4ae780(…, 2) at 0x4adcc5. C: `0x4b3671 lea eax,[ebx+0x4b]` → `_strnicmp(…,"null",4)` sets the "has mid" flag (0x4b3679..0x4b3692); lists checked at 0x4b37c8/0x4b380f; CRC via `0x4b39d7 call 0x4b3d50` | 2 distinct: "null" 283, "wbtck_1a.wdf" 10 |
| 0x50 | 13 | char[13] | wdfRear | Rear wheels (slot 4). | A: `0x4ad9ec lea ecx,[ebx+0x58]` → 0x4ae5e0(…, 4) at 0x4ad9f1. B: `0x4adcde lea eax,[ebp+0x50]` → 0x4ae780(…, 4) at 0x4adce3. C: `0x4b372f lea ebx,[edx+0x58]` lists at 0x4b3736/0x4b3781; CRC via 0x4b39e4 | 22 distinct; same leaders as front |
| 0x5d | 16 | u32[4] | armor[4] | Armour per facet. The Open76 order is front, left, right, rear; the exe copies the block as a whole, so the facet order is Open76's, not confirmed by the exe. **Copied verbatim, with no scaling** (see §2.4). | A: `0x4adac1 lea esi,[ebx+0x65]`, `0x4adac9 mov edi,[ecx]` .. `0x4adae3 mov ecx,[ecx+0xc]` → veh+0x138..+0x147 (0x4adad1..0x4adae6); again → veh+0x158..+0x167 (0x4adaf1..0x4adb0a); `0x4adb12 rep movsd` (5 dwords) → veh+0x178..+0x18b, then `0x4adb1e mov [eax+0x188],0x64` overwrites the 5th dword with 100. B: `0x4adc30 lea ecx,[ebp+0x5d]` / `0x4adc33 mov esi,[ebp+0x5d]` → R+0xa7c..+0xa8b. C: `0x4b389b add esi,0x65`, loop `0x4b38d6 mov ecx,[edx]` / `0x4b38d8 add edi,ecx` / `0x4b38da cmp ecx,eax` | per facet 100..10000. f: 27 distinct (600:70, 200:65, 800:49, 400:48). l/r: 22 distinct. rear: 24 distinct. |
| 0x6d | 16 | u32[4] | chassis[4] | Chassis (inner) points per facet, same order. | A: `0x4adb14 lea esi,[ebx+0x75]`, `0x4adb2a mov ebx,[edi]`..`0x4adb3a` → veh+0x148..+0x157; `0x4adb48`..`0x4adb5b` → veh+0x168..+0x177; `0x4adb69 rep movsd` (5 dwords) → veh+0x18c..+0x19f, then `0x4adb6b mov [eax+0x19c],edx(=100)`. B: `0x4adc4a lea eax,[ebp+0x6d]` → R+0xa8c..+0xa9b. C: `0x4b388f lea eax,[esi+0x75]`, loop 0x4b38fa..0x4b3913 | 100..10000, 24 to 25 distinct per facet (200:71, 600:70, 400:52, 800:49) |
| 0x7d | 4 | u32 | sparePoints | Unallocated armour/chassis points ("ArmorOrChassisLeftToAdd" in Open76). **The validator proves its meaning**: it starts the budget sum from this value. **In-game it is unused**: A reads it only as the 5th dword of the rep movsd at 0x4adb69, and 0x4adb6b then overwrites that dword. | B: `0x4adc70 mov ecx,[ebp+0x7d]` → R+0xa9c (0x4adc74). C: `0x4b3889 mov ecx,[esi+0x85]` → `0x4b38bc mov edi,ecx` (sum seed) | 0..200 {0:278, 80:6, 160:6, 200:3} |

No VCFC byte goes entirely unread: every offset is read by at least one handler. Per handler:
- A skips 0x00..0x0f. It reads 0x7d but the value is dead, because it is overwritten.
- B reads the whole body.
- C skips 0x00..0x0f, 0x1d..0x35 and all three component ids. C only CRCs compnent.cdf as a whole: `0x4b39ed push 0x4ffcd0` / `0x4b39f2 call 0x4b3d50`.

### 2.2 SPEC body (4 bytes)

| off | width | type | name | meaning | citation | corpus (n=112) |
|---|---|---|---|---|---|---|
| 0x00 | 4 | u32 | specialId | Special-equipment id. The Open76 enum is 1 RadarJammer, 2 Nitrous, 3 Blower, 4 XAustBrake, 5 StructoBumper, 6 CurbFeelers, 7 MudFlaps, 8 HeatedSeats, 9 CupHolders. | In-game 0x4ade50: `0x4ade81 mov eax,[esp+0xc]` / `0x4ade85 mov ecx,[eax+8]` → `0x467280(obj, id, slot)` (0x4ade8a), which creates a "v-spcl" object at veh+0x3ec+slot*4 (0x4672a1..0x4672b0) and initialises it with id (0x4672c5). Slot = first zero in scratch+0xa70[0..2], which is then marked 1 (0x4ade73). A 4th SPEC is silently ignored (0x4ade6e). Shell 0x4adea0: `0x4adec4 mov ecx,[ecx+8]` → R+0xa70+slot*4 (0x4adec7). A 4th SPEC returns 0 (0x4adebd). Validator 0x4b3a10: `0x4b3a17 mov ebx,[eax+8]` is compared with the earlier ids at 0x5db968[] (0x4b3a3e) and stored at 0x4b3a82. | 1..9, 9 distinct {1:6, 2:25, 3:23, 4:16, 5:28, 6:4, 7:5, 8:3, 9:2} |

A validator detail: a repeated nonzero id sets `out[0]` bit (7+i), where i is the index of the earlier duplicate (0x4b3a56..0x4b3a65), and clears "legal". The array 0x5db968 has 3 slots and its count lives at 0x5db974, immediately after it. A 4th SPEC would therefore overwrite the count (inferred from the addresses; no bound check at 0x4b3a82).

### 2.3 WEPN body (17 bytes)

| off | width | type | name | meaning | citation | corpus (n=881) |
|---|---|---|---|---|---|---|
| 0x00 | 4 | u32 | hardpoint | Mount index. It is matched against the VDF HLOC index. | In-game 0x4aeb90: `0x4aebea mov ecx,[eax+8]` → local ctx+0x10 (0x4aebf0), compared with scratch+0x378+i*0xfc+0xb0 over i < scratch+0xa5c (0x4aec49..0x4aec6f). If there is no match, 0x4af21f returns 0 and the weapon is skipped. Shell 0x4af250: `0x4af27f mov esi,[edi+8]` vs R+0x428+i*0xfc (0x4af296). Validator 0x4b3aa0: `0x4b3abc mov esi,[edi+8]` vs 0x5db190+i*0xfc (0x4b3ac4). The hardpoint bit goes into `out[0]` bits 0..6 (0x4b3b5b..0x4b3b77). | 0..4 {0:273, 1:247, 2:190, 3:119, 4:52} |
| 0x04 | 13 | char[13] | gdfFile | Weapon .gdf. "null" makes LoadDef return 1 without parsing (0x4b41f5). The in-game handler then takes its failure path, because 0x4aec84 tests a GDF-filled local that stays 0 (inferred). | In-game: `0x4aebed lea edi,[eax+0xc]` → `_splitpath` 0x4aec0b, LoadDef(0x4ff270 'GDFC', 6) at 0x4aec39. The GDF mass is added to veh+0xa4 (`0x4af1b7 fld [esp+0xb4]` / 0x4af1c7). Shell: `0x4af2bf add edi,0xc` → LoadDef(0x4ff2d0, 6) at 0x4af2cb; the GDF name is copied to R+0x3c8+i*0xfc (0x4af2ef..0x4af314); mass is added to R+0xaa0 (0x4af316..0x4af320). Validator: `0x4b3aea lea ebp,[edi+0xc]` → LoadDef(0x500160, 6) at 0x4b3af9; forbidden gtktank/gtptank/tthowitz.gdf sets flag 0x2000 (0x4b3b96..0x4b3bc5); CRC32 of the file at 0x4b3c58..0x4b3c97. | 42 distinct; gmmedium 118, gmlight 79, glandmin 70, gmheavy 70, "null" 39. 168 entries have junk after the NUL. |

### 2.4 How armour becomes the veh values (the "×2" question)

All three VCFC handlers move the eight u32s with plain `mov` and `rep movsd`. The exe does no multiply or shift anywhere on this path. The resulting veh layout is:
- +0x138: armor[4]
- +0x148: chassis[4]
- +0x158: armor[4]
- +0x168: chassis[4]
- +0x178: armor[4], then +0x188 = 100
- +0x18c: chassis[4], then +0x19c = 100

This matches the pristine file values: `sandbox-gog/.../ADDON/vmxmarx3.vcf` has 800×8, the same as the zfs copy. **So the ×2 seen live has to come from the modded ADDON files, not from the exe.**

The in-game .vsf handler, VCST 0x4b0350, restores only +0x138/+0x158 (armor) and +0x148/+0x168 (chassis), at 0x4b0411..0x4b0490. It leaves +0x178/+0x18c at the VCF values. Engine, brake and suspension behave the same way: the .vsf writes only the "current" slot (see §3), and the other slot keeps the design maximum.

- **inferred**: +0x178..+0x187 and +0x18c..+0x19b are the design maximums, and +0x138/+0x158 (armour) and +0x148/+0x168 (chassis) are the current values.
- **This contradicts the brief's note that +0x178 is "current"; check it live.** The dword at +0x188/+0x19c = 100 is a 5th per-block value with unknown meaning.

Validator budget (C), with `s = VDFC.size` (0x4b3cb4 → 0x5db958):
- Size is remapped: s=6 → 10 and s=5 → 4 (0x4b389e..0x4b38b4).
- `budget = 1600*s` (0x4b38b9 lea×5, 0x4b38be lea×5, 0x4b38c1 shl 6).
- Every facet must be ≥ `budget/32 = 50*s` (0x4b38c6..0x4b38ce sar 5; 0x4b38da/0x4b38fe). Otherwise flag 0x800 is set.
- `spare + Σarmor + Σchassis` must equal `budget` (0x4b3919). Otherwise flag 0x400 is set.

Across the corpus, 257 of the 293 totals are exact multiples of 1600: 1600:74, 3200:60, 4800:69, 6400:48, 8000:2, 16000:4. The remaining 36 are one-offs such as 800 (×10), 2480 and 80000. These are presumably AI/mission-only vehicles, because the check runs only on a network join.

---

## 3. .vsf (BWD2 REV = 2)

Only one sample exists (`ADDON/vehscn.vsf`). Its chunks are REV, VCST(76), WLST(24), WPST(12)×4 and EXIT. It has no SALV chunk, so SALV is decoded from code only.

### 3.1 VCST body (76 bytes)

| off | width | type | name | meaning | citation | sample |
|---|---|---|---|---|---|---|
| 0x00 | 13 | char[13] | vcfFile | The .vcf this state belongs to. It is only a sanity check: the first 8 chars of the fname are compared with the object name `[obj]` and a mismatch only logs, through the no-op log. | In-game 0x4b0350: `0x4b0368 lea esi,[eax+8]` → `_splitpath` 0x4b038d, `_strnicmp(…,8)` 0x4b03a7 | "vehscn.vcf" |
| 0x0d | 16 | u32[4] | armorCur[4] | Current armour. | `0x4b0411 lea ecx,[esi+0xd]` → veh+0x138..+0x147 (0x4b041e..0x4b042f) and veh+0x158..+0x167 (0x4b043a..0x4b044f). Shell `shell_cb_06` reads it back from V+0x0d.. at 0x4b7248..0x4b7270 → out+0x118.. | 600×4 |
| 0x1d | 16 | u32[4] | chassisCur[4] | Current chassis. | `0x4b0452 lea ecx,[esi+0x1d]` → veh+0x148 (0x4b045f..0x4b0470) and veh+0x168 (0x4b047b..0x4b0490) | 600×4 |
| 0x2d | 12 | f32[3] | velocity (inferred) | Stored to veh+0xbc..+0xc4, and its magnitude `sqrt(x²+y²+z²)` goes to veh+0xac. | `0x4b04af lea ecx,[esi+0x2d]` → 0x4b04bc..0x4b04c7; fsqrt at 0x4b04fa → `0x4b04fc fstp [eax+0xac]` | 0,0,0 |
| 0x39 | 4 | f32 | unknown | Widened to double at `[obj]+0x48`. | `0x4b0502 fld [esi+0x39]` / `0x4b050e fstp qword [edx+0x48]` | 0.0 |
| 0x3d | 4 | i32 | engineHpCur | Engine current hit points. It goes to engine data +0 (the max is at +4). | `0x4b0497 mov edx,[esi+0x3d]` → `0x4b049a mov [ecx],edx` (ecx = `[veh+0x3c4]+0x70`, 0x4b03de/0x4b03eb) | 300 |
| 0x41 | 4 | i32 | brakeHpCur | Brake current hit points. It goes to brake data +4 (the max is at +8). | `0x4b04a9 mov edx,[esi+0x41]` → `0x4b04ac mov [ecx+4],edx` (ecx = `[veh+0x3cc]+0x70`, 0x4b0400/0x4b040d) | 150 |
| 0x45 | 4 | i32 | suspHpCur | Suspension current hit points. It goes to suspension data +0. | `0x4b04a0 mov edx,[esi+0x45]` → `0x4b04a3 mov [ecx],edx` (ecx = `[veh+0x3c8]+0x70`, 0x4b03ef/0x4b03fc) | 200 |
| 0x49 | 3 | u8[3] | unknown flags | **The in-game handler 0x4b0350 never reads these.** The shell reads them as three bytes. | Shell: 0x4b0520 copies all 76 bytes to V (`0x4b0530 mov ecx,0x13` / `0x4b053a rep movsd`); `shell_cb_06` `0x4b7236 mov al,[esp+0x51]`, 0x4b723a, 0x4b723e → out+0x114..+0x116 | 01 01 01 |

The engine, brake and suspension values sit in the order engine, brake, suspension. `shell_cb_06` copies them to out+0, +4, +8 (0x4b71d0/0x4b71d4/0x4b71cc).

### 3.2 WLST body (24 bytes)

| off | width | type | name | meaning | citation | sample |
|---|---|---|---|---|---|---|
| 0x00..0x17 | 6×4 | i32[6] | wheelState[6] | One value per wheel object `veh+0x3a8..+0x3bc` (6 slots). Each value is written to `[wheel+0x70]+4` if the wheel exists (inferred: wheel health). -1 means the wheel slot is absent. | In-game 0x4b0540: `0x4b055f mov esi,[edx+8]`, `0x4b0576 [edx+0xc]`, `0x4b058d [edx+0x10]`, `0x4b05a4 [edx+0x14]`, `0x4b05bb [edx+0x18]`, `0x4b05d2 [edx+0x1c]`. Shell 0x4b05e0: `0x4b05ed lea esi,[eax+8]` / `0x4b05f8 rep movsd` (6) → V+0x4c; shell_cb_06 → out+0xc..+0x20 | 100,100,-1,-1,100,100 (the mid pair is absent) |

### 3.3 WPST body (12 bytes; repeated)

| off | width | type | name | meaning | citation | sample (n=4) |
|---|---|---|---|---|---|---|
| 0x00 | 4 | i32 | hardpoint | Weapon key. | In-game 0x4b0610: `0x4b061a mov eax,[eax+8]` → 2nd arg of `weapon_SetState 0x4a34c0`, matched at 0x4a3501 | 3,2,1,0 |
| 0x04 | 4 | i32 | stateA | Always stored in the weapon record +0 (global 0x5aab14 + idx*0x4c). Inferred: hit points or ammo. | `0x4b0614 mov ecx,[eax+0xc]` (pushed as the 4th arg) → `0x4a353c mov edx,[esp+0x14]` / `0x4a3546 mov [eax+0x5aab14],edx`. Shell 0x4b0640 appends the 3 dwords to V+0x64+n*12 (0x4b0657..0x4b066c, n = V+0xbc); shell_cb_06 → out+0x9c+4i (0x4b722b/0x4b722e) | 200 ×4 |
| 0x08 | 4 | i32 | stateB | Stored in the weapon record +0x14 (0x5aab28) **only if ≠ -1**. | `0x4b0617 mov edx,[eax+0x10]` → `0x4a3538 mov ecx,[esp+0x10]`, `0x4a3543 cmp ecx,-1`, `0x4a354e mov [eax+0x5aab28],ecx`. Shell: the copy lands in V, but shell_cb_06 does not read the 3rd dword (it reads entry[0] and entry[1] only, 0x4b7222/0x4b722b) | -1 ×4 |

### 3.4 SALV

- **In-game**: the table 0x4ff360 has handler 0, so SALV is skipped.
- **Shell (0x4b0680)**: if `V+0xb8` (a callback) is nonzero, it calls `cb(body, *(u32*)(body+0x10), *(u32*)(body+0x14))` (0x4b068e..0x4b06a1). The callback is at `0x4b0688 mov ecx,[eax+4]` / `0x4b068e mov ecx,[ecx+0xb8]`.
- Both shell callers zero V first and never set +0xb8, so **SALV is dead in the retail exe**.
- The layout is at least 0x18 bytes: body+0 is passed as a pointer, and +0x10 and +0x14 are dwords. There are no corpus samples.

---

## 4. compnent.cdf (BWD2 REV = 1)

The file is ECNK, NTBL, ENGN×4, EXIT, then BCNK, BTBL, BRAK×4, EXIT, then SCNK, STBL, SUSP×4, EXIT, EXIT. ECNK, BCNK and SCNK have empty bodies. **No handler exists for them in either table** (handler 0 at 0x4ff380, 0x4ff3c0, 0x4ff400, 0x4ff450, 0x4ff490, 0x4ff4d0).

Both tables use the same scratch context L, 0xb0 bytes, zeroed by `rep stosd` with 0x2c dwords (0x4ada15/0x4add06/0x4b1016):

| L off | content |
|---|---|
| +0 | veh (in-game only) |
| +4 | engineId |
| +8 | found flag |
| +0xc | ENGN counter |
| +0x10 | ENGN body copy (26 bytes) |
| +0x2a | engine name (16 bytes) |
| +0x3c | brakeId |
| +0x40 | found flag |
| +0x44 | BRAK counter |
| +0x48 | BRAK body copy |
| +0x62 | brake name |
| +0x74 | suspensionId |
| +0x78 | found flag |
| +0x7c | SUSP counter |
| +0x80 | SUSP body copy (30 bytes) |
| +0x9e | suspension name |

A record is applied only when `counter == wanted`. Each handler increments its counter on every record: 0x4b0da0, 0x4b0e04, 0x4b0e5b, 0x4b0ed4, 0x4b0f11, 0x4b0f3d.

### 4.1 ENGN body (26 bytes) ×4

| off | width | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0x00 | 4 | u32 | maxHp | Engine hit points, stored as both current (+0) and max (+4) of the engine data `[veh+0x3c4]+0x70`. The getter `0x46a9f0` returns ([0],[1]). The shell lists it at record+0x4c. | In-game 0x4b0d00: `0x4b0dca mov ecx,[esi+8]` → `0x4b0dd0 mov [eax+4],ecx`, `0x4b0dd3 mov [eax],ecx`. Shell 0x4b0e70: whole-record copy to L+0x10 (`0x4b0ef8 lea edi,[ebx+0x10]` / 0x4b0f00 rep movsd 6 / 0x4b0f02 movsw); `0x4b4f8f mov eax,[esp+0x20]` → list +0x4c (0x4b4f93) | 300 ×4 |
| 0x04 | 4 | f32 | power | Drive power scalar, stored at engine+0x14. Consumer: 0x43c310 `0x43c55e fld [eax+0x14]` / `0x43c561 fmul [eax+0x18]`, then × veh+0xa8 (1/mass) × veh+0x128. Inferred: drive force. | `0x4b0dd5 mov ecx,[esi+0xc]` → `0x4b0dd8 mov [eax+0x14],ecx` | 104440, 138010, 193960, 290940 |
| 0x08 | 4 | f32 | mass | Added to veh+0xa4, which is mass (it goes to rigidbody_SetMass at 0x438f57). The shell adds it to R+0xaa0 (the shell total mass, seeded from VDFC mass at `0x4adfb7`/`0x4adfc2`) and lists it at +0x50. | `0x4b0dea fld [esi+0x10]` / 0x4b0ded fadd / `0x4b0df3 fstp [eax+0xa4]`. Shell `0x4addde fld [esp+0x2c]` (L+0x18) → 0x4ade01 R+0xaa0; `0x4b4f9d fld [esp+0x28]` → list +0x50 (0x4b4fb2) | 200, 230, 275, 340 |
| 0x0c | 13 | char[13] | internalName | Unread. 0x4b0d00 stops at +0x10. 0x4b0e70 copies it to L+0x1c.., but no L reader touches L+0x1c..0x28: 0x4adb90 reads only L+0x18 and L+0x2a; 0x4b4e40 reads only L+0x10 and L+0x18. | none | "eng01".."eng04" |
| 0x19 | 1 | u8 | lastFlag (inferred) | Unread, for the same reasons. | none | 0,0,0,1 (1 on the last record) |

### 4.2 BRAK body (26 bytes) ×4

| off | width | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0x00 | 4 | u32 | maxHp | Stored at brake data +4 (current) and +8 (max). The getter 0x46d9f0 returns ([4],[8]). | `0x4b0e25 mov edx,[esi+8]` → `0x4b0e2b mov [eax+8],edx`, `0x4b0e2e mov [eax+4],edx` (eax = `[veh+0x3cc]+0x70`, 0x4b0e1f/0x4b0e28). Shell list `0x4b5111 mov edx,[esp+0x58]` → +0x4c | 150 ×4 |
| 0x04 | 4 | f32 | brakeStrength | Nominal braking coefficient, stored at brake+0xc. A damage callback (0x46a7f0, referenced from .data 0x4f78dc) sets brake+0x10 = max(cur/max × brake+0xc, 0.2 × brake+0xc): `0x46a803 fld [edx+0xc]` / `0x46a806 fmul [0x4be308]`(=0.2), then `0x46a83a fild [edx+4]` / `fidiv [edx+8]` / `fmul [edx+0xc]` / `0x46a845 fstp [edx+0x10]`. The effective value +0x10 is read at 0x43c49a `fld [eax+0x10]`. The low-brake sound "fdmg1.wav" plays when +0x10 < 0.5×+0xc (0x43d60d/0x43d616). | `0x4b0e31 mov edx,[esi+0xc]` → `0x4b0e34 mov [eax+0xc],edx` | 1.0, 1.3, 1.6, 2.0 |
| 0x08 | 4 | f32 | mass | Added to veh+0xa4 and to the shell R+0xaa0. | `0x4b0e3f fld [esi+0x10]` → `0x4b0e48 fstp [eax+0xa4]`. Shell `0x4addee fadd [esp+0x64]` (L+0x50); list `0x4b5129 fld [esp+0x60]` | 12, 15, 17, 20 |
| 0x0c | 13 | char[13] | internalName | Unread. | none | "bra01".."bra04" |
| 0x19 | 1 | u8 | lastFlag (inferred) | Unread. | none | 0,0,0,1 |

The brake data also gets brake+0x14 = brakeId (`0x4b0e37 mov edx,[ecx+0x3c]` / `0x4b0e3a mov [eax+0x14],edx`).

### 4.3 SUSP body (30 bytes) ×4

| off | width | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0x00 | 4 | u32 | maxHp | Stored at suspension data +0 (current) and +4 (max). The getter 0x46a9f0 returns ([0],[1]). | `0x4b0d4c mov edx,[esi+8]` → `0x4b0d5e mov [eax+4],edx`, `0x4b0d61 mov [eax],edx` (eax = `[veh+0x3c8]+0x70`, 0x4b0d55/0x4b0d5b). Shell list `0x4b52aa mov edx,[esp+0x90]` | 200 ×4 |
| 0x04 | 4 | f32 | handlingCoef (inferred) | Stored at susp+0x14 and +0x18. Consumer: 0x43c6f0 `0x43c7c2 fmul [edi+0x14]` (together with veh+0x46c); the same pattern appears in 0x43ce10. | `0x4b0d69 fld [esi+0xc]` → `0x4b0d70 fstp [eax+0x18]`, `0x4b0d75 fstp [eax+0x14]` | 1.0, 1.25, 1.55, 2.0 |
| 0x08 | 4 | f32 | percent (inferred: stiffness/softness %) | susp+0x1c = (100 − value) × 0.01. The constants are 0x4bec84 = 100.0 and 0x4bec88 = 0.01. | `0x4b0d4f fld [0x4bec84]`, `0x4b0d78 fsub [esi+0x10]`, `0x4b0d7b fmul [0x4bec88]`, `0x4b0d81 fstp [eax+0x1c]` | 0, 10, 20, 45 |
| 0x0c | 4 | f32 | mass | Added to veh+0xa4 and to the shell R+0xaa0. | `0x4b0d86 fld [esi+0x14]` → `0x4b0d8f fstp [eax+0xa4]`. Shell `0x4addf8 fld [esp+0xa0]` (L+0x8c); list `0x4b52c5 fld [esp+0x9c]` | 35, 37, 41, 46 |
| 0x10 | 13 | char[13] | internalName | Unread. 0x4b0d00 stops at +0x14, and no reader of L+0x90..0x9d exists. | none | "sus01".."sus04" |
| 0x1d | 1 | u8 | lastFlag (inferred) | Unread. | none | 0,0,0,1 |

The suspension data also gets susp+8 = suspensionId (`0x4b0d63 mov edx,[ecx+0x74]` / `0x4b0d66 mov [eax+8],edx`).

### 4.4 NTBL / BTBL / STBL body (1028 bytes)

| off | width | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0x000 | 4 | u32 | count | **No handler reads it.** All three handlers index from chunk+0xc. | none | 4 in each table |
| 0x004 | 64×16 | char[16][64] | displayName[] | Display names. Row `idx` is copied as 16 bytes into L. The shell then runs it through StrLookup (localisation) (0x4b4e79..0x4b4e8a) and copies it to R+0x137 (engine, 0x4add85), R+0x147 (brake, 0x4addd0) and R+0x157 (suspension, 0x4addaf). | NTBL 0x4b0f50: idx = `engsnd_CompId(engineId)` (0x4b0f58..0x4b0f59), then `0x4b0f65 shl eax,4`, `0x4b0f6f mov eax,[eax+ecx+0xc]`, → L+0x2a (0x4b0f62..0x4b0f89). BTBL 0x4b0f90: idx = `[L+0x3c]` (0x4b0f98), `0x4b0fa1 lea ecx,[ecx+edx+0xc]` → L+0x62. STBL 0x4b0fd0: idx = `[L+0x74]` (0x4b0fd8) → L+0x9e | Rows 0..3 are used; rows 4..63 are all zero. NTBL: "261ci 6 cyl", "305ci V-8", "432ci SHO V8", "595ci V-10". BTBL: "4-Wheel Drum", "Disc & Drum", "4-Wheel Disc", "Aircraft Brk". STBL: "Stock", "Sway Bars", "Coil Overs", "EtherX Rally". |

**How the engine id resolves.** `engsnd_LoadTable` 0x469b00 is called from WinMain (0x4031d4, 0x4034e7) with "engsnd.dat". It sscanf's `" %d %d %d %s %s %s %f %s %f %s %f "` (0x469c4d) into 0x60-byte rows at 0x588e00, and the count goes to 0x58d900 (0x469c62). `engsnd_CompId` 0x469f10 finds the row whose `+0` equals the VCF engineId (0x469f26) and returns row+4, the "ENG COMP ID" column (0x469f3d). That value is then used two ways:
- as the ENGN ordinal to match: `0x4b0db3 call 0x469f10` / `0x4b0dbe cmp eax,ecx`, and 0x4b0eec/0x4b0ef4 in the shell;
- as the NTBL row.

The ids map as follows. The ids in the corpus are 0–5, 10, 20 and 99, and all are present.

| VCF engineId | ENGN / NTBL row |
|---|---|
| 0 | 0 |
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 0 |
| 5 | 3 |
| 10 | 3 |
| 20 | 0 |
| 41 | 0 |
| 50 | 0 |
| 51 | 0 |
| 99 | 0 |

Two engine-data fields are also set from the id: `engine_SetId` 0x46a060 sets engine+0x28 = engineId (0x46a06c) and engine+0x2c = engsnd row index (0x46a08d).

An id missing from engsnd.dat would make 0x469f10 return -1. The ENGN record would then never match, and NTBL would read from chunk-4 (inferred from 0x4b0f65..0x4b0f6f).

Brake and suspension ids index BRAK/SUSP and BTBL/STBL directly.

---

## 5. Handler summaries

- **0x4ad950 VCFC in-game**:
  1. Loads the VDF (0x4ad974) and the VTF (0x4ad997), then the three wheels (0x4ad9b5/0x4ad9d3/0x4ad9f1). Any failure returns 0, which aborts the file because VCFC has flag 0x20.
  2. Parses compnent.cdf with its engine/suspension/brake ids (0x4ada53).
  3. Writes armour and chassis to the veh block at +0x138..+0x19f (0x4adac1..0x4adb6b).
- **0x4adb90 VCFC shell**: copies name, vdf, vtf, armour, chassis and spare into R (0x4adbb1..0x4adc74). Loads the VDF (0x4adc82) and the wheels. Sums the wheel masses R+0x2f4 + R+0x334 + R+0x374 into R+0xaa0 (0x4adcfa..0x4add1f). Parses the cdf with names (0x4add51), copies the 3 component names (0x4add61..0x4adddc) and adds the 3 component masses to R+0xaa0.
- **0x4b3650 VCFC validator**: whitelist checks on wheels vs trucks, flag 0x1000 (0x4b3696..0x4b3839). VDF parse that captures size and hardpoint count (0x4b3868). Budget checks, flags 0x800/0x400 (0x4b3889..0x4b3924). CRC32 of the vdf, wdf×3 and compnent.cdf (0x4b3930..0x4b39f2).
- **0x4ade50 / 0x4adea0 / 0x4b3a10 SPEC**: attach the special to veh / store it in R+0xa70 / check for duplicates (§2.2).
- **0x4aeb90 / 0x4af250 / 0x4b3aa0 WEPN**:
  - 0x4aeb90 finds the hardpoint, loads the GDF, builds the weapon, adds its mass to veh+0xa4, and records the weapon in the first free slot of 0x467440(obj)+0x3a8 for ecx 10..16 (0x4af1d8..0x4af208).
  - 0x4af250 finds the hardpoint, loads the GDF name into R+0x3c8+i*0xfc, and adds mass to R+0xaa0.
  - 0x4b3aa0 checks the hardpoint, duplicate slots, forbidden GDFs, heavy-class exclusivity (flags 0x2000/0x4000/0x8000) and hardpoint type, and CRCs the GDF.
- **0x4b0350 VCST in-game**: restores current armour, chassis, velocity, the obj+0x48 value and the three component hit points (§3.1). **0x4b0520** is the shell raw copy.
- **0x4b0540 WLST in-game**: sets the 6 wheel states. **0x4b05e0** is the shell copy to V+0x4c.
- **0x4b0610 WPST in-game**: calls `weapon_SetState`. **0x4b0640** is the shell append at V+0x64 (count at V+0xbc).
- **0x4b0680 SALV shell**: calls an optional callback, which is never set.
- **0x4b0d00 ENGN/BRAK/SUSP in-game**: switches on the tag (0x4b0d08/0x4b0d13/0x4b0d1e). When the wanted ordinal comes up, it writes hit points, the coefficient and the id into the component data, and adds the mass to veh+0xa4.
- **0x4b0e70 ENGN/BRAK/SUSP shell**: raw copy of the wanted record into L (26/26/30 bytes).
- **0x4b0f50 / 0x4b0f90 / 0x4b0fd0**: NTBL/BTBL/STBL name-row copy into L.
- **0x4b1010**: `cdf_LookupComponent(id, kind, L)`, where kind 0 = engine, 1 = brake, 2 = suspension (0x4b1027..0x4b105d). Used by the shell list builders 0x4b4e40, 0x4b4fe0 and 0x4b5170.

## 6. Proposed exe function names

| addr | proposed name | evidence |
|---|---|---|
| 0x4ad6f0 | vcf_LoadForObject | pushes table 0x4fef70 at 0x4ad7c7 → LoadDef 0x4ad7cd; ".vsf" at 0x4ad808 → LoadDef(0x4ff330) 0x4ad87d (the name matches data/notes/vdf.md) |
| 0x4ad8c0 | vcf_LoadShellRecord | pushes 0x4fefb0 at 0x4ad8e0; caller shell_cb_05 0x4b58c2 logs "Error loading shell vehicle %s" (0x4b58cf) |
| 0x4ad900 | vsf_LoadShellState | pushes 0x4ff180 'VCST' at 0x4ad92e; zeroes V+0xbc at 0x4ad91d |
| 0x4b35a0 | vcf_ValidateNetJoin (now shell_cb_26) | pushes 0x500050 at 0x4b360d; CRC poly 0x4c11db7 at 0x4b35ec; caller 0x457072 prints "hacked vehicle" at 0x4570b0 |
| 0x4ad950 | bwd2_h_VCFC_ApplyToVeh | writes veh+0x138.. at 0x4adad1..0x4adb6b; cdf at 0x4ada53 |
| 0x4adb90 | bwd2_h_VCFC_ToShellRecord | strcpy name → R+0x50 at 0x4adbca; R+0xa7c/0xa8c/0xa9c at 0x4adc36..0x4adc74 |
| 0x4b3650 | bwd2_h_VCFC_Validate | budget math 0x4b38b9..0x4b3919; CRC 0x4b3930..0x4b39f2 |
| 0x4ade50 | bwd2_h_SPEC_ApplyToVeh | `0x4ade8a call 0x467280` with body+0 |
| 0x4adea0 | bwd2_h_SPEC_ToShellRecord | `0x4adec7 mov [edx+eax*4+0xa70],ecx` |
| 0x4b3a10 | bwd2_h_SPEC_Validate | duplicate test 0x4b3a3e, store 0x4b3a82 |
| 0x4aeb90 | bwd2_h_WEPN_MountOnVeh | hardpoint scan 0x4aec5f; GDFC LoadDef 0x4aec39; mass 0x4af1c7 |
| 0x4af250 | bwd2_h_WEPN_ToShellRecord | hardpoint scan 0x4af296; name → R+0x3c8+i*0xfc at 0x4af308 |
| 0x4b3aa0 | bwd2_h_WEPN_Validate | 0x5db190 scan 0x4b3ac4; forbidden gdf 0x4b3b96..; CRC 0x4b3c78.. |
| 0x4b0350 | bwd2_h_VCST_ApplyToVeh | "State file %s calls for %s…" 0x4b03cc; veh+0x138 at 0x4b041e |
| 0x4b0520 | bwd2_h_VCST_CopyShell | rep movsd 0x13 dwords at 0x4b053a |
| 0x4b0540 | bwd2_h_WLST_ApplyToVeh | writes `[veh+0x3a8..0x3bc]→+0x70→+4` at 0x4b0562..0x4b05d5 |
| 0x4b05e0 | bwd2_h_WLST_CopyShell | `0x4b05f0 add edi,0x4c` / rep movsd 6 |
| 0x4b0610 | bwd2_h_WPST_ApplyToVeh | `0x4b0627 call 0x4a34c0` |
| 0x4b0640 | bwd2_h_WPST_AppendShell | count V+0xbc at 0x4b0647/0x4b0651; dest V+0x64+n*12 at 0x4b0657 |
| 0x4b0680 | bwd2_h_SALV_ShellCallback | `0x4b068e mov ecx,[ecx+0xb8]` / `0x4b06a1 call ecx` |
| 0x4b0d00 | bwd2_h_CDF_ApplyComponentToVeh | tag switch 0x4b0d08/0x4b0d13/0x4b0d1e; veh+0x3c4/0x3c8/0x3cc |
| 0x4b0e70 | bwd2_h_CDF_CopyComponent | rep movsd to L+0x10/+0x48/+0x80 at 0x4b0f00/0x4b0f2f/0x4b0ec8 |
| 0x4b0f50 | bwd2_h_NTBL_EngineName | 0x469f10 index, `0x4b0f6f mov eax,[eax+ecx+0xc]` → L+0x2a |
| 0x4b0f90 | bwd2_h_BTBL_BrakeName | idx L+0x3c (0x4b0f98) → L+0x62 |
| 0x4b0fd0 | bwd2_h_STBL_SuspName | idx L+0x74 (0x4b0fd8) → L+0x9e |
| 0x4b1010 | cdf_LookupComponent | kind switch 0x4b1027..0x4b105d; LoadDef(compnent.cdf, 0x4ff450) 0x4b106d |
| 0x4b4e40 / 0x4b4fe0 / 0x4b5170 | shell_ListEngines / shell_ListBrakes / shell_ListSuspensions | 0x4b1010(i, 0/1/2, L) at 0x4b4e74/0x4b5014/0x4b51a4; list +0x4c = hp, +0x50 = mass |
| 0x469b00 | engsnd_LoadTable | sscanf format 0x4f8654 at 0x469c4d; WinMain pushes "engsnd.dat" 0x4031cf |
| 0x469f10 | engsnd_EngineIdToCompId | `0x469f26 cmp [ecx],esi`, `0x469f3d mov eax,[eax+0x588e04]` |
| 0x46a060 | engine_SetEngineId | `0x46a06c mov [edi+0x28],esi`, `0x46a08d mov [edi+0x2c],eax` |
| 0x467490 / 0x4674a0 / 0x4674b0 | veh_GetEngineData / veh_GetSuspData / veh_GetBrakeData | return `[[p+0x3c4/0x3c8/0x3cc]+0x70]` (Ghidra body; 14 bytes each) |
| 0x46a9f0 | component_GetHpCurMax | returns [0],[1] with default 300/300 (Ghidra body) |
| 0x46d9f0 | brake_GetHpCurMax | returns [4],[8] with default 300/300 (Ghidra body) |
| 0x46a7f0 | brake_ApplyDamage (inferred) | subtracts damage from +4 (0x46a826 `sub eax,esi` / 0x46a828 `mov [edx+4],eax`), effective +0x10 = max(cur/max·nominal, 0.2·nominal) (0x46a803..0x46a845) |
| 0x4a34c0 | weapon_SetState | "Cannot set the state on nonexistant weapons." 0x4a3523; writes 0x5aab14/0x5aab28 |
| 0x467280 | veh_AttachSpecial | "v-spcl" pushed at 0x467297; slot veh+0x3ec+slot*4 at 0x4672a1 |
| 0x4b3d50 | crc32_AccumulateFile | table 0x5dace0 at 0x4b3d8c |
| 0x4b3cb0 | bwd2_h_VDFC_ValidateCapture | 0x5db958 ← VDFC+0x18 (0x4b3cb7); 0x5db7c4 ← VDFC+0x3c (0x4b3cc0) |
| 0x4b3d30 | bwd2_h_GDFC_ValidateCapture | 0x5dacd8 ← GDFC+0x10 (0x4b3d37); 0x5db978 ← GDFC+0x14 (0x4b3d40) |
| 0x4ae5e0 / 0x4ae780 | wdf_LoadWheelForVeh / wdf_LoadWheelForShell | LoadDef(0x4ff210/0x4ff240 'WDFC', 3) at 0x4ae662/0x4ae7d9; slot arg 0/2/4 from the VCFC handlers |

## 7. Open items

- Which of +0x138/+0x158/+0x178 the damage code decrements. The .vsf pattern says +0x138/+0x158 are current and +0x178 is max (inferred); check with a live read.
- The meaning of the 100 stored at veh+0x188 and +0x19c.
- The meaning of VCST +0x39 (the double at obj+0x48), the VCST +0x49..+0x4b flags, and WPST stateA/stateB. The latter need the weapon-record (0x5aab14, stride 0x4c) family.
- There is only one .vsf sample. The .vsf distributions have n=1.
