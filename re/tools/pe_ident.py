#!/usr/bin/env python3
r"""pe_ident.py - identity of one PE module: hashes, headers, sections, imports per DLL.

Shared by gen_binaries.py (binaries\*.toml) and which_build.py (live stamp). Every field is read
from the file with pefile / hashlib; nothing is inferred. Import counts are import-descriptor
entries (method: pefile DIRECTORY_ENTRY_IMPORT), not call sites (gate C: call-site counts live in
symbols\imports.tsv, method capstone).

    python tools\pe_ident.py <file> [<file> ...]      print the JSON identity of each file
"""
import datetime
import hashlib
import json
import os
import sys

try:
    import pefile
except ImportError:  # pragma: no cover
    pefile = None

CHUNK = 1 << 20


def hashes(path):
    m = hashlib.md5()
    s = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            m.update(b)
            s.update(b)
    return m.hexdigest(), s.hexdigest()


def is_pe(path):
    try:
        with open(path, "rb") as f:
            head = f.read(0x40)
        if len(head) < 0x40 or head[:2] != b"MZ":
            return False
        e_lfanew = int.from_bytes(head[0x3C:0x40], "little")
        with open(path, "rb") as f:
            f.seek(e_lfanew)
            return f.read(4) == b"PE\0\0"
    except OSError:
        return False


def utc(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def identity(path, with_imports=True):
    """Return a dict describing the PE at path. Raises pefile.PEFormatError on a non-PE."""
    st = os.stat(path)
    md5, sha256 = hashes(path)
    d = {
        "file": os.path.basename(path),
        "path": os.path.abspath(path),
        "size": st.st_size,
        "md5": md5,
        "sha256": sha256,
        "mtime_utc": utc(st.st_mtime),
    }
    pe = pefile.PE(path, fast_load=True)
    try:
        pe.parse_data_directories(directories=[
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"],
        ])
        fh = pe.FILE_HEADER
        oh = pe.OPTIONAL_HEADER
        d.update({
            "machine": hex(fh.Machine),
            "is_dll": bool(fh.Characteristics & 0x2000),
            "characteristics": hex(fh.Characteristics),
            "pe_timestamp": fh.TimeDateStamp,
            "pe_timestamp_utc": utc(fh.TimeDateStamp),
            "linker": "%d.%02d" % (oh.MajorLinkerVersion, oh.MinorLinkerVersion),
            "subsystem": oh.Subsystem,
            "image_base": hex(oh.ImageBase),
            "entry_point_va": hex(oh.ImageBase + oh.AddressOfEntryPoint),
            "size_of_image": oh.SizeOfImage,
            "size_of_code": oh.SizeOfCode,
            "size_of_init_data": oh.SizeOfInitializedData,
            "size_of_uninit_data": oh.SizeOfUninitializedData,
            "relocs_stripped": bool(fh.Characteristics & 0x0001),
            "sections": [],
            "imports": {},
            "import_total": 0,
            "export_count": 0,
        })
        for s in pe.sections:
            name = s.Name.rstrip(b"\0").decode("latin-1")
            d["sections"].append({
                "name": name,
                "va": hex(oh.ImageBase + s.VirtualAddress),
                "rva": hex(s.VirtualAddress),
                "vsize": s.Misc_VirtualSize,
                "raw_ptr": hex(s.PointerToRawData),
                "raw_size": s.SizeOfRawData,
                "characteristics": hex(s.Characteristics),
                # VA - file offset for bytes inside the raw image (gate A section-delta)
                "file_delta": hex(oh.ImageBase + s.VirtualAddress - s.PointerToRawData),
            })
        if with_imports and hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
            for entry in pe.DIRECTORY_ENTRY_IMPORT:
                dll = entry.dll.decode("latin-1")
                n = len(entry.imports)
                d["imports"][dll] = d["imports"].get(dll, 0) + n
                d["import_total"] += n
        if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
            d["export_count"] = len(pe.DIRECTORY_ENTRY_EXPORT.symbols)
            d["export_name"] = (pe.DIRECTORY_ENTRY_EXPORT.name or b"").decode("latin-1")
    finally:
        pe.close()
    return d


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    out = []
    for p in argv:
        out.append(identity(p))
    json.dump(out if len(out) > 1 else out[0], sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
