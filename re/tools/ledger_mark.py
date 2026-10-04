#!/usr/bin/env python3
r"""ledger_mark.py - append a respawn/event marker for ledger_types.py (runbook item 005).

    python tools\ledger_mark.py --capture 005-ledger --label self-destruct
    python tools\ledger_mark.py --dir <dir> --label <text>

Call it from the console script right after cheatlib `Send-SelfDestruct` (CTRL+ALT+X, the scripted death /
respawn marker). Writes {"t_ms": epoch ms (same clock as the ledger drains' t_ms: host wall clock),
"t_utc", "label"} into <dir>\ledger\markers.json (append-only, read back after write).
"""
import argparse
import datetime
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--capture")
    g.add_argument("--dir")
    ap.add_argument("--label", default="self-destruct")
    a = ap.parse_args()
    base = a.dir or os.path.join(ROOT, "captures", a.capture)
    ldir = os.path.join(base, "ledger")
    os.makedirs(ldir, exist_ok=True)
    path = os.path.join(ldir, "markers.json")
    doc = {"markers": []}
    if os.path.exists(path):
        doc = json.load(open(path, encoding="utf-8"))
    m = {"t_ms": int(time.time() * 1000), "t_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
         "label": a.label}
    doc["markers"].append(m)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, path)
    back = json.load(open(path, encoding="utf-8"))
    assert back["markers"][-1] == m, "marker read-back mismatch"
    print(json.dumps({"written": path, "marker": m, "n_markers": len(back["markers"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
