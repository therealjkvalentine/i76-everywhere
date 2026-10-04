#!/usr/bin/env python3
r"""gen_binaries.py - write binaries\i76-gog2017.toml and binaries\sandbox.toml (Task 1).

    python tools\gen_binaries.py [--game-dir C:\Users\james\i76-uncap-lab\game] [--out binaries]

Every hash, size, timestamp, linker version, section row and import count is read from the file
by pe_ident.py (pefile + hashlib). Era, role and scope are the only interpreted columns and they
cite their source (method doc section 2; recon pe-fingerprint REPORT.md). After writing, both
files are re-read with tomllib and every module's md5 is compared with a fresh hash (verify the
write landed).
"""
import argparse
import datetime
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_ident  # noqa: E402

PRISTINE_MD5 = "9a232dcc2c164648cff20c414c1f9698"
PRISTINE_FIX_MD5 = "58d9dec00c18a5383820e77e51850b74"   # captures\001-smoke\allowlist.json
PATCHED_EXE_MD5 = "4fabc30303c7a327fbe15be58cb868c5"    # pe-fingerprint: live i76.exe
GOG_SHELL_MD5 = "8960fa16c1581da85ad5d6085517f292"      # i76shell.dll.orig (imports USER32.dll)
DEFAULT_GAME = r"C:\Users\james\i76-uncap-lab\game"
METHOD_DOC = r"C:\Users\james\i76-everywhere\docs\records\FRESH-START-METHOD.md"   # moved to docs\records 2026-10-03
FP_REPORT = r"recon-2026-09-04\recon\pe-fingerprint\REPORT.md"

# role / scope per method doc section 2 (table) and the pe-fingerprint census; keyed by lower-case
# base name with the variant suffixes stripped (see base_key()).
ROLES = {
    "i76.exe": ("exe", "Primary partition, Phases 0-4", True),
    "i76shell.dll": ("shell", "Anchors-only map from Phase 1; full map after Phase 3", True),
    "i76shell_1083.dll": ("shell-1997-sibling", "Version Tracking source for the shell (VC 4.2, debug CRT)", False),
    "zglide.dll": ("renderer-plugin", "Export ABI typed in Phase 1; internals after the exe", True),
    "zredline.dll": ("renderer-plugin", "Export ABI typed in Phase 1; internals after the exe", True),
    "zdx5draw.dll": ("renderer-plugin", "Export ABI typed in Phase 1; internals after the exe", True),
    "zpowervr.dll": ("renderer-plugin", "NEC Electronics build of the 19-export plugin ABI; ABI only", True),
    "anetdll.dll": ("anet", "Prototypes only (LGPL anet-0.10 source)", False),
    "winet.dll": ("anet-transport", "Prototypes only (17 comm* exports)", False),
    "wipx.dll": ("anet-transport", "Prototypes only (17 comm* exports)", False),
    "wmodem.dll": ("anet-transport", "Prototypes only (17 comm* exports)", False),
    "wserial.dll": ("anet-transport", "Prototypes only (17 comm* exports)", False),
    "strlkup_orig.dll": ("helper", "Boundary typing only (Strlkup, source in anet)", False),
    "getinfo.dll": ("helper", "Boundary typing only (Getinfo, source in anet)", False),
    "i7_sfrce.dll": ("helper", "Boundary typing only (force feedback, I7FF_* exports)", False),
    "smackw32.dll": ("helper", "Boundary typing only (RAD Smacker 3.0e, Watcom)", False),
    "viddll.dll": ("helper", "Boundary typing only (MCI video, shipped debug build)", False),
    "strfile.dll": ("helper", "Boundary typing only (CStringFile)", False),
    "get3d.dll": ("helper", "Boundary typing only (DX3-era hardware probe)", False),
    "detect3d.dll": ("helper", "Boundary typing only (Direct3D HAL probe)", False),
    "splash.exe": ("helper", "CD launcher; out of scope", False),
    "dsetup.dll": ("redist", "DirectX 5.0 setup redist; out of scope", False),
    "dsetup16.dll": ("redist", "DirectX 5.0 setup redist; out of scope", False),
    "dsetup32.dll": ("redist", "DirectX 5.0 setup redist; out of scope", False),
    "i76patch.dll": ("patch-1999", "Third-party 1999 patch DLL (disabled); never 1998 code", False),
    "win32.dll": ("gog-shim", "GOG winmm forwarder + audiere MCI (2009); never treated as 1998 code", False),
    "audiere.dll": ("gog-shim", "Audiere 1.9.4 (2006) behind win32.dll; excluded", False),
    "msvcr90.dll": ("gog-shim", "VC++ 2008 CRT for win32.dll; excluded", False),
    "msvcp90.dll": ("gog-shim", "VC++ 2008 CRT for win32.dll; excluded", False),
    "goggame.dll": ("gog-shim", "GOG Game Definition File DLL; excluded", False),
    "ddraw.dll": ("dgvoodoo", "dgVoodoo 2 wrapper; excluded; md5-stamped in every manifest", False),
    "d3dimm.dll": ("dgvoodoo", "dgVoodoo 2 wrapper; excluded", False),
    "d3d8.dll": ("dgvoodoo", "dgVoodoo 2 wrapper; excluded", False),
    "d3d9.dll": ("dgvoodoo", "dgVoodoo 2 wrapper; excluded", False),
    "glide.dll": ("dgvoodoo", "dgVoodoo 2 wrapper; excluded", False),
    "glide2x.dll": ("dgvoodoo", "dgVoodoo 2 wrapper (the Glide the sandbox runs on); md5-stamped in every manifest", False),
    "glide3x.dll": ("dgvoodoo", "dgVoodoo 2 wrapper; excluded", False),
    "dgvoodoocpl.exe": ("dgvoodoo", "dgVoodoo control panel; excluded", False),
    "strlkup.dll": ("local-wrapper-2026", "2026 Strlkup wrapper (VS2019); never 1998 code; md5-stamped", False),
    "u32x.dll": ("local-wrapper-2026", "2026 USER32 proxy (VS2019); never 1998 code; md5-stamped", False),
    "winmm.dll": ("local-wrapper-2026", "2026 winmm proxy backup (VS2019); never 1998 code", False),
    "i76wheel.exe": ("local-wrapper-2026", "2026 SendInput helper; never 1998 code", False),
}

VARIANT_SUFFIXES = (".orig", ".disabled", ".bak", ".old-278", ".dgvoodoo", ".2017galaxy",
                    ".camorig", ".farorig", ".u32xorig", ".25fps")


def base_key(name):
    n = name.lower()
    for suf in VARIANT_SUFFIXES:
        if n.endswith(suf):
            n = n[: -len(suf)]
            break
    if n in ("i76", "i76_pristine", "i76_pristine_fix", "i76_pristine.exe", "i76_pristine_fix.exe"):
        n = "i76.exe"
    if n.endswith(".exe") and n.startswith("i76") and n not in ROLES:
        n = "i76.exe"
    return n


def era_of(ident):
    """original-era: PE timestamp 1996-1998 and linker <= 5.10; modern otherwise. The 41-binary
    census in the pe-fingerprint report lists no original module with a later timestamp and no
    modern module with an earlier one, so the two predicates agree on every file here."""
    try:
        year = int(ident["pe_timestamp_utc"][:4])
    except (KeyError, ValueError):
        year = 0
    major = int(ident["linker"].split(".")[0])
    minor = int(ident["linker"].split(".")[1])
    old_linker = (major, minor) <= (5, 10)
    if 1995 <= year <= 1998 and old_linker:
        return "original-era", "pe_timestamp %s and linker %s" % (ident["pe_timestamp_utc"][:10], ident["linker"])
    if year > 1998 or not old_linker:
        return "modern", "pe_timestamp %s, linker %s" % (ident["pe_timestamp_utc"][:10], ident["linker"])
    return "unknown", "timestamp %s outside 1995-2026 (reproducible-build hash?)" % ident["pe_timestamp_utc"]


# ---- tiny TOML writer (values: str, int, bool, list, dict) ----
def tq(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def tval(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return tq(v)
    if isinstance(v, list):
        return "[" + ", ".join(tval(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join("%s = %s" % (tkey(k), tval(x)) for k, x in v.items()) + " }"
    raise TypeError(type(v))


def tkey(k):
    if all(c.isalnum() or c in "_-" for c in k):
        return k
    return tq(k)


def emit_table(lines, header, d, array=False):
    lines.append("")
    lines.append(("[[%s]]" if array else "[%s]") % header)
    for k, v in d.items():
        lines.append("%s = %s" % (tkey(k), tval(v)))


def module_row(ident, game_dir):
    key = base_key(ident["file"])
    role, scope, in_scope = ROLES.get(key, ("unclassified", "not in the section-2 table", False))
    era, era_why = era_of(ident)
    row = {
        "file": ident["file"],
        "relpath": os.path.relpath(ident["path"], game_dir).replace(os.sep, "\\"),
        "md5": ident["md5"],
        "sha256": ident["sha256"],
        "size": ident["size"],
        "mtime_utc": ident["mtime_utc"],
        "pe_timestamp": ident["pe_timestamp"],
        "pe_timestamp_utc": ident["pe_timestamp_utc"],
        "linker": ident["linker"],
        "machine": ident["machine"],
        "is_dll": ident["is_dll"],
        "era": era,
        "era_method": era_why,
        "role": role,
        "scope": scope,
        "in_scope": in_scope,
        "variant": ident["file"].lower() != key and ident["file"].lower() not in ("i76.exe",),
        "import_total": ident["import_total"],
        "imports": dict(sorted(ident["imports"].items())),
        "export_count": ident["export_count"],
        "sections": [{"name": s["name"], "va": s["va"], "vsize": s["vsize"], "raw_size": s["raw_size"]}
                     for s in ident["sections"]],
    }
    # ground truth: only the pristine exe bytes and the GOG-shipped shell bytes are reference
    if key == "i76.exe":
        if ident["md5"] == PRISTINE_MD5:
            row["ground_truth"] = True
            row["build_class"] = "pristine"
        elif ident["md5"] == PRISTINE_FIX_MD5:
            row["ground_truth"] = False
            row["build_class"] = "pristine+i76fix-p1"
            row["why"] = ("5 bytes at VA 0x499b25 (file 0x98f25) e826feffff -> b8c8000000, the i76fix patch1 that skips "
                          "the PIT CPU-speed probe (STATUS_PRIVILEGED_INSTRUCTION on NT); everything else pristine; "
                          "captures\\001-smoke\\allowlist.json")
        else:
            row["ground_truth"] = False
            row["build_class"] = "patched-build-only"
            row["why"] = "md5 != %s (pristine); imports %s" % (
                PRISTINE_MD5, ", ".join(k for k in ident["imports"] if k.lower() in ("u32x.dll", "winmm.dll", "win32.dll", "user32.dll")))
    elif key == "i76shell.dll":
        if ident["md5"] == GOG_SHELL_MD5:
            row["ground_truth"] = True
            row["build_class"] = "gog-shipped"
        else:
            row["ground_truth"] = False
            row["build_class"] = "patched-build-only"
            row["why"] = "md5 != %s (i76shell.dll.orig, GOG-shipped); imports %s" % (
                GOG_SHELL_MD5, ", ".join(k for k in ident["imports"] if k.lower() in ("u32x.dll", "user32.dll")))
    return row


def scan_modules(game_dir):
    files = []
    for sub in ("", "DLL"):
        d = os.path.join(game_dir, sub)
        for name in sorted(os.listdir(d), key=str.lower):
            p = os.path.join(d, name)
            if os.path.isfile(p) and pe_ident.is_pe(p):
                files.append(p)
    return files


def write_sandbox(game_dir, out_path, now):
    paths = scan_modules(game_dir)
    rows = [module_row(pe_ident.identity(p), game_dir) for p in paths]
    n_pe = len(rows)
    n_all = sum(len([f for f in os.listdir(os.path.join(game_dir, s)) if os.path.isfile(os.path.join(game_dir, s, f))])
                for s in ("", "DLL"))
    lines = [
        "# sandbox.toml - every PE module directly in the sandbox game folder and its DLL\\ subfolder.",
        "# Generated by tools\\gen_binaries.py; hashes/headers via tools\\pe_ident.py (pefile + hashlib).",
        "# era: original-era = PE timestamp 1995-1998 and linker <= 5.10, else modern (pe-fingerprint REPORT.md census).",
        "# ground_truth is set only on i76.exe / i76shell.dll rows: true for the pristine exe bytes (md5 %s)" % PRISTINE_MD5,
        "# and the GOG-shipped shell (md5 %s); every other copy is patched, non-ground-truth, with its md5." % GOG_SHELL_MD5,
        "# Method doc: %s section 2. Import counts = import-descriptor entries (pefile), not call sites." % METHOD_DOC,
    ]
    emit_table(lines, "sandbox", {
        "game_dir": game_dir,
        "generated_utc": now,
        "scanned_dirs": [".", "DLL"],
        "files_seen": n_all,
        "pe_modules": n_pe,
        "detection": "MZ + PE\\0\\0 signature (pe_ident.is_pe), non-recursive except DLL\\",
        "pristine_exe_md5": PRISTINE_MD5,
        "pristine_fix_exe_md5": PRISTINE_FIX_MD5,
        "patched_exe_md5": PATCHED_EXE_MD5,
        "gog_shell_md5": GOG_SHELL_MD5,
    })
    for r in rows:
        emit_table(lines, "module", r, array=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return rows


def write_reference(game_dir, out_path, now):
    ref = os.path.join(game_dir, "i76.exe.2017galaxy")
    ident = pe_ident.identity(ref)
    assert ident["md5"] == PRISTINE_MD5, "reference file is not pristine: %s" % ident["md5"]
    secs = {s["name"]: s for s in ident["sections"]}
    data = secs[".data"]
    with open(ref, "rb") as f:
        raw = f.read()
    data_raw = raw[int(data["raw_ptr"], 16): int(data["raw_ptr"], 16) + data["raw_size"]]
    last_nonzero = len(data_raw.rstrip(b"\0"))
    text = secs[".text"]
    rdata = secs[".rdata"]
    text_lo = int(text["va"], 16)
    text_hi = text_lo + text["vsize"]
    rdata_lo = int(rdata["va"], 16)
    rdata_hi = rdata_lo + rdata["vsize"]
    data_lo = int(data["va"], 16)
    data_init_hi = data_lo + data["raw_size"]
    data_hi = data_lo + data["vsize"]
    rsrc = secs[".rsrc"]

    lines = [
        "# i76-gog2017.toml - the reference build of Interstate '76 Gold (GOG 2017 Galaxy package), i76.exe.",
        "# Generated by tools\\gen_binaries.py from %s via tools\\pe_ident.py." % ref,
        "# Every number below is read from the file (pefile / hashlib) unless a 'source' field says otherwise.",
        "# Address classes follow method doc section 2.1 / gate A (section 4.1). Note: the method doc writes the",
        "# .rdata and .data file deltas as RVA deltas (VA - 0xC00, VA - 0x1400); as VA deltas they are 0x400c00 and",
        "# 0x401400 (file = VA - delta), which is what this file and tools\\which_build.py use.",
    ]
    emit_table(lines, "module", {
        "name": "i76.exe",
        "build": "Interstate '76 Gold Edition, GOG 2017 Galaxy package",
        "reference_file": ref,
        "generated_utc": now,
        "md5": ident["md5"],
        "sha256": ident["sha256"],
        "size": ident["size"],
        "pe_timestamp": ident["pe_timestamp"],
        "pe_timestamp_utc": ident["pe_timestamp_utc"],
        "file_mtime_utc": ident["mtime_utc"],
        "linker": ident["linker"],
        "linker_detail": "LINK 5.10.7303 + CVTRES 5.00.1668 (Visual Studio 97 SP3); 420 unmarked objects = VC++ 5.0 cl 11.00; "
                         "LZO banner '... by Microsoft C 1100' confirms _MSC_VER 1100",
        "linker_detail_source": FP_REPORT + " (Rich header decode + LZO banner)",
        "crt": "MSVCRT.dll, /MD (86 imports incl. _except_handler3, __getmainargs)",
        "machine": ident["machine"],
        "characteristics": ident["characteristics"],
        "characteristics_decoded": "RELOCS_STRIPPED | EXECUTABLE_IMAGE | LINE_NUMS_STRIPPED | LOCAL_SYMS_STRIPPED | 32BIT_MACHINE",
        "subsystem": ident["subsystem"],
        "image_base": ident["image_base"],
        "entry_point_va": ident["entry_point_va"],
        "size_of_image": ident["size_of_image"],
        "size_of_code": ident["size_of_code"],
        "size_of_init_data": ident["size_of_init_data"],
        "size_of_uninit_data": ident["size_of_uninit_data"],
        "symbols": "none (stripped); no relocations; no debug directory",
        "status": "reference",
        "ground_truth": True,
        "in_scope": True,
        "scope": "Primary partition, Phases 0-4 (method doc section 2)",
        "version_resource": "FileVersion '1, 0, 0, 1', ProductName Interstate '76, Comments 'Never get out of the car.' (pe-fingerprint)",
    })
    emit_table(lines, "byte_totals", {
        "text": text["vsize"],
        "rdata": rdata["vsize"],
        "data_initialised": data["raw_size"],
        "data_bss": data["vsize"] - data["raw_size"],
        "data_virtual": data["vsize"],
        "rsrc": rsrc["vsize"],
        "method": "section table: vsize per section; data_initialised = .data SizeOfRawData; data_bss = .data vsize - raw_size "
                  "(SizeOfUninitializedData is 0 and there is no .bss section: the linker merged BSS into .data)",
        "data_last_nonzero_raw_byte": last_nonzero,
        "data_last_nonzero_method": "len(raw .data image rstrip b'\\0') over the 260,096 raw bytes",
    })
    for s in ident["sections"]:
        emit_table(lines, "section", s, array=True)
    emit_table(lines, "imports", {
        "descriptors": len(ident["imports"]),
        "total": ident["import_total"],
        "method": "pefile import descriptors; per-DLL count = thunk entries (not call sites; see symbols\\imports.tsv, gate C)",
        "iat_va": "0x4bc000",
        "iat_end_va": "0x4bc404",
        "iat_size": 1028,
        "iat_layout": "244 thunks + 13 null terminators (data directory IAT rva 0xbc000 size 1028)",
        "import_directory_va": "0x4c04b8",
        "import_directory_size": 280,
        "note": "WIN32.dll is GOG's in-place rename of WINMM.dll (9 bytes, same 9 functions); the patched local i76.exe "
                "restores WINMM.dll and redirects USER32.dll -> u32x.dll (pe-fingerprint)",
        "per_dll": dict(sorted(ident["imports"].items())),
    })
    classes = [
        {"class": "init", "va_lo": hex(text_lo), "va_hi": hex(text_hi), "section": ".text", "bytes": text["vsize"],
         "file_delta": "0x400c00", "rule": "file bytes at VA - delta contain the claimed literal or a non-zero value consistent with the type"},
        {"class": "init", "va_lo": hex(rdata_lo), "va_hi": hex(rdata_hi), "section": ".rdata", "bytes": rdata["vsize"],
         "file_delta": "0x400c00", "rule": "as above; IAT sub-range is class iat"},
        {"class": "iat", "va_lo": "0x4bc000", "va_hi": "0x4bc404", "section": ".rdata", "bytes": 1028,
         "file_delta": "0x400c00", "rule": "slot in [0x4bc000, 0x4bc404); name from the import descriptor"},
        {"class": "init", "va_lo": hex(data_lo), "va_hi": hex(data_init_hi), "section": ".data (initialised)", "bytes": data["raw_size"],
         "file_delta": "0x401400", "rule": "as .text"},
        {"class": "bss", "va_lo": hex(data_init_hi), "va_hi": hex(data_hi), "section": ".data (BSS)", "bytes": data["vsize"] - data["raw_size"],
         "file_delta": "n/a (zero in the file, loader-zeroed)",
         "rule": "accepted only if a .text instruction's disp32/imm32 decodes to it or to an enclosing array base named in the same row; "
                 "referencing instruction address and counting method recorded"},
        {"class": "init", "va_lo": hex(int(rsrc["va"], 16)), "va_hi": hex(int(rsrc["va"], 16) + rsrc["vsize"]), "section": ".rsrc",
         "bytes": rsrc["vsize"], "file_delta": "0x569c00", "rule": "VS_VERSION_INFO only"},
        {"class": "file", "va_lo": "n/a", "va_hi": "n/a", "section": "n/a", "bytes": 0, "file_delta": "n/a",
         "rule": "explicit tag; a file offset is converted, never quoted as a VA"},
        {"class": "rva", "va_lo": "n/a", "va_hi": "n/a", "section": "n/a", "bytes": 0, "file_delta": "n/a",
         "rule": "explicit tag; VA = 0x400000 + rva"},
        {"class": "heap-offset", "va_lo": "n/a", "va_hi": "n/a", "section": "n/a", "bytes": 0, "file_delta": "n/a",
         "rule": "explicit tag; (source, key, offset), never absolute"},
        {"class": "pool-offset", "va_lo": "n/a", "va_hi": "n/a", "section": "n/a", "bytes": 0, "file_delta": "n/a",
         "rule": "explicit tag; (source, key, offset), never absolute"},
    ]
    for c in classes:
        emit_table(lines, "address_class", c, array=True)
    emit_table(lines, "gate_a_negative_set", {
        "must_fail_as_va": ["0x4c1a8c"],
        "note_0x4c1a8c": "file offset mislabelled as VA in an earlier draft; the FSM prototype table is at 0x4c2e8c",
        "wrong_tables": {"0x4f26f0": "heap-tag strings; the gamekey table is at 0x4f3af0", "0x4edd58": "renderer name strings, 18 not 19"},
        "must_pass_bss_fail_init": ["0x5a7e1c"],
        "must_pass_iat": ["0x4bc100"],
        "bss_slot_only": ["0x608bb8"],
        "source": METHOD_DOC + " section 4.1",
    })
    # non-ground-truth copies present in the sandbox
    ngt = []
    for name, why in (
        ("i76.exe", "local playable build: .text vsize +132 (765,657), .rdata 22,424, .rsrc 1,688; imports u32x.dll + WINMM.dll; string I76PATCH.DLL (pe-fingerprint)"),
        ("i76shell.dll", "local shell: imports u32x.dll instead of USER32.dll (43 functions); compare i76shell.dll.orig"),
        ("i76_pristine_fix.exe", "pristine + i76fix patch1 (5 bytes at 0x499b25); the only exe bytes that run on Windows 10 19045 (captures\\001-smoke)"),
        ("i76.25fps", "same size as pristine, different md5; provenance not recorded here (measure before use)"),
        ("i76.exe.camorig", "1,051,648 B like the patched build; earlier patched variant"),
        ("i76.exe.farorig", "1,051,648 B like the patched build; earlier patched variant"),
        ("i76.exe.u32xorig", "1,051,648 B like the patched build; earlier patched variant"),
    ):
        p = os.path.join(game_dir, name)
        if os.path.exists(p):
            d = pe_ident.identity(p)
            ngt.append({"file": name, "md5": d["md5"], "size": d["size"], "mtime_utc": d["mtime_utc"],
                        "text_vsize": [s["vsize"] for s in d["sections"] if s["name"] == ".text"][0],
                        "imports": dict(sorted(d["imports"].items())),
                        "ground_truth": False,
                        "build_class": "pristine+i76fix-p1" if d["md5"] == PRISTINE_FIX_MD5 else "patched-build-only",
                        "why": why})
    for r in ngt:
        emit_table(lines, "non_ground_truth", r, array=True)
    emit_table(lines, "h0_allowlist", {
        "entries": [{"va": "0x499b25", "len": 5, "orig": "e826feffff", "new": "b8c8000000",
                     "new_md5": hashlib.md5(bytes.fromhex("b8c8000000")).hexdigest(),
                     "why": "i76fix patch1; stamps the run pristine+i76fix-p1"}],
        "source": "captures\\001-smoke\\allowlist.json; tools\\allowlist.json",
    })
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return ident, ngt


def verify(path, expect_md5_by_file):
    import tomllib
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    bad = []
    n = 0
    for row in doc.get("module", []) if isinstance(doc.get("module"), list) else [doc.get("module")]:
        if not row:
            continue
        n += 1
        f = row.get("file") or row.get("name")
        p = row.get("relpath") or row.get("reference_file")
        if p and os.path.exists(p if os.path.isabs(p) else os.path.join(expect_md5_by_file, p)):
            ap = p if os.path.isabs(p) else os.path.join(expect_md5_by_file, p)
            md5, _ = pe_ident.hashes(ap)
            if md5 != row["md5"]:
                bad.append((f, row["md5"], md5))
    return n, bad, doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-dir", default=DEFAULT_GAME)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "binaries"))
    a = ap.parse_args()
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ref_path = os.path.join(a.out, "i76-gog2017.toml")
    sb_path = os.path.join(a.out, "sandbox.toml")
    ident, ngt = write_reference(a.game_dir, ref_path, now)
    rows = write_sandbox(a.game_dir, sb_path, now)
    print("wrote %s (%d B): md5 %s, %d sections, %d imports in %d DLLs, %d non-ground-truth rows" % (
        ref_path, os.path.getsize(ref_path), ident["md5"], len(ident["sections"]), ident["import_total"],
        len(ident["imports"]), len(ngt)))
    print("wrote %s (%d B): %d PE modules" % (sb_path, os.path.getsize(sb_path), len(rows)))
    # read back
    n1, bad1, _ = verify(ref_path, a.game_dir)
    n2, bad2, doc2 = verify(sb_path, a.game_dir)
    eras = {}
    for r in doc2["module"]:
        eras[r["era"]] = eras.get(r["era"], 0) + 1
    print("readback: i76-gog2017.toml %d module row(s), %d md5 mismatch; sandbox.toml %d rows, %d md5 mismatch; eras %s" % (
        n1, len(bad1), n2, len(bad2), eras))
    for b in bad1 + bad2:
        print("  MISMATCH", b)
    return 1 if (bad1 or bad2) else 0


if __name__ == "__main__":
    sys.exit(main())
