r"""PE inventory: md5, size, machine, PE timestamp, linker version, Rich header, CRT import, for every
.exe/.dll under a root. Writes <root>\PE-INVENTORY.tsv (sorted) and prints rows whose path matches the
optional --show regex. Linker->compiler mapping is a heuristic (LINK 3.00=VC4.0, 3.10=VC4.1/4.2,
5.00=VC5.0, 5.10/5.12=VC5.0 SP3, 6.00=VC6, 7.x=VS2002/3, 8=VS2005, 9=VS2008, 14.x=VS2015+), noted as such."""
import argparse, datetime, hashlib, os, re, sys
import pefile

GEN = {(2, 5): "VC2.x", (2, 6): "VC2.x", (3, 0): "VC4.0", (3, 10): "VC4.1/4.2", (4, 20): "VC4.2b",
       (5, 0): "VC5.0", (5, 10): "VC5.0-SP3", (5, 12): "VC5.0-SP3", (6, 0): "VC6.0", (7, 0): "VS2002",
       (7, 10): "VS2003", (8, 0): "VS2005", (9, 0): "VS2008", (10, 0): "VS2010", (14, 0): "VS2015",
       (14, 29): "VS2019-16.11"}

def row(root, path):
    rel = os.path.relpath(path, root)
    data = open(path, "rb").read()
    md5 = hashlib.md5(data).hexdigest()
    try:
        pe = pefile.PE(data=data, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    except pefile.PEFormatError as e:
        return [rel, len(data), md5, "not-PE", "", "", "", "", "", "", ""]
    ts = pe.FILE_HEADER.TimeDateStamp
    tsi = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else "0"
    lk = (pe.OPTIONAL_HEADER.MajorLinkerVersion, pe.OPTIONAL_HEADER.MinorLinkerVersion)
    rich = ""
    try:
        rh = pe.parse_rich_header()
        if rh and rh.get("values"):
            v = rh["values"]; pairs = sorted({(v[i] >> 16, v[i] & 0xffff, v[i + 1]) for i in range(0, len(v), 2)})
            rich = "rich:" + ";".join("%d.%d x%d" % p for p in pairs[:6])
        else:
            rich = "no-rich"
    except Exception:
        rich = "no-rich"
    crt = []
    for imp in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        n = imp.dll.decode(errors="replace").upper()
        if re.match(r"MSVC|CRTDLL|MFC|UCRT|VCRUNTIME|API-MS-WIN-CRT", n): crt.append(n)
    return [rel, len(data), md5, hex(pe.FILE_HEADER.Machine), tsi, "%d.%d" % lk, GEN.get(lk, "?"),
            rich, ",".join(sorted(set(crt))) or "-", pe.FILE_HEADER.NumberOfSections,
            "DLL" if pe.is_dll() else "EXE"]

ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--show", default=".")
a = ap.parse_args()
rows = []
for dp, dn, fn in os.walk(a.root):
    for f in fn:
        if f.lower().endswith((".exe", ".dll")): rows.append(row(a.root, os.path.join(dp, f)))
rows.sort(key=lambda r: r[0].lower())
hdr = ["path", "size", "md5", "machine", "pe_timestamp_utc", "linker", "gen_heuristic", "rich", "crt_imports", "sections", "kind"]
out = os.path.join(a.root, "PE-INVENTORY.tsv")
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\t".join(hdr) + "\n")
    for r in rows: fh.write("\t".join(str(x) for x in r) + "\n")
print("# %d exe/dll rows -> %s" % (len(rows), out))
print("\t".join(hdr))
for r in rows:
    if re.search(a.show, r[0], re.I): print("\t".join(str(x) for x in r))
