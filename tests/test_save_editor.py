"""Byte-exact tests for the save editor library (i76-save-editor.py) and the browser editor's parser.

    python -m pytest tests/ -q            (or:  python tests/test_save_editor.py)

Runs over EVERY sample save: the committed sets (saves/, saves/lab-20261002 = today's player saves
copied read-only from the lab, saves/windows-20260906, saves/rescue-20260718) and, when present, the
live lab copy C:/Users/james/i76-uncap-lab/game (read-only; set I76_LAB_DIR to point elsewhere or to
"" to skip).  Rules: parse -> serialise must equal the input for every file, not one; sizes come from
the writer's formula; a written directory never shrinks; records stay 116 bytes.
"""
import glob, importlib.util, json, os, shutil, subprocess, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("i76_save_editor", os.path.join(REPO, "i76-save-editor.py"))
ed = importlib.util.module_from_spec(spec); spec.loader.exec_module(ed)

SAMPLE_DIRS = [os.path.join(REPO, "saves"), os.path.join(REPO, "saves", "lab-20261002"),
               os.path.join(REPO, "saves", "windows-20260906"), os.path.join(REPO, "saves", "rescue-20260718")]
LAB = os.environ.get("I76_LAB_DIR", "C:/Users/james/i76-uncap-lab/game")
if LAB and os.path.isdir(LAB):
    SAMPLE_DIRS.append(LAB)

def _rel(p): return os.path.relpath(p, REPO).replace("\\", "/")
CMP_FILES = sorted(p for d in SAMPLE_DIRS for p in glob.glob(os.path.join(d, "save*.cmp")) + glob.glob(os.path.join(d, "*.spc")))
DIR_FILES = sorted(p for d in SAMPLE_DIRS if os.path.isfile(p := os.path.join(d, "savegame.dir")))
# saves the 2026-07 editor wrote with its records framed 32 bytes late: their states and repair
# queue are scrambled in a way the game-written invariants do not hold for (documented in
# docs/SAVE-EDITOR-STATUS-2026-10-02.md); they still have to round-trip byte for byte.
EDITOR_TOUCHED = {"saves/save008.cmp", "saves/rescue-20260718/save004.cmp", "saves/rescue-20260718/save006.cmp",
                  "saves/rescue-20260718/save007.cmp", "saves/rescue-20260718/save008.cmp"}
LAB_FIX = os.path.join(REPO, "saves", "lab-20261002")
NODE = shutil.which("node")
NODE_TEST = os.path.join(REPO, "tools", "tests", "test-save-editor-cmp.mjs")

def _read(p):
    with open(p, "rb") as f: return f.read()

# ---------------------------------------------------------------- .cmp / .spc
@pytest.mark.parametrize("path", CMP_FILES, ids=_rel)
def test_cmp_roundtrip_byte_exact(path):
    data = _read(path)
    c = ed.Cmp(data)
    assert c.to_bytes() == data
    assert len(data) == ed.HDR_LEN + 8 + ed.REC_LEN * (len(c.a) + len(c.c))
    assert all(len(p.raw) == ed.REC_LEN for p in c.a + c.c)

@pytest.mark.parametrize("path", CMP_FILES, ids=_rel)
def test_cmp_game_invariants(path):
    c = ed.Cmp(_read(path))
    assert c.car == "Picard Piranha" and c.ident == "doarmel"
    assert all(p.type in ed.KNOWN_TYPES and p.state in ed.STATE_BADGE for p in c.a + c.c)
    assert all(p.name and p.dfl for p in c.a + c.c)
    warnings = c.check()
    if _rel(path) in EDITOR_TOUCHED:
        assert warnings, "listed as editor-touched but passes every invariant - drop it from EDITOR_TOUCHED"
    else:
        assert warnings == [], warnings

def test_frame_constants_match_the_writer():
    # the shell's Cmp_Write: GarageRec 0x8c4, PartNode 0x20 + PartRec 0x54, armor at +0x7fc, names at +0x400
    assert (ed.HDR_LEN, ed.REC_LEN, ed.G_ARMOR, ed.G_EQ) == (0x8c4, 0x74, 0x7fc, 0x400)
    assert (ed.N_COND, ed.N_STATE, ed.R_NAME, ed.R_TYPE, ed.R_CLS, ed.R_DFL, ed.R_FULL, ed.R_WT) == \
           (0x0c, 0x10, 0x20, 0x3e, 0x4e, 0x5b, 0x6c, 0x70)

def test_lab_save003_known_values():
    c = ed.Cmp.load(os.path.join(LAB_FIX, "save003.cmp"))
    assert (len(c.a), len(c.c)) == (64, 8)
    assert c.armor == [900, 600, 600, 700, 650, 400, 400, 550]
    assert c.equipped[0] == "261ci  6 cyl" and c.equipped[13] == "Structo Bmpr"
    assert c.vtf == "piranha1.vtf" and c.vdf == "vppirnha.vdf"
    first = c.a[0]
    assert (first.name, first.cond, first.state, first.full) == ("13in Stock", 19, 4, 100)   # the bytes at 0x8c8
    assert sum(1 for p in c.a if p.state == 1) == 14 == len(c.mounted())
    assert sorted(p.key() for p in c.c) == sorted(p.key() for p in c.a if p.state == 3)

def test_edit_cond_and_state_then_write(tmp_path):
    src = os.path.join(LAB_FIX, "save003.cmp"); dst = tmp_path / "save003.cmp"
    shutil.copy(src, dst)
    c = ed.Cmp.load(dst)
    orig = _read(src)
    n_queue = len(c.c)
    c.a[0].cond = 77
    van = next(p for p in c.a if p.state == 2 and p.type != 13)
    van.state = 3
    assert c.sync_repair_queue() is True
    n = ed.write_cmp(str(dst), c)
    assert n == len(orig) + ed.REC_LEN
    back = ed.Cmp.load(dst)
    assert back.a[0].cond == 77 and back.a[1].cond == c.a[1].cond            # lands on record 0, not record 1
    assert len(back.c) == n_queue + 1 and any(p.key() == van.key() for p in back.c)
    assert back.check() == []
    assert _read(str(dst) + ".pre-edit") == orig                               # one-time backup of the original
    assert glob.glob(str(dst) + ".bak-*")                                      # timestamped backup
    # a second write keeps .pre-edit as the original
    back.a[0].cond = 78; ed.write_cmp(str(dst), back)
    assert _read(str(dst) + ".pre-edit") == orig

def test_sync_repair_queue_is_identity_on_game_files():
    for p in CMP_FILES:
        if _rel(p) in EDITOR_TOUCHED: continue
        data = _read(p); c = ed.Cmp(data)
        assert c.sync_repair_queue() is False and c.to_bytes() == data, _rel(p)

def test_part_new_and_identity():
    p = ed.Part.new("50cal Turret", 7, "slg02", "tmmedium.gdf", 400, 47.0, cond=100, state=2)
    assert len(p.raw) == ed.REC_LEN
    assert (p.name, p.type, p.cls, p.dfl, p.full, p.cond, p.state) == ("50cal Turret", 7, "slg02", "tmmedium.gdf", 400, 100, 2)
    assert abs(p.wt - 47.0) < 1e-6
    with pytest.raises(ValueError): p.state = 9

# ---------------------------------------------------------------- savegame.dir
@pytest.mark.parametrize("path", DIR_FILES, ids=_rel)
def test_dir_roundtrip_byte_exact(path):
    data = _read(path)
    sd = ed.SaveDir(data)
    assert sd.to_bytes() == data
    assert not sd.short
    assert len(data) >= sd.exact_len == 4 + 60 * len(sd.records)
    for r in sd.records:
        assert r.file.startswith("save") and r.state in (1, 8) and r.flags == 0

def test_lab_dir_known_values():
    sd = ed.SaveDir.load(os.path.join(LAB_FIX, "savegame.dir"))
    assert [r.scene for r in sd.records] == [1, 2, 3, 5, 6, 6, 5, 5, 6]
    assert [r.state for r in sd.records] == [1, 1, 1, 8, 8, 8, 8, 1, 1]
    assert sd.get("save005").name == "s" and sd.get("save008").name == "Andreeeewwwwww"
    assert sd.get("save003").plays() == 5 and sd.get("save000").plays() == 2   # state 8 as-is, state 1 next

def test_dir_edit_preserves_stale_name_bytes():
    path = os.path.join(REPO, "saves", "savegame.dir")        # carries "\0eppers" after a NUL
    data = _read(path); sd = ed.SaveDir(data)
    sd.set_scene("save000", 9)
    out = sd.to_bytes()
    assert len(out) == len(data)
    diff = [i for i in range(len(data)) if data[i] != out[i]]
    assert diff == [4]                                        # only record 0's scene low byte
    assert ed.SaveDir(out).get("save000").scene == 9

def test_dir_add_remove_and_never_shrink(tmp_path):
    dst = tmp_path / "savegame.dir"
    shutil.copy(os.path.join(REPO, "saves", "savegame.dir"), dst)   # 876 B = 13 records + 92 slack
    size0 = os.path.getsize(dst)
    sd = ed.SaveDir.load(dst)
    sd.remove("save017")
    ed.write_dir(str(dst), sd)
    assert os.path.getsize(dst) == size0                             # never shrinks
    back = ed.SaveDir.load(dst)
    assert len(back.records) == 12 and back.get("save017") is None
    slot = back.free_slot(); assert slot == "save003"
    back.add(slot, 7, "CAL LABEL", state=8)
    ed.write_dir(str(dst), back)
    again = ed.SaveDir.load(dst)
    r = again.get(slot)
    assert (r.scene, r.name, r.state, r.plays()) == (7, "CAL LABEL", 8, 7)
    assert os.path.getsize(dst) >= size0

def test_dir_short_file_reads_zero_filled():
    data = _read(os.path.join(LAB_FIX, "savegame.dir"))
    sd = ed.SaveDir(data[:-10])
    assert sd.short and len(sd.records) == 9 and sd.records[-1].file == "save008"
    assert len(sd.to_bytes()) == len(data)

# ---------------------------------------------------------------- the HTML parser must match
@pytest.mark.skipif(not NODE, reason="node not installed")
def test_html_parser_lockstep_with_python():
    files = CMP_FILES + DIR_FILES
    js = json.loads(subprocess.check_output([NODE, NODE_TEST, "--json", *files], text=True))
    assert len(js) == len(files)
    for path, j in zip(files, js):
        py = json.loads(json.dumps(ed.SaveDir(_read(path)).info(os.path.basename(path), os.path.getsize(path))
                                   if path.endswith(".dir") else ed.Cmp(_read(path)).info(os.path.basename(path), os.path.getsize(path))))
        assert j.get("error") is None, (path, j.get("error"))
        if path.endswith(".dir"):
            assert j["count"] == py["count"]
            for r in py["records"]:
                assert j["records"][r["file"]] == {"scene": r["scene"], "name": r["name"], "state": r["state"]}, (path, r)
        else:
            for k in ("size", "car", "variant", "nA", "nC", "armor", "equipped"):
                assert j[k] == py[k], (path, k)
            assert j["a"] == py["a"] and j["c"] == py["c"], path

@pytest.mark.skipif(not NODE, reason="node not installed")
def test_html_parser_self_checks():
    subprocess.check_call([NODE, NODE_TEST, *CMP_FILES, *DIR_FILES], stdout=subprocess.DEVNULL)

@pytest.mark.skipif(not NODE, reason="node not installed")
def test_html_dir_functions():
    subprocess.check_call([NODE, os.path.join(REPO, "tools", "tests", "test-save-editor-dir.mjs"),
                           os.path.join(LAB_FIX, "savegame.dir")], stdout=subprocess.DEVNULL)

# ---------------------------------------------------------------- calibration staging
def test_calibration_staging(tmp_path):
    out = tmp_path / "staging"
    subprocess.check_call([sys.executable, os.path.join(REPO, "i76-calibration-saves.py"),
                           "--game", LAB_FIX, "--staging", str(out)], stdout=subprocess.DEVNULL)
    game_dir = ed.SaveDir.load(os.path.join(LAB_FIX, "savegame.dir"))
    sd = ed.SaveDir.load(out / "savegame.dir")
    assert os.path.getsize(out / "savegame.dir") == sd.exact_len               # exact, 4 + 60n
    assert [r.raw for r in sd.records[:len(game_dir.records)]] == [r.raw for r in game_dir.records]   # the game's records untouched
    new = sd.records[len(game_dir.records):]
    assert len(new) >= 7 and all((r.name.startswith("CAL") or r.name == "") and r.state in (1, 8) for r in new)
    assert sum(1 for r in new if r.name.startswith("CAL")) >= 6 and all(r.scene in (base.scene, 7) for r in new for base in [game_dir.get("save003")])
    for r in new:
        p = out / (r.file + ".cmp")
        assert p.is_file(), r.file
        data = _read(p); c = ed.Cmp(data)
        assert c.to_bytes() == data and c.check() == [], r.file
    assert (out / "CAL-MANIFEST.md").is_file()
    # staging never touches the game directory
    assert ed.SaveDir.load(os.path.join(LAB_FIX, "savegame.dir")).to_bytes() == game_dir.to_bytes()

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
