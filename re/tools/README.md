# tools

`manifest.py` (Task 0): md5 + size + path for every file under a root; `--check` re-verifies;
`--large N` emits the .gitignore block.

Added by later Phase 0 tasks (owner in brackets; details in `status\tasks\<label>.md`):

| file | what |
|---|---|
| `pe_ident.py`, `gen_binaries.py` (t1) | PE identity reader; generates `binaries\*.toml` and re-hashes every module on read-back |
| `which_build.py`, `allowlist.json`, `launch.ps1`, `tests\` (t1) | H0 stamp of a live/offline image; the one allowlisted patch (0x499b25); the H0/RDP-gated launcher; fake-target tests |
| `hookability.py`, `struct_diff.py` (t2) | hookability funnel -> `symbols\functions.tsv`/`hookability.tsv`/`duplicates.tsv`; G7 structural diff of two exports |
| `gen_tables.py` (t3) | strings/imports/tables/regions TSVs; `--verify` = gate A negative set + gate C ratios |
| `merge.py`, `anchors_t4.py`, `g3_check.py` (t4, t8) | the single writer of functions.tsv/globals.tsv/evidence; the Task 4 anchor batch builder; G3/G7 check |
| `evidence_supply.py`, `tu_boundaries.py`, `eh_decode.py` (t5) | evidence-kind histogram -> `status\evidence_supply.json`; TU neighbourhoods -> `symbols\modules.tsv`; VC5 EH frames -> `types\cpp_island.md` |
| `t5b_roanish_parse.py`, `t5b_port.py`, `t5b_globals.py` (t5b) | Roanish item parser; VT + signature join -> `symbols\ported.tsv`; operand-alignment global port |
| `env-check\` (t6) | frida/pyghidra/unicorn/cl smoke scripts with their `.out` records |
| `truthset_select.py`, `emulate_leaf.py`, `blind_eval.py` (t7) | truth-set sealer; Unicorn gate E harness; blind render/score/reveal |
| `proposal.py`, `lease.py`, `disasm.py`, `build_queue.py`, `gates\`, `i76fmt\` (t8) | proposal/review file contract; queue leases; capstone view; queue builder; 13 gate executables; format parsers + round trip |
| `VC5-SETUP.md`, `vc5_verify.py`, `lzo_calibrate.py` (t9a) | where VS97 SP3 / VC4.2 are; toolchain identity check; LZO object-vs-exe calibration |
| `completeness.py` (t11) | section 5 metrics -> `status\progress.json` (timeline) + `status\progress.svg` |
| `frida_gettick.py` (t11) | Task 1 smoke: attach to the game, hook kernel32!GetTickCount, count calls whose return address is in .text (self-tested on SysWOW64 notepad) |
| `snapshot.py` (t11) | one-shot ReadProcessMemory of 0x4c2000-0x669ef8 + canaries -> `captures\<id>\raw\snapshot.bin` (Task 10 item 002) |
| `merge.py` `ported` batch section, `gates\gateP_ported.py`, `gates\capture_gates.py` (p5-foldin-merge) | gate P fast path `ported-static` (quoted bytes vs the pristine file; aio patch clusters -> `build-shifted`), G-ENC / G-BUILD-TAG in the merge, gate C `hwbp-trap-after`, gate A negative-set additions (also in `gen_tables.py --verify`); manifest validators G-STIM / G-UNITS / G-TORN / G-NORESTORE / G-ATTEST / G-CONF / G-POS (`--selftest`, `--all`); the ledger converter is `foldin\ledger\make_batch.py` |

| `census.js`, `ledger.js`, `frida_run.py`, `census_classify.py`, `ledger_types.py`, `ledger_mark.py` (p1-census-ledger) | Task 10 items 004/005: CModule per-function call counters and the 36-B allocation-record ring (HeapCreate/Alloc/ReAlloc/Free/Destroy, msvcrt, pool_Reserve/pool_Free, the 0x499ce0 wrapper, watermarks 0x6442ec/0x654380); the driver (H0 stamp first, attach never spawn, G-ATTEST blocks); rate classes -> `census\classes.csv`; types keyed (source, key, size, retaddr) -> `ledger\types.csv`; self-destruct markers |
| `i76poke.py`, `pump_counter.js`, `tests\fake_sim.py`, `tests\test_p2_instruments.py` (p2-poke-snapshot-h0) | write + three-horizon read-back (H0 gate, H3 classes sticks / clobbered-per-frame / clobbered-on-event / did-not-land, root chains as (source, key, offset)); PeekMessageA pump counter (paused canary); fake ticking target; 49 checks. `snapshot.py` 0.2: series mode, `--heaps --read-heaps`, `--pump`, `--pos-control`, xz deltas under the 20 GB budget; `which_build.py` 0.2: G-CONF, G-ATTEST, per-build diff signatures (`binaries\diff-*.tsv`), `--classify`; `launch.ps1` 0.2: `-GameArgs @()` |
| `harness\` (p3-harness-pause) | the console harness re-pointed at the H0 build (`enter-*-pristine.ps1` through `launch.ps1`, `make-harness.py --check`), `stimuli.ps1` (G-STIM stimuli with proof of firing, `Invoke-DebugKey`, `Save-Screenshot`), item 007 `gamekey.map` proposal + `apply-gamekey-007.ps1` |
| `refresh_funcrows.py` (p4-ghidra-fixes) | copies size/conv/hookable from a scratch `hookability.py` run into selected functions.tsv rows; inserts `auto` rows for new functions. `g3_check.py`: G7 rule > 2 / baseline pair, `--addrs`, `--before` |
| `make_sentinel_vcf.py`, `sentinel_scan.py` (p6-finalize) | Task 10 item 006: the loose ADDON `.vcf` with sentinel armour dwords via `i76fmt.bwd2` (armour at body+93 = file 0x79; read-back, diff window, sidecar JSON; byte-identical to the prior `make-test-variant.py`); the null / variant scan over `raw\*.bin` with aligned-u32 hit addresses and the `[[[0x54a264]]+0x70]` chain resolved through the stored heap regions -> manifest `null_scan` / `variant_scan` |

Still planned: `strides.py` (gate B stride evidence), a CreateFileA/`fopen` file-open hook (item 006's loose-vs-ZFS log).
