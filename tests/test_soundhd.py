"""Offline tests of the HD sound pack tool (tools/soundhd). Starts no game, touches no game folder.

    tools\\soundhd\\.venv\\Scripts\\python -m pytest tests/test_soundhd.py -q

install/uninstall run only against a temporary FAKE game folder (dummy I76.ZFS); the real allowed roots are
checked to refuse that folder, the daily driver and the pristine copy. Tests needing pyloudnorm skip without it;
tests needing the extracted stock corpus (tools/soundhd/out/work/stock) skip when it is absent.
"""
import hashlib, json, os, struct, sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SH = os.path.join(REPO, "tools", "soundhd")
sys.path.insert(0, SH)

import sh_dsp as D  # noqa: E402
import sh_install  # noqa: E402
import sh_wav  # noqa: E402

STOCK = os.path.join(SH, "out", "work", "stock")
PACK = os.path.join(SH, "out", "pack-v1")


def md5(b):
    return hashlib.md5(b).hexdigest()


# ------------------------------------------------------------------------------------------------ formats
def stock_header(mode=1, volume=60):
    return b"GAS0" + struct.pack("<6i", 70, 2, mode, volume, -1, -1)


def test_riff_layout_fmt_then_data_only():
    riff = sh_wav.build_riff(sh_wav.to_pcm16(np.zeros(101)), 22050)
    chunks, fmt, data = sh_wav.walk_riff(riff)
    assert [c[0] for c in chunks] == ["fmt ", "data"]
    assert fmt == dict(tag=1, channels=1, rate=22050, byte_rate=44100, block_align=2, bits=16, fmt_size=16)
    assert len(data) == 202 and struct.unpack_from("<I", riff, 4)[0] == len(riff) - 8


def test_gpw_keeps_stock_header_verbatim():
    hdr = stock_header()
    riff = sh_wav.build_riff(sh_wav.to_pcm16(np.zeros(10)), 11025)
    blob = sh_wav.build_gpw(hdr, riff)
    assert blob[:0x1c] == hdr and blob[0x1c:0x20] == b"RIFF"
    h2, gas, r2 = sh_wav.split_gpw(blob)
    assert h2 == hdr and r2 == riff
    assert gas == dict(priority=70, max_instances=2, play_mode=1, volume=60, random_pitch=-1, frequency=-1)
    with pytest.raises(sh_wav.WavError):
        sh_wav.build_gpw(b"RIFF" + b"\0" * 24, riff)


def test_8bit_decode_is_unsigned():
    riff = sh_wav.build_riff(bytes([128, 255, 0]), 11025, bits=8)
    x = sh_wav.decode(riff)["x"]
    assert np.allclose(x, [0.0, 127 / 128, -1.0])


def _riff_raw(tag, bits, rate, data):
    align = bits // 8
    fmt = struct.pack("<HHIIHH", tag, 1, rate, rate * align, align, bits)
    body = b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data
    return b"RIFF" + struct.pack("<I", len(body)) + body


def test_rx_prepass_formats_decode():
    """RX Batch Processor exports 24-bit PCM or 32-bit float WAVE; render --clean must read both."""
    v = np.array([0.0, 0.5, -0.5, -1.0])
    f32 = _riff_raw(3, 32, 22050, v.astype("<f4").tobytes())
    assert np.allclose(sh_wav.decode(f32)["x"], v)
    i24 = b"".join(int(round(s * (1 << 23))).to_bytes(4, "little", signed=True)[:3] for s in [0.0, 0.5, -0.5, -1.0])
    assert np.allclose(sh_wav.decode(_riff_raw(1, 24, 22050, i24))["x"], v)


@pytest.mark.skipif(not os.path.isdir(STOCK), reason="stock corpus not extracted")
def test_every_stock_gpw_has_riff_at_0x1c():
    n = 0
    for fn in os.listdir(STOCK):
        if fn.endswith(".gpw"):
            b = open(os.path.join(STOCK, fn), "rb").read()
            assert b[:4] == b"GAS0" and b[0x1c:0x20] == b"RIFF", fn
            n += 1
    assert n == 123


# ------------------------------------------------------------------------------------------------ DSP
def test_synthetic_tone_gets_sub_only_at_onsets():
    """Design 6.1.5: a 1 kHz tone file gains a 35-90 Hz sub only at onsets and nothing else."""
    fs = 22050
    x = np.zeros(fs * 2)
    t = np.arange(int(0.2 * fs)) / fs
    starts = [int(0.3 * fs), int(1.3 * fs)]
    for s in starts:
        x[s:s + len(t)] = 0.5 * np.sin(2 * np.pi * 1000 * t)
    ons = D.onsets(x, fs, False)
    assert [abs(o[0] - s) < fs * 0.01 for o, s in zip(ons, starts)] == [True, True] and len(ons) == 2
    sub = D.transient_sub(len(x), fs, ons, False, -6.0, tau_s=0.1, sweep_s=0.1)
    e = sub ** 2
    before = e[: starts[0] - int(0.02 * fs)].sum()
    near = sum(e[s:s + int(0.6 * fs)].sum() for s in starts)
    assert before < 1e-9 * near and near > 0.98 * e.sum()
    # spectrum of the sub: inside 30-90 Hz, nothing at the tone
    f = np.fft.rfftfreq(len(sub), 1 / fs)
    p = np.abs(np.fft.rfft(sub)) ** 2
    assert p[(f > 25) & (f < 100)].sum() > 0.95 * p.sum()
    assert p[(f > 900) & (f < 1100)].sum() < 1e-6 * p.sum()


def engine_like_loop(fs=11025, f0=90.0, seconds=1.0):
    n = int(fs * seconds)
    per = int(round(fs / f0))
    n -= n % per  # a seamless stock-style loop: whole number of pulse periods
    x = np.zeros(n)
    x[::per] = 1.0
    k = np.exp(-np.arange(per) / (per / 6))
    x = np.real(np.fft.ifft(np.fft.fft(x) * np.fft.fft(np.pad(k, (0, n - per)))))  # circular
    return 0.6 * x / np.max(np.abs(x))


def test_octave_sub_period_matched_and_seamless():
    fs = 11025
    x = engine_like_loop(fs)
    y, info = D.octave_sub(x, fs, True, -8.0)
    assert info["tracker"] == "autocorr" and info["octave_div"] == 2
    assert abs(info["sub_median_hz"] - 45.0) < 3.0
    assert isinstance(info["sub_cycles"], int) and info["sub_cycles"] >= 1
    assert D.seam_ratio(y) <= 1.0


def test_loop_processing_keeps_the_seam():
    fs = 11025
    x = engine_like_loop(fs)
    for y in (D.denoise_quant(x, fs, True), D.resample(x, fs, 22050, True), D.limit(x * 2, fs, True)):
        assert D.seam_ratio(y) <= max(1.0, D.seam_ratio(x) * 1.25 + 0.1)


def test_declick_repairs_spike_but_not_nyquist_content():
    fs = 11025
    x = 0.3 * np.sin(2 * np.pi * 5000 * np.arange(2000) / fs)  # near-Nyquist content: every sample "spiky"
    y, n = D.declick(x, False)
    assert n == 0 and np.array_equal(x, y)
    z = 0.05 * np.sin(2 * np.pi * 200 * np.arange(2000) / fs)
    z[1000] += 0.8
    y, n = D.declick(z, False)
    assert n == 1 and abs(y[1000] - z[1000]) > 0.7


def test_match_and_limit_hits_loudness_and_true_peak():
    pytest.importorskip("pyloudnorm")
    fs = 22050
    rng = np.random.default_rng(1)
    x = np.clip(rng.standard_normal(fs) * 0.4, -1, 1)
    target = D.loudness(x, fs)
    out, g, info = D.match_and_limit(x * 1.5, fs, False, target)
    assert abs(D.loudness(out, fs) - target) <= 0.5
    assert D.true_peak_db(out) <= -0.3


# ------------------------------------------------------------------------------------------------ install
def make_fake_game(tmp_path, name="game-fake"):
    root = tmp_path / "lab"
    g = root / name
    (g / "ADDON").mkdir(parents=True)
    (g / "I76.ZFS").write_bytes(b"ZFSF-not-really")
    (g / "ADDON" / "vehscn.vcf").write_bytes(b"owner mod")  # an owner file soundhd must never touch
    return root, g


def make_fake_pack(tmp_path, names=("vexplode.gpw", "cammo.gpw")):
    pack = tmp_path / "pack"
    (pack / "addon").mkdir(parents=True)
    sounds = []
    for i, n in enumerate(names):
        blob = sh_wav.build_gpw(stock_header(), sh_wav.build_riff(sh_wav.to_pcm16(np.full(50, 0.01 * (i + 1))), 22050))
        (pack / "addon" / n).write_bytes(blob)
        sounds.append(dict(name=n[:-4], replacement=dict(file=n, md5=md5(blob))))
    (pack / "manifest.json").write_text(json.dumps(dict(pack_version="test", sounds=sounds)))
    return pack


def listing(g):
    a = g / "ADDON"
    return {p.name: md5(p.read_bytes()) for p in a.iterdir()}


def test_default_roots_refuse_everything_but_lab_game_folders(tmp_path):
    _, g = make_fake_game(tmp_path)
    for target in (str(g), r"C:\Users\james\Games\Interstate76-2026-10-03", r"C:\Users\james\i76-map\sandbox-gog\main\app",
                   r"C:\Users\james\i76-uncap-lab", r"C:\Users\james\i76-uncap-lab\captures"):
        with pytest.raises(sh_install.InstallRefused):
            sh_install.check_target(target)


def test_denied_root_wins_over_allowed(tmp_path):
    root, g = make_fake_game(tmp_path)
    with pytest.raises(sh_install.InstallRefused):
        sh_install.check_target(str(g), allowed_roots=[str(root / "game*")], denied_roots=[str(root)])


def test_requires_a_game_folder(tmp_path):
    root, g = make_fake_game(tmp_path)
    (g / "I76.ZFS").unlink()
    with pytest.raises(sh_install.InstallRefused):
        sh_install.check_target(str(g), allowed_roots=[str(root / "game*")], denied_roots=[])
    with pytest.raises(sh_install.InstallRefused):
        sh_install.check_target(str(root / "notgame"), allowed_roots=[str(root / "game*")], denied_roots=[])


def test_install_dry_run_apply_readback_uninstall(tmp_path):
    root, g = make_fake_game(tmp_path)
    pack = make_fake_pack(tmp_path)
    kw = dict(allowed_roots=[str(root / "game*")], denied_roots=[], log=lambda *_: None)
    before = listing(g)
    r = sh_install.install(str(pack), str(g), apply=False, **kw)
    assert r["dry_run"] and listing(g) == before
    r = sh_install.install(str(pack), str(g), apply=True, **kw)
    assert r["installed"] == 2 and r["written"] == 2
    after = listing(g)
    for n in ("vexplode.gpw", "cammo.gpw"):
        assert after[n] == md5((pack / "addon" / n).read_bytes())
    assert after["vehscn.vcf"] == before["vehscn.vcf"]
    rec = json.loads((g / "ADDON" / sh_install.RECORD).read_text())
    assert set(rec["files"]) == {"vexplode.gpw", "cammo.gpw"}
    # idempotent: a second install writes nothing
    r = sh_install.install(str(pack), str(g), apply=True, **kw)
    assert r["written"] == 0
    r = sh_install.uninstall(str(g), apply=True, **kw)
    assert r["deleted"] == 2 and listing(g) == before


def test_install_refuses_to_overwrite_foreign_addon_file(tmp_path):
    root, g = make_fake_game(tmp_path)
    pack = make_fake_pack(tmp_path)
    (g / "ADDON" / "VEXPLODE.GPW").write_bytes(b"someone else's sound")  # case-insensitive clash
    before = listing(g)
    with pytest.raises(sh_install.InstallRefused):
        sh_install.install(str(pack), str(g), apply=True, allowed_roots=[str(root / "game*")], denied_roots=[],
                           log=lambda *_: None)
    assert listing(g) == before


def test_install_refuses_stale_pack(tmp_path):
    root, g = make_fake_game(tmp_path)
    pack = make_fake_pack(tmp_path)
    (pack / "addon" / "cammo.gpw").write_bytes(b"edited after the manifest")
    with pytest.raises(sh_install.InstallRefused):
        sh_install.install(str(pack), str(g), apply=True, allowed_roots=[str(root / "game*")], denied_roots=[],
                           log=lambda *_: None)


def test_uninstall_keeps_files_changed_since_install(tmp_path):
    root, g = make_fake_game(tmp_path)
    pack = make_fake_pack(tmp_path)
    kw = dict(allowed_roots=[str(root / "game*")], denied_roots=[], log=lambda *_: None)
    sh_install.install(str(pack), str(g), apply=True, **kw)
    (g / "ADDON" / "cammo.gpw").write_bytes(b"owner replaced it by hand")
    r = sh_install.uninstall(str(g), apply=True, **kw)
    assert r["deleted"] == 1 and r["kept"] == ["cammo.gpw"]
    assert (g / "ADDON" / "cammo.gpw").read_bytes() == b"owner replaced it by hand"
    assert not (g / "ADDON" / "vexplode.gpw").exists()
    rec = json.loads((g / "ADDON" / sh_install.RECORD).read_text())
    assert list(rec["files"]) == ["cammo.gpw"]


def test_soundhd_stages_refuse_game_output_dirs():
    import soundhd
    for p in (r"C:\Users\james\i76-uncap-lab\game\soundhd", r"C:\Users\james\i76-uncap-lab\game-dd-20261003",
              r"C:\Users\james\Games\Interstate76-2026-10-03\x", r"C:\Users\james\i76-map\sandbox-gog\main\app\ADDON"):
        with pytest.raises(SystemExit):
            soundhd.guard_check(p)


# ------------------------------------------------------------------------------------------------ built pack
@pytest.mark.skipif(not os.path.exists(os.path.join(PACK, "check-results.json")), reason="pack not built")
def test_built_pack_check_passes():
    r = json.load(open(os.path.join(PACK, "check-results.json"), encoding="utf-8"))["summary"]
    assert r["failed"] == 0 and r["checked"] == 123
