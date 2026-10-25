"""Index the community-content archive (read-only over the data; uses the data track's parsers).

usage: python -I index.py <root> <outdir>
  root   = <archive>\\community-20261024 (holds dl\\ and x\\)
  outdir = where files.csv, maps.csv, maps.json, cars.csv, audio.csv, frc.csv, paints.csv go
The parsers (<re-archive>\\data\\fmt) are imported, never modified; nothing here executes archive content.
"""
import os, sys, csv, json, hashlib, re, struct, collections

FMT = (__import__("os").path.expanduser("~") + r"\i76-map\data\fmt")
MAP = (__import__("os").path.expanduser("~") + r"\i76-map")
sys.path.insert(0, FMT)
import bwd2x, fsm_protos  # noqa: E402

root, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
EXTRA = [((__import__("os").path.expanduser("~") + r"\i76-everywhere\refs\route380"), "route380-prior-mirror")]
MSN = {'.lvl', '.msn', '.cbt', '.rac', '.cf2', '.cf3', '.cf4'}
TXT = {'.txt', '.doc', '.nfo', '.rtf', '.wri', '.diz', '.me', '.1st', '.htm', '.html'}
AUD = {'.wav', '.mp3', '.flac', '.ogg'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# ---- stock name and hash sets (Gold = GOG I'76 Gold; Nitro = GOG Nitro) -----------------------------------
def names_and_hashes(dirs, exts):
    names, hashes = set(), {}
    for d in dirs:
        for b, _, fs in os.walk(d):
            for f in fs:
                names.add(f.lower())
                if os.path.splitext(f)[1].lower() in exts:
                    p = os.path.join(b, f)
                    if os.path.getsize(p) < 64 << 20:
                        hashes[sha(p)] = os.path.relpath(p, MAP)
    return names, hashes


STOCK_EXT = MSN | {'.ter', '.vcf'}
gold_names, gold_hash = names_and_hashes([os.path.join(MAP, r"sandbox-gog\main\app"),
                                          os.path.join(MAP, r"recon-2026-09-04\recon\formats\zfs_out")], STOCK_EXT)
nitro_names, nitro_hash = names_and_hashes([os.path.join(MAP, r"sandbox-gog\nitro-full\app"),
                                            os.path.join(MAP, r"sandbox-gog\nitro-full\zfs_out")], STOCK_EXT)
nitro_only = nitro_names - gold_names
stock_refs = set()
for d in (os.path.join(MAP, "sandbox-gog", "main", "app"), os.path.join(MAP, "sandbox-gog", "nitro-full", "app")):
    for b, _, fs in os.walk(d):
        for f in fs:
            if os.path.splitext(f)[1].lower() in MSN:
                try:
                    dd = bwd2x.decode(open(os.path.join(b, f), 'rb').read(), '.msn')
                except Exception:  # noqa: BLE001
                    continue
                for _, c, info in bwd2x.chunks(dd, 'WRLD', 'WDEF'):
                    for k, v in (info.value or {}).items():
                        if isinstance(v, str) and '.' in v:
                            stock_refs.add(v.lower())
print('stock WRLD refs', len(stock_refs), flush=True)
print('stock names gold', len(gold_names), 'nitro', len(nitro_names), 'nitro-only', len(nitro_only), flush=True)


# ---- walk -------------------------------------------------------------------------------------------------
def source_of(rel):
    parts = rel.replace('\\', '/').split('/')
    if parts[0] in ('dl', 'x'):
        parts = parts[1:]
    if parts[0] in ('lsm', 'ia', 'localditch', 'compendium-disk1'):
        return '/'.join(parts[:2])
    return parts[0]


def unit_of(rel):
    """the top-level downloaded file this path came from (dl/<...>/<file>)."""
    parts = rel.replace('\\', '/').split('/')
    if parts[0] == 'x':
        # x/<same path as dl>/... : the dl file is the shortest prefix that exists in dl
        for i in range(2, len(parts) + 1):
            cand = os.path.join(root, 'dl', *parts[1:i])
            if os.path.isfile(cand):
                return 'dl/' + '/'.join(parts[1:i])
    return rel.replace('\\', '/')


files = []
walk_roots = [(root, None)] + EXTRA
for wr, label in walk_roots:
    for sub in (['dl', 'x'] if label is None else ['']):
        base0 = os.path.join(wr, sub)
        for b, dirs, fs in os.walk(base0):
            for f in fs:
                if f.endswith('.part'):
                    continue
                p = os.path.join(b, f)
                rel = os.path.relpath(p, wr if label is None else os.path.dirname(wr))
                files.append(dict(source=label or source_of(rel), unit=(label + '/' + '/'.join(os.path.relpath(p, wr).split(os.sep)[:3])) if label else unit_of(rel),
                                  path=rel.replace('\\', '/'), name=f, ext=os.path.splitext(f)[1].lower(),
                                  size=os.path.getsize(p), abspath=p))
print('files', len(files), flush=True)
for r in files:
    r['sha256'] = sha(r['abspath'])
with open(os.path.join(outdir, 'files.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['source', 'unit', 'path', 'ext', 'size', 'sha256'])
    for r in files:
        w.writerow([r['source'], r['unit'], r['path'], r['ext'], r['size'], r['sha256']])

by_dir = collections.defaultdict(list)
for r in files:
    by_dir[os.path.dirname(r['abspath']).lower()].append(r)
by_unit = collections.defaultdict(list)
for r in files:
    by_unit[r['unit']].append(r)


# ---- readmes: author lines --------------------------------------------------------------------------------
AUTH = re.compile(r"(?i)\b(author|authors|created by|made by|designed by|map by|level by|built by|written by|"
                  r"designer|creator|by:)\s*[:\-]?\s*([^\r\n]{2,60})")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def read_text(p):
    b = open(p, 'rb').read(200000)
    if b[:4] == b'\xd0\xcf\x11\xe0':  # OLE .doc: pull printable runs
        b = b' '.join(re.findall(rb'[\x20-\x7e\r\n\t]{6,}', b))
    t = b.decode('latin-1', 'replace')
    if p.lower().endswith(('.htm', '.html')):
        t = re.sub(r'<[^>]+>', ' ', t)
    return t


def readme_info(cands):
    authors, titles, emails, docs = [], [], [], []
    for r in cands:
        if r['ext'] not in TXT and not r['name'].lower().startswith('readme'):
            continue
        if r['size'] > 300000:
            continue
        docs.append(r['name'])
        t = read_text(r['abspath'])
        for m in AUTH.finditer(t):
            a = m.group(2).strip(' .:-*=\t')
            if a and a.lower() not in [x.lower() for x in authors] and len(authors) < 3:
                authors.append(a)
        emails += [e for e in EMAIL.findall(t) if e not in emails][:2]
        first = [l.strip() for l in t.splitlines() if l.strip()][:1]
        if first:
            titles.append(first[0][:70])
    return authors, emails[:2], titles[:1], docs[:5]


def is_doc(x):
    return x['ext'] in TXT or x['name'].lower().startswith('readme')


def pick_readme(r):
    """same folder if it holds few missions; else a readme in the unit whose stem matches the mission stem."""
    stem = os.path.splitext(r['name'])[0].lower()
    same = by_dir[os.path.dirname(r['abspath']).lower()]
    n_msn = sum(1 for x in same if x['ext'] in MSN)
    unit = by_unit[r['unit']]
    if n_msn <= 3 and any(is_doc(x) for x in same):
        return readme_info(same)
    byst = [x for x in unit if is_doc(x) and os.path.splitext(x['name'])[0].lower() == stem]
    if not byst and len(stem) >= 5:
        byst = [x for x in unit if is_doc(x) and os.path.splitext(x['name'])[0].lower()[:5] == stem[:5]]
    if byst:
        return readme_info(byst[:2])
    n_unit = sum(1 for x in unit if x['ext'] in MSN)
    if n_unit <= 3:
        return readme_info(unit)
    return [], [], [], []


_rc = {}


def short_wrld(b):
    """WRLD bodies of 315 bytes (I76EDIT 1997 output) stop before the 16-byte title at +0x13b; read what is there."""
    if len(b) < 0x93:
        return {}
    names = ['intro_smk', 'outro_smk', 'palette', 'lum_table', 'xluc_table', 'objective_text', 'sky_texture',
             'scrounge_sdf', 'terrain_texture', 'map_screen', 'horizon_hzd']
    v = dict(cd_track=struct.unpack_from('<I', b, 0)[0])
    for i, n in enumerate(names):
        v[n] = b[4 + 13 * i:4 + 13 * i + 13].split(bytes(1))[0].decode('latin-1')
    if len(b) >= 0x97:
        v['hour_of_day'] = struct.unpack_from('<i', b, 0x93)[0]
    if len(b) >= 0x13b:
        v['far_clip'] = struct.unpack_from('<i', b, 0x137)[0]
    v['mission_title'] = ''
    return v


def resolvable(x, names, local):
    """x is on disk (pack or stock), or - for art referenced by stem - some stock file starts with its stem
    (the engine expands texture / map-screen names by a naming rule, e.g. tt081sd_ -> tt0812sd_.map)."""
    if x in local or x in names:
        return True
    key = (x, id(names))
    if key not in _rc:
        stem, ext = os.path.splitext(x)
        _rc[key] = ext in ('.map', '.hzd', '.act', '.lum', '.tbl', '.pak', '.npt') and len(stem) >= 4 and             any(n.startswith(stem) for n in names | stock_refs)
    return _rc[key]


# ---- maps -------------------------------------------------------------------------------------------------
def strip_label(s):
    return bytes(b & 0x7f for b in s.encode('latin-1', 'replace')).split(b'\0')[0].decode('latin-1')


def fsm_names(doc):
    out = []
    for _, c, info in bwd2x.chunks(doc, "FSM", "ADEF"):
        v = info.value if info is not None else None
        if not v:
            continue
        acts = v.get("actions") if isinstance(v, dict) else None
        for a in acts or []:
            out.append(a if isinstance(a, str) else (a.get("name") if isinstance(a, dict) else str(a)))
    return out


SOURCE_GAME = {'lsm/exclusive': 'nitro', 'lsm/exclusive2': 'nitro', 'lsm/combat1': 'nitro', 'lsm/combat2': 'nitro',
               'lsm/combat3': 'nitro', 'lsm/racing1': 'nitro', 'lsm/racing2': 'nitro', 'lsm/ctf': 'nitro',
               'i76com-download': None}
maps = []
for r in files:
    if r['ext'] not in MSN:
        continue
    data = open(r['abspath'], 'rb').read()
    m = dict(source=r['source'], unit=r['unit'], path=r['path'], file=r['name'], ext=r['ext'], size=r['size'],
             sha256=r['sha256'])
    m['stock'] = gold_hash.get(r['sha256']) or nitro_hash.get(r['sha256']) or ''
    if data[:4] != b'BWD2':
        m['parse'] = 'not BWD2'
        maps.append(m)
        continue
    try:
        doc = bwd2x.decode(data, r['ext'] if r['ext'] != '.msn' else '.msn')
        errs = [e for e in bwd2x.errors(doc) if not (e[0] == 'WRLD' and 'short read str at 315' in e[1])]
        m['parse'] = ('ok' if not bwd2x.errors(doc) else 'ok (WRLD 315 B: no title field)') if not errs else 'errors: ' + '; '.join('%s %s' % e for e in bwd2x.errors(doc)[:3])
    except Exception as ex:  # noqa: BLE001
        m['parse'] = 'exception: %s' % ex
        maps.append(m)
        continue
    cls = collections.Counter(); labels = collections.Counter(); refs = set(); ters = []
    nobj = nl = nr = 0; wrld = {}
    for par, c, info in bwd2x.chunks(doc):
        v = info.value if info is not None else None
        if c.tag_str == 'WRLD' and isinstance(v, dict):
            wrld = v
        elif c.tag_str == 'WRLD':
            wrld = short_wrld(c.body)
        elif c.tag_str == 'WREV' and isinstance(v, dict):
            m['wrev'] = v.get('revision')
        elif c.tag_str == 'ZONE' and isinstance(v, dict):
            ters.append(v['ter'])
        elif c.tag_str == 'RSEG':
            nr += 1
        elif c.tag_str == 'OBJ' and par == 'ODEF' and isinstance(v, dict):
            nobj += 1
            cls[v.get('class_id')] += 1
            lab = strip_label(v.get('label') or '')
            low = lab.lower()
            key = None
            if low in ('spawn', 'regen'):
                key = low
            elif re.match(r'#?spawn\d', low):
                key = 'spawnN(team)'
            elif low.startswith('#'):
                key = '#other'
            elif re.match(r'check\d+', low):
                key = 'checkN'
            elif low.startswith('flag'):
                key = 'flag*'
            if key:
                labels[key] += 1
            else:
                refs.add(low + ('.vcf' if v.get('class_id') in (1, 8, 9) else '.sdf'))
        elif c.tag_str == 'OBJ' and par == 'LDEF':
            nl += 1
    for k in ('palette', 'lum_table', 'xluc_table', 'objective_text', 'sky_texture', 'scrounge_sdf',
              'terrain_texture', 'map_screen', 'horizon_hzd'):
        if wrld.get(k):
            refs.add(wrld[k].lower())
    refs = {x for x in refs if x and all(32 < ord(ch) < 127 for ch in x) and x != 'none.sdf'}
    local = {x['name'].lower() for x in by_unit[r['unit']]}
    acts = fsm_names(doc)
    unknown_acts = sorted({a for a in acts if a not in fsm_protos.ACTIONS})
    ter_status = []
    for t in ters:
        tl = t.lower()
        ter_status.append(t + ('' if tl in local else (' (stock)' if tl in gold_names or tl in nitro_names else ' (MISSING)')))
    wrld_refs = {wrld[k].lower() for k in ('palette', 'lum_table', 'xluc_table', 'objective_text', 'sky_texture',
                 'terrain_texture', 'map_screen', 'horizon_hzd') if wrld.get(k)}
    miss_gold = sorted(x for x in refs if not resolvable(x, gold_names, local))
    nitro_needed = sorted(x for x in miss_gold if resolvable(x, nitro_names, local))
    absent = sorted(x for x in miss_gold if x not in nitro_needed)
    absent_core = [x for x in absent if x in wrld_refs and not x.endswith('.npt')]
    absent_obj = [x for x in absent if x not in wrld_refs]
    # game and mode
    if r['ext'] in ('.cbt', '.rac', '.cf2', '.cf3', '.cf4'):
        game = 'nitro'
    else:
        game = SOURCE_GAME.get(r['source']) or ('nitro' if 'nitro' in r['path'].lower() else 'i76')
    if r['ext'] == '.rac' or labels['checkN']:
        mode = 'race'
    elif r['ext'] in ('.cf2', '.cf3', '.cf4') or labels['spawnN(team)'] or labels['flag*']:
        mode = 'ctf'
    elif r['ext'] == '.msn' and acts:
        mode = 'mission'
    elif acts:
        mode = 'scripted-melee'
    else:
        mode = 'melee'
    gold_spawns = labels['spawn']
    terr_missing = any('(MISSING)' in t for t in ter_status)
    if terr_missing or unknown_acts:
        verdict = 'broken: ' + ', '.join(filter(None, ['terrain missing' if terr_missing else '',
                                                       'unknown FSM ' + ' '.join(unknown_acts[:3]) if unknown_acts else '',
                                                       '']))
    elif nitro_needed:
        verdict = 'nitro-only (needs %d Nitro asset%s)' % (len(nitro_needed), 's' if len(nitro_needed) > 1 else '')
    elif mode in ('race', 'ctf') and (labels['checkN'] or labels['spawnN(team)']):
        verdict = 'gold-loads; %s rules are Nitro-only (Gold sees %d plain spawn)' % (mode, gold_spawns)
    elif gold_spawns == 0 and mode != 'mission':
        verdict = 'gold-loads; no plain spawn labels'
    else:
        verdict = 'gold-static-ok'
    if absent_core and not verdict.startswith('broken'):
        verdict += '; risk: missing art %s (untested)' % ' '.join(absent_core[:3])
    if absent_obj:
        verdict += '; drops objects (%s)' % ' '.join(absent_obj[:4])
    a, e, t, d = pick_readme(r)
    m.update(title=(wrld.get('mission_title') or '').split('\0')[0].strip(), game=game, mode=mode,
             terrain=' '.join(ter_status), zones=len(ters), objects=nobj, class_hist=dict(cls), lines=nl, roads=nr,
             spawn=labels['spawn'], regen=labels['regen'], team_spawn=labels['spawnN(team)'], checkpoints=labels['checkN'],
             fsm_actions=len(acts), unknown_fsm=' '.join(unknown_acts), cd_track=wrld.get('cd_track'),
             hour=wrld.get('hour_of_day'), far_clip=wrld.get('far_clip'), sky=wrld.get('sky_texture'),
             terrain_texture=wrld.get('terrain_texture'), nitro_assets=' '.join(nitro_needed[:8]),
             missing=' '.join(absent[:8]), gold_verdict=verdict, author=' | '.join(a), email=' '.join(e),
             readme_first_line=' '.join(t), readmes=' '.join(d))
    maps.append(m)

# dedupe by mission-file content hash
groups = collections.defaultdict(list)
for m in maps:
    groups[m['sha256']].append(m)
for h, ms in groups.items():
    ms.sort(key=lambda m: (m['source'].startswith('ia/'), m['source'] == 'route380-prior-mirror', m['path']))
    for i, m in enumerate(ms):
        m['dup_group'] = h[:12]
        m['copies'] = len(ms)
        m['canonical'] = 'yes' if i == 0 else 'no'
        m['also_in'] = ' '.join(sorted({x['source'] for x in ms if x is not m}))
json.dump(maps, open(os.path.join(outdir, 'maps.json'), 'w', encoding='utf-8'), indent=1, default=str)
cols = ['canonical', 'dup_group', 'wrev', 'copies', 'stock', 'game', 'mode', 'title', 'file', 'author', 'email', 'source', 'unit',
        'path', 'size', 'sha256', 'parse', 'terrain', 'zones', 'objects', 'lines', 'roads', 'spawn', 'regen', 'team_spawn',
        'checkpoints', 'fsm_actions', 'unknown_fsm', 'cd_track', 'hour', 'far_clip', 'sky', 'terrain_texture',
        'nitro_assets', 'missing', 'gold_verdict', 'also_in', 'readmes', 'readme_first_line']
with open(os.path.join(outdir, 'maps.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, cols, extrasaction='ignore')
    w.writeheader()
    for m in sorted(maps, key=lambda m: (m['game'] if 'game' in m else 'z', m.get('mode', ''), m['file'].lower())):
        w.writerow(m)
print('maps', len(maps), 'unique', len(groups), flush=True)

# ---- cars (.vcf) ------------------------------------------------------------------------------------------
cars = []
for r in files:
    if r['ext'] != '.vcf':
        continue
    m = dict(source=r['source'], unit=r['unit'], path=r['path'], file=r['name'], size=r['size'], sha256=r['sha256'],
             stock=gold_hash.get(r['sha256']) or nitro_hash.get(r['sha256']) or '')
    try:
        doc = bwd2x.decode(open(r['abspath'], 'rb').read(), '.vcf')
        weps = []
        for _, c, info in bwd2x.chunks(doc):
            v = info.value if info is not None else None
            if c.tag_str == 'VCFC' and isinstance(v, dict):
                m.update(variant=v['variant'].split('\0')[0], vdf=v['vdf'], vtf=v['vtf'], engine=v['engine_id'],
                         armour='/'.join(map(str, v['armour'])), chassis='/'.join(map(str, v['chassis'])))
            elif c.tag_str == 'WEPN' and isinstance(v, dict) and v['gdf'].lower() != 'null':
                weps.append(v['gdf'])
        m['weapons'] = ' '.join(weps)
        local = {x['name'].lower() for x in by_unit[r['unit']]}
        need = [x.lower() for x in [m.get('vdf'), m.get('vtf')] + weps if x]
        m['needs_nitro'] = ' '.join(x for x in need if x not in gold_names and x not in local and x in nitro_names)
        m['missing'] = ' '.join(x for x in need if x not in gold_names and x not in local and x not in nitro_names)
        m['custom_parts'] = ' '.join(x['name'] for x in by_unit[r['unit']]
                                     if x['ext'] in ('.vdf', '.vtf', '.geo', '.map', '.pak', '.wdf', '.gdf', '.tmt', '.pix'))[:300]
    except Exception as ex:  # noqa: BLE001
        m['parse'] = 'exception: %s' % ex
    a, e, t, d = readme_info(by_unit[r['unit']])
    m.update(author=' | '.join(a), readmes=' '.join(d))
    cars.append(m)
cc = collections.Counter(c['sha256'] for c in cars)
with open(os.path.join(outdir, 'cars.csv'), 'w', newline='', encoding='utf-8') as f:
    cols = ['source', 'unit', 'file', 'variant', 'vdf', 'vtf', 'engine', 'armour', 'chassis', 'weapons', 'stock',
            'needs_nitro', 'missing', 'custom_parts', 'author', 'readmes', 'copies', 'path', 'size', 'sha256', 'parse']
    w = csv.DictWriter(f, cols, extrasaction='ignore')
    w.writeheader()
    for c in sorted(cars, key=lambda c: (c['source'], c['path'])):
        c['copies'] = cc[c['sha256']]
        w.writerow(c)
print('vcf', len(cars), 'non-stock', sum(1 for c in cars if not c['stock']), flush=True)

# ---- paint jobs / car packs: archive-level listing ------------------------------------------------------
with open(os.path.join(outdir, 'paints.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['source', 'unit', 'n_files', 'bytes', 'vcf', 'vtf', 'textures(.map/.pak/.tmt/.pix/.bmp/.pcx)', 'geo', 'author', 'readmes', 'files'])
    for u, fs in sorted(by_unit.items()):
        src = fs[0]['source']
        if src not in ('kcr', 'ava'):
            continue
        ex = collections.Counter(x['ext'] for x in fs)
        a, e, t, d = readme_info(fs)
        w.writerow([src, u, len(fs), sum(x['size'] for x in fs), ex['.vcf'], ex['.vtf'],
                    sum(ex[k] for k in ('.map', '.pak', '.tmt', '.pix', '.bmp', '.pcx')), ex['.geo'],
                    ' | '.join(a), ' '.join(d), ' '.join(sorted(x['name'] for x in fs))[:400]])


# ---- audio ------------------------------------------------------------------------------------------------
def dur_wav(p):
    with open(p, 'rb') as f:
        b = f.read(1 << 16)
    if b[:4] != b'RIFF':
        return None
    i, rate, ch, bits, size = 12, None, None, None, None
    while i + 8 <= len(b):
        tag, n = b[i:i + 4], struct.unpack('<I', b[i + 4:i + 8])[0]
        if tag == b'fmt ':
            _, ch, rate, byterate, _, bits = struct.unpack('<HHIIHH', b[i + 8:i + 24])
        if tag == b'data':
            return n / byterate if rate else None
        i += 8 + n + (n & 1)
    return None


def dur_flac(p):
    with open(p, 'rb') as f:
        b = f.read(64)
    if b[:4] != b'fLaC':
        return None
    si = b[8:8 + 34]
    x = int.from_bytes(si[10:18], 'big')
    rate = x >> 44
    total = x & ((1 << 36) - 1)
    return total / rate if rate else None


BR = {1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320], 2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def dur_mp3(p):
    size = os.path.getsize(p)
    with open(p, 'rb') as f:
        b = f.read(200000)
    i = 0
    if b[:3] == b'ID3':
        i = 10 + ((b[6] & 0x7f) << 21 | (b[7] & 0x7f) << 14 | (b[8] & 0x7f) << 7 | (b[9] & 0x7f))
    while i < len(b) - 4:
        if b[i] == 0xff and (b[i + 1] & 0xe0) == 0xe0:
            ver = (b[i + 1] >> 3) & 3; lay = (b[i + 1] >> 1) & 3
            bri = b[i + 2] >> 4; sri = (b[i + 2] >> 2) & 3
            if ver != 1 and lay == 1 and 0 < bri < 15 and sri < 3:
                sr = SR[ver][sri]
                spf = 1152 if ver == 3 else 576
                fr = b[i:i + 200]
                for tag in (b'Xing', b'Info'):
                    j = fr.find(tag)
                    if j > 0 and fr[j + 7] & 1:
                        return struct.unpack('>I', fr[j + 8:j + 12])[0] * spf / sr
                kbps = BR[1 if ver == 3 else 2][bri]
                return (size - i) * 8 / (kbps * 1000)
        i += 1
    return None


audio = []
for r in files:
    if r['ext'] not in AUD:
        continue
    if r['source'] == 'ia/Interstate.76' or 'miss' in r['path'].lower().split('/')[-2:-1]:
        pass
    d = {'.wav': dur_wav, '.flac': dur_flac, '.mp3': dur_mp3}.get(r['ext'], lambda p: None)(r['abspath'])
    audio.append(dict(source=r['source'], unit=r['unit'], folder=os.path.dirname(r['path']).split('/')[-1], file=r['name'],
                      ext=r['ext'], size=r['size'], seconds=round(d, 1) if d else '', sha256=r['sha256'], path=r['path']))
with open(os.path.join(outdir, 'audio.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, ['source', 'unit', 'folder', 'file', 'ext', 'size', 'seconds', 'sha256', 'path'])
    w.writeheader()
    for a in audio:
        w.writerow(a)
print('audio', len(audio), flush=True)

# ---- FRC (DirectInput force-feedback RIFF 'FORC') ----------------------------------------------------------
frc = []
for r in files:
    if r['ext'] != '.frc':
        continue
    b = open(r['abspath'], 'rb').read()
    names = [n.decode('latin-1') for n in re.findall(rb'data....(?:.{4})?([A-Za-z][\w ]{2,30})\x00', b)]
    effs = b.count(b'efct')
    frc.append(dict(source=r['source'], file=r['name'], size=r['size'], riff=b[:4].decode('latin-1'),
                    form=b[8:12].decode('latin-1'), effects=effs, names=' '.join(sorted(set(names))), sha256=r['sha256'], path=r['path']))
with open(os.path.join(outdir, 'frc.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, ['source', 'file', 'size', 'riff', 'form', 'effects', 'names', 'sha256', 'path'])
    w.writeheader()
    for a in frc:
        w.writerow(a)
print('frc', len(frc), flush=True)

# ---- summary ----------------------------------------------------------------------------------------------
summ = dict(files=len(files), bytes=sum(r['size'] for r in files),
            by_source={s: dict(files=n, bytes=sum(r['size'] for r in files if r['source'] == s))
                       for s, n in collections.Counter(r['source'] for r in files).items()},
            maps=len(maps), maps_unique=len(groups),
            maps_unique_nonstock=len({m['sha256'] for m in maps if not m['stock']}),
            maps_by_game_mode=collections.Counter('%s/%s' % (m.get('game'), m.get('mode')) for m in maps if m.get('canonical') == 'yes' and not m['stock']),
            maps_by_verdict=collections.Counter((m.get('gold_verdict') or '').split(' (')[0].split(';')[0] for m in maps if m.get('canonical') == 'yes' and not m['stock']),
            vcf=len(cars), vcf_nonstock=len({c['sha256'] for c in cars if not c['stock']}), audio=len(audio), frc=len(frc))
json.dump(summ, open(os.path.join(outdir, 'summary.json'), 'w'), indent=1, default=str)
print(json.dumps(summ, indent=1, default=str))
