# binaries

One TOML per module: md5, sections, byte totals, scope, status (method doc section 2). Task 1 writes
`i76-gog2017.toml` (the reference, with the live patched i76.exe 4fabc303... and i76shell.dll listed as
non-ground-truth) and `sandbox.toml` (every DLL in the sandbox with md5).

Written by Task 1 (`tools\gen_binaries.py`; read back with tomllib and a fresh md5 per module):
`i76-gog2017.toml` (reference exe, sections, 244 imports, gate A negative set, 7 non-ground-truth copies,
the H0 allowlist) and `sandbox.toml` (52 PE modules of `C:\Users\james\i76-uncap-lab\game`, 32
original-era / 20 modern, `in_scope` flags). `tools\completeness.py` reads the `in_scope` rows for the
process-wide remainder.

`diff-9a232dcc-vs-<md5>.tsv` (p2-poke-snapshot-h0, `python tools\which_build.py --gen-diffs`): per-section
differing runs (gap 8) and clusters (gap 64) of each known patched build against the pristine file -
`58d9dec0` (pristine+i76fix-p1: 1 run, 5 B at 0x499b25), `60abf7bc` (aio 2019: 45 .text clusters, 2,459 B, +132-B
tail), `4fabc303` (sandbox: aio + pools 0x402f9b-0x402fd4 + far clip 0x4059de + camera rate 0x4bc528 + u32x
import rename), `6319abf7` (portable: aio + u32x rename). `which_build.py --classify <va,...>` reads them to tag an
address `build-shifted` (inside a cluster) or `transfers`; `tools\merge.py` unions the 60abf7bc clusters into
gate P's `PATCH_CLUSTERS`.
