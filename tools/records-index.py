#!/usr/bin/env python3
"""records-index.py - write docs/records/README.md, the index of the dated lane records, grouped by topic.

    python tools/records-index.py           rewrite docs/records/README.md
    python tools/records-index.py --check   exit 1 if the file is not what this script would write (CI / pre-commit)

Each record gets: its date (from the file name, YYYY-MM-DD or YYYYMMDD; else the first date in its name, title or, for a .md,
its first 15 lines; else "undated"), its title (the first "# " heading; else the file name) and one topic (the first row of
TOPICS with a keyword that is a whole word of the file name, else of the title; else "Other"). Newest first inside a topic.
Records are never edited by this script.
Keep the keyword table small and ordered: a new record lands in the right group when its file name says what it is about.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RECORDS = os.path.join(os.path.dirname(HERE), "docs", "records")
OUT = os.path.join(RECORDS, "README.md")

# (topic, keywords). A keyword matches whole words of the file name (words split at - _ . and spaces), so LAN does not
# match PLAN. First match wins: the topics are ordered so the narrower question comes first.
TOPICS = [
    ("Frame rate, simulation and physics", ["FPS", "FRAME", "FRAMERATE", "TICK", "STEP", "PHYSICS", "CLOCKS", "HANDLING",
                                            "ARCADE", "ENVELOPE", "REBASELINE", "FINGERPRINT", "W95", "STABILITY", "BENCH"]),
    ("Multiplayer, co-op and AI opponents", ["MP", "LAN", "COOP", "LOBBY", "RELAY", "INTERNET", "GAME-NIGHT", "AI"]),
    ("Mac", ["MAC"]),
    ("Steam Deck", ["DECK"]),
    ("Nitro Pack", ["NITRO"]),
    ("Force feedback, rumble and motion", ["FFB", "RUMBLE", "MOTION", "HEADLOOK"]),
    ("Audio and music", ["MUSIC", "SOUND"]),
    ("Controls and input", ["CONTROLS", "INPUT", "ANALOG", "CURSOR", "DEBUG-MENU"]),
    ("Menus, saves and the save editor", ["MENU", "SAVE", "SAVES", "SHELL", "MOUNT", "DIFFICULTY", "SETTINGS", "CUTSCENES"]),
    ("Graphics and rendering", ["GRAPHICS", "RENDER", "RENDERER", "TERRAIN", "FARCLIP", "FAR-EDGE", "MIRROR", "TEXTURE",
                                "TEXTURES", "SUPERSAMPLE", "UPSCALE", "DGVOODOO", "HEALTH-BAR", "WINDOWED", "1080P", "STUTTER"]),
    ("Status, backlogs and overnight runs", ["BACKLOG", "STATUS", "OVERNIGHT", "OWNER-NOTES", "OWNER-FEEDBACK", "READY-TO-TEST",
                                             "PLAYTEST", "OUTREACH"]),
    ("Install, kits and releases", ["INSTALL", "INSTALLER", "KIT", "TESTER-BUILD", "LAUNCHERS", "FRESH-GOG", "DAILY-DRIVER",
                                    "PRIVACY", "PROXY-CLEANUP", "SETUP", "RUNNING-I76-EVERYWHERE", "PORTS", "WHAT-THIS-IS",
                                    "PROMOTION"]),
    ("Reverse engineering, versions and research", ["RE", "GHIDRA", "STATIC", "STRUCTS", "FRESH-START", "EXE", "EMU", "DEV",
                                                    "BASE-DECISION", "VERSIONS", "WHAT-IS-STOCK", "REIMPLEMENTATION", "REMAKE",
                                                    "RETAIL", "FIX-INVENTORY", "TRAINER", "DEBUG", "FINDINGS", "RESEARCH", "LAB",
                                                    "HARDWARE"]),
]

DATE_NAME = re.compile(r"(20\d\d)-?(\d\d)-?(\d\d)")
DATE_TEXT = re.compile(r"(20\d\d)-(\d\d)(?:-(\d\d))?")


def title_of(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if line.startswith("# "):
                    return line[2:].strip()
                if i > 40:
                    break
    except OSError:
        pass
    return ""


def date_of(name, title, path):
    m = DATE_NAME.search(name)
    if m:
        return "%s-%s-%s" % m.groups()
    for text in (name, title, head_of(path) if name.endswith(".md") else ""):
        m = DATE_TEXT.search(text)
        if m:
            return "-".join(g for g in m.groups() if g)
    return "undated"


def head_of(path, lines=15):
    """The first lines of a record, where its own date usually is ("Written 2026-07-18", a dated note)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readline() for _ in range(lines))
    except OSError:
        return ""


def topic_of(name, title):
    for where in (name.upper(), title.upper()):
        for topic, keys in TOPICS:
            if any(re.search(r"(?:^|[-_. ])" + re.escape(k) + r"(?:[-_. ]|$)", where) for k in keys):
                return topic
    return "Other"


def plain(title):
    """A heading as link text: no markdown emphasis or code ticks, no brackets that would end the link."""
    t = re.sub(r"[`*_]", "", title)
    return t.replace("[", "(").replace("]", ")")


def build():
    rows = []
    for name in sorted(os.listdir(RECORDS)):
        path = os.path.join(RECORDS, name)
        if name == "README.md" or not os.path.isfile(path) or not name.endswith((".md", ".txt")):
            continue
        title = title_of(path) if name.endswith(".md") else ""
        rows.append((topic_of(name, title), date_of(name, title, path), name, plain(title) or name))
    order = [t for t, _ in TOPICS] + ["Other"]
    out = [
        "# Records: the index",
        "",
        "Generated by [`tools/records-index.py`](../../tools/records-index.py) from the files in this folder: do not edit by hand,",
        "run `python tools/records-index.py` after adding a record (`--check` says whether this page is current).",
        "",
        "A record is a dated account of one lane, test run, survey or research pass. Records are not rewritten: later facts",
        "are added as dated notes at the top, so read those first. A path written inside a record is the path on the day it",
        "was written (the repository was reorganised on 2026-10-03 and 2026-10-26; [the docs hub](../README.md) says where",
        "things are now). Living docs are in [`../guides/`](../guides/), [`../engine/`](../engine/), [`../research/`](../research/)",
        "and [`../process/`](../process/).",
        "",
        "%d records. Date from the file name (else the first date in the title or the opening lines); topic from a keyword in" % len(rows),
        "the file name (or the title), the first match in the script's table.",
        "",
    ]
    present = [t for t in order if any(r[0] == t for r in rows)]
    out.append(" | ".join("[%s](#%s)" % (t, re.sub(r"[^a-z0-9 -]", "", t.lower()).replace(" ", "-")) for t in present))
    for topic in present:
        out += ["", "## " + topic, ""]
        sel = sorted((r for r in rows if r[0] == topic), key=lambda r: (r[1] == "undated", r[1], r[2]), reverse=False)
        dated = sorted((r for r in sel if r[1] != "undated"), key=lambda r: (r[1], r[2]), reverse=True)
        undated = sorted((r for r in sel if r[1] == "undated"), key=lambda r: r[2])
        for _, date, name, title in dated + undated:
            out.append("- %s [%s](%s)" % (date, title, name.replace(" ", "%20")))
    return "\n".join(out) + "\n"


def main():
    text = build()
    if "--check" in sys.argv:
        try:
            cur = open(OUT, encoding="utf-8").read().replace("\r\n", "\n")
        except OSError:
            cur = ""
        if cur != text:
            print("docs/records/README.md is out of date: run python tools/records-index.py")
            return 1
        print("docs/records/README.md is current")
        return 0
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote %s" % os.path.relpath(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
