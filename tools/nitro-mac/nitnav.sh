#!/bin/bash
# nitnav.sh APP cmd ... : drive Nitro's shell in APP's Wine session on an UNLOCKED Mac (nitro-mac lane 2026-10-21).
#   start            open APP muted (I76_MUTE=1), Esc through the intro; marker file = ours
#   calib            warp the real pointer to two client points, read NITSHELL's mouse object -> UI map (saved)
#   click X Y        UI 640x480 point: i76probe mclick (holds the shell's mouse object there; button via SendInput)
#   join             MELEE group > MULTIPLAYER > JOIN > IPX (the lab instrument's points, NITRO-MP-DESIGN s.0.5)
#   list             the JOIN list: count [nitshell+0x15b038], row names (0xe4-byte rows at +0x1593b8)
#   joinrow          click row 0, then JOIN GAME;   net    state / net flag / my id / host id / players
#   stop             wineserver -k of APP's prefix (only if this lane started it)
A="$1"; shift; H=$HOME/i76-nitro-mac-20261021
export DYLD_FALLBACK_LIBRARY_PATH="$A/Contents/Frameworks:$A/Contents/SharedSupport/wine/lib" WINEPREFIX="$A/Contents/SharedSupport/prefix" WINEDEBUG=-all WINEESYNC=1 WINEMSYNC=1
P() { ( cd $H && "$A/Contents/SharedSupport/wine/bin/wine" $H/i76probe3.exe "$@" 2>&1 | tr -d '\r' | grep -v msync ); }
ids() { W=$(P wins | awk '/Nitro Pack/{print $2, $4; exit}'); export I76PROBE_HWND=${W% *} I76PROBE_PID=${W#* }; }
nsb() { printf '0x%08x' $(( $(P mods | awk 'tolower($3)=="nitshell.dll"{print $1}') )); }
peek() { P peek $(printf '0x%x' $1) ${2:-1} | tail -1; }
win() { P wins | awk -v h=$I76PROBE_HWND '$2==h{for(i=1;i<=NF;i++) if($i=="rect"){split($(i+1),p,","); split($(i+2),s,"x"); print p[1], p[2], s[1], s[2]}}'; }
mouse() { local b mo; b=$(nsb); mo=0x$(peek $((b+0x130484))); set -- $(peek $((mo+0x2c)) 2); echo $((16#$1)) $((16#$2)); }
case "$1" in
start) pgrep -f 'nitro\.exe' >/dev/null && { echo "REFUSED: nitro.exe runs"; exit 2; }
  open --env I76_MUTE=1 "$A"; touch $H/ours; for i in $(seq 1 60); do sleep 1; pgrep -f 'nitro\.exe' >/dev/null && break; done
  sleep 15; ids   # Esc only while NITSHELL's mouse object does not exist yet (the intro): an Esc at the main menu quits Nitro
  for k in 1 2 3 4 5 6 7 8 9 10; do b=$(nsb); [ "$b" != 0x00000000 ] && [ "$(peek $((b+0x130484)))" != 00000000 ] && break; P key 1B >/dev/null; sleep 6; done
  echo "started; window $I76PROBE_HWND pid $I76PROBE_PID nitshell $(nsb) mouse object $(peek $(( $(nsb)+0x130484 ))) after $k";;
calib) ids; read wx wy ww wh < <(win)
  $H/cur $((wx+ww/4)) $((wy+wh/4)) >/dev/null; sleep 0.8; read a b < <(mouse)
  $H/cur $((wx+ww*3/4)) $((wy+wh*3/4)) >/dev/null; sleep 0.8; read c d < <(mouse)
  echo "$wx $wy $ww $wh | $((wx+ww/4)),$((wy+wh/4)) -> UI $a,$b ; $((wx+ww*3/4)),$((wy+wh*3/4)) -> UI $c,$d"
  echo "$(( wx+ww/4 )) $a $(( wx+ww*3/4 )) $c $(( wy+wh/4 )) $b $(( wy+wh*3/4 )) $d" > $H/map.txt;;
click) ids; b=$(nsb); I76PROBE_MO_PTR=$(printf '%x' $((b+0x130484))) P mclick $2 $3   # holds NITSHELL's mouse object at UI x,y, button via SendInput
  echo "  provider $(peek $((b+0x4701c))) list $(peek $((b+0x15b038)))";;
join) for pt in "469 311" "417 351" "439 379" "364 406"; do $0 "$A" click $pt; sleep 2.5; done;;
list) ids; b=$(nsb); n=$(peek $((b+0x15b038))); echo "JOIN list count 0x$n"
  for r in 0 1 2; do [ $((16#$n)) -gt $r ] && P peek $(printf '0x%x' $((b+0x1593b8+r*0xe4))) 8 | tail -1; done;;
joinrow) $0 "$A" click 60 179; sleep 1.5; $0 "$A" click 299 462;;
net) ids; echo "state $(peek 0x4f30cc) net $(peek 0x53f264) me/host $(peek 0x53f25c) $(peek 0x53ecfc) players $(peek 0x53ed00)";;
stop) [ -f $H/ours ] || { echo "not ours"; exit 2; }; "$A/Contents/SharedSupport/wine/bin/wineserver" -k
  for i in $(seq 1 30); do pgrep -f 'nitro\.exe' >/dev/null || break; sleep 1; done; rm -f $H/ours; pgrep -fl 'nitro\.exe' || echo stopped;;
esac
