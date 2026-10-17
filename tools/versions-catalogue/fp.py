import sys, hashlib, pefile, datetime, os
def vinfo(pe):
    out={}
    try:
        for fi in pe.FileInfo:
            for e in fi:
                if hasattr(e,'StringTable'):
                    for st in e.StringTable:
                        for k,v in st.entries.items(): out[k.decode(errors='ignore')]=v.decode(errors='ignore')
    except Exception as ex: pass
    try:
        ff=pe.VS_FIXEDFILEINFO[0]; out['_fixed']='%d.%d.%d.%d'%(ff.FileVersionMS>>16,ff.FileVersionMS&0xffff,ff.FileVersionLS>>16,ff.FileVersionLS&0xffff)
    except Exception: pass
    return out
for p in sys.argv[1:]:
    b=open(p,'rb').read()
    md5=hashlib.md5(b).hexdigest(); sha=hashlib.sha256(b).hexdigest()
    try:
        pe=pefile.PE(data=b)
        ts=datetime.datetime.utcfromtimestamp(pe.FILE_HEADER.TimeDateStamp).strftime('%Y-%m-%d %H:%M:%S')
        imps=[e.dll.decode() for e in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[])]
        lv='%d.%02d'%(pe.OPTIONAL_HEADER.MajorLinkerVersion,pe.OPTIONAL_HEADER.MinorLinkerVersion)
        print(f"{p}\n  size {len(b)} md5 {md5} sha256 {sha[:16]}.. link {ts}Z linker {lv}\n  imports {imps}\n  ver {vinfo(pe)}")
    except Exception as ex:
        print(f"{p}\n  size {len(b)} md5 {md5} (not PE: {ex})")
