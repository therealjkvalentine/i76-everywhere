"""
parse-asset-bible.py - turn DIVER's "Complete Asset Bible" (asset.doc) into markdown.

The Bible maps in-game object CLASS NAMES to dimensions and object type, which is what makes it
possible to read a level's object list and know what is actually there. i76render cites it for
exactly that.

Two quirks of the source:
  * it is an old BINARY .doc, so text is recovered by pulling printable runs out of the bytes
  * the recovered stream is OUT OF ORDER - Word stores a tail fragment before the document
    body, so the header/index appears partway through. Reordered around the font-table marker.

Row format:  <object name, space padded>  <CLASS NAME>  <X DIM>  <Z DIM>  <Class ID>
"""
import re, sys, os

ROW = re.compile(r'^(.{5,45}?)\s{2,}([A-Z0-9_\[\]\-]{4,16})\s+(\d+)\s+(\d+)\s+(\w+)\s*$')
FONT_MARKER = 'MS Sans Serif'

# The doc's own index names the sections. Match on these rather than on a generic
# "line is all-caps" rule: the real headers include parentheticals
# ("BRIDGES AND RAMPS (notch is high end of ramp)") and a naive word-count filter drops them,
# which silently folds Bridges/Ramps and Signs into whatever section preceded them.
CATEGORIES = [
    'COMMERCIAL STRUCTURES', 'DINING STRUCTURES', 'FILLING STATIONS', 'HOUSING STRUCTURES',
    'BRIDGES AND RAMPS', 'ROADS & INTERSECTIONS', 'ROADS AND INTERSECTIONS',
    'AMBIENT OBJECTS', 'SIGNS', 'MISCELLANEOUS OBJECTS', 'NATURE',
]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'docs/assets-raw/asset-extracted.txt'
    dst = sys.argv[2] if len(sys.argv) > 2 else 'docs/ASSET-BIBLE.md'
    text = open(src, encoding='utf-8', errors='ignore').read()

    # reorder: everything from the font table onward is the document START
    i = text.find(FONT_MARKER)
    if i > 0:
        text = text[i:] + '\n' + text[:i]

    cats = []          # [(category, [rows])]
    cur = None
    for line in text.splitlines():
        line = line.rstrip()
        m = ROW.match(line)
        if m:
            name, cls, x, z, cid = (g.strip() for g in m.groups())
            if name.upper() == name and not any(c.isdigit() for c in name) and len(name) > 25:
                pass       # a stray heading that happens to match; keep anyway
            if cur is None:
                cur = ('UNCATEGORISED', [])
                cats.append(cur)
            cur[1].append((name, cls, int(x), int(z), cid))
            continue
        up = line.strip().upper()
        for cat in CATEGORIES:
            if up.startswith(cat):
                cur = (cat, [])
                cats.append(cur)
                break

    cats = [(t, r) for t, r in cats if r]
    total = sum(len(r) for _, r in cats)

    out = []
    out.append("# The Complete Asset Bible — object class names, dimensions and types\n")
    out.append("Source: **DIVER, 2000** — *\"More information than you would ever want to know...\"*  ")
    out.append("Mirrored from `asset.doc`. The online copy at "
               "<https://interstate76.com/resources/diver/index.html> is a nested frameset that "
               "cannot be fetched in one go, so this local parse is the usable form.\n")
    out.append("**What it is for:** levels reference objects by CLASS NAME. This table turns those "
               "codes into a real object, its footprint, and its type — which is how you read a "
               "level's contents without rendering it. `greg-kennedy/i76render` cites it for the "
               "same reason. See [COMMUNITY-RESOURCES.md](COMMUNITY-RESOURCES.md).\n")
    out.append("`X DIM` / `Z DIM` are the footprint in metres. `Class ID` is the engine's object "
               "class (`Struct1`, `Bridge`, `Ramp`, `Paved`, `Dirt`, …).\n")
    out.append("**Ramps carry their height in the object name** — the single most useful thing here "
               "for jump/ballistics work, since it gives a known launch height per ramp.\n")
    out.append(f"Parsed {total} objects across {len(cats)} categories "
               f"(`tools/parse-asset-bible.py`).\n")
    out.append("---\n")

    for title, rows in cats:
        out.append(f"\n## {title.title()}\n")
        out.append("| object | class name | X | Z | class ID |")
        out.append("|---|---|---:|---:|---|")
        for name, cls, x, z, cid in rows:
            out.append(f"| {name} | `{cls}` | {x} | {z} | {cid} |")

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print(f"{total} objects, {len(cats)} categories -> {dst}")
    for t, r in cats:
        print(f"  {len(r):4}  {t}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
