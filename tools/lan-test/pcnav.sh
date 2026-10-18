#!/bin/bash
# pcnav.sh cmd... : drive the PC's LAN copy (Git Bash on the PC) with the native i76probe (build/i76probe.exe).
#   start            PLAY-LAN.bat, wait for its i76.exe (by path), Esc to the main menu; pid saved in build/pc.pid
#   calib2           move the pointer to two points, read the shell's mouse object -> build/pc-map.txt
#   nav host|join, hostgo [row y], joingo, drive SECS, pos, state, shell, st, find TEXT, stop (only the pid we started)
# Needs the console lock (pc-lock.ps1 -Take) while the game is up: it takes the screen, mouse and keyboard.
here=$(cd "$(dirname "$0")" && pwd); LAN=${LAN:-/c/Users/james/Games/Interstate76-LAN-2026-10-17/Interstate 76}
PR="$here/build/i76probe.exe"; PIDF="$here/build/pc.pid"; MAPF="$here/build/pc-map.txt"
[ -f "$PIDF" ] && export I76PROBE_PID=$(cat "$PIDF")
P() { "$PR" "$@" | tr -d '\r'; }
lanpid() { powershell.exe -NoProfile -Command "(Get-Process i76 -ErrorAction SilentlyContinue | Where-Object { \$_.Path -like '*Interstate76-LAN-2026-10-17*' } | Select-Object -First 1).Id" | tr -d '\r'; }
[ -f "$MAPF" ] && export I76PROBE_MAP="$(cat "$MAPF")"
st() { P shell | awk 'NR==1{for(i=1;i<=NF;i++){if($i=="mfn")m=$(i+1); if($i=="sfn")s=$(i+1)}} /button id/{b=b" "$3} END{print s" "m b}'; }
top() { local s k; for k in 1 2 3 4 5 6 7 8; do s=$(st)
    case "$s" in "0x10025a50 0x00000000 13 2 0 17") return 0;; *" 0x1000e6b0"*) P key 1B >/dev/null;;
      "0x10025a50 "*) P click 446 310 >/dev/null;; *) P key 1B >/dev/null;; esac; sleep 2; done; echo "top FAILED: $s"; return 1; }
step() { local t s; for t in 1 2 3; do P click $1 $2 >/dev/null; sleep 2.5; s=$(st); echo "$s" | grep -q -E "$3" && return 0; echo "  miss $1,$2 try $t: $s"; done; return 1; }
nav() { local r; for r in 1 2 3; do top || continue
    step 446 310 " 15 1$" || continue; step 394 350 " 3 5$" || continue
    if [ "$1" = host ]; then step 366 378 " 6 7 14 8 16$" || continue; else step 416 378 " 6 7 14 8 16$" || continue; fi
    P click 343 405 >/dev/null; sleep 6; echo "nav $1: $(st)"; return 0; done; echo "nav $1 FAILED"; return 1; }
hostgo() { local y=${1:-208}; P click 67 $y >/dev/null; sleep 2; P click 298 461 >/dev/null
  local i; for i in $(seq 1 20); do sleep 2; P state | grep -q "net 1" && break; done; P state | head -3; }
joingo() { local t i; for t in 1 2 3; do P click 80 157 >/dev/null; sleep 2; P click 298 461 >/dev/null
    for i in $(seq 1 10); do sleep 2; P state | grep -q "net 1" && { P state | head -4; return 0; }; done; echo "join try $t: $(P state | sed -n 2p)"; done; return 1; }
calib2() { local wx wy mo a b c d
  read wx wy < <(P wins | awk '/\(i76\)/ && /Gold Edition/{split($(NF-1),p,","); print p[1], p[2]; exit}')
  mo=$(P peek shell+cc514 1)
  P move 0 0 >/dev/null; I76PROBE_MAP= I76PROBE_RAW=1 P move 1200 300 >/dev/null; sleep 0.8; set -- $(P peek $mo 13 | tail -1); a=$((16#$4)); b=$((16#$5))
  I76PROBE_MAP= I76PROBE_RAW=1 P move 2200 1100 >/dev/null; sleep 0.8; set -- $(P peek $mo 13 | tail -1); c=$((16#$4)); d=$((16#$5))
  python -c "kx=1000/($c-$a); ky=800/($d-$b); print('%.4f %.1f %.4f %.1f' % (kx, 1200-kx*$a, ky, 300-ky*$b))" > "$MAPF"
  echo "calib2 (points inside the 3440x1440 4:3 picture; measured map 3.0 760 3.0 0): client 1200,300 -> UI $a,$b; 2200,1100 -> UI $c,$d; map $(cat "$MAPF")"; }
drive() { local end=$(( $(date +%s) + $1 )) i=0
  while [ $(date +%s) -lt $end ]; do P key 57 4800 >/dev/null &
    sleep 1; [ $((i%2)) = 0 ] && P key 41 700 >/dev/null || P key 44 700 >/dev/null; wait
    echo "$(date +%H:%M:%S) $(P pos)"; i=$((i+1)); done; }
cmd=$1; shift
case $cmd in
  start) [ -n "$(lanpid)" ] && { echo "LAN copy already running: $(lanpid)"; exit 1; }
         cmd.exe //c start "" "$(cygpath -w "$LAN/PLAY-LAN.bat")"; for i in $(seq 1 60); do sleep 1; p=$(lanpid); [ -n "$p" ] && break; done
         echo "$p" > "$PIDF"; export I76PROBE_PID=$p; echo "pid $p after $i s"; sleep 25
         for k in 1 2 3 4 5; do P key 1B >/dev/null; sleep 4; st | grep -q "^0x10025a50 0x00000000 13 2 0 17" && { echo "main menu ($k Esc)"; exit 0; }; done; echo "main menu NOT reached: $(st)";;
  stop) p=$(cat "$PIDF" 2>/dev/null); [ -n "$p" ] && [ "$p" = "$(lanpid)" ] && taskkill //PID $p //F && rm -f "$PIDF";;
  calib2) calib2;; top) top && echo top;; nav) nav "$@";; st) st;; drive) drive "$@";; hostgo) hostgo "$@";; joingo) joingo;;
  *) P $cmd "$@";;
esac
