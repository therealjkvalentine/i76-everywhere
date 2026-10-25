"""Offline checks of PLAY-i76.ps1's render scale / antialiasing keys (I76_RENDER_SCALE, I76_AA).

    python -m pytest tests/test_render_keys.py -q

Starts no game: PLAY-i76.ps1 -RenderOnly applies the render step to a scratch game folder and exits.
The scratch folder holds the driver's wide conf (tools/conf/dgVoodoo.daily-wide-ss2x-2026-10-12.conf, 6880x2880 + 4x) as
dgVoodoo.wide.conf and dgVoodoo.conf, and _i76e/display.txt = 3440x1440 so the result does not depend on this PC's monitor.
docs/records/RENDER-KEYS-2026-10-25.md.
"""
import hashlib, os, re, shutil, subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LAUNCHER = os.path.join(REPO, "PLAY-i76.ps1")
TEMPLATE = os.path.join(REPO, "tools", "conf", "dgVoodoo.daily-wide-ss2x-2026-10-12.conf")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="needs Windows PowerShell")


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def glide(p):
    t = open(p, encoding="ascii").read()
    sec = t[t.index("[Glide]"):]
    sec = sec[:sec.index("[GlideExt]")]
    return (re.search(r"(?m)^Resolution\s*=\s*(\S+)", sec).group(1), re.search(r"(?m)^Antialiasing\s*=\s*(\S+)", sec).group(1))


@pytest.fixture
def game(tmp_path):
    g = tmp_path / "game"
    (g / "presets").mkdir(parents=True)
    (g / "_i76e").mkdir()
    (g / "_i76e" / "display.txt").write_text("3440x1440 scale 2\n", encoding="ascii")
    shutil.copy(TEMPLATE, g / "dgVoodoo.wide.conf")
    (g / "presets" / "rk.psd1").write_text("@{\n    Name = 'rk'\n    Summary = 'scratch'\n    Env = @{\n        I76_FAR_CLIP = '600'\n    }\n}\n", encoding="ascii")
    return g


def run(game, local=None, extra=()):
    lp = game / "presets" / "local.psd1"
    if local is None:
        if lp.exists():
            lp.unlink()
    else:
        body = "\n".join("        %s = '%s'" % kv for kv in local.items())
        lp.write_text("@{\n    Env = @{\n%s\n    }\n}\n" % body, encoding="ascii")
    shutil.copy(game / "dgVoodoo.wide.conf", game / "dgVoodoo.conf")   # what PLAY.bat does before PLAY-i76.ps1
    env = {k: v for k, v in os.environ.items() if not k.startswith("I76_")}
    r = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", LAUNCHER, "-GameDir", str(game),
                        "-Preset", str(game / "presets" / "rk.psd1"), "-RenderOnly"] + list(extra),
                       capture_output=True, text=True, env=env, timeout=120)
    return r


def test_defaults_touch_nothing(game):
    r = run(game)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "render: 2x (6880x2880), AA 4x (default" in r.stdout
    assert md5(game / "dgVoodoo.wide.conf") == md5(TEMPLATE) == md5(game / "dgVoodoo.conf")
    assert not (game / "dgVoodoo.wide.conf.pre-render-keys").exists()


def test_scale_aa_round_trip(game):
    r = run(game, {"I76_RENDER_SCALE": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "render: 1x (3440x1440), AA 4x (from local" in r.stdout
    assert glide(game / "dgVoodoo.conf") == ("3440x1440", "4x")
    assert md5(game / "dgVoodoo.wide.conf.pre-render-keys") == md5(TEMPLATE)
    # only the two [Glide] lines differ from the installed conf
    a = open(TEMPLATE, encoding="ascii").read().splitlines()
    b = open(game / "dgVoodoo.wide.conf", encoding="ascii").read().splitlines()
    assert len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1

    r = run(game, {"I76_RENDER_SCALE": "1", "I76_AA": "0"})
    assert "render: 1x (3440x1440), AA off (from local" in r.stdout
    assert glide(game / "dgVoodoo.conf") == ("3440x1440", "off")

    r = run(game, {"I76_RENDER_SCALE": "1.5", "I76_AA": "8"})
    assert glide(game / "dgVoodoo.conf") == ("5160x2160", "8x")

    r = run(game, {"I76_AA": "2"}, extra=("-RenderScale", "1"))   # the kit's --no-supersample alias wins over the key
    assert glide(game / "dgVoodoo.conf") == ("3440x1440", "2x")

    r = run(game)   # keys removed: the installed conf comes back byte for byte
    assert "the installed dgVoodoo.wide.conf put back" in r.stdout
    assert md5(game / "dgVoodoo.wide.conf") == md5(TEMPLATE) == md5(game / "dgVoodoo.conf")
    assert not (game / "dgVoodoo.wide.conf.pre-render-keys").exists()


def test_bad_values_fall_back(game):
    r = run(game, {"I76_RENDER_SCALE": "3", "I76_AA": "6"})
    assert "is not 1, 1.5 or 2 - using 2" in r.stdout and "is not 0, 2, 4 or 8 - using 4" in r.stdout
    assert md5(game / "dgVoodoo.conf") == md5(TEMPLATE)


def test_other_conf_untouched(game):
    lp = game / "presets" / "local.psd1"
    lp.write_text("@{ Env = @{ I76_RENDER_SCALE = '1' } }\n", encoding="ascii")
    other = game / "dgVoodoo.conf"
    open(other, "w", encoding="ascii").write(open(TEMPLATE, encoding="ascii").read().replace("1680x1050", "1920x1200"))
    before = md5(other)
    env = {k: v for k, v in os.environ.items() if not k.startswith("I76_")}
    r = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", LAUNCHER, "-GameDir", str(game),
                        "-Preset", str(game / "presets" / "rk.psd1"), "-RenderOnly"], capture_output=True, text=True, env=env, timeout=120)
    assert "render keys NOT applied" in r.stdout
    assert md5(other) == before and md5(game / "dgVoodoo.wide.conf") == md5(TEMPLATE)
