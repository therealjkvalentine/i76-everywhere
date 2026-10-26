"""Offline checks of presets/*.psd1 and of PLAY-i76.ps1's preset guard.

    python -m pytest tests/test_presets.py -q

Starts no game. The guard rules (PLAY-i76.ps1, "preset guard"):
  - I76_TERRAIN_LOD > 1 without I76_FAR_CLIP is REFUSED: more terrain detail overruns the stock transformed-vertex
    pool in binoculars (exe+0x919B1, 3 of 3 batches on t05; only I76_FAR_CLIP enlarges the pools;
    ../<lab>/docs/RENDER-FREEZE-2026-10-04.md section 4).
  - I76_COLL_WINDOW without I76_FIXED_STEP is WARNED about: the proxy's apply_coll_window() needs the fixed step and
    patches nothing without it (music-fix/strlkproxy.c, "coll-window: needs I76_FIXED_STEP").
The first test applies both rules to every shipped preset; the launcher tests run PLAY-i76.ps1 -DryRun (exits before
anything starts) against scratch presets and are skipped where Windows PowerShell is not available.
"""
import os, re, shutil, subprocess, glob

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LAUNCHER = os.path.join(REPO, "windows", "PLAY-i76.ps1")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")

ENV_LINE = re.compile(r"^\s*(I76_[A-Z0-9_]+)\s*=\s*'([^']*)'", re.M)


def preset_env(path):
    """The I76_* = '<value>' lines of a preset's Env block (comments stripped first)."""
    text = open(path, encoding="utf-8-sig").read()
    text = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    return dict(ENV_LINE.findall(text))


def guard_problems(env):
    """(refusals, warnings) for one environment, the same rules as PLAY-i76.ps1."""
    refuse, warn = [], []
    try:
        lod = int(env.get("I76_TERRAIN_LOD", "0"))
    except ValueError:
        lod = 0
    if lod > 1 and not env.get("I76_FAR_CLIP"):
        refuse.append("I76_TERRAIN_LOD=%d without I76_FAR_CLIP" % lod)
    cw = env.get("I76_COLL_WINDOW", "")
    if cw and cw != "0" and not env.get("I76_FIXED_STEP"):
        warn.append("I76_COLL_WINDOW=%s without I76_FIXED_STEP" % cw)
    return refuse, warn


PRESETS = sorted(glob.glob(os.path.join(REPO, "shared", "presets", "*.psd1")))


@pytest.mark.parametrize("path", PRESETS, ids=[os.path.basename(p) for p in PRESETS])
def test_shipped_preset_passes_guard(path):
    env = preset_env(path)
    assert env or os.path.basename(path) == "stock.psd1", "no I76_* lines parsed from %s" % path
    refuse, warn = guard_problems(env)
    assert not refuse, "%s: %s" % (os.path.basename(path), refuse)
    assert not warn, "%s: %s" % (os.path.basename(path), warn)


def test_rules_themselves():
    assert guard_problems({"I76_TERRAIN_LOD": "8"})[0]
    assert not guard_problems({"I76_TERRAIN_LOD": "8", "I76_FAR_CLIP": "1200"})[0]
    assert not guard_problems({"I76_TERRAIN_LOD": "1"})[0]
    assert guard_problems({"I76_COLL_WINDOW": "2"})[1]
    assert not guard_problems({"I76_COLL_WINDOW": "2", "I76_FIXED_STEP": "24"})[1]


def run_dry(tmp_path, env_lines):
    preset = tmp_path / "guardtest.psd1"
    body = "\n".join("        %s = '%s'" % kv for kv in env_lines)
    preset.write_text("@{\n    Name = 'guardtest'\n    Summary = 'scratch'\n    Env = @{\n%s\n    }\n}\n" % body,
                      encoding="ascii")
    game = tmp_path / "game"
    game.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("I76_")}
    return subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", LAUNCHER,
                           "-GameDir", str(game), "-Preset", str(preset), "-DryRun"],
                          capture_output=True, text=True, env=env, timeout=120)


@pytest.mark.skipif(not POWERSHELL, reason="no PowerShell on this machine")
def test_launcher_refuses_terrain_lod_without_far_clip(tmp_path):
    r = run_dry(tmp_path, [("I76_FIXED_STEP", "24"), ("I76_TERRAIN_LOD", "8")])
    assert r.returncode == 3, r.stdout + r.stderr
    assert "REFUSED" in r.stdout and "I76_FAR_CLIP" in r.stdout
    assert "DRY RUN" not in r.stdout


@pytest.mark.skipif(not POWERSHELL, reason="no PowerShell on this machine")
def test_launcher_warns_coll_window_without_fixed_step(tmp_path):
    r = run_dry(tmp_path, [("I76_COLL_WINDOW", "2")])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "I76_COLL_WINDOW=2 without I76_FIXED_STEP" in r.stdout
    assert "DRY RUN" in r.stdout


@pytest.mark.skipif(not POWERSHELL, reason="no PowerShell on this machine")
def test_launcher_dry_run_of_a_good_preset(tmp_path):
    r = run_dry(tmp_path, [("I76_FIXED_STEP", "24"), ("I76_FAR_CLIP", "1800"), ("I76_TERRAIN_LOD", "8"),
                           ("I76_COLL_WINDOW", "2")])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "REFUSED" not in r.stdout and "WARNING: I76_COLL_WINDOW" not in r.stdout
    assert "DRY RUN" in r.stdout and "I76_TERRAIN_LOD=8" in r.stdout


@pytest.mark.skipif(not POWERSHELL, reason="no PowerShell on this machine")
@pytest.mark.parametrize("name", ["best-wide", "best-wide-balanced", "best-120"])
def test_launcher_dry_run_of_the_driver_presets(tmp_path, name):
    game = tmp_path / "game"
    game.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("I76_")}
    r = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", LAUNCHER,
                        "-GameDir", str(game), "-Preset", name, "-DryRun"],
                       capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DRY RUN" in r.stdout and "REFUSED" not in r.stdout
