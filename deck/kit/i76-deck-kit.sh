#!/bin/bash
# =====================================================================================================================
#  I'76 Deck Kit (i76-everywhere) - builds Interstate '76 Gold for the Steam Deck from YOUR GOG copy of the game.
#  Nothing of the game is in this kit. It installs into one folder (default ~/Games/Interstate76) plus a download cache;
#  the Steam library entry is a separate, optional step. README.md beside this script is the user guide.
#
#    ./i76-deck-kit.sh install --gog <setup_interstate76_*.exe | GOG game folder> [--dest <folder>] [--ge-proton] [--replace]
#    ./i76-deck-kit.sh steam   [--dest <folder>] [--name "Interstate 76"] [--dry-run]   add the library entry (restarts Steam)
#    ./i76-deck-kit.sh verify  [--dest <folder>]                                     re-check every file the kit placed (md5)
#
#  What install does (the recipe of the owner's Deck as measured 2026-10-25, docs/records/DECK-2026-10-25.md):
#   1. downloads (once, cached in ~/.cache/i76-deck-kit) and checks by SHA-256 (pins.txt): innoextract 1.9, dgVoodoo 2.78.2,
#      IPXWrapper 0.7.2 (and GE-Proton 10-12 with --ge-proton)
#   2. your GOG files: unpacked from the offline installer (innoextract) or copied from a GOG folder, into <dest>/game
#   3. patched in place: i76.exe and i76shell.dll by the byte patches in payload/patches (checked against your file's md5
#      before and the result's md5 after; the same patches the Mac Kit uses: shell keys, text entry, u32x, the Wine PIT
#      skip), the co-op / scenario arenas built from your own mission files; every GOG file replaced is kept in game/_gog-originals
#   4. our files: the proxy STRLKUP.DLL (GOG's kept as strlkup_orig.dll), u32x.dll, the rumble shim i7_sfrce.dll, the key map;
#      dgVoodoo's Glide2x / ddraw / d3dimm + the Deck's dgVoodoo.conf; IPXWrapper; the rumble envelopes from your sound files
#   5. <dest>: the launchers, the preset i76-env.sh, i76-env.local.sh (yours, created once), the AutoHotkey pad layer
# =====================================================================================================================
set -euo pipefail
KIT="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PAY="$KIT/payload"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/i76-deck-kit"
VERSION="$(head -1 "$KIT/VERSION.txt" 2>/dev/null || echo dev)"
say()  { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '   ok  %s\n' "$*"; }
note() { printf '   ..  %s\n' "$*"; }
die()  { printf '\n\033[31mi76-deck-kit: %s\033[0m\n' "$*" >&2; exit 1; }
md5of() { md5sum "$1" 2>/dev/null | cut -c1-32 || echo missing; }
GOLD_EXE_MD5=9a232dcc2c164648cff20c414c1f9698      # GOG 2.1.0.17 offline installer / GOG Galaxy (the Mac Kit's input too)

# case-insensitive lookup of a game-relative path (GOG ships STRLKUP.DLL, glide2x.dll, miss16/S03.MSN ...); prints the real path
ci() {
    local base="$1" rel="$2" cur="$1" part hit
    IFS=/ read -r -a parts <<< "$rel"
    for part in "${parts[@]}"; do
        hit="$(find "$cur" -maxdepth 1 -mindepth 1 -iname "$part" -print -quit 2>/dev/null)"
        [ -n "$hit" ] || return 1
        cur="$hit"
    done
    printf '%s\n' "$cur"
}

DEST="$HOME/Games/Interstate76"; GOG=""; GEPROTON=0; REPLACE=0; NAME="Interstate 76"; DRY=0
cmd="${1:-}"; [ $# -gt 0 ] && shift
while [ $# -gt 0 ]; do
    case "$1" in
        --gog) GOG="$2"; shift 2;;
        --dest) DEST="$2"; shift 2;;
        --ge-proton) GEPROTON=1; shift;;
        --replace) REPLACE=1; shift;;
        --name) NAME="$2"; shift 2;;
        --dry-run) DRY=1; shift;;
        *) die "unknown option $1 (see the top of this script)";;
    esac
done
DEST="$(readlink -m "$DEST")"; G="$DEST/game"; ORIG="$G/_gog-originals"; LIST="$DEST/KIT-FILES.md5"

# ---------------------------------------------------------------------------------------------------------------------
preflight() {
    for t in python3 curl tar xz md5sum sha256sum unzip find; do command -v "$t" >/dev/null || die "missing tool: $t"; done
    [ -d "$PAY" ] || die "no payload/ folder beside the script: unzip the whole kit, not just this file"
    local free; free=$(df -Pk "$(dirname "$DEST")" 2>/dev/null | awk 'NR==2 {print int($4/1024)}')
    [ "${free:-0}" -ge 1500 ] || die "need about 1.5 GB free beside $DEST (have ${free:-?} MB)"
    if pgrep -f '[i]76\.exe' >/dev/null; then die "Interstate '76 is running: quit it first"; fi
}

# pins.txt: name  sha256  url ; prints the cached file's path
fetch() {
    local line sha url f got
    line="$(awk -v n="$1" '$1 == n' "$KIT/pins.txt")"; [ -n "$line" ] || die "no pin for $1"
    sha="$(echo "$line" | awk '{print $2}')"; url="$(echo "$line" | awk '{print $3}')"; f="$CACHE/$1"
    mkdir -p "$CACHE"
    if [ -f "$f" ] && [ "$(sha256sum "$f" | cut -c1-64)" = "$sha" ]; then echo "$f"; return; fi
    note "downloading $1" >&2
    curl -fL --retry 3 -o "$f.part" "$url" >&2 || die "download failed: $url"
    got="$(sha256sum "$f.part" | cut -c1-64)"
    [ "$got" = "$sha" ] || { rm -f "$f.part"; die "$1: sha256 $got is not the pinned $sha (not installed)"; }
    mv "$f.part" "$f"; echo "$f"
}

# keep a GOG original once (game-relative path) before we replace it
keep() {
    local real="$1" rel
    [ -f "$real" ] || return 0
    rel="${real#$G/}"
    if [ ! -e "$ORIG/$rel" ]; then mkdir -p "$(dirname "$ORIG/$rel")"; cp -p "$real" "$ORIG/$rel"; fi
}

place() {   # place SRC as game-relative TARGET (any existing file of that name, any case, is kept first and removed)
    local src="$1" rel="$2" old
    if old="$(ci "$G" "$rel")"; then keep "$old"; rm -f "$old"; fi
    mkdir -p "$(dirname "$G/$rel")"; cp "$src" "$G/$rel"
    echo "$(md5of "$G/$rel")  game/$rel" >> "$LIST"
}

# ---------------------------------------------------------------------------------------------------------------------
do_install() {
    [ -n "$GOG" ] || die "install needs --gog <setup_interstate76_*.exe | GOG game folder>"
    preflight
    say "I'76 Deck Kit $VERSION -> $DEST"
    if [ -e "$G/i76.exe" ]; then
        [ "$REPLACE" = 1 ] || die "$G already has a game: pass --replace to move it aside and install fresh (or pick another --dest)"
        local old="$DEST.before-kit-$(date +%Y%m%d-%H%M%S)"; mv "$DEST" "$old"; note "the old install is now $old"
    fi
    mkdir -p "$DEST"

    say "1. downloads (sha256-pinned)"
    local IE DGV IPX; IE="$(fetch innoextract-1.9-linux.tar.xz)"; DGV="$(fetch dgVoodoo2_78_2.zip)"; IPX="$(fetch ipxwrapper-0.7.2.zip)"
    ok "innoextract 1.9, dgVoodoo 2.78.2, IPXWrapper 0.7.2"
    if [ "$GEPROTON" = 1 ]; then
        local CT="$HOME/.steam/steam/compatibilitytools.d"
        if [ -d "$CT/GE-Proton10-12" ]; then ok "GE-Proton10-12 already installed"
        else local GP; GP="$(fetch GE-Proton10-12.tar.gz)"; mkdir -p "$CT"; tar -xzf "$GP" -C "$CT"; ok "GE-Proton10-12 installed (restart Steam to see it)"; fi
    fi

    say "2. your GOG files"
    local T; T="$(mktemp -d "$DEST/.kit-tmp.XXXX")"
    if [ -d "$GOG" ]; then
        local src; src="$(dirname "$(find "$GOG" -maxdepth 2 -iname i76.exe -print -quit)")"
        [ -n "$src" ] && [ "$src" != . ] || die "no i76.exe in $GOG"
        cp -a "$src/." "$T/game/" 2>/dev/null || { mkdir -p "$T/game"; cp -a "$src/." "$T/game/"; }
        ok "copied from $src"
    elif [ -f "$GOG" ]; then
        tar -xJf "$IE" -C "$T" innoextract-1.9-linux/bin/amd64/innoextract
        "$T/innoextract-1.9-linux/bin/amd64/innoextract" --gog --silent -d "$T/x" "$GOG" || die "innoextract could not unpack $GOG"
        local src; src="$(dirname "$(find "$T/x" -maxdepth 3 -iname i76.exe -print -quit)")"
        [ -n "$src" ] && [ "$src" != . ] || die "no i76.exe in the installer (is it the Interstate '76 GOG installer, not the Nitro Pack?)"
        mv "$src" "$T/game"; ok "unpacked $(basename "$GOG")"
    else
        die "--gog $GOG: no such file or folder"
    fi
    mv "$T/game" "$G"; rm -rf "$T"
    local m; m="$(md5of "$(ci "$G" i76.exe)")"
    [ "$m" = "$GOLD_EXE_MD5" ] || die "i76.exe md5 $m is not GOG 2.1.0.17's ($GOLD_EXE_MD5): this kit's patches fit only that build"
    : > "$LIST"; mkdir -p "$ORIG"
    ok "i76.exe = GOG 2.1.0.17"

    say "3. byte patches (payload/patches)"
    local n=0 app tgt srcrel smd5 tmd5 pf s out
    while IFS=$'\t' read -r app tgt srcrel smd5 tmd5 pf; do
        case "$app" in gold) ;; *) continue;; esac
        s="$(ci "$G" "$srcrel")" || die "patch source missing: $srcrel"
        [ "$(md5of "$s")" = "$smd5" ] || die "$srcrel md5 $(md5of "$s") is not $smd5 (not a GOG 2.1.0.17 file)"
        out="$DEST/.patch.out"
        python3 "$KIT/tools/bspatch.py" "$s" "$out" "$PAY/patches/$pf" || die "patch $pf failed"
        [ "$(md5of "$out")" = "$tmd5" ] || die "patched $tgt md5 $(md5of "$out") is not $tmd5"
        place "$out" "$tgt"; rm -f "$out"; n=$((n + 1))
    done < <(grep -v '^#' "$PAY/patches/patches.txt")
    ok "$n files patched and read back (i76.exe, i76shell.dll, ADDON auto / coop arenas)"

    say "4. our files"
    local s0; s0="$(ci "$G" STRLKUP.DLL)" || die "no STRLKUP.DLL in the game folder"
    keep "$s0"; [ -e "$G/strlkup_orig.dll" ] || cp -p "$ORIG/${s0#$G/}" "$G/strlkup_orig.dll"
    place "$PAY/gold/STRLKUP.DLL" STRLKUP.DLL
    place "$PAY/gold/u32x.dll" u32x.dll
    place "$PAY/gold/i7_sfrce.dll" i7_sfrce.dll
    place "$PAY/gold/input.map" input.map.profile-pad; place "$PAY/gold/input.map" input.map
    ok "proxy STRLKUP.DLL $(md5of "$G/STRLKUP.DLL" | cut -c1-8) (GOG's = strlkup_orig.dll), u32x.dll, rumble shim i7_sfrce.dll, input.map"
    local D; D="$(mktemp -d "$DEST/.kit-dgv.XXXX")"
    unzip -q -o "$DGV" '3Dfx/x86/Glide2x.dll' 'MS/x86/DDraw.dll' 'MS/x86/D3DImm.dll' -d "$D"
    place "$D/3Dfx/x86/Glide2x.dll" Glide2x.dll; place "$D/MS/x86/DDraw.dll" ddraw.dll; place "$D/MS/x86/D3DImm.dll" d3dimm.dll
    place "$KIT/dgVoodoo.conf" dgVoodoo.conf; rm -rf "$D"
    ok "dgVoodoo 2.78.2 Glide2x / ddraw / d3dimm + the Deck's dgVoodoo.conf (GOG's glide2x.dll kept in _gog-originals)"
    D="$(mktemp -d "$DEST/.kit-ipx.XXXX")"; unzip -q -o "$IPX" -d "$D"
    for f in ipxwrapper.dll wsock32.dll mswsock.dll; do s="$(find "$D" -iname "$f" -print -quit)"; [ -n "$s" ] || die "IPXWrapper zip has no $f"; place "$s" "$f"; done
    rm -rf "$D"; ok "IPXWrapper 0.7.2 (LAN games)"
    if p="$(ci "$G" I76PATCH.DLL)"; then keep "$p"; mv "$p" "$p.disabled"; ok "I76PATCH.DLL disabled (GOG's 20 fps cap; the fixed step paces the game)"; fi
    if (cd "$KIT/tools" && python3 gpw-envelopes.py "$G" --out "$G/rumble-envelopes.ini") >/dev/null 2>&1; then
        echo "$(md5of "$G/rumble-envelopes.ini")  game/rumble-envelopes.ini" >> "$LIST"
        ok "rumble envelopes from your sound files: $(grep -c = "$G/rumble-envelopes.ini") (textures the slip / road rumble)"
    else
        note "rumble envelopes not made (needs liblzo2; SteamOS has it): rumble runs physics-only"
    fi

    say "5. launchers, preset, pad layer"
    for f in i76-deck-launch.sh i76-deck-launch-mp.sh; do cp "$PAY/deck/$f" "$DEST/$f"; chmod +x "$DEST/$f"; echo "$(md5of "$DEST/$f")  $f" >> "$LIST"; done
    for f in i76-env.sh i76-env-mp.sh; do cp "$KIT/$f" "$DEST/$f"; echo "$(md5of "$DEST/$f")  $f" >> "$LIST"; done
    [ -f "$DEST/i76-env.local.sh" ] || cp "$KIT/i76-env.local.sh.example" "$DEST/i76-env.local.sh"
    mkdir -p "$DEST/ahk"; for f in AutoHotkeyU32.exe license.txt i76-remap.ahk; do cp "$PAY/ahk/$f" "$DEST/ahk/$f"; echo "$(md5of "$DEST/ahk/$f")  ahk/$f" >> "$LIST"; done
    cp "$PAY/deck/controller_neptune_i76_pad.vdf" "$DEST/"
    printf '%s\n' "$VERSION" > "$DEST/KIT-VERSION.txt"
    ok "i76-deck-launch.sh (+ -mp), i76-env.sh (preset), i76-env.local.sh (yours), ahk/ (pad layer)"
    say "done: $(grep -c . "$LIST") files placed, $(find "$ORIG" -type f | wc -l) GOG originals kept in game/_gog-originals"
    echo
    echo "Next: ./i76-deck-kit.sh steam   (adds the library entry; Steam restarts), or by hand in Desktop Mode:"
    echo "  Steam > Add a Game > Add a Non-Steam Game > Browse > $G/i76.exe, then its Properties:"
    echo "    Launch options:  \"$DEST/i76-deck-launch.sh\" %command% -glide"
    echo "    Compatibility:   Force ... GE-Proton10-12 (or Proton Experimental)"
    echo "    Controller:      Browse Configs > Templates > Interstate 76 gamepad (controller_neptune_i76_pad.vdf)"
}

do_steam() {
    [ -f "$G/i76.exe" ] || die "no game in $G: run install first"
    local TPL="$HOME/.steam/steam/controller_base/templates"
    export I76_GAMEDIR="$G" I76_LAUNCH_OPTIONS="\"$DEST/i76-deck-launch.sh\" %command% -glide" I76_TEMPLATE=controller_neptune_i76_pad.vdf
    export I76_TEMPLATE_SRC="$DEST/controller_neptune_i76_pad.vdf" I76_SHORTCUT_NAME="$NAME"
    if [ "$DRY" = 1 ]; then I76_DRY_RUN=1 python3 "$KIT/tools/add-to-steam.py"; return; fi
    say "Steam must be closed to add the entry (it rewrites its files at exit). Close it now? [y/N]"
    read -r a; case "$a" in y|Y) ;; *) die "cancelled (nothing changed)";; esac
    "$HOME/.local/share/Steam/steam.sh" -shutdown >/dev/null 2>&1 || true
    for i in $(seq 1 40); do pgrep -x steam >/dev/null || break; sleep 1; done
    pgrep -x steam >/dev/null && die "Steam is still running: close it and run this again"
    mkdir -p "$TPL"
    python3 "$KIT/tools/add-to-steam.py"
    ( setsid steam >/dev/null 2>&1 & ) || true
    ok "library entry '$NAME' added; Steam is starting again. Play it from Game Mode."
}

do_verify() {
    [ -f "$LIST" ] || die "no $LIST (not a kit install)"
    local bad=0 m rel
    while read -r m rel; do [ "$(md5of "$DEST/$rel")" = "$m" ] || { echo "   changed: $rel"; bad=$((bad + 1)); }; done < "$LIST"
    echo "verify: $(grep -c . "$LIST") kit files, $bad changed ($DEST)"; [ "$bad" -eq 0 ]
}

case "$cmd" in
    install) do_install;;
    steam) do_steam;;
    verify) do_verify;;
    *) sed -n '5,9p' "$0" | sed 's/^#  \{0,1\}//'; exit 2;;
esac
