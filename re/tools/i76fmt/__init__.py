"""i76fmt - parsers and serialisers for Interstate '76 (GOG 2017 Gold) game-data formats.

Ported by Task 8 (t8-agent-loop) from recon-2026-09-04\\recon\\formats\\{lzo.py, zfs_parse.py, zfs_extract.py,
bwd2_walk.py, bwd2_nested.py} and the layouts measured in that directory's REPORT.md. Every module exposes
parse(bytes) -> object and serialise(object) -> bytes; gate R (method doc 4.3) is parse -> serialise -> parse
over the full corpus with 0 byte diffs (tools\\i76fmt\\roundtrip.py -> status\\roundtrip.json).

Modules: lzo (LZO1X/LZO1Y decode, LZO 1.00 stream), zfs (ZFSF v1 directory, payload decode, byte-exact
serialise, stored-mode method-0 repack), bwd2 (tagged chunk container; nested xDEF groups), ter (128x128 u16
tiles), images (.map, .vqm, .cbk), fnt ("1." bitmap fonts), frc (RIFF FORC force-feedback files).
Nothing here reads the executable; all offsets are file offsets (class `file`).
"""
from . import lzo, zfs, bwd2, ter, images, fnt, frc  # noqa: F401
__all__ = ["lzo", "zfs", "bwd2", "ter", "images", "fnt", "frc"]
__version__ = "0.1.0"
