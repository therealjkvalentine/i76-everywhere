"""Extract every downloaded archive into its own new folder (never runs anything from the archive).
usage: python -I extract.py <root>   (root holds dl/; output x/ mirrors dl/, nested archives -> <name>.x/)"""
import os, sys, subprocess, json
SZ = r"C:\Program Files\7-Zip\7z.exe"
root = sys.argv[1]
DL, X = os.path.join(root, 'dl'), os.path.join(root, 'x')
ARCH = {'.zip', '.rar', '.7z', '.arj', '.lzh', '.cab', '.gz', '.tar', '.tgz'}
log = []
def is_sfx(p):
    r = subprocess.run([SZ, 'l', '-y', p], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    types = [l.split('=',1)[1].strip() for l in r.stdout.splitlines() if l.startswith('Type = ')]
    return r.returncode == 0 and any(t not in ('PE', 'COFF', 'MZ') for t in types)
def x(p, out):
    if os.path.exists(out) and os.listdir(out):
        return 'exists'
    os.makedirs(out, exist_ok=True)
    try:
        r = subprocess.run([SZ, 'x', '-y', '-pnone', '-o' + out, p], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=1800)
    except subprocess.TimeoutExpired:
        return 'timeout'
    return 'ok' if r.returncode == 0 else 'rc%d %s' % (r.returncode, (r.stderr or r.stdout).strip().splitlines()[-1:] )
def nested(d, depth):
    if depth > 4: return
    for base, dirs, files in os.walk(d):
        for f in files:
            p = os.path.join(base, f); e = os.path.splitext(f)[1].lower()
            if e in ARCH:
                out = p + '.x'
                st = x(p, out); log.append(dict(archive=os.path.relpath(p, root), out=os.path.relpath(out, root), status=st, nested=depth))
                if st in ('ok', 'exists'): nested(out, depth + 1)
        dirs[:] = [z for z in dirs if not z.endswith('.x')]
for base, dirs, files in os.walk(DL):
    for f in files:
        if f.endswith('.part'): continue
        p = os.path.join(base, f); e = os.path.splitext(f)[1].lower()
        rel = os.path.relpath(p, DL)
        if e in ARCH or (e == '.exe' and is_sfx(p)) or (e == '.bin' and 'CD1' in f):
            out = os.path.join(X, rel)
            st = x(p, out); log.append(dict(archive=os.path.relpath(p, root), out=os.path.relpath(out, root), status=st, nested=0))
            print(st, rel, flush=True)
            if st in ('ok', 'exists'): nested(out, 1)
json.dump(log, open(os.path.join(root, 'EXTRACT-LOG.json'), 'w'), indent=1)
print('archives', len(log), 'bad', sum(1 for l in log if l['status'] not in ('ok', 'exists')))
