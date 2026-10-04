"""l_msn.py - mission (.msn/.lvl) and scenery (.sdf) chunk layouts, cited (data\\notes\\msn-sdf.md).

Leaf handlers receive the chunk HEADER pointer (walker 0x4b3db0, 0x4b403a..0x4b4042), so an exe operand
[reg+N] on a handler's argument is body offset N-8. Citations are instruction addresses in i76.exe (GOG, md5 9a232dcc).
"""
from layouts import register, Layout, S, L
from schema import U8, U16, U32, I32, F32, Str, Raw, Arr, Struct, Field
import fsm


def F(name, typ, meaning="", cite="", unused=False):
    return Field(name, typ, meaning, cite, unused)


def St(name, *fields):
    return Struct(name, list(fields))


VEC3 = S("vec3", ("x", F32, "x"), ("y", F32, "y"), ("z", F32, "z"))
MAT3 = Arr(F32, 9)

# ---- WDEF/WRLD (331 B): wrld_h_Load 0x4b8a10, title reader 0x4b4a10 ------------------------------------------
SURFACE = St("surface",
             F("grip", F32, "surface grip (inferred name); zeroed above 0.2 for flag-0x400 vehicles", "accessor 0x492777; consumers 0x43c310/0x43c6f0/0x43ce10/0x43d240"),
             F("drag", F32, "rolling drag (inferred name): -f*load term", "accessor 0x492787; consumers 0x40f9c0, 0x43a5d0"),
             F("bump", F32, "bump amplitude: height += f * noise (0x4be398)", "accessor 0x492797; consumer 0x46dc10"),
             F("pad", U32, "never read (no accessor, no xref to 0x64422c)", "copied by 0x4b8b26 only", unused=True),
             F("damage_rate", I32, "random part damage rate at speed > 7.65 (f*dt)", "accessor 0x4927a7 fild; consumer 0x438fd0 -> 0x4641e0"))
WRLD = St("WRLD",
          F("cd_track", U32, "CD-audio music track", "0x4b8a17 -> 0x423320 -> [0x4ed800]"),
          F("intro_smk", Str(13), "movie before the mission", "0x4b8bd7..0x4b8bff -> 0x5dd300 -> WinMain 0x403716"),
          F("outro_smk", Str(13), "movie after the mission", "0x4b8bfc..0x4b8c20 -> 0x5dd310 -> WinMain 0x40425f"),
          F("palette", Str(13), ".ACT palette (768 B -> 0x4fa170)", "0x4b8a33 -> 0x46ffc0; 0x4b8a88"),
          F("lum_table", Str(13), ".LUM luminance table", "0x4b8a53 -> 0x46ffc0; 0x4b8a9b"),
          F("xluc_table", Str(13), ".TBL translucency table (64 KB -> 0x60afa0)", "0x4b8ac8; 0x4b8af3"),
          F("objective_text", Str(13), ".npt notepad objectives", "0x4b8b6e -> 0x6094f0; loader 0x45dea0"),
          F("sky_texture", Str(13), "sky .MAP", "0x4b8b49 -> 0x5dce60; 0x404e50"),
          F("scrounge_sdf", Str(13), "scrounge pickup .sdf ('' = none)", "0x4b8bb3 -> 0x4b8500"),
          F("terrain_texture", Str(13), "terrain texture set .MAP", "0x4b8bbf -> 0x4908f0"),
          F("map_screen", Str(13), "in-game map image", "0x4b8b8f -> 0x5a7ec8; 0x49cdf0"),
          F("horizon_hzd", Str(13), ".HZD horizon definition", "0x4b8bcb -> 0x401540"),
          F("hour_of_day", I32, "0..23; sky/sun table index ((h+2)%24)*8/24", "0x4b8a21 -> 0x477b00"),
          F("surfaces", Arr(SURFACE, 8), "per-surface-type physics, indexed by veh+0x45c", "0x4b8b26..0x4b8b47 -> 0x644220"),
          F("far_clip", I32, "view distance (600 in every mission); used when option 0x654b8a is set, else 150; clamped 100..100000", "0x4b8c2a fild [hdr+0x13f] -> 0x4c271c; 0x4059de -> 0x472220"),
          F("mission_title", Str(16), "title for the shell mission picker (loader never reads it)", "0x4b4a21 (shell_cb_22 0x4b4a80)"))
register("msn", "WDEF", "WRLD", L(WRLD))

# ---- TDEF (table 0x4fae18, walker 0x493910) ----------------------------------------------------------------
ZMAP = St("ZMAP",
          F("zone_count", U8, "distinct terrain zones (= 32 KiB tiles in the .ter)", "0x49397f movsx [hdr+8] -> 0x5a4620"),
          F("grid", Raw(6400), "80x80 i8 zone per 640 m cell, row-major, -1 = none; each < zone_count", "0x493983/0x49398c rep movsd -> 0x5a4768; check 0x493990..0x4939b2"))
ZONE = St("ZONE",
          F("pad", U8, "skipped (handler starts at hdr+9); 0xFF in every mission", "0x4939db lea ebx,[eax+9]", unused=True),
          F("ter", Str(13), "terrain .ter (addon\\ first, then CD)", "0x4939f2..0x493b51 -> 0x471400"))
register("msn", "TDEF", "ZMAP", L(ZMAP))
register("msn", "TDEF", "ZONE", L(ZONE))

# ---- RDEF/RSEG (handler 0x4b8780) -------------------------------------------------------------------------
RPOINT = St("road_xsec",
            F("lx", F32, "left edge x", "0x48e1a0"), F("ly", F32, "left y: overwritten by terrain height", "0x48e4ed fstp", unused=True),
            F("lz", F32, "left edge z", "0x48e1a0"),
            F("rx", F32, "right edge x", "0x48e1a0"), F("ry", F32, "right y: overwritten by terrain height", "0x48e418 fstp", unused=True),
            F("rz", F32, "right edge z", "0x48e1a0"))
RSEG = St("RSEG",
          F("type", U32, "road type; only type % 3 is used: 0 paved, 1 dirt, 2 wash", "0x4b881c -> node+0x10; 0x48ea18 idiv 3"),
          F("n", U32, "cross-section count (split into nodes of <= 25)", "0x4b8789"),
          F("sections", Arr(RPOINT, "n"), "road ribbon", "copy 0x4b8837/0x4b8903"))
register("msn", "RDEF", "RSEG", L(RSEG))

# ---- ODEF/OBJ (handler 0x4b7ac0 -> obj_CreateFromRecord 0x4b8230, snap=1) -------------------------------------
OBJ = St("OBJ",
         F("label", Str(8), "object file name (+.vcf/.sdf) with bit 7 of each byte = MSB-first instance number; raw 8 bytes = entity key", "0x4b7aca -> 0x4ad640 (and 0x7f); 0x4b7d97 -> 0x457610"),
         F("rotation", MAT3, "3x3 rows right/up/forward -> obj+0x18", "0x4b8256..0x4b8288"),
         F("pos_x", F32, "world X", "0x4b828f"),
         F("pos_y", F32, "world Y: replaced by terrain height (ODEF snaps)", "0x4b8297 then 0x4b82b5 -> 0x493550", unused=True),
         F("pos_z", F32, "world Z", "0x4b829d"),
         F("bounds", Raw(36), "bounds centre/radius/half extents: read only when snap==0; ODEF passes snap=1", "0x4b8337 (snap==0 path); ODEF 0x4b7b96 push 1", unused=True),
         F("class_id", U32, "1 car (spawn/regen/.vcf), 8/9 vehicle, 2/3/4/7/10/11/12/80/82/83 scenery (.sdf)", "0x4b7b06; switch 0x4b7b87"),
         F("flags", U16, "obj+0x10; 0x10 = player", "0x4b82c0 -> obj+0x10; 0x458bf8 test 0x10"),
         F("team", U16, "obj+0x12 (copied; no team reader found)", "0x4b82c0"))
register("msn", "ODEF", "OBJ", L(OBJ))

LOBJ_STR = St("LDEF_OBJ",
              F("label", Str(8), "string-object geometry name (afence3, aitire1)", "0x4b8f82 -> 0x4b8230"),
              F("rotation", MAT3, "read, then replaced by identity 0x4faed8", "0x4b9043", unused=True),
              F("pos", VEC3, "read, then replaced by point[0]", "0x4b9027", unused=True),
              F("bounds", Raw(36), "not read (snap=1)", "0x4b8230 snap path", unused=True),
              F("class_id", U32, "class of the first piece (later pieces class 3)", "0x4b831e -> 0x461970"),
              F("flags", U32, "obj+0x10", "0x4b82c0"),
              F("n_points", U32, "post count", "0x4b8fc5"),
              F("points", Arr(VEC3, "n_points"), "post positions, world coords (y re-snapped)", "0x4b8fe2 -> pool 0x5dd320"))
register("msn", "LDEF", "OBJ", L(LOBJ_STR))


# ---- ADEF/FSM ------------------------------------------------------------------------------------------------
def _fsm_cov(v):
    n = len(fsm.serialise(v))
    return {"cited": n, "typed": 0, "unused": 0, "unknown": 0}


register("msn", "ADEF", "FSM", Layout(parse=fsm.parse, serialise=fsm.serialise, cov=_fsm_cov, doc="mission script, see fsm.py"))

# ---- SDF (bwd2_LoadDef 0x4b41e0, table 0x500b18) --------------------------------------------------------------
SDFC = St("SDFC",
          F("display_name", Str(16), "editor name; never read", "no reader (buffer released 0x4b4278)", unused=True),
          F("class_hint", U32, "editor class; never read", "no reader", unused=True),
          F("stats", Arr(F32, 5), "copied to ctx+0x3c -> entity rec +0x1c..+0x2c (no reader found; Open76: size xyz + 2)", "0x4b7f7e rep movsd x5; 0x4572b0"),
          F("health", U32, "never read by SDFC (hit points come from SGEO part +0x64)", "no reader", unused=True),
          F("explosion_xdf", Str(13), "explosion .xdf (owner classes 2/3/11/12)", "0x4b7fb4 -> 0x4b8c40"),
          F("destroy_sound", Str(13), "destruction sound", "0x4b7fbe..0x4b7fda -> classdata+0x18"))
PART = St("part120",
          F("name", Str(8), "geometry name (+.geo)", "0x4b7800 -> 0x4ad640"),
          F("rotation", MAT3, "local rotation", "0x4b8256.."),
          F("pos", VEC3, "local position", "0x4b828f..0x4b829d"),
          F("parent", Str(8), "parent part; WORLD/NULL = owner", "0x4b7800 -> 0x4b47f0"),
          F("centre", VEC3, "bounds centre -> obj+0x84", "0x4b8340"),
          F("radius", F32, "bounding radius -> obj+0x90", "0x4b8337"),
          F("half", VEC3, "half extents -> obj+0x94..0xa8", "0x4b835d..0x4b839e"),
          F("class_id", U32, "part class (0x51 = attach-transform)", "0x4b831e, 0x4b83ad"),
          F("flags", U32, "obj+0x10; bits 10-11 select xdf/sound pair", "0x4b82c0; 0x4b7c7e"),
          F("hit_points", U32, "hit points (classes 2/3/4/11/12 -> 0x46b200)", "0x4b83cb, 0x4b8419, 0x4b8430"),
          F("params", Arr(F32, 3), "class 10 spin rates (x2pi) / class 7 params", "0x4b83fb, 0x4b83ce"),
          F("param4", U32, "class 7 only (0x46d6f0 arg 5)", "0x4b83ce"))
PART_NAMEONLY = St("part120_name",
                   F("name", Str(8), "geometry name for this LOD/damage slot", "0x4b7800 -> 0x4461e0"),
                   F("rest", Raw(112), "only the name of arrays 1..5 is read", "0x4b7800", unused=True))


def _sgeo_parse(b):
    import struct as _s
    n = _s.unpack_from("<I", b)[0]
    if len(b) != 4 + 720 * n:
        raise ValueError("SGEO size %d != 4+720*%d" % (len(b), n))
    arrs = []
    p = 4
    for k in range(6):
        t = PART if k == 0 else PART_NAMEONLY
        a = []
        for _ in range(n):
            v, p = t.parse(b, p, {"_end": len(b)})
            a.append(v)
        arrs.append(a)
    return {"n_parts": n, "arrays": arrs}


def _sgeo_emit(v):
    import struct as _s
    out = bytearray(_s.pack("<I", v["n_parts"]))
    for k, a in enumerate(v["arrays"]):
        t = PART if k == 0 else PART_NAMEONLY
        for x in a:
            out += t.emit(x, {})
    return bytes(out)


def _sgeo_cov(v):
    from schema import coverage
    c = {"cited": 4, "typed": 0, "unused": 0, "unknown": 0}
    for k, a in enumerate(v["arrays"]):
        t = PART if k == 0 else PART_NAMEONLY
        for x in a:
            for kk, n in coverage(t, x).items():
                c[kk] += n
    return c


SGEO_L = Layout(parse=_sgeo_parse, serialise=_sgeo_emit, cov=_sgeo_cov,
                doc="u32 n (0x4b800b), then 6 arrays of n 120-byte parts: arr[2*lod+damaged]; only arr[0] creates objects (0x4b8015..0x4b8026, 0x4b7800)")
SCHK_REC = St("chunk120",
              F("name", Str(8), "chunk name", "0x4b8175/0x4b816d -> 0x4a0ff0"),
              F("rotation", MAT3, "rotation", "0x4b80cb..0x4b810c"),
              F("pos", VEC3, "position", "0x4b80c8, 0x4b80d5, 0x4b80e9"),
              F("parent", Str(8), "not read by SCHK", "0x4b8050", unused=True),
              F("centre", VEC3, "not read (0,0,0 substituted)", "0x4b80b9..0x4b80c1", unused=True),
              F("radius", F32, "collision radius", "0x4b812e"),
              F("half", VEC3, "box half extents [-h,+h]", "0x4b8113/0x4b8150/0x4b8159, 0x4b8135..0x4b8143"),
              F("rest", Raw(28), "class etc.: not read", "0x4b8050", unused=True))
SCHK = St("SCHK",
          F("parent", Str(8), "parent part name (gets obj+0x10 |= 0x100000)", "0x4b8062/0x4b8065 -> 0x4b47f0"),
          F("n", U32, "collision chunk count", "0x4b80ae"),
          F("chunks", Arr(SCHK_REC, "n"), "collision boxes, stride 0x78", "0x4b81a2"))
SOBJ = St("SOBJ",
          F("name", Str(8), "shadow/extra geometry name -> owner obj+0x5c", "0x4b8479 -> 0x4ad640 -> 0x4469a0; 0x4b8498"),
          F("rest", Raw(92), "rotation/pos/parent/bounds/class: not read", "0x4b8470", unused=True))
LOBJ = St("LOBJ",
          F("light_type", U32, "0 omni, 1 spot", "0x4b8f16 -> 0x477c20"),
          F("rot01", Arr(F32, 6), "rotation rows 0-1: not read", "0x4b8ed0", unused=True),
          F("direction", VEC3, "spot direction (row 2, negated)", "0x4b8edc..0x4b8ee6"),
          F("pos", VEC3, "light position offset", "0x4b8eed..0x4b8efb"),
          F("rest8", Raw(8), "not read", "0x4b8ed0", unused=True),
          F("cone", F32, "cone angle rad, clamped 10..90 deg", "0x4b8f0f"),
          F("range", F32, "range, clamped >= 20", "0x4b8f13"),
          F("rest4", Raw(4), "not read", "0x4b8ed0", unused=True))
register("sdf", "", "SDFC", L(SDFC))
register("sdf", "", "SGEO", SGEO_L)
register("sdf", "", "SCHK", L(SCHK))
register("sdf vdf", "", "SOBJ", L(SOBJ))
register("sdf vdf", "", "LOBJ", L(LOBJ))
