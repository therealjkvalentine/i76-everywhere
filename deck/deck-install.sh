#!/bin/bash
# Interstate '76 -> Steam Deck: the "stupid easy" installer (BETA).
# Pattern: NonSteamLaunchers/EmuDeck bootstrapper - zenity-guided, idempotent,
# self-updating (fetches the repo fresh each run). See docs/STEAMDECK.md.
#
# What the end user does:  (1) buy I76 on GOG + download the *offline installer*
# to ~/Downloads   (2) run this (double-click Install-I76.desktop, or the curl
# one-liner)   (3) play from Game Mode. Everything else is automated, including
# the controller config (zero taps - SRM configset mechanism).
#
# Legal: this script downloads NO game content. It extracts the GOG installer
# THE USER downloaded with their own account. dgVoodoo is fetched from the
# public archive.org mirror at install time (not redistributed by this repo).
set -u
REPO_RAW="https://raw.githubusercontent.com/therealjkvalentine/i76-everywhere/main"
WORK="$HOME/.cache/i76-deck-install"
INSTALL="$HOME/Games/Interstate76"
GAME="$INSTALL/game"
Z() { zenity "$@" --title "Interstate '76 installer" 2>/dev/null; }
info() { echo "[i76] $*"; }
die() { Z --error --text "$1" || true; echo "[i76] FATAL: $1"; exit 1; }
have_zenity=1; command -v zenity >/dev/null || have_zenity=0
[ $have_zenity -eq 0 ] && Z() { shift; echo "[i76-dialog] $*"; }

mkdir -p "$WORK" "$INSTALL"

# ---------- 0. fetch the repo payload (configs, scripts, artwork) ----------
info "fetching latest port files..."
for f in add-to-steam.py controller_neptune_i76.vdf controller_neptune_i76_opt2.vdf \
         first-launch-fix.sh; do
  curl -fsSL "$REPO_RAW/deck/$f" -o "$WORK/$f" || die "network: couldn't fetch $f"
done
curl -fsSL "$REPO_RAW/dgVoodoo.conf" -o "$WORK/dgVoodoo.conf" || die "couldn't fetch dgVoodoo.conf"
mkdir -p "$WORK/artwork"
for a in capsule_p header hero logo icon; do
  curl -fsSL "$REPO_RAW/deck/artwork/authentic/$a.png" -o "$WORK/artwork/$a.png" \
    || curl -fsSL "$REPO_RAW/deck/artwork/$a.png" -o "$WORK/artwork/$a.png" || true
done

# ---------- 1. game files ----------
if [ -f "$GAME/i76.exe" ]; then
  info "game already present at $GAME"
else
  SETUP=$(ls "$HOME"/Downloads/setup_*nterstate*76*.exe 2>/dev/null | head -1)
  if [ -z "${SETUP:-}" ]; then
    Z --info --text "Select your GOG Interstate '76 offline installer (setup_interstate_76...exe).\n\nDon't have it? Buy the game on GOG.com and download the OFFLINE installer from your library first." || true
    SETUP=$(zenity --file-selection --file-filter='GOG installer | *.exe' --filename="$HOME/Downloads/" 2>/dev/null) || die "No GOG installer selected. Download it from your GOG library to ~/Downloads and re-run."
  fi
  info "extracting $SETUP ..."
  # static innoextract (zlib license) fetched at install time
  if [ ! -x "$WORK/innoextract" ]; then
    curl -fsSL "https://constexpr.org/innoextract/files/innoextract-1.9/innoextract-1.9-linux.tar.xz" -o "$WORK/ie.tar.xz" \
      && tar -xJf "$WORK/ie.tar.xz" -C "$WORK" --strip-components=2 --wildcards '*/bin/amd64/innoextract' 2>/dev/null \
      || tar -xJf "$WORK/ie.tar.xz" -C "$WORK" --strip-components=1 2>/dev/null || true
    IE=$(find "$WORK" -name innoextract -type f | head -1); [ -n "$IE" ] && cp "$IE" "$WORK/innoextract" && chmod +x "$WORK/innoextract"
  fi
  [ -x "$WORK/innoextract" ] || die "innoextract unavailable. Fallback: add the setup exe to Steam as a non-Steam game, run it once with Proton, then re-run this installer."
  mkdir -p "$WORK/extract"
  "$WORK/innoextract" --gog -d "$WORK/extract" "$SETUP" || die "Extraction failed (GOG may have re-packed with a newer Inno Setup than innoextract 1.9 supports). Fallback: run the setup exe once via Proton, then re-run this installer."
  SRC=$(dirname "$(find "$WORK/extract" -iname 'i76.exe' | head -1)")
  [ -n "$SRC" ] || die "i76.exe not found in the extracted installer"
  mkdir -p "$GAME"; cp -a "$SRC/." "$GAME/"
  info "game extracted to $GAME"
fi

# ---------- 2. dgVoodoo 2.78.2 Glide wrapper (public mirror, install-time) ----------
if [ ! -f "$GAME/Glide2x.dll" ] || [ "$(stat -c%s "$GAME/Glide2x.dll" 2>/dev/null)" -gt 300000 ]; then
  info "fetching dgVoodoo 2.78.2 ..."
  curl -fsSL "https://archive.org/download/dgvoodoo2_78_2_202205/dgVoodoo2_78_2.zip" -o "$WORK/dgv.zip" \
    && python3 -c "
import zipfile
z=zipfile.ZipFile('$WORK/dgv.zip')
m=[n for n in z.namelist() if n.lower().endswith('3dfx/x86/glide2x.dll')]
open('$GAME/Glide2x.dll','wb').write(z.read(m[0]))
print('Glide2x.dll installed')" || info "WARNING: dgVoodoo fetch failed - drop 3Dfx/x86/Glide2x.dll into $GAME manually"
fi

# ---------- 3. configs ----------
cp "$WORK/dgVoodoo.conf" "$GAME/dgVoodoo.conf"
python3 - "$GAME/dgVoodoo.conf" <<'PY'
import re,sys
f=sys.argv[1]; t=open(f).read()
t=re.sub(r'FullScreenMode\s*=\s*\w+.*','FullScreenMode                       = true', t)
t=re.sub(r'ScalingMode\s*=\s*\S+.*','ScalingMode                          = stretched', t)
t=re.sub(r'Resolution\s*=\s*\S+.*','Resolution                           = 1280x800', t)
open(f,'w').write(t)
PY
printf 'dxvk.enableAsync = true\n' > "$GAME/dxvk.conf"
# input.map: Deck bindings (joystick1, no mouse-analog, glance on both arrow flavors)
python3 - "$GAME/input.map" <<'PY' 2>/dev/null || echo "[i76] input.map not present yet (generated on first launch) - re-run installer after one launch to patch it"
import re,sys
p=sys.argv[1]; t=open(p).read()
t=t.replace("joystick5","joystick1")
t=re.sub(r"steer \{[^}]*\}","steer {\n   - joystick1  Left/Right\n}",t,count=1)
t=re.sub(r"throttle \{[^}]*\}","throttle {\n   - joystick1  Down/Up\n}",t,count=1)
if "Deck: glance also on Grey" not in t:
    t=t.rstrip()+"""

# --- Deck: glance also on Grey* arrows ---
pilot_glance_up {\n   + keyboard   GreyUpArrow\n   - keyboard   Shift\n}
pilot_glance_down {\n   + keyboard   GreyDownArrow\n   - keyboard   Shift\n}
pilot_glance_left {\n   + keyboard   GreyLeftArrow\n   - keyboard   Shift\n}
pilot_glance_right {\n   + keyboard   GreyRightArrow\n   - keyboard   Shift\n}
"""
open(p,"w").write(t)
print("input.map patched for Deck")
PY

# ---------- 4. GE-Proton (detect, else fetch latest) ----------
CT="$HOME/.steam/steam/compatibilitytools.d"; mkdir -p "$CT"
if ! ls -d "$CT"/GE-Proton* >/dev/null 2>&1; then
  info "no GE-Proton found - downloading latest (NSL pattern)..."
  URL=$(curl -fsSL https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest | python3 -c "import json,sys; r=json.load(sys.stdin); print([a['browser_download_url'] for a in r['assets'] if a['name'].endswith('.tar.gz')][0])" 2>/dev/null)
  [ -n "${URL:-}" ] && curl -fsSL "$URL" -o "$WORK/ge.tgz" && tar -xzf "$WORK/ge.tgz" -C "$CT" && info "GE-Proton installed" || info "WARNING: GE-Proton fetch failed - Proton Experimental will be used"
fi

# ---------- 5. controller templates ----------
mkdir -p "$HOME/.steam/steam/controller_base/templates"
cp "$WORK/controller_neptune_i76.vdf" "$HOME/.steam/steam/controller_base/templates/"
cp "$WORK/controller_neptune_i76_opt2.vdf" "$HOME/.steam/steam/controller_base/templates/" 2>/dev/null || true

# ---------- 6. Steam shortcut + artwork + compat + ZERO-TAP controller config ----------
Z --question --text "Steam needs to restart to add the game to your library.\n\nClose any running game first. Continue?" || die "cancelled before Steam restart"
"$HOME/.local/share/Steam/steam.sh" -shutdown >/dev/null 2>&1 &
for i in $(seq 1 40); do pgrep -x steam >/dev/null || break; sleep 1; done; sleep 2
mkdir -p "$WORK/bundle/artwork" "$WORK/bundle/config"
cp "$WORK/artwork/"*.png "$WORK/bundle/artwork/" 2>/dev/null || true
cp "$WORK/controller_neptune_i76.vdf" "$WORK/bundle/config/"
# add-to-steam.py resolves artwork/config relative to its OWN parent dir -> run the copy
cp "$WORK/add-to-steam.py" "$WORK/bundle/config/add-to-steam.py"
python3 "$WORK/bundle/config/add-to-steam.py" || die "Steam registration failed (see terminal)"
# relaunch Steam
( setsid steam >/dev/null 2>&1 & ) || true

Z --info --text "Done!\n\n1. Find 'Interstate 76' in your library (Non-Steam).\n2. Launch from GAME MODE (Desktop Mode has window-focus quirks).\n3. Set QAM > Performance > Framerate Limit = 20 (physics!).\n4. First launch builds the Proton prefix (a minute); if it misbehaves, run first-launch-fix.sh and see docs/STEAMDECK.md.\n\nThe controller layout is pre-applied. Have fun on the interstate." || true
info "install complete"
