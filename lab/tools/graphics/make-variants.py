"""make-variants.py - regenerate the conf-*.conf test variants from the sandbox's live game\\dgVoodoo.conf.

Each variant is a byte-for-byte copy of the live conf with only the listed keys changed, in the section the key
must live in (dgVoodoo silently ignores a key in the wrong section), plus a header comment naming the changes.
Run it again whenever game\\dgVoodoo.conf changes, so the variants never carry stale settings:

    python make-variants.py            # reads ..\\..\\game\\dgVoodoo.conf, writes conf-*.conf beside this file

Scale factors are relative to the PRESENTED frame (2304x1440 = the 16:10 Glide frame aspect-fitted into the 1440-tall
window), not to the [DirectX] Resolution. Every size is 16:10: the harness's cursor map (autotest\\lib\\maplib.ps1)
and u32x's pointer mapping both read the frame aspect, so the aspect must not change between variants.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.normpath(os.path.join(HERE, "..", "..", "game", "dgVoodoo.conf"))

G, GX, GE = "Glide", "GlideExt", "GeneralExt"
RES = {"1x": "2304x1440", "1.5x": "3456x2160", "2x": "4608x2880", "3x": "6912x4320"}

# name -> (what it is for, [(section, key, value), ...])
VARIANTS = {
    "1x":            ("reference: presented size, no antialiasing (what every other variant is compared against)",
                      [(G, "Resolution", RES["1x"]), (G, "Antialiasing", "off")]),
    "1x-msaa8":      ("MSAA only: presented size, 8x MSAA (geometry edges only; colour-keyed texture edges stay raw)",
                      [(G, "Resolution", RES["1x"]), (G, "Antialiasing", "8x")]),
    "1.5x":          ("supersampling only, 1.5x per axis (2.25x pixels), no MSAA",
                      [(G, "Resolution", RES["1.5x"]), (G, "Antialiasing", "off")]),
    "1.5x-msaa4":    ("1.5x supersampling + 4x MSAA",
                      [(G, "Resolution", RES["1.5x"]), (G, "Antialiasing", "4x")]),
    "2x":            ("supersampling only, 2x per axis (4x pixels), no MSAA; bilinear downscale is an exact 2x2 box here",
                      [(G, "Resolution", RES["2x"]), (G, "Antialiasing", "off")]),
    "2x-msaa4":      ("2x supersampling + 4x MSAA (16 samples per presented pixel on geometry edges)",
                      [(G, "Resolution", RES["2x"]), (G, "Antialiasing", "4x")]),
    "2x-msaa8":      ("2x supersampling + 8x MSAA (32 samples per presented pixel on geometry edges)",
                      [(G, "Resolution", RES["2x"]), (G, "Antialiasing", "8x")]),
    "2x-bicubic":    ("2x supersampling, bicubic downscale instead of bilinear (sharper, may ring)",
                      [(G, "Resolution", RES["2x"]), (G, "Antialiasing", "off"), (GE, "Resampling", "bicubic")]),
    "2x-lanczos3":   ("2x supersampling, lanczos-3 downscale (sharpest, strongest halo on HUD text and poles)",
                      [(G, "Resolution", RES["2x"]), (G, "Antialiasing", "off"), (GE, "Resampling", "lanczos-3")]),
    "3x":            ("supersampling only, 3x per axis (9x pixels), no MSAA; near the D3D11 FL10.1 8192 px limit",
                      [(G, "Resolution", RES["3x"]), (G, "Antialiasing", "off")]),
    "3x-bicubic":    ("3x supersampling, bicubic downscale (bilinear reads only 4 of the 9 source pixels at 3x)",
                      [(G, "Resolution", RES["3x"]), (G, "Antialiasing", "off"), (GE, "Resampling", "bicubic")]),
    "live-tmu-appdriven": ("live resolution and MSAA, texture filter left to the engine instead of forced bilinear",
                      [(G, "TMUFiltering", "appdriven")]),
}


def set_key(lines, section, key, value):
    """Replace `key` inside [section]; return (old value, was it found). Never adds a key to another section."""
    cur = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        m = re.match(rb"^\[(.+?)\]", s)
        if m:
            cur = m.group(1).decode("ascii", "replace"); continue
        if cur != section or s.startswith(b";"):
            continue
        m = re.match(rb"^(\s*" + re.escape(key.encode()) + rb"\s*=\s*)([^\r\n]*?)(\s*)$", raw.rstrip(b"\r\n"), re.I)
        if m:
            eol = raw[len(raw.rstrip(b"\r\n")):]
            lines[i] = m.group(1) + value.encode() + eol
            return m.group(2).decode("ascii", "replace"), True
    return None, False


def main():
    src = open(LIVE, "rb").read()
    eol = b"\r\n" if b"\r\n" in src else b"\n"
    made = []
    for name, (why, changes) in VARIANTS.items():
        lines = src.splitlines(keepends=True)
        notes = []
        for section, key, value in changes:
            old, found = set_key(lines, section, key, value)
            if not found:
                sys.exit("%s: [%s] %s is not in the live conf - add it there (in that section) first" % (name, section, key))
            notes.append("[%s] %s = %s   (live: %s)%s" % (section, key, value, old, "  - unchanged" if old == value else ""))
        head = ["; ==== i76-uncap-lab tools\\graphics\\conf-%s.conf - TEST VARIANT, sandbox only ====" % name,
                "; " + why,
                "; Generated by make-variants.py from game\\dgVoodoo.conf; identical to it except:"]
        head += [";   " + n for n in notes]
        head += ["; Install with apply-conf.ps1 -Variant %s ; put the live conf back with apply-conf.ps1 -Restore." % name,
                 "; See i76-everywhere docs\\records\\GRAPHICS-ENHANCEMENT.md.", ";"]
        out = eol.join(h.encode() for h in head) + eol + b"".join(lines)
        path = os.path.join(HERE, "conf-%s.conf" % name)
        open(path, "wb").write(out)
        made.append((name, notes))
    for name, notes in made:
        print("conf-%s.conf" % name)
        for n in notes:
            print("    " + n)


if __name__ == "__main__":
    main()
