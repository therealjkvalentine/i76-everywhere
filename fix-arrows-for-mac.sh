#!/bin/sh
# Interstate '76: make the original arrow-key driving controls work on a Mac.
#
# The game distinguishes the two PC arrow clusters: KEYBOARD.MAP's plain
# "UpArrow" names vs the "Grey*" names. Wine's Mac driver delivers Mac arrow
# keys as the Grey* codes - which the stock map binds to glance/track camera,
# while driving sits on the plain names Mac arrows never produce. Symptom:
# arrows look around the cockpit instead of steering.
#
# This swaps the four arrow tokens throughout KEYBOARD.MAP (driving -> real
# Mac arrows; glance/track -> the numpad, still usable on a full-size external
# keyboard). Run it on the KEYBOARD.MAP inside your wrapper's game folder:
#
#   ./fix-arrows-for-mac.sh "~/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76/KEYBOARD.MAP"
#
# A .pre-mac-arrows backup is written beside the file. Restart the game after.
set -e
MAP=${1:?usage: fix-arrows-for-mac.sh <path-to-KEYBOARD.MAP>}
cp "$MAP" "$MAP.pre-mac-arrows"
# placeholder pass so "UpArrow" never matches inside "GreyUpArrow"
sed -i '' \
  -e 's/GreyUpArrow/@KPUP@/g'    -e 's/GreyDownArrow/@KPDN@/g' \
  -e 's/GreyLeftArrow/@KPLT@/g'  -e 's/GreyRightArrow/@KPRT@/g' \
  -e 's/UpArrow/GreyUpArrow/g'   -e 's/DownArrow/GreyDownArrow/g' \
  -e 's/LeftArrow/GreyLeftArrow/g' -e 's/RightArrow/GreyRightArrow/g' \
  -e 's/@KPUP@/UpArrow/g'        -e 's/@KPDN@/DownArrow/g' \
  -e 's/@KPLT@/LeftArrow/g'      -e 's/@KPRT@/RightArrow/g' \
  "$MAP"
echo "Swapped arrow tokens in $MAP (backup: $MAP.pre-mac-arrows)"
