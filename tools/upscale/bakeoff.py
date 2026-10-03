#!/usr/bin/env python3
"""Model bake-off driver for the I'76 benchmark set (agent U2, plan hypotheses H1 / H4 / H5).

Wraps upscale_run.py (its CLI is unchanged) and score.py; adds what a many-model bake-off needs:

  python bakeoff.py probe                                   # every weight in WORK/models: arch, scale, loadable
  python bakeoff.py run MODEL [MODEL ...] [--prefix u2] [--overscale 4] [--target 2] [--also1x] [--set k=v ...]
        one upscale_run per model (run id <prefix>-<slug>-o<overscale>-t<target>), then score.py on it.
        --also1x derives a native-size (target 1) run from the same 4x intermediates without re-running the
        model (same lanczos RGB / area mask downscale as upscale_run), id ...-t1, and scores it too.
  python bakeoff.py interp A B --w 0.7 [--name NAME]       # state-dict blend w*A + (1-w)*B (same arch only),
        written to WORK/models/interp/NAME.pth (spandrel re-detects it; usable as model=interp/NAME.pth)
  python bakeoff.py rank RUN [RUN ...] [--csv OUT]          # per-class mean lpips/dists/de/lapvar table
  python bakeoff.py sheet RUN [RUN ...] --cls CLASS [--out PNG] [--crop 128] [--zoom 2] [--labels a,b,..]
        per-class contact sheet, columns = original (native) | nearest 2x | each run's final;
        rows = the class's tiles; --crop N shows only the N x N native-px centre crop of large tiles.
  python bakeoff.py abprep --pairs CLASS:RUN_A:RUN_B [...] [--session NAME]
        builds runs/<NAME>-A and runs/<NAME>-B whose final/<class>/ hold the per-class picks, plus
        runs/<NAME>.json (which real run sits behind A/B per class). Then one command judges every class:
        python ab_viewer.py <NAME>-A <NAME>-B --rater james
"""
import argparse, csv, glob, json, os, re, shutil, subprocess, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import upscale_common as uc  # noqa: E402

PY = sys.executable


def slug(model):
    s = os.path.splitext(os.path.basename(model))[0]
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def load_spandrel(path):
    import spandrel
    try:
        import spandrel_extra_arches
        spandrel_extra_arches.install()
    except Exception:
        pass
    return spandrel.ModelLoader().load_from_file(path)


def model_path(work, name):
    return name if os.path.isabs(name) else os.path.join(work, "models", name)


def cmd_probe(a):
    files = sorted(glob.glob(os.path.join(a.work, "models", "**", "*.pth"), recursive=True)
                   + glob.glob(os.path.join(a.work, "models", "**", "*.safetensors"), recursive=True))
    for p in files:
        rel = os.path.relpath(p, os.path.join(a.work, "models"))
        try:
            m = load_spandrel(p)
            n = sum(x.numel() for x in m.model.parameters()) / 1e6
            print(f"OK  {rel:55s} {m.architecture.name:20s} x{m.scale} {n:5.1f}M")
        except Exception as e:
            print(f"ERR {rel:55s} {type(e).__name__}: {str(e)[:90]}")


def derive_native(work, run_id, new_id):
    """Native-size final from runs/<run_id>/4x (RGB lanczos, mask area) -> runs/<new_id>."""
    from PIL import Image
    from upscale_run import resize
    src = uc.run_dir(work, run_id)
    meta = json.load(open(os.path.join(src, "run.json")))
    out = uc.run_dir(work, new_id)
    rows = {(r["class"], r["name"]): r for r in uc.load_manifest(work)}
    for p in glob.glob(os.path.join(src, "4x", "*", "*.png")):
        cls, name = os.path.basename(os.path.dirname(p)), os.path.splitext(os.path.basename(p))[0]
        r = rows.get((cls, name))
        if not r:
            continue
        im = np.asarray(Image.open(p), np.float32) / 255
        cfg = meta["resolved"][cls]
        rgb = resize(im[..., :3], r["native_w"], r["native_h"], cfg["downscale"]).clip(0, 1)
        al = resize(im[..., 3], r["native_w"], r["native_h"], "area").clip(0, 1) if im.shape[2] == 4 else None
        if al is not None and cfg["alpha"] == "threshold":
            al = (al >= float(cfg["alpha_threshold"])).astype(np.float32)
        uc.save_rgb(os.path.join(out, "final", cls, name + ".png"), rgb, al)
    m2 = dict(meta, id=new_id, derived_from=run_id)
    m2["resolved"] = {k: dict(v, target_scale=1) for k, v in meta["resolved"].items()}
    json.dump(m2, open(os.path.join(out, "run.json"), "w"), indent=2)


def cmd_run(a):
    recipe = a.recipe or os.path.join(HERE, "recipes", "u2-bake.yaml")
    for model in a.models:
        rid = f"{a.prefix}-{slug(model)}-o{a.overscale:g}-t{a.target:g}"
        rd = uc.run_dir(a.work, rid)
        if os.path.exists(os.path.join(rd, "run.json")) and not a.force:
            print("skip (exists)", rid)
        else:
            cmd = [PY, os.path.join(HERE, "upscale_run.py"), "--recipe", recipe, "--id", rid, "--work", a.work,
                   "--set", f"model={model}", "--set", f"overscale={a.overscale:g}",
                   "--set", f"target_scale={a.target:g}", "--force"]
            for s in a.set or []:
                cmd += ["--set", s]
            if a.classes:
                cmd += ["--classes", a.classes]
            print(">>", rid, flush=True)
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode:
                print(r.stdout[-1500:], r.stderr[-3000:])
                continue
            print(r.stdout.strip().splitlines()[-1])
        runs = [rid]
        if a.also1x:
            nid = rid.rsplit("-t", 1)[0] + "-t1"
            derive_native(a.work, rid, nid)
            runs.append(nid)
        if not a.noscore:
            r = subprocess.run([PY, os.path.join(HERE, "score.py"), *runs, "--work", a.work], capture_output=True,
                               text=True)
            print("\n".join(l for l in r.stdout.splitlines() if l.startswith("==")) or r.stderr[-2000:], flush=True)


def cmd_interp(a):
    import torch
    ma, mb = load_spandrel(model_path(a.work, a.a)), load_spandrel(model_path(a.work, a.b))
    if ma.architecture.id != mb.architecture.id or ma.scale != mb.scale:
        raise SystemExit(f"arch mismatch: {ma.architecture.id} x{ma.scale} vs {mb.architecture.id} x{mb.scale}")
    sa, sb = ma.model.state_dict(), mb.model.state_dict()
    if set(sa) != set(sb) or any(sa[k].shape != sb[k].shape for k in sa):
        raise SystemExit("state dicts differ in keys/shapes (different block count or width)")
    out = {k: (a.w * sa[k].float() + (1 - a.w) * sb[k].float()).to(sa[k].dtype) if sa[k].is_floating_point()
           else sa[k] for k in sa}
    name = a.name or f"{slug(a.a)}__{slug(a.b)}__w{int(round(a.w * 100))}"
    p = os.path.join(a.work, "models", "interp", name + ".pth")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    torch.save(out, p)
    chk = load_spandrel(p)  # make sure spandrel re-detects the blend
    print(f"wrote {p} ({chk.architecture.name} x{chk.scale})")


def read_scores(work, run):
    p = os.path.join(uc.run_dir(work, run), "scores.csv")
    return list(csv.DictReader(open(p, newline=""))) if os.path.exists(p) else []


def cmd_rank(a):
    rows = []
    for run in a.runs:
        by = {}
        for s in read_scores(a.work, run):
            by.setdefault(s["class"], []).append(s)
        for cls, ss in by.items():
            m = {k: float(np.mean([float(s[k]) for s in ss])) for k in ("lpips", "dists", "de2000", "lapvar",
                                                                          "lapvar_ref")}
            rows.append(dict(run=run, cls=cls, n=len(ss), **m))
    rows.sort(key=lambda r: (r["cls"], r["lpips"]))
    cur = None
    for r in rows:
        if r["cls"] != cur:
            cur = r["cls"]
            print(f"\n## {cur}\n{'run':50s} {'n':>2s} {'lpips':>7s} {'dists':>7s} {'dE':>6s} {'lapvar':>8s}")
        print(f"{r['run']:50s} {r['n']:2d} {r['lpips']:7.4f} {r['dists']:7.4f} {r['de2000']:6.2f} {r['lapvar']:8.2f}")
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, ["cls", "run", "n", "lpips", "dists", "de2000", "lapvar", "lapvar_ref"])
            w.writeheader()
            w.writerows(rows)


def cmd_sheet(a):
    from PIL import Image, ImageDraw
    rows = [r for r in uc.load_manifest(a.work) if r["class"] == a.cls]
    if a.names:
        rows = [r for r in rows if r["name"] in a.names.split(",")]
    labels = a.labels.split(",") if a.labels else a.runs
    z = a.zoom

    def flat(im):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 0, 255, 255))
        bg.alpha_composite(im)
        return bg.convert("RGB")

    def crop_box(r, scale):
        c = a.crop
        if not c or (r["native_w"] <= c and r["native_h"] <= c):
            return None
        cw, ch = min(c, r["native_w"]), min(c, r["native_h"])
        x0, y0 = (r["native_w"] - cw) // 2 + a.dx, (r["native_h"] - ch) // 2 + a.dy
        return tuple(round(v * scale) for v in (x0, y0, x0 + cw, y0 + ch))

    cols = ["original", "nearest 2x"] + labels
    cells = []
    for r in rows:
        o = Image.open(os.path.join(a.work, r["file"])).convert("RGB")
        if r["has_alpha"]:
            o.putalpha(Image.open(os.path.join(a.work, r["mask"])).convert("L"))
        line = []
        b = crop_box(r, 1)
        oc = o.crop(b) if b else o
        line.append(flat(oc))
        line.append(flat(oc).resize((oc.width * 2 * z, oc.height * 2 * z), Image.NEAREST))
        for run in a.runs:
            fp = uc.final_path(a.work, run, r)
            if not os.path.exists(fp):
                line.append(None)
                continue
            im = Image.open(fp)
            s = im.width / r["native_w"]
            b = crop_box(r, s)
            im = flat(im.crop(b) if b else im)
            tw, th = oc.width * 2 * z, oc.height * 2 * z  # every model column shown at 2x-equivalent size
            line.append(im.resize((tw, th), Image.NEAREST if im.width <= tw else Image.LANCZOS))
        cells.append((r, line))
    colw = [max((ln[i].width if ln[i] else 0) for _, ln in cells) for i in range(len(cols))]
    pad, lab = 6, 14
    W = sum(colw) + pad * (len(cols) + 1)
    H = 18 + sum(max(c.height for c in ln if c) + lab + pad for _, ln in cells)
    sheet = Image.new("RGB", (W, H), (32, 32, 32))
    d = ImageDraw.Draw(sheet)
    x = pad
    for c, w in zip(cols, colw):
        d.text((x, 3), c[:max(8, w // 6)], fill=(255, 255, 0))
        x += w + pad
    y = 18
    for r, ln in cells:
        x = pad
        d.text((x, y), f"{r['name']} {r['native_size']}" + (f" crop{a.crop}" if crop_box(r, 1) else ""),
               fill=(220, 220, 220))
        for c, w in zip(ln, colw):
            if c:
                sheet.paste(c, (x, y + lab))
            x += w + pad
        y += max(c.height for c in ln if c) + lab + pad
    out = a.out or os.path.join(a.work, "runs", "u2-sheets", f"{a.cls}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print("wrote", out, sheet.size)


def cmd_abprep(a):
    rows = uc.load_manifest(a.work)
    sess = {"session": a.session, "pairs": {}}
    for side in "AB":
        d = uc.run_dir(a.work, f"{a.session}-{side}")
        if os.path.exists(d):
            shutil.rmtree(d)
    for spec in a.pairs:
        cls, ra, rb = spec.split(":")
        sess["pairs"][cls] = {"A": ra, "B": rb}
        for side, run in (("A", ra), ("B", rb)):
            for r in rows:
                if r["class"] != cls:
                    continue
                src = uc.final_path(a.work, run, r)
                if not os.path.exists(src):
                    raise SystemExit(f"missing {src}")
                dst = uc.final_path(a.work, f"{a.session}-{side}", r)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
    for side in "AB":
        json.dump({"id": f"{a.session}-{side}", "ab_session": a.session,
                   "sources": {c: p[side] for c, p in sess["pairs"].items()}},
                  open(os.path.join(uc.run_dir(a.work, f"{a.session}-{side}"), "run.json"), "w"), indent=2)
    p = os.path.join(a.work, "runs", a.session + ".json")
    json.dump(sess, open(p, "w"), indent=2)
    print("wrote", p)
    print(f"judge with:  {PY} {os.path.join(HERE, 'ab_viewer.py')} {a.session}-A {a.session}-B --rater james")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default=uc.DEFAULT_WORK)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("probe")
    p = sp.add_parser("run")
    p.add_argument("models", nargs="+")
    p.add_argument("--prefix", default="u2")
    p.add_argument("--recipe")
    p.add_argument("--overscale", type=float, default=4)
    p.add_argument("--target", type=float, default=2)
    p.add_argument("--also1x", action="store_true")
    p.add_argument("--classes")
    p.add_argument("--set", action="append")
    p.add_argument("--force", action="store_true")
    p.add_argument("--noscore", action="store_true")
    p = sp.add_parser("interp")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--w", type=float, required=True, help="weight of A")
    p.add_argument("--name")
    p = sp.add_parser("rank")
    p.add_argument("runs", nargs="+")
    p.add_argument("--csv")
    p = sp.add_parser("sheet")
    p.add_argument("runs", nargs="+")
    p.add_argument("--cls", required=True)
    p.add_argument("--names")
    p.add_argument("--labels")
    p.add_argument("--out")
    p.add_argument("--crop", type=int, default=0)
    p.add_argument("--dx", type=int, default=0)
    p.add_argument("--dy", type=int, default=0)
    p.add_argument("--zoom", type=int, default=1)
    p = sp.add_parser("abprep")
    p.add_argument("--pairs", nargs="+", required=True, metavar="CLASS:RUN_A:RUN_B")
    p.add_argument("--session", default="u2-ab")
    a = ap.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
