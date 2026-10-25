"""Offline checks of tools/patch-shell-modals.py's opt-in F2 (the orphaned-bookmark fix, <re-archive> shell/FIXES.md F2).

    python -m pytest tests/test_shell_f2.py -q

Starts no game. Needs a stock i76shell.dll: $I76_SHELL, else the pristine GOG shell in ../<re-archive>/shell/bin
(deb41008); skipped when neither exists. The emulation checks need unicorn + pefile (skipped without them).
  - the default run (no --with-f2) is unchanged: F2 is not in it, the promoted M1..K4 set is;
  - --only F2 on the pristine shell changes exactly the 10 bytes at 0x10014866 and the 2-byte relocation entry of
    0x10014868 (md5 6cd6b51f = <re-archive> tools/patch_shell.py --fixes F2, cross-checked 2026-10-16);
  - the emulation passes on the patched file and fails on the stock control (the check discriminates).
"""
import hashlib, os, subprocess, sys, importlib.util

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TOOL = os.path.join(REPO, "tools", "patch-shell-modals.py")
PRISTINE_MD5 = "deb41008321cf018ba33c27bfbbfa074"
F2_MD5 = "6cd6b51f8175fd1372c12311b43c6cdc"


def _shell():
    for p in (os.environ.get("I76_SHELL"),
              os.path.join(REPO, "..", "i76-map", "shell", "bin", "i76shell.dll")):
        if p and os.path.isfile(p):
            return os.path.abspath(p)
    return None


SHELL = _shell()
needs_shell = pytest.mark.skipif(SHELL is None, reason="no stock i76shell.dll (set I76_SHELL)")


def _has_emu():
    return all(importlib.util.find_spec(m) for m in ("unicorn", "pefile"))


def _run(*args):
    return subprocess.run([sys.executable, TOOL] + list(args), capture_output=True, text=True)


def _diff(a, b):
    x, y = open(a, "rb").read(), open(b, "rb").read()
    assert len(x) == len(y)
    return [i for i in range(len(x)) if x[i] != y[i]]


@needs_shell
def test_default_set_excludes_f2(tmp_path):
    out = tmp_path / "default.dll"
    r = _run(SHELL, str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "F2" not in r.stdout
    data = open(out, "rb").read()
    assert bytes.fromhex("c705807f0510ffffffff") in data


@needs_shell
def test_only_f2_bytes(tmp_path):
    out = tmp_path / "f2.dll"
    r = _run(SHELL, str(out), "--only", "F2")
    assert r.returncode == 0, r.stdout + r.stderr
    d = _diff(SHELL, out)
    assert len(d) == 12
    assert d[:10] == list(range(0x13c66, 0x13c70))          # the 10-byte mov at 0x10014866 (file 0x13c66)
    assert d[10:] == [d[10], d[10] + 1]                     # one u16 relocation entry
    if hashlib.md5(open(SHELL, "rb").read()).hexdigest() == PRISTINE_MD5:
        assert hashlib.md5(open(out, "rb").read()).hexdigest() == F2_MD5
    again = _run(str(out), str(tmp_path / "f2-again.dll"), "--only", "F2")
    assert "nothing to do" in again.stdout


@needs_shell
@pytest.mark.skipif(not _has_emu(), reason="unicorn / pefile not installed")
def test_f2_emulation_discriminates(tmp_path):
    out = tmp_path / "f2.dll"
    assert _run(SHELL, str(out), "--with-f2").returncode == 0
    ok = _run(str(out), "--emulate", "--with-f2")
    assert ok.returncode == 0 and "mismatches=0" in ok.stdout, ok.stdout
    ctrl = _run(SHELL, "--emulate", "--only", "F2")
    assert ctrl.returncode == 1 and "mismatches=5" in ctrl.stdout, ctrl.stdout
