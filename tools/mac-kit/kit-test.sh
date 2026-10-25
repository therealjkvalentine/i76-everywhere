#!/bin/bash
# kit-test.sh APP menu|mission [SECONDS] [OUTDIR] - MAINTAINER: boot a kit-built app headless and silent, read its proxy log.
#   menu     plain start: passes when the proxy logs the shell up (Gold: the Esc-menu pointer fix, installed once the main menu
#            runs; with PROBE=<i76probe.exe> Esc is sent through the intro movies. Nitro: NITSHELL attached and hooked, no key
#            sent: Esc at Nitro's main menu quits) and nothing failed
#   mission  I76_MISSION boot (Gold t05, Nitro P01): passes when the proxy logs mission frames ("fps: N (M frames")
# Started through LaunchServices with open -n --env (an SSH-started process gets no window). Muted: I76_MUTE=1; build the app with --null-audio for
# a test, so Wine never opens CoreAudio. Stops only this app's processes: SIGTERM to its launcher (which reaps its own Wine
# processes), then this prefix's wineserver -k. Refuses while the app runs. Prints PASS / FAIL and the log's key lines.
set -u
A="${1%/}"; MODE="$2"; T="${3:-150}"; OUT="${4:-$HOME/i76-mac-kit-test/runs}"
[ -x "$A/Contents/MacOS/Sikarugir" ] || { echo "no app $A"; exit 2; }
P="$A/Contents/SharedSupport/prefix"; G="$(find "$P/drive_c/GOG Games" -mindepth 1 -maxdepth 1 -type d | head -1)"
case "$G" in *Nitro) KIND=nitro; MIS=P01;; *) KIND=gold; MIS=t05;; esac
# this app's processes: its launcher and its wineserver (their command lines keep the bundle path; Wine rewrites the
# .exe processes' command lines, and those end with this prefix's wineserver -k below)
mine() { ps -A -ww -o pid=,command= | grep -F "$A/Contents/" | grep -v -e ' awk ' -e 'grep ' | awk '{print $1}'; }
[ -z "$(mine)" ] || { echo "REFUSED: $A is running"; exit 2; }
mkdir -p "$OUT"; tag="$KIND-$MODE-$(date +%H%M%S)"
[ -f "$G/mciproxy.log" ] && mv "$G/mciproxy.log" "$OUT/$tag.before.log"
# through LaunchServices (open -n --env, the lab's Mac pattern): a process started from an SSH shell is outside the GUI
# session and Wine's Mac driver cannot open a window there ("no driver could be loaded")
env=(--env I76_MUTE=1 --env I76_SKIP_MOVIES=1); [ "$MODE" = mission ] && env+=(--env I76_MISSION=$MIS)
open -n "${env[@]}" "$A" || { echo "open failed"; exit 2; }
STUB=""; for _ in $(seq 1 20); do STUB=$(ps -A -ww -o pid=,command= | grep -F "$A/Contents/MacOS/Sikarugir" | grep -v 'grep ' | awk '{print $1; exit}'); [ -n "$STUB" ] && break; sleep 1; done
[ -n "$STUB" ] || { echo "the launcher did not start"; exit 2; }
t0=$(date +%s); res=FAIL; why="timeout ${T}s"
while [ $(( $(date +%s) - t0 )) -lt "$T" ]; do
    sleep 5
    kill -0 $STUB 2>/dev/null || { why="launcher exited after $(( $(date +%s) - t0 )) s"; break; }
    L="$G/mciproxy.log"; [ -f "$L" ] || continue
    # the intro movies wait for a key: Esc through them (from 30 s, every 10 s) until the shell is up, never after it
    # (Esc at Nitro's main menu quits). Needs PROBE = tools/wine-probe i76probe.exe (its "key" command)
    if [ "$MODE" = menu ] && [ "$KIND" = gold ] && [ -n "${PROBE:-}" ] && [ $(( $(date +%s) - t0 )) -ge 30 ] && [ $(( ($(date +%s) - t0) % 10 )) -lt 5 ]; then
        ( cd "$(dirname "$PROBE")" && DYLD_FALLBACK_LIBRARY_PATH="$A/Contents/Frameworks:$A/Contents/SharedSupport/wine/lib" WINEPREFIX="$P"           WINEDEBUG=-all WINEESYNC=1 WINEMSYNC=1 "$A/Contents/SharedSupport/wine/bin/wine" "$PROBE" key 1B >/dev/null 2>&1 )
        keys=$(( ${keys:-0} + 1 ))
    fi
    if [ "$MODE" = mission ]; then
        [ "$(grep -cE 'fps: [0-9.]+ \([0-9]+ frames' "$L")" -ge 6 ] && { res=PASS; why="mission frames at $(( $(date +%s) - t0 )) s"; break; }
    elif [ "$KIND" = gold ]; then
        grep -q 'menu-ptr: .*call sites repointed' "$L" && { sleep 10; res=PASS; why="shell up at $(( $(date +%s) - t0 )) s"; break; }
    else
        grep -q 'nitro-types: ON' "$L" && grep -q 'nitshell hooks: dpEnumSessions ok' "$L" && { sleep 20; kill -0 $STUB 2>/dev/null && res=PASS; why="NITSHELL up and hooked at $(( $(date +%s) - t0 )) s, still running 20 s later"; break; }
    fi
done
cp "$G/mciproxy.log" "$OUT/$tag.log" 2>/dev/null
kill -TERM $STUB 2>/dev/null; for _ in $(seq 1 40); do kill -0 $STUB 2>/dev/null || break; sleep 1; done
gv="$A/Contents/Frameworks/GStreamer.framework/Versions/1.0"
DYLD_FALLBACK_LIBRARY_PATH="$A/Contents/Frameworks:$gv/lib:$A/Contents/SharedSupport/wine/lib" WINEPREFIX="$P" \
    "$A/Contents/SharedSupport/wine/bin/wineserver" -k 2>/dev/null; sleep 3
left=$(mine | wc -l | tr -d ' ')
L="$OUT/$tag.log"
crash=$(grep -c 'CRASH' "$L" 2>/dev/null); bad=$(grep -ciE 'NOT applied|UNEXPECTED|bytes differ' "$L" 2>/dev/null)
fps=$(grep -oE 'fps: [0-9.]+ \(' "$L" 2>/dev/null | tail -8 | grep -oE '[0-9.]+' | awk '{s+=$1; n++} END {if (n) printf "%.1f", s/n; else print "-"}')
[ "${crash:-0}" -eq 0 ] && [ "${bad:-0}" -eq 0 ] || res=FAIL
echo "$res $tag: $why (Esc keys sent ${keys:-0}); CRASH lines ${crash:-?}, NOT-applied/UNEXPECTED/differ lines ${bad:-?}, fps (last 8 lines) $fps, processes left $left; log $L"
grep -E '^ *(exe:|mission-launch:|menu-ptr:|mp-menu:|nitro-types:|nitro-mp:|pit-skip:|zglide-tmufix:|coop-ai:|fps-cap:|music:)' "$L" 2>/dev/null | cut -c1-170 | sort -u | head -24
[ "$res" = PASS ]
