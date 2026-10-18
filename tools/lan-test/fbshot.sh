#!/bin/bash
# fbshot.sh APP|deck OUT.raw : dump the shell's two 640x480 8-bit back buffers (display object [shell+0xcc518], dwords 17
# and 22) to OUT_1.raw / OUT_2.raw. The menus are drawn there before the Glide upload, so this is a screenshot of the
# shell that works where the screen cannot be captured (Mac over SSH: no Screen Recording; locked screen).
A="$1"; OUT="$2"; N=$(dirname "$0")/macnav.sh; [ -x "$N" ] || N=/tmp/i76mp/macnav.sh
w() { echo "Z:$1" | tr '/' '\'; }     # Wine path of a Unix file
d=$($N "$A" peek shell+cc518 1); set -- $($N "$A" peek $d 24); b1=${18}; b2=${23}
$N "$A" dump $b1 307200 "$(w "${OUT%.raw}_1.raw")" >/dev/null; $N "$A" dump $b2 307200 "$(w "${OUT%.raw}_2.raw")" >/dev/null; echo "buffers $b1 $b2"
