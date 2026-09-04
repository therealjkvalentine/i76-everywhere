<!-- Produced 2026-09-04 by the fresh-start judge-panel workflow (5 proposals, 3 judges, synthesis, 2 critics, revision). Companion overview: FRESH-START-2026-09-04.md. Path shorthand: <SCR> = the session scratchpad, now archived at C:\Users\james\i76-map\recon-2026-09-04 (so <SCR>\recon = ...\recon-2026-09-04\recon). -->

# Interstate '76 (GOG 2017 Gold, i76.exe md5 9a232dcc2c164648cff20c414c1f9698): the methodology, revision 2

Date: 2026-09-04. Status: revised after two adversarial reviews (critic-dead-end, critic-completeness). Evidence base: the eleven fresh recon reports and the refutation reports under `<SCR>\recon\` (`<SCR>` = `C:\Users\james\AppData\Local\Temp\claude\C--Users-james-i76-everywhere\42a6c4bf-f9e3-4332-9f8e-c9c772ecd960\scratchpad`), plus direct reads of the pass-4 export made while writing this revision. No prior project notes were read.

Shorthand: `<FP>` = `<SCR>\recon\fp-ghidra`, `<AH>` = `<SCR>\recon\agent-harness`, `<FMT>` = `<SCR>\recon\formats`, `MAP` = `C:\Users\james\i76-map`.

---

## Changes from v1

Every fatal and missing item raised by the two critics is listed with its disposition. "Accepted" means the rule or task below was changed; "rebutted" means kept with the evidence stated.

| # | Critic | Item | Disposition |
|---|---|---|---|
| F1 | dead-end | Gate A rejected every BSS address (0x501800-0x669ef8 is zero in the file) | Accepted. Gate A now has three address classes with three tests (init / bss / iat) and a negative test set that includes 0x5a7e1c (must pass as bss, fail as init). Section 4.1. |
| F2 | dead-end | "Free anchors" wrote wrong terminal labels: LZO range, CRT-startup range, BWD2 handlers named by tag | Accepted. `library` needs a per-function evidence row (gate L); 0x4ba300-0x4ba97f and 0x4baee0-0x4bb9a0 enter as `auto`; table anchors carry every (table, tag) pair and a no-duplicate-name merge check. Section 4.2. |
| F3 | dead-end, completeness | G6 string-less truth half had no ground truth; anchored half was not blind | Accepted. String-less truth = sealed machine-checkable fact tuples, not names; name-level truth only for owners of poke-verified globals; frozen Phase 0 export for blind runs; truth-set functions and their direct callers excluded from ApplyMap. Section 4.3 (G6). |
| F4 | dead-end, completeness | Phase 1 exit (40% bytes by week 8) mis-sized; evidence supply never measured | Accepted. Week-1 evidence-supply histogram sets the exit; provisional exit is 30% of .text bytes at supported+ by week 8; primary evidence kinds defined; a paused-game snapshot of 0x4c2000-0x669ef8 is added to the first console sitting so impure leaves become emulable from week 3. Sections 3, 4.2. |
| F5 | dead-end | H0 was an on-disk md5 check never exercised against a running pristine exe | Accepted. H0 keys on the live image (.text/.rdata diff against pristine with an allowlist) and Task 1 gains a 30-minute console smoke test on day 2-3. Section 4.5 (H0), Task 1. |
| F6 | dead-end | Gate D re-introduced the n-frame drift test v1 itself called chaotic | Accepted. Gate D is split by function class: chaotic sim-core gets per-call differential only; parsers/FSM/BWD2/LZO get bit-exact per call plus drift. Compiler flags recorded beside tolerances. Section 4.4. |
| F7 | completeness | "Complete" was scoped to i76.exe while the process holds i76shell.dll (258,880 B .text, ~687 KB BSS), ZGLIDE (1.39 MB BSS), ZDX5DRAW, i7_sfrce, ANet, Strlkup, Smacker | Accepted with sequencing. `binaries\*.toml` becomes a per-module inventory; remainder counts are per module and process-wide over the declared in-scope set; the i76.exe partition remains the first target; the shell map starts at low intensity in Phase 1 (anchors only) and at full intensity after Phase 3; the 0x467470 crash entry moves under the shell map. Section 2. |
| F8 | completeness | The allocation ledger could not see the engine's VirtualAlloc pools (0x498940; WinMain pools at 0x5dd320 / 0x5dd324; 0x5dd2ec = pool + 54000) | Accepted; verified in the export this revision (`<AH>\export\functions\00498940.c`, `00402b30.c` lines 207-214). Allocation source kind `pool` added; 0x498940 and 0x499ce0 hooked; carve/free functions identified in Phase 1 from the 24 readers of 0x5dd320. Phase 2 item 3. |
| F9 | completeness | Gate C's "settled values" mixed Ghidra xref counts with capstone site counts; globals denominator was pass-1 | Accepted. Canonical refs = capstone instruction-operand sites split call/load; Ghidra's count in `ghidra_refs`; globals denominator restated from pass 4: 7,277 rows (2,049 .rdata / 2,854 initialised .data / 2,371 BSS / 3 other), computed this revision from `<FP>\pass4\hot_globals.csv`. Section 4.1 (gate C). |
| F10 | completeness | `types\i76.h` v0 carried an untested enum bit (flags & 4 as "mandatory"); walker tests 0x10/0x20/0x40/0x80/0x1000/0x2000 | Accepted. Gate T: every field width and enum bit cites the instruction that tests it; v0 ships only cited fields. Section 4.2. |
| F11 | completeness | H2's "predicted display change" capped the tweak layer at HUD-visible state | Accepted. Four verification channels of equal standing: display, consequence-poke via the snapshot ring, built-in debug screens as read-back, file round-trip, plus in-situ hook-replay. Section 4.5 (H2). |
| M1 | dead-end | Evidence base lives only in %TEMP% | Accepted. Task 0 copies `<SCR>\recon` and `<SCR>\design` into `MAP\recon-2026-09-04\` with an md5 manifest before `git init`. |
| M2 | dead-end | Parameter ID conventions entered as facts (0x4b9fc0 is cdecl/5, tagged thiscall) | Accepted. All Parameter ID conventions are `auto`; a convention claim needs call-site cleanup evidence; G3's parameter-count check is suspended for rows carrying it. |
| M3 | dead-end | G1 named the reporter, not the named function (FFB loader would become I7FF_SIM_Effect) | Accepted. G1 self-name grammar restricted; "X failed" strings anchor the callee only under a single-adjacent-callee rule. |
| M4 | dead-end | Census hooked 2,165 functions with no hookability filter | Accepted. Hookability computed in Task 2 (size >= 8 B, no branch target in first 5 B, not funclet/thunk/EH stub); census run at two hook-set sizes (200, then all hookable). |
| M5 | dead-end | No RDP/session rules | Accepted as gate H10: sittings run from the console session, monitored over OpenSSH, Frida attaches never spawns when remote, harness refuses capture while the console session is disconnected. |
| M6 | dead-end | H2 poke-while-paused collides with the H4 live canary | Accepted. Per-state canaries: paused -> PeekMessageA pump count / profiler stamp; driving -> 0x5a7e1c and the rand log. |
| M7 | dead-end | Virtual clock step unit undefined; both obvious choices wrong alone | Accepted. Advance +40 ms at the 0x4039b8 hook (one sim frame at the i76fix 25 fps target) plus +1 ms after K consecutive reads with no frame advance (spin escape, logged). |
| M8 | dead-end | No disk budget for H8 | Accepted. Per-sitting budget, xz delta rings against frame 0, compression recorded in the manifest. |
| M9 | dead-end | No token/time ceiling or stop rule | Accepted as gate Q: 150 K tokens per function across attempts, weekly cap, halt below 5 accepted/day with a full queue. |
| M10 | dead-end, completeness | Static arrays had no bound rule; BSS remainder gameable; no stride tool | Accepted as gate B plus `tools\strides.py`; unbounded array rows stay `proposed` and their bytes count as remainder. |
| M11 | dead-end | G4 two same-model drafts over the same text are not independent | Accepted. Second draft sees a different view (.pcode or raw disassembly plus callers only); agreement-when-both-wrong measured on the truth set. |
| M12 | dead-end | G7 double-rebuild diffed decompiler text | Accepted. Diff the structural inventory; text differences informational. |
| M13 | dead-end | Sentinel capture had no file-open log | Accepted. CreateFileA/fopen IAT hook log in every capture manifest. |
| M14 | dead-end | No throughput re-projection for the x87 majority (717 functions, 462,513 B) | Accepted. Human bytes/day on x87 functions measured in Phase 3's first fortnight and the calendar re-projected in `progress.json` at every subsystem closure. |
| M15 | completeness | No translation-unit / link-order reconstruction | Accepted. `tools\tu_boundaries.py` -> `modules.tsv`; `tu-neighbourhood` is a weak combinable G2 kind, never primary. |
| M16 | completeness | VC++ 5.0 SP3 never acquired | Deferred to the user (open decision 1); the plan states what changes with and without it. Gate D works with VS2019 `/arch:IA32 /fp:precise` under measured tolerances. |
| M17 | completeness | Sibling-build Version Tracking (nitro.exe) not scheduled | Accepted as time-boxed Task 5b, conditional on the user's permission to extract nitro.exe from the GOG installer in Downloads. |
| M18 | completeness | C++ island not typed via EH tables | Accepted. `tools\eh_decode.py` over the 30 FuncInfo / 30 UnwindMap arrays at 0x4bffa8-0x4c03a0. |
| M19 | completeness | 27-slot exe->shell callback table absent from anchors | Accepted; verified in `<AH>\export\functions\004022e0.c` this revision (27 slots, `GetProcAddress(DAT_005dd2f8, "ShellMain")`). Task 4 anchors them as `shell_cb_NN`. |
| M20 | completeness | Built-in (non-plugin) render path had no closure plan; H0 stamp omitted what selects it | Accepted. Manifest carries command line, dgVoodoo.conf hash, resolution, FPSLimit, Z*.DLL md5s; one census run on the built-in path; rasteriser is a Phase 3 subsystem. |
| M21 | completeness | I76EDIT.EXE / BUILDER.DOC / Asset Bible unused as writer-side oracle | Accepted in Phase 2 typing. |
| M22 | completeness | Built-in debug facilities unused as instruments | Accepted as week-2 item 007. |
| M23 | completeness | Hack prevention / cheater flag not located before the tweak layer | Accepted as a Phase 1 string-anchor item with a cheat-flag column in the tweak audit. |
| M24 | completeness | Determinism scope excluded heaps, pools, non-sim threads | Accepted. Determinism diff covers .data, private heaps and both pools; excluded threads listed per capture. |
| M25 | completeness | FSM semantics ported as addresses, never tested | Accepted. FSM conformance corpus of hand-assembled loose .msn programs in Phase 3. |
| M26 | completeness | H9 seeded with one crash | Accepted. Seven entries seeded (VOGONS, Peelar, UCyborg) with i76fix/AiO offsets as first evidence. |
| M27 | completeness | No time-boxed symbol-leak hunt | Accepted. Two-day hunt in Phase 0 with a written stop rule. |
| M28 | completeness | Dependent measurements not listed as H7 blockers | Accepted. `requests\measurements.yaml` with one sentence, owner, earliest task, and the decision each result flips. |
| M29 | completeness | Missing veteran conventions: `synthetic` status, in-situ replacement, contract-first docs, progress board | Accepted. `synthetic` added; in-situ Detours replacement is gate D tier 1; each `subsystems\*.md` opens with a contract; `progress.svg` generated per commit. |

Rebuttals, stated once: none of the critics' fatal items survives as a disagreement. Two partial rebuttals on emphasis: (a) the process-wide scope (F7) is accepted for accounting but not for sequencing; the exe holds the simulation, physics, AI, FSM, loaders and renderer seams, so it stays first and the shell follows with the same gates; (b) in-situ Detours replacement (M29) is accepted as tier 1 of gate D but it perturbs a frame-coupled sim, so it never replaces the A/A control rule.

---

## 1. The approach and why

### 1.1 Thesis

The product is a plain-text, git-versioned map (names, prototypes, types, globals, heap types, evidence) covering every byte of the in-scope modules, with Ghidra as a rebuildable cache (1 min 54 s headless rebuild, 53.5 s decompile-all measured: `<AH>` section 1). Agents read exported text and write proposals; a single merge worker writes Ghidra; gates decide. Dynamic work runs in scheduled, scripted, retained console sittings and is folded back as evidence. Hooks, pokes, proxies and replacements are consumers of the map, generated from it, never the way the map is built.

This is the map-first proposal (leaderboard 127) with the grafts the three judges asked for, each credited below, and with the two critics' corrections applied.

### 1.2 Why this binary suits it (measured, not hoped)

- Fixed base 0x400000, relocations stripped, no ASLR/NX, dynamic MSVCRT (86 imports), 244 imports from 13 DLLs (pe-fingerprint findings; `<FP>` section 2). Every address is a constant for the life of the project.
- Pass-4 Ghidra: 2,165 functions, 722,640 of 765,525 .text bytes in bodies (94.3%), 75 gaps totalling 25,763 B, 1,783/1,784 decompile (`<FP>` sections 0, 11; `<AH>` section 1).
- Dense ground-truth anchors: 2,449 strings with 1,674 xrefs from 353 functions (`<FP>` section 9); 244 imports; six BWD2 descriptor tables with 115 non-null (tag, handler) rows and 70 distinct handlers (`<SCR>\recon\bwd2-refute\tables.txt`); an 18-name renderer table at 0x608ba4-0x608be4 (`<SCR>\recon\refute-renderer-plugin\REPORT.md` section B); a 27-slot exe->shell callback table in 0x4022e0; 26 HeapCreate creator functions tagged by strings such as `ordnc`, `clasfn`, `chnkmgr` (`<FP>` section 9); 82 FSM prototype names and 166 gamekey names (strings-mining sections 5.3-5.4).
- The user's own hygiene lessons map one-to-one onto machine-checkable gates (section 4.5).

### 1.3 What the evidence says about the alternatives (why not them first)

- Dynamic-first: no finisher built a map from runtime observation first (prior-art section 3.2); "no name without a capture" idles ~350 free anchors and makes never-executed code (96-way FSM dispatcher at 0x412ce0, 12 dpSend callers, 75 gaps) un-nameable by construction. Its components are the right dynamic batches inside this plan.
- Leverage-first: cross-build addresses do not transfer (That Tony's 0x40EBB0/0x40D0D0/0x40BF40 are mid-instruction in this build; the FSM functions are 0x412ce0/0x414670/0x410a10: `<SCR>\recon\fsm-addr-refute\REPORT.md`); masked signatures collapse to the 0.1-0.2% null across a compiler change (nitro-vs-i76 section 3); constants and strings do transfer (refute-nitro-map section B). Ported names are proposals under gate P, and the zero-inference items (LZO source, ANet headers, DX5 headers with vtable slots checked at known sites) are absorbed into Phase 1.
- Theseus-first: adopts the historically slowest goal (OpenLoco 7.5 years to zero globals; SW_RACER_RE, VC++ 5, 2,132 functions, 71.2% after 8 years: prior-art sections 1.5, 1.10) and reaches the map last. Its md5-gated launcher, GLOBAL(addr,type) header, snapshot ring at the sim tick and differential harness are consumers here.
- Data-first: the strongest per-finding truth chain (sentinel -> null scan -> spread -> poke -> read-back) but its reach stops at file-originated state; ~1,500 dataless functions remain. Its round-trip gate, chunk-descriptor enumeration and sentinel protocol are Phase 0-2 work here.
- Raw decompiler dumps, byte-exact matching as a gate, annotated reassembly, GUI-bound MCP agents, kernel tracing (CE Ultimap2/DBVM under VBS), PANDA/Win98: avoided for the reasons in prior-art section 3.4 and `<AH>` section 3.10.

### 1.4 Grafts and credit

- From prop-data-first: chunk-descriptor tables from the callers of the generic walker 0x4b3db0 (0x4b41e0, 0x4b42b0) as an anchor source; the round-trip gate R; sentinel-in-data as the standard H2 route; the 20-row blind tweak audit on two draws.
- From prop-dynamic-first: the Frida allocation ledger keyed (heap, size, return address) and the CModule-counter census as the first console sitting; the A/A idle-churn measurement of p before any A/B; the funnel format for every scan; the stepped monotonic virtual clock (never a constant pin: busy-wait at 0x479bf2, timeouts at 0x42340d/0x4237fb/0x423962, ttd-refute section 4).
- From prop-theseus-first: the md5-gated launcher that prints path + md5 + tool version atop every log; the in-process snapshot ring taken at the sim tick by hooking the `call 0x49c920` at 0x4039b8 (the site i76fix uses); the differential harness for the hard subset; the emulated-execution evidence kind (Unicorn 2.1.4 already ran the game's own LZO decoders on 5,623 entries byte-identically: zfs-lzo-refute section 3b).
- From prop-leverage-first: DX5/DirectSound vtable typing in week 1 with slot numbers checked at the three known sites (+0x18 CreateSurface with dwSize 0x6c, +0x64 Lock, +0x8 Release: `<FP>` section 12); ANet/Strlkup prototypes from source (engine-lineage sections 3.1-3.2); LZO 1.00 source for the decoder block; the constant-anchor pass over the p-code export with a uniqueness rule; `which_build.py`.
- From the judges: the address-space gate and the counting-method gate (missing from all five proposals).
- From the critics: everything in the table above.

---

## 2. Scope: the process, not the file

The user's goal is every value in the running game. `MAP\binaries\` is therefore a module inventory, one TOML per module, each with md5, sections, byte totals, status and in-scope flag:

| Module | .text / static data | Symbols, relocs | Scope and sequencing |
|---|---|---|---|
| i76.exe (9a232dcc...) | 765,525 / 22,408 + 1,736,440 (260,096 initialised, 1,476,344 BSS) | none / stripped | Primary partition, Phases 0-4 |
| i76shell.dll (1998-02-19, LINK 5.10, MSVCRT) | 258,880 code / ~687 KB BSS | relocs present; assert paths `D:\TVF\I76Upgrade\Shell\Source Files\Carcnfg.cpp`, `Shnet.cpp` (strings-mining section 2.1); 1997 sibling I76SHELL_1083.DLL (VC 4.2, debug CRT) for Version Tracking | Anchors-only map from Phase 1; full map after Phase 3 with the same gates; owns the Gold 12->13 crash entry (0x467470 dereferences `[EAX+0x3BC]+0x70` with a null from the shell's data: web-sweep section 3.1) |
| ZGLIDE / ZREDLINE / ZDX5DRAW / zpowervr | ZGLIDE .data 1,474,580 virtual vs 20,480 raw | 19 exports each (16 for ZDX5DRAW) | Export ABI typed in Phase 1 (needed for the proxy); internals after the exe |
| ANETDLL + WINET/WIPX/WMODEM/WSERIAL | - | LGPL anet-0.10 source; CTP2 anet2.map (824 symbols, 261 `_dp*`); 37 of 42 exports declared in 0.10 headers (engine-lineage section 3.1) | Prototypes only; internals out of scope unless a netcode question needs them |
| Strlkup, Getinfo, i7_sfrce, SMACKW32, viddll | - | Strlkup/Getinfo source in anet; Smacker 3.0e is RAD's | Boundary typing only |
| dgVoodoo, win32.dll (GOG shim), audiere, u32x.dll, i76wheel.exe, STRLKUP.DLL (2026 wrapper) | - | modern | Never treated as 1998 code; excluded from partitions; md5-stamped in every manifest |

Remainder counts (section 5) are reported per module and process-wide over the in-scope set. The exe partition is the first zero the plan aims for; the shell is the second.

### 2.1 Address classes and the in-file layout (used by gate A)

- `.text` 0x401000-0x4bbe55 (765,525 B), file offset = VA - 0x400c00.
- `.rdata` 0x4bc000-0x4c1788 (22,408 B), file = VA - 0xC00; IAT 0x4bc000-0x4bc404 (244 thunks + 13 nulls).
- `.data` initialised 0x4c2000-0x501800 (260,096 B), file = VA - 0x1400.
- `.data` BSS 0x501800-0x669ef8 (1,476,344 B): zero in the file, loader-zeroed; the hottest globals live here (0x59bc00 cluster, 0x6439d8, 0x5dcec0, 0x5dd320, 0x5a7e1c, 0x608ba4-0x608be4, 0x5dd2bc-0x5dd2e8, 0x52bbdc-0x52bbe4, 0x655180).
- `.rsrc` 0x66a000 (920 B, VS_VERSION_INFO).

---

## 3. Phases

Calendar weeks assume the user at roughly 15-20 h/week plus agents. Console sittings are the constrained resource: 3D does not initialise over RDP, so every sitting is scheduled, scripted and retained (H8, H10).

### Phase 0: Foundation (weeks 1-2)

Goal: a rebuildable, gated, measured starting point; the build identity locked on the live image; all zero-inference anchors applied; the first console sitting done.

Steps: the ten tasks of section 7. Tools: Ghidra 11.4.1 headless, Python 3.13 (pefile, capstone, numpy, pywin32), git, Frida (install), Unicorn 2.1.4 (present), VS2019 cl (present, not on PATH).

Deliverables: `MAP` repo with `recon-2026-09-04\` archived; `ghidra\export\` (2,165 .c/.pcode), `callgraph.json`; `symbols\functions.tsv`, `globals.tsv`, `strings.tsv`, `imports.tsv`, `tables.tsv`, `modules.tsv`, `regions.tsv`; `types\i76.h` v0 (cited fields only); `status\evidence_supply.json` (histogram); `status\truthset.json` (sealed); `requests\measurements.yaml`; captures 000-008; gate scripts as executables.

Exit criteria: double rebuild reproducible (structural diff empty); H0 launcher refuses the live patched exe (md5 4fabc30303c7a327fbe15be58cb868c5) and accepts the sandbox; smoke test capture retained with the H0 stamp; evidence-supply histogram published and the Phase 1 exit set from it; first sitting yields census, ledger, p, paused snapshot and the sentinel armour label at `verified`.

Effort: ~40 h human, agents on tasks 2-5 and 8-9, two console sittings (day 2-3 smoke, day 8-10 first batch).

### Phase 1: Anchors, tables, leaves, formats (weeks 2-8)

Goal: name and type the part of the binary that the anchors reach without inference, and measure the drafter process on it.

Steps:
1. Table anchors: six BWD2 descriptor tables (70 distinct handlers; EXIT handler 0x4b4290 anchored once; shared handlers named with all (table, tag) pairs, e.g. `bwd2_h_ENGN_BRAK_SUSP_4ff3a0`); the six 125-entry key tables (0x4f4ca8, 0x4f56f0, 0x500f98, 0x501190, 0x501388, 0x501580); the 232-entry dispatch table 0x4f9538 (4 targets, 5 call sites); the 16-handler table 0x4c2994; the 27 shell callbacks; the 18 renderer slots; the FFB slots 0x52bbdc/e0/e4; the display-mode table 0x4f9e08 (7-dword records).
2. Library and boundary rows under gate L: LZO object (0x4ba980 lzo_init-like, 0x4ba9e0, 0x4baa00 lzo1y_decompress, 0x4babd8 lzo1x_decompress, 0x4badb0 adler idiom, ending 0x4baed5) each with the asm-shape evidence from zfs-lzo-refute section 2; `__allshl`/`__allshr` (FID); the 42 `Unwind@` funclets and 24 EH stubs (`synthetic`); CRT entry 0x4ba0e0 (396 B). Everything else in 0x4ba300-0x4bb9a0 stays `auto`.
3. DX5 COM typing at the 404 `call [reg+off]` sites after the three-site slot check; ANet/Strlkup prototypes on the 10 `dp*` and 5 `StrLookup*` thunks; Smacker ordinals 2-38 (0x499d60-0x49ae50).
4. Loader spine from the formats work: ZFS (0x4b9800 open, 0x4b9bd0 record read, 0x4b9fc0 dispatch as cdecl/5 by call-site evidence), VFS (0x4b28c0, strides 0x10c/0x30), BWD2 walker/def loader/REV handler (0x4b3db0/0x4b41e0/0x4b4610; ext table 0x5003b8; header table 0x500328), writer 0x4b4840 and the save writers 0x4b0900-0x4b0cc0; the silent logger 0x42d5d0 (`ret`).
5. Leaves-first agent grind on the 478 leaves (95,532 B) and the <=30-line band, with the emulated-io evidence kind on the ~196 pure leaves and, from week 3, on impure leaves against the paused snapshot (gate E).
6. Sim-clock cluster (0x49c7f0, 0x49c920, getters 0x49c8b0/0x49c8c0/0x49c7d0/0x49c7e0), profiler (0x498af0-0x4990b0), FSM trio, rsqrt 0x495000 with its LUT 0x655180, hash clusters (2029/109 buckets at 0x4461c8-0x44ae22 and 0x44748a...), pools (0x498940, 0x498a00, 0x498a50, 0x499ce0 and the carve functions among the 24 readers of 0x5dd320), hack-prevention and cheater-flag functions (string anchors `has tried to join with a hacked vehicle`, `I'm a cheater`, `Cheaters aren't allowed to advance`).
7. Shell anchors-only pass: assert strings, `TMPackDataBaseObj::GetDBItem`, `DDRAW_*`/`DisplayDib*` names (strings-mining section 2.1), Version Tracking against I76SHELL_1083.DLL (same source, two compilers: pe-fingerprint).
8. `tools\tu_boundaries.py` -> `modules.tsv`; `tools\eh_decode.py` -> classes for the C++ island (117 functions, 74,069 B at 0x472000-0x488000; 30 FuncInfo at 0x4bffa8-0x4c03a0; 16 `operator new` sites in 0x473960 give class sizes).

Deliverables: functions.tsv with every anchored/library/synthetic row evidenced; i76.h with loader structs and DX5/ANet types; weekly blind-eval scores; `status\progress.json` trend.

Exit: >= 30% of .text bytes at `supported` or better (provisional; finalised from the week-1 histogram); every import wrapper, table target, BWD2 handler and loader-spine function at `anchored` or `supported`; G6 fact-tuple score above the floor; gate Q not tripped.

### Phase 2: Globals, structs and the dynamic batches (weeks 5-12)

Goal: type the static data, recover heap and pool object layouts, convert captures into write-verified labels.

Steps:
1. Static globals by owner: start from the 7,277 code-referenced addresses; width from the accessing instruction; reader/writer sets from the export; `tools\strides.py` for arrays (gate B); first-write-time map from the snapshot ring; BSS status column `{array(stride,count), struct, scratch, never-written, unowned}`.
2. Sentinel campaigns per format family (VCFC/WEPN/SPEC, then VDF/GDF/WDF/CDF/XDF/VTF/SDF), one family per launch, many sentinels per variant file, with the file-open log (M13) and the loose-override rule tested in the first sitting (formats section 13 leaves it open; stored-mode ZFS repack is the fallback, legal per 0x4b9bd0).
3. Heap and pool universe: ledger keyed (source, heap or pool id, size, return address); types split when two instances disagree on an accessed offset (H6); heaptypes.tsv with a `source` column `{win32-heap, msvcrt, new, pool-A(0x5dd320), pool-B(0x5dd324)}`.
4. Writer-side oracles: I76EDIT.EXE strings (CLASS_ID_*, surface enums), BUILDER.DOC (640 m grid, 5 m resolution, far clip 600), the Asset Bible class ids, checked against i76.h before any of them enters (gate P, single instance).
5. Debug screens as read-back channels: MONO_DEBUG_*, FSM_DEBUGGER, DAMAGE_DEBUG_*, HASH_DEBUG_*, ALTREP_DEBUG_*, NETWORK_POSLOG_TOGGLE, TOGGLE_FRAMERATE bound in the sandbox keyboard.map (week-2 item 007 decides which render).
6. Determinism layer: stepped virtual GetTickCount at IAT 0x4bc100 (M7), pinned srand/time (0x402b30/0x4a9020/0x4ad260), joyGetPosEx record/replay through the WIN32.dll seam, mciSendCommandA and I7FF_* pinned; criterion p = 0 over .data, private heaps and both pools between two runs with identical input logs; excluded threads listed.

Deliverables: globals.tsv with widths/owners/labels; heaptypes.tsv; sentinel labels at `verified`; determinism report with n and the first diverging dword if non-zero.

Exit: every hot global in the top 200 by refs has a typed row with reader/writer sets; every ledger and pool type seen in the capture corpus has a struct covering every accessed offset; >= 100 `verified` semantic labels across all four H2 channels; p = 0 achieved or the blocker stated (H7).

### Phase 3: Subsystem closure (weeks 10-30)

Goal: close whole subsystems with a written contract each, corroborated across independent instances.

Order (anchors first, x87 last): sound/CD audio (DirectSoundCreate at 0x425c10; mciSendCommandA in 0x423b30-0x424ac0), input (166 gamekeys, six key tables, joystick seam), FSM VM (0x414670 opcode switch, 0x412ce0 action dispatcher, 0x410a10 match_prototype) with the conformance corpus (M25), loaders and caches (mesh cache 12*k+0xaab hash; VFS/PIX/ZIX), renderer seams (plugin table; the built-in path selected when no -glide/-redline/-d3d/-powervr switch is present: flag 0x504be8 stays 0 and 0x42d0c0 runs), world/mission/terrain, AI tactics (81 labels), damage/weapons, physics (0x43a5d0/0x418200/0x437230 with 400-600 x87 instructions each), netcode call sites (12 dpSend callers 0x455fa0-0x456640), profiler, shell boundary.

Each `subsystems\<name>.md` opens with a one-paragraph contract, then members, anchors, globals, heap types, captures, open blockers. Human bytes/day on x87 functions is measured in the first fortnight and the calendar re-projected at every closure (M14).

Exit per subsystem: zero `auto` rows in the member set; every member's regenerated decompilation free of `FUN_/DAT_/param_/local_/undefined/in_EAX/unaff_` or each residual listed with a reason; contract corroborated by >= 2 independent instances (static + capture, or two captures).

### Phase 4: Long tail and completeness audit (weeks 28 onward, open-ended)

Goal: the operational definition of complete (section 5) for the exe, then the shell.

Steps: forced execution for never-seen code (FSM injection via loose .msn, debug keys, multiplayer loopback, the software render path); static unreachability proofs for the residue (no code xref, no data pointer, not in any table, not among the 116 computed-jump targets, never executed across the corpus); dead-with-proof tagging; array bounds for every BSS pool; the shell map at full intensity.

Exit: `status\completeness.md` reports zero untagged .text bytes, zero unowned referenced data addresses, zero unbounded array rows, zero untyped ledger/pool keys, zero unverified labels in the tweak manifest, for the exe; then the same for the shell.

### Phase 5: Consumers, the tweak-anything layer (from week 10, in parallel)

Generated from the map, never hand-addressed:
- `i76_map.h` with `GLOBAL(addr,type)` for every typed global and `ORIG(addr,proto)` for every prototyped function.
- `i76poke` CLI: every write reads back and asserts (H3), logs itself as a capture, refuses while H0 fails.
- `i76hook.dll` (Detours/MinHook) loaded through the existing I76SHELL.DLL LoadLibraryA seam at 0x4022e0 (no exe patch): hook table and callback signatures generated from functions.tsv with the hookability column; named-pipe peek/poke; the virtual clock; the snapshot ring at 0x4039b8.
- Proxy ZGLIDE.DLL (19 exports; 18 resolved by the exe; all cdecl by call-site cleanup: refute-renderer-plugin section F) and proxy WIN32.dll (timeGetTime/joy* seam) for logging, determinism and replacement.
- Byte-patch generator emitting md5-guarded patches in the i76fix style.
- Differential replacement under gate D for the hard subset (physics, FSM interpreter, rsqrt).
- Milestones that prove "anything": frame limiter as a hook replacing the i76fix patch at 0x4039b8; draw distance/far clip; FOV/aspect; the FFB descriptor at 0x4f2328 (0x16c B) and the three I7FF_* pointers; FSM action injection; a cheat-flag column on every tweak (M23).

Exit: the 20-row blind tweak audit passes on two independent draws (20 random `verified` rows -> 20 verified changes each), and >= 50 replaced functions spanning every rate class pass gate D.

---

## 4. Gates (each a testable rule; each produces a machine-readable line)

### 4.1 Address and counting gates

Gate A (address space). Every number entering the map carries a class tag and passes the class test in `tools\gen_tables.py --verify`:
- `init`: VA in 0x401000-0x501800 (or .rdata/.rsrc); the file bytes at the section-delta offset contain the claimed literal, or a non-zero value consistent with the claimed type.
- `bss`: VA in [0x501800, 0x669ef8); accepted only if a .text instruction's disp32/imm32 decodes to it, or to an enclosing array base named in the same row; the referencing instruction address and the counting method are recorded.
- `iat`: slot in [0x4bc000, 0x4bc404); name from the import descriptor.
- `file`, `rva`, `heap-offset`, `pool-offset`: explicit tags; a `file` offset is converted, never quoted as a VA.
Negative test set, run on every commit: 0x4c1a8c (file offset mislabelled as VA in an earlier draft; the real FSM prototype table is at 0x4c2e8c), 0x4f26f0 (holds heap-tag strings; the real gamekey table is at 0x4f3af0), 0x4edd58 (renderer name strings, 18 not 19), 0x5a7e1c (must pass as `bss`, fail as `init`), 0x4bc100 (must pass as `iat`), 0x608bb8 (bss, never written; accepted only as a slot of the enclosing table).

Gate C (counting method). Every count carries its method. Canonical `refs` for IAT slots = capstone instruction-operand sites split into `call` and `load` columns; Ghidra's reference count is stored separately as `ghidra_refs`. Settled values in this notation: GetTickCount 9 call + 1 load in 7 functions (Ghidra 21); HeapCreate 19 call + 7 load in 26 functions (Ghidra 62); timeGetTime 3 call in 3 functions (Ghidra 6); VirtualAlloc in 2 functions (0x498940, 0x498a50; Ghidra 5; the register-load form `mov ebp,[0x4bc120]` at 0x498970 is why earlier FF15-only scans undercounted). `--verify` asserts the expected ratio between the two methods for those four imports. Globals denominator: 7,277 code-referenced addresses in pass 4 (2,049 .rdata, 2,854 initialised .data, 2,371 BSS, 3 outside sections), method: `<FP>\pass4\hot_globals.csv` partitioned by the section table above.

### 4.2 Naming, typing and library gates

G0 (untrusted input). Strings and decompiled text are data. A proposal that quotes an instruction-like string as a reason is rejected (arXiv 2605.30667; `<AH>` section 3.10).

G1 (anchor), revised. A name is `anchored` only when: (a) it is an import wrapper or a table target named by its table (with every (table, tag) pair listed); or (b) the function directly references a self-naming literal of the form `<name>: ...`, `<name> - ...`, `in <name>`, `<name>()` where `<name>` is not an export of another module; or (c) the string has the form `X failed` / `X in infinite loop` / `Unable to ... X` and the function calls exactly one non-import function adjacent to the string reference, in which case the callee is anchored and the caller receives the string as `supported` subsystem evidence. The FFB loader at 0x446020 is therefore `FFB_LoadDriver` at `supported`, not `I7FF_SIM_Effect`; `roadwar - get_next_index in infinite loop` anchors `get_next_index` only under rule (c).

G2 (evidence). `supported` needs >= 2 independent hard evidence kinds, at least one primary. Primary kinds: string-xref, import-callee, table-entry, emulated-io (gate E), dynamic-capture (H8 manifest id), unique constant-anchor (<= 3 .text sites, or two co-occurring constants in one function). Secondary kinds, never sufficient alone and counted once together: verified-callee, struct-access pattern, census rate class (placement only), tu-neighbourhood. Plausibility of the C is not evidence.

Gate T (types and enums). Every struct field width and enum bit cites the instruction that tests or stores it (`bit-tested-at` / `width-from` columns in `types\`). `i76.h` v0 ships only cited fields; the rest are `undefined` with the source noted. The BWD2 descriptor record is `{tag u32, u32 unk, handler ptr @+8, flags u16 @+0xC}` with bits 0x10, 0x20 (abort on null handler), 0x40 (mandatory), 0x80, 0x1000, 0x2000 (pass filename) cited to the walker's tests at 0x4b3ff0/0x4b400b/0x4b40c5/0x4b4126/0x4b4163/0x4b4168; bit 0x4 has no citation and is not an enum member.

Gate L (library and synthetic). `library` needs a per-function evidence row: asm-shape match against source (LZO 1.00 `lzo1x_d.ch`/`lzo1y_d.ch` branches, cited in zfs-lzo-refute section 2), FID match, or an emulated-io identity against the reference implementation. Ranges are never marked library. `synthetic` covers compiler-generated code: 42 `Unwind@` funclets (11 B each, 0x4bba40-0x4bbe40), 24 EH stubs `mov eax,FuncInfo; jmp __CxxFrameHandler`, `_ftol`-style thunks, intra-module thunks; these leave the naming denominator honestly.

Gate K (conventions). Every calling convention and parameter count from Decompiler Parameter ID is `auto`. A convention claim needs call-site cleanup evidence (`add esp,N` after the call, or `ret N`), the method refute-renderer-plugin section F used. G3's parameter-count check is suspended for rows carrying such an item. Known correction: 0x4b9fc0 is cdecl with five stack arguments `(src, size, flags, dst, flags>>8)`, not thiscall/5.

Gate N (names unique). The merge script rejects two rows receiving the same name; a tag-derived name must list every (table, tag) pair pointing at the function (0x4b4290 EXIT appears 31 times; 0x4b0d00 serves ENGN/BRAK/SUSP at 0x4ff3a0-0x4ff420; 0x4b0e70 serves the same three at 0x4ff470-0x4ff4f0; VCFC maps to 0x4ad950/0x4adb90/0x4b3650 in three tables).

Gate B (bounded arrays). An array claim needs stride evidence (imul/lea scale in a referencing function, `tools\strides.py`) and a bound from one of {compare immediate in the loop, HeapCreate/VirtualAlloc/pool size, observed max index in a capture}. Rows without a bound stay `proposed` and their bytes count as remainder. "Absorb unreferenced bytes" is not a rule.

### 4.3 Process gates

G3 (consistency). After ApplyMap, re-decompile the function and all callers/callees; any new `WARNING:`, `undefined`, `in_stack`/`unaff_` artefact reverts the row to `proposed`, except where the reviewer records an override with reason (correct struct types can raise warning counts transiently) and except the parameter-count check under gate K.

G4 (consensus, independent views). Two drafts: draft 1 sees the `.c` with callers/callees; draft 2 sees the `.pcode` or raw disassembly plus callers only. Only the intersection of name and field claims is accepted; disagreements requeue with both views. The truth set records agreement-when-both-wrong so G4's effect is measured, not assumed.

G5 (dynamic). Any runtime-behaviour claim cites a `captures\<id>\manifest.json`. Static and structural facts (anchors, tables, math helpers, funclets) need no capture.

G6 (truth set), revised. Two sealed halves, evaluated weekly against the frozen Phase 0 export (`ghidra\export-frozen\`):
- Anchored half (30): functions with G1 names, withheld; the withheld functions and their direct callers are excluded from ApplyMap so their names never enter the cache or the regenerated corpus.
- String-less half (30): sealed fact tuples, not names: `{callee set from the export, globals written (disp32 targets), census rate class with n, ledger/pool key, emulated input->output table for pure leaves}`; a draft is graded by contradiction count against the tuple. Name-level truth for a string-less function only when it owns an H2-verified global (the writer of a poke-verified label is a fact).
Bulk acceptance halts when the anchored half falls below 80% (Phase 1) / 90% (Phase 4), or the string-less half exceeds 1 contradiction per 4 tuples.

G7 (revert-ability). Each merge is a git commit; decompile failures > 1 (baseline: FUN_004b06b0), or rising `undefined4` parameter counts, auto-revert. Reproducibility is checked by diffing the structural inventory (functions.json minus timings, prototypes, xref counts); decompiler text differences are informational.

Gate Q (budget and stop rule). Per function: 150 K tokens across all attempts, then parked `budget-exhausted` with the last blocker sentence. Per week: a token cap set by the user (open decision 4). Process: below 5 accepted rows/day with a full queue halts drafting pending a method change. All three reported in `progress.json`. Prior art: an unattended Opus loop "could burn through the Claude 20x Max plan in a matter of days" and plateaus at 60-75% (prior-art section 1.15).

Gate S (static-first requests). Every `requests\dynamic-*.yaml` item is checked against the export and the refute corpus before it may cost a console sitting. Already settled statically, never to be requested: the sim clock (0x49c7f0/0x49c920, dt = delta(GetTickCount) * 0.001 clamped to [0.001, 0.2] s in 0x4fe428; refute-timer-claim section 3); the renderer slots (0x608ba4-0x608be4, 18 names); the plugin ABI convention (cdecl); the LZO identity (emulated, 5,623 entries).

Gate P (ported names). Any name, type or address from Roanish, That Tony, Peelar, VOGONS, i76fix, UCyborg or the user's earlier notes enters as `proposed` with `source_instance` and counts as one instance under H6. It reaches `supported` only with a GOG-side anchor (string xref, unique constant, table entry, capture, or a Version Tracking match with a stated score and no implied-match propagation). Cross-build and sibling work is time-boxed at 5 days with a stop rule: a phase ends when accepted names fall below 5/day.

Gate R (round trip). No parser output counts as evidence until parse -> serialise -> parse over the full corpus (6,116 ZFS payloads, 80 .msn, 81 .ter, 300 .vcf, loose files) reports 0 byte diffs; LZO recompression identity is measured and recorded, not required (LZO 1.00's compressor is not reproducible with 2.x). Stored-mode (method 0) repack is the archive gate: the loader returns raw bytes when `flags & 6 == 0` (zfs-lzo-refute section 2).

Gate E (emulated-io). A pure leaf (no data-section varnode in `.pcode`) is run under Unicorn on generated inputs and its input->output table is a primary evidence kind when an oracle-library entry predicts it (math identities with ulp tolerance, LUT recognisers, sort/hash/strcmp/memcpy semantics, 3x3/4x4 matrix ops, the 0xbfc rsqrt trick). Impure leaves are emulated against the paused-game snapshot of 0x4c2000-0x669ef8 taken in the first sitting (H8 capture 002), with the referenced bytes recorded. A table without an oracle prediction is data, not evidence.

### 4.4 Replacement gate (consumer, not map builder)

Gate D, split by class.
- Tier 1, in-situ (re3 pattern): Detours one function, run original and replacement on each live call, diff outputs and side effects for N calls; cheap, perturbs the sim, so it is paired with an A/A control (H1) and used for non-chaotic functions first.
- Tier 2, recorded-state replay off the console: inputs/outputs of N invocations from a trace corpus; ints, bytes and pointers-as-arena-offsets bit-exact; floats within a per-function tolerance measured as the max ulp error of the replacement compiled with VS2019 `/arch:IA32 /fp:precise /Oy /O2` over the corpus, recorded in i76.h beside the prototype.
- Chaotic sim-core (physics, integrators, anything on the 38-caller dt path): per-call differential only; no drift test (per-tick state diverges after one ulp: prior-art section 1.9).
- Non-chaotic (parsers, FSM opcode switch 0x414670, BWD2 handlers, LZO, hash functions): bit-exact per call and an n-frame drift test over >= 600 ticks is legitimate.
- Every certified row needs a branch-coverage statement over the corpus and a mutation test (a deliberately wrong replacement must fail) before the harness certifies anything.
- reccmp against VC5 SP3 codegen, if the compiler is acquired (open decision 1), is a ratchet: the score is recorded and must not fall below the function's previous score; never a gate.

### 4.5 Hygiene gates (the user's lessons, as executable rules)

H0 (check which build is live). The launcher accepts a target only when the live image's .text 0x401000-0x4bbe55 and .rdata 0x4bc000-0x4c1788 equal the pristine bytes except in an explicit allowlist (initially empty; the patched build's +132 .text bytes may be allowlisted with their hash only if they sit past 0x4bbe55). `tools\which_build.py` writes on-disk md5, live .text diff, import DLL names (WIN32/WINMM/u32x), i76shell.dll timestamp, command line, dgVoodoo.conf hash, resolution, FPSLimit, every Z*.DLL and wrapper md5, the process SessionId, into every capture manifest; the merge script rejects evidence whose md5 is not 9a232dcc2c164648cff20c414c1f9698 unless tagged `patched-build-only` and the claim is about the patch. Every log begins `launched <path> md5 <md5> <tool> <version>`.

H1 (same-condition control, report n). No A/B is accepted without a preceding A/A run of the same length and script; the A/A spread and n are printed beside the delta; a delta not exceeding the spread is recorded as noise; expected false survivors N * p^k are computed from the measured idle churn p, never assumed; k >= 5 alternations.

H2 (verify by writing), four channels of equal standing, each a record `{address or (source,key,offset), value written, value read back, predicted effect, observed effect, evidence}`:
1. Display: the game's own HUD/screen changes (screenshot).
2. Consequence-poke: poke A, predict and observe a change in an already-verified B through the snapshot ring, n >= 2.
3. Built-in debug screens as read-back (MONO_DEBUG_*, FSM_DEBUGGER, DAMAGE_DEBUG_*), once week-2 item 007 shows they render.
4. File round-trip: the game writes VCST/WEPN/VCFC through 0x4b0900-0x4b0cc0; a poked value that lands in the saved file is verified.
Plus in-situ hook-replay agreement (gate D tier 1) for function-level claims. Watch-only evidence caps at `supported`.

H3 (read back after every write). A write without a readback field is discarded; a mismatch is logged as a finding (silent write failure), and the trial aborts.

H4 (read the null). Every scan emits its funnel (candidates -> after each predicate -> survivors) and the instrument settings; an empty result is filed with the funnel and the reviewer states what the null already rules out before any hypothesis. Per-state canaries in the manifest: driving -> frame counter 0x5a7e1c and the rand log advanced; paused -> PeekMessageA pump count from the hook DLL or the profiler timeGetTime stamp advanced. A dead canary voids the capture.

H5 (suspect the instrument). Any measured constant that is a small ratio or power of two (5/6, 4/3, 3/4, 3/2, 640/480, 1680/1050, 3360/2100, 2^n) is cross-checked against instrument scale factors (dgVoodoo 3360x2100 vs 1680x1050, FPSLimit, snapshot cadence vs tick, x87 80-bit vs 32-bit, Ghidra float10 rendering, the parser's own scaling per gate R) before it is recorded as a property of the game; the evidence row carries `instrument-checked: yes`.

H6 (invariant frame + intersection). Heap and pool claims are `(source, key, offset)`, never absolute addresses; static-root chains and field labels need >= 2 independent instances (two vehicles, two runs, or static vs dynamic); the four duplicate function pairs (0x48a870/0x48c320, 0x487480/0x488e40, 0x489be0/0x48b690, 0x486860/0x488220) are free second instances and carry a `duplicate-of` column; ported names count as one instance and never alone.

H7 (precise blocker). Every open request, parked row and stalled subsystem carries one falsifiable sentence naming the blocker; the reviewer appends its complement as the next task. `requests\measurements.yaml` lists the plan's own dependent unknowns from day 1: Frida 64->32 attach on this host; TTD recording under dgVoodoo; Unicorn on x87 leaves; nitro<->i76 VT rate; idle churn p; whether MONO_DEBUG/FSM_DEBUGGER render; whether vehicle objects come from a heap or a pool; whether the built-in render path runs on Win10; vsOlder_x86 FID hit rate on Z*.DLL; whether Replay/NETWORK_POSLOG records; DynamoRIO injection on 19045. Each has an owner, earliest task, and the decision it flips.

H8 (raw retention). A capture is accepted only with `raw\` present and a manifest (condition, build stamp, instrument, time, canary state, file-open log). Disk budget per sitting: 20 GB; snapshot rings stored as xz deltas against frame 0 (BSS is zero-heavy; .data at 20 Hz is 34.7 MB/s raw); TTD windows capped at 60 s; compression recorded in the manifest. Re-mining an old capture is a first-class task.

H9 (crash channel). A reproducible crash becomes a capture (fault EIP as image offset, module list, registers, stack, last 64 hook entries, .data ring) and a queue item for the function at that offset. Seeded entries: Gold 12->13 at 0x467470 (shell map); privileged-instruction CPU measurement (disabled by i76fix); hardware-sound freeze; 3D-init crash; > 2 GB RAM detection; registry handle leak; ramming-restores-health overflow (Peelar); UCyborg's out-of-bounds writes and heap-handle overwrite (AiO patch). i76fix/AiO offsets are the first evidence on each.

H10 (session rules). A sitting is driven by a script started in the console session (Task Scheduler "run only when user is logged on", or a local runbook) and monitored over OpenSSH, never RDP; Frida attaches, never spawns, when driven remotely; the harness refuses to start a capture while the console session is disconnected or the game's SessionId differs from the console session.

---

## 5. Metrics and honest reporting

All computed from files by `tools\completeness.py` on every commit; `status\progress.json` is the timeline and `progress.svg` the board.

Functions (denominator 765,525 .text bytes; 2,165 rows): bytes and counts per status `{auto, proposed, supported, verified, anchored, library, synthetic, stub(reason), dead(proof)}`; the partition check: every byte in exactly one of function / library / synthetic / data-in-text (131 switch tables, padding) / dead-with-proof; untagged bytes (baseline 25,763 in 75 gaps).

Data (denominators: 22,408 .rdata; 260,096 initialised .data; 1,476,344 BSS; 7,277 referenced addresses): typed bytes per region; unowned referenced addresses; BSS status counts; unbounded array rows (their bytes count as remainder).

Heap and pool universe: keys observed in the corpus vs keys with full field tables, per source.

Labels: verified labels per H2 channel; tweak-manifest rows; cheat-flag hits.

Quality: G4 disagreement rate and agreement-when-both-wrong; G3 revert rate; G6 anchored-half accuracy and string-less contradiction rate; WARNING and undefined counts across the corpus; residual `FUN_/DAT_/param_/local_` identifiers.

Throughput and cost: proposals/hour, acceptance rate per drafter view, tokens per accepted function, per-function and weekly budget consumption (gate Q), human bytes/day on x87 functions (M14), launches per confirmed field (sentinel campaigns), oldest lease age.

Dynamic: open requests, captures collected, disk used, canary failures, H0 refusals.

Process-wide: the same remainder counts per in-scope module and summed.

Done means the remainder counts are zero for the exe, then for the shell; not that it feels done.

---

## 6. Repository, map layout and agent loop

```
C:\Users\james\i76-map\
  README.md                 conventions, gates, rebuild instructions
  recon-2026-09-04\         verbatim copy of <SCR>\recon and <SCR>\design + md5 manifest (Task 0)
  binaries\                 one TOML per module: md5, sections, byte totals, scope, status
    i76-gog2017.toml        reference; live patched copies listed as non-ground-truth
    sandbox.toml            every DLL in the sandbox with md5
  symbols\
    functions.tsv           addr size name status conv conv_evidence hookable duplicate_of tu subsystem evidence_ids
    globals.tsv             addr class width type name status readers writers bound_evidence evidence_ids
    heaptypes.tsv           source key(heap|pool,size,retaddr) struct owner lifetime instances
    strings.tsv imports.tsv tables.tsv regions.tsv modules.tsv
  types\
    i76.h                   the one header Ghidra parses; every field cites width-from / bit-tested-at
    dx5.h anet.h            boundary types from SDK headers and anet-0.10 source
  functions\<addr>.md       claim, evidence, prototype, contract, blockers, gate results
  subsystems\<name>.md      contract paragraph first, then members
  evidence\E*.json          {kind, addr, data, source, capture_id, instrument-checked, n, spread, p}
  captures\<id>\            manifest.json raw\ derived\   (append-only)
  requests\                 dynamic-N.yaml (checked by gate S), measurements.yaml (H7)
  ghidra\
    proj\  scripts\ (ExportBaseline, EnableParamID, CreateFuncsFromDataPtrs, ApplyMap, DumpAll)
    export\  export-frozen\  callgraph.json
  tools\                    gen_tables.py which_build.py launcher completeness.py strides.py
                            tu_boundaries.py eh_decode.py i76fmt i76poke census.js ledger.js ...
  status\                   progress.json progress.svg queue.json truthset.json completeness.md blockers.md
  agents\                   drafter-c.md drafter-pcode.md reviewer.md (file-based; no Ghidra access)
```

Agent loop (from `<AH>` section 4.2 with this revision's changes): lease from `queue.json` (leaves-first, then callers of accepted rows, >300-line functions last, truth-set functions and their callers never leased); read bounded context (own .c or .pcode, <= 5 callers/callees, strings, imports, existing .md, capture summaries); write `functions\<addr>.proposal.md` with one evidence pointer per claim and `hypothesis:` lines for the rest; reviewer subagent sees only the proposal and the same files; merge script (single writer) applies gates A, C, T, L, K, N, B, G0-G4, Q and appends; ApplyMap + DumpAll on a schedule (every K merges or 10 min; ~2 min); G3/G7 re-check; lease release; progress update. Six drafters (three per view) and two reviewers to start; agents never launch the game.

Merge command (one writer):
```
"C:\Users\james\Downloads\ghidra_11.4.1_PUBLIC_20250731\ghidra_11.4.1_PUBLIC\support\analyzeHeadless.bat" ^
  C:\Users\james\i76-map\ghidra\proj i76map -process i76_ref.exe -noanalysis ^
  -postScript ApplyMap.py -postScript DumpAll.py -scriptPath C:\Users\james\i76-map\ghidra\scripts
```

---

## 7. The first ten tasks

Task 0 (day 1): archive the evidence base, then `git init`.
```
robocopy "<SCR>\recon" C:\Users\james\i76-map\recon-2026-09-04\recon /E
robocopy "<SCR>\design" C:\Users\james\i76-map\recon-2026-09-04\design /E
python tools\manifest.py recon-2026-09-04 > recon-2026-09-04\MANIFEST.md5
git init && git add -A && git commit -m "recon archive 2026-09-04"
```
Output: the 71 MB Ghidra project, 43 MB export, 139 MB extracted ZFS, `bwd2-refute\tables.txt`, `zfs-lzo-refute\emu_game_decoder.py` and every refute script inside the repo with md5s.

Task 1 (days 1-3): build identity and the smoke test. Write `binaries\i76-gog2017.toml` and `sandbox.toml` (md5 every module; list the live patched i76.exe 4fabc303... and i76shell.dll as non-ground-truth); write `tools\which_build.py` and the launcher with the live .text/.rdata diff and the refusal path. Console (day 2-3, 30 min): launch the pristine exe in the sandbox with the exact wrapper set, drive 60 s, screenshot, attach a Frida script hooking only GetTickCount at IAT 0x4bc100, record the H0 stamp -> `captures\000-live-check\`, `captures\001-smoke\`. Test: the launcher refuses the playable install's exe; H7 blocker sentence if the pristine image does not run under the wrapper set.

Task 2 (days 1-2): port `ExportBaseline.java`, `EnableParamID.java`, `CreateFuncsFromDataPtrs.java`, `DumpAll.py`; run the pass-4 build; compute hookability per function (size >= 8 B, no branch target in the first 5 B, not funclet/thunk/EH stub, relocatable first instructions) into functions.tsv; rebuild twice from clean and diff the structural inventory (G7). Output: `ghidra\export\` (2,165 .c/.pcode), `export-frozen\`, `callgraph.json`, hookability column, reproducibility proof or the list of analyzers to pin.

Task 3 (day 3): `tools\gen_tables.py` producing strings.tsv (2,449), imports.tsv (244 with call/load site counts per gate C), tables.tsv (pointer-run scan of .data/.rdata plus the six BWD2 tables, six key tables, 0x4f9538, 0x4c2994, the 27 shell slots, the 18 renderer slots, FFB slots, display-mode table), regions.tsv (.text partition seed), and `--verify` with the gate A negative set. Output: five TSVs; `--verify` green on 0x4c2e8c/0x4f3af0/0x4edd58/0x5a7e1c/0x4bc100/0x608bb8.

Task 4 (days 3-4): apply the zero-inference anchors under gates G1/L/N/T: 20 import thunks; Smacker ordinals; entry/WinMain 0x402b30; 42 funclets and 24 EH stubs as `synthetic`; the LZO object per function; the 70 BWD2 handlers with (table, tag) pairs; the 27 shell callbacks `shell_cb_NN`; the renderer/FFB/shell loaders; self-naming strings under the G1 grammar; heap-tag namespaces on the 26 creators. Output: ~300-400 anchored/library/synthetic rows; ApplyMap proven; re-export; G3 report.

Task 5 (day 4): evidence-supply histogram. Per function count the statically available kinds (strings, imports, table membership, unique constants, EH frame, TU neighbourhood, pure-leaf emulability). Publish `status\evidence_supply.json` and set the Phase 1 exit from it. Also the constant-anchor pass over `.pcode` (0xbfc, 0x1a5e0, 54000, 0xe14, 0x10c, 0x2e47454f 'OEG.', 0x32445742 'BWD2', 2029, 109, 0xaab) with the uniqueness rule; 0x6cd is recorded with its 7 sites (0x46039f, 0x4718ba-0x471de4) and not assigned to the mesh cache.

Task 5b (week 2, time-boxed 5 days, needs open decision 2): extract nitro.exe from the GOG installer in Downloads into a second sandbox; md5 (i76fix targets 28b8ae276e88f4ffb13f17df159f09dc); pass-4 import; Version Tracking (exact bytes, instructions, mnemonics, then reference correlators, then BSim) with a stated acceptance score and no implied propagation; Roanish's ~130 items enter as `proposed` with scores. Output: `status\vt-nitro.json`.

Task 6 (day 4): environment. `pip install frida frida-tools`; confirm 64-bit Python attaches to a throwaway 32-bit process (notepad over RDP is fine for this); install PyGhidra from the shipped wheels; confirm Unicorn 2.1.4; check `cl.exe` from VS2019 with `/arch:IA32 /fp:precise`. Output: environment notes or H7 sentences in `measurements.yaml`.

Task 7 (day 5): select and seal the truth set (30 anchored, 30 string-less fact tuples) against `export-frozen\`; exclude them and their direct callers from ApplyMap; write the blind-eval script; run an unprimed drafter for the floor.

Task 8 (days 5-6): write `agents\*.md` (drafter-c, drafter-pcode, reviewer), `queue.json` with leases, gate scripts as executables (A, C, T, L, K, N, B, G0-G7, Q, S, P, R, E, H0-H10 checks); `tools\i76fmt` round-trip over the full corpus (gate R) and the stored-mode ZFS repack; one dry-run merge end to end. Output: `roundtrip.json` (expected 0 diffs), one merged commit.

Task 9 (days 7-8): run the loop on the leaves at 6 drafters / 2 reviewers with gate Q live; seed `types\i76.h` with the cited loader structs (ZFS header/entry, BWD2 descriptor, VFS source 0x10c, VFS entry 0x30, display-mode record, FFB descriptor 0x4f2328 size 0x16c, renderer slot table) and `dx5.h` after the three-site slot check; `tools\tu_boundaries.py` and `tools\eh_decode.py` first runs. Output: first 200-400 merged rows; acceptance, revert and token figures.

Task 10 (days 8-10, one console sitting of ~3 h under H10): `requests\dynamic-1.yaml`, pre-checked by gate S, in this order:
- 002 paused snapshot: ReadProcessMemory of 0x4c2000-0x669ef8 while PAUSE_GAME is held, stamped, canary = pump count (gate E input).
- 003 null spread: cockpit idle, engine on, 30 s, 3 A/A pairs -> p for .data, per heap, per pool.
- 004 census: `census.js` from functions.tsv hookable rows, CModule counters, first 200 hooks then all hookable; rate classes; never-seen list.
- 005 ledger: `ledger.js` on HeapCreate/HeapAlloc/HeapReAlloc/HeapFree, malloc/free, operator new/delete, and the pool functions 0x498940/0x499ce0 (+ carve functions if identified by then), keyed (source, key, size, return address, tick).
- 006 sentinel: armour = 695 (and 697 adjacent) in a loose `ADDON\vppt01.vcf`; null scan on a no-variant run first (0 hits required); n = 2 variant runs, spread 0 in the invariant frame; poke while paused; cockpit armour lamp; read back; file-open log decides whether the loose file was read (else stored-mode repack).
- 007 debug keys: bind MONO_DEBUG_TOGGLE, FSM_DEBUGGER, DAMAGE_DEBUG_*, TOGGLE_FRAMERATE in the sandbox keyboard.map; screenshot each.
- 008 renderer: one GetProcAddress return hook confirming stores into 0x608ba4-0x608be4 and the FFB slots; one census pass on the built-in path (no -glide switch).
Output: captures 002-008 with manifests, `null-spread.json`, `census\classes.csv`, `ledger\types.csv`, `semantics\labels.csv` with the first verified label, `debug-keys.md` verdict, `measurements.yaml` updated.

Days 11-14: continue the grind; first blind eval; Phase 0 report with every metric in section 5 as a number; go/no-go on the Phase 1 exit value.

---

## 8. Folding in older work (later, safely)

The user's own docs (`i76-everywhere\docs`, `i76-uncap-lab\docs`, AGENTS.md), the FFB tools in `tools\ffb\`, Roanish's REVERSING.md, That Tony's posts, Peelar's blog, i76fix, UCyborg's AiO, VOGONS threads, and the Sketchfab model collection are folded in from Phase 2 onward, one claim at a time, exactly as any external instance:
1. Each claim becomes an `evidence\E*.json` of kind `ported` with `source_instance`, the source's build identity (Nitro, CD-era, unversioned, or this md5), and the original text quoted as data (G0).
2. It enters `functions.tsv`/`globals.tsv` as `proposed`, never higher, and counts as one instance under H6.
3. It reaches `supported` only with an independent GOG-side anchor (gate P); addresses are re-derived from strings/constants, never trusted (That Tony's three addresses are mid-instruction here; Peelar's 0x49C310 is not the GOG rsqrt at 0x495000; Roanish's 0x6cd cluster does not land where his map says).
4. Contradictions between a ported claim and the map are logged as findings, not resolved by seniority; the gate P time box and stop rule apply to each source.
5. The user's earlier dynamic captures, if raw files survive, are re-mined under H8 with a manifest reconstructed from whatever build stamp can be recovered; captures with no recoverable build identity are tagged `build-unknown` and used only to generate requests.

---

## 9. Open decisions only the user can make

1. Visual C++ 5.0 SP3: acquire (archive.org items listed in fingerprint-toolchain section 2.7; legality is the user's call) or not. With it: LZO 1.00 compiled and byte-diffed against 0x4ba980-0x4baed5 to pin flags, Homeworld/anet calibration, reccmp as a ratchet. Without it: gate D uses VS2019 `/arch:IA32` with measured tolerances; no byte-level ratchet.
2. Permission to extract nitro.exe from the GOG Nitro Pack installer in Downloads into a second sandbox for Task 5b.
3. Console cadence: how many sittings per fortnight (the plan assumes one 3 h sitting per fortnight in Phases 1-2, two in Phase 3) and whether Task Scheduler runbooks may be installed on the console machine (H10).
4. Token budget: the weekly cap for gate Q and the acceptable plateau (the plan halts drafting below 5 accepted rows/day).
5. Scope order after the exe: shell first (garage, lobby, save, difficulty, the 12->13 crash) or the renderer DLLs first (needed for a replacement renderer). The plan assumes shell first.
6. Whether the two-day symbol-leak hunt may contact people (Peelar for the unreleased Gold HAL beta and the netcode .udd files; Ken Miller for Battlezone) or is confined to public archives.
7. Whether the playable install may ever be launched with the hook DLL for a demo of the tweak layer, or the sandbox remains the only runnable copy for the life of the project (the plan assumes sandbox only).

---

## 10. Effort curve and comparables

Comparables (prior-art sections 2-3): solo functional decompilation of a 1 MB C game 1-3 years (Pinball, Fallout 1/2, TFE); LEGO Island ~1,500 team-hours with a comparer; Tomb1Main injected DLL to own exe in under a year; OpenLoco 7.5 years to zero globals; SW_RACER_RE (VC++ 5, 2,132 functions, no symbols) 71.2% after 8 years; LLM grinds fast to 60-75% then plateau on math-heavy code, with no x86/MSVC data point.

This target's specific difficulty: 717 x87 functions holding 462,513 B (64% of function bytes); 1,762 functions (476,220 B) reference no string; 103 string-less functions >= 1 KB hold 170,326 B. Agents will compress the anchored, table-driven and leaf part; the x87 core is human-led with agents on the mechanical parts.

Projection, to be replaced by measurement at the end of Phase 3's first fortnight (M14):
- Weeks 1-2: Phase 0; ~350 rows anchored/library/synthetic; first verified label.
- Weeks 2-8: Phase 1; 30% of .text bytes at supported+ (provisional).
- Weeks 5-12: Phase 2; top-200 globals typed; heap/pool universe typed for the corpus; ~100 verified labels; determinism report.
- Weeks 10-30: Phase 3; subsystems closed in anchor-first order; the physics/AI core is the slow stretch and is where the calendar is re-projected.
- Week 28 onward: Phase 4; exe remainder to zero is realistically 12-18 months from start at 15-20 h/week plus agents; the shell adds 3-6 months after that.
- Phase 5 runs from week 10 in parallel; "tweak anything" is literal for every verified row from the moment it is verified and universal when the audit reaches zero.

The finish driver is the remainder count, recomputed on every commit, and the stop rules (gates P and Q) that keep the preamble from becoming the project.

---

## Appendix A. Addresses and facts cited (verified against the pass-4 export or the refute reports this revision)

- Sim clock: 0x49c7f0 init (caller 0x403247), 0x49c920 per-frame (callers 0x403526, 0x4039b8, 0x452eea); dt 0x4fe428, clamp constants 0x4be9ac (0.001f) / 0x4be9b0 (0.2f); frame counter 0x5a7e1c; game time 0x5a7e74; getters 0x49c8b0 (38 callers), 0x49c8c0 (59), 0x49c7d0 (6), 0x49c7e0 (7). Other GetTickCount users: 0x41b270 (value discarded), 0x423400 (5 s / 60 s rearm), 0x423620 (10 s CB expiry), 0x42f6b0 (166/333 ms debounce), 0x479a90 (palette-fade busy-wait at 0x479bf2). Source: refute-timer-claim sections 3, 6; ttd-refute section 4.
- Renderer plugin: loader 0x426900 (LoadLibraryA 0x426912, GetProcAddress 0x426922); companion 0x426b40; command-line parser 0x49d1d0; name buffer 0x5dd340; flag 0x504be8; built-in init 0x42d0c0 under `-hal`; slot table 0x608ba4-0x608be4 with 0x608bb8 never written; 18 names at file 0xEC958-0xECA54; all call sites caller-cleanup (cdecl). Source: refute-renderer-plugin sections B-F.
- Shell: 0x4022e0 builds 27 callback slots then `GetProcAddress(DAT_005dd2f8, "ShellMain" @0x4c228c)`; ShellWindowProc pointer to 0x504bec. Source: `<AH>\export\functions\004022e0.c`; refute-nitro-map section B.
- FFB: 0x446020/0x446050 loads I7_SFRCE.DLL; pointers 0x52bbdc/e0/e4; descriptor 0x4f2328 (0x16c B).
- FSM: 0x412ce0 action dispatcher (96-case table 0x4144e4; default pushes `Uknown fsm prototype - %s` @0x4c33e8); 0x414670 opcode switch (14-case table 0x4149b8; default pushes `Unknown fsm assembler instuction` @0x4c3404); 0x410a10 match_prototype (6,327 B, 149 string refs). Source: fsm-addr-refute.
- BWD2: walker 0x4b3db0; def loader 0x4b41e0 (25 callers); mission loaders 0x4b423f/0x4b44c8/0x4b4aef; header table 0x500328; REV handler 0x4b4610; ext table 0x5003b8; xREV table 0x500438; body tables 0x4fef00-0x500e00 (153 rows, 115 non-null, 70 distinct handlers); EXIT handler 0x4b4290; writer 0x4b4840; save writers 0x4b0900-0x4b0cc0; logger stub 0x42d5d0. Source: bwd2-refute.
- ZFS/LZO: 0x4b9800, 0x4b9bd0, 0x4b9fc0 (cdecl/5), 0x4ba980, 0x4baa00 (LZO1Y), 0x4babd8 (LZO1X), 0x4badb0; banner at 0x4bfd80-0x4bfe49; error string 0x500f54. Source: zfs-lzo-refute sections 2-3.
- VFS: 0x4b28c0 with strides 0x10c (0x4b2923/0x4b2929) and 0x30; ZFS block 0xe14 at 0x4b96e6/0x4b997b/0x4b9a03. Source: refute-nitro-map section B.
- Pools: 0x498940(size, reserve) -> VirtualAlloc(NULL, round64K, MEM_RESERVE|MEM_TOP_DOWN, PAGE_READWRITE) then commit; descriptor via 0x499ce0(0x10) linked at 0x5a6170; WinMain: 0x5dd320 = pool(0x1a5e0, 0x40000); 0x5dd2ec = 0x5dd320 + 54000; 0x5dd324 = pool(0x80000, 0x80000); failure string `Unable Allocate Virtual Memory` @0x4c25c0; 0x498a00 releases 0x5dd320. Source: `<AH>\export\functions\00498940.c`, `00402b30.c`.
- rsqrt: 0x495000 with `0xbfc - (param_2 >> 0x14) >> 1` and LUT 0x655180. Source: `<AH>\export\functions\00495000.c`; Peelar's 0x49C310/0x5FB180 are another build.
- Hot globals: 0x6439d8 (487 refs, 23 fns), 0x59bc00/08/38/b0/50 float cluster (23 fns), 0x4faf18 read-only table (58 fns in pass 4), 0x5dd320 (117 refs, 24 fns), 0x5dcec0 (30 fns). Source: `<FP>` section 8.
- Crash: 0x467470 dereferences `[EAX+0x3BC]+0x70` (VOGONS t=25721).
- Live patched exe: md5 4fabc30303c7a327fbe15be58cb868c5, .text vsize 765,657, imports u32x.dll + WINMM.dll, string I76PATCH.DLL. Source: pe-fingerprint.
- i76fix: hooks 0x4039B8, uses IAT 0x4bc100 (https://github.com/immi101/i76fix).
- Sources: https://github.com/Roanish/i76 (REVERSING.md), https://inbetweennames.net/blog/2021-05-06-i76rsqrt/, https://www.vogons.org/viewtopic.php?t=25721, https://kegel.com/anet/, https://github.com/ptitSeb/ctp2 (anet2.map), https://raw.githubusercontent.com/nemequ/lzo/master/src/lzo1x_d.ch, https://blog.chrislewis.au/the-long-tail-of-llm-assisted-decompilation/, https://quesma.com/blog/ghidra-mcp-unlimited-lives/.