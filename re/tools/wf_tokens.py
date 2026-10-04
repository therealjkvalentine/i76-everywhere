r"""wf_tokens.py - real token usage per (key, role) from a workflow run's agent transcripts (PILOT-1-REMERGE rule 1).

    python tools\wf_tokens.py <run dir>                    table: key, role (c | pcode | review | gate | fix), output tokens, cached reads
    python tools\wf_tokens.py <run dir> --json out.json    the same as JSON {key: {role: {"out": n, "in": n, "cache": n, "agents": n}}}

<run dir> is ...\subagents\workflows\wf_<id>\ (agent-*.jsonl inside). Sums message.usage fields per agent; the key and
role are read from the agent's first user message (the prompt names the key and the brief).
"""
import glob, json, os, re, sys, collections


def scan(run_dir):
    per = collections.defaultdict(lambda: {"out": 0, "in": 0, "cache": 0, "agents": 0})
    for f in glob.glob(os.path.join(run_dir, "agent-*.jsonl")):
        key = role = None; out = inp = cache = 0
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                j = json.loads(line)
            except ValueError:
                continue
            msg = j.get("message") if isinstance(j, dict) else None
            head0 = json.dumps(msg)[:300] if isinstance(msg, dict) else ""
            # the first user turn is now the harness relay of the user's request; the task prompt is the next one
            if key is None and isinstance(msg, dict) and msg.get("role") == "user" \
                    and not ("[Workflow harness" in head0 and "user request]" in head0) and "tool_result" not in head0:
                s = json.dumps(msg)
                m = (re.search(r"key ([0-9a-f]{8})", s) or re.search(r"--proposal ([0-9a-f]{8})", s)
                     or re.search(r"([0-9a-f]{8})\.proposal", s) or re.search(r"key=([0-9a-f]{8})", s))
                key = m.group(1) if m else "?"
                head = s[:900]
                role = ("fix" if "Narrow fix-up" in head else "gate" if "Report key" in head
                        else "review" if "reviewer" in head else "c" if "drafter-c" in head else "pcode" if "drafter-pcode" in head else "other")
            u = msg.get("usage") if isinstance(msg, dict) else None
            if isinstance(u, dict):
                out += u.get("output_tokens", 0); inp += u.get("input_tokens", 0)
                cache += u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        p = per[(key or "?", role or "?")]
        p["out"] += out; p["in"] += inp; p["cache"] += cache; p["agents"] += 1
    return per


def main():
    run_dir = sys.argv[1]
    per = scan(run_dir)
    if "--json" in sys.argv:
        outp = sys.argv[sys.argv.index("--json") + 1]
        nested = collections.defaultdict(dict)
        for (k, r), p in per.items():
            nested[k][r] = p
        json.dump(nested, open(outp, "w"), indent=1, sort_keys=True); print("wrote", outp)
        return
    tot_out = tot_cache = 0
    print("%-9s %-7s %8s %10s %s" % ("key", "role", "out", "cache", "agents"))
    for (k, r), p in sorted(per.items()):
        print("%-9s %-7s %8d %10d %d" % (k, r, p["out"], p["cache"], p["agents"]))
        tot_out += p["out"]; tot_cache += p["cache"]
    print("TOTAL out %d cache %d agents %d" % (tot_out, tot_cache, sum(p["agents"] for p in per.values())))


if __name__ == "__main__":
    main()
