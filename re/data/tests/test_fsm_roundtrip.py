import sys,glob,os
sys.path.insert(0,os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"fmt"))
sys.path.insert(0,r'C:\Users\james\i76-map\tools')
from i76fmt import bwd2
import fsm
ok=0;bad=0
for p in sorted(glob.glob(r'C:\Users\james\i76-map\sandbox-gog\main\app\miss16\*.MSN')):
    d=bwd2.parse(open(p,'rb').read())
    for c,_ in d.walk():
        if c.tag_str=='FSM':
            v=fsm.parse(c.body); s=fsm.serialise(v)
            t=fsm.disassemble(v,os.path.basename(p)); v2=fsm.assemble(t); s2=fsm.serialise(v2)
            if s==c.body and s2==c.body: ok+=1
            else: bad+=1; print('FAIL',p,s==c.body,s2==c.body,len(c.body),len(s2))
print(ok,bad)
