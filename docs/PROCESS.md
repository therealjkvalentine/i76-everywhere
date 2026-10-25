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

"i76-everywhere roadmap" (GitHub Projects v2, public, linked to the repo). Fields: **Status** (Backlog / Now / Next / Later / Done),
**Evidence**, **Area**, **Effort**. `tools/roadmap/setup-project.py` creates it and sets the fields from each issue's labels and state
(closed = Done, `priority/now` = Now, ...); re-running it is safe. Views are made in the web UI (the API cannot create them):
**Board** grouped by Status; **Roadmap** (timeline) by Milestone; **Done** = a table filtered `status:Done`.

## Privacy

Issues, discussions and the board are public. No personal names (say "the developer", "a tester"), no private paths, machine names or
addresses, no copyrighted game material, no exe bytes or addresses in an issue body (link the record instead).
