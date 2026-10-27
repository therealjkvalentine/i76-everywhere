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
$SSH "$HOST" true || { echo "the Deck ($HOST) does not answer - nothing done"; exit 1; }
if $SSH "$HOST" 'pgrep -f "[i]76\.exe" >/dev/null'; then echo "i76.exe is running on the Deck - not deploying"; exit 1; fi
# keep the evidence of the last session before anything is replaced (the next launch truncates deck-launch.log)
CAP="${I76_DECK_CAPTURE_DIR:-$HOME/i76-deck-captures}/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$CAP"
for f in deck-launch.log i76-env.sh i76-deck-launch.sh game/mciproxy.log game/dgVoodoo.conf ahk/i76-remap.ahk; do
    scp -q -o BatchMode=yes "$HOST:Games/Interstate76/$f" "$CAP/$(echo "$f" | tr / _)" 2>/dev/null || echo "  (no $f)"
done
$SSH "$HOST" 'cd ~/Games/Interstate76 && ls -la game | grep -i -E "sfrce|strlkup|ffb|rumble"; md5sum game/[Ii]7_[Ss][Ff][Rr][Cc][Ee]*.[Dd][Ll][Ll] game/Strlkup.dll 2>/dev/null' > "$CAP/game-files.txt" 2>/dev/null || true
$SSH "$HOST" 'B=$(cat ~/Games/Interstate76/backups/LAST-TV 2>/dev/null) && cat "$B/game/dgVoodoo.conf"' > "$CAP/pre-tv_dgVoodoo.conf" 2>/dev/null || true
echo "== last session's logs and conf -> $CAP"
$SSH "$HOST" "mkdir -p ~/$DEST/deck"
scp -q -o BatchMode=yes "$HERE/setup-deck-tv.sh" "$HERE/i76-deck-launch.sh" "$HERE/Strlkup.deck-padmenu.dll" "$HERE/../windows/i76-remap.ahk" "$HOST:~/$DEST/deck/"
$SSH "$HOST" "sed -i 's/\r$//' ~/$DEST/deck/setup-deck-tv.sh ~/$DEST/deck/i76-deck-launch.sh; bash ~/$DEST/deck/setup-deck-tv.sh $ARGS"
