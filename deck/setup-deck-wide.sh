#!/bin/bash
# Interstate '76 - bring the Deck up to the current graphics build. RUNS ON THE DECK.
#
# What the Windows daily driver runs (preset best-wide-balanced), adapted to the Deck's
# 1280x800 panel:
#   * the Strlkup.dll proxy (music-fix/), which carries every I76_* engine switch:
#     Hor+ widescreen at 16:10, the HUD squeeze, fixed 24 Hz physics step + render
#     interpolation (smooth above 20 fps without breaking jumps), the frame-rate fixes,
#     draw distance 1200 m, terrain/texture/object detail x8, bushes 300 m, mirror 300 m,
#     the terrain-flash fix, the TMU fix, and in-mission music from GOG's mp3s
#   * dgVoodoo.conf: stretched to the panel at native 1280x800 (the Deck's conf point-samples
#     its downscale, so 2x internal would only add shimmer), 4x MSAA, TMU 8192 (only together
#     with I76_ZGLIDE_TMUFIX), FPSLimit off, forced 32-bit dithering
#   * I76PATCH.DLL (GOG's ~20 fps cap) disabled: the fixed step keeps physics at stock pace
#   * LAN play: IPXWrapper's three DLLs (if the push brought them) + WINEDLLOVERRIDES for
#     wsock32/mswsock, the recipe that put the Mac into a PC-hosted IPX game (docs/MULTIPLAYER.md)
#
# Kept as is: dgVoodoo 2.78.2 (the version proven under Proton on this Deck), the Steam
# Input controller layout, input.map; the AHK pad layer stays off (I76_DECK_AHK=0). Not
# carried: u32x.dll (the Windows mouse DLL; the Esc menu's mouse map may be off at 16:10).
#
# STATUS: built 2026-10-06. The proxy ran every switch under Wine 10 on the Mac with this
# same exe (AiO + stack patch, docs/records/PORTING-WINDOWS-WINS-TO-MAC.md); not yet under
# Proton. Everything below verifies before it writes; --revert puts every touched file back.
#
#   ./setup-deck-wide.sh                 install (re-runnable)
#   ./setup-deck-wide.sh --revert        restore the files saved by the last install
#
# Steam launch options must run the wrapper (it loads the switch file):
#     "/home/deck/Games/Interstate76/i76-deck-launch.sh" %command% -glide
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
INSTALL="${I76_INSTALL:-$HOME/Games/Interstate76}"
GAME="${I76_GAMEDIR:-$INSTALL/game}"
BACKUPS="$INSTALL/backups"
LAST="$BACKUPS/LAST-WIDE"
PAYLOAD="${I76_PAYLOAD:-$HERE/..}"        # repo root (or the pushed copy of it)
PROXY_MD5="d603cccf889bb8cff784fc1e933f6f27"

say() { echo "  $*"; }
die() { echo "FATAL: $*"; exit 1; }
md5() { md5sum "$1" | cut -d' ' -f1; }

# ---------------------------------------------------------------- revert ----
if [ "${1:-}" = "--revert" ]; then
    [ -f "$LAST" ] || die "no install recorded ($LAST missing)"
    B="$(cat "$LAST")"
    [ -d "$B" ] || die "backup folder gone: $B"
    echo "== reverting from $B =="
    # MANIFEST lines: <relative path> <present|absent>
    while read -r rel state; do
        if [ "$state" = present ]; then
            cp -f "$B/$rel" "$INSTALL/$rel"; say "restored $rel"
        elif [ "$rel" = i76-deck-launch.sh ]; then
            # Steam's launch options now point at it; without i76-env.sh it launches stock.
            say "kept $rel (launch options use it; no switches without i76-env.sh)"
        else
            rm -f "$INSTALL/$rel"; say "removed $rel (was absent before)"
        fi
    done < "$B/MANIFEST"
    rm -f "$LAST"
    echo "Done. Launch options can stay: the wrapper launches bare without i76-env.sh."
    exit 0
fi

[ -f "$GAME/i76.exe" ] || die "no i76.exe in $GAME (set I76_GAMEDIR)"
[ -f "$PAYLOAD/music-fix/Strlkup.dll" ] || die "payload missing: $PAYLOAD/music-fix/Strlkup.dll"
[ "$(md5 "$PAYLOAD/music-fix/Strlkup.dll")" = "$PROXY_MD5" ] \
    || die "proxy md5 is not $PROXY_MD5 (copy damaged, or the repo build moved on: update PROXY_MD5)"
if pgrep -x 'i76.exe' >/dev/null 2>&1; then die "the game is running - quit it first"; fi

# ------------------------------------------------------------ 0. backup -----
# Only the FIRST install is backed up: a re-run (e.g. a newer proxy) keeps the original
# pre-wide state as the revert target instead of saving its own previous output.
TS="$(date +%Y%m%d-%H%M%S)"
if [ -f "$LAST" ] && [ -d "$(cat "$LAST")" ]; then
    B="$(cat "$LAST")"
    echo "== 0. re-run: keeping the original backup $B =="
else
    B="$BACKUPS/pre-wide-$TS"
    mkdir -p "$B/game"
    : > "$B/MANIFEST"
    for rel in game/Strlkup.dll game/STRLKUP.DLL game/strlkup_orig.dll game/dgVoodoo.conf \
               game/I76PATCH.DLL game/I76PATCH.DLL.disabled game/ipxwrapper.dll game/wsock32.dll \
               game/mswsock.dll i76-env.sh i76-deck-launch.sh; do
        if [ -e "$INSTALL/$rel" ]; then
            cp -p "$INSTALL/$rel" "$B/$rel"; echo "$rel present" >> "$B/MANIFEST"
        else
            echo "$rel absent" >> "$B/MANIFEST"
        fi
    done
    echo "$B" > "$LAST"
    echo "== 0. backup -> $B =="
    ( cd "$GAME" && md5sum i76.exe Strlkup.dll Glide2x.dll 2>/dev/null ) | sed 's/^/  /' | tee "$B/md5-before.txt"
fi

# ------------------------------------------------------------- 1. proxy -----
echo "== 1. Strlkup.dll proxy =="
# GOG's installer may write it upper case. Wine resolves either; this script needs one name.
if [ ! -f "$GAME/Strlkup.dll" ] && [ -f "$GAME/STRLKUP.DLL" ]; then
    mv "$GAME/STRLKUP.DLL" "$GAME/Strlkup.dll"; say "STRLKUP.DLL -> Strlkup.dll (revert restores the old name)"
fi
[ -f "$GAME/Strlkup.dll" ] || die "no Strlkup.dll in $GAME"
if grep -qa 'strlkup_orig' "$GAME/Strlkup.dll"; then
    say "Strlkup.dll is already a proxy - replacing it with $PROXY_MD5"
    [ -f "$GAME/strlkup_orig.dll" ] || die "proxy present but strlkup_orig.dll missing - restore GOG's Strlkup.dll first"
else
    if [ -f "$GAME/strlkup_orig.dll" ]; then
        die "strlkup_orig.dll exists AND Strlkup.dll is not a proxy - unclear state, sort it by hand"
    fi
    mv "$GAME/Strlkup.dll" "$GAME/strlkup_orig.dll"
    say "GOG's Strlkup.dll -> strlkup_orig.dll"
fi
cp -f "$PAYLOAD/music-fix/Strlkup.dll" "$GAME/Strlkup.dll"
[ "$(md5 "$GAME/Strlkup.dll")" = "$PROXY_MD5" ] || die "copy check failed"
say "proxy installed ($PROXY_MD5)"

# ---------------------------------------------------- 2. GOG's 20 fps cap ----
echo "== 2. I76PATCH.DLL =="
if [ -f "$GAME/I76PATCH.DLL" ]; then
    mv -f "$GAME/I76PATCH.DLL" "$GAME/I76PATCH.DLL.disabled"; say "disabled (I76PATCH.DLL.disabled)"
else
    say "not present - nothing to do"
fi

# ------------------------------------------------------- 3. dgVoodoo.conf ----
echo "== 3. dgVoodoo.conf =="
[ -f "$GAME/dgVoodoo.conf" ] || die "no dgVoodoo.conf in $GAME"
# Only values change, never keys: dgVoodoo rejects a whole conf over one line it does not
# know (lab DGVOODOO-CONF-REJECTED.md), and this one is a 2.78.2 file. Each key must occur
# exactly once in its section or nothing is written.
python3 - "$GAME/dgVoodoo.conf" <<'PY'
import re, sys
p = sys.argv[1]
t = open(p, encoding="latin-1").read()
want = [  # (section, key, value, mode)  mode: req = must exist, opt = skip if absent, add = insert if absent
    ("General",    "ScalingMode",           "stretched",   "req"),  # fills 16:10; I76_ASPECT widens the camera to match
    ("General",    "KeepWindowAspectRatio", "false",       "opt"),
    ("GeneralExt", "FPSLimit",              "0",           "req"),  # pacing: I76_GLIDE_REFRESH; physics: the fixed step
    # Without this dgVoodoo switches to a 640x480 mode and Proton scales that mode to the panel
    # keeping 4:3: a 1067x800 pillarbox whatever ScalingMode says (measured on the Deck 2026-10-06:
    # child window 1067x800 at x=107). Fake fullscreen presents at the desktop's 1280x800.
    # The key exists in 2.78.2 (the repo's 2.78 conf carries it empty).
    ("GeneralExt", "FullscreenAttributes",  "fake",        "add"),
    ("Glide",      "MemorySizeOfTMU",       "8192",        "req"),   # ONLY with I76_ZGLIDE_TMUFIX=1 (4096+ without it corrupts textures)
    ("Glide",      "Resolution",            "1280x800",    "req"),   # the panel, 16:10
    ("Glide",      "Antialiasing",          "4x",          "req"),
    ("GlideExt",   "Dithering",             "forcealways", "opt"),
]
sec_re = re.compile(r'(?m)^\[([^\]]+)\]\s*$')
heads = [(m.group(1), m.start(), m.end()) for m in sec_re.finditer(t)]
def span(name):
    for i, (n, s, e) in enumerate(heads):
        if n == name:
            return e, (heads[i + 1][1] if i + 1 < len(heads) else len(t))
    raise SystemExit("REFUSED: no [%s] section" % name)
for sec, key, val, mode in want:
    a, b = span(sec)
    body = t[a:b]
    # value, then an optional inline "; comment" that is kept
    pat = re.compile(r'(?m)^(%s\s*=[ \t]*)([^;\r\n]*?)([ \t]*;[^\r\n]*)?$' % re.escape(key))
    hits = pat.findall(body)
    if len(hits) == 0 and mode == "opt":
        print("  [%s] %s: absent, left absent (optional)" % (sec, key))
        continue
    if len(hits) == 0 and mode == "add":
        body = "\n%-37s= %s   ; added by deck/setup-deck-wide.sh" % (key, val) + body
        t = t[:a] + body + t[b:]
        heads = [(m.group(1), m.start(), m.end()) for m in sec_re.finditer(t)]
        print("  [%s] %s: absent -> %s (added)" % (sec, key, val))
        continue
    if len(hits) != 1:
        raise SystemExit("REFUSED: [%s] %s occurs %d times" % (sec, key, len(hits)))
    old = hits[0][1].strip()
    # unchanged value keeps its comment; a changed one says what it was
    note = lambda m: (m.group(3) or "") if old == val else "   ; was %s (deck/setup-deck-wide.sh)" % (old or "empty")
    body = pat.sub(lambda m: m.group(1) + val + note(m), body)
    t = t[:a] + body + t[b:]
    heads = [(m.group(1), m.start(), m.end()) for m in sec_re.finditer(t)]
    print("  [%s] %s: %s -> %s" % (sec, key, old or "(empty)", val))
open(p, "w", encoding="latin-1", newline="").write(t)
PY

# ------------------------------------------------------------ 3b. LAN (IPX) --
echo "== 3b. IPXWrapper (LAN play) =="
IPX=""
if [ -f "$PAYLOAD/ipx/ipxwrapper.dll" ] && [ -f "$PAYLOAD/ipx/wsock32.dll" ] && [ -f "$PAYLOAD/ipx/mswsock.dll" ]; then
    cp -f "$PAYLOAD/ipx/ipxwrapper.dll" "$PAYLOAD/ipx/wsock32.dll" "$PAYLOAD/ipx/mswsock.dll" "$GAME/"
    IPX=1; say "ipxwrapper.dll, wsock32.dll, mswsock.dll installed"
elif [ -f "$GAME/ipxwrapper.dll" ]; then
    IPX=1; say "already installed"
else
    say "not in the payload - skipped (LAN over IPX unavailable; see docs/MULTIPLAYER.md)"
fi

# ----------------------------------------------------- 4. the switch file ----
echo "== 4. i76-env.sh (preset best-wide-balanced, Deck values) =="
# Deck model: LCD (Jupiter) 60 Hz, OLED (Galileo) 90 Hz. The engine paces to the Glide
# refresh it asks for, so this is the frame-rate target.
HZ=60
if grep -qi galileo /sys/class/dmi/id/product_name 2>/dev/null; then HZ=90; fi
cat > "$INSTALL/i76-env.sh" <<EOF
# Interstate '76 engine switches for the Deck - sourced by i76-deck-launch.sh.
# Written by deck/setup-deck-wide.sh on $TS. Source: presets/best-wide-balanced.psd1,
# with I76_ASPECT for the 1280x800 panel and the refresh for this Deck ($HZ Hz).
# Delete this file (or run setup-deck-wide.sh --revert) to launch with no switches.
export I76_HIRES_CLOCK=1
export I76_FIXED_STEP=24
export I76_FRAMERATE_FIXES=1
export I76_ENGINE_DT_FIX=1
export I76_RENDER_INTERP=1
export I76_FIX_HEALTH_PCT=1
export I76_FIX_LABEL_TABLE=1
export I76_FAR_CLIP=1200
export I76_CAM_GROUND_FIX=1
export I76_ZGLIDE_TMUFIX=1          # required by MemorySizeOfTMU 8192 in dgVoodoo.conf
export I76_INPUT_LATCH=1
export I76_AI_BACKAWAY_GRID=1
export I76_GLIDE_REFRESH=$HZ
export I76_ASPECT=1280x800          # Hor+ 16:10; HUD sprites squeezed back to shape automatically
export I76_TERRAIN_LOD=8
export I76_TERRAIN_TEX=8
export I76_OBJECT_LOD=8
export I76_SHADOW_DIST=4
export I76_ROAD_TEX=8
export I76_CLUTTER_DIST=300
export I76_MIRROR_FAR=300
export I76_COLL_DEDUPE=0
export I76_AI_ROLL_HOLD=0
export I76MUSIC_LOG=1               # mciproxy.log in the game folder: proves which switches applied
export I76_DECK_AHK=0               # 1 = start the baseline AHK pad layer too (deck/setup-deck-baseline.sh)
EOF
if [ -n "$IPX" ]; then
    cat >> "$INSTALL/i76-env.sh" <<'EOF'
# IPXWrapper: Wine must load the game folder's winsock DLLs, not its own.
export WINEDLLOVERRIDES="wsock32,mswsock=n,b${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
EOF
fi
say "written ($HZ Hz target)"

# ------------------------------------------------------------ 5. wrapper ----
echo "== 5. launch wrapper =="
cp -f "$HERE/i76-deck-launch.sh" "$INSTALL/i76-deck-launch.sh"
chmod +x "$INSTALL/i76-deck-launch.sh"
say "installed -> $INSTALL/i76-deck-launch.sh"

# ------------------------------------------------------- 6. launch options ----
echo "== 6. Steam launch options =="
WANT="\"$INSTALL/i76-deck-launch.sh\" %command% -glide"
if pgrep -x steam >/dev/null 2>&1 || pgrep -f 'steamwebhelper' >/dev/null 2>&1; then
    say "Steam is running, so shortcuts.vdf is left alone. Set it by hand:"
    say "  Steam > Interstate 76 > Properties > Launch Options:"
    say "  $WANT"
else
    python3 "$HERE/set-launch-options.py" "Interstate 76" "$WANT" || say "could not set them - do it by hand (above)"
fi

cat <<EOF

================================================================
Done. Backup + revert list: $B
Rollback:  bash $HERE/setup-deck-wide.sh --revert

First launch: Game Mode. Leave QAM > Performance > Framerate limit at its default
(off): the game paces itself to $HZ Hz (I76_GLIDE_REFRESH). If you once set a
per-game limit of 20 for the old build, turn it off. Play Instant Melee first.
After a session, mciproxy.log in the game folder lists every switch the
proxy applied (look for 'aspect', 'hud-squeeze', 'fixed-step', 'tmufix').
================================================================
EOF
