#!/bin/bash
# make-nitro-app.sh GOLD_APP NEW_APP PAYLOAD_DIR STUB [OWNER_TAG]
#
# nitro-mac lane 2026-10-21 (docs/records/NITRO-MAC-2026-10-21.md). Runs ON a Mac. Makes the standalone
# "Interstate 76 Nitro.app" as an APFS clone of the Gold wrapper GOLD_APP, then changes ONLY the clone:
#   - the clone's prefix loses the Gold game folder and any old "Interstate 76 Nitro Pack" folder (the Gold app keeps its own)
#   - PAYLOAD_DIR (GOG Nitro Pack stock + our proxy as Strlkup.dll + GOG's strlkup.dll as strlkup_orig.dll) goes to
#     C:\GOG Games\Interstate 76 Nitro
#   - the Gold app's renderer (OpenGLide-HD Glide2x.dll + OpenGLid.INI) and IPXWrapper (ipxwrapper.dll, wsock32.dll,
#     mswsock.dll) are COPIED (read) from the Gold game folder; GOG's own glide2x.dll / OpenGLid.INI go to _gog-originals\
#   - DxWnd profile 1 -> nitro.exe -glide (same flags as the Gold profile), the Gold app's profile-2 lines dropped
#   - prefix env: Nitro switch set (the whole-sim tick I76_SIM_TICK_MS=41.667 + I76_SIM_TICK_INPUT as PC main Nitro runs it,
#     the Mac Gold apps' 120 fps cap, fixes, music); Gold-only switches removed. Until 2026-10-25 this was a 24 fps cap (the
#     41.7 ms step came from the cap while the tick clashed with nitro-ai's ai_FrameTick site; fixed by 91d2b14, chained):
#     docs/records/NITRO-MAC-UNCAP-2026-10-25.md
#   - AppDefaults\nitro.exe: wsock32 / mswsock native,builtin, WindowsFloatWhenInactive = all (as i76.exe has)
#   - Info.plist: own bundle id / name; Contents/MacOS/Sikarugir = STUB (i76-nitro-app-stub.swift)
# The Gold app is only read. Refuses if NEW_APP exists or a game runs in GOLD_APP.
set -euo pipefail
GOLD="$1"; NEW="$2"; PAY="$3"; STUB="$4"
GP="$GOLD/Contents/SharedSupport/prefix"; NP="$NEW/Contents/SharedSupport/prefix"
GG="$GP/drive_c/GOG Games/Interstate 76"; ND="$NP/drive_c/GOG Games/Interstate 76 Nitro"
[ -d "$GOLD/Contents" ] || { echo "no Gold app at $GOLD"; exit 1; }
[ -e "$NEW" ] && { echo "REFUSED: $NEW exists"; exit 1; }
[ -f "$PAY/nitro.exe" ] && [ -f "$PAY/Strlkup.dll" ] && [ -f "$PAY/strlkup_orig.dll" ] || { echo "bad payload $PAY"; exit 1; }
if pgrep -f 'i76\.exe|nitro\.exe' >/dev/null; then echo "REFUSED: a game is running"; pgrep -fl 'i76\.exe|nitro\.exe'; exit 2; fi

goldsum() { ( cd "$GOLD" && find Contents/MacOS Contents/Info.plist "Contents/SharedSupport/prefix/user.reg" \
  "Contents/SharedSupport/prefix/drive_c/dxwnd/dxwnd.ini" -type f -print0 | xargs -0 md5 -r | sort -k2;
  find "Contents/SharedSupport/prefix/drive_c/GOG Games" -type f | wc -l ) | md5 -q; }
G0=$(goldsum); echo "gold fingerprint before: $G0"

echo "[1] clone"; cp -cR "$GOLD" "$NEW"
case "$NP" in "$NEW"/*) ;; *) echo "path guard"; exit 3;; esac
echo "[2] clone: drop Gold game folder + old Nitro folder"
rm -rf "$NP/drive_c/GOG Games/Interstate 76" "$NP/drive_c/GOG Games/Interstate 76 Nitro Pack"
echo "[3] payload"; mkdir -p "$ND"; ( cd "$PAY" && tar -cf - . ) | ( cd "$ND" && tar -xf - )
mkdir -p "$ND/_gog-originals"; mv "$ND/glide2x.dll" "$ND/OpenGLid.INI" "$ND/_gog-originals/"
cp "$GG/Glide2x.dll" "$ND/glide2x.dll"; cp "$GG/OpenGLid.INI" "$ND/OpenGLid.INI"
for f in ipxwrapper.dll wsock32.dll mswsock.dll; do cp "$GG/$f" "$ND/$f"; done

echo "[4] dxwnd.ini"; INI="$NP/drive_c/dxwnd/dxwnd.ini"
perl -i -ne 'if (/^\[target\]/) {$t=1} elsif (/^\[/) {$t=0}
  next if $t && /^[A-Za-z]+1=/;
  s/^title0=.*?(\r?)$/title0=Interstate 76 Nitro$1/; s/^path0=.*?(\r?)$/path0=C:\\GOG Games\\Interstate 76 Nitro\\nitro.exe$1/;
  s/^cmdline0=.*?(\r?)$/cmdline0=nitro.exe -glide$1/; s/^notes0=.*?(\r?)$/notes0=$1/; print' "$INI"
grep -E '^(title|path|cmdline)[0-9]=' "$INI"

echo "[5] registry"
gv="$NEW/Contents/Frameworks/GStreamer.framework/Versions/1.0"
export DYLD_FALLBACK_LIBRARY_PATH="$NEW/Contents/Frameworks:$gv/lib:$NEW/Contents/SharedSupport/wine/lib"
export WINEPREFIX="$NP" WINEESYNC=1 WINEMSYNC=1 WINEDEBUG=-all
W="$NEW/Contents/SharedSupport/wine/bin/wine"
r() { "$W" reg "$@" >/dev/null 2>&1 || echo "  reg $* failed"; }
for k in I76_AI_ROLL_HOLD I76_COLL_DEDUPE I76_COOP_AI I76_COOP_CHAIN I76_ENGINE_DT_FIX I76_FIXED_STEP I76_FRAMERATE_FIXES I76_RENDER_INTERP; do
  r delete 'HKCU\Environment' /v $k /f; done
for kv in I76_HIRES_CLOCK=1 I76_FIX_HEALTH_PCT=1 I76_FIX_LABEL_TABLE=1 \
          I76_ZGLIDE_TMUFIX=1 I76_CAM_GROUND_FIX=1 I76_TERRAIN_HULL_FIX=1 I76_MUSIC_RETAIL=1 I76_MUSIC_RESUME=1 \
          I76_MUSIC_THREAD=1 I76_SIM_TICK_MS=41.667 I76_SIM_TICK_INPUT=1 I76_FPS_CAP=120 I76_FPS_LOG=5; do
  r add 'HKCU\Environment' /v "${kv%%=*}" /d "${kv#*=}" /f; done
r add 'HKCU\Software\Wine\AppDefaults\nitro.exe' /v Version /d win98 /f
r add 'HKCU\Software\Wine\AppDefaults\nitro.exe\Explorer' /v Desktop /d i76 /f
r add 'HKCU\Software\Wine\AppDefaults\nitro.exe\DllOverrides' /v wsock32 /d native,builtin /f
r add 'HKCU\Software\Wine\AppDefaults\nitro.exe\DllOverrides' /v mswsock /d native,builtin /f
r add 'HKCU\Software\Wine\AppDefaults\nitro.exe\Mac Driver' /v WindowsFloatWhenInactive /d all /f
"$NEW/Contents/SharedSupport/wine/bin/wineserver" -w || true
awk '/^\[Environment\]/,/^$/' "$NP/user.reg"

echo "[6] bundle"
plutil -replace CFBundleIdentifier -string com.sikarugir.Interstate76Nitro "$NEW/Contents/Info.plist"
plutil -replace CFBundleName -string "Interstate76Nitro" "$NEW/Contents/Info.plist"
rm -f "$NEW/Contents/MacOS/Sikarugir.dxwnd-stub" "$NEW/Contents/MacOS/Sikarugir.pre-20261004b" "$NEW/Contents/MacOS/Sikarugir.minos26"
cp "$STUB" "$NEW/Contents/MacOS/Sikarugir"; chmod 755 "$NEW/Contents/MacOS/Sikarugir"
G1=$(goldsum); echo "gold fingerprint after:  $G1"; [ "$G0" = "$G1" ] && echo "GOLD UNCHANGED" || echo "!! GOLD CHANGED"
md5 -r "$ND/Strlkup.dll" "$ND/strlkup_orig.dll" "$ND/nitro.exe" "$ND/nitshell.dll" "$ND/glide2x.dll" "$ND/ipxwrapper.dll" \
  "$ND/wsock32.dll" "$ND/mswsock.dll" "$NEW/Contents/MacOS/Sikarugir" "$NP/drive_c/dxwnd/dxwnd.ini"
du -sh "$ND"; echo DONE
