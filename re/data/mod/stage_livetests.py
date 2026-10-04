#!/usr/bin/env python3
r"""stage_livetests.py - build every LIVE-TESTS.md test's files into data\out\livetests\<T>\ with a manifest.

    python data\mod\stage_livetests.py

Nothing is installed anywhere: each manifest.json lists (file, md5, install target relative to the TEST COPY
game folder i76-uncap-lab\game, the pristine file it replaces and that file's md5 for the rollback check),
the prediction, and the memory reads. The console owner installs, runs, and restores.
"""
import os, sys, json, hashlib, struct, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
MAP = os.path.dirname(DATA)
sys.path.insert(0, os.path.join(DATA, "fmt"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(MAP, "tools"))
import bwd2x, fsm, schema  # noqa: E402
import zfspatch  # noqa: E402
from i76fmt import zfs  # noqa: E402

APP = os.path.join(MAP, "sandbox-gog", "main", "app")   # pristine source of every edit
TEST = r"C:\Users\james\i76-uncap-lab\game"             # install target; read here only for rollback md5s
OUT = os.path.join(DATA, "out", "livetests")
md5 = lambda b: hashlib.md5(b).hexdigest()


def edit(data, ext, edits):
    doc = bwd2x.decode(data, ext)
    for chunk, field, val in edits:
        par, tag = chunk.split("/") if "/" in chunk else (None, chunk)
        idx = 0
        if "#" in tag:
            tag, i = tag.split("#"); idx = int(i)
        hits = bwd2x.chunks(doc, tag, par)
        schema.put(hits[idx][2].value, field, val)
    out = bwd2x.encode(doc)
    back = bwd2x.decode(out, ext)
    for chunk, field, val in edits:
        par, tag = chunk.split("/") if "/" in chunk else (None, chunk)
        idx = 0
        if "#" in tag:
            tag, i = tag.split("#"); idx = int(i)
        got = schema.get(bwd2x.chunks(back, tag, par)[idx][2].value, field)
        assert (abs(float(got) - float(val)) < 1e-6) if isinstance(val, float) else (str(got) == str(val)), (chunk, field, got, val)
    return out


def write(test, name, data, target, replaces=None, **manifest):
    d = os.path.join(OUT, test)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    open(p, "wb").write(data)
    assert open(p, "rb").read() == data
    mf = os.path.join(d, "manifest.json")
    m = json.load(open(mf)) if os.path.exists(mf) else {"test": test, "files": []}
    ent = {"file": name, "md5": md5(data), "install_to": target}
    tp = os.path.join(TEST, target)
    ent["replaces_in_test_copy"] = {"path": target, "md5": md5(open(tp, "rb").read()) if os.path.exists(tp) else None,
                                    "note": "back this file up before installing; restore it after the run"}
    m["files"].append(ent)
    m.update(manifest)
    json.dump(m, open(mf, "w"), indent=1)


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    raw_zfs = open(os.path.join(APP, "I76.ZFS"), "rb").read()
    z = zfs.parse(raw_zfs)
    arc = {e.name.lower(): e for e in z.entries}
    zread = lambda n: z.read(arc[n])

    # T1 armour chain, sentinel values on the melee car the capture-012 path loads
    # valepre4.vcf is the shell-written player car (not in the archive); build from the user's pre-mod original,
    # read (never written) from the test copy
    src_path = os.path.join(TEST, "ADDON", "valepre4.orig")
    src = open(src_path, "rb").read()
    a = [611, 622, 633, 644]; c = [655, 666, 677, 688]
    out = edit(src, ".vcf", [("VCFC", "armour[%d]" % i, a[i]) for i in range(4)] + [("VCFC", "chassis[%d]" % i, c[i]) for i in range(4)])
    write("T1-armour-chain", "valepre4.vcf", out, "ADDON\\valepre4.vcf", "ADDON/valepre4.vcf",
          source={"path": src_path, "md5": md5(src)}, prediction="single player: veh+0x138 = [1222,1244,1266,1288], +0x148 = [1310,1332,1354,1376]; +0x158/+0x168 equal those; "
                     "+0x178/+0x18c equal them too (capture 012 pattern). Any other factor refutes 'copy x1 then 0x463120 doubles'.")

    # T3 total mass of the same car (unchanged file; the prediction comes from the chain)
    sys.path.insert(0, os.path.join(DATA, "fmt"))
    import vehicle_sheet  # noqa: F401 (documents the formula)

    # T4 far clip + T5 hour of day + T6 script injection, all on T01 (enter-trip1.ps1 route)
    t01 = open(os.path.join(APP, "miss16", "T01.MSN"), "rb").read()
    out = edit(t01, ".msn", [("WDEF/WRLD", "far_clip", 1200)])
    for d in ("miss16", "miss8"):
        write("T4-far-clip", "T01.MSN", out, d + "\\T01.MSN", d + "/T01.MSN",
              prediction="after T01 loads: f32 [0x4c271c] == 1200.0 (stock 600.0). With the detail option that sets 0x654b8a, "
                         "the camera far plane (camera +0x10) is 1200; without it 150. Visible draw distance doubles.")
    doc = bwd2x.decode(t01, ".msn")
    hour0 = bwd2x.chunks(doc, "WRLD")[0][2].value["hour_of_day"]
    out = edit(t01, ".msn", [("WDEF/WRLD", "hour_of_day", 21)])
    for d in ("miss16", "miss8"):
        write("T5-hour", "T01.MSN", out, d + "\\T01.MSN", d + "/T01.MSN",
              prediction="stock hour %d; with 21: i32 [0x58db00] == 7 ((21+2)%%24*8//24), night sky, headlight LOBJ lights appear" % hour0)
    # T6: successAll 0 injected at the start of machine 0
    fdoc = bwd2x.decode(t01, ".msn")
    info = bwd2x.chunks(fdoc, "FSM")[0][2]
    text = fsm.disassemble(info.value, "T01")
    lines = text.splitlines()
    k = lines.index("m0:")
    # at machine entry SP = BP+1, so a pushed temporary is BP[1]; SP is restored before the original code runs
    inject = ["  push 0", "  arga 1", "  action successAll", "  drop 1"]
    lines = lines[:k + 1] + inject + lines[k + 1:]
    info.value = fsm.assemble("\n".join(lines))
    out = bwd2x.encode(fdoc)
    os.makedirs(os.path.join(OUT, "T6-fsm-inject"), exist_ok=True)
    open(os.path.join(OUT, "T6-fsm-inject", "T01.fsm"), "w", encoding="latin1").write("\n".join(lines) + "\n")
    for d in ("miss16", "miss8"):
        write("T6-fsm-inject", "T01.MSN", out, d + "\\T01.MSN", d + "/T01.MSN",
              prediction="within ~1 s of T01 starting: i32 [0x5244e4] == 1 and the mission ends as won (fsm_RunMachines 0x4149f0 -> game_SetState). "
                         "Control: stock T01 keeps [0x5244e4] == 0 for 60 s.")

    # T7 ammo through the archive (hybrid stored-mode repack) and T8 loose-over-archive precedence
    g = zread("gmmedium.gdf")
    g7 = edit(g, ".gdf", [("GDFC", "ammo", 1234)])
    new = zfspatch.patch(raw_zfs, {"gmmedium.gdf": g7})
    bad, n = zfspatch.verify(new, {"gmmedium.gdf": g7}, raw_zfs)
    assert not bad
    write("T7-ammo-archive", "I76.ZFS", new, "I76.ZFS", "I76.ZFS",
          prediction="a car carrying gmmedium.gdf (e.g. Jade's car weapon 2 '50cal MG' if equipped) starts with 1234 rounds: weapon instance "
                     "+0x20 (table 0x5aab08 stride 0x4c) == 1234 and the HUD ammo counter shows 1234. Stock ammo %d." %
                     schema.get(bwd2x.chunks(bwd2x.decode(g, ".gdf"), "GDFC")[0][2].value, "ammo"))
    g8 = edit(g, ".gdf", [("GDFC", "ammo", 777)])
    write("T8-loose-precedence", "gmmedium.gdf", g8, "ADDON\\gmmedium.gdf",
          prediction="with T7's archive installed AND this loose file in ADDON: ammo 777 (container 0 = addon wins, vfs_LoadZix 0x4b23e0). "
                     "1234 means the archive wins; then loose files only work for names the ZIX lists under container 0.")

    # T9 terrain height: +500 raw (50.0 m) on every sample of t01.ter, loaded from addon\ first (0x4939fd)
    ter = bytearray(open(os.path.join(APP, "miss16", "T01.TER"), "rb").read())
    for i in range(0, len(ter), 2):
        v = struct.unpack_from("<H", ter, i)[0]
        h = min((v & 0xFFF) + 500, 0xFFF)
        struct.pack_into("<H", ter, i, (v & 0xF000) | h)
    write("T9-terrain-height", "t01.ter", bytes(ter), "ADDON\\t01.ter",
          prediction="player Y at the T01 spawn is 50.0 +- 0.2 higher than stock (height = raw x 0.1, terrain_GetHeightBilinear 0x493550); "
                     "samples already above 3595 clip at 409.5 m.")

    # T10 surface grip: every surface's grip x 0.25 on T01
    doc = bwd2x.decode(t01, ".msn")
    s = bwd2x.chunks(doc, "WRLD")[0][2].value["surfaces"]
    ed = [("WDEF/WRLD", "surfaces[%d].grip" % i, float(s[i]["grip"]) * 0.25) for i in range(8)]
    out = edit(t01, ".msn", ed)
    for d in ("miss16", "miss8"):
        write("T10-surface-grip", "T01.MSN", out, d + "\\T01.MSN", d + "/T01.MSN",
              prediction="f32 [0x644220 + 20*i] == stock grip x 0.25 for i=0..7 (stock %s); full throttle from rest spins the wheels: "
                         "0-20 m/s takes clearly longer than the A/A control (n>=3 each), and cornering at 20 m/s slides." %
                         ",".join("%.2f" % float(x["grip"]) for x in s))
    print("staged tests in", OUT)
    for t in sorted(os.listdir(OUT)):
        m = json.load(open(os.path.join(OUT, t, "manifest.json")))
        print(" ", t, [f["file"] + " -> " + f["install_to"] for f in m["files"]])


if __name__ == "__main__":
    main()
