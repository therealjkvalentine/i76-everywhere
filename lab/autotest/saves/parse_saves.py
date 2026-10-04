"""parse_saves.py - byte-exact inline checks from SAVES-STATE-AND-TEST-PLAN.md section 4.3 (read-only).

    python parse_saves.py <gamedir>            # savegame.dir records + every save*.cmp size check + GarageRec +0x7fc
    python parse_saves.py <gamedir> --json     # the same as JSON (for diffing snapshots)

dir: size == 4 + 60*count; record k at 4 + 60k = {u32 scene, char[32] name, char[16] file, u32 a11, u32 flags}
cmp: size == 0x8c4 + 8 + 0x74*(nA + nC), nA at 0x8c4, nC at 0x8c8 + 0x74*nA; GarageRec armour/chassis = 8 x u32 at +0x7fc
"""
import sys, os, struct, glob, hashlib, json

def md5(p):
    with open(p, 'rb') as f: return hashlib.md5(f.read()).hexdigest()

def cstr(b):
    return b.split(b'\0', 1)[0].decode('latin-1')

def parse_dir(p):
    b = open(p, 'rb').read()
    count = struct.unpack_from('<I', b, 0)[0]
    out = {'file': os.path.basename(p), 'size': len(b), 'md5': md5(p), 'count': count,
           'size_ok': len(b) == 4 + 60 * count, 'records': []}
    for k in range(count):
        o = 4 + 60 * k
        if o + 60 > len(b): out['records'].append({'k': k, 'truncated': True}); break
        scene, name, fname, a11, flags = struct.unpack_from('<I32s16sII', b, o)
        out['records'].append({'k': k, 'scene': scene, 'name': cstr(name), 'file': cstr(fname), 'a11': a11, 'flags': flags,
                               'name_raw': name.hex()})
    return out

def parse_cmp(p):
    b = open(p, 'rb').read()
    out = {'file': os.path.basename(p), 'size': len(b), 'md5': md5(p)}
    if len(b) < 0x8cc: out['error'] = 'shorter than header'; return out
    nA = struct.unpack_from('<I', b, 0x8c4)[0]
    oC = 0x8c8 + 0x74 * nA
    nC = struct.unpack_from('<I', b, oC)[0] if oC + 4 <= len(b) else None
    out.update({'nA': nA, 'nC': nC, 'size_ok': (nC is not None and len(b) == 0x8c4 + 8 + 0x74 * (nA + nC)),
                'armour': list(struct.unpack_from('<4I', b, 0x7fc)), 'chassis': list(struct.unpack_from('<4I', b, 0x80c)),
                'garage_7fc_hex': b[0x7fc:0x81c].hex()})
    # section A record names (PartRec +0 name, +0x1e type, +0x3b file) - first few only
    recs = []
    for i in range(min(nA, 40)):
        o = 0x8c8 + 0x74 * i
        recs.append({'cond': struct.unpack_from('<I', b, o + 0xc)[0], 'state': struct.unpack_from('<I', b, o + 0x10)[0],
                     'name': cstr(b[o + 0x14:o + 0x14 + 0x1e]) if False else cstr(b[o:o + 0x1e])})
    out['secA_head'] = recs[:8]
    return out

def main():
    g = sys.argv[1]
    as_json = '--json' in sys.argv
    res = {'dir': None, 'cmps': [], 'orphans': []}
    d = os.path.join(g, 'savegame.dir')
    if os.path.exists(d): res['dir'] = parse_dir(d)
    for p in sorted(glob.glob(os.path.join(g, 'save*.cmp'))):
        res['cmps'].append(parse_cmp(p))
    res['orphans'] = [os.path.basename(p) for p in glob.glob(os.path.join(g, 'save-*.cmp'))]
    if res['dir']:
        have = {c['file'].lower() for c in res['cmps']}
        res['dir']['missing_cmp'] = [r['file'] for r in res['dir']['records'] if 'file' in r and (r['file'].lower() + '.cmp') not in have]
    if as_json:
        print(json.dumps(res, indent=1)); return
    if res['dir']:
        dd = res['dir']
        print(f"savegame.dir size {dd['size']} count {dd['count']} 4+60n={'OK' if dd['size_ok'] else 'FAIL'} md5 {dd['md5']}")
        for r in dd['records']:
            print(f"  [{r.get('k')}] scene {r.get('scene')} name {r.get('name')!r} file {r.get('file')} +0x34 {r.get('a11')} flags {r.get('flags')}")
        if dd['missing_cmp']: print("  MISSING .cmp for:", dd['missing_cmp'])
    for c in res['cmps']:
        print(f"{c['file']} size {c['size']} nA {c.get('nA')} nC {c.get('nC')} formula={'OK' if c.get('size_ok') else 'FAIL'} "
              f"armour {c.get('armour')} chassis {c.get('chassis')} md5 {c['md5']}")
    if res['orphans']: print("ORPHANS:", res['orphans'])

if __name__ == '__main__':
    main()
