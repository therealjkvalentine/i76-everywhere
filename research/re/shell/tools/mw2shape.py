#!/usr/bin/env python3
"""mw2shape.py - render a '1.10' shape table from DATABASE.MW2, per the shell's blitter 0x1003a8f4:
frame offset = u32 at 8 + 8*i (0x1003a998..0x1003a9a3); frame +8 x0, +0xc y0, +0x10 x1, +0x14 y1 (inclusive; 0x1003a9a9..0x1003a9c7);
pixel stream at +0x18 (0x1003a9cd), one run list per line, decoded as in the skip loop 0x1003aa90..0x1003aa9a:
  0 = end of line; 1 = skip next-byte transparent pixels; odd b>1 = (b>>1) literal pixels; even b = (b>>1) x next byte.
    python mw2shape.py <DATABASE.MW2> <item> <palette-item> <outdir>
"""
import sys, os, struct, io
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
src = open(os.path.join(os.path.dirname(__file__), 'mw2db.py')).read().replace('main(sys.argv)', '')
ns = {}; exec(src, ns)
def frames(b):
    n = struct.unpack_from('<I', b, 4)[0]
    for i in range(n):
        off = struct.unpack_from('<I', b, 8 + 8 * i)[0]
        x0, y0, x1, y1 = struct.unpack_from('<4i', b, off + 8)
        w, h = x1 - x0 + 1, y1 - y0 + 1
        px = bytearray(w * h); mask = bytearray(w * h)
        p = off + 0x18
        for y in range(h):
            x = 0
            while True:
                c = b[p]; p += 1
                if c == 0: break
                if c == 1:
                    x += b[p]; p += 1
                elif c & 1:
                    k = c >> 1
                    for j in range(k):
                        if 0 <= x < w: px[y * w + x] = b[p + j]; mask[y * w + x] = 1
                        x += 1
                    p += k
                else:
                    k = c >> 1; v = b[p]; p += 1
                    for j in range(k):
                        if 0 <= x < w: px[y * w + x] = v; mask[y * w + x] = 1
                        x += 1
        yield i, (x0, y0, x1, y1), w, h, px, mask
def main(a):
    d, items = ns['load'](a[1]); k = int(a[2], 0); pk = int(a[3], 0)
    o, s = items[k - 1]; b = d[o:o + s]
    po, ps = items[pk - 1]; pal_img = Image.open(io.BytesIO(ns['unlzss'](d[po:po + ps])))
    pal = pal_img.getpalette()
    os.makedirs(a[4], exist_ok=True)
    for i, bb, w, h, px, mask in frames(b):
        im = Image.frombytes('P', (w, h), bytes(px)); im.putpalette(pal)
        rgb = im.convert('RGB'); bg = Image.new('RGB', (w, h), (255, 0, 255))
        bg.paste(rgb, mask=Image.frombytes('L', (w, h), bytes(255 if m else 0 for m in mask)))
        bg.save(os.path.join(a[4], 'item%02x_frame%02d.png' % (k, i)))
        print(i, bb, w, h)
if __name__ == '__main__':
    main(sys.argv)
