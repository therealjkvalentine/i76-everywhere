#!/usr/bin/env python3
"""lease.py - leases on status\\queue.json for the drafters (method doc section 6; Task 8).

    python tools\\lease.py next --view c|pcode --holder <agent-id> [--ttl 3600]      -> JSON {addr,key,lease,...}
    python tools\\lease.py release --lease <id> --result drafted|abandon --tokens N [--blocker "..."]
    python tools\\lease.py merge-result --key <addr8> --result accepted|rejected|requeue [--reason "..."] [--tokens N]
    python tools\\lease.py expire            sweep expired leases back to open (attempts += 1)
    python tools\\lease.py status            counts per state and tier; oldest lease age
    python tools\\lease.py show --key <addr8>

Rules enforced here: an address is leased to one holder per view; the two views of one address never go to
the same holder (G4 independence); rank order; items parked `budget-exhausted` / `done` / `rejected` are never
leased; an item over 150,000 tokens is parked `budget-exhausted` on release and needs a blocker sentence (gate Q);
every write goes to .tmp, is renamed, then read back (H3). A lock file status\\queue.lock serialises writers.
"""
import os, sys, json, time, argparse, datetime

TOOLS = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MAP = os.path.dirname(TOOLS)
BUDGET = 150000


def item_budget(it):
    """Gate Q per-item budget: 150 K unless the item records a method change with its own budget
    (queue item field method_change {time, note, budget}; gateQ_budget.py reads the same field)."""
    mc = it.get("method_change") or {}
    return int(mc.get("budget") or BUDGET)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ts_to_epoch(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").timestamp()


class Queue:
    def __init__(self, M):
        self.M = M
        self.path = os.path.join(M, "status", "queue.json")
        self.lock = self.path + ".lock"
        self.q = None

    def __enter__(self):
        for _ in range(300):
            try:
                fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, ("%d %s" % (os.getpid(), now())).encode()); os.close(fd)
                break
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.lock) > 120:
                        os.remove(self.lock); continue
                except OSError:
                    pass
                time.sleep(0.1)
        else:
            raise SystemExit("queue.lock held for > 30 s: %s" % self.lock)
        self.q = json.load(open(self.path, encoding="utf-8"))
        self.by_key = {it["key"]: it for it in self.q["items"]}
        return self

    def __exit__(self, et, ev, tb):
        try:
            if et is None and self.dirty:
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(self.q, fh, indent=1)
                os.replace(tmp, self.path)
                back = json.load(open(self.path, encoding="utf-8"))
                if len(back["items"]) != len(self.q["items"]):
                    raise RuntimeError("readback mismatch after write")
        finally:
            try:
                os.remove(self.lock)
            except OSError:
                pass

    dirty = False

    def expire(self):
        n = 0
        t = time.time()
        for it in self.q["items"]:
            for v, st in it["views"].items():
                L = st.get("lease")
                if L and ts_to_epoch(L["expires"]) < t:
                    st["lease"] = None; st["state"] = "open"; st["attempts"] = st.get("attempts", 0) + 1
                    it["history"].append({"time": now(), "event": "lease-expired", "view": v, "lease": L["id"]})
                    n += 1
            if it["status"] == "leased" and not any(s.get("lease") for s in it["views"].values()):
                it["status"] = "open"
        if n:
            self.dirty = True
        return n

    def next(self, view, holder, ttl, key=None):
        self.expire()
        # status\hotlist.txt (one 8-hex key or 0x address per line, comments with #): leased before rank order
        hot = []
        hp = os.path.join(self.M, "status", "hotlist.txt")
        if os.path.exists(hp):
            for line in open(hp, encoding="utf-8"):
                line = line.split("#", 1)[0].strip()
                if line:
                    hot.append("%08x" % int(line, 16))
        order = [it for k in hot for it in self.q["items"] if it["key"] == k] + [it for it in self.q["items"] if it["key"] not in hot]
        for it in order:
            if key and it["key"] != key:
                continue   # --key: lease exactly this item (redraft/reconcile rounds), rank order otherwise
            if it["status"] not in ("open", "requeued", "leased"):
                continue
            if view not in it["views_available"]:
                continue
            st = it["views"][view]
            if st["state"] != "open" or st.get("lease"):
                continue
            other = it["views"]["pcode" if view == "c" else "c"]
            if other.get("lease") and other["lease"]["holder"] == holder:
                continue
            if other.get("holder") == holder:
                continue  # the same agent drafted the other view earlier
            lid = "L-%s-%s-%s" % (it["key"], view, time.strftime("%Y%m%dT%H%M%S"))
            st["lease"] = {"id": lid, "holder": holder, "since": now(),
                           "expires": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + ttl))}
            st["state"] = "leased"
            it["status"] = "leased"
            it["history"].append({"time": now(), "event": "lease", "view": view, "lease": lid, "holder": holder})
            self.dirty = True
            k = it["key"]
            files = {"c": "ghidra/export/functions/%s.c" % k, "pcode": "ghidra/export/functions/%s.pcode" % k,
                     "proposal": "functions/%s.proposal.md" % k if view == "c" else "functions/%s.proposal.pcode.md" % k,
                     "existing_md": "functions/%s.md" % k}
            return {"addr": it["addr"], "key": k, "name": it["name"], "lease": lid, "view": view, "ttl": ttl,
                    "tier": it["tier"], "rank": it["rank"], "size": it["size"], "c_lines": it["c_lines"],
                    "tokens_used": it["tokens_used"], "budget_left": item_budget(it) - it["tokens_used"],
                    "requeue": it.get("requeue"), "files": files, "expires": st["lease"]["expires"]}
        return None

    def find_lease(self, lid):
        for it in self.q["items"]:
            for v, st in it["views"].items():
                if st.get("lease") and st["lease"]["id"] == lid:
                    return it, v, st
        return None, None, None

    def release(self, lid, result, tokens, blocker):
        it, v, st = self.find_lease(lid)
        if it is None:
            raise SystemExit("no live lease %s" % lid)
        holder = st["lease"]["holder"]
        st["lease"] = None
        st["tokens"] = st.get("tokens", 0) + tokens
        st["holder"] = holder
        it["tokens_used"] += tokens
        it["attempts"] += 1
        st["attempts"] = st.get("attempts", 0) + 1
        if result == "drafted":
            st["state"] = "drafted"
            st["proposal"] = "functions/%s.proposal%s.md" % (it["key"], "" if v == "c" else ".pcode")
        else:
            st["state"] = "open"
        both = all(s["state"] == "drafted" for k, s in it["views"].items() if k in it["views_available"])
        it["status"] = "review" if both else ("open" if not any(s.get("lease") for s in it["views"].values()) else "leased")
        if blocker:
            it["blocker"] = blocker
        if it["tokens_used"] > item_budget(it):
            it["status"] = "budget-exhausted"
            if not it.get("blocker"):
                raise SystemExit("%s exceeds %d tokens and needs --blocker (one falsifiable sentence, gate Q)" % (it["addr"], item_budget(it)))
        it["history"].append({"time": now(), "event": "release", "view": v, "lease": lid, "result": result, "tokens": tokens,
                              "holder": holder, "blocker": blocker})
        self.dirty = True
        return it

    def merge_result(self, key, result, reason, tokens):
        it = self.by_key.get(key)
        if it is None:
            raise SystemExit("no queue item %s" % key)
        if tokens:
            it["tokens_used"] += tokens
        if result == "accepted":
            it["status"] = "done"
        elif result == "rejected":
            it["status"] = "rejected"; it["blocker"] = reason or it.get("blocker")
        else:
            it["status"] = "requeued"
            it["requeue"] = {"time": now(), "reason": reason,
                             "views": {v: s.get("proposal") for v, s in it["views"].items()}}
            for s in it["views"].values():
                s["state"] = "open"; s["lease"] = None; s.pop("holder", None)
            if it["tokens_used"] > item_budget(it):
                it["status"] = "budget-exhausted"; it["blocker"] = it.get("blocker") or reason
        it["history"].append({"time": now(), "event": "merge", "result": result, "reason": reason})
        self.dirty = True
        return it


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["next", "release", "merge-result", "expire", "status", "show"])
    ap.add_argument("--map", default=DEFAULT_MAP)
    ap.add_argument("--view", choices=["c", "pcode"])
    ap.add_argument("--holder")
    ap.add_argument("--ttl", type=int, default=None)
    ap.add_argument("--lease")
    ap.add_argument("--result")
    ap.add_argument("--tokens", type=int, default=0)
    ap.add_argument("--blocker")
    ap.add_argument("--reason")
    ap.add_argument("--key")
    a = ap.parse_args()
    with Queue(a.map) as Q:
        if a.cmd == "next":
            if not a.view or not a.holder:
                ap.error("next needs --view and --holder")
            r = Q.next(a.view, a.holder, a.ttl or Q.q.get("lease_ttl_seconds", 3600), key=a.key)
            print(json.dumps(r, indent=1) if r else json.dumps({"addr": None, "why": "queue empty for view %s" % a.view}))
            return 0 if r else 3
        if a.cmd == "release":
            if not a.lease or a.result not in ("drafted", "abandon"):
                ap.error("release needs --lease and --result drafted|abandon")
            it = Q.release(a.lease, a.result, a.tokens, a.blocker)
            print(json.dumps({"addr": it["addr"], "status": it["status"], "tokens_used": it["tokens_used"], "views": {v: s["state"] for v, s in it["views"].items()}}))
            return 0
        if a.cmd == "merge-result":
            if not a.key or a.result not in ("accepted", "rejected", "requeue"):
                ap.error("merge-result needs --key and --result accepted|rejected|requeue")
            it = Q.merge_result(a.key, a.result, a.reason, a.tokens)
            print(json.dumps({"addr": it["addr"], "status": it["status"]}))
            return 0
        if a.cmd == "expire":
            print("expired %d leases" % Q.expire()); return 0
        if a.cmd == "show":
            it = Q.by_key.get(a.key)
            print(json.dumps(it, indent=1) if it else "no item %s" % a.key); return 0 if it else 1
        # status
        st = {}
        oldest = None
        for it in Q.q["items"]:
            st[it["status"]] = st.get(it["status"], 0) + 1
            for s in it["views"].values():
                if s.get("lease"):
                    age = time.time() - ts_to_epoch(s["lease"]["since"])
                    oldest = max(oldest or 0, age)
        print(json.dumps({"items": len(Q.q["items"]), "by_status": st, "by_tier": Q.q["counts"]["by_tier"],
                          "oldest_lease_seconds": None if oldest is None else int(oldest), "generated": Q.q["generated"]}, indent=1))
        return 0


if __name__ == "__main__":
    sys.exit(main())
