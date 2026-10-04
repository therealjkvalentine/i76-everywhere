#!/bin/sh
# Build the Strlkup proxy on a Mac: Apple clang compiles (it understands the source's
# MSVC-style __asm blocks with -fasm-blocks, which mingw gcc does not), Homebrew's
# i686 mingw links. Needs: Xcode CLT, `brew install mingw-w64`.
#
#   music-fix/build-mac.sh [out.dll]      default: music-fix/Strlkup.mac.dll
#
# Never writes music-fix/Strlkup.dll - that is the committed Windows (MSVC) build the
# installers and the daily driver check by hash. Differences of this build, both
# from the source's #ifdef _MSC_VER branches: no SEH guards around the telemetry and
# trainer paths, and the UCRT (api-ms-win-crt-*, present in Wine and Windows 10+)
# instead of a static CRT. libgcc is linked statically.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$HERE/Strlkup.mac.dll}"
GCC=i686-w64-mingw32-gcc
command -v "$GCC" >/dev/null || { echo "missing $GCC - brew install mingw-w64"; exit 1; }
MWI="$(dirname "$(dirname "$("$GCC" -print-libgcc-file-name)")")"
MWI="$(cd "$MWI/../../../i686-w64-mingw32/include" && pwd)"
RD="$(clang -print-resource-dir)"
TMP="$(mktemp -d)"
clang -target i686-w64-mingw32 -fms-extensions -fasm-blocks -O2 \
      -nostdinc -isystem "$RD/include" -isystem "$MWI" -Wno-everything \
      -c "$HERE/strlkproxy.c" -o "$TMP/strlkproxy.o"
"$GCC" -m32 -s -shared -static -static-libgcc -o "$OUT" "$TMP/strlkproxy.o"
rm -rf "$TMP"
echo "built $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"
