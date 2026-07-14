#!/bin/sh
# Interstate '76 - wire up (or silence) in-mission music via DxWnd's virtual CD audio.
#
# WHY: I76's mission soundtrack was originally CD redbook audio (the game plays
# "CD audio track N"). The GOG version ships those tracks as music/2.mp3 .. music/17.mp3
# plus an (empty) tracklen.nfo. Under Wine there's no real CD, so the music is silent.
# DxWnd's virtual CD audio (its bundled dxwplay.dll) emulates the CD - BUT it looks for
# files named Music\TrackNN.mp3 (zero-padded), not the GOG N.mp3 naming. This script
# creates the TrackNN.mp3 names (hard links, no extra disk) and clears the broken empty
# tracklen.nfo so dxwplay regenerates it. The VIRTUALCDAUDIO flag is bit 0 of flagm0 in
# the profile. MP3 decode rides the GStreamer env the launch stub already sets.
#
#   setup-music.sh          wire tracks + ENABLE virtual-CD music (default)
#   setup-music.sh --off    DISABLE it (flagm0 bit 0 off) - silences in-mission music,
#                           but lets the FMV cutscenes play their OWN baked audio cleanly.
#                           Use this if the known GOG "music-over-cutscenes" bug bugs you
#                           (see docs/VERIFIED-FIXES.md - the cutscene score is inside the
#                           smk/*.SMK movies; the mission CD track otherwise bleeds over it).
#   setup-music.sh --on     re-ENABLE it.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
GAME="$APP/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76"
DXWINI="$APP/Contents/SharedSupport/prefix/drive_c/dxwnd/dxwnd.ini"
REPO_DXW="$HERE/interstate-76.dxw"

# Flip bit 0 of flagm0 (VIRTUALCDAUDIO) in every profile file that exists. CRLF-safe.
set_vcd() {  # $1 = on|off
    for f in "$DXWINI" "$REPO_DXW"; do
        [ -f "$f" ] || continue
        python3 - "$f" "$1" <<'EOF'
import re,sys
p,mode=sys.argv[1],sys.argv[2]
b=open(p,'rb').read()
m=re.search(rb'(?m)^flagm0=(\d+)',b)
if not m:  # no flagm0 line: add one only when enabling
    if mode=='on': b=b.rstrip()+b'\r\nflagm0=1\r\n'; open(p,'wb').write(b)
    print(f"  {p.split('/')[-1]}: flagm0 absent ({'added' if mode=='on' else 'nothing to disable'})"); raise SystemExit
v=int(m.group(1)); nv = (v|1) if mode=='on' else (v & ~1)
b=b[:m.start(1)]+str(nv).encode()+b[m.end(1):]
open(p,'wb').write(b)
print(f"  {p.split('/')[-1]}: flagm0 {v} -> {nv} (VIRTUALCDAUDIO {'ON' if nv&1 else 'OFF'})")
EOF
    done
}

case "$1" in
  --off)
    echo "Disabling virtual-CD music (cutscenes will play their own baked audio; missions go silent):"
    set_vcd off
    echo "Done. Relaunch. Undo with: $0 --on"
    exit 0 ;;
  --on)
    echo "Enabling virtual-CD music:"
    set_vcd on
    echo "Done. Relaunch."
    exit 0 ;;
esac

# default: wire the TrackNN.mp3 links + ensure the flag is on
[ -d "$GAME/music" ] || { echo "music folder not found: $GAME/music"; exit 1; }
cd "$GAME/music"
for f in [0-9]*.mp3; do
  [ -e "$f" ] || continue
  n="${f%.mp3}"
  printf -v tn "Track%02d.mp3" "$n" 2>/dev/null || tn=$(printf "Track%02d.mp3" "$n")
  [ -f "$tn" ] || ln "$f" "$tn"
done
rm -f "$GAME/music/tracklen.nfo"   # empty file breaks dxwplay; let it regenerate
echo "Music wired: $(ls Track*.mp3 2>/dev/null | wc -l | tr -d ' ') CD tracks -> TrackNN.mp3"
set_vcd on
echo "Done. (Cutscenes will show the known GOG music-overlap bug - run '$0 --off' to trade"
echo " in-mission music for clean cutscenes. See docs/VERIFIED-FIXES.md.)"
