#!/bin/bash
# i76-deck-launch-mp.sh - start Interstate '76 on the Deck with the LAN switch file (2026-10-20, pack mp-pack-20261020-polish;
# relative to its own folder since 2026-10-25, Deck kit). The normal launcher (i76-deck-launch.sh) with i76-env-mp.sh instead
# of i76-env.sh and its own log. Since 2026-10-25 the Deck's i76-env.sh carries the three LAN switches itself (as PLAY.bat on
# the PC), so the normal launcher plays LAN too; this one stays for setups whose i76-env.sh has no LAN switches.
#   Steam launch options:  "<install folder>/i76-deck-launch-mp.sh" %command% -glide
H="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
export I76_HOME="${I76_HOME:-$H}"
export I76_ENV_FILE="${I76_ENV_FILE:-$H/i76-env-mp.sh}"
export I76_LAUNCH_LOG="${I76_LAUNCH_LOG:-$H/deck-launch-mp.log}"
exec "$H/i76-deck-launch.sh" "$@"
