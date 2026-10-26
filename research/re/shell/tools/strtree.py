import sys, json
from fninfo import facts, load
from sdis import fname
F,cg=load()
def body(a):
    r=F.get(a)
    return (a,int(r['end'],16)+1) if r else None
def strs(a,depth,seen):
    out=[]
    if a in seen or a not in F: return out
    seen.add(a)
    S,IM,CB,G,C=facts(*body(a))
    out+= [ (depth,a,s[0]) for s in S]
    if depth<2:
        for t,_ in C:
            if t in F and F[t]['size']<3000: out+=strs(t,depth+1,seen)
    return out
for x in sys.argv[1:]:
    a=int(x,16); seen=set()
    r=strs(a,0,seen)
    uniq=[]
    for d,f,s in r:
        if s not in [u[2] for u in uniq]: uniq.append((d,f,s))
    print('== %x : %d strings'%(a,len(uniq)))
    for d,f,s in uniq[:40]: print('   %d %x %r'%(d,f,s[:70]))
