"""l_vehicle.py - vehicle definition chain layouts (.vdf here; .vcf/.vsf/.cdf/.gdf/.wdf/.xdf/.vtf in l_defs.py).

Citations from data\\notes\\vdf.md. Handlers get the chunk header, so [hdr+N] = body N-8.
Handler sets: A spawn (table 0x4feff0), B VCF info (0x4ff0b0), C VCF legality check (0x500090).
Fields that a handler only copies opaquely into a struct nobody reads are `typed` (meaning inferred from values).
"""
import struct
from layouts import register, Layout, L
from schema import U8, U16, U32, I32, F32, Str, Raw, Arr, Struct, Field, coverage


def F(name, typ, meaning="", cite="", unused=False):
    return Field(name, typ, meaning, cite, unused)


def St(name, *fields):
    return Struct(name, list(fields))


VEC3 = St("vec3", F("x", F32), F("y", F32), F("z", F32))
MAT3 = Arr(F32, 9)

VDFC = St("VDFC",
          F("name", Str(20), "display name (not NUL-terminated at 20 chars; handler B strcpy then over-reads)", "B 0x4adf7e, strcpy 0x4adf9e -> info+0xa0"),
          F("class_id", U32, "object class: 1 car, 8 emplacement, 9 aircraft (table 0x4f76e0)", "A 0x4adeea -> obj_SetClass 0x461970"),
          F("size", U32, "weight class: armour+chassis budget 1600*size, each facet >= 50*size", "A 0x4adf28 -> classdata+0x47c; C 0x4b3cb4 -> 0x5db958 (check 0x4b3896..0x4b3919)"),
          F("lod", Arr(F32, 5), "LOD switch distances (last = 100000 sentinel)", "A 0x4adf41 rep movsd -> ctx+0x3c -> entity+0x1c (0x457350)"),
          F("mass", F32, "mass: rigidbody_SetMass stores m and 1/m", "A 0x4adf0d -> classdata+0xa4; 0x438f3b -> 0x438340; B 0x4adfb7 -> info+0xaa4"),
          F("collision_mult", F32, "stored at classdata+0x124; no reader (always 1.0)", "A 0x4adf16/0x4adf19"),
          F("drag", F32, "aerodynamic drag: k*v^2*drag", "A 0x4adf1f -> classdata+0x120; 0x43ad99, 0x40fb07"),
          F("hardpoint_count", U32, "number of HLOC chunks (weapon mounts)", "A 0x4adf57, B 0x4adfac, C 0x4b3cbd -> 0x5db7c4"),
          F("elt", Str(13), "HUD element table (vpit_1.elt)", "A 0x4adf31 -> elt_Load 0x448010"))

PART100 = St("part100",
             F("name", Str(8), "part name = geometry stem (+.geo, bit 7 masked, 'null' = none)", "0x4b770a/0x4b7707 -> 0x4ad640"),
             F("rotation", MAT3, "rows right/up/forward -> obj+0x18", "0x4b8256..0x4b8285"),
             F("pos", VEC3, "local position -> obj+0x40", "0x4b828f..0x4b829d"),
             F("parent", Str(8), "parent part ('WORLD'/'NULL' = owner)", "0x4b7633..0x4b7665 -> 0x4b47f0"),
             F("centre", VEC3, "bounding box centre -> obj+0x84", "0x4b8340"),
             F("radius", F32, "bounding sphere radius -> obj+0x90", "0x4b8337"),
             F("half", VEC3, "AABB half extents", "0x4b835d..0x4b839e"),
             F("class_id", U32, "part class (65 BDYF, 66 BDYM, 67 BDYB, 68 BDYT, 71 HLGT, 72 BLGT ... -> classdata slots, cb 0x4ae2e0)", "0x4b831e, 0x4b83ad"),
             F("flags", U32, "obj+0x10 flag word", "0x4b82c0/0x4b82cb"))
PART_NAME = St("part100_name",
               F("name", Str(8), "geometry name for this LOD/damage slot", "0x4b7707/0x4b770a -> geocache_SetGeoName 0x4461e0"),
               F("rest", Raw(92), "never read for rows other than (0,0)", "0x4b77ee path", unused=True))


def _rows_parse(b, nrows, off):
    n = struct.unpack_from("<I", b, off)[0]
    p = off + 4
    rows = []
    for r in range(nrows):
        t = PART100 if r == 0 else PART_NAME
        row = []
        for _ in range(n):
            v, p = t.parse(b, p, {"_end": len(b)})
            row.append(v)
        rows.append(row)
    return n, rows, p


def _vgeo_parse(b):
    n, rows, p = _rows_parse(b, 28, 0)
    if p != len(b):
        raise ValueError("VGEO %d != 4+2800*%d" % (len(b), n))
    return {"n_parts": n, "rows": rows}


def _vgeo_emit(v):
    out = bytearray(struct.pack("<I", v["n_parts"]))
    for r, row in enumerate(v["rows"]):
        t = PART100 if r == 0 else PART_NAME
        for x in row:
            out += t.emit(x, {})
    return bytes(out)


def _vgeo_cov(v):
    c = {"cited": 4, "typed": 0, "unused": 0, "unknown": 0}
    for r, row in enumerate(v["rows"]):
        t = PART100 if r == 0 else PART_NAME
        for x in row:
            for k, n in coverage(t, x).items():
                c[k] += n
    return c


VGEO_L = Layout(parse=_vgeo_parse, serialise=_vgeo_emit, cov=_vgeo_cov,
                doc="u32 n (0x4ae3b6) + 28 rows (row = lod*4 + damage; 7 LOD x 4 damage) of n 100-byte parts (0x4b7570, 0x4b75a0)")

CHUNK100 = St("vchk_rec",
              F("name", Str(8), "chunk name", "0x4ae525/0x4ae51d"),
              F("rotation", MAT3, "rotation", "0x4ae47b..0x4ae4bc"),
              F("pos", VEC3, "position", "0x4ae478/0x4ae485/0x4ae499"),
              F("parent", Str(8), "not read", "0x4ae400", unused=True),
              F("centre", VEC3, "not read (zeros used)", "0x4ae469..0x4ae471", unused=True),
              F("radius", F32, "collision sphere radius", "0x4ae4de"),
              F("half", VEC3, "box half extents", "0x4ae4e5/0x4ae4ec/0x4ae4f3"),
              F("class_id", U32, "not read", "0x4ae400", unused=True),
              F("flags", U32, "not read", "0x4ae400", unused=True))
VCHK = St("VCHK",
          F("parent", Str(8), "owning part (gets obj+0x10 |= 0x100000)", "0x4ae412/0x4ae415 -> 0x4b47f0"),
          F("n", U32, "record count", "0x4ae45e, loop 0x4ae558"),
          F("chunks", Arr(CHUNK100, "n"), "collision/debris chunks -> obj_AddChunk 0x4a0ff0", "0x4ae531"))

VLOC = St("VLOC",
          F("class_id", U32, "locator kind: 35 tach needle, 36 speedo needle, 38 headlight mask, 40 cockpit camera, 42 position only", "0x4ae013 switch (table 0x4ae2b4)"),
          F("rotation", MAT3, "child rotation (ignored for class 42)", "0x4ae253..0x4ae289; 0x4ae094 rep movsd"),
          F("pos", VEC3, "child position", "0x4ae28c..0x4ae298; class 42: 0x4ae02e -> classdata+0x12c"))

COLP = St("COLP",
          F("z", Arr(F32, 4), "Z planes max outer, max inner, min inner, min outer", "colp_BuildBox 0x4b81c0: 0x4b820f..0x4b8221"),
          F("x", Arr(F32, 4), "X planes (same order)", "0x4b81df..0x4b81f1"),
          F("y", Arr(F32, 4), "Y planes (same order)", "0x4b81f7..0x4b8209; ignored for class 8 (0x4ae57f)"))

WHEELLOC = St("wloc",
              F("present", U32, "wheel slot used (1) (inferred; absent slots hold garbage)"),
              F("rotation", MAT3, "wheel rotation (inferred)"),
              F("pos", VEC3, "wheel position (inferred)"),
              F("ui_x", U16, "garage UI x (inferred)"), F("ui_y", U16, "garage UI y (inferred)"))
WLOC = St("WLOC", F("wheels", Arr(WHEELLOC, 6), "6 wheel slots copied opaquely by 0x4ae5b1 -> info+0x168 (no reader found)"))

HLOC = St("HLOC",
          F("label", Str(16), "hardpoint label", "B 0x4aea9c strcpy -> slot+0"),
          F("index", U32, "mount index matched against VCF WEPN mounts", "A 0x4aea22 -> +0xb0; C 0x4b3cea; match 0x4aec5f, 0x4b3ac4"),
          F("facing", U32, "facing (1/2)", "A 0x4aea50 -> +0xb4; C 0x4b3cfd"),
          F("mesh_type", U32, "mount mesh type (1,2,4,5)", "A 0x4aea39 -> +0xb8; C 0x4b3d09"),
          F("transform", Arr(F32, 12), "mount rotation[9] + position[3]", "A 0x4aea5a rep movsd -> slot+0xbc"),
          F("extra", U32, "copied to slot+0xec (always 0)", "B 0x4aeb33"))

SPCS = St("SPCS", F("slots", Arr(St("uixy", F("x", U16), F("y", U16)), 3), "3 specials icon positions (inferred), copied by 0x4aeb60 -> info+0xa64"))
VSHL = St("VSHL",
          F("smk", Str(13), "garage showcase video (scarcon1.smk) (inferred)"),
          F("xy", Arr(U16, 4), "two UI x,y pairs (inferred)"),
          F("zeros", Arr(U32, 5), "zero in every file"),
          F("xy2", Arr(U16, 2), "UI x,y (inferred); whole chunk copied by 0x4adfd0 -> info+0x10a, no reader"))

register("vdf", "", "VDFC", L(VDFC))
register("vdf", "", "VGEO", VGEO_L)
register("vdf", "", "VCHK", L(VCHK))
register("vdf", "", "VLOC", L(VLOC))
register("vdf", "", "COLP", L(COLP))
register("vdf", "", "WLOC", L(WLOC))
register("vdf", "", "HLOC", L(HLOC))
register("vdf", "", "SPCS", L(SPCS))
register("vdf", "", "VSHL", L(VSHL))
