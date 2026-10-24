"""MODE1/2352 data track -> 2048-byte ISO. usage: bin2iso.py in.bin out.iso [n_sectors]"""
import sys
src, dst = sys.argv[1], sys.argv[2]
lim = int(sys.argv[3]) if len(sys.argv) > 3 else None
n = 0
with open(src, 'rb') as f, open(dst, 'wb') as o:
    while lim is None or n < lim:
        s = f.read(2352)
        if len(s) < 2352: break
        o.write(s[16:2064]); n += 1
print(n, 'sectors')
