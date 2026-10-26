"""Create or refresh the public "i76-everywhere roadmap" project (GitHub Projects v2) from the repo's issues.

Needs a gh token with the project scope:  gh auth refresh -s project,read:project
Run:  python -I tools/roadmap/setup-project.py            (create if missing, add every issue, set the fields)
      python -I tools/roadmap/setup-project.py --dry      (print what each issue would get; no project calls)

Fields (set from each issue; re-running is safe and updates them):
  Status   Done if the issue is closed, else Waiting for QA if it has the needs-qa label, else Now / Next / Later
           from its priority/* label, else Backlog
  Evidence measured / designed / idea from its evidence/* label
  Area     the first area/* label
  Effort   S / M / L from the body's "**Effort:** X" line
Views: "QA queue" (VIEWS) is created if missing; the others were made in the web UI (docs/process/PROCESS.md "Project board").
"""
import json, re, subprocess, sys

OWNER = "therealjkvalentine"
REPO = f"{OWNER}/i76-everywhere"
TITLE = "i76-everywhere roadmap"
NUMBER = 1  # the board that carries the hand-made views (github.com/users/<owner>/projects/1); matched before TITLE
QA_LABEL = "needs-qa"  # open + this label = Status "Waiting for QA" (docs/process/PROCESS.md "QA issues")
FIELDS = {
    "Status": ["Backlog", "Now", "Waiting for QA", "Next", "Later", "Done"],
    "Evidence": ["measured", "designed", "idea"],
    "Area": ["graphics", "multiplayer", "mac", "deck", "windows", "ffb-haptics", "audio-music", "content", "installer-kit", "docs"],
    "Effort": ["S", "M", "L"],
}
COLORS = {"Backlog": "GRAY", "Now": "RED", "Next": "YELLOW", "Later": "BLUE", "Waiting for QA": "PURPLE", "Done": "GREEN"}
VIEWS = [("QA queue", "TABLE_LAYOUT", 'status:"Waiting for QA"')]  # created if missing; existing views are left alone


def gh(*args, parse=True):
    out = subprocess.check_output(["gh", *args], text=True, encoding="utf-8")
    return json.loads(out) if parse and out.strip() else out


def gql(query, **v):
    args = ["api", "graphql", "-f", "query=" + query]
    for k, x in v.items():
        args += ["-F" if isinstance(x, (int, bool)) else "-f", f"{k}={x}"]
    return gh(*args)


def values(issue):
    labels = [l["name"] for l in issue["labels"]]
    pick = lambda pre: next((l[len(pre):] for l in labels if l.startswith(pre)), None)
    if issue["state"] == "CLOSED":
        status = "Done"
    elif QA_LABEL in labels:
        status = "Waiting for QA"
    else:
        status = {"now": "Now", "next": "Next", "later": "Later"}.get(pick("priority/"), "Backlog")
    m = re.search(r"\*\*Effort:\*\*\s*([SML])\b", issue["body"] or "")
    return {"Status": status, "Evidence": pick("evidence/"), "Area": pick("area/"), "Effort": m.group(1) if m else None}


def main():
    issues = gh("issue", "list", "-R", REPO, "--state", "all", "-L", "1000", "--json", "number,title,state,labels,body,url")
    issues = [i for i in issues if not any(l["name"] in ("duplicate", "invalid") for l in i["labels"])]
    if "--dry" in sys.argv:
        for i in sorted(issues, key=lambda i: i["number"]):
            print(i["number"], values(i), i["title"][:70])
        print(len(issues), "issues")
        return

    projects = gh("project", "list", "--owner", OWNER, "--format", "json", "--limit", "100")["projects"]
    proj = (next((p for p in projects if p["number"] == NUMBER), None)
            or next((p for p in projects if p["title"] == TITLE), None))
    if not proj:
        proj = gh("project", "create", "--owner", OWNER, "--title", TITLE, "--format", "json")
        print("created project", proj["url"])
    num, pid = proj["number"], proj["id"]
    gh("project", "edit", str(num), "--owner", OWNER, "--visibility", "PUBLIC",
       "--description", "Shipping / designed / ideas for Interstate '76 everywhere. Vote on ideas in Discussions > Ideas.", parse=False)
    try:
        gh("project", "link", str(num), "--owner", OWNER, "--repo", REPO, parse=False)
    except subprocess.CalledProcessError:
        pass  # already linked

    def field_map():
        fl = gh("project", "field-list", str(num), "--owner", OWNER, "--format", "json", "--limit", "100")["fields"]
        return {f["name"]: f for f in fl}

    fm = field_map()
    for name, opts in FIELDS.items():
        f = fm.get(name)
        if f is None:
            gh("project", "field-create", str(num), "--owner", OWNER, "--name", name, "--data-type", "SINGLE_SELECT",
               "--single-select-options", ",".join(opts), parse=False)
        elif [o["name"] for o in f.get("options", [])] != opts:
            # set the options in this order, passing the id of each option that already exists so items keep their
            # values; an option that is not in FIELDS is kept (appended), never dropped
            old = {o["name"]: o["id"] for o in f.get("options", [])}
            names = opts + [x for x in old if x not in opts]
            o = ",".join('{%sname:%s,color:%s,description:""}' % ("id:%s," % json.dumps(old[x]) if x in old else "",
                                                                  json.dumps(x), COLORS.get(x, "GRAY")) for x in names)
            gql("mutation($f:ID!){updateProjectV2Field(input:{fieldId:$f,singleSelectOptions:[%s]}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}" % o,
                f=f["id"])
    fm = field_map()

    views = gql("query($o:String!,$n:Int!){user(login:$o){projectV2(number:$n){views(first:50){nodes{name}}}}}",
                o=OWNER, n=num)["data"]["user"]["projectV2"]["views"]["nodes"]
    for name, layout, flt in VIEWS:
        if name not in [v["name"] for v in views]:
            vid = gql("mutation($p:ID!,$n:String!){createProjectV2View(input:{projectId:$p,name:$n,layout:%s}){projectV2View{id}}}"
                      % layout, p=pid, n=name)["data"]["createProjectV2View"]["projectV2View"]["id"]
            gql("mutation($v:ID!,$f:String!){updateProjectV2View(input:{viewId:$v,filter:$f}){projectV2View{id}}}", v=vid, f=flt)
            print("created view", name)

    items = gh("project", "item-list", str(num), "--owner", OWNER, "--format", "json", "--limit", "2000")["items"]
    have = {it.get("content", {}).get("url"): it["id"] for it in items}
    for i in sorted(issues, key=lambda i: i["number"]):
        iid = have.get(i["url"]) or gh("project", "item-add", str(num), "--owner", OWNER, "--url", i["url"], "--format", "json")["id"]
        for name, val in values(i).items():
            if not val:
                continue
            f = fm[name]
            oid = next(o["id"] for o in f["options"] if o["name"] == val)
            gh("project", "item-edit", "--id", iid, "--project-id", pid, "--field-id", f["id"],
               "--single-select-option-id", oid, parse=False)
        print(i["number"], values(i)["Status"], i["title"][:60])
    print("project:", proj["url"])


if __name__ == "__main__":
    main()
