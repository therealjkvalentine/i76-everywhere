"""
asset-bible-to-md.py - convert DIVER's Asset Bible (4th ed.) HTML into agent-searchable markdown.

The Bible is the community's reference for turning an in-game CLASS NAME into a real object, its
footprint and its type. It is the thing i76render cites for reading level contents. Online it is
a nested frameset that cannot be fetched in one go; the 4th edition ships as a local HTML tree,
which is what this converts.

Kept deliberately simple: the source tables are extremely regular
(<TR><TD>ClassID</TD><TD>X</TD><TD>Z</TD><TD>class name</TD><TD><a>Object name</a></TD></TR>),
so regex beats pulling in a parser dependency. Image hrefs are preserved as relative links back
into refs/ so a picture is one click away.

CREDIT: original Asset Bible writer and DIVER, "Happy Nitrous Delivery Services -the Ruins
Project-". Redistributed here for reference; see docs/COMMUNITY-RESOURCES.md.
"""
import re, os, sys, html

TAG = re.compile(r'<[^>]+>')
ROW = re.compile(r'<TR\b[^>]*>(.*?)</TR>', re.I | re.S)
CELL = re.compile(r'<T[DH]\b[^>]*>(.*?)</T[DH]>', re.I | re.S)
TABLE = re.compile(r'<TABLE\b[^>]*>(.*?)</TABLE>', re.I | re.S)
HREF = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.I)
COLSPAN = re.compile(r'colspan\s*=\s*["\']?(\d+)', re.I)


def clean(s):
    s = re.sub(r'<BR\b[^>]*>', ' / ', s, flags=re.I)
    s = TAG.sub('', s)
    s = html.unescape(s)
    s = s.replace('|', r'\|')
    return re.sub(r'\s+', ' ', s).strip()


def read_text(path):
    """The Bible is Japanese-authored; naive latin-1 turns full-width punctuation into mojibake
    ('Â@Â@'). Try UTF-8, then Shift-JIS (cp932), then fall back."""
    raw = open(path, 'rb').read()
    for enc in ('utf-8', 'cp932', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1', errors='replace')


def convert(path, relimg):
    src = read_text(path)
    out = []
    for tbl in TABLE.findall(src):
        rows = []
        for r in ROW.findall(tbl):
            # Honour colspan. The real header uses colspan=2 for "X-Z DIM", so without this it
            # comes out narrower than the data rows, gets mistaken for a banner, and the first
            # DATA row is promoted into the header position.
            vals = []
            for cm in re.finditer(r'<T[DH]\b([^>]*)>(.*?)</T[DH]>', r, re.I | re.S):
                attrs, c = cm.group(1), cm.group(2)
                txt = clean(c)
                m = HREF.search(c)
                if m and m.group(1).lower().endswith(('.gif', '.png', '.jpg')):
                    txt = f"[{txt}]({relimg}/{m.group(1)})"
                n = COLSPAN.search(attrs)
                span = int(n.group(1)) if n else 1
                vals.append(txt)
                vals.extend([''] * (span - 1))
            rows.append(vals)
        if len(rows) < 2:
            continue
        width = max(len(r) for r in rows)
        # first row that has the full width is the header; earlier ones are section banners
        hdr_i = next((i for i, r in enumerate(rows) if len(r) == width), 0)
        for banner in rows[:hdr_i]:
            t = ' '.join(x for x in banner if x)
            if t:
                out.append(f"\n**{t}**\n")
        hdr = rows[hdr_i] + [''] * (width - len(rows[hdr_i]))
        out.append('| ' + ' | '.join(hdr) + ' |')
        out.append('|' + '---|' * width)
        for r in rows[hdr_i + 1:]:
            r = r + [''] * (width - len(r))
            out.append('| ' + ' | '.join(r[:width]) + ' |')
        out.append('')
    if not out:
        body = clean(src)
        if len(body) > 40:
            out.append(body)
    return '\n'.join(out)


def main():
    srcdir = sys.argv[1]
    dstdir = sys.argv[2]
    relimg = sys.argv[3] if len(sys.argv) > 3 else '../../refs/route380/extracted/i76cab4/data'
    os.makedirs(dstdir, exist_ok=True)

    made = []
    for root, _, files in os.walk(srcdir):
        for fn in sorted(files):
            if not fn.lower().endswith(('.html', '.htm')):
                continue
            if fn.lower() in ('null.html', 'blank.html'):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, srcdir).replace('\\', '/')
            body = convert(full, relimg + '/' + os.path.dirname(rel) if os.path.dirname(rel) else relimg)
            if len(body) < 60:
                continue
            name = rel.replace('/', '__').rsplit('.', 1)[0] + '.md'
            title = rel.rsplit('.', 1)[0]
            hdr = (f"# Asset Bible — `{title}`\n\n"
                   f"*Interstate '76 / '77 Complete Asset Bible, 4th edition. "
                   f"Credit: **original Asset Bible writer and DIVER**, "
                   f"\"Happy Nitrous Delivery Services -the Ruins Project-\". "
                   f"Source: <https://route380.stars.ne.jp/i76/resource_i76/> (`i76cab4.zip`). "
                   f"Converted by `tools/asset-bible-to-md.py`; see "
                   f"[COMMUNITY-RESOURCES.md](../COMMUNITY-RESOURCES.md).*\n\n"
                   f"Original file: `{rel}`\n\n---\n\n")
            open(os.path.join(dstdir, name), 'w', encoding='utf-8').write(hdr + body + '\n')
            made.append((name, rel, len(body)))

    made.sort()
    idx = ["# Asset Bible — index\n",
           "Searchable markdown conversion of the **Interstate '76 / '77 Complete Asset Bible, "
           "4th edition**.\n",
           "> **Credit:** original Asset Bible writer and **DIVER** "
           "(\"Happy Nitrous Delivery Services -the Ruins Project-\"). "
           "Obtained from <https://route380.stars.ne.jp/i76/resource_i76/> as `i76cab4.zip`. "
           "Reproduced here for reference and to make it greppable by agents working on this "
           "repo — see [COMMUNITY-RESOURCES.md](../COMMUNITY-RESOURCES.md).\n",
           "**What it gives you:** every placeable object's CLASS NAME, footprint (X/Z in "
           "metres) and engine class ID, plus vehicle codes. That turns a level's raw object "
           "list into something readable, and gives known dimensions for physics work.\n",
           "| page | source file | size |", "|---|---|---:|"]
    for name, rel, n in made:
        idx.append(f"| [{name.rsplit('.',1)[0]}]({name}) | `{rel}` | {n:,} |")
    open(os.path.join(dstdir, 'INDEX.md'), 'w', encoding='utf-8').write('\n'.join(idx) + '\n')
    print(f"{len(made)} pages -> {dstdir}")
    for name, rel, n in made[:40]:
        print(f"  {n:7,}  {rel}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
