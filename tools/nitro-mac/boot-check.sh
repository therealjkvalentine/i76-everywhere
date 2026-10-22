#!/bin/bash
# boot-check.sh APP : start APP (Interstate 76 Nitro.app) muted, Esc through the intro with i76probe3.exe, read the proxy log
# for the Nitro / shell lines, then end ONLY this app's Wine session (wineserver -k of its prefix). Refuses if a game runs.
A="$1"; H=$HOME/i76-nitro-mac-20261021; D="$A/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76 Nitro"
export DYLD_FALLBACK_LIBRARY_PATH="$A/Contents/Frameworks:$A/Contents/SharedSupport/wine/lib" WINEPREFIX="$A/Contents/SharedSupport/prefix" WINEDEBUG=-all WINEESYNC=1 WINEMSYNC=1
probe() { ( cd $H && "$A/Contents/SharedSupport/wine/bin/wine" $H/i76probe3.exe "$@" 2>&1 | tr -d '\r' | grep -v msync ); }
if pgrep -f 'i76\.exe|nitro\.exe' >/dev/null; then echo "REFUSED: a game runs"; exit 2; fi
[ -f "$D/mciproxy.log" ] && mv "$D/mciproxy.log" "$H/mciproxy.before-$(date +%H%M%S).log"
open --env I76_MUTE=1 "$A"; for i in $(seq 1 60); do sleep 1; pgrep -f 'nitro\.exe' >/dev/null && break; done; echo "nitro.exe after $i s"
sleep 20; W=$(probe wins | awk '/Nitro Pack/{print $2, $4; exit}'); echo "window/pid: $W"
export I76PROBE_HWND=${W% *} I76PROBE_PID=${W#* }
for k in 1 2 3; do probe key 1B >/dev/null; sleep 6; done; sleep 6
probe mods | grep -i -E "nitshell|zglide|glide2x|strlkup"
grep -E "^exe:|pit-skip|shell watch|nitshell hooks|nitro-form|zglide-tmufix: ZG|^nitro:|fps-cap|CRASH|PLAY track" "$D/mciproxy.log" | cut -c1-200
echo "CRASH lines: $(grep -c CRASH "$D/mciproxy.log")"; ps -axo etime,time,command | grep 'nitro.exe' | grep -v grep
cp "$D/mciproxy.log" "$H/boot-check-$(date +%H%M%S).log"
"$A/Contents/SharedSupport/wine/bin/wineserver" -k
for i in $(seq 1 30); do pgrep -f 'Nitro\.app/Contents/MacOS|nitro\.exe' >/dev/null || break; sleep 1; done
pgrep -fl 'nitro\.exe|winedbg' && echo "STILL RUNNING" || echo "stopped: no nitro.exe"
