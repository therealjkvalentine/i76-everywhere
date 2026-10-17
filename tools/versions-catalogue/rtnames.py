import re,collections,sys
b=open(sys.argv[1],'rb').read()
pat=re.compile(rb'[A-Za-z0-9_~]{1,40}\.(?:exe|dll|zfs|zix|def|hlp|txt|smk|cnt|map|ini|doc|pdf|ttf|lst|EXE|DLL|ZFS|ZIX|DEF|HLP|TXT|SMK|CNT|MAP|INI|DOC|PDF|TTF|LST)\x00')
c=collections.Counter(n[:-1].decode().lower() for n in pat.findall(b))
print(len(c)); print(sorted(c.items()))
i=b.find(b'Version 1.0 -> 1.2'); print(b[i-200:i+200])
