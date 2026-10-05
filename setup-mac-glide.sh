#!/bin/bash
# Interstate '76 - turn a Mac DxWnd wrapper into the Glide setup: OpenGLide-HD under DxWnd.
#
# What the Mac daily install has run since 2026-10-04 (tools/openglide-hd/MAC-BUILD.md sections 7-10), as one step:
#   - i76.exe -glide through real OpenGLide (voyageur/openglide + tools/openglide-hd/*.patch), built here with
#     Homebrew mingw: ~100-120 fps on Apple Silicon, against ~22 for the software renderer under Rosetta
#   - DxWnd still owns the window: it scales the 640x480 menus and maps the cursor; OpenGLide draws the 3D into it
#     (OGL_OUTPUT=parent; the launcher computes OGL_VIEWPORT for the display at every start)
#   - 4x MSAA, the 3dfx-style gamma OpenGLide never applied (OGL_GAMMA), the gentle stretch to the screen's shape
#   - the music-fix proxy (music-fix/build-mac.sh) with the 120 fps switch set, and as the CD player: DxWnd's own
#     virtual CD is switched off, the proxy re-claims the music hooks and continues tracks instead of restarting them
#   - Wine's GDI DirectDraw for the menus (the GL one raced OpenGLide and crashed ~1 launch in 6)
#   - Terrain Resolution Medium (the frame's biggest CPU cost under Rosetta), music level raised if it was off
#
#   setup-mac-glide.sh [wrapper.app]     default: ~/Applications/Sikarugir/Interstate 76.app
#
# Needs: Xcode CLT (swiftc, clang), `brew install mingw-w64`, git (OpenGLide is cloned into ~/Library/Caches once).
# Run with the game closed. Every file it replaces is kept beside it as *.pre-glide-<timestamp>; the wrapper must
# already be a working DxWnd install (setup-dxwnd.sh / mac-install.command). Nitro is not touched.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="${1:-$HOME/Applications/Sikarugir/Interstate 76.app}"
P="$APP/Contents/SharedSupport/prefix"
G="$P/drive_c/GOG Games/Interstate 76"
DX="$P/drive_c/dxwnd/dxwnd.ini"
REG="$P/user.reg"
TS="pre-glide-$(date +%Y%m%d-%H%M%S)"
CACHE="$HOME/Library/Caches/i76-everywhere"

die() { echo "setup-mac-glide: $*" >&2; exit 1; }
[ -d "$G" ] || die "no game folder at $G"
[ -f "$DX" ] || die "no DxWnd profile at $DX (run setup-dxwnd.sh first)"
[ -f "$REG" ] || die "no Wine registry at $REG"
pgrep -f 'i76\.exe|nitro\.exe' >/dev/null && die "the game is running - quit it first"
pgrep -f "$(printf '%s' "$APP/Contents/SharedSupport/wine/bin/wineserver" | sed 's/[][\.*^$()+?{}|]/\\&/g')" >/dev/null \
    && die "this wrapper's wineserver is still running (it would overwrite the registry on exit)"
command -v i686-w64-mingw32-g++ >/dev/null || die "missing mingw - brew install mingw-w64"
command -v swiftc >/dev/null || die "missing swiftc - xcode-select --install"

keep() { [ -e "$1" ] && cp -p "$1" "$1.$TS" && echo "  kept $(basename "$1").$TS"; return 0; }

echo "== 1/6 OpenGLide-HD"
OG="$CACHE/openglide"
mkdir -p "$CACHE"
if [ ! -d "$OG/.git" ]; then git clone -q https://github.com/voyageur/openglide.git "$OG"; fi
( cd "$OG" && git am --abort >/dev/null 2>&1 || true
  git -c advice.detachedHead=false checkout -q ad9a3dd
  git -c user.name=i76 -c user.email=i76@local am -q "$HERE"/tools/openglide-hd/*.patch
  CXX=i686-w64-mingw32-g++ sh build-mingw.sh >/dev/null )
[ -f "$OG/glide2x.dll" ] || die "OpenGLide build failed"
keep "$G/Glide2x.dll"
cp "$OG/glide2x.dll" "$G/Glide2x.dll"
keep "$G/OpenGLid.INI"
# Version= must match the DLL or the file is ignored; 2 MB TMU / frame buffer are load-bearing (I'76 panics on more).
printf 'Configuration File for OpenGLide\r\n\r\nVersion=0.09rc9\r\n\r\n[Options]\r\nWrapperPriority=2\r\nCreateWindow=1\r\nInitFullScreen=0\r\nEnableMipMaps=0\r\nIgnorePaletteChange=0\r\nWrap565to5551=1\r\nEnablePrecisionFix=1\r\nEnableMultiTextureEXT=1\r\nEnablePaletteEXT=1\r\nEnableVertexArrayEXT=0\r\nTextureMemorySize=2\r\nFrameBufferMemorySize=2\r\nNoSplash=1\r\nWinOpenDelayMS=0\r\nResolution=0\r\n' > "$G/OpenGLid.INI"

echo "== 2/6 music-fix proxy"
"$HERE/music-fix/build-mac.sh" "$CACHE/Strlkup.mac.dll" >/dev/null
# the original goes to strlkup_orig.dll once (the proxy forwards to it by that name); never overwrite it
if [ ! -f "$G/strlkup_orig.dll" ]; then
    [ -f "$G/STRLKUP.DLL" ] || [ -f "$G/Strlkup.dll" ] || die "no Strlkup.dll in the game folder"
    for f in "$G/STRLKUP.DLL" "$G/Strlkup.dll"; do [ -f "$f" ] && { mv "$f" "$G/strlkup_orig.dll"; break; }; done
else
    keep "$G/Strlkup.dll"
fi
cp "$CACHE/Strlkup.mac.dll" "$G/Strlkup.dll"
[ -f "$G/I76PATCH.DLL" ] && mv "$G/I76PATCH.DLL" "$G/I76PATCH.DLL.disabled" && echo "  I76PATCH.DLL (GOG's 20 fps cap) -> .disabled"

echo "== 3/6 DxWnd profile (target 0 only)"
keep "$DX"
python3 - "$DX" <<'PY'
import re, sys
p = sys.argv[1]; b = open(p, 'rb').read(); s = b.decode('latin-1')
def setk(k, v):
    global s
    if re.search(r'(?m)^' + k + r'=', s): s = re.sub(r'(?m)^' + k + r'=[^\r\n]*', k + '=' + v, s)
    else: s = s.rstrip('\r\n') + '\r\n' + k + '=' + v + '\r\n'
setk('cmdline0', 'i76.exe -glide')     # DxWnd passes it as the WHOLE command line: program name first
setk('maxfps0', '0')                    # the proxy paces at 120; DxWnd's limiter only added waits
setk('sizx0', '1728'); setk('sizy0', '1117')   # the window's shape: the 14" panel's (a gentle stretch, no extra fov)
m = re.search(r'(?m)^flagm0=(\d+)', s)  # bit 0 = DxWnd's virtual CD: off, the proxy is the CD player now
if m: s = s[:m.start(1)] + str(int(m.group(1)) & ~1) + s[m.end(1):]
open(p, 'wb').write(s.encode('latin-1'))
PY

echo "== 4/6 Wine registry (environment, DirectDraw renderer, Retina off)"
keep "$REG"
python3 - "$REG" <<'PY'
import sys
p = sys.argv[1]; s = open(p, encoding='utf-8').read()
def section(key):
    global s
    if key not in s:
        s = s.rstrip('\n') + '\n\n' + key + ' 1791000000\n#time=1dd542a7cc3b12e\n'
    i = s.index(key); e = s.find('\n\n', i); e = len(s) if e < 0 else e
    return i, e
def setv(key, name, val):
    global s
    i, e = section(key)
    lines = s[i:e].split('\n')
    lines = [l for l in lines if not l.startswith('"%s"=' % name)]
    lines.insert(2, '"%s"=%s' % (name, val))
    s = s[:i] + '\n'.join(lines) + s[e:]
env = '[Environment]'
for k, v in [('I76_HIRES_CLOCK', '1'), ('I76_FIXED_STEP', '24'), ('I76_FRAMERATE_FIXES', '1'), ('I76_ENGINE_DT_FIX', '1'),
             ('I76_RENDER_INTERP', '1'), ('I76_FIX_HEALTH_PCT', '1'), ('I76_FIX_LABEL_TABLE', '1'), ('I76_FPS_CAP', '120'),
             ('I76_COLL_DEDUPE', '0'), ('I76_AI_ROLL_HOLD', '0'), ('I76_FPS_LOG', '5'), ('I76MUSIC_LOG', '1'),
             ('OGL_OUTPUT', 'parent'), ('OGL_VIEWPORT', '1728x1117'), ('OGL_MSAA', '4'), ('OGL_GAMMA', '1.3')]:
    setv(env, k, '"%s"' % v)
setv('[Software\\\\Wine\\\\AppDefaults\\\\i76.exe\\\\Direct3D]', 'renderer', '"gdi"')
setv('[Software\\\\Wine\\\\Mac Driver]', 'RetinaMode', '"n"')
open(p, 'w', encoding='utf-8').write(s)
PY

echo "== 5/6 player options (I76PLYR.DEF)"
PLYR="$G/I76PLYR.DEF"
if [ -f "$PLYR" ]; then
    keep "$PLYR"
    python3 - "$PLYR" <<'PY'
import sys
p = sys.argv[1]; b = bytearray(open(p, 'rb').read())
# the options block is saved at file offset 0x40 (re/subsystems/options.md: 0x654b80 + n)
if len(b) > 0x50:
    b[0x47] = 1                       # Terrain Resolution: Medium - holds the 120 cap under Rosetta, High does not
    if b[0x50] <= 1: b[0x50] = 5      # Music level: 0/1 is "off" (the engine mutes the CD and stops it after menus)
    open(p, 'wb').write(b)
    print('  terrain resolution -> Medium, music level', b[0x50])
PY
else
    echo "  none yet (first run): set Graphic Detail -> Terrain Resolution: Medium in game"
fi

echo "== 6/6 launcher (computes OGL_VIEWPORT for the display at every start)"
MB="$APP/Contents/MacOS"
[ -f "$MB/Sikarugir.orig" ] || cp -p "$MB/Sikarugir" "$MB/Sikarugir.orig"
keep "$MB/Sikarugir"
swiftc -O -o "$CACHE/launch-stub" "$HERE/i76-launch-stub.swift"
cp "$CACHE/launch-stub" "$MB/Sikarugir.new" && codesign -f -s - "$MB/Sikarugir.new" 2>/dev/null && mv -f "$MB/Sikarugir.new" "$MB/Sikarugir"

echo
echo "Done: $APP now runs i76.exe -glide through OpenGLide under DxWnd."
echo "Every replaced file is kept beside it as *.$TS."
