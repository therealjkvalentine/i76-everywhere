"""Checks for merge._resolve_synonyms (G4 word-disagreement tie-break, 2026-09-26)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from merge import _resolve_synonyms
M = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
g = lambda c, p: {"name_c": c, "name_pcode": p}
rv = lambda n, s=True: {"data": {"reconcile": {"name": n, "synonyms": s}}}
CASES = [
    (g("sound_MciClose", "sound_CloseCdAudio"), rv("sound_CloseCdAudio"), "sound_CloseCdAudio"),   # picks one of the two
    (g("sound_MciClose", "sound_CloseCdAudio"), rv("sound_StopCd"), None),                         # never a third name
    (g("sound_MciClose", "sound_CloseCdAudio"), rv("sound_CloseCdAudio", False), None),            # needs synonyms: true
    (g("bwd2_FillVehicleRecords", "entity_GetVehicleState"), rv("entity_GetVehicleState"), None),  # prefixes differ
    (g("ffb_Enable", "keep"), rv("ffb_Enable"), None),                                              # keep is no reading
    (g("math_Mat3MulVec3", "math_MatrixMulVector"), None, None),                                    # no review
]
bad = 0
for gg, r, want in CASES:
    got, how = _resolve_synonyms(M, gg, r)
    print("ok " if got == want else "BAD", gg["name_c"], gg["name_pcode"], "->", got, "|", how)
    bad += got != want
print("%d checks, %d failed" % (len(CASES), bad))
sys.exit(1 if bad else 0)
