"""Static stack-balance check of every mission script under the FSM.md VM model.

For each machine, walk every path from its entry with the SP depth relative to BP (entry = 1: BP[0] is the return
slot). The model is consistent if (a) every instruction is reached with one depth, (b) depth never drops below 1
(below the frame), (c) `ret n` pops exactly the n arguments (n == n_args for machine entries), (d) arga/argv
indices address live slots: locals 1..depth-1 or parameters -(n_args+1)..-2.
"""
import sys, os, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fmt"))
import bwd2x

problems, checked, machines = [], 0, 0
for p in sorted(glob.glob(r"C:\Users\james\i76-map\sandbox-gog\main\app\miss16\*.MSN")):
    d = bwd2x.decode(open(p, "rb").read(), ".msn")
    v = bwd2x.chunks(d, "FSM")[0][2].value
    if not v:
        continue
    code = v["code"]
    depth_at = {}
    for mi, m in enumerate(v["machines"]):
        machines += 1
        na = m["n_args"]
        work = [(m["start"], 1)]
        seen = set()
        while work:
            ip, sp = work.pop()
            while True:
                if (ip, sp) in seen:
                    break
                seen.add((ip, sp))
                prev = depth_at.setdefault((os.path.basename(p), ip), sp)
                if prev != sp:
                    problems.append((p, mi, ip, "depth %d vs %d" % (prev, sp)))
                op, a = code[ip]["op"], code[ip]["arg"]
                checked += 1
                nxt = ip + 1
                if op == 1:
                    sp += 1
                elif op in (4, 5):
                    ok = (1 <= a < sp) or (-(na + 1) <= a <= -2)
                    if not ok:
                        problems.append((p, mi, ip, "slot %d outside frame (sp %d, n_args %d)" % (a, sp, na)))
                elif op == 6:
                    sp += a
                elif op == 7:
                    sp -= a
                    if sp < 1:
                        problems.append((p, mi, ip, "drop below frame"))
                elif op == 8:
                    nxt = a
                elif op == 9:
                    work.append((a, sp))
                elif op == 10:
                    work.append((a, sp)); break
                elif op == 12:
                    if a != na:
                        problems.append((p, mi, ip, "ret %d with %d args" % (a, na)))
                    break
                elif op in (2, 3, 11):
                    problems.append((p, mi, ip, "unexpected opcode %d" % op))
                    break
                ip = nxt
print("machines %d, instruction visits %d, problems %d" % (machines, checked, len(problems)))
for x in problems[:20]:
    print(" ", x)
