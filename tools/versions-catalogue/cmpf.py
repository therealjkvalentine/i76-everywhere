import pickle,difflib,sys
T=pickle.load(open('functables.pkl','rb'))
base=T['r10']
phys={0x472360:'physics_StepVehicle',0x46fe20:'CheckImpact',0x472890:'collision response',0x473600:'ground/tyre solver',0x4759b0:'lateral fn',0x474400:'solver part 474400',0x474bf0:'solver part 474bf0',0x475100:'solver part 475100',0x471860:'solver part 471860',0x4719f0:'solver part 4719f0',0x470030:'attitude solver',0x475cb0:'front-wheel steer',0x42a5d0:'terrain damage',0x451250:'StepperBegin',0x450fa0:'simclock_Update',0x429c70:'entity_TickVehicle',0x42b830:'entity update',0x408510:'AI team add',0x451210:'StepperInit'}
def best(n,other):
    L=len(n); cands=[(a,v) for a,v in other.items() if abs(v[1]-L)<=max(10,L*0.3)]
    bs=(0,None)
    for a,v in cands:
        r=difflib.SequenceMatcher(None,n,v[2],autojunk=False).quick_ratio()
        if r>bs[0]-0.0001:
            r=difflib.SequenceMatcher(None,n,v[2],autojunk=False).ratio()
            if r>bs[0]: bs=(r,a)
    return bs
for o in ['r106','r1081','r1083']:
    hs={v[0] for v in T[o].values()}
    same=sum(1 for v in base.values() if v[0] in hs)
    print(f'{o}: retail functions with an identical normalized body: {same}/{len(base)} ({100*same/len(base):.1f}%)')
for a,name in sorted(phys.items()):
    if a not in base: print(hex(a),name,'not a call-target start'); continue
    row=[hex(a),name,str(base[a][1])+' ins']
    for o in ['r106','r1081','r1083']:
        hs={v[0]:k for k,v in T[o].items()}
        if base[a][0] in hs: row.append(f'{o}=same@{hex(hs[base[a][0]])}')
        else:
            r,b=best(base[a][2],T[o]); row.append(f'{o}=CHANGED best {r:.3f}@{hex(b) if b else None}')
    print(' | '.join(row))
