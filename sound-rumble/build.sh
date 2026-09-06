#!/bin/sh
# Build the sound-rumble dsound.dll proxy (32-bit PE). Needs mingw-w64.
# Uses the CRT startup (threads + critical sections); still a small, import-light DLL.
set -e
cd "$(dirname "$0")"
i686-w64-mingw32-gcc -O2 -shared -nostdlib -nostartfiles \
    -o dsound.dll dsndrumble.c dsound.def \
    -Wl,-e,_DllMainCRTStartup@12 -Wl,--enable-stdcall-fixup \
    -luser32 -lkernel32
echo "built: $(pwd)/dsound.dll"
