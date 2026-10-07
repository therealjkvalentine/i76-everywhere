#!/bin/bash
# Interstate '76 - push the current graphics build (widescreen + engine switches) to the
# Deck and run deck/setup-deck-wide.sh there. Runs FROM a dev machine, not on the Deck.
#
#   ./deck/deck-push-wide.sh                    # host: $I76_DECK_HOST, else steamdeck
#   ./deck/deck-push-wide.sh steamdeck-ts       # over Tailscale
#   ./deck/deck-push-wide.sh steamdeck --revert
#
# First time on SteamOS see deck-push.sh (passwd + sshd). ssh/scp only, no rsync.
set -eu
HOST=""; ARGS=""
for a in "$@"; do
    case "$a" in
        --revert) ARGS="--revert" ;;
        -*) ;;
        *) if [ -z "$HOST" ]; then HOST="$a"; fi ;;
    esac
done
if [ -z "$HOST" ]; then HOST="${I76_DECK_HOST:-steamdeck}"; fi
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
DEST="i76-deploy"

echo "== target: $HOST =="
ssh -o ConnectTimeout=10 "$HOST" 'echo "   reachable: $(uname -n)"' \
    || { echo "Cannot reach $HOST - Deck awake? sshd on? (see deck-push.sh)"; exit 1; }

echo "== copying payload =="
ssh "$HOST" "mkdir -p ~/$DEST/deck"
scp -q "$HERE/Strlkup.deck.dll" "$HERE/setup-deck-wide.sh" "$HERE/i76-deck-launch.sh" "$HERE/set-launch-options.py" \
       "$HERE/add-to-steam.py" "$HOST:~/$DEST/deck/"
N=5
# IPXWrapper (GPL-2.0, solemnwarning.net/ipxwrapper; not in this repo): taken from a local
# copy, by default the Mac IPX test wrapper's game folder (docs/MULTIPLAYER.md section 6).
IPXD="${I76_IPXWRAPPER_DIR:-$HOME/Applications/Sikarugir/I76 IPX TEST.app/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76}"
if [ -f "$IPXD/ipxwrapper.dll" ] && [ -f "$IPXD/wsock32.dll" ] && [ -f "$IPXD/mswsock.dll" ]; then
    ssh "$HOST" "mkdir -p ~/$DEST/ipx"
    scp -q "$IPXD/ipxwrapper.dll" "$IPXD/wsock32.dll" "$IPXD/mswsock.dll" "$HOST:~/$DEST/ipx/"
    N=$((N + 3))
else
    echo "   (no IPXWrapper DLLs in $IPXD - LAN over IPX skipped; set I76_IPXWRAPPER_DIR)"
fi
echo "   $N files -> ~/$DEST"

echo "== running setup on the Deck =="
ssh "$HOST" "sed -i 's/\r$//' ~/$DEST/deck/*.sh; chmod +x ~/$DEST/deck/*.sh; bash ~/$DEST/deck/setup-deck-wide.sh $ARGS"
