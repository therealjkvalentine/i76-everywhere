#!/bin/bash
# hosts.sh: source me. on <L|A|M|D> [args] runs a bash script from stdin on that machine (from the PC).
#   L = the developer's laptop (Tailscale), A = the M2 tester Mac, M = the M4 Max tester Mac (both through the laptop), D = Steam Deck.
# Private hosts live outside the repo: copy hosts.local.sh.example to hosts.local.sh (git-ignored) and fill it in.
_here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
[ -f "$_here/hosts.local.sh" ] && . "$_here/hosts.local.sh"
LAPTOP=${LAPTOP:-user@laptop-mac}
M2MAC=${M2MAC:-user@m2-mac}
M4MAC=${M4MAC:-user@m4-mac}
DECK=${DECK:-deck@steamdeck.local}
SSHO="-o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15"
on() {
  local m=$1; shift
  case $m in
    L) ssh $SSHO $LAPTOP bash -s -- "$@" ;;
    A) ssh $SSHO $LAPTOP "ssh $SSHO $M2MAC bash -s -- $*" ;;
    M) ssh $SSHO $LAPTOP "ssh $SSHO $M4MAC bash -s -- $*" ;;
    D) ssh $SSHO -o HostKeyAlias=steamdeck.local $DECK bash -s -- "$@" ;;
  esac
}
# fetch <L|A|M|D> <remote-path> <local-path> : copy a file back to the PC (Macs through the laptop's /tmp)
fetch() {
  case $1 in
    L) scp -q $SSHO "$LAPTOP:$2" "$3" ;;
    A|M) local u; [ $1 = A ] && u=$M2MAC || u=$M4MAC
       ssh $SSHO $LAPTOP "scp -q $SSHO '$u:$2' /tmp/i76mp/_fetch.tmp" && scp -q $SSHO "$LAPTOP:/tmp/i76mp/_fetch.tmp" "$3" ;;
    D) scp -q $SSHO -o HostKeyAlias=steamdeck.local "$DECK:$2" "$3" ;;
  esac
}
