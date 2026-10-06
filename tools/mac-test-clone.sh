#!/bin/bash
# Interstate '76 - Mac test copies that never raise a macOS privacy prompt (microphone, Documents, ...).
#
#   tools/mac-test-clone.sh make NAME [SOURCE.app]   APFS-clone SOURCE (default: the daily install) as NAME.app
#   tools/mac-test-clone.sh run  NAME                start it from this shell (see "why run, not open")
#   tools/mac-test-clone.sh stop NAME                kill its wineserver and everything under the bundle
#
# NAME is a bundle name in ~/Applications/Sikarugir ("I76 IPX TEST") or a path to a .app.
#
# Why the prompt appeared (measured 2026-10-06, MAC-BUILD.md section 12):
#   - Wine's CoreAudio driver opens an AudioUnit on every INPUT device (built-in mic, webcams, the EVO4) as soon
#     as anything initialises winmm's wave devices: waveOutGetNumDevs alone runs ~270 format tests across them.
#     macOS counts that as microphone access.
#   - TCC remembers the answer per app PATH plus the cdhash of Contents/MacOS/Sikarugir (the wrappers are ad-hoc
#     signed; TCC.db stores client_type 1 = path and csreq 'cdhash H"..."'). So every new clone name, and every
#     rebuild of the launcher, asks again - including on the daily install after a launcher change.
#
# What this script does about it, two independent layers:
#   1. make: the clone gets Wine's null audio driver (HKCU\Software\Wine\Drivers "Audio"="", "User explicitly
#      chose no driver" in the mmdevapi trace): CoreAudio is never loaded, nothing touches an input device, and
#      the test is silent, as AGENTS.md requires of test instances. I76_MUSIC_THREAD=1 keeps the proxy's MP3
#      open from hanging the game thread when there is no audio device.
#   2. run: started from a shell instead of through LaunchServices (`open`), every process of the game is
#      attributed by TCC to the app that owns the shell (responsibility_get_pid_responsible_for_pid on i76.exe
#      returned Claude Code's pid). That app's existing decision applies; no new app, no new prompt. From
#      Terminal.app it is Terminal's decision instead (asked once, ever, if it has none).
#
# The daily install is never modified. The clone gets its own bundle id so LaunchServices keeps the two apart,
# and any user-folder symlink that leaves the prefix (Templates -> ~/Templates) becomes a plain folder.
set -euo pipefail
ROOT="$HOME/Applications/Sikarugir"
DAILY="$ROOT/Interstate 76.app"

die() { echo "mac-test-clone: $*" >&2; exit 1; }
app_path() { case "$1" in */*.app|*.app) [[ "$1" == /* ]] && echo "$1" || echo "$ROOT/$1" ;; *) echo "$ROOT/$1.app" ;; esac; }

cmd="${1:-}"; name="${2:-}"
[ -n "$cmd" ] && [ -n "$name" ] || { sed -n '4,7p' "$0"; exit 2; }
APP="$(app_path "$name")"
P="$APP/Contents/SharedSupport/prefix"
WINE="$APP/Contents/SharedSupport/wine"
[ "$APP" != "$DAILY" ] || die "refusing to touch the daily install ($DAILY)"

case "$cmd" in
make)
    SRC="$(app_path "${3:-$DAILY}")"
    [ -d "$SRC" ] || die "no source app at $SRC"
    [ -e "$APP" ] && die "$APP already exists"
    pgrep -f "$(basename "$SRC")/Contents" >/dev/null && die "the source is running - quit it first"
    cp -c -R "$SRC" "$APP"
    slug="$(basename "$APP" .app | tr -cs 'A-Za-z0-9' '.' | tr 'A-Z' 'a-z' | sed 's/^\.//; s/\.$//')"
    /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.i76everywhere.test.$slug" \
                            -c "Set :CFBundleName $(basename "$APP" .app)" "$APP/Contents/Info.plist"
    # user folders that point out of the prefix: plain folders (a symlink into ~ is a TCC folder prompt)
    find "$P/drive_c/users" -maxdepth 2 -type l | while read -r l; do
        case "$(readlink "$l")" in /*) rm "$l"; mkdir "$l"; echo "  $(basename "$l"): plain folder" ;; esac
    done
    python3 - "$P/user.reg" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p, encoding='utf-8').read()
def setv(key, name, val):
    global s
    if key not in s:
        s = s.rstrip('\n') + '\n\n' + key + ' 1791000000\n'
    i = s.index(key); e = s.find('\n\n', i); e = len(s) if e < 0 else e
    lines = [l for l in s[i:e].split('\n') if not l.startswith('"%s"=' % name)]
    lines.insert(1 if len(lines) < 2 or not lines[1].startswith('#time') else 2, '"%s"=%s' % (name, val))
    s = s[:i] + '\n'.join(lines) + s[e:]
setv('[Software\\\\Wine\\\\Drivers]', 'Audio', '""')          # null driver: no CoreAudio, no input devices, silent
setv('[Environment]', 'I76_MUSIC_THREAD', '"1"')                # MCI off the game thread (no audio device = slow open)
setv('[Environment]', 'I76_SKIP_MOVIES', '"1"')
open(p, 'w', encoding='utf-8').write(s)
PY
    echo "made $APP (null audio, music thread, movies skipped). Start it with: $0 run \"$name\""
    ;;
run)
    [ -d "$APP" ] || die "no app at $APP"
    pgrep -f 'i76\.exe' >/dev/null && die "a game is already running"
    grep -q '^"Audio"=""' "$P/user.reg" || echo "mac-test-clone: warning: $APP has a real audio driver (not silent)" >&2
    nohup "$APP/Contents/MacOS/Sikarugir" >/dev/null 2>&1 &
    for _ in $(seq 1 60); do sleep 1; pgrep -f 'i76\.exe' >/dev/null && { echo "started (pid $(pgrep -f 'i76\.exe' | head -1))"; exit 0; }; done
    die "i76.exe did not appear within 60 s"
    ;;
stop)
    DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$WINE/lib" WINEPREFIX="$P" "$WINE/bin/wineserver" -k 2>/dev/null || true
    sleep 2
    pkill -9 -f "$(basename "$APP" | sed 's/[][\.*^$()+?{}|]/\\&/g')/Contents" 2>/dev/null || true
    echo stopped
    ;;
*) die "unknown command $cmd (make | run | stop)" ;;
esac
