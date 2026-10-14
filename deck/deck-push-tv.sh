#!/bin/bash
# Interstate '76 - push the docked-TV fixes to the Deck and run deck/setup-deck-tv.sh there.
# Runs FROM a dev machine. Never launches the game; refuses while i76.exe runs on the Deck.
#   ./deck/deck-push-tv.sh [deck] [--revert]
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
# "[i]" keeps pgrep from matching its own command line
if $SSH "$HOST" 'pgrep -f "[i]76\.exe" >/dev/null'; then echo "i76.exe is running on the Deck - not deploying"; exit 1; fi
$SSH "$HOST" "mkdir -p ~/$DEST/deck"
scp -q -o BatchMode=yes "$HERE/setup-deck-tv.sh" "$HERE/i76-deck-launch.sh" "$HERE/Strlkup.deck-padmenu.dll" "$HOST:~/$DEST/deck/"
$SSH "$HOST" "sed -i 's/\r$//' ~/$DEST/deck/setup-deck-tv.sh ~/$DEST/deck/i76-deck-launch.sh; bash ~/$DEST/deck/setup-deck-tv.sh $ARGS"
