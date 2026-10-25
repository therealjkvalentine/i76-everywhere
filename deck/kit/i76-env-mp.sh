# i76-env-mp.sh - the LAN switch file for i76-deck-launch-mp.sh: the Deck preset (i76-env.sh) + the three LAN switches.
# The kit's i76-env.sh already exports them; this file exists so an i76-deck-launch-mp.sh shortcut keeps working.
. "${I76_HOME:-$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")}/i76-env.sh"
export I76_COOP_AI=1 I76_COOP_CHAIN=1 I76_MP_MENU=1
