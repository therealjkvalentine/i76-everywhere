"""Offline checks of the player settings file <game>\\i76-settings.txt (PLAY-i76.ps1, "player settings file").

    python -m pytest tests/test_settings_file.py -q

Starts no game: PLAY-i76.ps1 -WriteSettings / -DryRun / -RenderOnly on a scratch game folder.
docs/records/SETTINGS-FILE-2026-10-25.md.
"""
import os, re, shutil, subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LAUNCHER = os.path.join(REPO, "windows", "PLAY-i76.ps1")
TEMPLATE = os.path.join(REPO, "tools", "conf", "dgVoodoo.daily-wide-ss2x-2026-10-12.conf")
PRESET = os.path.join(REPO, "presets", "tick19-42.psd1")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="needs Windows PowerShell")
BANNER = "If something went wrong, attach this file to a GitHub issue: https://github.com/therealjkvalentine/i76-everywhere/issues/new/choose"


@pytest.fixture
def game(tmp_path):
    g = tmp_path / "game folder"          # a space, as in "Interstate 76"
    (g / "presets").mkdir(parents=True)
    (g / "_i76e").mkdir()
    (g / "_i76e" / "display.txt").write_text("3440x1440 scale 2\n", encoding="ascii")
    shutil.copy(PRESET, g / "presets" / "tick19-42.psd1")
    shutil.copy(TEMPLATE, g / "dgVoodoo.wide.conf")
    return g


def ps(game, *args, preset=None):
    shutil.copy(game / "dgVoodoo.wide.conf", game / "dgVoodoo.conf")   # what PLAY.bat does first
    env = {k: v for k, v in os.environ.items() if not k.startswith("I76_")}
    r = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", LAUNCHER, "-GameDir", str(game),
                        "-Preset", preset or str(game / "presets" / "tick19-42.psd1")] + list(args),
                       capture_output=True, text=True, env=env, timeout=120)
    return r


def game_env(stdout):
    """the 'environment handed to the game process' block of -DryRun"""
    block = stdout.split("environment handed to the game process", 1)[1]
    return dict(re.findall(r"(?m)^    (I76\w+)=(.*)$", block))


def write_settings(game, edits=(), extra=()):
    r = ps(game, "-WriteSettings")
    assert r.returncode == 0, r.stdout + r.stderr
    p = game / "i76-settings.txt"
    lines = p.read_text(encoding="utf-8").splitlines()
    for name, value in edits:
        hits = [i for i, l in enumerate(lines) if l == "%s = default" % name]
        assert len(hits) == 1, name
        lines[hits[0]] = "%s = %s" % (name, value)
    lines += list(extra)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")   # Notepad's UTF-8 (with BOM)
    return lines


def lineno(lines, text):
    return lines.index(text) + 1


def test_written_file_is_clean_and_changes_nothing(game):
    r = ps(game, "-WriteSettings")
    assert r.returncode == 0, r.stdout + r.stderr
    t = (game / "i76-settings.txt").read_text(encoding="utf-8")
    lines = t.splitlines()
    assert lines[1] == "# " + BANNER
    settings = [l for l in lines if l and not l.startswith("#") and not l.startswith("[")]
    assert len(settings) >= 30 and all(l.endswith(" = default") for l in settings)
    # each setting line has its allowed values and the value now in the note above it
    for i, l in enumerate(lines):
        if l in settings:
            assert lines[i - 1].startswith("# allowed: ") and "now: " in lines[i - 1], l
    assert "now: 1800 (preset tick19-42)" in t                       # draw distance from the preset
    assert "now: 2 = the 3D drawn at 6880x2880" in t                   # render scale on this display
    bat = (game / "SETTINGS.bat").read_text(encoding="ascii")
    assert "notepad.exe" in bat and "-WriteSettings" in bat
    # read back: nothing changed, nothing reported
    a = ps(game, "-DryRun"); b = ps(game, "-DryRun", "-NoSettings")
    assert "0 value(s) changed from the launcher's, 0 line(s) not understood" in a.stdout
    assert game_env(a.stdout) == game_env(b.stdout)


def test_values_apply_and_bad_lines_are_reported_by_number(game):
    lines = write_settings(game, [("field of view", "100"), ("antialiasing", "16"), ("co-op scaling", "no"),
                                  ("draw distance", "2000  # a note after the value"), ("skip mission movies", "yes")],
                           ["this is junk", "speed = fast", "I76_GLIDE_GAMMA = 1.3", "terrain detail = 1,5"])
    r = ps(game, "-DryRun")
    assert r.returncode == 0, r.stdout + r.stderr
    e = game_env(r.stdout)
    assert e["I76_FOV"] == "100" and e["I76_FAR_CLIP"] == "2000" and e["I76_COOP_SCALE"] == "0"
    assert e["I76_SKIP_CUTSCENES"] == "1" and e["I76_GLIDE_GAMMA"] == "1.3"
    assert e["I76_TERRAIN_LOD"] == "24"                                # the bad line left the preset's value
    assert "line %d: 'antialiasing = 16' - not one of off, 2, 4, 8" % lineno(lines, "antialiasing = 16") in r.stdout
    assert "line %d: 'this is junk' - not a 'name = value' line" % lineno(lines, "this is junk") in r.stdout
    assert "line %d: 'speed = fast' - no setting called 'speed'" % lineno(lines, "speed = fast") in r.stdout
    assert "line %d: 'terrain detail = 1,5' - not a number" % lineno(lines, "terrain detail = 1,5") in r.stdout
    assert "4 line(s) not understood" in r.stdout


def test_precedence_preset_settings_local_commandline(game):
    lines = write_settings(game, [("field of view", "100"), ("render scale", "1"), ("road distance", "900")])
    (game / "presets" / "local.psd1").write_text("@{\n    Env = @{\n        I76_FOV = '110'\n    }\n}\n", encoding="ascii")
    r = ps(game, "-DryRun")
    e = game_env(r.stdout)
    assert e["I76_FOV"] == "110"                                       # local.psd1 beats the file
    assert e["I76_ROAD_DIST"] == "900"                                 # the file beats the preset (1800)
    assert "local override: I76_FOV=110 (i76-settings.txt line %d said 100)" % lineno(lines, "field of view = 100") in r.stdout
    # render scale from the file is applied to the conf ...
    r = ps(game, "-RenderOnly")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "render: 1x (3440x1440), AA 4x (from i76-settings.txt line %d" % lineno(lines, "render scale = 1") in r.stdout
    # ... and the command line beats it
    r = ps(game, "-RenderOnly", "-RenderScale", "2")
    assert "render: 2x (6880x2880), AA 4x (from -RenderScale" in r.stdout


def test_launcher_options_and_command_line(game):
    write_settings(game, [("wheel force feedback", "off"), ("simulation tick", "33.333"), ("windowed", "1280x720")])
    r = ps(game, "-DryRun")
    assert "wheel force feedback = off" in r.stdout and "FFB interposer" not in r.stdout
    assert game_env(r.stdout)["I76_SIM_TICK_MS"] == "33.333"
    assert game_env(r.stdout)["I76_ASPECT"] == "1280x720"
    r = ps(game, "-DryRun", "-Ffb", "-TickMs", "41.667")
    assert "the command line says otherwise, it wins" in r.stdout and "FFB interposer" in r.stdout
    assert game_env(r.stdout)["I76_SIM_TICK_MS"] == "41.667"


def test_stock_preset_stays_stock(game):
    write_settings(game, [("field of view", "100")])
    (game / "presets" / "stock.psd1").write_text("@{\n    Name = 'stock'\n    Env = @{}\n}\n", encoding="ascii")
    r = ps(game, "-DryRun", preset="stock")
    assert "NOT applied (preset stock stays stock)" in r.stdout
    assert "I76_FOV" not in game_env(r.stdout)


def test_never_overwritten_dry_run_writes_nothing(game):
    r = ps(game, "-DryRun")
    assert not (game / "i76-settings.txt").exists() and not (game / "SETTINGS.bat").exists()
    write_settings(game, [("field of view", "100")])
    before = (game / "i76-settings.txt").read_bytes()
    r = ps(game, "-WriteSettings")
    assert "already exists" in r.stdout and (game / "i76-settings.txt").read_bytes() == before


def test_logs_start_with_the_feedback_line(game):
    (game / "mciproxy.log").write_bytes(b"old proxy line\r\n")
    for _ in range(2):
        r = ps(game, "-RenderOnly")
        assert r.returncode == 0, r.stdout + r.stderr
    m = (game / "mciproxy.log").read_bytes().decode("ascii").splitlines()
    assert m == [BANNER, "old proxy line"]
    p = (game / "play-i76.log").read_text(encoding="utf-8-sig").splitlines()
    assert p[0] == BANNER and p.count(BANNER) == 1 and len(p) > 2


def test_sim_rate_steps_per_second(game):
    for value, tick in (("20", "49.9"), ("classic", "49.9"), ("24", "41.667")):
        (game / "i76-settings.txt").unlink(missing_ok=True)
        write_settings(game, [("sim rate", value)])
        r = ps(game, "-DryRun")
        assert game_env(r.stdout)["I76_SIM_TICK_MS"] == tick, (value, r.stdout)
    text = (game / "i76-settings.txt").read_text(encoding="utf-8-sig")
    assert "# allowed: 20, 24, default." in text and "Steps per second of the game's simulation" in text
    (game / "i76-settings.txt").unlink(missing_ok=True)
    lines = write_settings(game, [("sim rate", "30")])
    r = ps(game, "-DryRun")
    assert "line %d: 'sim rate = 30'" % lineno(lines, "sim rate = 30") in r.stdout and "not one of 20, 24" in r.stdout
