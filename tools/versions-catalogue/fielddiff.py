import pickle,sys,os,collections,math
sys.path.insert(0,'C:/Users/james/i76-map/data/fmt')
import bwd2x
ret,gold,a106,a1081=pickle.load(open('vdfs.pkl','rb'))
r=dict(ret); r.update(a106)
def flat(v,p,out):
    if isinstance(v,dict):
        for k,x in v.items(): flat(x,p+'.'+str(k),out)
    elif isinstance(v,(list,tuple)):
        for i,x in enumerate(v): flat(x,p+'[%d]'%i,out)
    elif hasattr(v,'__dict__') and not isinstance(v,(bytes,str)):
        flat(vars(v),p,out)
    else: out[p]=v
def fl(data,ext):
    d=bwd2x.decode(data,ext); out={}; cnt=collections.Counter()
    for par,c,info in bwd2x.chunks(d):
        key=(par+'/' if par else '')+c.tag_str; i=cnt[key]; cnt[key]+=1
        if info is None or info.value is None: out[key+'#%d'%i]=('raw',bytes(c.body)); continue
        flat(info.value,key+'#%d'%i,out)
    return out
exts=sys.argv[1].split(',')
agg=collections.defaultdict(list)
for k in sorted(set(r)&set(gold)):
    e=os.path.splitext(k)[1][1:]
    if e not in exts: continue
    try: A=fl(r[k],e); B=fl(gold[k],e)
    except Exception as ex: print('ERR',k,ex); continue
    for f in set(A)|set(B):
        a=A.get(f); b=B.get(f)
        if a!=b:
            g=f.split('#')[0]+'#'+f.split('#',1)[1].split('[',1)[-1] if False else f
            agg[(e,f.split('#')[0]+f[f.index('#')+2:] if '#' in f else f)].append((k,a,b))
for (e,f),L in sorted(agg.items()):
    if any(isinstance(x[1],float) or isinstance(x[2],float) for x in L):
        rat=[x[2]/x[1] for x in L if isinstance(x[1],(int,float)) and isinstance(x[2],(int,float)) and x[1]]
        rs=sorted(rat); med=rs[len(rs)//2] if rs else None
        print(f'{e:4} {f:45} n={len(L):4} ratio med={med} min={rs[0] if rs else None} max={rs[-1] if rs else None} ex={L[0][0]} {L[0][1]}->{L[0][2]}')
    else:
        print(f'{e:4} {f:45} n={len(L):4} ex={L[0][0]} {str(L[0][1])[:40]}->{str(L[0][2])[:40]}')
