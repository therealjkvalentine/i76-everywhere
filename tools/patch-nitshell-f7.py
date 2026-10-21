"""patch-nitshell-f7.py - shell fix F7 for the Nitro Pack's NITSHELL.DLL (f804f50d): Enter / Space close its OK popups.

    python tools/patch-nitshell-f7.py <in nitshell.dll> <out nitshell.dll> [--no-modal-ok] [--emulate]
    python tools/patch-nitshell-f7.py <nitshell.dll> --emulate

The same patch as tools/patch-shell-f7.py (Gold's i76shell.dll), run with NITSHELL's addresses (nitro-port lane 2026-10-21,
docs/records/NITRO-PORT-2026-10-21.md s.7). Read side by side with Gold's shell: NITSHELL carries the same modal family, the
loops byte-identical but for addresses -
  Modal_Ok        (Gold loop 0x1000b789)  NITSHELL top 0x1002257a, `cmp eax,1 ; jne top` at 0x10022590, hit test 0x10022595,
                                          close 0x100225c2 (hit rect 0x76..0xa1 x 0x3c..0x4b, OK drawn at 0x13e,0x76: as Gold)
  Modal_ImageOk   (Gold loop 0x1000b900)  NITSHELL top 0x100226f0, hook 0x10022706, hit 0x1002270b, close 0x10022736
  KeyInput_Poll   (Gold 0x1001c110)       NITSHELL 0x1000ae30 (same prologue); its object [0x1013047c] (all 10 callers load it)
Caves in the .text raw slack (VirtualSize 0x38635, raw 0x38800): 0x10039640 and 0x10039680 (61 bytes each); .text
VirtualSize -> 0x38700. Every check of the Gold script applies: the file must hold exactly the expected original bytes at
each hook and zeros in each cave (or exactly the F7 bytes: then nothing is written), no base relocation may fall in a patched
range, and the output is read back and diffed. Owner rule 2026-10-21: Nitro's menu data is fragile - nothing is patched on
any mismatch.
"""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('f7', os.path.join(HERE, 'patch-shell-f7.py'))
f7 = importlib.util.module_from_spec(spec); spec.loader.exec_module(f7)

f7.KEYOBJ = 0x1013047c
f7.KEYPOLL = 0x1000ae30
f7.SITES = [
    ('Modal_ImageOk', 0x10022706, 0x100226f0, 0x1002270b, 0x10022736, 0x10039680),
    ('Modal_Ok',      0x10022590, 0x1002257a, 0x10022595, 0x100225c2, 0x10039640),
]
f7.TEXT_VS_OFF = 0x1c0
f7.TEXT_VS_OLD, f7.TEXT_VS_NEW = 0x38635, 0x38700
f7.IMG_MAP = 0x180000                        # NITSHELL's image is 0x184ac0 long; KeyInput's object lives at 0x1013047c
f7.__doc__ = __doc__

if __name__ == '__main__':
    f7.main()
