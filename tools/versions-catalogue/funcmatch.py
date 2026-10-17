import pefile,capstone,re,hashlib,struct,sys,collections,json
def load(p):
    pe=pefile.PE(p); ib=pe.OPTIONAL_HEADER.ImageBase
    t=[s for s in pe.sections if s.Name.startswith(b'.text')][0]
    code=t.get_data(); tva=ib+t.VirtualAddress
    img=pe.get_memory_mapped_image()
    return pe,ib,code,tva,img
def funcs(code,tva):
    starts=set()
    for m in re.finditer(b'\xe8',code):
        i=m.start()
        if i+5>len(code): continue
        tgt=tva+i+5+struct.unpack_from('<i',code,i+1)[0]
        if tva<=tgt<tva+len(code): starts.add(tgt)
    return sorted(starts)
cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
HEX=re.compile(r'0x[0-9a-f]+')
def norm(code,tva,ib,img,a,b):
    out=[]
    for ins in cs.disasm(code[a-tva:b-tva],a):
        ops=ins.op_str
        if ins.mnemonic.startswith('j') or ins.mnemonic=='call':
            out.append(ins.mnemonic+' T'); continue
        def rep(m):
            v=int(m.group(0),16)
            if 0x400000<=v<0x400000+len(img):
                # constant value for fpu loads
                if 'ptr [0x' in ops and ins.mnemonic.startswith(('fld','fmul','fadd','fsub','fdiv','fcom','fcomp','fsubr','fdivr')):
                    off=v-ib; sz=8 if 'qword' in ops else 4
                    return 'C'+img[off:off+sz].hex()
                if ins.mnemonic=='cmp' and False: pass
                return 'A'
            return m.group(0)
        out.append(ins.mnemonic+' '+HEX.sub(rep,ops))
    return out
def table(p):
    pe,ib,code,tva,img=load(p); st=funcs(code,tva); st.append(tva+len(code)); res={}
    for a,b in zip(st,st[1:]):
        n=norm(code,tva,ib,img,a,b)
        res[a]=(hashlib.md5('\n'.join(n).encode()).hexdigest(),len(n),n)
    return res
if __name__=='__main__':
    import pickle
    T={k:table(v) for k,v in [x.split('=') for x in sys.argv[1:]]}
    pickle.dump(T,open('functables.pkl','wb'))
    for k,v in T.items(): print(k,len(v),'funcs')
