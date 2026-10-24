import json, collections, csv, sys, os
idx = sys.argv[1]
maps = json.load(open(os.path.join(idx, 'maps.json'), encoding='utf-8'))
for m in maps:
    ter = (m.get('terrain') or '').split(' ')[0].lower()
    m['map_key'] = os.path.splitext(m['file'])[0].lower() + '|' + ter
RETAIL = ('ia/Interstate-76-Deutsch', 'ia/Interstate76_1020', 'ia/Arsenal_201610')
ns = [m for m in maps if not m['stock'] and m['source'] not in RETAIL and (m.get('parse') or '').startswith('ok')]
keys = collections.defaultdict(list)
for m in ns: keys[m['map_key']].append(m)
print('non-stock parsed copies', len(ns), 'unique hashes', len({m['sha256'] for m in ns}), 'unique map keys', len(keys))
def best(ms):
    order = {'gold-static-ok': 0, 'gold-loads': 1, 'nitro-only': 2, 'broken': 3}
    return sorted(ms, key=lambda m: (order.get(m['gold_verdict'].split(';')[0].split(' (')[0].split(':')[0], 9), m['source'].startswith('ia/')))[0]
rows = []
for k, ms in keys.items():
    b = best(ms)
    rows.append(dict(map_key=k, title=next((x['title'] for x in ms if x.get('title')), ''), game=b['game'], mode=b['mode'],
        author=next((x['author'] for x in ms if x.get('author')), ''), best_verdict=b['gold_verdict'], files=len(ms),
        variants=len({x['sha256'] for x in ms}), sources=' '.join(sorted({x['source'] for x in ms})),
        objects=b.get('objects'), spawn=b.get('spawn'), regen=b.get('regen'), team_spawn=b.get('team_spawn'),
        checkpoints=b.get('checkpoints'), fsm_actions=b.get('fsm_actions'), terrain=b.get('terrain'), best_path=b['path']))
rows.sort(key=lambda r: (r['game'], r['mode'], r['map_key']))
with open(os.path.join(idx, 'maps-unique.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); [w.writerow(r) for r in rows]
c = collections.Counter((r['game'], r['mode']) for r in rows); print(c)
v = collections.Counter(r['best_verdict'].split(';')[0].split(' (')[0] for r in rows); print(v)
print('with author', sum(1 for r in rows if r['author']), 'with title', sum(1 for r in rows if r['title']))
print('drops objects', sum(1 for r in rows if 'drops objects' in r['best_verdict']), 'risk art', sum(1 for r in rows if 'risk' in r['best_verdict']))
src = collections.Counter(s for r in rows for s in r['sources'].split()); print(src)
only = collections.Counter(r['sources'] for r in rows if len(r['sources'].split()) == 1); print('only-in', only)
