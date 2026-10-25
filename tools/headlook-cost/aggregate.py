"""aggregate.py <out dirs...>: per-condition table (mean, sd, n) and a regression fps ~ cond + MsMpEng + other-load."""
import sys, json, subprocess, collections, statistics as st, re
rows = []
for d in sys.argv[1:]:
    out = subprocess.run(['python', '-I', 'analyze.py', d], capture_output=True, text=True).stdout
    rows += [json.loads(l) for l in out.splitlines() if l.startswith('{')]
by = collections.OrderedDict()
for r in rows:
    c = re.sub(r'-r\d+$', '', r['name']); by.setdefault(c, []).append(r)
def g(r, k): return r.get('cpu', {}).get(k, 0.0)
def ms(v): return (round(st.mean(v), 1), round(st.stdev(v), 1) if len(v) > 1 else 0.0)
print('| cond | n | hill median fps (mean, sd) | each | 1 % low fps (mean) | opentrack % core | layer % core | MsMpEng % core | i76 % core | system busy % | GPU % |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for c, rs in by.items():
    f = [r['med_fps'] for r in rs]
    lay = [max([v for k, v in r.get('cpu', {}).items() if k.startswith('AHK:i76-opentrack-headlook')] or [0]) for r in rs]
    print('| %s | %d | %s | %s | %.1f | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f |' % (c, len(rs), '%.1f, %.1f' % ms(f), ' / '.join('%.1f' % x for x in f), st.mean(r['low1_fps'] for r in rs), st.mean(g(r, 'opentrack') for r in rs), st.mean(lay), st.mean(g(r, 'MsMpEng') for r in rs), st.mean(g(r, 'i76') for r in rs), st.mean(r.get('sys_busy_pct', 0) for r in rs), st.mean(r.get('gpu_util', 0) for r in rs)))
try:
    import numpy as np
    conds = [c for c in by]; base = 'a'
    X = []; y = []
    for r in rows:
        c = re.sub(r'-r\d+$', '', r['name'])
        if 'cpu' not in r: continue
        X.append([1.0] + [1.0 if c == k else 0.0 for k in conds if k != base] + [g(r, 'MsMpEng') / 100.0]); y.append(r['med_fps'])
    X = np.array(X); y = np.array(y); beta, res, rk, sv = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta; dof = max(1, len(y) - X.shape[1]); s2 = (resid @ resid) / dof
    cov = s2 * np.linalg.pinv(X.T @ X); se = np.sqrt(np.diag(cov))
    names = ['intercept(a)'] + ['%s - a' % k for k in conds if k != base] + ['per +100 pct MsMpEng core']
    print('\nregression fps ~ cond + MsMpEng (n=%d, resid sd %.1f):' % (len(y), s2 ** .5))
    for n, b, e in zip(names, beta, se): print('  %-28s %+7.1f fps  (se %.1f)' % (n, b, e))
except ImportError:
    print('(numpy missing: no regression)')
