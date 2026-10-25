#!/bin/bash
# build-stubs.sh [OUTDIR] - MAINTAINER, on a Mac with the Xcode command line tools: build the I'76 Mac Kit's launch stubs
# (the apps' Contents/MacOS/Sikarugir) from this repo's sources and give each its FIXED Mach-O UUID.
#
#   gold-arm64    i76-launch-stub.swift      -target arm64-apple-macos11      UUID 6ED7F4D1-5229-3D03-9757-1DA26C62501A
#   nitro-arm64   i76-nitro-app-stub.swift   -target arm64-apple-macos11      UUID 03B81E57-0956-3BBA-8D89-3C8EDF8713C4
#   gold-x86_64   i76-launch-stub.swift      -target x86_64-apple-macos13  UUID 9C1E5A4B-76A1-4D7E-9E3B-1976A11D0601
#   nitro-x86_64  i76-nitro-app-stub.swift   -target x86_64-apple-macos13  UUID 9C1E5A4B-76A1-4D7E-9E3B-1976A11D0602
#
# Why fixed UUIDs (docs/records/NITRO-MAC-2026-10-21.md s.8): macOS Local Network privacy remembers an app's permission by
# the Mach-O UUID of its main executable, and every swiftc build gets a new one. A user who answered "Allow" once would be
# asked again after every kit rebuild, and until then the game's LAN unicasts are dropped (sessions list, joins stall).
# The two arm64 UUIDs are the ones the family Macs' apps carry (Gold 565c4bd9, Nitro 384a0f8e / e61e4e57). The x86_64
# ones are new (no Intel Mac has run these apps). minos 11 (x86_64: 13, the lowest this SDK links for Intel; Sikarugir itself needs 14.6): a minos-26 build was refused on macOS 15.5
# (LaunchServices -10825, NITRO-MAC s.1).
# Then ad-hoc signed (codesign -s -). Writes OUTDIR/Sikarugir-<name> and OUTDIR/STUBS.md5; commit them to tools/mac-kit/stubs.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$REPO/tools/mac-kit/stubs}"
mkdir -p "$OUT"
setuuid() {   # setuuid <thin 64-bit Mach-O> <UUID with dashes>: overwrite LC_UUID (0x1b)
    perl -e '
        my ($f, $u) = @ARGV; $u =~ s/-//g; length($u) == 32 or die "bad uuid\n";
        open(my $h, "+<:raw", $f) or die "$f: $!\n"; local $/; my $b = <$h>;
        unpack("V", substr($b, 0, 4)) == 0xfeedfacf or die "$f: not a thin 64-bit Mach-O\n";
        my $n = unpack("V", substr($b, 16, 4)); my $o = 32;
        for (1 .. $n) { my ($c, $s) = unpack("VV", substr($b, $o, 8));
            if ($c == 0x1b) { seek($h, $o + 8, 0); print $h pack("H32", $u); close $h; exit 0 } $o += $s }
        die "$f: no LC_UUID\n";' "$1" "$2"
}
build() {   # build <name> <source> <target> <uuid>
    local f="$OUT/Sikarugir-$1"
    rm -f "$f"
    swiftc -O -target "$3" -o "$f" "$REPO/$2"
    setuuid "$f" "$4"
    codesign -f -s - "$f" 2>/dev/null
    printf '%-14s %s  %s\n' "$1" "$(md5 -q "$f")" "$(dwarfdump --uuid "$f" | awk '{print $2}')"
}
build gold-arm64   i76-launch-stub.swift    arm64-apple-macos11     6ED7F4D1-5229-3D03-9757-1DA26C62501A
build nitro-arm64  i76-nitro-app-stub.swift arm64-apple-macos11     03B81E57-0956-3BBA-8D89-3C8EDF8713C4
build gold-x86_64  i76-launch-stub.swift    x86_64-apple-macos13 9C1E5A4B-76A1-4D7E-9E3B-1976A11D0601
build nitro-x86_64 i76-nitro-app-stub.swift x86_64-apple-macos13 9C1E5A4B-76A1-4D7E-9E3B-1976A11D0602
( cd "$OUT" && md5 -r Sikarugir-* > STUBS.md5 )
echo "built from $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?'): $OUT"
