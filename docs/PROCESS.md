# How work is tracked

**Issues are the task layer.** Every piece of work, open or done, is a GitHub issue. Records (`docs/records/*.md`) hold the evidence;
the issue holds the task, links the record, and is closed by the commit that lands it. [ROADMAP.md](../ROADMAP.md) is the overview.

**Every change lands with its record linked from the issue.** A change that alters behaviour gets a record (what was measured, n, where
the evidence is) and the issue links it before it is closed.

**Automated agents triage issues.** A maintainer's agent reads new issues and may reply: it asks for missing logs, adds labels, links
duplicates and related records. The developer decides what gets built and when.

## Labels

| group | values | meaning |
|---|---|---|
| `area/*` | graphics, multiplayer, mac, deck, windows, ffb-haptics, audio-music, content, installer-kit, docs | which part of the project |
| `kind/*` | bug, feature, idea, research | bug = works wrongly; feature = new or changed; idea = big, not designed, vote in Discussions; research = a question to answer before building |
| `evidence/*` | measured, designed, idea | how much is known: measured = a reproduced run or measurement in a record; designed = a written design or spike, not measured end to end; idea = discussed only |
| `priority/*` | now, next, later | now = being worked on or next up for the current milestone; next = after that; later = wanted, no date |
| other | `good first issue`, `help wanted`, `needs-triage`, `multiplayer` | the last two come from the issue forms; `needs-triage` is removed once an area / kind / priority is set |

## Milestones

**v0.8.0** the current draft release; **v0.9** builder-testers (first outside builders on Windows / Mac / Deck, internet play, feedback
loop); **v1.0** after the first feedback round; **Later** no date.

## Issue body

What / Why / Evidence (level + record link) / Design (inline, a link to the design file, or "none yet - ideas welcome") / Done when /
`**Effort:** S|M|L (~N lane-days)` (S under a day, M 1-3, L a week or more). In-progress issues start with a `Status: in progress` line.

## Project board

"i76-everywhere roadmap" (GitHub Projects v2, public, linked to the repo: https://github.com/users/therealjkvalentine/projects/1).
Fields: **Status** (Backlog / Now / Waiting for QA / Next / Later / Done), **Evidence**, **Area**, **Effort**.
`tools/roadmap/setup-project.py` creates it and sets the fields from each issue's labels and state (closed = Done, `needs-qa` = Waiting
for QA, `priority/now` = Now, ...); re-running it is safe and keeps every existing Status option. Views: **Board** grouped by Status;
**Roadmap** (timeline) by Milestone; **Done** = a table filtered `status:Done` (made in the web UI); **QA queue** = a table filtered
`status:"Waiting for QA"` (https://github.com/users/therealjkvalentine/projects/1/views/5; the script creates it if missing).

## QA issues: work that needs a person at a machine

When a unit cannot be finished by a script - it needs someone to play, feel, watch, record, or rule on something - the lane files a
**QA issue** and moves on. Anyone with the hardware can pick one up; it is assigned to the developer only when it needs his own
machines or his ruling (a `Decide:` issue, the family LAN, the developer's Deck or wheel, captures for the launch video). Where a kit user
could do it, it also gets `help wanted`.

- **Title** `QA: <what is checked>` (a ruling: `Decide: <the question>`).
- **Labels** `needs-qa` + the area/kind labels; `help wanted` when an outside tester can do it. **Status** follows the label: Waiting for QA.
- **Assignee** `therealjkvalentine` only when the developer's own hardware or ruling is needed; otherwise unassigned.
- **Milestone** the one the parent issue is in. Link the parent with `Refs #<n>`.

Body sections (in this order; `tools/roadmap/qa-template.md` is the copy to start from):

1. **Needs** - the hardware and copy, in words an outside tester understands: "a Windows PC with a force-feedback wheel", "a Mac with
   the Mac Kit apps", "two machines on one LAN", "a Steam Deck with a paired Xbox controller"; which copy (the Patch Kit release, the
   developer's main copy, a test copy) and which build (proxy md5 as it appears in the log).
2. **What to run** - the exact file and arguments, with generic paths: `<game folder>` = the folder with `i76.exe` (a Patch Kit install
   has `PLAY.bat` there too); repo-relative for tools (`tools\launch-video\RECORD-TAKE.bat`). Never a user name, drive letter, machine
   name or address.
3. **Steps** - numbered, 3-8.
4. **Acceptance criteria** - checkboxes, each one observable by the tester: "the force feedback is still on after Alt-Tab and back",
   "no `CRASH` line in `<game folder>\mciproxy.log`", "the log has `ffb-focus: focus back #1 ... effects STILL playing 2 of 3`".
5. **If it fails** - what to attach (which log, a screenshot, the time it happened).
6. **Context** - the record(s) in the repo that the test comes from.

Closing: when the boxes are ticked or the ruling is in a comment, the lane (or the coordinator) closes the issue with a one-line
summary and links the record that took the result; a failed box becomes a new bug issue linked from it. A ruling is copied into the
record or ROADMAP.md before the issue closes. Template commands:

```
gh issue create -R therealjkvalentine/i76-everywhere --title "QA: <what>" --body-file <body.md> --label needs-qa \
  --label area/<a> [--label "help wanted"] [--assignee therealjkvalentine] --milestone <m>
python -I tools/roadmap/setup-project.py      # adds it to the board with Status = Waiting for QA
```

## Privacy

Issues, discussions and the board are public. No personal names (say "the developer", "a tester"), no private paths, machine names or
addresses, no copyrighted game material, no exe bytes or addresses in an issue body (link the record instead).
