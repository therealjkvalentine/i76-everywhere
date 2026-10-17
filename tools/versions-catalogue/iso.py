import struct,sys,os
class Iso:
    def __init__(s,p): s.f=open(p,'rb')
    def sec(s,n,c=1): s.f.seek(n*2048); return s.f.read(2048*c)
    def root(s):
        pvd=s.sec(16); r=pvd[156:156+34]; return struct.unpack_from('<I',r,2)[0],struct.unpack_from('<I',r,10)[0]
    def ls(s,lba,size):
        s.f.seek(lba*2048); d=s.f.read(size); out=[]; i=0
        while i<len(d):
            l=d[i]
            if l==0: i=((i//2048)+1)*2048; continue
            e=d[i:i+l]; ext=struct.unpack_from('<I',e,2)[0]; sz=struct.unpack_from('<I',e,10)[0]; fl=e[25]; nl=e[32]; nm=e[33:33+nl]
            dt=e[18:25]
            if nm not in (b'\0',b'\1'): out.append((nm.decode('latin-1').split(';')[0],ext,sz,bool(fl&2),'%04d-%02d-%02d %02d:%02d'%(1900+dt[0],dt[1],dt[2],dt[3],dt[4])))
            i+=l
        return out
    def walk(s,lba=None,size=None,pre=''):
        if lba is None: lba,size=s.root()
        for nm,ext,sz,isd,dt in s.ls(lba,size):
            yield pre+nm,ext,sz,isd,dt
            if isd: yield from s.walk(ext,sz,pre+nm+'/')
    def get(s,ext,sz): s.f.seek(ext*2048); return s.f.read(sz)
if __name__=='__main__':
    iso=Iso(sys.argv[1])
    for p,ext,sz,isd,dt in iso.walk():
        if len(sys.argv)>2 and sys.argv[2]=='-d' or not isd: print(f'{sz:>11} {dt} {p}{"/" if isd else ""}')
