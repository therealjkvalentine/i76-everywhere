#!/bin/bash
# Double-click this file (the first time: right-click > Open > Open, because it is not from the App Store).
# It asks where your GOG Interstate '76 files are, then runs i76-mac-kit.sh build. README.md explains every step.
cd "$(dirname "$0")" || exit 1
pick() {   # pick "<what>" -> a POSIX path, or nothing
    local kind
    kind=$(osascript -e "button returned of (display dialog \"Where is your GOG $1?\" & return & return & \"The Windows offline installer from your GOG library (setup_...exe), or the game folder copied from a PC.\" buttons {\"Skip\", \"Game folder\", \"Installer (.exe)\"} default button 3 with title \"I'76 Mac Kit\")" 2>/dev/null) || return 0
    case "$kind" in
        "Installer (.exe)") osascript -e "POSIX path of (choose file with prompt \"The GOG $1 installer (setup_...exe)\")" 2>/dev/null ;;
        "Game folder")      osascript -e "POSIX path of (choose folder with prompt \"The GOG $1 folder\")" 2>/dev/null ;;
    esac
}
GOLD=$(pick "Interstate '76 (Gold)")
NITRO=$(pick "Interstate '76 Nitro Pack")
if [ -z "$GOLD$NITRO" ]; then echo "Nothing chosen - nothing done."; read -r -p "Press Return to close." _; exit 0; fi
ARGS=(build)
[ -n "$GOLD" ] && ARGS+=(--gold "${GOLD%/}")
[ -n "$NITRO" ] && ARGS+=(--nitro "${NITRO%/}")
for a in Gold Nitro; do
    [ -e "$HOME/Applications/Sikarugir/Interstate 76 $a.app" ] || continue
    r=$(osascript -e "button returned of (display dialog \"Interstate 76 $a.app already exists in Applications > Sikarugir. Replace it? (The old one goes to the Trash; your saves inside it go with it - copy them out first if you want them.)\" buttons {\"Stop\", \"Replace\"} default button 1 with title \"I'76 Mac Kit\")" 2>/dev/null)
    [ "$r" = Replace ] || { echo "Stopped: nothing changed."; read -r -p "Press Return to close." _; exit 0; }
    ARGS+=(--replace); break
done
bash ./i76-mac-kit.sh "${ARGS[@]}"
rc=$?
echo
[ $rc -eq 0 ] && echo "All done." || echo "The build stopped (exit $rc). The red line above says why; README.md > If something goes wrong."
read -r -p "Press Return to close this window." _
