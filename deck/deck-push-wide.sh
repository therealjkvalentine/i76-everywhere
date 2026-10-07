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
ssh -o ConnectTimeout=10 "$HOST" 'echo "   reachable: $(hostname)"' \
    || { echo "Cannot reach $HOST - Deck awake? sshd on? (see deck-push.sh)"; exit 1; }

echo "== copying payload =="
ssh "$HOST" "mkdir -p ~/$DEST/deck ~/$DEST/music-fix"
scp -q "$REPO/music-fix/Strlkup.dll" "$HOST:~/$DEST/music-fix/Strlkup.dll"
scp -q "$HERE/setup-deck-wide.sh" "$HERE/i76-deck-launch.sh" "$HERE/set-launch-options.py" \
       "$HERE/add-to-steam.py" "$HOST:~/$DEST/deck/"
echo "   5 files -> ~/$DEST"

echo "== running setup on the Deck =="
ssh "$HOST" "sed -i 's/\r$//' ~/$DEST/deck/*.sh; chmod +x ~/$DEST/deck/*.sh; bash ~/$DEST/deck/setup-deck-wide.sh $ARGS"
