#!/bin/bash
# apply-pack-delta.sh GAMEDIR DELTADIR : update a LAN-pack game folder IN PLACE from the 2026-10-17 pack to the 2026-10-18
# pack (co-op arenas ADDON/coop01..17.lvl, stock M01 back, proxy ba2b45c1). DELTADIR holds add.tar, delete.txt, add.txt,
# common.md5 (made on the PC from the two packs' md5 lists). Every file it replaces or deletes is first copied to
# GAMEDIR/../lan-pack-pre-20261018/ (a new folder beside the game folder). Then it verifies GAMEDIR against common.md5.
# Refuses while i76.exe runs. Nothing outside GAMEDIR and that backup folder is touched.
set -u
G="$1"; D="$2"; B="$G/../lan-pack-pre-20261018"
pgrep -f 'i76\.exe' >/dev/null && { echo "game running - refusing"; exit 1; }
[ -f "$G/i76.exe" ] || { echo "no i76.exe in $G"; exit 1; }
mkdir -p "$B"
while IFS= read -r f; do [ -n "$f" ] && [ -e "$G/$f" ] && { mkdir -p "$B/$(dirname "$f")"; cp -p "$G/$f" "$B/$f"; }; done < <(cat "$D/delete.txt" "$D/add.txt")
n=0; while IFS= read -r f; do [ -n "$f" ] && [ -e "$G/$f" ] && rm -f "$G/$f" && n=$((n+1)); done < "$D/delete.txt"
tar xf "$D/add.tar" -C "$G"
m5() { md5 -q "$1" 2>/dev/null || md5sum "$1" | cut -d' ' -f1; }
bad=0; t=0; while IFS= read -r line; do h="${line%%  *}"; f="${line#*  }"; t=$((t+1)); [ "$(m5 "$G/$f" 2>/dev/null)" = "$h" ] || { echo "MISMATCH $f"; bad=$((bad+1)); }; done < "$D/common.md5"
echo "deleted $n, added $(tar tf "$D/add.tar" | wc -l | tr -d ' '); verify $t files, $bad mismatches; backup $B"
ls "$G/ADDON" | grep -i coop | head -3; ls "$G/ADDON" | grep -c '^coop[0-9][0-9]\.lvl$'
