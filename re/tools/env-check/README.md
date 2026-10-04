# tools/env-check (Task 6, t6-environment)

Reproducible environment probes; each writes a one-line JSON `.out` beside it.
- `frida_attach32.py`  64-bit Python + frida attach to a self-spawned SysWOW64 notepad, hook GetTickCount, detach, kill.
- `pyghidra_smoke.py [scratch_dir]`  pyghidra.start(), open the pristine exe in a scratch project (never `ghidra\proj`), print version/blocks.
- `unicorn_x86_32.py`  10 integer instructions + 6 x87 instructions against hand-computed results; exit 1 on mismatch.
- `cl-hello\build.cmd`  vcvarsall x86 + `cl /arch:IA32 /fp:precise /O2 /Oy /FAs`; `hello.asm` shows x87 codegen.
- `pe_inventory.py <root> [--show REGEX]`  md5 / PE timestamp / linker / Rich / CRT for every exe+dll under root -> `<root>\PE-INVENTORY.tsv`.
