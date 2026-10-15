#!/bin/bash
# Interstate '76 - put the Deck's game/ADDON back to stock textures (moves the retired HD pack aside) by
# running deck/setup-deck-stock-textures.sh there. Runs FROM a dev machine. Never launches the game;
# refuses while i76.exe runs on the Deck.
#   ./deck/deck-push-stock-textures.sh [deck] [--revert]
set -eu
HOST=""; ARGS=""
for a in "$@"; do
    case "$a" in
        --revert) ARGS="--revert" ;;
        -*) ;;
        *) if [ -z "$HOST" ]; then HOST="$a"; fi ;;
    esac
done
if [ -z "$HOST" ]; then HOST="${I76_DECK_HOST:-deck}"; fi
HERE="$(cd "$(dirname "$0")" && pwd)"; DEST="i76-deploy"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10"
$SSH "$HOST" true || { echo "the Deck ($HOST) does not answer - nothing done"; exit 1; }
# "[i]" keeps pgrep from matching its own command line
if $SSH "$HOST" 'pgrep -f "[i]76\.exe" >/dev/null'; then echo "i76.exe is running on the Deck - not deploying"; exit 1; fi
$SSH "$HOST" "mkdir -p ~/$DEST/deck"
scp -q -o BatchMode=yes "$HERE/setup-deck-stock-textures.sh" "$HERE/i76-deck-launch.sh" "$HOST:~/$DEST/deck/"
$SSH "$HOST" "sed -i 's/\r$//' ~/$DEST/deck/setup-deck-stock-textures.sh ~/$DEST/deck/i76-deck-launch.sh; bash ~/$DEST/deck/setup-deck-stock-textures.sh $ARGS"
