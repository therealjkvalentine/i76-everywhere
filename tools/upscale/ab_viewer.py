#!/usr/bin/env python3
"""Blind pairwise A/B viewer (plan section 9, method a - image-viewer stand-in until the Godot bench exists).

  python ab_viewer.py RUN_A RUN_B [--classes ..] [--names ..] [--zoom 3] [--rater james] [--seed N]
  python ab_viewer.py --left IMG --right IMG [--label TILE]       # two arbitrary images

One tile at a time; which run is on the left is randomised per tile and hidden.
Keys: Left / Right = that side is better, Down or '=' = equal, o = flash the original (hold), s = skip,
Esc = quit. Each pick appends a row to WORK/runs/picks.csv:
  time, rater, tile, class, run_left, run_right, pick (left|right|equal), pick_run (winning run id or 'equal')
Images are drawn nearest-neighbour at --zoom over magenta (alpha visible).
"""
import argparse, csv, datetime, os, random, sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upscale_common as uc  # noqa: E402

FIELDS = ["time", "rater", "tile", "class", "run_left", "run_right", "pick", "pick_run"]


def flat(im, size):
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 0, 255, 255))
    bg.alpha_composite(im)
    return bg.convert("RGB").resize(size, Image.NEAREST)


def build_pairs(a):
    if a.left:
        return [{"tile": a.label or os.path.basename(a.left), "class": "", "orig": None,
                 "A": (a.left, a.left), "B": (a.right, a.right)}]
    rows = uc.filter_rows(uc.load_manifest(a.work, a.manifest), a.classes, a.names)
    pairs = []
    for r in rows:
        pa, pb = uc.final_path(a.work, a.run_a, r), uc.final_path(a.work, a.run_b, r)
        if os.path.exists(pa) and os.path.exists(pb):
            orig = Image.open(os.path.join(a.work, r["file"])).convert("RGB")
            if r["has_alpha"]:
                orig.putalpha(Image.open(os.path.join(a.work, r["mask"])).convert("L"))
            pairs.append({"tile": r["name"], "class": r["class"], "orig": orig,
                          "A": (a.run_a, pa), "B": (a.run_b, pb)})
    return pairs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_a", nargs="?")
    ap.add_argument("run_b", nargs="?")
    ap.add_argument("--left")
    ap.add_argument("--right")
    ap.add_argument("--label")
    ap.add_argument("--work", default=uc.DEFAULT_WORK)
    ap.add_argument("--manifest")
    ap.add_argument("--classes")
    ap.add_argument("--names")
    ap.add_argument("--zoom", type=float, default=3)
    ap.add_argument("--max-side", type=int, default=900, help="cap each image's displayed width")
    ap.add_argument("--rater", default=os.environ.get("USERNAME", "anon"))
    ap.add_argument("--seed", type=int)
    ap.add_argument("--picks", help="default WORK/runs/picks.csv")
    ap.add_argument("--selftest", action="store_true", help="build the window, close it, write nothing")
    a = ap.parse_args()
    if not a.left and not (a.run_a and a.run_b):
        ap.error("give RUN_A RUN_B or --left/--right")
    pairs = build_pairs(a)
    if not pairs:
        raise SystemExit("no tiles with a final in both runs")
    rng = random.Random(a.seed)
    rng.shuffle(pairs)
    for p in pairs:
        p["swap"] = rng.random() < 0.5
    picks = a.picks or os.path.join(a.work, "runs", "picks.csv")

    import tkinter as tk
    from PIL import ImageTk
    root = tk.Tk()
    root.title("I'76 A/B - Left / Right / Down=equal / o=original / s=skip / Esc")
    root.configure(bg="#202020")
    info = tk.Label(root, fg="#ddd", bg="#202020", font=("Segoe UI", 11))
    info.pack(side="top", pady=4)
    frame = tk.Frame(root, bg="#202020")
    frame.pack()
    lw, rw = tk.Label(frame, bg="#202020"), tk.Label(frame, bg="#202020")
    lw.pack(side="left", padx=6, pady=6)
    rw.pack(side="left", padx=6, pady=6)
    state = {"i": 0, "imgs": None, "n": 0}

    def sides(p):
        return (p["B"], p["A"]) if p["swap"] else (p["A"], p["B"])

    def show():
        if state["i"] >= len(pairs):
            info.config(text=f"done: {state['n']} picks -> {picks}")
            lw.config(image="")
            rw.config(image="")
            return
        p = pairs[state["i"]]
        L, R = sides(p)
        il, ir = Image.open(L[1]), Image.open(R[1])
        w, h = round(il.width * a.zoom), round(il.height * a.zoom)
        if w > a.max_side:
            w, h = a.max_side, round(h * a.max_side / w)
        state["size"] = (w, h)
        state["imgs"] = [ImageTk.PhotoImage(flat(il, (w, h))), ImageTk.PhotoImage(flat(ir, (w, h)))]
        if p["orig"] is not None:
            state["orig"] = ImageTk.PhotoImage(flat(p["orig"], (w, h)))
        lw.config(image=state["imgs"][0])
        rw.config(image=state["imgs"][1])
        info.config(text=f"{state['i'] + 1}/{len(pairs)}  {p['class']}/{p['tile']}")

    def record(choice):
        if state["i"] >= len(pairs):
            return
        p = pairs[state["i"]]
        L, R = sides(p)
        win = {"left": L[0], "right": R[0], "equal": "equal"}[choice]
        if not a.selftest:
            new = not os.path.exists(picks)
            os.makedirs(os.path.dirname(picks), exist_ok=True)
            with open(picks, "a", newline="") as f:
                w = csv.DictWriter(f, FIELDS)
                if new:
                    w.writeheader()
                w.writerow({"time": datetime.datetime.now().isoformat(timespec="seconds"), "rater": a.rater,
                            "tile": p["tile"], "class": p["class"], "run_left": L[0], "run_right": R[0],
                            "pick": choice, "pick_run": win})
        state["n"] += 1
        state["i"] += 1
        show()

    def orig_on(_):
        if state.get("orig") is not None and state["i"] < len(pairs):
            lw.config(image=state["orig"])
            rw.config(image=state["orig"])

    def orig_off(_):
        if state["imgs"] and state["i"] < len(pairs):
            lw.config(image=state["imgs"][0])
            rw.config(image=state["imgs"][1])

    root.bind("<Left>", lambda e: record("left"))
    root.bind("<Right>", lambda e: record("right"))
    root.bind("<Down>", lambda e: record("equal"))
    root.bind("=", lambda e: record("equal"))
    root.bind("s", lambda e: (state.__setitem__("i", state["i"] + 1), show()))
    root.bind("<KeyPress-o>", orig_on)
    root.bind("<KeyRelease-o>", orig_off)
    root.bind("<Escape>", lambda e: root.destroy())
    show()
    if a.selftest:
        root.update()
        record("left")
        root.update()
        print(f"selftest ok: {len(pairs)} pairs, window built, 1 simulated pick (not written)")
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
