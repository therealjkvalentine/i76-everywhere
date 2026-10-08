#!/bin/bash
# Interstate '76 - push the shared pad-layer profile to the Deck and run deck/setup-deck-pad.sh there.
# Runs FROM a dev machine. Close Steam on the Deck first (or let this script do it with --restart-steam)
# so the second library entry can be written.
#   ./deck/deck-push-pad.sh deck@steamdeck.local [--restart-steam] [--revert]
set -eu
HOST=""; RESTART=""; ARGS=""
for a in "$@"; do
    case "$a" in
        --restart-steam) RESTART=1 ;;
        --revert) ARGS="--revert" ;;
        -*) ;;
        *) if [ -z "$HOST" ]; then HOST="$a"; fi ;;
    esac
done
if [ -z "$HOST" ]; then HOST="${I76_DECK_HOST:-deck@steamdeck.local}"; fi
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/.." && pwd)"; DEST="i76-deploy"
ssh -o ConnectTimeout=10 "$HOST" "mkdir -p ~/$DEST/deck ~/$DEST/controls ~/$DEST/tools"
scp -q "$REPO/controls/input.map" "$HOST:~/$DEST/controls/"
scp -q "$REPO/i76-remap.ahk" "$HOST:~/$DEST/"
scp -q "$REPO/tools/lint-input-map.py" "$HOST:~/$DEST/tools/"
scp -q "$HERE/setup-deck-pad.sh" "$HERE/controller_neptune_i76_pad.vdf" "$HERE/i76-deck-launch.sh" \
       "$HERE/add-pad-shortcut.py" "$HERE/add-to-steam.py" "$HOST:~/$DEST/deck/"
if [ -n "$RESTART" ]; then
    ssh "$HOST" 'export DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1000; steam -shutdown >/dev/null 2>&1; for i in $(seq 1 40); do pgrep -x steam >/dev/null || break; sleep 1; done; pgrep -x steam >/dev/null && echo "Steam still running" || echo "Steam stopped"'
fi
ssh "$HOST" "sed -i 's/\r$//' ~/$DEST/deck/*.sh; bash ~/$DEST/deck/setup-deck-pad.sh $ARGS"
if [ -n "$RESTART" ]; then
    ssh "$HOST" 'systemd-run --user --unit=steam-i76-$(date +%H%M%S) --collect -E DISPLAY=:0 -E WAYLAND_DISPLAY=wayland-0 -E XDG_RUNTIME_DIR=/run/user/1000 -E DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus -E XDG_SESSION_TYPE=wayland /usr/bin/steam -silent >/dev/null 2>&1; echo "Steam restarted (desktop session)"'
fi
