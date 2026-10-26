#!/usr/bin/env python3
"""Gate Q (budget and stop rule; method doc 4.3).

Per function: 150 K tokens across all attempts, then parked `budget-exhausted` with the last blocker sentence.
Per week: a token cap set by the user (open decision 4; read from status\\budget.json {"weekly_cap": N} when
present, else unset = note only). Process: below 5 accepted rows/day with a full queue halts drafting.

Reads status\\queue.json (tokens_used per item, leases, attempts) and status\\progress.json / merge-log.jsonl
(accepted rows per day). Fails when: an item over 150,000 tokens is not parked `budget-exhausted` with a blocker;
a batch row (--batch) belongs to a parked item; the weekly cap is exceeded; the last full day had < 5 accepted
rows while >= 50 items were open (the halt condition; the gate reports it as a failure so the loop stops).
"""
import os, sys, json, time, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, parse_addr

PER_FUNCTION = 150000
MIN_ROWS_PER_DAY = 5
FULL_QUEUE = 50


def main():
    ctx, args = make("gateQ", __doc__)
    qp = ctx.path("status", "queue.json")
    if not os.path.exists(qp):
        ctx.note("no status/queue.json yet"); return ctx.finish()
    q = json.load(open(qp, encoding="utf-8"))
    items = q.get("items", [])
    by = {it["addr"]: it for it in items}
    over = 0
    for it in items:
        t = int(it.get("tokens_used") or 0)
        mc = it.get("method_change") or {}
        limit = int(mc.get("budget") or PER_FUNCTION)   # a recorded method change may carry its own budget (lease.item_budget)
        if t > limit:
            over += 1
            # parked = budget-exhausted, or rejected/done (no further attempts), always with a blocker sentence
            if it.get("status") not in ("budget-exhausted", "rejected", "done") or not it.get("blocker"):
                ctx.fail("%s used %d tokens (> %d) but is not parked budget-exhausted with a blocker sentence" % (it["addr"], t, limit))
    if ctx.batch:
        for r in ctx.batch_rows("functions"):
            it = by.get("0x%x" % parse_addr(r["addr"]))
            if it and it.get("status") == "budget-exhausted":
                ctx.fail("%s is parked budget-exhausted; a new attempt needs a method change recorded in the queue item" % r["addr"])
    cap = None
    bp = ctx.path("status", "budget.json")
    if os.path.exists(bp):
        cap = json.load(open(bp, encoding="utf-8")).get("weekly_cap")
    week_tokens = 0
    lp = ctx.path("status", "merge-log.jsonl")
    per_day = {}
    if os.path.exists(lp):
        cutoff = time.time() - 7 * 86400
        for line in open(lp, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            ts = e.get("time", "")
            try:
                t = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").timestamp()
            except ValueError:
                continue
            if t >= cutoff:
                week_tokens += int(e.get("tokens", 0) or 0)
            day = ts[:10]
            per_day[day] = per_day.get(day, 0) + int(e.get("accepted", 0) or 0)
    if cap is not None and week_tokens > cap:
        ctx.fail("weekly token cap %d exceeded: %d tokens merged in the last 7 days" % (cap, week_tokens))
    open_items = sum(1 for it in items if it.get("status") in ("open", "leased", "requeued"))
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    if yesterday in per_day and per_day[yesterday] < MIN_ROWS_PER_DAY and open_items >= FULL_QUEUE:
        ctx.fail("stop rule: %d accepted rows on %s with %d open items (< %d/day with a full queue): drafting halts pending a method change" %
                 (per_day[yesterday], yesterday, open_items, MIN_ROWS_PER_DAY))
    ctx.note("items %d, over-budget %d, open %d, week tokens %d (cap %s), accepted per day %s" %
             (len(items), over, open_items, week_tokens, cap, json.dumps(per_day, sort_keys=True)))
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
