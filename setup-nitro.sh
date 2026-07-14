#!/bin/sh
# ============================================================================
#  setup-nitro.sh - install + fully configure the Interstate '76 NITRO PACK in
#  the Mac wrapper, with EVERY base-game fix applied. Reproducible + idempotent.
# ============================================================================
#  Nitro Riders is a STANDALONE GOG product (separate installer, own nitro.exe).
#  It installs alongside the base game in the SAME Sikarugir wrapper prefix and
#  gets a second DxWnd profile (/R:2) + its own satellite launcher app.
#
#  Bring your own GOG Nitro installer (setup_interstate76_nitro_pack_*.exe). This
#  script ships NO game content. Requires the base
#    "Interstate 76 - Software (DxWnd).app"
#  wrapper to already be set up (it reuses that wrapper's wine, DxWnd, our
#  input.map, and the already-built SMACKW32 cutscene-music proxy).
#
#  Steps (each idempotent - safe to re-run):
#    0. locate + innoextract your GOG Nitro installer
#    1. install into drive_c/GOG Games/Interstate 76 Nitro Pack
#    2. registry: nitro.exe -> win98 + virtual desktop (or it page-faults at boot)
#    3. DxWnd profile 2, cloned from the base profile (aspect/letterbox/~19.2fps/
#       primary-surface renderer/virtual-CD)
#    4. virtual-CD in-mission music (Track NN.mp3 hard links)
#    5. cutscene-music proxy (SMACKW32 -> smackorg)
#    6. Mac arrow-keys fix (KEYBOARD.MAP)
#    7. our known-good input.map (WASD/mouse/number-keys/specials)
#    8. 8 MB stack patch (nitro.exe PE)
#    9. CPU-SPEED CRASH patch - NOP the privileged 8253-PIT calibration
#       (CLI + port I/O at ~0x49ACB7). This is the documented WineHQ crash the
#       AiO-patched base i76.exe avoids; GOG's 2011 nitro.exe still has it.
#   10. build + install "Interstate 76 Nitro (DxWnd).app"
#
#  Usage:  ./setup-nitro.sh [path/to/setup_interstate76_nitro_pack_X.exe]
#          ./setup-nitro.sh --revert     (uninstall Nitro + its launcher)
# ============================================================================
set -eu

DIR=$(cd "$(dirname "$0")" && pwd)
SIK="$HOME/Applications/Sikarugir"
APP="$SIK/Interstate 76 - Software (DxWnd).app"
PFX="$APP/Contents/SharedSupport/prefix"
GOGDIR="$PFX/drive_c/GOG Games"
BASE="$GOGDIR/Interstate 76"
NITRO="$GOGDIR/Interstate 76 Nitro Pack"
WINE="$APP/Contents/SharedSupport/wine/bin/wine"
DXINI="$PFX/drive_c/dxwnd/dxwnd.ini"
LAUNCHER="$SIK/Interstate 76 Nitro (DxWnd).app"

[ -d "$APP" ] || { echo "Base wrapper not found: $APP"; echo "Set up the base game first (see docs/MAC-BUILD.md)."; exit 1; }

# ---- --revert -------------------------------------------------------------
if [ "${1:-}" = "--revert" ]; then
    echo "Reverting Nitro..."
    pkill -9 -f "nitro\.exe|Interstate 76 Nitro (DxWnd).app" 2>/dev/null || true
    rm -rf "$NITRO" "$LAUNCHER"
    # drop DxWnd profile 1 (Nitro) - keep everything up to the last profile-0 key
    if [ -f "$DXINI" ]; then
        cp "$DXINI" "$DXINI.pre-revert"
        grep -av '^[A-Za-z][A-Za-z]*1=' "$DXINI.pre-revert" > "$DXINI"
    fi
    echo "Nitro removed. (Registry keys for nitro.exe are harmless; left in place.)"
    exit 0
fi

# ---- quit any running session (we mutate dxwnd.ini + patch nitro.exe) -----
if pgrep -f "i76\.exe|nitro\.exe|dxwnd\.exe" >/dev/null 2>&1; then
    echo "Quitting the running game first (we edit dxwnd.ini + nitro.exe)..."
    pkill -f "i76\.exe|nitro\.exe" 2>/dev/null || true
    "$APP/Contents/SharedSupport/wine/bin/wineserver" -w 2>/dev/null || true
    n=0; while pgrep -f "dxwnd\.exe|nitro\.exe|i76\.exe" >/dev/null 2>&1 && [ $n -lt 15 ]; do sleep 1; n=$((n+1)); done
fi

# ---- 0/1. locate installer + install into the prefix ----------------------
if [ -f "$NITRO/nitro.exe" ]; then
    echo "[1] Nitro already installed at: $NITRO (skipping extract)"
else
    SETUP="${1:-}"
    if [ -z "$SETUP" ]; then
        SETUP=$(ls "$DIR"/game-data/downloads/setup_interstate76_nitro_pack_*.exe \
                   "$HOME"/Downloads/setup_interstate76_nitro_pack_*.exe 2>/dev/null | head -1 || true)
    fi
    [ -n "$SETUP" ] && [ -f "$SETUP" ] || { echo "GOG Nitro installer not found."; echo "Pass it: ./setup-nitro.sh /path/to/setup_interstate76_nitro_pack_X.exe"; exit 1; }
    command -v innoextract >/dev/null 2>&1 || { echo "Installing innoextract (brew)..."; brew install innoextract; }
    STAGE="$DIR/game-data/nitro-extracted"
    if [ ! -f "$STAGE/app/nitro.exe" ]; then
        echo "[0] Extracting $(basename "$SETUP") ..."
        rm -rf "$STAGE"; mkdir -p "$STAGE"
        innoextract --gog -s -d "$STAGE" "$SETUP" >/dev/null
    fi
    [ -f "$STAGE/app/nitro.exe" ] || { echo "Extraction produced no nitro.exe"; exit 1; }
    echo "[1] Installing into: $NITRO"
    mkdir -p "$NITRO"
    cp -R "$STAGE/app/." "$NITRO/"
fi

# ---- 2. registry: nitro.exe win98 + virtual desktop (NEEDS the DYLD env) ---
echo "[2] Registry: nitro.exe -> win98 + virtual desktop"
gv="$APP/Contents/Frameworks/GStreamer.framework/Versions/1.0"
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$gv/lib:$APP/Contents/SharedSupport/wine/lib"
export WINEPREFIX="$PFX" WINEESYNC=1 WINEMSYNC=1 WINEDEBUG=-all
"$WINE" reg add 'HKCU\Software\Wine\AppDefaults\nitro.exe' /v Version /d win98 /f >/dev/null 2>&1 || true
"$WINE" reg add 'HKCU\Software\Wine\AppDefaults\nitro.exe\Explorer' /v Desktop /d i76 /f >/dev/null 2>&1 || true
"$APP/Contents/SharedSupport/wine/bin/wineserver" -w 2>/dev/null || true

# ---- 3. DxWnd profile 2 = clone of base profile 0, retargeted to nitro -----
if grep -aq '^title1=' "$DXINI" 2>/dev/null; then
    echo "[3] DxWnd profile 2 already present (skipping)"
else
    echo "[3] Cloning DxWnd base profile -> profile 2 (Nitro)"
    cp "$DXINI" "$DXINI.pre-nitro"
    awk '
      /^\[target\]/{intgt=1; next} /^\[/{intgt=0}
      intgt && /^[A-Za-z]+0=/{
        key=$0; sub(/=.*/,"",key); val=$0; sub(/^[^=]*=/,"",val)
        base=substr(key,1,length(key)-1)
        if(base=="title"){val="Interstate 76 Nitro Pack"}
        else if(base=="path"){val="C:\\GOG Games\\Interstate 76 Nitro Pack\\nitro.exe"}
        else if(base=="launchpath"){val="\"\""}
        else if(base=="notes"){val=""}
        print base "1=" val
      }' "$DXINI" | sed 's/$/\r/' >> "$DXINI"
fi

# ---- 4. virtual-CD in-mission music (TrackNN.mp3 hard links) ---------------
if [ -d "$NITRO/music" ]; then
    echo "[4] Wiring virtual-CD music (TrackNN.mp3)"
    ( cd "$NITRO/music"
      for f in [0-9]*.mp3; do
        [ -f "$f" ] || continue
        n=${f%.mp3}
        tn=$(printf "Track%02d.mp3" "$n" 2>/dev/null) || tn="Track$n.mp3"
        [ -f "$tn" ] || ln "$f" "$tn"
      done
      rm -f tracklen.nfo )
fi

# ---- 5. cutscene-music proxy (reuse the base game's built SMACKW32) --------
if [ -f "$NITRO/smackorg.dll" ]; then
    echo "[5] Cutscene-music proxy already installed (skipping)"
elif [ -f "$BASE/SMACKW32.DLL" ] && [ "$(stat -f%z "$BASE/SMACKW32.DLL" 2>/dev/null || echo 0)" -lt 40000 ]; then
    echo "[5] Installing cutscene-music proxy (from base game's built proxy)"
    cp "$NITRO/SMACKW32.DLL" "$NITRO/SMACKW32.DLL.orig"
    cp "$NITRO/SMACKW32.DLL" "$NITRO/smackorg.dll"
    cp "$BASE/SMACKW32.DLL" "$NITRO/SMACKW32.DLL"
else
    echo "[5] SKIP proxy: base game's SMACKW32 proxy not found/built."
    echo "    Build it: smack-music-fix/build.sh, then re-run, or run setup-cutscene-music-fix.sh."
fi

# ---- 6. Mac arrow-keys fix (KEYBOARD.MAP) ---------------------------------
if [ -f "$NITRO/KEYBOARD.MAP" ] && [ ! -f "$NITRO/KEYBOARD.MAP.pre-mac-arrows" ]; then
    echo "[6] Mac arrow-keys fix on Nitro KEYBOARD.MAP"
    sh "$DIR/fix-arrows-for-mac.sh" "$NITRO/KEYBOARD.MAP" >/dev/null 2>&1 || echo "    (arrow fix skipped)"
else
    echo "[6] Arrow-keys fix already applied (or no KEYBOARD.MAP) - skipping"
fi

# ---- 7. our known-good input.map -----------------------------------------
SRC_IM="$BASE/input.map"; [ -f "$SRC_IM" ] || SRC_IM="$DIR/docs/input.map.reference"
if [ -f "$SRC_IM" ]; then
    echo "[7] Applying known-good input.map (source: $(basename "$(dirname "$SRC_IM")")/input.map)"
    [ -f "$NITRO/input.map.pre-i76fixes" ] || cp "$NITRO/input.map" "$NITRO/input.map.pre-i76fixes" 2>/dev/null || true
    cp "$SRC_IM" "$NITRO/input.map"
fi

# ---- 8 + 9. binary patches on nitro.exe (stack + CPU-speed crash) ----------
echo "[8+9] Patching nitro.exe (8MB stack + CPU-speed crash)"
[ -f "$NITRO/nitro.exe.pre-patch" ] || cp "$NITRO/nitro.exe" "$NITRO/nitro.exe.pre-patch"
python3 - "$NITRO/nitro.exe" <<'PY'
import sys,struct
p=sys.argv[1]; d=bytearray(open(p,'rb').read())
# --- 8. SizeOfStackReserve 1MB -> 8MB (PE32 OptionalHeader+0x48) ---
e=struct.unpack_from('<I',d,0x3C)[0]
assert d[e:e+4]==b'PE\x00\x00' and struct.unpack_from('<H',d,e+0x18)[0]==0x10B, "not PE32"
so=e+0x18+0x48; old=struct.unpack_from('<I',d,so)[0]
if old!=0x800000:
    struct.pack_into('<I',d,so,0x800000); print(f"     stack: {old:#x} -> 0x800000")
else: print("     stack: already 8MB")
# --- 9. NOP the JAE guarding the privileged 8253-PIT CPU-speed block ---
# signature: JAE(+0x0a) | MOV EAX,-666;POP ESI;MOV ESP,EBP;POP EBP;RET | CLI;MOV AL,B8;OUT 43
sig=bytes.fromhex('730ab866fdffff5e8be55dc3fab0b8e643')
done=bytes.fromhex('9090b866fdffff5e8be55dc3fab0b8e643')
i=d.find(sig)
if i>=0:
    d[i]=0x90; d[i+1]=0x90; print(f"     cpu-speed: JAE->NOP NOP at {i:#x} (PIT block now unreachable)")
elif d.find(done)>=0:
    print("     cpu-speed: already patched")
else:
    print("     cpu-speed: WARNING pattern not found (different build?) - if nitro.exe")
    print("                crashes on a 'privileged instruction', it needs manual patching.")
open(p,'wb').write(d)
PY

# ---- 10. build + install the Nitro launcher app ---------------------------
echo "[10] Building the Nitro launcher app"
TMP=$(mktemp -d)
swiftc -O -o "$TMP/nitro" "$DIR/i76-nitro-stub.swift"
B="$LAUNCHER/Contents"
mkdir -p "$B/MacOS" "$B/Resources"
cp "$TMP/nitro" "$B/MacOS/i76-nitro"
ICON="$(ls "$APP/Contents/Resources"/*.icns 2>/dev/null | head -1 || true)"
[ -n "$ICON" ] && cp "$ICON" "$B/Resources/app.icns"
cat > "$B/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleExecutable</key><string>i76-nitro</string>
  <key>CFBundleIdentifier</key><string>com.jkv.i76.nitro</string>
  <key>CFBundleName</key><string>Interstate 76 Nitro</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleIconFile</key><string>app</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
EOF
codesign -f -s - "$B/MacOS/i76-nitro"
rm -rf "$TMP"

echo
echo "Done. Launch:  $LAUNCHER"
echo "(Base + Nitro share one prefix - run one at a time. A re-sign re-prompts for"
echo " mic permission once: deny it. Backups kept as *.pre-* / smackorg.dll.)"
