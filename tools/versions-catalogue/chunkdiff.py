import pickle,struct,collections
ret,gold,a106,a1081=pickle.load(open('vdfs.pkl','rb'))
def chunks(b):
    assert b[:4]==b'BWD2'; i=8; out=[]
    while i+8<=len(b):
        t=b[i:i+4].decode('latin-1'); sz=struct.unpack_from('<I',b,i+4)[0]
        if sz<8: break
        out.append((t,b[i+8:i+sz])); i+=sz
    return out
def cmp(a,b):
    ca,cb=chunks(a),chunks(b); res=[]
    ta=collections.Counter(t for t,_ in ca); tb=collections.Counter(t for t,_ in cb)
    if [t for t,_ in ca]!=[t for t,_ in cb]: res.append('tagseq differ: %s vs %s'%(dict(ta-tb),dict(tb-ta)))
    for (t1,b1),(t2,b2) in zip(ca,cb):
        if t1==t2 and b1!=b2:
            nd=sum(x!=y for x,y in zip(b1,b2))+abs(len(b1)-len(b2)); res.append(f'{t1}({len(b1)}->{len(b2)} B, {nd} B differ)')
    return res
tally=collections.Counter()
for n in sorted(a106):
    if not n.endswith('.vdf') or n not in ret: continue
    r=cmp(ret[n],a106[n]); print('RET->106',n,'; '.join(r))
    for x in r: tally[x.split('(')[0]]+=1
print(tally)
tg=collections.Counter()
for n in sorted(a106):
    if n.endswith('.vdf') and n in gold:
        r=cmp(a106[n],gold[n]); print('106->GOLD',n,'; '.join(r))
        for x in r: tg[x.split('(')[0]]+=1
print(tg)
