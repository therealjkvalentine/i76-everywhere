"""compile-soak.py - build the far-clip soak table from the per-mission frame_stats outputs (%TEMP%\\soak-<m>.out)
and the proxy log (game\\mciproxy.log: one 'mission-launch: booting directly into' line per run, CRASH lines after it).

    python compile-soak.py [--since-line N] > runs\\farclip-soak\\<ts>.md
"""
import glob, os, re, sys

log = r"C:\Users\james\i76-uncap-lab\game\mciproxy.log"
tmp = os.environ.get("TEMP", r"C:\Users\james\AppData\Local\Temp")
since = int(sys.argv[sys.argv.index("--since-line") + 1]) if "--since-line" in sys.argv else 0
lines = open(log, encoding="latin1").read().split("\n")[since:]
runs = []                                                   # (mission, crash line or "")
for ln in lines:
    m = re.search(r"booting directly into '(\w+)\.msn'", ln)
    if m:
        runs.append([m.group(1), ""])
    elif ln.startswith("CRASH: code") and runs and not runs[-1][1]:
        runs[-1][1] = ln.split("|")[0].strip()
crash = {}
for mission, c in runs:                                    # last run of each mission wins
    crash[mission] = c
def short(s):
    s = re.sub(r" \| bins.*", "", s)
    return re.sub(r"frames in [\d.]+ s = ", "", s)
print("| mission | drive | hood (F6) | binoculars (B) | crash |")
print("|---|---|---|---|---|")
order = ["t%02d" % i for i in range(1, 18)] + ["m%02d" % i for i in range(1, 16)] + ["s%02d" % i for i in range(1, 8)] + ["a01"]
for mission in order:
    p = os.path.join(tmp, "soak-%s.out" % mission)
    if not os.path.exists(p):
        continue
    d = {}
    for ln in open(p, encoding="latin1"):
        k, _, v = ln.partition(": ")
        if k in ("drive", "hood", "binoc"):
            d[k] = short(v.strip())
    print("| %s | %s | %s | %s | %s |" % (mission, d.get("drive", "-"), d.get("hood", "-"), d.get("binoc", "-"), crash.get(mission) or "none"))
