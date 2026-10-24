#!/bin/bash
# stub-test.sh APP CLONE [minutes] : the launch stub's own-prefix test (nitro-mac lane 2026-10-22, NITRO-MAC s.8), on a Mac.
#   APP is started muted, its game window minimised (i76probe3 showwin 6); CLONE (a copy of APP with its own prefix) is
#   started 60 s later and quit 60 s after that by SIGTERM to its stub (what a Dock / cmd-Q quit sends). APP must keep
#   running, minimised, for [minutes] (default 10); then APP is quit the same way and both prefixes must be empty.
# Every 30 s: per app, the stub pid, the game pid (own processes: image under the bundle), Wine windows.
# A boot that dies before the APP's game window (the EIP-0 wined3d fault) makes the run VOID (exit 3); rerun it.
A="$1"; C="$2"; MIN=${3:-10}; H=$HOME/i76-nitro-mac-20261021
# own processes = executable image under the bundle's SharedSupport (pidpath = proc_pidpath; `ps -E` shows no WINEPREFIX on
# Wine's Windows processes, 2026-10-23), as the stubs' ownProcs
own() { $H/pidpath " " | awk -F ' [|] ' -v p="$1/Contents/SharedSupport/" 'index($1, p)' ; }   # image field only (not the grep's own args)
game() { own "$1" | grep -i "nitro.exe" | grep -v grep | awk '{print $1}' | head -1; }
stub() { pgrep -f "$(printf '%s' "$1" | sed 's/[][()\.*^$+?{}|]/\\&/g')/Contents/MacOS/Sikarugir" | head -1; }
probe() { ( export DYLD_FALLBACK_LIBRARY_PATH="$1/Contents/Frameworks:$1/Contents/SharedSupport/wine/lib" WINEPREFIX="$1/Contents/SharedSupport/prefix" WINEDEBUG=-all WINEESYNC=1 WINEMSYNC=1
            shift; cd $H && "$A/Contents/SharedSupport/wine/bin/wine" $H/i76probe3.exe "$@" 2>&1 | tr -d '\r' | grep -v msync ); }
line() { echo "$(date +%T) t+$(( $(date +%s) - T0 ))s APP stub $(stub "$A") game $(game "$A") | CLONE stub $(stub "$C") game $(game "$C") | own windows: $($H/winlist | grep -c pid)"; }
pgrep -f 'nitro\.exe' >/dev/null && { echo "REFUSED: a nitro.exe runs"; exit 2; }
T0=$(date +%s)
open --env I76_MUTE=1 "$A"; sleep 25
W=$(probe "$A" wins | awk '/Nitro Pack/{print $2, $4; exit}'); echo "APP window/pid $W"
export I76PROBE_HWND=${W% *} I76PROBE_PID=${W#* }
[ -n "$(game "$A")" ] && [ -n "${W% *}" ] || { echo "VOID: APP game not up at t+25 s (boot crash?)"; grep CRASH "$A/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76 Nitro/mciproxy.log" | head -2; kill -TERM $(stub "$A") 2>/dev/null; exit 3; }
probe "$A" showwin 6 & PP=$!; sleep 15; kill $PP 2>/dev/null; line
sleep 35; open --env I76_MUTE=1 "$C"; sleep 30; line
sleep 30; S=$(stub "$C"); echo "$(date +%T) SIGTERM to CLONE stub $S"; kill -TERM $S; sleep 20; line
probe "$A" wins | head -3
END=$(( T0 + MIN * 60 )); while [ $(date +%s) -lt $END ]; do sleep 30; line; [ -z "$(game "$A")" ] && { echo "APP GAME GONE"; break; }; done
S=$(stub "$A"); echo "$(date +%T) SIGTERM to APP stub $S"; kill -TERM $S; sleep 25; line
echo "own processes left: APP $(own "$A" | wc -l | tr -d ' '), CLONE $(own "$C" | wc -l | tr -d ' ')"
