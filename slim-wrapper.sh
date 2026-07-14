#!/bin/sh
# Interstate '76 - slim the Wine wrapper down to what I76 actually needs.
# The Sikarugir wrapper is cloned from a Steam game, so it carries ~2.3 GB of bulk a
# 1997 GOG DirectDraw/Glide game never touches. This removes it. Takes the wrapper from
# ~3.9 GB to ~1.6 GB. All removals are provably unused by I76 (boot-verified in both
# the DxWnd and Voodoo modes). Reversible only by re-cloning/re-setting-up the wrapper,
# so the big items are moved to a quarantine first and only deleted after you confirm.
#
# Usage: ./slim-wrapper.sh            (quarantine + report; nothing deleted)
#        ./slim-wrapper.sh --commit   (delete the quarantine = free the space)
#        ./slim-wrapper.sh --restore  (undo: move quarantine back)
set -e
SIK="$HOME/Applications/Sikarugir"
APP="$SIK/Interstate 76 - Software (DxWnd).app"
PFX="$APP/Contents/SharedSupport/prefix/drive_c"
SHARE="$APP/Contents/SharedSupport/wine/share/wine"
Q="$SIK/.i76-quarantine"
[ -d "$APP" ] || { echo "wrapper not found: $APP"; exit 1; }

case "$1" in
  --restore)
    [ -d "$Q" ] || { echo "no quarantine to restore"; exit 0; }
    [ -d "$Q/Steam" ] && mv "$Q/Steam" "$PFX/Program Files (x86)/Steam"
    [ -d "$Q/mono" ]  && mv "$Q/mono"  "$SHARE/mono"
    [ -d "$Q/gecko" ] && mv "$Q/gecko" "$SHARE/gecko"
    [ -d "$Q/renderer" ]   && mv "$Q/renderer"   "$FW/renderer"
    [ -d "$Q/moltenvkcx" ] && mv "$Q/moltenvkcx" "$FW/moltenvkcx"
    [ -f "$Q/libMoltenVK.dylib" ] && mv "$Q/libMoltenVK.dylib" "$FW/libMoltenVK.dylib"
    [ -d "$Q/uSteam" ] && mv "$Q/uSteam" "$UAPP/Local/Steam"
    [ -d "$Q/uCEF" ]   && mv "$Q/uCEF"   "$UAPP/Local/CEF"
    rmdir "$Q" 2>/dev/null || true
    echo "restored."; exit 0 ;;
  --commit)
    [ -d "$Q" ] || { echo "nothing quarantined; run without --commit first"; exit 0; }
    echo "freeing $(du -sh "$Q" | cut -f1)..."
    rm -rf "$Q"; echo "done. wrapper is now $(du -sh "$APP" | cut -f1)."; exit 0 ;;
esac

# default: quarantine the fat (reversible). Takes the wrapper ~3.9G -> ~1.4G.
FW="$APP/Contents/Frameworks"
UAPP="$APP/Contents/SharedSupport/prefix/drive_c/users/Sikarugir/AppData"
mkdir -p "$Q"
#  - Steam client (~1.9G): leftover from the Steam-game clone; I76 is GOG, launched
#    directly by our stub - zero Steam code.
#  - wine-mono (~230M): the .NET runtime; I76 is native Win32.
#  - wine-gecko (~207M): the embedded browser (mshtml); I76 has no web content.
[ -d "$PFX/Program Files (x86)/Steam" ] && mv "$PFX/Program Files (x86)/Steam" "$Q/Steam" && echo "quarantined: Steam client"
[ -d "$SHARE/mono" ] && mv "$SHARE/mono" "$Q/mono" && echo "quarantined: wine-mono (.NET)"
[ -d "$SHARE/gecko" ] && mv "$SHARE/gecko" "$Q/gecko" && echo "quarantined: wine-gecko (browser)"
#  - Voodoo GPU stack (~140M): renderer backends (d3dmetal/dxmt/d9vk/dxvk) + MoltenVK.
#    The SOFTWARE renderer (the Mac build) is CPU->DirectDraw->winemac GL - it uses
#    NONE of these. Only the parked Voodoo/Glide path did. Verified: software mode
#    boots + renders menu/3D with all of this gone. (Un-parking Voodoo needs it back -
#    docs/VOODOO-PARKED.md.)
[ -d "$FW/renderer" ]   && mv "$FW/renderer"   "$Q/renderer"   && echo "quarantined: renderer backends"
[ -d "$FW/moltenvkcx" ] && mv "$FW/moltenvkcx" "$Q/moltenvkcx" && echo "quarantined: moltenvkcx"
[ -f "$FW/libMoltenVK.dylib" ] && mv "$FW/libMoltenVK.dylib" "$Q/libMoltenVK.dylib" && echo "quarantined: libMoltenVK"
#  - Steam/CEF profile leftovers (~70M) in the wine user profile.
[ -d "$UAPP/Local/Steam" ] && mv "$UAPP/Local/Steam" "$Q/uSteam" && echo "quarantined: user Steam data"
[ -d "$UAPP/Local/CEF" ]   && mv "$UAPP/Local/CEF"   "$Q/uCEF"   && echo "quarantined: user CEF cache"

echo ""
echo "Wrapper is now $(du -sh "$APP" | cut -f1) (quarantine holds $(du -sh "$Q" | cut -f1))."
echo "Launch it to confirm it still runs, then:  ./slim-wrapper.sh --commit"
echo "If anything broke:  ./slim-wrapper.sh --restore"
echo ""
echo "FURTHER (optional, ~120M): Contents/Frameworks/renderer/{d3dmetal,dxmt,d9vk} are"
echo "alternate D3D->Metal backends we don't use (our DXVK lives in wine/lib). Safe to"
echo "delete too, but confirm a Voodoo *mission* renders first (boot alone won't load them)."
