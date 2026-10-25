#!/bin/bash
# =====================================================================================================================
#  I'76 Mac Kit (i76-everywhere) - builds "Interstate 76 Gold.app" and "Interstate 76 Nitro.app" on YOUR Mac from YOUR
#  GOG copy of the game. Nothing of the game is in this kit; nothing is installed outside the two apps (+ a download cache).
#  README.md beside this script is the user guide. No sudo, no admin password, no Xcode, no Homebrew needed.
#
#    ./i76-mac-kit.sh build --gold <GOG Gold folder | setup_interstate76_*.exe | .zip>
#                           [--nitro <GOG Nitro Pack folder | setup_interstate76_nitro_pack_*.exe | .zip>]
#                           [--dest <folder>]        default ~/Applications/Sikarugir (where the family Macs keep them)
#                           [--graphics auto|base|fast|stock]   default auto (by chip: Pro / Max / Ultra = fast)
#                           [--replace]              move an existing app of the same name to the Trash first
#                           [--null-audio]           Wine's null sound driver (silent, no microphone prompt; for testing)
#    ./i76-mac-kit.sh graphics <app> auto|base|fast|stock|<file.env>   change the graphics keys of a built Gold app later
#    ./i76-mac-kit.sh verify <app>                   re-check every file the kit put into an app (md5)
#
#  What build does, per app (the same recipe as the hand-built family apps: docs/records/MAC-KIT-2026-10-25.md):
#   1. downloads (once, cached in ~/Library/Caches/i76-mac-kit) and checks by SHA-256 (pins.txt): the Sikarugir wrapper
#      template 1.0.11 and Wine engine WS12WineSikarugir 10.0_6 (GitHub, Sikarugir-App), DxWnd 2.06.14 (SourceForge),
#      IPXWrapper 0.7.2 (GitHub, solemnwarning)
#   2. the app = the template + the engine (minus wine-mono, wine-gecko, MoltenVK and the D3D-to-Metal renderers I'76 never
#      uses), its Contents/MacOS/Sikarugir = our launch stub (stubs/, fixed Mach-O UUID: macOS keeps the Local Network answer)
#   3. a fresh Wine prefix (wineboot), user folders kept inside the app (no links into your home folder)
#   4. your GOG files copied in, then patched in place: our proxy as STRLKUP.DLL (GOG's kept as strlkup_orig.dll), the
#      byte patches of payload/patches (checked against your file's md5 before, the result's md5 after), OpenGLide-HD,
#      IPXWrapper, the controls, the co-op / scenario arenas; every GOG file we replace is kept beside it or in _gog-originals
#   5. DxWnd + its profile sized for your main display, the Wine registry keys, the graphics tier
# =====================================================================================================================
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
PAY="$KIT/payload"
CACHE="$HOME/Library/Caches/i76-mac-kit"
VERSION="$(head -1 "$KIT/VERSION.txt" 2>/dev/null || echo dev)"
say()  { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '   ok  %s\n' "$*"; }
note() { printf '   ..  %s\n' "$*"; }
die()  { printf '\n\033[31mi76-mac-kit: %s\033[0m\n' "$*" >&2; exit 1; }
md5of() { md5 -q "$1" 2>/dev/null || echo missing; }

# known GOG inputs (GOG offline installers 2.1.0.17 / GOG Galaxy: the same files)
GOLD_EXE_MD5=9a232dcc2c164648cff20c414c1f9698
NITRO_EXE_MD5=28b8ae276e88f4ffb13f17df159f09dc
OLD_GOLD_EXE_MD5=60abf7bc   # the 2019 GOG build some older libraries still have (not supported by this kit yet)

usage() { sed -n '5,14p' "$0" | sed 's/^#  \{0,1\}//'; exit 2; }

# ---------------------------------------------------------------------------------------------------------------------
preflight() {
    [ "$(uname -s)" = Darwin ] || die "this kit runs on macOS"
    local v; v="$(sw_vers -productVersion)"
    case "$v" in 1[0-3].*|14.[0-5]|14.[0-5].*) die "macOS $v: the Sikarugir Wine runtime needs macOS 14.6 or later";; esac
    ARCH="$(uname -m)"
    if [ "$ARCH" = arm64 ] && ! arch -x86_64 /usr/bin/true 2>/dev/null; then
        die "Rosetta 2 is not installed (Wine runs as an Intel program). Install it once, then run this again:
    softwareupdate --install-rosetta --agree-to-license"
    fi
    for t in curl shasum tar bspatch perl plutil codesign md5 ditto xattr system_profiler; do
        command -v "$t" >/dev/null || die "missing system tool: $t"
    done
    [ -d "$PAY" ] || die "no payload/ folder beside the script: unzip the whole kit, not just this file"
    local free; free=$(df -k "$HOME" | awk 'NR==2 {print int($4/1024/1024)}')
    [ "$free" -ge 6 ] || die "only ${free} GB free in your home folder; the build needs about 6 GB (the two apps end at about 3 GB)"
}

# pins.txt: name  sha256  url
fetch() {   # fetch <name> -> prints the cached file path
    local line sha url f
    line="$(awk -v n="$1" '$1 == n' "$KIT/pins.txt")"; [ -n "$line" ] || die "no pin for $1"
    sha="$(echo "$line" | awk '{print $2}')"; url="$(echo "$line" | awk '{print $3}')"
    mkdir -p "$CACHE"; f="$CACHE/$1"
    if [ -f "$f" ] && [ "$(shasum -a 256 "$f" | awk '{print $1}')" = "$sha" ]; then echo "$f"; return; fi
    printf '   ..  downloading %s\n' "$url" >&2
    curl -fL --retry 3 --progress-bar -o "$f.part" "$url" >&2 || die "download failed: $url"
    local got; got="$(shasum -a 256 "$f.part" | awk '{print $1}')"
    [ "$got" = "$sha" ] || { rm -f "$f.part"; die "$1: SHA-256 $got is not the pinned $sha - not used"; }
    mv "$f.part" "$f"; echo "$f"
}

wineenv() {   # wineenv <app>: the environment the launch stub sets, for wine calls during the build
    local A="$1" gv="$1/Contents/Frameworks/GStreamer.framework/Versions/1.0"
    export DYLD_FALLBACK_LIBRARY_PATH="$A/Contents/Frameworks:$gv/lib:$A/Contents/SharedSupport/wine/lib"
    export WINEPREFIX="$A/Contents/SharedSupport/prefix" WINEESYNC=1 WINEMSYNC=1 WINEDEBUG=-all
    export WINEDLLOVERRIDES="mscoree,mshtml="   # no wine-mono / wine-gecko install dialogs (both removed from the engine)
    W="$A/Contents/SharedSupport/wine/bin/wine"; WS="$A/Contents/SharedSupport/wine/bin/wineserver"
}

# ---------------------------------------------------------------------------------------------------------------------
# the base runtime: template + engine, slimmed (made once per run in the work folder, then cloned per app)
make_base() {
    local tpl eng
    tpl="$(fetch Template-1.0.11.tar.xz)"; eng="$(fetch WS12WineSikarugir10.0_6.tar.xz)"
    say "Wine runtime (Sikarugir template 1.0.11 + Wine 10.0_6)"
    mkdir -p "$WORK/x"
    tar -xJf "$tpl" -C "$WORK/x"; tar -xJf "$eng" -C "$WORK/x"
    BASE="$WORK/base.app"
    mv "$WORK/x/Template-1.0.11.app" "$BASE"
    mv "$WORK/x/wswine.bundle" "$BASE/Contents/SharedSupport/wine"
    rm -rf "$BASE/Contents/SharedSupport/wine/share/wine/mono" "$BASE/Contents/SharedSupport/wine/share/wine/gecko" \
           "$BASE/Contents/Frameworks/renderer" "$BASE/Contents/Frameworks/moltenvkcx" "$BASE/Contents/Frameworks/libMoltenVK.dylib"
    xattr -cr "$BASE" 2>/dev/null || true
    ok "$(du -sh "$BASE" | awk '{print $1}') runtime ($(cat "$BASE/Contents/SharedSupport/wine/version" 2>/dev/null))"
}

# ---------------------------------------------------------------------------------------------------------------------
# GOG input: a folder, a GOG offline installer (.exe, Inno Setup) or a zip of the folder -> echo the game folder
gog_source() {   # gog_source <path> <gold|nitro>
    local p="$1" kind="$2" exe d
    [ "$kind" = gold ] && exe=i76.exe || exe=nitro.exe
    if [ -d "$p" ]; then
        d="$(find "$p" -maxdepth 3 -iname "$exe" -type f | head -1)"
        [ -n "$d" ] || die "no $exe in $p (give the folder that holds $exe)"
        dirname "$d"; return
    fi
    [ -f "$p" ] || die "not found: $p"
    local out="$WORK/gog-$kind"; rm -rf "$out"; mkdir -p "$out"
    case "$(echo "$p" | tr 'A-Z' 'a-z')" in
    *.zip)
        note "unpacking $(basename "$p")" >&2
        ditto -x -k "$p" "$out" || die "could not unpack $p" ;;
    *.exe)
        if command -v innoextract >/dev/null; then
            note "extracting $(basename "$p") with innoextract" >&2
            innoextract -s -d "$out" "$p" >&2 || die "innoextract failed on $p"
        else
            # no innoextract: run GOG's own installer, silently, in a throw-away Wine prefix (needs the runtime first)
            note "running $(basename "$p") silently under Wine (a minute or two; nothing is installed on your Mac)" >&2
            # Wine's null graphics driver: the installer runs without any window (nothing to click, nothing on screen)
            local sp="$WORK/setup-prefix-$kind"
            ( wineenv "$BASE"; export WINEPREFIX="$sp"
              "$W" wineboot --init >/dev/null 2>&1; "$WS" -w
              "$W" reg add 'HKCU\Software\Wine\Drivers' /v Graphics /d null /f >/dev/null 2>&1
              "$W" "$(winpath "$p")" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /NOICONS /DIR='C:\gogout' >/dev/null 2>&1 || true
              "$WS" -w )
            [ -d "$sp/drive_c/gogout" ] || die "the GOG installer did not write a game folder (install innoextract, or copy the folder from a PC)"
            ditto "$sp/drive_c/gogout" "$out/app"; rm -rf "$sp"
            rm -f "$out/app"/unins000.* "$out/app"/*.lnk   # the installer's uninstaller and Start-menu shortcut (not the game)
            # tested 2026-10-25: the result = innoextract's app\ folder, file for file (GOG 2.1.0.17 Gold and Nitro Pack)
        fi ;;
    *) die "$p: give a folder, a GOG setup_*.exe or a .zip" ;;
    esac
    d="$(find "$out" -maxdepth 4 -iname "$exe" -type f | head -1)"
    [ -n "$d" ] || die "no $exe found in $(basename "$p") - is it the right GOG installer (the Windows one)?"
    dirname "$d"
}

check_gog() {   # check_gog <folder> <gold|nitro>
    local m
    if [ "$2" = gold ]; then
        m="$(md5of "$1/i76.exe")"
        case "$m" in
        $GOLD_EXE_MD5) ok "GOG Interstate '76 2.1.0.17 (i76.exe ${m:0:8})" ;;
        ${OLD_GOLD_EXE_MD5}*) die "this i76.exe ($m) is GOG's older 2019 build. The kit's patches are made for the current one:
    download the current Windows offline installer from your GOG library and give that." ;;
        *) die "$1/i76.exe md5 $m is not GOG's Interstate '76 (2.1.0.17: $GOLD_EXE_MD5); a patched or other copy?" ;;
        esac
    else
        m="$(md5of "$1/nitro.exe")"
        [ "$m" = "$NITRO_EXE_MD5" ] || die "$1/nitro.exe md5 $m is not GOG's Nitro Pack ($NITRO_EXE_MD5)"
        ok "GOG Interstate '76 Nitro Pack (nitro.exe ${m:0:8})"
    fi
    [ -f "$1/strlkup_orig.dll" ] && die "$1 already carries i76-everywhere files (strlkup_orig.dll): give a clean GOG copy"
    return 0
}

# ---------------------------------------------------------------------------------------------------------------------
ci() {   # ci <folder> <name>: the file's actual name in a folder, case-insensitive (GOG mixes cases)
    local f; f="$(find "$1" -maxdepth 1 -iname "$2" | head -1)"; [ -n "$f" ] && echo "$f" || echo "$1/$2"
}
keep() {   # keep <folder> <name> <kept name>: move GOG's file aside once (never overwrite a kept original)
    local s; s="$(ci "$1" "$2")"
    [ -f "$s" ] || die "missing GOG file $2 in $1"
    if [ -e "$1/$3" ]; then rm -f "$s"; else mv "$s" "$1/$3"; fi
}
put() {   # put <src> <dst>: copy, then read back
    rm -f "$2"; cp "$1" "$2"
    [ "$(md5of "$1")" = "$(md5of "$2")" ] || die "write did not read back: $2"
    MANIFEST="$MANIFEST$(md5of "$2")  ${2#$GD/}"$'\n'
}
apply_patches() {   # apply_patches <gold|nitro>: payload/patches/patches.txt rows for that app
    local app src dst sm dm pf n=0
    while IFS=$'\t' read -r app dst src sm dm pf; do
        case "$app" in \#*|'') continue;; esac
        [ "$app" = "$1" ] || continue
        local s d; s="$GD/$src"; d="$GD/$dst"
        [ -f "$s" ] || s="$(ci "$(dirname "$s")" "$(basename "$s")")"
        [ "$(md5of "$s")" = "$sm" ] || die "$src: md5 $(md5of "$s") is not GOG's ($sm) - patch $pf not applied"
        mkdir -p "$(dirname "$d")"
        if [ "$src" = "$dst" ]; then
            [ -e "$GD/_gog-originals/$(basename "$s")" ] || cp "$s" "$GD/_gog-originals/$(basename "$s")"
            bspatch "$s" "$d.kit-new" "$PAY/patches/$pf"; mv "$d.kit-new" "$d"
        else rm -f "$d"; bspatch "$s" "$d" "$PAY/patches/$pf"; fi
        [ "$(md5of "$d")" = "$dm" ] || die "$dst: patched md5 $(md5of "$d") is not $dm"
        MANIFEST="$MANIFEST$dm  $dst"$'\n'; n=$((n + 1))
    done < "$PAY/patches/patches.txt"
    ok "$n byte patches applied, each result md5-checked"
}

# DxWnd profile: the family apps' profile (payload/dxwnd-profile.ini), sized for the main display. The window keeps the
# 1728x1117 shape (the 14" MacBook panel, measured on every family Mac incl. a 3440x1440 monitor) unless the main display
# is 16:10 or narrower, then its own size (Andrew's 1440x900: a narrower window put the menu pointer ~14 px off).
display_size() {
    local s; s="$(system_profiler SPDisplaysDataType 2>/dev/null | awk '
        /^        [^ ].*:$/ { ui = ""; res = "" }
        /Resolution:/ { res = $2 "x" $4 }
        /UI Looks like:/ { ui = $4 "x" $6 }
        /Main Display: Yes/ { main = 1 }
        main && (ui != "" || res != "") && /Online|Mirror|Rotation/ { print (ui != "" ? ui : res); exit }')"
    echo "${s:-1728x1117}"
}
dxwnd_ini() {   # dxwnd_ini <gold|nitro> <dst>
    local sz w h; sz="$(display_size)"; w="${sz%x*}"; h="${sz#*x}"
    if [ "$w" -gt 0 ] 2>/dev/null && [ $((w * 100 / h)) -le 161 ]; then :; else w=1728; h=1117; fi
    DXW="$w"; DXH="$h"
    if [ "$1" = gold ]; then
        sed -e "s/@SIZX@/$w/; s/@SIZY@/$h/" "$PAY/dxwnd-profile.ini" > "$2"
    else
        sed -e "s/@SIZX@/$w/; s/@SIZY@/$h/" \
            -e 's/^title0=.*/title0=Interstate 76 Nitro/' -e 's/^path0=.*/path0=C:\\GOG Games\\Interstate 76 Nitro\\nitro.exe/' \
            -e 's/^notes0=.*/notes0=/' -e 's/^cmdline0=.*/cmdline0=nitro.exe -glide/' "$PAY/dxwnd-profile.ini" > "$2"
    fi
    perl -pi -e 's/\r?\n/\r\n/' "$2"
}

tier_for_chip() {
    local c; c="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo unknown)"
    case "$c" in *Pro*|*Max*|*Ultra*) echo fast;; *) echo base;; esac
}
tier_reg() {   # tier_reg <auto|base|fast|stock|file> -> .reg lines for HKCU\Environment (every tier key: set or deleted)
    local t="$1" keys f
    [ "$t" = auto ] && t="$(tier_for_chip)"
    keys="$(cat "$PAY/graphics/base.env" "$PAY/graphics/fast.env" | grep -E '^[A-Z0-9_]+=' | sed 's/=.*//' | sort -u)"
    case "$t" in base|fast) f="$PAY/graphics/$t.env";; stock) f=/dev/null;; *) [ -f "$t" ] || die "no graphics file $t"; f="$t";; esac
    TIER="$t"
    for k in $keys; do
        local v; v="$(grep -E "^$k=" "$f" | tail -1 | sed 's/^[^=]*=//' || true)"
        [ -n "$v" ] && printf '"%s"="%s"\n' "$k" "$v" || printf '"%s"=-\n' "$k"
    done
    if [ "$f" != /dev/null ]; then   # a file's own extra keys (not in either tier)
        { grep -E '^[A-Z0-9_]+=' "$f" || true; } | while IFS='=' read -r k v; do
            echo "$keys" | grep -qx "$k" && continue
            [ -n "$v" ] && printf '"%s"="%s"\n' "$k" "$v" || printf '"%s"=-\n' "$k"; done   # KEY= removes it again
    fi
    return 0
}

# ---------------------------------------------------------------------------------------------------------------------
build_app() {   # build_app <gold|nitro> <GOG folder>
    local kind="$1" src="$2" name bid bname stub game exe
    if [ "$kind" = gold ]; then name="Interstate 76 Gold"; bid=com.sikarugir.Interstate76; bname=Interstate76; game="Interstate 76"
    else name="Interstate 76 Nitro"; bid=com.sikarugir.Interstate76Nitro; bname=Interstate76Nitro; game="Interstate 76 Nitro"; fi
    local A="$DEST/$name.app"
    say ""; say "== $name.app"
    if [ -e "$A" ]; then
        [ -n "$REPLACE" ] || die "$A exists. Quit it and run again with --replace (it goes to the Trash), or pick --dest"
        pgrep -f "$(printf '%s' "$A" | sed 's/[][\.*^$()+?{}|]/\\&/g')/Contents" >/dev/null && die "$name is running - quit it first"
        mkdir -p "$HOME/.Trash"; mv "$A" "$HOME/.Trash/$name $(date +%Y%m%d-%H%M%S).app"; note "old app moved to the Trash"
    fi
    mkdir -p "$DEST"
    cp -cR "$BASE" "$A" 2>/dev/null || cp -R "$BASE" "$A"
    # bundle identity: the family apps' ids (LaunchServices keeps Gold and Nitro apart) + the fixed-UUID launch stub
    plutil -replace CFBundleIdentifier -string "$bid" "$A/Contents/Info.plist"
    plutil -replace CFBundleName -string "$bname" "$A/Contents/Info.plist"
    plutil -replace "Program Name and Path" -string "C:\\GOG Games\\$game\\$( [ $kind = gold ] && echo i76.exe || echo nitro.exe)" "$A/Contents/Info.plist"
    mv "$A/Contents/MacOS/Sikarugir" "$A/Contents/MacOS/Sikarugir.orig"
    stub="$KIT/stubs/Sikarugir-$kind-$ARCH"; [ -f "$stub" ] || die "no launch stub for $ARCH ($stub)"
    cp "$stub" "$A/Contents/MacOS/Sikarugir"; chmod 755 "$A/Contents/MacOS/Sikarugir"
    ok "bundle $bid, launcher $(md5of "$A/Contents/MacOS/Sikarugir" | cut -c1-8) ($ARCH)"

    say "   Wine prefix"
    wineenv "$A"
    "$W" wineboot --init >/dev/null 2>&1 || true
    "$WS" -w || true
    [ -f "$WINEPREFIX/system.reg" ] || die "wineboot did not create the prefix (is Rosetta working? try: arch -x86_64 /usr/bin/true)"
    # user folders that point out of the prefix (Desktop -> ~/Desktop, ...) become plain folders: a link into ~ is a
    # macOS privacy prompt (Documents, Desktop) the first time the game lists a folder
    find "$WINEPREFIX/drive_c/users" -maxdepth 2 -type l | while read -r l; do
        case "$(readlink "$l")" in /*) rm "$l"; mkdir "$l";; esac; done
    ok "prefix ($(du -sh "$WINEPREFIX" | awk '{print $1}'))"

    say "   game folder: C:\\GOG Games\\$game"
    GD="$WINEPREFIX/drive_c/GOG Games/$game"; MANIFEST=""
    mkdir -p "$GD"; ditto "$src" "$GD"; xattr -cr "$GD" 2>/dev/null || true
    ok "$(find "$GD" -type f | wc -l | tr -d ' ') GOG files copied"
    local og="$GD/_gog-originals"; mkdir -p "$og"
    keep "$GD" strlkup.dll strlkup_orig.dll
    if [ "$kind" = gold ]; then
        put "$PAY/gold/STRLKUP.DLL" "$GD/STRLKUP.DLL"
        apply_patches gold
        for f in ADDON/auto0{1,2,3,4,5,6,7}.lvl ADDON/coop{01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17}.lvl; do
            printf 'installed by tools/coop-install.py\r\n' > "$GD/$f.coop"; done   # the packs' marker (written on Windows: CRLF)
        put "$PAY/gold/u32x.dll" "$GD/u32x.dll"
        keep "$GD" input.map input.map.stock-gog; put "$PAY/gold/input.map" "$GD/input.map"
        keep "$GD" SMACKW32.DLL smackorg.dll;     put "$PAY/gold/SMACKW32.DLL" "$GD/SMACKW32.DLL"
        keep "$GD" i7_sfrce.dll i7_sfrce_org.dll; put "$PAY/gold/i7_sfrce.dll" "$GD/i7_sfrce.dll"
        put "$PAY/gold/rumble-envelopes.ini" "$GD/rumble-envelopes.ini"
        # the graphic-detail options the Windows Patch Kit sets, only while they are GOG's defaults (rear mirror full)
        local def; def="$(ci "$GD" I76PLYR.DEF)"
        if [ -f "$def" ] && [ "$(md5of "$def")" = 1bff014676ba4fb370d2524383a0a145 ]; then
            cp "$def" "$def.pre-i76e"
            perl -e 'open(my $h, "+<:raw", $ARGV[0]) or die; for ([0x4A,2],[0x4D,2],[0x4E,1]) { seek($h,$_->[0],0); print $h chr($_->[1]) } close $h' "$def"
            ok "graphic detail options: GOG's defaults -> 2 / 2 / 1 (I76PLYR.DEF $(md5of "$def" | cut -c1-8); original .pre-i76e)"
        fi
    else
        put "$PAY/nitro/Strlkup.dll" "$GD/Strlkup.dll"
        apply_patches nitro
    fi
    # OpenGLide-HD (GOG ships OpenGLide; ours adds the Mac output modes, gamma and HD textures) + its INI
    keep "$GD" glide2x.dll _gog-originals/glide2x.dll; keep "$GD" OpenGLid.INI _gog-originals/OpenGLid.INI
    put "$PAY/openglide/glide2x.dll" "$GD/$( [ $kind = gold ] && echo Glide2x.dll || echo glide2x.dll)"
    put "$PAY/openglide/OpenGLid.INI" "$GD/OpenGLid.INI"
    # IPXWrapper 0.7.2 (LAN games over UDP; Wine loads it for the game only, registry below)
    local ipx; ipx="$(fetch ipxwrapper-0.7.2.zip)"; rm -rf "$WORK/ipx"; mkdir -p "$WORK/ipx"; tar -xf "$ipx" -C "$WORK/ipx"
    for f in ipxwrapper.dll wsock32.dll mswsock.dll; do put "$WORK/ipx/ipxwrapper-0.7.2/$f" "$GD/$f"; done
    printf '%s' "$MANIFEST" > "$A/Contents/i76-mac-kit-files.md5"

    say "   DxWnd 2.06.14 + profile"
    local dx; dx="$(fetch dxwnd-v2_06_14_build.rar)"
    mkdir -p "$WINEPREFIX/drive_c/dxwnd"; tar -xf "$dx" -C "$WINEPREFIX/drive_c/dxwnd"
    dxwnd_ini "$kind" "$WINEPREFIX/drive_c/dxwnd/dxwnd.ini"
    ok "window shape ${DXW}x${DXH} (main display $(display_size))"
    if [ "$kind" = gold ]; then   # the mouse-button / wheel remapper the Gold launcher starts when present
        mkdir -p "$WINEPREFIX/drive_c/AutoHotkey"
        for f in AutoHotkeyU32.exe license.txt i76-remap.ahk; do cp "$PAY/ahk/$f" "$WINEPREFIX/drive_c/AutoHotkey/$f"; done
    fi

    say "   registry"
    local reg="$WORK/$kind.reg"
    [ "$kind" = gold ] && exe=i76.exe || exe=nitro.exe
    {
        printf 'REGEDIT4\n\n[HKEY_CURRENT_USER\\Environment]\n'
        grep -E '^[A-Za-z0-9_]+=' "$PAY/env/$kind.env" | while IFS='=' read -r k v; do printf '"%s"="%s"\n' "$k" "$v"; done
        printf '"OGL_VIEWPORT"="%s"\n' "$(viewport "$DXW" "$DXH")"
        [ "$kind" = gold ] && tier_reg "$GRAPHICS"
        printf '\n[HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\%s]\n"Version"="win98"\n' "$exe"
        printf '\n[HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\%s\\Direct3D]\n"renderer"="gdi"\n' "$exe"
        printf '\n[HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\%s\\DllOverrides]\n"mswsock"="native,builtin"\n"wsock32"="native,builtin"\n' "$exe"
        printf '\n[HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\%s\\Mac Driver]\n"WindowsFloatWhenInactive"="all"\n' "$exe"
        [ "$kind" = nitro ] && printf '\n[HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\nitro.exe\\Explorer]\n"Desktop"="i76"\n'
        printf '\n[HKEY_CURRENT_USER\\Software\\Wine\\Explorer\\Desktops]\n"i76"="1280x960"\n'
        printf '\n[HKEY_CURRENT_USER\\Software\\Wine\\Mac Driver]\n"AllowSetGamma"=dword:00000000\n"LeftCommandIsCtrl"="Y"\n"LeftOptionIsAlt"="Y"\n"RetinaMode"="n"\n"RightCommandIsCtrl"="Y"\n"RightOptionIsAlt"="Y"\n'
        [ -n "$NULLAUDIO" ] && printf '\n[HKEY_CURRENT_USER\\Software\\Wine\\Drivers]\n"Audio"=""\n'
        # the keys GOG's installer writes on Windows (a copied folder brings none): "Minimum"="0" = a full install, the data on
        # the hard disk. Without it Gold 2.1.0.17 stops at boot on "Please insert CD 'Interstate '76 CD 2'" (kit test
        # 2026-10-25) and a Nitro mission's terrain never loads (NITRO-MP-DESIGN s.0.5.16). Both registry views (WOW6432Node).
        local prod view
        [ "$kind" = gold ] && prod="Interstate '76 Gold Edition" || prod="Interstate '76 Nitro Pack"
        for view in 'Software' 'Software\Wow6432Node'; do
            printf '\n[HKEY_LOCAL_MACHINE\\%s\\Activision\\%s]\n"Minimum"="0"\n' "$view" "$prod"
            if [ "$kind" = gold ]; then printf '\n[HKEY_LOCAL_MACHINE\\%s\\Activision\\%s]\n"EXE"="i76.exe"\n' "$view" "Interstate '76"; fi
        done
    } > "$reg"
    "$W" regedit /S "$(winpath "$reg")" >/dev/null 2>&1 || "$W" reg import "$(winpath "$reg")" >/dev/null 2>&1 || die "registry import failed"
    "$WS" -w || true
    grep -q '"I76_MUSIC_THREAD"="1"' "$WINEPREFIX/user.reg" && grep -q '"renderer"="gdi"' "$WINEPREFIX/user.reg" \
        && [ "$(grep -c '^"Minimum"="0"' "$WINEPREFIX/system.reg")" -ge 2 ] || die "registry keys did not read back"
    ok "Wine keys for $exe written and read back$( [ $kind = gold ] && echo ", graphics tier $TIER")$( [ -n "$NULLAUDIO" ] && echo ', NULL AUDIO')"

    xattr -dr com.apple.quarantine "$A" 2>/dev/null || true
    { echo "built by the I'76 Mac Kit $VERSION on $(date '+%Y-%m-%d %H:%M'), $(sw_vers -productVersion) $ARCH"
      echo "from $src"; echo "launcher $(md5of "$A/Contents/MacOS/Sikarugir"), graphics ${TIER:-n/a}, display ${DXW}x${DXH}"; } > "$A/Contents/i76-mac-kit.txt"
    ok "done: $A ($(du -sh "$A" | awk '{print $1}'))"
}
viewport() {   # the size the launcher computes at every start (the profile's shape fitted into the main display, points)
    local sz dw dh w h; sz="$(display_size)"; dw="${sz%x*}"; dh="${sz#*x}"
    if [ $(( dw * $2 )) -gt $(( dh * $1 )) ]; then h=$dh; w=$(( dh * $1 / $2 )); else w=$dw; h=$(( dw * $2 / $1 )); fi
    echo "${w}x${h}"
}
winpath() { echo "Z:$(echo "$1" | sed 's|/|\\|g')"; }

# ---------------------------------------------------------------------------------------------------------------------
cmd="${1:-}"; [ -n "$cmd" ] || usage; shift
case "$cmd" in
build)
    GOLD=""; NITRO=""; DEST="$HOME/Applications/Sikarugir"; GRAPHICS=auto; REPLACE=""; NULLAUDIO=""
    while [ $# -gt 0 ]; do case "$1" in
        --gold) GOLD="$2"; shift 2;; --nitro) NITRO="$2"; shift 2;; --dest) DEST="$2"; shift 2;;
        --graphics) GRAPHICS="$2"; shift 2;; --replace) REPLACE=1; shift;; --null-audio) NULLAUDIO=1; shift;;
        *) die "unknown option $1";; esac; done
    [ -n "$GOLD$NITRO" ] || usage
    preflight
    say "I'76 Mac Kit $VERSION  ($(sw_vers -productVersion), $ARCH, $(sysctl -n machdep.cpu.brand_string 2>/dev/null))"
    WORK="$(mktemp -d "${TMPDIR:-/tmp}/i76-mac-kit.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT
    make_base
    if [ -n "$GOLD" ]; then say "GOG Gold: $GOLD"; GS="$(gog_source "$GOLD" gold)"; check_gog "$GS" gold; fi
    if [ -n "$NITRO" ]; then say "GOG Nitro Pack: $NITRO"; NS="$(gog_source "$NITRO" nitro)"; check_gog "$NS" nitro; fi
    [ -n "$GOLD" ] && build_app gold "$GS"
    [ -n "$NITRO" ] && build_app nitro "$NS"
    say ""; say "Finished. Open the apps from $DEST (Finder: Go > Home > Applications > Sikarugir)."
    say "First start: macOS may ask about the microphone (either answer works; answer it, the game waits) and, the first"
    say "time you JOIN a network game, about finding devices on your local network (say Allow). README.md has the rest."
    ;;
graphics)
    A="${1:?app}"; T="${2:?auto|base|fast|stock|file}"; A="${A%/}"
    [ -f "$A/Contents/SharedSupport/prefix/user.reg" ] || die "not a kit app: $A"
    pgrep -f "$(printf '%s' "$A" | sed 's/[][\.*^$()+?{}|]/\\&/g')/Contents" >/dev/null && die "quit the game first"
    preflight; WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
    { printf 'REGEDIT4\n\n[HKEY_CURRENT_USER\\Environment]\n'; tier_reg "$T"; } > "$WORK/t.reg"
    wineenv "$A"; "$W" regedit /S "$(winpath "$WORK/t.reg")" >/dev/null 2>&1; "$WS" -w || true
    say "graphics tier $TIER written to $(basename "$A"):"; awk '/^\[Environment\]/,/^$/' "$WINEPREFIX/user.reg" | grep -E 'I76_(ROAD|FAR|CLUTTER|TERRAIN|OBJECT|SHADOW|SHADE|MIRROR|GLIDE_FOG|SKY)' || echo "   (stock: no graphics keys)"
    ;;
verify)
    A="${1:?app}"; A="${A%/}"; M="$A/Contents/i76-mac-kit-files.md5"; [ -f "$M" ] || die "no kit manifest in $A"
    G="$(find "$A/Contents/SharedSupport/prefix/drive_c/GOG Games" -mindepth 1 -maxdepth 1 -type d | head -1)"
    bad=0; n=0
    while read -r h f; do n=$((n + 1)); [ "$(md5of "$G/$f")" = "$h" ] || { echo "CHANGED $f"; bad=$((bad + 1)); }; done < "$M"
    echo "verify: $n kit files, $bad changed ($G)"; [ "$bad" -eq 0 ]
    ;;
*) usage ;;
esac
