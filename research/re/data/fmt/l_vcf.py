"""l_vcf.py - .vcf vehicle configuration, .vsf vehicle state, compnent.cdf component catalogue.

Citations from data\\notes\\vcf-chain.md. Handler sets: A in-game spawn (table 0x4fef70, loader 0x4ad6f0),
B shell/garage record (0x4fefb0, loader 0x4ad8c0), C multiplayer-join legality check + CRC (0x500050, 0x4b35a0).
"""
from layouts import register, L, S
from schema import U8, U16, U32, I32, F32, Str, Raw, Arr, Struct, Field


def F(name, typ, meaning="", cite="", unused=False):
    return Field(name, typ, meaning, cite, unused)


def St(name, *fields):
    return Struct(name, list(fields))


FACETS = "front, left, right, rear (Open76 order; the exe copies the block whole)"
VCFC = St("VCFC",
          F("variant", Str(16), "variant display name", "B 0x4adbb1 strcpy -> R+0x50"),
          F("vdf", Str(13), "chassis .vdf", "A 0x4ad96b -> LoadDef(0x4feff0); B 0x4adbc7; C 0x4b3853 (+CRC32)"),
          F("vtf", Str(13), "texture set .vtf", "A 0x4ad98e -> LoadDef(0x4ff1d0); B 0x4adc00"),
          F("engine_id", U32, "engine number in engsnd.dat (ENG NUM); its ENG COMP ID picks the ENGN record", "A 0x4ada12; B 0x4add25; engsnd_EngineIdToCompId 0x469f10"),
          F("suspension_id", U32, "SUSP record / STBL row", "A 0x4ada08; B 0x4add2b"),
          F("brake_id", U32, "BRAK record / BTBL row", "A 0x4ada0b; B 0x4add28"),
          F("wdf_front", Str(13), "front wheels .wdf (slot 0)", "A 0x4ad9b0 -> 0x4ae5e0; B 0x4adca2; C 0x4b3696"),
          F("wdf_mid", Str(13), "mid wheels (slot 2), 'null' = none", "A 0x4ad9ce; B 0x4adcc0; C 0x4b3671"),
          F("wdf_rear", Str(13), "rear wheels (slot 4)", "A 0x4ad9ec; B 0x4adcde; C 0x4b372f"),
          F("armour", Arr(U32, 4), "armour points per facet (" + FACETS + "); copied verbatim to veh+0x138, +0x158, +0x178", "A 0x4adac1..0x4adb12; B 0x4adc30; C 0x4b389b"),
          F("chassis", Arr(U32, 4), "chassis points per facet; copied to veh+0x148, +0x168, +0x18c", "A 0x4adb14..0x4adb69; B 0x4adc4a; C 0x4b388f"),
          F("spare", U32, "unallocated points: spare + armour + chassis must equal 1600*size (join check); dead in game", "B 0x4adc70 -> R+0xa9c; C 0x4b3889 (sum seed), check 0x4b3919"))
SPEC = St("SPEC", F("special_id", U32, "1 radar jammer, 2 nitrous, 3 blower, 4 exhaust brake, 5 structo bumper, 6 curb feelers, 7 mud flaps, 8 heated seats, 9 cup holders (Open76 names); max 3", "A 0x4ade85 -> veh_AttachSpecial 0x467280; B 0x4adec4; C 0x4b3a17"))
WEPN = St("WEPN",
          F("hardpoint", U32, "mount index, matched against VDF HLOC index", "A 0x4aebea (scan 0x4aec5f); B 0x4af27f; C 0x4b3abc"),
          F("gdf", Str(13), "weapon .gdf ('null' = empty)", "A 0x4aebed -> LoadDef(0x4ff270); B 0x4af2bf; C 0x4b3aea (+CRC32)"))
register("vcf", "", "VCFC", L(VCFC))
register("vcf", "", "SPEC", L(SPEC))
register("vcf", "", "WEPN", L(WEPN))

# ---- .vsf -----------------------------------------------------------------------------------------------------
VCST = St("VCST",
          F("vcf", Str(13), "vcf this state belongs to (sanity check only)", "0x4b0368 -> _splitpath, 0x4b03a7"),
          F("armour", Arr(U32, 4), "current armour -> veh+0x138 and +0x158", "0x4b0411..0x4b044f"),
          F("chassis", Arr(U32, 4), "current chassis -> veh+0x148 and +0x168", "0x4b0452..0x4b0490"),
          F("velocity", Arr(F32, 3), "velocity (inferred) -> veh+0xbc; |v| -> veh+0xac", "0x4b04af..0x4b04fc"),
          F("f39", F32, "-> obj+0x48 (double)", "0x4b0502/0x4b050e"),
          F("engine_hp", I32, "engine current hit points", "0x4b0497"),
          F("brake_hp", I32, "brake current hit points", "0x4b04a9"),
          F("susp_hp", I32, "suspension current hit points", "0x4b04a0"),
          F("flags", Arr(U8, 3), "three flags (shell reads; in-game never)", "shell_cb_06 0x4b7236..0x4b723e"))
WLST = St("WLST", F("wheel_hp", Arr(I32, 6), "per wheel slot state, -1 = absent (inferred: health)", "0x4b055f..0x4b05d2 -> [wheel+0x70]+4"))
WPST = St("WPST",
          F("hardpoint", I32, "weapon key", "0x4b061a -> weapon_SetState 0x4a34c0"),
          F("state_a", I32, "weapon record +0 (hp or ammo, inferred)", "0x4b0614 -> 0x4a3546"),
          F("state_b", I32, "weapon record +0x14 unless -1", "0x4b0617 -> 0x4a354e"))
register("vsf", "", "VCST", L(VCST))
register("vsf", "", "WLST", L(WLST))
register("vsf", "", "WPST", L(WPST))

# ---- compnent.cdf ---------------------------------------------------------------------------------------------
ENGN = St("ENGN",
          F("max_hp", U32, "engine hit points (current and max)", "0x4b0dca -> engine+0/+4"),
          F("power", F32, "drive power scalar (x 1/mass): engine+0x14", "0x4b0dd5; consumer 0x43c55e"),
          F("mass", F32, "added to vehicle mass veh+0xa4", "0x4b0dea..0x4b0df3"),
          F("internal_name", Str(13), "eng01..: never read", "none", unused=True),
          F("last", U8, "never read (1 on the last record)", "none", unused=True))
BRAK = St("BRAK",
          F("max_hp", U32, "brake hit points", "0x4b0e25 -> brake+4/+8"),
          F("strength", F32, "brake coefficient brake+0xc; effective +0x10 = max(cur/max, 0.2) x it", "0x4b0e31; 0x46a7f0; consumer 0x43c49a"),
          F("mass", F32, "added to veh+0xa4", "0x4b0e3f"),
          F("internal_name", Str(13), "never read", "none", unused=True),
          F("last", U8, "never read", "none", unused=True))
SUSP = St("SUSP",
          F("max_hp", U32, "suspension hit points", "0x4b0d4c -> susp+0/+4"),
          F("handling", F32, "handling coefficient susp+0x14/+0x18 (inferred)", "0x4b0d69; consumer 0x43c7c2"),
          F("percent", F32, "susp+0x1c = (100 - x)/100 (stiffness %, inferred)", "0x4b0d4f..0x4b0d81"),
          F("mass", F32, "added to veh+0xa4", "0x4b0d86"),
          F("internal_name", Str(13), "never read", "none", unused=True),
          F("last", U8, "never read", "none", unused=True))
NAMETBL = St("NAMETBL",
             F("count", U32, "never read (4)", "none", unused=True),
             F("names", Arr(Str(16), 64), "display names by row (engine row = engsnd comp id)", "0x4b0f6f / 0x4b0fa1 / STBL 0x4b0fd0"))
register("cdf", "*", "ENGN", L(ENGN))
register("cdf", "*", "BRAK", L(BRAK))
register("cdf", "*", "SUSP", L(SUSP))
for t in ("NTBL", "BTBL", "STBL"):
    register("cdf", "*", t, L(NAMETBL))
for t in ("ECNK", "BCNK", "SCNK"):
    register("cdf", "*", t, L(S("EMPTY")))
