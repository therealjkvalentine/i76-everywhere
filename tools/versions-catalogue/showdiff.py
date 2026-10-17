import pickle,difflib,sys
T=pickle.load(open('functables.pkl','rb'))
o=sys.argv[1]
for pair in sys.argv[2:]:
    a,b=[int(x,16) for x in pair.split(':')]
    A=T['r10'][a][2]; B=T[o][b][2]
    print('=====',hex(a),'->',o,hex(b),len(A),len(B))
    for l in difflib.unified_diff(A,B,lineterm='',n=1): print(l)
