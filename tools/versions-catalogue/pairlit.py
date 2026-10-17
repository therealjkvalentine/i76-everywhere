import pickle,re,collections,sys
T=pickle.load(open('functables.pkl','rb'))
def lits(n):
    c=collections.Counter()
    for l in n:
        l=re.sub(r'\[esp[^\]]*\]','[S]',l)
        if l.startswith(('int3','nop')): continue
        for m in re.findall(r'C[0-9a-f]{8,16}|0x[0-9a-f]+|\b\d+\b',l.split(' ',1)[1] if ' ' in l else ''): c[m]+=1
        c['op:'+l.split(' ')[0]]+=1
    return c
o=sys.argv[1]
for p in sys.argv[2:]:
    name,ab=p.split('='); a,b=[int(x,16) for x in ab.split(':')]
    A=lits(T['r10'][a][2]); B=lits(T[o][b][2])
    d1={k:v for k,v in (A-B).items() if not k.startswith('op:')}; d2={k:v for k,v in (B-A).items() if not k.startswith('op:')}
    print(f'{name:10} {T["r10"][a][1]:4}/{T[o][b][1]:4} ins  lit only-1.0 {d1}  only-{o} {d2}')
