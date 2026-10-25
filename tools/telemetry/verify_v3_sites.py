#!/usr/bin/env python3
"""verify_v3_sites.py - static check of every exe site the i76tel v3 hooks patch (music-fix/strlkproxy.c,
I76_SOUND_EVENTS / I76_DAMAGE_EVENTS), against one or more i76.exe images. Read-only.

  python verify_v3_sites.py [exe ...]

Default images: the pristine GOG exe (md5 9a232dcc) and the lab twin of the daily driver. For every site it prints
the expected bytes, what the image holds, and the disassembly, and exits 1 if any site differs in any image. The
expected bytes here are the same arrays strlkproxy.c hands to patch_bytes / tel_detour (keep the two in step).
"""
import hashlib, os, struct, sys
from exedis import PE, disasm

DEFAULT = [(__import__("os").path.expanduser("~") + r"\i76-map\sandbox-gog\main\app\i76.exe"),
           (__import__("os").path.expanduser("~") + r"\i76-uncap-lab\game-dd-20261003\Interstate 76\i76.exe")]


def call(site, target):
    return bytes([0xE8]) + struct.pack("<i", target - (site + 5))


SITES = [
    # (va, expected bytes, what)
    (0x004220c0, bytes.fromhex("a1e8d74e0053"), "sound_StartVoice entry: mov eax,[0x4ed7e8]; push ebx (6, detour)"),
    (0x00422d20, bytes.fromhex("568b742408"), "sound_StopVoice (park / evict) entry: push esi; mov esi,[esp+8] (5, detour)"),
    (0x00425ef0, bytes.fromhex("81ec14020000"), "sound voice release entry: sub esp,0x214 (6, detour)"),
    (0x0042150b, call(0x0042150b, 0x00422540), "per-frame update: voice ended (failed restart), call 0x422540 (5, repoint)"),
    (0x004215a2, call(0x004215a2, 0x00422540), "per-frame update: voice ended (buffer stopped), call 0x422540 (5, repoint)"),
    (0x00463a80, bytes.fromhex("81ecc0000000"), "entity_DamageAndKill entry: sub esp,0xc0 (6, detour)"),
    (0x004a5dff, call(0x004a5dff, 0x004250f0), "weapon cycle click, call 0x4250f0 (5, repoint)"),
    (0x004a6333, call(0x004a6333, 0x004250f0), "weapon link click, call 0x4250f0 (5, repoint)"),
    (0x004a6021, call(0x004a6021, 0x004250f0), "weapon unlink click, call 0x4250f0 (5, repoint)"),
]

# read-only addresses the v3 frame fields and hooks depend on (constants checked by value)
CONSTS = [
    (0x004bd1e0, struct.pack("<f", 7.84), "lateral grip limit per unit grip (0x43cee0 fmul)"),
    (0x004be1c8, struct.pack("<f", 0.8), "DamageAndKill top threshold"),
    (0x004be1cc, struct.pack("<f", 0.707), "DamageAndKill side / zone threshold"),
    (0x004be1d0, struct.pack("<f", -0.707), "DamageAndKill side / zone threshold (negative)"),
    (0x00438c64, bytes.fromhex("d99618010000"), "physics_InitEntity: fst [esi+0x118] (wheelbase)"),
    (0x00438c72, bytes.fromhex("d99e10010000"), "physics_InitEntity: fstp [esi+0x110] (steer gain)"),
    (0x00438c01, bytes.fromhex("d99e14010000"), "physics_InitEntity: fstp [esi+0x114] (front track)"),
    (0x004f77a4, struct.pack("<I", 0x00463a80), "class damage-handler table slot -> entity_DamageAndKill"),
]


def main():
    exes = sys.argv[1:] or DEFAULT
    bad = 0
    for path in exes:
        if not os.path.exists(path):
            print("MISSING %s" % path)
            bad += 1
            continue
        pe = PE(path)
        print("== %s  md5 %s" % (path, hashlib.md5(pe.d).hexdigest()))
        for va, want, what in SITES + CONSTS:
            got = pe.read(va, len(want))
            ok = got == want
            bad += not ok
            print("  %s 0x%08x %-44s %s" % ("ok  " if ok else "DIFF", va, got.hex(), what))
            if not ok:
                print("        expected %s" % want.hex())
            if (va, want, what) in SITES:
                for line in disasm(pe, va, 12)[:2]:
                    print("        " + line)
    print("RESULT: %s" % ("all sites match" if not bad else "%d mismatches" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
