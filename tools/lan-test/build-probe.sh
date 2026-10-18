#!/bin/bash
# build-probe.sh [outdir] : build tools/wine-probe/i76probe.c with MSVC 2019 x86 (Build Tools) -> outdir/i76probe.exe
here=$(cd "$(dirname "$0")" && pwd); out=${1:-$here/build}; mkdir -p "$out"; cp "$here/../wine-probe/i76probe.c" "$out/"
rm -f "$out/i76probe.exe"; w=$(cygpath -w "$out")
powershell.exe -NoProfile -Command "Set-Location '$w'; cmd /c '\"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars32.bat\" >nul 2>nul && cl /nologo /O2 i76probe.c user32.lib gdi32.lib' | Select-Object -Last 2"
md5sum "$out/i76probe.exe"
