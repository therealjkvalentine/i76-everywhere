#!/usr/bin/env python3
"""uses.py - hand-read helper for the Gold -> Nitro site map (nitro-port lane, 2026-10-21): every instruction in either
exe that names an address, with a few instructions of context, side by side, so a global's MEANING can be checked by its
use sites rather than by the vote (nitro-mp-design lane note: 0x541010 voted 1/1 onto a flag word).
    python tools/nitro-sites/uses.py 0x5aab08 [--nitro 0x5b5358] [--ctx 3] [--max 6]
The Nitro address defaults to the site table's. Reads the same exes as gen_sites.py."""
import argparse, csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_sites as G  # noqa: E402


def show(exe, addr, ctx, mx, tag):
    n = 0
    for fa, sz in exe.funcs:
        ins = exe.dis(fa, sz)
        for k, i in enumerate(ins):
            if addr in G.abs_addrs(i, exe):
                print('%s %s (function 0x%x)' % (tag, hex(i.address), fa))
                for j in ins[max(0, k - ctx):k + ctx + 1]:
                    print('   %s%-8x %-24s %s %s' % ('>' if j.address == i.address else ' ', j.address, j.bytes.hex(), j.mnemonic, j.op_str))
                n += 1
                if n >= mx:
                    return n
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('gold'); ap.add_argument('--nitro'); ap.add_argument('--ctx', type=int, default=3); ap.add_argument('--max', type=int, default=6)
    a = ap.parse_args()
    g = int(a.gold, 16)
    n = int(a.nitro, 16) if a.nitro else None
    if n is None:
        for r in csv.DictReader(open(os.path.join(HERE, 'sites_nitro.csv'))):
            if int(r['gold'], 16) == g and r['nitro']:
                n = int(r['nitro'], 16); print('table: %s -> %s %s %s' % (r['gold'], r['nitro'], r['status'], r['how']))
    gold = G.Exe(G.D['gold'], G.D['gold_funcs'])
    nit = G.Exe(G.D['nitro'], G.D['nitro_funcs'])
    show(gold, g, a.ctx, a.max, 'GOLD ')
    if n:
        show(nit, n, a.ctx, a.max, 'NITRO')


if __name__ == '__main__':
    main()
