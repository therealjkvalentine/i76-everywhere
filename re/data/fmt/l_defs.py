"""l_defs.py - weapon (.gdf), wheel (.wdf), explosion (.xdf) and texture-set (.vtf) layouts.

Citations from data\\notes\\gdf-wdf-xdf-vtf.md; handlers get the chunk header ([hdr+N] = body N-8).
Grouped 100-byte part records (GGEO/OGEO/WGEO/XGEO): geo_SplitPartGroups 0x4b7570 + geo_BuildLodParts 0x4b75a0;
the first group of each build creates objects (full record read by 0x4b8230), the other groups contribute only
their 8-byte geometry name (0x4b771f -> 0x4461e0).
"""
import struct
from layouts import register, Layout, L
from schema import U8, U16, U32, I32, F32, Str, Raw, Arr, Struct, Field, coverage
from l_vehicle import PART100, PART_NAME, VEC3, MAT3


def F(name, typ, meaning="", cite="", unused=False):
    return Field(name, typ, meaning, cite, unused)


def St(name, *fields):
    return Struct(name, list(fields))


def grouped(ngroups, full, doc):
    """u32 count + ngroups x count part records; groups in `full` are read whole, the rest name-only."""
    def parse(b):
        n = struct.unpack_from("<I", b)[0]
        p, groups = 4, []
        for g in range(ngroups):
            t = PART100 if g in full else PART_NAME
            row = []
            for _ in range(n):
                v, p = t.parse(b, p, {"_end": len(b)})
                row.append(v)
            groups.append(row)
        if p != len(b):
            raise ValueError("grouped: consumed %d of %d" % (p, len(b)))
        return {"count": n, "groups": groups}

    def emit(v):
        out = bytearray(struct.pack("<I", v["count"]))
        for g, row in enumerate(v["groups"]):
            t = PART100 if g in full else PART_NAME
            for x in row:
                out += t.emit(x, {})
        return bytes(out)

    def cov(v):
        c = {"cited": 4, "typed": 0, "unused": 0, "unknown": 0}
        for g, row in enumerate(v["groups"]):
            t = PART100 if g in full else PART_NAME
            for x in row:
                for k, n in coverage(t, x).items():
                    c[k] += n
        return c
    return Layout(parse=parse, serialise=emit, cov=cov, doc=doc)


# ---- .gdf weapon ---------------------------------------------------------------------------------------------
GDFC = St("GDFC",
          F("name", Str(16), "display name", "0x4aeea9; weapdef_Register 0x4a303c"),
          F("class", I32, "1 handgun, 2 slug, 3 mortar, 4 SPP, 5 flame, 6 dropper (else 'ERROR weapon has no class')", "0x4aedaf -> rec+0x5c (0x4a306e); 0x4b3d34; 0x4b5582"),
          F("sub", I32, "index within class; >= 100 = turret variant (mount location forced to 3)", "0x4aee01 -> rec+0x58; 0x4aec8a"),
          F("lod", Arr(F32, 5), "never read (LOD distances by shape)", "no GDFC loader reads 24..43", unused=True),
          F("damage", I32, "per-hit damage; x difficulty, split over the ORDF damage-type bits at impact", "0x4aed77 -> rec+0x60 -> inst+0x10 -> proj+0x44; impact 0x4a774d"),
          F("hp", I32, "weapon hit points (current/max)", "0x4aed7e -> rec+0x64 -> inst+0xc/+0x14"),
          F("mass", F32, "mass added to the vehicle", "0x4af1b7 (classdata+0xa4 +=), 0x4af316"),
          F("icon", Str(12), "garage/inventory bitmap base", "0x4b5503"),
          F("pad68", U8, "never read (0)", "none", unused=True),
          F("flag69", U8, "never read; 1 for the late-game weapons", "none", unused=True),
          F("lifetime", F32, "projectile life in s (lifetime*speed = 500 guns, 1000 missiles)", "0x4aedfa -> rec+0x68 -> proj+4 (0x4a0af0)"),
          F("burst_cooldown", F32, "delay after a burst", "0x4aed8c -> rec+0x6c; 0x4a6665"),
          F("fire_rate", F32, "shots per second (interval = 1/rate)", "0x4aed9a -> rec+0x70; 0x4a6659, 0x4a68dd"),
          F("burst_count", I32, "shots per burst", "0x4aee11 -> rec+0x78; 0x4a689d"),
          F("eject", F32, "dropper eject parameter (inferred)", "0x4aedd2 -> rec+0x74; 0x49ffc0"),
          F("ordnance_id", I32, "ordnance table key (= ORDF id)", "0x4aedbd -> rec+0x80; 0x4a667c"),
          F("ammo", I32, "ammo capacity; live counter decremented at 0x4a6f64", "0x4aeda8 -> rec+0x7c -> inst+0x20 (0x4a53ab)"),
          F("spread", F32, "spread, degrees", "0x4aee1f -> rec+0x84; 0x4a7078"),
          F("muzzle_xdf", Str(13), "muzzle flash .xdf", "0x4aef5f -> 0x4b8c40"),
          F("fire_sound", Str(13), "fire sound .wav ('null' = none)", "0x4aeeee -> rec+0x90; 0x4a6ed8"),
          F("sound_mode", I32, "1 = looped/continuous fire sound path (0x423230), 0 = one-shot (0x4231f0)", "0x4aeed6 -> rec+0xa0; 0x4a6ec9"),
          F("select_on", Str(16), "weapon-select on sound", "0x4aee53 -> rec+0xa8"),
          F("select_off", Str(16), "weapon-select off sound", "0x4aede7 -> rec+0xbd"))
POF = St("pof", F("rotation", MAT3, "muzzle rotation", "0x4af438.."), F("pos", VEC3, "muzzle position", "0x4af438.."))
GPOF = St("GPOF", F("pof", Arr(POF, 4), "point of fire for mount locations 1 (P), 2 (S), 3 (T), 5 (I); only the active one is read", "gdf_h_GPOF 0x4af3d0 switch 0x4af664"))
ORDF = St("ORDF",
          F("id", I32, "ordnance id", "0x4aef83 -> ord+0 (0x49f7b5)"),
          F("speed", F32, "muzzle speed", "0x4aef8a -> ord+0x34 -> proj+0x38 (0x4a0afc)"),
          F("gravity", F32, "gravity scale (x -9.8)", "0x4aef98 -> ord+0x38; 0x4a7468"),
          F("damage_mask", I32, "damage types: 1 bullet, 2 explosive, 4 fire, 8 blox (damage split evenly over set bits)", "0x4aefbe -> ord+0x68; 0x4a775b..0x4a7797"),
          F("tracer", I32, "tracer parameter (MGs only)", "0x4aefb0 -> ord+0x64; 0x4a01e0 -> 0x441d10"),
          F("xdf_a", Str(13), "stored at ord+0x58, no reader ('null' in all)", "0x4af18c"),
          F("impact_xdf_ground", Str(13), "impact effect, surface -1", "0x4af0f1 -> ord+0x70; 0x4a7306"),
          F("impact_wav_ground", Str(13), "impact sound, surface -1", "0x4aefc7 -> ord+0x78; 0x4a7325"),
          F("impact_xdf_car", Str(13), "impact effect, surfaces 1/4/8/9", "0x4af126 -> ord+0x88; 0x4a71fc"),
          F("impact_wav_car", Str(13), "impact sound, surfaces 1/4/8/9", "0x4af024 -> ord+0x90; 0x4a721f"),
          F("impact_xdf_bldg", Str(13), "impact effect, surfaces 2/0xC", "0x4af148 -> ord+0xa0; 0x4a7257"),
          F("impact_wav_bldg", Str(13), "impact sound, surfaces 2/0xC", "0x4af06e -> ord+0xa8; 0x4a727a"),
          F("impact_xdf_other", Str(13), "impact effect, surfaces 3/0xB", "0x4af16a -> ord+0xb8; 0x4a72b2"),
          F("impact_wav_other", Str(13), "impact sound, surfaces 3/0xB", "0x4af0b8 -> ord+0xc0; 0x4a72d1"))
register("gdf", "", "GDFC", L(GDFC))
register("gdf", "", "GPOF", L(GPOF))
register("gdf", "", "ORDF", L(ORDF))
register("gdf", "", "GGEO", grouped(12, {0, 3, 6, 9}, "u32 count + 12 groups (4 mount locations P/S/T/I x 3 LODs) of count parts; gdf_h_GGEO 0x4af680"))
register("gdf", "", "OGEO", grouped(1, {0}, "u32 count + count projectile-model parts; gdf_h_OGEO 0x4af890"))

# ---- .wdf wheel ----------------------------------------------------------------------------------------------
WDFC = St("WDFC",
          F("name", Str(16), "display name", "0x4ae92c strncpy"),
          F("flag16", U32, "never read (1 for truck/tank wheels)", "none", unused=True),
          F("lod", Arr(F32, 4), "never read (LOD distances by shape)", "none", unused=True),
          F("f36", F32, "never read (100000)", "none", unused=True),
          F("hp", I32, "wheel hit points", "0x4ae8c0..0x4ae8e1 -> [obj+0x70]+4/+8; 0x4ae93c"),
          F("mass", F32, "mass per wheel (vehicle += 2*m)", "0x4ae8ec..0x4ae8fc; 0x4ae96d"),
          F("size", F32, "size factor 1.0/1.2/1.4/1.6 for 13-16 in (use inferred)", "0x4ae8cf -> [obj+0x70]+0xc"),
          F("icon", Str(14), "icon base", "0x4ae93f..0x4ae96b"))
register("wdf", "", "WDFC", L(WDFC))
register("wdf", "", "WGEO", grouped(16, {0, 8}, "u32 count + 16 groups: right wheel [0..7], left [8..15], each LOD 1..4 x variant 1/A; wdf_h_WGEO 0x4ae980"))

# ---- .xdf explosion ------------------------------------------------------------------------------------------
XDFC = St("XDFC",
          F("anim", I32, "animation parameter (frames/rate, inferred)", "0x4b8ca4 -> 0x49ecbf"),
          F("lod", Arr(F32, 5), "never read", "none", unused=True),
          F("duration", F32, "seconds", "0x4b8ca8 -> 0x49ec31"),
          F("blast_damage", F32, "area damage (0 = none)", "0x4b8cd7 -> 0x49ecdf -> 0x435120"),
          F("blast_radius", F32, "area damage radius", "0x4b8cd3 -> 0x49ecef"),
          F("f36", I32, "never read (looks like a damage mask)", "none", unused=True))
register("xdf", "", "XDFC", L(XDFC))
register("xdf", "", "XGEO", grouped(3, {0}, "u32 count + 3 LOD groups; record 0's name is the effect handle; xdf_h_XGEO 0x4b8e20"))

# ---- .vtf texture set ----------------------------------------------------------------------------------------
SIDES = ("ft", "bk", "rt", "lf", "tp", "un")


def tgroup(prefix, cite, unused=False):
    return [F("%s_%s" % (prefix, s), Str(13), "%s %s TMT" % (prefix, s.upper()), cite, unused) for s in SIDES]


VTFC_FIELDS = [F("vdf", Str(13), "vdf name: never read", "none", unused=True),
               F("scheme", Str(16), "paint scheme name (15 chars used)", "0x4b0329 strncpy 15")]
for lod, base in (("v1", "0x4af92a"), ("v3", "0x4afa2b"), ("v5", "0x4afb0e")):
    for grp in ("ft", "md", "bk", "tp"):
        VTFC_FIELDS += tgroup("%s_%s" % (lod, grp), "vtf_h_VTFC 0x4af8f0 (%s group)" % lod)
    ro = lod != "v1"
    VTFC_FIELDS += [F("%s_fb" % lod, Str(13), "front bumper TMT" + (" (never read; V1 slot used for all LODs)" if ro else ""), "0x4b0005" if not ro else "none", ro),
                    F("%s_bb" % lod, Str(13), "back bumper TMT" + (" (never read)" if ro else ""), "0x4b0056" if not ro else "none", ro)]
VTFC_FIELDS += [F("extra_maps", Arr(Str(13), 12), "extra maps for flagged objects", "0x4b00ab -> 0x4b0290"),
                F("body_map", Str(13), "body map replacing 'V1 BO DY.map'", "0x4b00e5, 0x4b0123")]
VTFC = Struct("VTFC", VTFC_FIELDS)
register("vtf", "", "VTFC", L(VTFC))

try:
    import l_vcf  # noqa: F401  vcf/vsf/cdf layouts
except ImportError:
    pass
