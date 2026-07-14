#!/bin/sh
# ============================================================================
#  Interstate '76 -> Apple Silicon Mac : one-double-click setup   (BETA)
# ============================================================================
#  Double-click this file (or run it) to finish setting up the Mac build. It
#  sequences the already-verified setup-*.sh steps + the required Wine registry
#  keys + builds the launcher apps -- turning the manual 7-step recipe into one
#  action.
#
#  *** BETA / not yet tested on a clean machine. ***  It does NOT create the
#  Wine wrapper from nothing (that still needs the manual step in
#  docs/MAC-BUILD.md, "The working recipe", or an agent). It requires that a
#  Sikarugir Wine-10 wrapper already exists with the GOG game inside its prefix.
#  It preflight-checks for exactly that and tells you what to do if it's missing.
#
#  Ships NO game content -- you bring your own GOG copy. Idempotent: safe to
#  re-run. Report what happens (works / breaks, which Mac) as a GitHub issue.
# ============================================================================
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
PFX="$APP/Contents/SharedSupport/prefix"
GAMEDIR="$PFX/drive_c/GOG Games/Interstate 76"
WINE="$APP/Contents/SharedSupport/wine/bin/wine"

say()  { printf '\n\033[1;33m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32mok\033[0m  %s\n' "$*"; }
warn() { printf '   \033[31m!!\033[0m  %s\n' "$*"; }
step() { # step "label" command...  -- run, report, keep going
  label="$1"; shift
  if "$@" >/tmp/i76-install.log 2>&1; then ok "$label"
  else warn "$label FAILED (see /tmp/i76-install.log)"; fi
}

cat <<'BANNER'

   ##  INTERSTATE '76  ->  Apple Silicon Mac  (BETA installer)
   --------------------------------------------------------------
   Finishes setup on an existing Sikarugir wrapper. No game files
   are downloaded; you must already own + have placed the GOG game.

BANNER

# ---------- Preflight: the wrapper + game must already exist ----------
say "Checking prerequisites"
missing=0
if [ ! -d "$APP" ]; then
  warn "No wrapper found at:"
  warn "  $APP"
  missing=1
fi
if [ ! -f "$GAMEDIR/i76.exe" ]; then
  warn "Game not found in the prefix (expected $GAMEDIR/i76.exe)"
  missing=1
fi
if [ "$missing" -eq 1 ]; then
  cat <<EOF

   This installer finishes an EXISTING wrapper; it can't build one from scratch.
   To create it (one-time), follow docs/MAC-BUILD.md -> "The working recipe":
     1. Get a Sikarugir Wine-10 wrapper (free) and clone it (APFS: cp -c).
     2. Unzip your GOG Interstate '76 into:
          .../prefix/drive_c/GOG Games/Interstate 76/
     3. Re-run this installer.

   Fastest path if you use AI tooling: open this repo in Claude Code and say
   "set up Interstate '76 on this Mac following docs/MAC-BUILD.md; my GOG zip
   is at ~/Downloads/i76.zip".

EOF
  exit 1
fi
ok "wrapper + game present"
[ -x "$WINE" ] || warn "wrapper wine binary not executable at $WINE (registry step may skip)"

# ---------- 1. Required Wine registry keys (idempotent) ----------
# Without the virtual desktop the game page-faults at boot; without the Mac-Driver
# float key the window vanishes on focus loss. See docs/VERIFIED-FIXES.md.
say "Applying required Wine registry keys"
if [ -x "$WINE" ]; then
  export WINEPREFIX="$PFX" WINEESYNC=1 WINEMSYNC=1 WINEDEBUG=-all
  reg() { "$WINE" reg add "$1" /v "$2" /d "$3" /f >/dev/null 2>&1; }
  step "i76.exe -> win98"            reg 'HKCU\Software\Wine\AppDefaults\i76.exe' Version win98
  step "i76.exe -> virtual desktop"  reg 'HKCU\Software\Wine\AppDefaults\i76.exe\Explorer' Desktop i76
  step "desktop i76 = 1280x960"      reg 'HKCU\Software\Wine\Explorer\Desktops' i76 1280x960
  step "float when inactive"         reg 'HKCU\Software\Wine\Mac Driver' WindowsFloatWhenInactive all
  "$APP/Contents/SharedSupport/wine/bin/wineserver" -w 2>/dev/null || true
else
  warn "skipped (no wine binary) -- set the 4 keys manually per docs/MAC-BUILD.md"
fi

# ---------- 2. Verified setup scripts, in order ----------
say "DxWnd (big 4:3 window, software renderer)"
step "install DxWnd + profile" sh "$HERE/setup-dxwnd.sh"

say "In-mission music (virtual CD audio)"
step "wire mission music" sh "$HERE/setup-music.sh"

say "Cutscene-music fix (SMACKW32 proxy)"
step "install SMACKW32 proxy" sh "$HERE/setup-cutscene-music-fix.sh"

say "Controls: known-good input map (WASD driving + mouse guns) & Mac arrows"
if [ -f "$HERE/docs/input.map.reference" ]; then
  [ -f "$GAMEDIR/input.map" ] && cp "$GAMEDIR/input.map" "$GAMEDIR/input.map.pre-install" 2>/dev/null
  if cp "$HERE/docs/input.map.reference" "$GAMEDIR/input.map"; then ok "installed known-good input.map"
  else warn "couldn't write input.map"; fi
else
  warn "docs/input.map.reference missing -- skipped"
fi
[ -f "$GAMEDIR/KEYBOARD.MAP" ] && step "Mac arrow-key fix" sh "$HERE/fix-arrows-for-mac.sh" "$GAMEDIR/KEYBOARD.MAP"

# ---------- 3. Build + install the launcher apps ----------
say "Building launcher apps"
step "build launchers" sh "$HERE/build-launchers.sh"

# ---------- Done ----------
printf '\n   \033[1;32mDone (BETA).\033[0m  Launch from:\n'
cat <<EOF
     ~/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app

   Optional next steps:
     * Restore the maintainer's shared saves:  ./setup-saves.sh
     * Edit your garage in a browser:          i76-save-editor.command
     * Tweak the DxWnd profile:                "Interstate 76 - DxWnd Settings.app"

   In-game: set Options -> Graphic Detail -> Screen Resolution -> 1024x768 once.

   This installer is BETA -- please report how it went (which Mac, what worked
   or broke) at github.com/therealjkvalentine/i76-everywhere/issues.

EOF
