"""Offline checks of the shipped control map and the quick reference sheet's sources.

    python -m pytest tests/test_controls.py -q

Starts no game. The consistency check is tools/controls-sheet/build_sheet.py --check: the map, the
AutoHotkey layers, the launcher's mouse-wheel defaults and controls-sheet.json must agree, and the
generated table in docs/CONTROLS.md must be current.  The lint needs an i76.exe (none is in the repo):
set I76_EXE, or it uses the lab copies when present, else that one test is skipped.
"""
import hashlib, importlib.util, os, subprocess, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHEET = os.path.join(REPO, "tools", "controls-sheet", "build_sheet.py")
MAP = os.path.join(REPO, "controls", "input.map")

spec = importlib.util.spec_from_file_location("build_sheet", SHEET)
bs = importlib.util.module_from_spec(spec); spec.loader.exec_module(bs)


def test_sources_agree():
    """The one-command check: exit 0. Known mismatches, when there are any, are named in its output."""
    r = subprocess.run([sys.executable, SHEET, "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "sources agree" in r.stdout


def test_map_is_the_recorded_file():
    """controls/README.md and docs/CONTROLS.md quote this md5; -text in .gitattributes keeps the bytes."""
    md5 = hashlib.md5(open(MAP, "rb").read()).hexdigest()
    readme = open(os.path.join(REPO, "controls", "README.md"), encoding="utf-8").read()
    assert md5 in readme, "controls/input.map changed: update the md5 in controls/README.md and rebuild the sheet"
    controls = open(os.path.join(REPO, "docs", "CONTROLS.md"), encoding="utf-8").read()
    assert md5 in controls, "docs/CONTROLS.md was generated from another map: run tools\\controls-sheet\\build.ps1"


def test_map_has_analog_sinks_and_no_native_buttons():
    blocks = bs.parse_map_text(bs.read(MAP))
    b = bs.bindings_of(blocks)
    analog = {x.action: x.analog for x in b if x.analog}
    assert analog == {"steer": ("joystick1", "Left/Right"), "throttle": ("joystick1", "Down/Up")}
    assert not [x for x in b if (x.dev or "").startswith("joystick")], "native joystick buttons double-fire with the AutoHotkey layers"


def test_checker_fails_loudly():
    """The facility is only worth having if it fails. Four ways it must."""
    M = bs.load()
    assert bs.check(M) == [], "baseline must be clean"

    M = bs.load()                                   # a key a layer sends loses its binding
    del M.by_key[("keyboard", "tab")]
    assert any("KEY NOT BOUND" in f and "Tab" in f for f in bs.check(M))

    M = bs.load()                                   # an action in the data file that the map does not have
    M.actions["warp_drive"] = {"group": "driving", "label": "Warp", "key": "Warp"}
    assert any("warp_drive" in f for f in bs.check(M))

    M = bs.load()                                   # two actions on one key, not allow-listed
    M.bindings.append(bs.Binding("honk_horn", [["+", "keyboard", "Q"]]))
    assert any("share" in f for f in bs.check(M))

    M = bs.load()                                   # the data file disagrees with the parsed .ahk
    M.remap["gWheelBase"]["3"] = "g"
    assert any("wheel 3" in f and "meant to be" in f for f in bs.check(M))

    M = bs.load()                                   # a known mismatch that is no longer one must be removed
    M.known["gamepad:B(tap):C"] = "Pad B sends 'C' (fixed 2026-10-03: it sends Tab)"
    assert any("no longer finds" in f for f in bs.check(M))

    M = bs.load()                                   # an unbound key that IS listed is tolerated, and recorded
    del M.by_key[("keyboard", "tab")]
    M.known.update({"gamepad:B(tap):Tab": "x", "wheel:3:Tab": "x", "mouse:WheelUp:Tab": "x"})
    assert bs.check(M) == [] and "gamepad:B(tap):Tab" in M.mismatches


def _exe():
    for p in (os.environ.get("I76_EXE"), os.path.join(REPO, "..", "i76-uncap-lab", "game", "i76.exe"),
              os.path.join(REPO, "..", "i76-uncap-lab", "game-gogtest", "gog-extract", "app", "i76.exe")):
        if p and os.path.isfile(p):
            return p


def test_shipped_map_lints_clean():
    exe = _exe()
    if not exe:
        pytest.skip("no i76.exe available (set I76_EXE)")
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "lint-input-map.py"), MAP, exe],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
