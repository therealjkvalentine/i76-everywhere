#!/bin/bash
# Interstate '76 - push the BASELINE control tier to the Deck over the network.
# Runs FROM a dev machine (macOS, or Windows via Git Bash) - not on the Deck.
#
#   ./deck/deck-push.sh                 # host defaults to $I76_DECK_HOST or steamdeck
#   ./deck/deck-push.sh deck@steamdeck
#   ./deck/deck-push.sh deck@100.106.138.71 --revert
#
# Uses ssh/scp only - no rsync (absent from Git Bash on Windows).
#
# FIRST TIME on SteamOS, sshd is off and the deck user has no password. On the
# Deck, in Desktop Mode, once:
#     passwd                       # set a password for the 'deck' user
#     sudo systemctl enable --now sshd
# Then from here:  ssh-copy-id deck@steamdeck   (optional, saves retyping)
set -eu

# Order-independent parsing. Written with explicit if/then rather than
# `[ x ] && y` one-liners: under `set -e` a trailing false test is the loop's
# exit status and would abort the script.
HOST=""
REVERT=""
for a in "$@"; do
    case "$a" in
        --revert) REVERT="--revert" ;;
        -*)       ;;                              # ignore unknown flags
        *)        if [ -z "$HOST" ]; then HOST="$a"; fi ;;
    esac
done
if [ -z "$HOST" ]; then HOST="${I76_DECK_HOST:-steamdeck}"; fi
case "$HOST" in *@*) ;; *) HOST="deck@$HOST" ;; esac

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
DEST="i76-deploy"

echo "== target: $HOST =="
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" 'echo reachable' >/dev/null 2>&1; then
    if ! ssh -o ConnectTimeout=10 "$HOST" 'echo reachable' >/dev/null 2>&1; then
        cat <<EOF
Cannot reach $HOST.

Checklist:
  * Deck powered on and awake (it sleeps aggressively; suspend drops the link)
  * On the same network / Tailscale up on both ends  -> tailscale status
  * sshd running on the Deck:  sudo systemctl enable --now sshd
  * a password set for the deck user:  passwd
EOF
        exit 1
    fi
fi
echo "   reachable"

echo "== copying payload =="
ssh "$HOST" "mkdir -p ~/$DEST/deck"
scp -q "$REPO/i76-remap.ahk"              "$HOST:~/$DEST/i76-remap.ahk"
scp -q "$HERE/setup-deck-baseline.sh"     "$HOST:~/$DEST/deck/setup-deck-baseline.sh"
scp -q "$HERE/i76-deck-launch.sh"         "$HOST:~/$DEST/deck/i76-deck-launch.sh"
ssh "$HOST" "chmod +x ~/$DEST/deck/*.sh"
echo "   3 files -> ~/$DEST"

echo "== running setup on the Deck =="
# Line endings: this repo is developed on Windows too, and a stray CR makes
# bash fail with an unreadable '\r: command not found'. Strip defensively.
ssh "$HOST" "sed -i 's/\r$//' ~/$DEST/deck/*.sh 2>/dev/null; bash ~/$DEST/deck/setup-deck-baseline.sh $REVERT"
