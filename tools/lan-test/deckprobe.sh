#!/bin/bash
# deckprobe.sh args... : run i76probe3.exe inside the Deck game's Proton prefix / wineserver (GE-Proton10-12)
W=$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton10-12/files/bin/wine
export WINEPREFIX=$HOME/.local/share/Steam/steamapps/compatdata/2731345568/pfx WINEDEBUG=-all WINEFSYNC=1 WINEESYNC=1
cd $HOME/Games/Interstate76/lan-test-20261018 && "$W" ./i76probe3.exe "$@" 2>&1 | tr -d '\r' | grep -v -E "fsync|esync|ERROR: ld.so"
