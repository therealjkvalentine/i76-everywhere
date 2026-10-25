import csv, re, os, json, shutil
BS = chr(92)
src = 'D:/i76-archive/community-20261024'
out = (__import__("os").path.expanduser("~") + '/i76-everywhere/docs/research/content-2026-10-24/index')
EM = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
for name, drop in [('maps-unique.csv', []), ('maps.csv', ['email']), ('cars.csv', []), ('audio.csv', []),
                   ('frc.csv', []), ('paints.csv', [])]:
    rows = list(csv.DictReader(open(os.path.join(src, 'index', name), encoding='utf-8')))
    cols = [c for c in rows[0].keys() if c not in drop]
    with open(os.path.join(out, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore'); w.writeheader()
        for r in rows:
            w.writerow({k: EM.sub('[email removed]', v or '') for k, v in r.items() if k in cols})
shutil.copy(os.path.join(src, 'index', 'summary.json'), out)
shutil.copy(os.path.join(src, 'MANIFEST.csv'), os.path.join(out, 'downloads-manifest.csv'))
ex = json.load(open(os.path.join(src, 'EXTRACT-LOG.json')))
with open(os.path.join(out, 'extract-log.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['archive', 'out', 'status', 'nested'])
    for e in ex: w.writerow([e['archive'].replace(BS, '/'), e['out'].replace(BS, '/'), e['status'], e['nested']])
