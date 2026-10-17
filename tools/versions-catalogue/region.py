import sys,re,collections
sys.argv_saved=sys.argv; sys.argv=['x']
from funcmatch import load,norm
def lits(n):
    c=collections.Counter()
    for l in n:
        l=re.sub(r'\[esp[^\]]*\]','[S]',l)
        if l.startswith(('int3','nop')): continue
        for m in re.findall(r'C[0-9a-f]{8,16}|0x[0-9a-f]+|\b\d+\b',l.split(' ',1)[1] if ' ' in l else ''): c[m]+=1
        c['op:'+l.split(' ')[0]]+=1
    return c
def reg(p,a,b):
    pe,ib,code,tva,img=load(p); return norm(code,tva,ib,img,a,b)
args=sys.argv_saved[1:]
A=reg(args[0],int(args[1],16),int(args[2],16)); B=reg(args[3],int(args[4],16),int(args[5],16))
la,lb=lits(A),lits(B)
print('ins',len(A),len(B)); print('only A',dict((la-lb).most_common(40))); print('only B',dict((lb-la).most_common(40)))
