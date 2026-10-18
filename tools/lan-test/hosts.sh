#!/bin/bash
# hosts.sh: source me. on <L|A|M|D> [args] runs a bash script from stdin on that machine (from the PC).
#   L = James's laptop (Tailscale), A = Andrew's Mac, M = Michael's Mac (both through the laptop), D = Steam Deck.
LAPTOP=${LAPTOP:-jamesvalentine@100.66.69.126}
ANDREW=${ANDREW:-andrewvalentine@192.168.1.205}
MICHAEL=${MICHAEL:-michael@192.168.1.226}
DECK=${DECK:-deck@192.168.1.130}
SSHO="-o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15"
on() {
  local m=$1; shift
  case $m in
    L) ssh $SSHO $LAPTOP bash -s -- "$@" ;;
    A) ssh $SSHO $LAPTOP "ssh $SSHO $ANDREW bash -s -- $*" ;;
    M) ssh $SSHO $LAPTOP "ssh $SSHO $MICHAEL bash -s -- $*" ;;
    D) ssh $SSHO -o HostKeyAlias=steamdeck.local $DECK bash -s -- "$@" ;;
  esac
}
# fetch <L|A|M|D> <remote-path> <local-path> : copy a file back to the PC (Macs through the laptop's /tmp)
fetch() {
  case $1 in
    L) scp -q $SSHO "$LAPTOP:$2" "$3" ;;
    A|M) local u; [ $1 = A ] && u=$ANDREW || u=$MICHAEL
       ssh $SSHO $LAPTOP "scp -q $SSHO '$u:$2' /tmp/i76mp/_fetch.tmp" && scp -q $SSHO "$LAPTOP:/tmp/i76mp/_fetch.tmp" "$3" ;;
    D) scp -q $SSHO -o HostKeyAlias=steamdeck.local "$DECK:$2" "$3" ;;
  esac
}
