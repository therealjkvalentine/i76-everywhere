#!/bin/sh
# Build the fake i7_SFRCE.DLL (32-bit PE, freestanding - no CRT imports).
# Needs: brew install mingw-w64   (same toolchain as ../smack-music-fix)
set -e
cd "$(dirname "$0")"
i686-w64-mingw32-gcc -O2 -shared -nostdlib -nostartfiles \
    -o I7_SFRCE.DLL i7ffshim.c i7_sfrce.def \
    -Wl,-e,_DllMainCRTStartup@12 -Wl,--enable-stdcall-fixup \
    -luser32 -lkernel32
echo "built: $(pwd)/I7_SFRCE.DLL"
