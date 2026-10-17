import re,sys
BAD=re.compile(r'[^A-Za-z0-9_ .,%:\/=+#<>()!?\[\]\'"-]')
def S(p): return set(m.decode('latin-1') for m in re.findall(rb'[\x20-\x7e]{6,}',open(p,'rb').read()))
P=dict(x.split('=') for x in sys.argv[1:]); names=list(P); sets={k:S(v) for k,v in P.items()}
ok=lambda s: re.search(r'[a-z]{3}',s,re.I) and not BAD.search(s)
for a,b in zip(names,names[1:]):
    add=[s for s in sorted(sets[b]-sets[a]) if ok(s)]; rem=[s for s in sorted(sets[a]-sets[b]) if ok(s)]
    print(f'##### {a} -> {b}: +{len(add)} -{len(rem)}'); print(' ADDED:',' | '.join(add[:400])); print(' REMOVED:',' | '.join(rem[:200]))
