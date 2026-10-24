"""Sequential polite downloader. usage: python -I fetch.py <list.tsv> <root> [delay]
list.tsv rows: dest_rel <TAB> url. Appends to <root>/MANIFEST.csv: date,url,dest,size,sha256,status"""
import urllib.parse, sys, os, time, hashlib, csv, urllib.request, urllib.error, datetime
lst, root = sys.argv[1], sys.argv[2]
delay = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
man = os.path.join(root, 'MANIFEST.csv')
done = set()
if os.path.exists(man):
    for r in csv.DictReader(open(man, encoding='utf-8')):
        if r['status'] == 'ok': done.add(r['dest'])
new = not os.path.exists(man)
mf = open(man, 'a', newline='', encoding='utf-8'); w = csv.writer(mf)
if new: w.writerow(['date','url','dest','size','sha256','status'])
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) i76-archive-research (single sequential fetch)'
def get(url, path):
    if 'blackhole' in url: raise RuntimeError('blocked: blackhole')
    url = urllib.parse.quote(url, safe=":/?=&%~#+")
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    h = hashlib.sha256(); n = 0
    tmp = path + '.part'
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as f:
        ctype = r.headers.get('Content-Type','')
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b); h.update(b); n += len(b)
    os.replace(tmp, path)
    return n, h.hexdigest(), ctype
for line in open(lst, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line or line.startswith('#'): continue
    dest, url = line.split('\t')[:2]
    if dest in done: continue
    path = os.path.join(root, dest); os.makedirs(os.path.dirname(path), exist_ok=True)
    st = 'err'; n = ''; sha = ''
    for attempt in (1, 2):
        try:
            n, sha, ctype = get(url, path)
            st = 'ok' if 'text/html' not in ctype or dest.lower().endswith(('.htm','.html')) else 'ok-html?'
            break
        except Exception as e:
            st = 'err:' + str(e)[:80].replace(',', ';')
            if attempt == 1: time.sleep(8)
    w.writerow([datetime.datetime.now().isoformat(timespec='seconds'), url, dest, n, sha, st]); mf.flush()
    print(st, n, dest, flush=True)
    time.sleep(delay)
