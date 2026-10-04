r"""merge_accepts.py - the merge worker's close-out for a workflow batch: merge every key whose review accepted, with the
review's measured output tokens as --review-tokens, and record the rest.

    python tools\merge_accepts.py <run dir> [--dry-run]

Reads the run's journal.jsonl (reviewer results carry verdict/key), tools\wf_tokens.py for the measured usage, and runs
`python tools\merge.py --proposal <key> --review-tokens <n> --log status\tasks\<run>-merge.log` per accepted key that
has no functions\<key>.md yet. Prints one line per key: merged / requeued / skipped, and a summary.

Keys whose gate said the names differ (G4 word disagreement) are requeued for real here, since the grind only ever
dry-runs them (added 2026-09-26: g1/g2 left such keys in "review" indefinitely): `merge.py --proposal <key>` requeues,
and both proposal files move to functions\history\<key>\requeue-<time>.<view>.md so the redrafters cannot read the
old other view (two g1/g2 drafters had to abandon keys after a grep surfaced it).
"""
import json, os, shutil, subprocess, sys, time
M = r"C:\Users\james\i76-map"
sys.path.insert(0, os.path.join(M, "tools"))
import wf_tokens


def main():
    run_dir = sys.argv[1].rstrip("\\/")
    dry = "--dry-run" in sys.argv
    keep_disputes = "--keep-disputes" in sys.argv   # leave name disputes in place (for a reconcile pass)
    run = os.path.basename(run_dir)
    verdicts, disputes = {}, {}
    for line in open(os.path.join(run_dir, "journal.jsonl"), encoding="utf-8"):
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if j.get("type") != "result":
            continue
        r = j.get("result") or j.get("value") or {}
        if isinstance(r, dict) and "verdict" in r and r.get("key"):
            verdicts[r["key"]] = r
        if isinstance(r, dict) and r.get("key") and r.get("both_views") and r.get("names_agree") is False:
            disputes[r["key"]] = r.get("g4_line") or ""
    usage = wf_tokens.scan(run_dir)
    log = os.path.join(M, "status", "tasks", "%s-merge.log" % run)
    merged = requeued = skipped = 0
    for key, r in sorted(verdicts.items()):
        rt = usage.get((key, "review"), {}).get("out", 0) or int(r.get("tokens_estimate") or 0)
        if os.path.exists(os.path.join(M, "functions", key + ".md")):
            print("%s skipped: already merged" % key); skipped += 1; continue
        if r["verdict"] != "accept":
            print("%s %s: %s" % (key, r["verdict"], (r.get("blocker") or "")[:120]))
            if not dry:
                subprocess.run([sys.executable, os.path.join(M, "tools", "merge.py"), "--proposal", key, "--review-tokens", str(rt), "--log", log], cwd=M, capture_output=True, text=True)
            requeued += 1; continue
        cmd = [sys.executable, os.path.join(M, "tools", "merge.py"), "--proposal", key, "--review-tokens", str(rt), "--log", log]
        if dry:
            cmd.append("--dry-run")
        p = subprocess.run(cmd, cwd=M, capture_output=True, text=True)
        lines = [l for l in p.stdout.splitlines()
                 if l.startswith(("MERGED", "REJECT", "NOTHING", "DRY RUN")) or (l.startswith("GATE ") and "FAIL" in l)]
        ok = any(l.startswith("MERGED") or (l.startswith("DRY RUN") and "green" in l) for l in lines)
        print("%s %s (review tokens %d): %s" % (key, "merged" if ok else "not merged", rt, (lines[-1] if lines else p.stdout[-200:])[:150]))
        merged += 1 if ok else 0
    stamp = time.strftime("%Y%m%dT%H%M%S")
    named = set()     # rows a batch merge already named (status past auto) are settled, not requeued
    for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8"):
        f = l.split("\t")
        if len(f) > 3 and f[0].startswith("0x") and f[3] != "auto":
            named.add("%08x" % int(f[0], 16))
    for key, line in sorted(disputes.items() if not keep_disputes else []):
        if key in verdicts or key in named or os.path.exists(os.path.join(M, "functions", key + ".md")):
            continue
        print("%s names differ -> requeue: %s" % (key, line[:120]))
        requeued += 1
        if dry:
            continue
        subprocess.run([sys.executable, os.path.join(M, "tools", "merge.py"), "--proposal", key, "--log", log], cwd=M, capture_output=True, text=True)
        hist = os.path.join(M, "functions", "history", key); os.makedirs(hist, exist_ok=True)
        for view, suffix in (("c", ".proposal.md"), ("pcode", ".proposal.pcode.md")):
            src = os.path.join(M, "functions", key + suffix)
            if os.path.exists(src):
                shutil.move(src, os.path.join(hist, "requeue-%s.%s.md" % (stamp, view)))
    print("SUMMARY %s: merged %d, requeued %d, skipped %d of %d reviewed" % (run, merged, requeued, skipped, len(verdicts)))


if __name__ == "__main__":
    main()
