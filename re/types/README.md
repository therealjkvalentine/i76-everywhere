# types

`i76.h`: the one header Ghidra parses; every field cites width-from / bit-tested-at (gate T). Uncited
fields stay `undefined` with the source noted. `dx5.h`, `anet.h`: boundary types from SDK headers and
anet-0.10 source. Seeded in Task 9.

p5-foldin-merge added the fold-in seeds to `i76.h`: `I7FF_SimState` (0x4f2328, 0x16c; every field cited to a store in
the writer 0x445ba0 / 0x445a60 / 0x446110), `I76_InputAction` (the 32-byte rows at 0x4f2860), `I76_AmmoSlot` (stride
0x4c at 0x5aab0c, +0x1c ammo), `I76_WorldCtx` (+0x70 player entity), `I76_EntityFlags` (+0x454 bits tested by the
FFB writer), `I76_Entity` v0 (+0xac..+0xe4, +0x108, +0x3a8..+0x45c) and `I76_Logic` (+0xa718/+0xa71c/+0xa738/+0xa818).
Field names follow the fold-in ledger (proposed semantics); widths and offsets are the pristine file's (gate T:
`python tools\gates\gateT_types.py` checks every member line). Uncited fields are `undefined_<off>` pads.

`i76_runtime.h` (2026-09-27): the consolidated runtime-structure header for a port, not for Ghidra, because it needs a
preprocessor. It has 42 structs and a globals section, and every field cites an instruction site or a spec. There are
126 compile-time offset and size checks, and it compiles clean with MSVC x86 `/W4` and x64 `/Zs`. It folds in the v0
`i76.h`, the `subsystems/*.md` field tables and the wave 1-5 draft field lists. Disagreements and a 15-claim
disassembly sample (14 confirmed, 1 qualified) are in `i76_runtime-conflicts.md`.
- **v0 errors it records:** `I76_WorldCtx +0x70` is misframed (0x44f1dd goes through `[world_GetRoot()]`).
  `I76_AmmoSlot` is framed 4 bytes late: the weapon-instance table starts at 0x5aab08, ammo at +0x20. The trainer's
  0x5aab0c + 0x1c is the same address.
