#!/bin/bash
# macnav.sh APP cmd... : drive I'76 in APP's Wine session on this Mac through i76probe3 (copy at /tmp/i76mp).
#   calib            measure this window's UI->client mapping from the MELEE button's edges; saves /tmp/i76mp/map.txt
#   top              back to the bare main menu (MELEE submenu closed, no Esc menu)
#   nav host|join    MELEE > MULTI MELEE > HOST|JOIN > IPX, every step checked in the shell's button list
#   click X Y | key VK [ms] | shell | state | pos | find TEXT   (pass-through, mapped clicks)
#   drive SECS       hold W (throttle) with a steer pulse every 5 s and print pos every 5 s
# Every click uses the measured map (I76PROBE_MAP), never the 4:3 guess: on the Macs DxWnd's picture is not the 4:3
# letterbox of the client (the M2 tester 1392x900: x' = 94 + 2.065 x, y' = 1.875 y; the letterbox guess missed HOST by 10 px).
# APP "deck" = the Steam Deck's Proton prefix (deckprobe.sh); the Deck's proxy maps the pointer stretched (I76_CURSOR_MAP=1).
A="$1"; shift
if [ "$A" = deck ]; then D=$HOME/Games/Interstate76/lan-test-20261018; P() { "$D/deckprobe.sh" "$@"; }; MAPF=$D/map.txt; export I76PROBE_STRETCH=1
else P() { /tmp/i76mp/probe3.sh "$A" "$@"; }; MAPF=/tmp/i76mp/map.txt; fi
export I76PROBE_HWND=${I76PROBE_HWND:-$(P wins | awk '/Gold Edition/{print $2; exit}')}
[ -f "$MAPF" ] && export I76PROBE_MAP="$(cat "$MAPF")"
st() { P shell | awk 'NR==1{for(i=1;i<=NF;i++){if($i=="mfn")m=$(i+1); if($i=="sfn")s=$(i+1)}} /button id/{b=b" "$3} END{print s" "m b}'; }
top() { local s k; for k in 1 2 3 4 5 6 7 8; do s=$(st)
    case "$s" in "0x10025a50 0x00000000 13 2 0 17") return 0;;
      *" 0x1000e6b0"*) P key 1B >/dev/null;;            # Esc menu open: close it
      "0x10025a50 "*) $CLICK 446 310 >/dev/null;;      # a submenu is open: MELEE toggles it shut
      *) P key 1B >/dev/null;; esac; sleep 2; done; echo "top FAILED: $s"; return 1; }
rawclick() { I76PROBE_MAP= I76PROBE_RAW=1 P click $1 $2 >/dev/null; sleep 2; }
calib() {   # MELEE: rect x 387..506 at y 286..335 (UI); client height / 480 is the y scale (measured 1.875 on 900)
  local ch cw ky y lo hi mid L R
  read cw ch < <(P wins | awk -v h=$I76PROBE_HWND '$2==h{split($NF,a,"x"); print a[1], a[2]}')
  ky=$(echo "$ch/480" | bc -l); y=$(printf %.0f $(echo "310*$ky" | bc -l))
  edge() {  # $1 lo (miss side) $2 hi (hit side): binary search the client x where MELEE starts/ends being hit
    local lo=$1 hi=$2 mid
    while [ $(( (hi>lo?hi-lo:lo-hi) )) -gt 2 ]; do mid=$(( (lo+hi)/2 )); top >/dev/null || return 1
      rawclick $mid $y; if st | grep -q " 15 1"; then hi=$mid; else lo=$mid; fi; done; echo $(( (lo+hi)/2 )); }
  L=$(edge $(( cw*30/100 )) $(( cw*70/100 ))); R=$(edge $(( cw*98/100 )) $(( cw*70/100 )))
  kx=$(echo "($R-$L)/(506-387)" | bc -l); ox=$(echo "$L-$kx*387" | bc -l)
  printf "%.4f %.1f %.4f 0\n" $kx $ox $ky > "$MAPF"; top >/dev/null; echo "calib: client ${cw}x$ch, MELEE edges $L..$R -> map $(cat "$MAPF")"; }
calib2() {  # unlocked Mac only: warp the real pointer (cur) to two points, read the shell's mouse object (UI space)
  local wx wy mo a b c d e f g h
  read wx wy < <(P wins | awk -v w=$I76PROBE_HWND '$2==w{split($(NF-1),p,","); print p[1], p[2]}')
  mo=$(P peek shell+cc514 1)
  /tmp/i76mp/cur $((wx+200)) $((wy+100)) >/dev/null; sleep 0.8; set -- $(P peek $mo 13 | tail -1); a=$((16#$4)); b=$((16#$5))
  /tmp/i76mp/cur $((wx+1200)) $((wy+700)) >/dev/null; sleep 0.8; set -- $(P peek $mo 13 | tail -1); c=$((16#$4)); d=$((16#$5))
  kx=$(echo "1000/($c-$a)" | bc -l); ky=$(echo "600/($d-$b)" | bc -l)
  ox=$(echo "200-$kx*$a" | bc -l); oy=$(echo "100-$ky*$b" | bc -l)
  printf "%.4f %.1f %.4f %.1f
" $kx $ox $ky $oy > "$MAPF"; echo "calib2: client +200,+100 -> UI $a,$b; +1200,+700 -> UI $c,$d; map $(cat "$MAPF")"; }
rclick() {  # warp the real pointer onto the mapped point, then click there (forms hit-test the real pointer on a Mac)
  local wx wy sx sy
  read wx wy < <(P wins | awk -v w=$I76PROBE_HWND '$2==w{split($(NF-1),p,","); print p[1], p[2]}')
  set -- $1 $2 $(cat "$MAPF")
  sx=$(printf %.0f $(echo "$wx+$4+$3*($1+0.5)" | bc -l)); sy=$(printf %.0f $(echo "$wy+$6+$5*($2+0.5)" | bc -l))
  [ -x /tmp/i76mp/cur ] && /tmp/i76mp/cur $sx $sy >/dev/null; sleep 0.3
  I76PROBE_MAP= I76PROBE_RAW=1 P click $((sx-wx)) $((sy-wy)); }
step() { local t s; for t in 1 2 3; do $CLICK $1 $2 >/dev/null; sleep 2.5; s=$(st); echo "$s" | grep -q -E "$3" && return 0; echo "  miss $1,$2 try $t: $s"; done; return 1; }
nav() { local r; for r in 1 2 3; do top || continue
    step 446 310 " 15 1$" || continue; step 394 350 " 3 5$" || continue
    if [ "$1" = host ]; then step 366 378 " 6 7 14 8 16$" || continue; else step 416 378 " 6 7 14 8 16$" || continue; fi
    P click 343 405 >/dev/null; sleep 6; echo "nav $1: $(st)"; return 0; done; echo "nav $1 FAILED"; return 1; }
drive() { local end=$(( $(date +%s) + $1 )) i=0
  while [ $(date +%s) -lt $end ]; do P key 57 4800 >/dev/null &   # W held ~5 s
    sleep 1; [ $((i%2)) = 0 ] && P key 41 700 >/dev/null || P key 44 700 >/dev/null; wait
    echo "$(date +%H:%M:%S) $(P pos)"; i=$((i+1)); done; }
# host form (NET MELEE HOST EVENT FORM): AREA OF PLAY rows at x 67: The Crater 157, Dunes 174, Air Base 191, Suburbia 208,
# Slick Track 225, Tombstone 242; BROADCAST GAME 298,461. Join form (ENTRY ROSTER): first GAME NAME row 80,157, JOIN GAME 298,461.
hostgo() { local y=${1:-208}; $CLICK 67 $y >/dev/null; sleep 2; $CLICK 298 461 >/dev/null
  local i; for i in $(seq 1 20); do sleep 2; P state | grep -q "net 1" && break; done; P state | head -3; }
joingo() { local t i; for t in 1 2 3; do $CLICK 80 157 >/dev/null; sleep 2; $CLICK 298 461 >/dev/null
    for i in $(seq 1 10); do sleep 2; P state | grep -q "net 1" && { P state | head -4; return 0; }; done; echo "join try $t: $(P state | sed -n 2p)"; done; return 1; }
# On a Mac every click warps the real pointer first (rclick); the Deck's proxy maps its own pointer (plain click).
if [ "$A" = deck ] || [ ! -x /tmp/i76mp/cur ] || [ ! -f "$MAPF" ]; then CLICK="P click"; else CLICK=rclick; fi
joinname() {  # select the join-list row whose session name is $1 (record address = a 'find' hit), then JOIN GAME
  local l n arr i e hits t
  hits=$(P find "$1" | awk -F: '/^0x/{print tolower($1)}'); l=$(P peek shell+f21a0 1); set -- $(P peek $l 3); n=$((16#$2)); arr=$3
  for i in $(seq 0 $((n-1))); do e=$(P peek $(printf %x $((16#$arr + 4*i))) 1)
    if echo "$hits" | grep -q "0x$e"; then echo "row $i of $n"; for t in 1 2 3; do $CLICK 80 $((157 + 17*i)) >/dev/null; sleep 2; $CLICK 298 461 >/dev/null
        for e in $(seq 1 10); do sleep 2; P state | grep -q "net 1" && { P state | sed -n 2,6p; return 0; }; done; done; return 1; fi; done
  echo "no row named $1 ($n rows)"; return 1; }
cmd=$1; shift
case $cmd in
  calib) calib;; calib2) calib2;; rclick) rclick "$@";; top) top && echo top;; nav) nav "$@";; st) st;; drive) drive "$@";; hostgo) hostgo "$@";; joingo) joingo;; joinname) joinname "$@";;
  *) P $cmd "$@";;
esac
