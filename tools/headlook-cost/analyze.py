"""analyze.py <out dir> ... : per-rep rows for the headlook-cost runs.
Reads <name>.txt (t05-hl output: 'out <prefix>' and 'game end epoch_ms'), <prefix>.frames.csv, .phases.tsv, .cpu.csv, .gpu.csv.
Hill window = the hill leg's frames placed on the wall clock by the game-end epoch minus the frame time logged after the leg.
CPU % = cpu-time delta / window, as % of ONE logical CPU (the box has 8). Prints a table (markdown) and writes rows.json."""
import sys, os, re, csv, json, glob, statistics as st

def load_frames(p):
    wall = []
    with open(p, newline='') as f:
        r = csv.reader(f); next(r)
        for row in r:
            try: wall.append(float(row[1]))
            except Exception: pass
    return wall

def pct(v, q):
    v = sorted(v); k = (len(v) - 1) * q; lo = int(k); hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)

def one(d, txt):
    t = open(os.path.join(d, txt), errors='replace').read()
    m = re.search(r'out (\S+)$', t, re.M); pre = None
    for ln in t.splitlines():
        if ln.startswith('t05-hl: game end'):
            m = re.search(r'epoch_ms (\d+); out (.+)$', ln); end = int(m.group(1)); pre = m.group(2).strip()
    if not pre: return None
    ph = {}
    for ln in open(pre + '.phases.tsv').read().splitlines()[1:]:
        c = ln.split('\t'); ph[c[0]] = (int(c[1]), int(c[2]))
    wall = load_frames(pre + '.frames.csv')   # index i = frames.csv line i+2 (line 1 header)
    l0, l1 = ph['hill']
    hill = wall[l0 - 2:l1 - 1] if False else wall[l0 - 2:l1 - 1]
    after = sum(wall[l1 - 1:])
    dur = sum(hill)
    t1 = end - after; t0 = t1 - dur
    row = {'name': txt[:-4], 'hill_s': round(dur / 1000, 1), 'frames': len(hill)}
    row['med_fps'] = round(1000 / st.median(hill), 1); row['mean_fps'] = round(1000 * len(hill) / dur, 1)
    row['p99_ms'] = round(pct(hill, 0.99), 2); row['low1_fps'] = round(1000 / pct(hill, 0.99), 1)
    mt = re.search(r'hill: med ([\d.]+) fps, 1% low ([\d.]+)', t)
    if mt: row['rcd_med'] = float(mt.group(1)); row['rcd_low1'] = float(mt.group(2))
    # cpu
    cp = pre + '.cpu.csv'
    if os.path.exists(cp):
        procs = {}; sysr = []; ftr = []
        for r in csv.reader(open(cp)):
            if r[0] == 't' or len(r) < 7: continue
            ms, kind, pid, nm, det, val = int(r[1]), r[2], r[3], r[4], r[5], int(r[6])
            if kind == 'sys':
                mm = re.match(r'idle=(\d+);kern=(\d+)', det); sysr.append((ms, int(mm.group(1)), int(mm.group(2)) + val))
            elif kind == 'proc': procs.setdefault((nm, pid, det), []).append((ms, val))
            elif kind == 'ft': ftr.append((ms, val, det))
        cpu = {}
        for (nm, pid, det), ser in procs.items():
            w = [x for x in ser if t0 - 5000 <= x[0] <= t1 + 5000]
            if len(w) < 3: continue
            v = (w[-1][1] - w[0][1]) / ((w[-1][0] - w[0][0]) * 10000.0) * 100
            lab = nm
            if nm.startswith('AutoHotkey'):
                mm = re.search(r'([\w-]+\.ahk)', det or ''); lab = 'AHK:' + (mm.group(1) if mm else pid)
            elif nm in ('python', 'powershell', 'pythonw'):
                mm = re.search(r'([\w-]+\.(?:py|ps1))', det or ''); lab = nm + ':' + (mm.group(1) if mm else pid)
            cpu[lab] = round(cpu.get(lab, 0) + v, 1)
        row['cpu'] = {k: v for k, v in sorted(cpu.items(), key=lambda kv: -kv[1]) if v >= 0.7 or k.startswith(('opentrack', 'AHK'))}
        w = [x for x in sysr if t0 <= x[0] <= t1]
        if len(w) > 5:
            di = w[-1][1] - w[0][1]; dt = w[-1][2] - w[0][2]; row['sys_busy_pct'] = round(100 * (1 - di / dt), 1)
        w = [x for x in ftr if t0 <= x[0] <= t1]
        if len(w) > 5:
            row['ft_updates_s'] = round((w[-1][1] - w[0][1]) / ((w[-1][0] - w[0][0]) / 1000), 1)
            ys = [float(re.match(r'yaw=([-\d.eE]+)', x[2]).group(1)) for x in w]; row['ft_yaw_range'] = [round(min(ys), 2), round(max(ys), 2)]
    gp = pre + '.gpu.csv'
    if os.path.exists(gp):
        import datetime
        g = []
        for ln in open(gp):
            c = [x.strip() for x in ln.split(',')]
            if len(c) < 5: continue
            try:
                tt = datetime.datetime.strptime(c[0], '%Y/%m/%d %H:%M:%S.%f').timestamp() * 1000
                g.append((tt, float(c[1]), float(c[3]), float(c[4])))
            except Exception: pass
        gw = [x for x in g if t0 <= x[0] <= t1]
        if gw: row['gpu_util'] = round(st.mean(x[1] for x in gw), 1); row['gpu_sm_mhz'] = round(st.mean(x[2] for x in gw)); row['gpu_w'] = round(st.mean(x[3] for x in gw))
    return row

if __name__ == '__main__':
    rows = []
    for d in sys.argv[1:]:
        for f in sorted(glob.glob(os.path.join(d, '*-r*.txt'))):
            try:
                r = one(d, os.path.basename(f))
                if r: rows.append(r)
            except Exception as e:
                print('ERR', f, repr(e))
    for r in rows:
        print(json.dumps(r))
    json.dump(rows, open(os.path.join(sys.argv[1], 'rows.json'), 'w'), indent=1)
