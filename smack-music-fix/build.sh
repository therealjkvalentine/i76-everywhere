#!/bin/sh
# Build the SMACKW32 proxy (32-bit PE, freestanding - no CRT imports).
# Needs: brew install mingw-w64
set -e
cd "$(dirname "$0")"
i686-w64-mingw32-gcc -O2 -shared -nostdlib -nostartfiles \
    -o SMACKW32.DLL smackproxy.c smackw32.def \
    -Wl,-e,_DllMainCRTStartup@12 -Wl,--enable-stdcall-fixup \
    -lwinmm -lkernel32
echo "built: $(pwd)/SMACKW32.DLL"
