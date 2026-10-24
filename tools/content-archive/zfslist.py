import sys, os, collections
sys.path.insert(0, r"C:\Users\james\i76-map\tools")
from i76fmt import zfs
d = open(sys.argv[1], 'rb').read()
z = zfs.parse(d)
ex = collections.Counter(os.path.splitext(e.name)[1].lower() for e in z.entries)
print(len(z.entries), dict(ex.most_common(12)))
gold = set(n.lower() for n in os.listdir(r"C:\Users\james\i76-map\recon-2026-09-04\recon\formats\zfs_out"))
names = set(e.name.lower() for e in z.entries)
print('only here', len(names - gold), sorted(names - gold)[:30])
print('only gold', len(gold - names), sorted(gold - names)[:20])
if len(sys.argv) > 2:
    out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    pats = sys.argv[3].split(',')
    n = 0
    for e in z.entries:
        if any(e.name.lower().endswith(p) for p in pats):
            open(os.path.join(out, e.name), 'wb').write(z.read(e)); n += 1
    print('wrote', n)
