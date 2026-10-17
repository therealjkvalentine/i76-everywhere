import sys,os,hashlib,glob
sys.path.insert(0,'C:/Users/james/i76-map/tools')
from i76fmt import zfs
def load(p):
    z=zfs.parse(open(p,'rb').read()); d={}
    for e in z.entries:
        if e.empty: continue
        d[e.name.lower()]=z.read(e)
    return d
ret=load('cd1/I76.ZFS'); gold=load('C:/Users/james/i76-map/sandbox-gog/main/app/I76.ZFS')
print('retail entries',len(ret),'gold entries',len(gold))
def addon(dirp):
    return {os.path.basename(f).lower():open(f,'rb').read() for f in glob.glob(dirp+'/*') if os.path.isfile(f)}
a106=addon('x106/I76v106/Addon'); a1081={}
for f in glob.glob('x1081/out/Data/*/*')+glob.glob('x1081/out/Data/*'):
    if os.path.isfile(f) and f.lower().endswith(('.vdf','.tmt','.vtf')): a1081[os.path.basename(f).lower()]=open(f,'rb').read()
print('1.06 addon',len(a106),'1.081 loose',len(a1081))
h=lambda b: hashlib.md5(b).hexdigest()[:8] if b is not None else '-'
print('%-14s %8s %8s %8s %8s  %s'%('file','retail','1.06','1.081','gold','note'))
for n in sorted(set(a106)|set(a1081)):
    r=ret.get(n); x=a106.get(n); y=a1081.get(n); g=gold.get(n)
    note=[]
    if r is not None and x is not None: note.append('106==ret' if r==x else '106!=ret')
    if x is not None and y is not None: note.append('1081==106' if x==y else '1081!=106')
    if g is not None and x is not None: note.append('gold==106' if g==x else 'gold!=106')
    print('%-14s %8s %8s %8s %8s  %s'%(n,h(r),h(x),h(y),h(g),' '.join(note)))
import pickle; pickle.dump((ret,gold,a106,a1081),open('vdfs.pkl','wb'))
