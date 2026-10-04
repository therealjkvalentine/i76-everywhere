r"""shell_menu_items.py - join the shell's menu item labels to their handlers, statically (2026-09-26).

    python tools\shell_menu_items.py [--out foldin\shell-menu-items.tsv]

shell_InitMenuStrings 0x497b20 looks each label up (StrLookup, push <literal>) and stores the result at
record+4 of a 0x3c-byte menu item record (mov dword ptr [rec+4], eax); the item's handler is the code pointer at
record+8 and its string/command id at record+0xc (the Play Options page 'plyopt1.map' lists items 0x4fc4d8 x9).
Method: capstone over the pristine file (md5 9a232dcc); every row carries the store site and literal address.
"""
import csv, os, re, struct, subprocess, sys
import pefile
M = r"C:\Users\james\i76-map"
EXE = r"C:\Users\james\i76-uncap-lab\game\i76.exe.2017galaxy"
pe = pefile.PE(EXE)
rd = lambda va, n: pe.__data__[pe.get_offset_from_rva(va - 0x400000):pe.get_offset_from_rva(va - 0x400000) + n]
fn = {int(r["addr"], 16): r for r in csv.DictReader((l for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t")}
out = subprocess.run([sys.executable, os.path.join(M, "tools", "disasm.py"), "0x497b20"], capture_output=True, text=True, cwd=M).stdout.splitlines()
rows, lit = [], None
for l in out:
    m = re.search(r"^(0x[0-9a-f]+)\s+push\s+0x([0-9a-f]+)\s+; init:0x[0-9a-f]+ string='(.*)'$", l)
    if m:
        lit = (m.group(1), "0x" + m.group(2), m.group(3)); continue
    m = re.search(r"^(0x[0-9a-f]+)\s+mov\s+dword ptr \[0x([0-9a-f]+)\], eax", l)
    if m and lit:
        rec = int(m.group(2), 16) - 4
        raw = rd(rec + 8, 8) if rec + 8 < 0x541000 else b""   # .bss records have no file bytes
        h, sid = struct.unpack("<II", raw) if len(raw) == 8 else (0, 0)
        rows.append({"label": lit[2], "record": "0x%x" % rec, "handler": ("0x%x" % h) if 0x401000 <= h < 0x4bc000 else "",
                     "handler_name": fn.get(h, {}).get("name", "") if h else "", "status": fn.get(h, {}).get("status", ""),
                     "id": "0x%x" % sid, "store_site": m.group(1), "literal_addr": lit[1], "push_site": lit[0]})
        lit = None
dst = os.path.join(M, sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else r"foldin\shell-menu-items.tsv")
with open(dst, "w", encoding="utf-8", newline="") as fh:
    fh.write("# shell-menu-items.tsv - shell_InitMenuStrings 0x497b20 label -> item record (label at +4, handler at +8, id at +0xc); tools/shell_menu_items.py, capstone over md5 9a232dcc\n")
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t"); w.writeheader(); w.writerows(rows)
print("%d labels, %d with a code handler -> %s" % (len(rows), sum(1 for r in rows if r["handler"]), dst))
for r in rows:
    print("%-24s %-10s %-8s %-36s %s" % (r["label"][:24], r["handler"], r["id"], r["handler_name"], r["status"]))
