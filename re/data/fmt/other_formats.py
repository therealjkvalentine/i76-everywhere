"""other_formats.py - every non-BWD2 game-data format, as schema layouts, registered with formats.py.

Citations for consumers of these formats are added in FORMATS.md as they are traced; fields without an exe
citation are `typed` (named from structure + corpus statistics + prior art), never `cited`.
"""
import os, struct
import formats
from formats import Handler
import schema
from schema import Struct, Field, Arr, U8, U16, U32, I32, F32, Str, Raw, Cond, parse_exact

EMPTY_COV = {"cited": 0, "typed": 0, "unused": 0, "unknown": 0}


def S(name, *fields):
    return Struct(name, [Field(*f) for f in fields])


def schema_handler(name, typ, method, cite_all=None):
    def dec(data, ext):
        return parse_exact(typ, data)

    def enc(v):
        return typ.emit(v, {})

    def cov(v):
        c = schema.coverage(typ, v)
        return c, {name: c}
    return Handler(name, dec, enc, cov, method=method)


VEC3 = S("vec3", ("x", F32, "x"), ("y", F32, "y"), ("z", F32, "z"))

# ---- .geo mesh (inside .pak): geo_Parse 0x446c90 (caller geo_Acquire 0x4469a0), data\notes\art.md ----------------
def Fc(name, typ, meaning="", cite="", unused=False):
    return Field(name, typ, meaning, cite, unused)


GEO_VREF = Struct("geo_vref", [Fc("vertex", U32, "vertex index", "0x447107"), Fc("normal", U32, "normal index", "0x447110"),
                               Fc("u", F32, "texture u", "0x447115"), Fc("v", F32, "texture v", "0x44711b")])
GEO_FACE = Struct("geo_face", [
    Fc("bsp_node", U32, "BSP node id (permutation of face numbers); never read", "geo_Parse 0x446c90 skips it", True),
    Fc("n_verts", U32, "corner count", "0x446f1a"),
    Fc("rgb", Raw(3), "flat colour r,g,b (nearest palette index via 0x4796a0)", "0x446f20..0x446f49"),
    Fc("plane", Arr(F32, 4), "plane nx,ny,nz,d with n.x + d = 0", "0x447182..0x447197"),
    Fc("zero", U32, "always 0; never read", "0x446c90", True),
    Fc("shading", U8, "surf0: mode-table row (1/2 wireframe, 3/4 textured unlit, 5 textured + .lum shaded, 0 flat)", "0x446f4c; table 0x4f71b8"),
    Fc("tex_opts", U8, "surf1: bit0 perspective-correct, bit1 UV wrap, bit2 colour key 0xFF", "0x446f52; 0x47c7b5, 0x47c6b0, 0x480557"),
    Fc("translucent", U8, "surf2: nonzero = translucent through .tbl (mode |= 0x80)", "0x446f58; 0x45ce8d"),
    Fc("texture", Str(13), "texture name ('' flat; no '.' -> .tmt if present else .map)", "0x446f64, 0x446f75, 0x44707f..0x447093"),
    Fc("bsp_parent", U32, "BSP parent node (-1 root); never read (engine rebuilds its own tree 0x45cbe0)", "0x446c90", True),
    Fc("bsp_side", U32, "1 front / 0 back of parent plane; never read", "0x446c90", True),
    Fc("vrefs", Arr(GEO_VREF, "n_verts"), "polygon corners", "0x447107..0x44711b")])
GEO = Struct("GEO", [
    Fc("magic", Raw(4), "'OEG.' (0x2e47454f)", "0x446c9b"),
    Fc("hdr_word4", U32, "0..115 or -1, no correlation found; never read", "0x446c90", True),
    Fc("name", Str(16), "mesh name (= file stem); never read, the cache keys on the file name", "0x446c90", True),
    Fc("n_verts", U32, "vertex (and normal) count", "0x446cad, 0x446e61"),
    Fc("n_faces", U32, "face count", "0x446cb0, 0x446efe"),
    Fc("hdr_word20", U32, "always 0; never read", "0x446c90", True),
    Fc("verts", Arr(VEC3, "n_verts"), "vertex positions", "0x446e99..0x446eb3"),
    Fc("normals", Arr(VEC3, "n_verts"), "vertex normals (lit by 0x478430)", "0x446ed6..0x446ef0"),
    Fc("faces", Arr(GEO_FACE, "n_faces"), "polygons, stored in BSP pre-order", "0x4471aa..0x4471b5"),
    Fc("unk_tail", Raw(), "bytes after the last face (none in the corpus)")])

# ---- images: tex_Acquire 0x4474b0, vqm_Decode 0x44b430, m16_Acquire 0x471980 --------------------------------
MAP = Struct("MAP", [Fc("w", U32, "width", "0x42cd75, 0x42ee46"), Fc("h", U32, "height (bits 29-31 are in-memory flags)", "0x471a32, 0x42cd67"),
                     Fc("pixels", Raw(), "w*h palette indices, 0xFF = colour key", "span 0x480557")])
VQM = Struct("VQM", [Fc("w", U32, "width", "0x44b437"), Fc("h", U32, "height", "0x44b45d"),
                     Fc("cbk", Str(12), "codebook .cbk (C string; may fill all 12)", "0x447635"),
                     Fc("w_residue", U32, "never read; = w & ~3, low byte zeroed by the authoring tool's NUL for 12-char names", "0x4474b0/0x44b430", True),
                     Fc("blocks", Raw(), "u16 per 4x4 block: bit15 = solid (low byte), else codebook tile index", "0x44b4ba..0x44b4ec")])
CBK = Struct("CBK", [Fc("n", U32, "tile count; never read (no bounds check)", "0x44b430", True),
                     Fc("tiles", Raw(), "n x 16 bytes: 4x4 row-major palette indices", "0x44b4e8")])
ACT = Struct("ACT", [Fc("rgb", Raw(768), "256 x (r,g,b) palette", "wrld_h_Load 0x4b8a94 -> 0x4fa170; order proven 0x42d970..0x42d983")])
LUM = Struct("LUM", [Fc("table", Raw(65536), "shade table [level][colour] -> colour", "0x479242 -> 0x61b2a0; index 0x47cc49/0x47cc55")])
TBL = Struct("TBL", [Fc("table", Raw(65536), "translucency [src texel][dst pixel] -> pixel (row 0xFF forced identity)", "0x4b8ae4 -> 0x60afa0; 0x47a4cf..0x47a4da")])
LUT256 = LUM
TAB = Struct("TAB", [Fc("table", Raw(131072), "65536 x u16: RGB565 -> RGB565 per-mission colour grade for 16-bit palettes (used only if exactly 0x20000 B)", "0x42da44..0x42da7e; applied 0x42ef5a")])
TMT = Struct("TMT", [
    Fc("w0", U32, "always 1; never read", "tmt_Parse 0x44ab90", True),
    Fc("scratch", Raw(16), "overwritten with the texture name at load; file bytes never read", "0x44a45c..0x44a463", True),
    Fc("n_dims", U32, "animation dimension count", "0x44abae"),
    Fc("dims", Arr(U32, 4), "dimension sizes (first n_dims used, read last-fastest)", "0x44abc0..0x44abcf"),
    Fc("rate", F32, "frames per second", "0x44ab98; 0x44a597"),
    Fc("flags", U32, "bit0 auto-animate, bit1 looping driver", "0x44aba8; 0x44a58f"),
    Fc("pad", Raw(16), "never read", "0x44ab90", True),
    Fc("frames", Arr(Str(8), None), "8-char frame names (+.map); count = product of dims", "0x44ac17..0x44ac2a")])
MSK = Struct("MSK", [Field("runs", Arr(U16, lambda c: (c["_end"]) // 2), "zoom-view screen mask: u16 runs, low 15 bits length, bit 15 masked; sums to W*H", "zoom_BuildScreenMask 0x4621e0: 0x4622c9, 0x4622de"),
                     Field("tail", Raw(), "odd trailing byte: the run list fills the buffer first, never affects output", "0x4621e0", True)])

def _m16_parse(data):
    w, hf = struct.unpack_from("<II", data)
    h = hf & 0x7FFFFFFF
    p = 8 + w * h
    if hf & 0x80000000:
        n = struct.unpack_from("<I", data, p)[0]
        pal = data[p + 4:p + 4 + 2 * n]
        if len(pal) != 2 * n:
            raise ValueError("m16 palette short")
        tail = data[p + 4 + 2 * n:]
    else:
        n, pal, tail = None, b"", data[p:]
    return {"w": w, "h_flags": hf, "pixels": data[8:p], "n_colours": n, "palette565": pal, "unk_tail": tail}


def _m16_emit(v):
    out = struct.pack("<II", v["w"], v["h_flags"]) + v["pixels"]
    if v["n_colours"] is not None:
        out += struct.pack("<I", v["n_colours"]) + v["palette565"]
    return out + v["unk_tail"]


def _m16_cov(v):
    c = dict(EMPTY_COV)
    c["cited"] = 8 + len(v["pixels"]) + (4 + len(v["palette565"]) if v["n_colours"] is not None else 0)  # m16_Acquire 0x471980, tex_GetPalette16 0x42cd60, 0x42ef20
    c["unknown"] = len(v["unk_tail"])
    return c, {"m16": c}


M16_H = Handler("m16", lambda d, e: _m16_parse(d), _m16_emit, _m16_cov,
                method="w, h|0x80000000, w*h u8 indices, u32 n, n x u16 RGB565 palette (flag set in every corpus file)")

# ---- Smacker video (RAD SMK2; decoded by SMACKW32.DLL, not by i76.exe) ------------------------------------------
SMK_HDR = S("SMK_HDR", ("sig", Raw(4), "'SMK2'"), ("width", U32, "640"), ("height", U32, "480"), ("frames", U32, "frame count"),
            ("frame_rate", I32, "RAD frame rate (ms if >0, 1/100 ms if <0)"), ("flags", U32, "ring frame / y-interlace / y-double"),
            ("audio_size", Arr(U32, 7), "largest audio chunk per track"), ("trees_size", U32, "huffman tree block size"),
            ("mmap_size", U32, "tree size"), ("mclr_size", U32, "tree size"), ("full_size", U32, "tree size"), ("type_size", U32, "tree size"),
            ("audio_rate", Arr(U32, 7), "per-track rate and flags"), ("dummy", U32, "reserved"))


def _smk_parse(data):
    h = parse_exact(SMK_HDR, data[:104])
    n = h["frames"] + (1 if h["flags"] & 1 else 0)
    sizes = list(struct.unpack_from("<%dI" % n, data, 104))
    types = data[104 + 4 * n:104 + 5 * n]
    return {"hdr": h, "sizes": sizes, "types": types, "rest": data[104 + 5 * n:]}


def _smk_emit(v):
    return SMK_HDR.emit(v["hdr"], {}) + struct.pack("<%dI" % len(v["sizes"]), *v["sizes"]) + v["types"] + v["rest"]


def _smk_cov(v):
    n = 104 + 5 * len(v["sizes"]) + len(v["rest"])
    c = {"cited": 0, "typed": n, "unused": 0, "unknown": 0}
    return c, {"smk": c}


SMK_H = Handler("smk", lambda d, e: _smk_parse(d), _smk_emit, _smk_cov,
                method="RAD Smacker 2 header + frame size/type tables parsed; trees and frames are RAD's codec (SMACKW32.DLL)")

# ---- RIFF (wav) and GAS0 (gpw) -------------------------------------------------------------------------------


def _riff_parse(data):
    if data[:4] not in (b"RIFF",):
        raise ValueError("not RIFF")
    return {"riff": data}


def _wav_cov(v):
    d = v["riff"] if isinstance(v, dict) else v
    c = {"cited": len(d), "typed": 0, "unused": 0, "unknown": 0}  # snd_LoadSample 0x425130 (no .gpw -> plain .wav), RIFF walk 0x425573
    return c, {"wav": c}


WAV_H = Handler("wav", lambda d, e: _riff_parse(d), lambda v: v["riff"], _wav_cov, method="standard RIFF WAVE PCM (8-bit mono 11025 Hz); identity")
GPW = Struct("GPW", [
    Field("magic", Raw(4), "'GAS0'", "snd_LoadSample 0x425288"),
    Field("priority", I32, "voice-stealing priority (-1 = 50; player vehicle +20)", "-> obj+0x34; 0x421fcc, 0x4228aa"),
    Field("max_instances", I32, "max simultaneous plays of this sample (-1 = 1)", "-> obj+0x38; 0x422884"),
    Field("play_mode", I32, "0 one-shot, 1 loop, 2 loop with one shared instance (-1 = 0)", "-> obj+0x3c; 0x4220e1"),
    Field("volume", I32, "volume percent (-1 = 100)", "-> obj+0x40; 0x4220fd"),
    Field("random_pitch", I32, "nonzero: frequency x 0.80..1.16 (-1 = 0)", "-> obj+0x44; 0x422100"),
    Field("frequency", I32, "overwritten by the WAVE sample rate at load; file value never used", "0x425753", True),
    Field("wav", Raw(), "embedded RIFF WAVE (fmt/data parsed)", "0x425573..0x4255b6")])

# ---- text manifests ----------------------------------------------------------------------------------------


def _text_parse(data):
    lines = data.split(b"\n")
    return {"lines": lines}


def _text_emit(v):
    return b"\n".join(v["lines"])


TEXT_READERS = {
    "hzd": "hzd_Load 0x401540: exactly 16 tokens split on ' ,\t\r\n' into 16-byte slots",
    "rtm": "road_LoadTextureManifest 0x48e1a0: up to 30 names (slots 10/10/5/5 over built-in defaults), 15 chars, blank lines ignored",
    "fsi": "fsi_LoadFitout 0x4b1a20: '#' comments; .wdf/.gdf by extension, eng/sus/bra/spc by prefix",
    "npt": "npt_Load 0x45dea0: <= 6 objectives ('(hidden)' prefix), then '(failure)' + <= 16 failure lines",
    "pcf": "pcf_Preload 0x4026c0: '<type p/t/x/v/a/g> <name>'; the trailing numbers are never parsed",
    "elt": "elt_Load 0x448010: dst/src <map>, label <name> x y w h, '#' comments",
    "dat": "engsnd_Load 0x469b00: sscanf 11 fields per non-# line",
    "zix": "vfs_LoadZix 0x4b23e0: count, volume table, container table, 'index name' lines",
    "lst": "fullres.lst: tex_ApplyFullResFlag 0x471840 (hashed name set); internet.lst is shell-only",
}


def text_handler(name, meaning):
    reader = TEXT_READERS.get(name)

    def cov(v):
        n = len(_text_emit(v))
        c = {"cited": n if reader else 0, "typed": 0 if reader else n, "unused": 0, "unknown": 0}
        if name == "pcf":  # only the first two tokens of a line are read (txt_ReadTypedName 0x402630)
            used = 0
            for ln in v["lines"]:
                t = ln.split(b" ")
                used += len(b" ".join(t[:2])) + 1
            used = min(used, n)
            c = {"cited": used, "typed": 0, "unused": n - used, "unknown": 0}
        return c, {name: c}
    return Handler(name, lambda d, e: _text_parse(d), _text_emit, cov, method="text: " + (reader or meaning))


# ---- .pix index + .pak container ---------------------------------------------------------------------------
MEMBER = {".geo": GEO, ".map": MAP, ".vqm": VQM, ".tmt": TMT}


def _pix_parse(data):
    lines = data.split(b"\r\n")
    n = int(lines[0])
    ents = []
    for ln in lines[1:1 + n]:
        name, off, size = ln.split(b" ")
        ents.append((name.decode("latin1"), int(off), int(size)))
    v = {"n": n, "entries": ents, "raw": data}
    if _pix_emit(v, fresh=True) != data:
        v["fresh_ok"] = False
    return v


def _pix_emit(v, fresh=False):
    if not fresh and v.get("fresh_ok") is False:
        return v["raw"]
    s = b"%d\r\n" % v["n"] + b"".join(b"%s %d %d\r\n" % (n.encode("latin1"), o, z) for n, o, z in v["entries"])
    return s


def _pix_cov(v):
    n = len(v["raw"])  # vfs pak index reader 0x470660: sscanf "%d" 0x470949, "%s %d %d" 0x4709c6, _strlwr 0x4709ea, qsort 0x470aa9
    c = {"cited": n, "typed": 0, "unused": 0, "unknown": 0}
    return c, {"pix": c}


PIX_H = Handler("pix", lambda d, e: _pix_parse(d), _pix_emit, _pix_cov, method="text: count, then 'NAME.EXT offset size' per member of the sibling .pak (reader 0x470660: sscanf '%d' then '%s %d %d', names lowercased, qsorted)")


def _member_parse(name, data):
    ext = os.path.splitext(name)[1].lower()
    if ext == ".m16":
        return ("m16", _m16_parse(data))
    t = MEMBER.get(ext)
    if t is None:
        return ("raw", data)
    try:
        return (ext, parse_exact(t, data))
    except Exception:  # noqa: BLE001
        return ("raw", data)


def _member_emit(m):
    kind, v = m
    if kind == "raw":
        return v
    if kind == "m16":
        return _m16_emit(v)
    return MEMBER[kind].emit(v, {})


def _member_cov(m):
    kind, v = m
    if kind == "raw":
        return {"cited": 0, "typed": 0, "unused": 0, "unknown": len(v)}
    if kind == "m16":
        return _m16_cov(v)[0]
    return schema.coverage(MEMBER[kind], v)


def pak_handler(path):
    pix = os.path.splitext(path)[0] + ".pix"
    if not os.path.exists(pix):
        return None

    def dec(data, ext):
        ents = _pix_parse(open(pix, "rb").read())["entries"]
        members, p = [], 0
        for name, off, size in ents:
            if off != p:
                raise ValueError("pak member %s at %d, expected %d" % (name, off, p))
            members.append((name, _member_parse(name, data[off:off + size])))
            p = off + size
        return {"members": members, "tail": data[p:]}

    def enc(v):
        return b"".join(_member_emit(m) for _, m in v["members"]) + v["tail"]

    def cov(v):
        c = dict(EMPTY_COV); per = {}
        for name, m in v["members"]:
            ext = "pak/" + os.path.splitext(name)[1].lower()
            mc = _member_cov(m)
            d = per.setdefault(ext, dict(EMPTY_COV))
            for k, n in mc.items():
                c[k] += n; d[k] += n
        c["unknown"] += len(v["tail"])
        return c, per

    def errs(v):
        return []
    return Handler("pak", dec, enc, cov, errs, method="members split by the sibling .pix; each member decoded by its extension")


# ---- MW2 database -----------------------------------------------------------------------------------------


import mw2db  # noqa: E402

MW2_H = Handler("mw2", lambda d, e: mw2db.parse(d), mw2db.serialise, mw2db.coverage,
                method="mw2db.py: u32 count + offsets; members decoded to values and re-encoded (LZSS-packed PCX backgrounds, "
                       "'1.10' shape tables, '1.' fonts; WAV and credits text held whole); consumer i76shell.dll TMPackDataBaseObj")

# ---- PCX -----------------------------------------------------------------------------------------------------
PCX = S("PCX", ("header", Raw(128), "ZSoft PCX v5 header"), ("rle", Raw(), "RLE image data + 0x0C + 768-byte palette"))

# ---- fonts / FFB / terrain via i76fmt (typed, round trip by i76fmt) -------------------------------------------
import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
from i76fmt import fnt as _fnt, frc as _frc  # noqa: E402


def lib_handler(name, mod, method):
    def cov(v):
        n = len(mod.serialise(v))
        c = {"cited": 0, "typed": n, "unused": 0, "unknown": 0}
        return c, {name: c}
    return Handler(name, lambda d, e: mod.parse(d), mod.serialise, cov, method=method)


TER = Struct("TER", [Field("tiles", Arr(Raw(32768), None),
    "N tiles (ZMAP zone_count) of 128x128 u16, row-major, 5 world units per sample: bits 0-11 height x 0.1 m, bit 12 AI no-go, bits 13-15 surface type 0-7 (indexes WRLD surfaces[], skid/dust sounds 0x4bd0d0, AI path cost 0x40e9d0)",
    "zone ptr = base + i*0x8000 (0x493b9d); height 0x4931a8 / bilinear 0x493550 x0.1 (0x4937a9); flag 0x492764; type 0x492881")])

# ---- registration ---------------------------------------------------------------------------------------------
REG = {
    ".geo": schema_handler("geo", GEO, "Open76 GeoParser layout, verified by exact consumption"),
    ".map": schema_handler("map", MAP, "u32 w, u32 h, w*h indices"),
    ".vqm": schema_handler("vqm", VQM, "u32 w, u32 h, cbk[12], u32, u16 per 4x4 block"),
    ".cbk": schema_handler("cbk", CBK, "u32 n, n*16 tile bytes"),
    ".act": schema_handler("act", ACT, "768-byte RGB palette"),
    ".lum": schema_handler("lum", LUM, "256x256 shade table [level][colour]"),
    ".tbl": schema_handler("tbl", TBL, "256x256 translucency [src][dst]"),
    ".tab": schema_handler("tab", TAB, "65536 x u16 RGB565 colour grade"),
    ".tmt": schema_handler("tmt", TMT, "64-byte header + 8-char frame names"),
    ".msk": schema_handler("msk", MSK, "u16 list"),
    ".gpw": schema_handler("gpw", GPW, "GAS0 + 6 i32 + RIFF WAVE"),
    ".pcx": schema_handler("pcx", PCX, "ZSoft PCX"),
    ".ter": schema_handler("ter", TER, "N x 32 KiB tiles"),
    ".m16": M16_H,
    ".smk": SMK_H,
    ".wav": WAV_H,
    ".pix": PIX_H,
    ".mw2": MW2_H,
    ".fnt": lib_handler("fnt", _fnt, "i76fmt.fnt: '1.' fonts"),
    ".frc": lib_handler("frc", _frc, "i76fmt.frc: RIFF FORC force-feedback effects"),
}
for ext, meaning in ((".hzd", "horizon strip list"), (".rtm", "road texture manifest"), (".fsi", "mission-start fit-out"),
                     (".npt", "objective text"), (".pcf", "per-mission preload list"), (".elt", "cockpit HUD element layout"),
                     (".dat", "engine sound table"), (".zix", "archive name index"), (".lst", "list"), (".def", "definitions"),
                     (".map_text", "input bindings")):
    REG[ext] = text_handler(ext.lstrip("."), meaning)
for ext, h in REG.items():
    formats.register(ext, h)

_orig = formats.handler_for


def handler_for(ext, path=None):
    if ext == ".pak" and path:
        h = pak_handler(path)
        if h:
            return h
    if ext == ".map" and path:
        with open(path, "rb") as fh:
            head = fh.read(8)
        if len(head) == 8:
            w, h = struct.unpack("<II", head)
            if 8 + w * h != os.path.getsize(path):
                return REG[".map_text"]
    if ext in (".lst", ".def") and path:
        pass
    return _orig(ext, path)


formats.handler_for = handler_for
