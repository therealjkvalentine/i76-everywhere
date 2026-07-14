#!/usr/bin/env python3
"""Phase 1 of the full-game HD pass: decode every renderable texture tile in the
game (car paint, world/terrain, dashboards, sky) to a flat staging folder of PNGs,
content-deduplicated (shared props like tires/barrels/wrecks appear once).

Categories, by the embedded extension of a pak's FIRST manifest entry (robust -
pak filenames don't reliably say what they hold, but every .pix line does):
  .vqm -> software-renderer palette-index tiles (level palette; we use t01.act,
          same convention this repo already ships for cars/dash)
  .m16 -> hardware-renderer (-glide) tiles with a SELF-CONTAINED per-tile RGB565
          palette - what this Windows setup actually renders
  .map -> plain 8bpp bitmap, same palette convention as vqm
  .geo / .tmt -> 3D mesh / material-table metadata, NOT images - skipped
Standalone loose .map/.m16 files (sky art etc, not archived in any pak) are
walked too.

Usage: python decode_all.py ASSETS_DIR STAGING_DIR MANIFEST.json
"""
import os, sys, glob, struct, hashlib, json, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import i76img

assets, staging, manifest_path = sys.argv[1:4]
os.makedirs(staging, exist_ok=True)
pal = i76img.read_act(os.path.join(assets, "t01.act"))

seen_hash = {}   # content hash -> staging filename (dedup)
manifest = []    # list of source records
t0 = time.time()

def stage(rgba, w, h):
    key = hashlib.blake2b(struct.pack("<2I", w, h) + bytes(rgba), digest_size=16).hexdigest()
    fname = seen_hash.get(key)
    if fname is None:
        fname = f"t{len(seen_hash):06d}_{key[:8]}.png"
        i76img.write_png(os.path.join(staging, fname), w, h, bytes(rgba))
        seen_hash[key] = fname
    return fname, key

n_pak = n_tile = n_skip = 0
for pix_path in sorted(glob.glob(os.path.join(assets, "*.pix"))):
    lines = open(pix_path).read().split()
    if len(lines) < 2:
        continue
    first_ext = os.path.splitext(lines[1])[1].lower()
    if first_ext not in (".vqm", ".m16", ".map"):
        n_skip += 1
        continue
    pak_path = os.path.splitext(pix_path)[0] + ".pak"
    if not os.path.exists(pak_path):
        continue
    d = open(pak_path, "rb").read()
    it = iter(lines[1:])
    entries = []
    ok = True
    for name in it:
        try:
            off, ln = int(next(it)), int(next(it))
        except StopIteration:
            break
        chunk = d[off:off + ln]
        ext = os.path.splitext(name)[1].lower()
        try:
            if ext == ".m16":
                w, h, flags, rgba = i76img.decode_m16(chunk)
            elif ext == ".vqm":
                w, h, rgba = i76img.decode_vqm(chunk, pal, assets)
                flags = None
            elif ext == ".map":
                w, h, rgba = i76img.decode_map(chunk, pal)
                flags = None
            else:
                continue
            if len(rgba) != w * h * 4:
                raise ValueError(f"truncated/corrupt tile: got {len(rgba)}b, want {w*h*4}b")
            fname, key = stage(rgba, w, h)
        except Exception as e:
            print(f"  SKIP {name} in {os.path.basename(pak_path)}: {e}", file=sys.stderr)
            continue
        entries.append({"name": name, "ext": ext, "w": w, "h": h, "flags": flags,
                         "staged": fname, "hash": key})
        n_tile += 1
    if entries:
        manifest.append({"kind": "pak", "pix": os.path.basename(pix_path),
                          "pak": os.path.basename(pak_path), "entries": entries})
        n_pak += 1
    if n_pak % 100 == 0 and n_pak:
        print(f"  ...{n_pak} paks, {n_tile} tiles, {len(seen_hash)} unique so far "
              f"({time.time()-t0:.0f}s)", flush=True)

# standalone loose files (not archived in any pak)
archived_maps = {os.path.basename(m["pix"]) for m in manifest}  # not used, just clarity
for loose in sorted(glob.glob(os.path.join(assets, "*.map"))):
    name = os.path.basename(loose)
    try:
        w, h, rgba = i76img.decode_map(open(loose, "rb").read(), pal)
        if len(rgba) != w * h * 4:
            raise ValueError(f"truncated/corrupt: got {len(rgba)}b, want {w*h*4}b")
        fname, key = stage(rgba, w, h)
    except Exception as e:
        print(f"  SKIP loose {name}: {e}", file=sys.stderr)
        continue
    manifest.append({"kind": "loose_map", "file": name,
                      "entries": [{"name": name, "ext": ".map", "w": w, "h": h,
                                   "flags": None, "staged": fname, "hash": key}]})
    n_tile += 1

for loose in sorted(glob.glob(os.path.join(assets, "*.m16"))):
    name = os.path.basename(loose)
    try:
        w, h, flags, rgba = i76img.decode_m16(open(loose, "rb").read())
        if len(rgba) != w * h * 4:
            raise ValueError(f"truncated/corrupt: got {len(rgba)}b, want {w*h*4}b")
        fname, key = stage(rgba, w, h)
    except Exception as e:
        print(f"  SKIP loose {name}: {e}", file=sys.stderr)
        continue
    manifest.append({"kind": "loose_m16", "file": name,
                      "entries": [{"name": name, "ext": ".m16", "w": w, "h": h,
                                   "flags": flags, "staged": fname, "hash": key}]})
    n_tile += 1

json.dump(manifest, open(manifest_path, "w"))
print(f"DONE: {n_pak} texture paks + loose files, {n_tile} tile refs, "
      f"{len(seen_hash)} unique images staged ({n_skip} non-texture paks skipped). "
      f"{time.time()-t0:.0f}s")
