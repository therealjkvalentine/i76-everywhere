#!/bin/bash
# deck-revert.sh (runs ON the Deck): undo the 2026-10-18 LAN test changes - stop the game this test started (only if
# it is the shortcut's i76.exe), put the Deck's own ADDON/valepre4.vcf back (4ed297ca), remove the debug ipxwrapper.ini
# and the test folder. Audio was already muted before the test (left muted).
T=$HOME/Games/Interstate76/lan-test-20261018; G=$HOME/Games/Interstate76/game
[ -d "$T" ] || { echo "nothing to revert"; exit 0; }
pkill -f 'Interstate76/game/i76\.exe' 2>/dev/null; sleep 5
[ -f "$T/valepre4.vcf.deck-original" ] && cp -p "$T/valepre4.vcf.deck-original" "$G/ADDON/valepre4.vcf"
rm -f "$G/ipxwrapper.ini"
echo "valepre4 $(md5sum "$G/ADDON/valepre4.vcf" | cut -c1-8), ini $(ls "$G/ipxwrapper.ini" 2>/dev/null || echo removed)"
rm -rf "$T"; echo "reverted $(date)"
