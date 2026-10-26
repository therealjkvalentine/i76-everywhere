"""Offline tests for the i76tel v3 layout and decoder (tools/telemetry/i76tel.h, i76tel_v2.h, i76tel.py). No game.

    python -m pytest tests/test_i76tel_v3.py -q        (or:  python tests/test_i76tel_v3.py)

Packs synthetic datagrams and shared-memory blocks the way music-fix/strlkproxy.c writes them (v3) and the way the
committed v2 proxy writes them, and decodes both with the v3 reader. What this cannot show: that the live game
produces these events (docs/process/OWNER-TEST-LIST.md has the live test).
"""
import importlib.util, mmap, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TEL = os.path.join(REPO, "tools", "telemetry")
sys.path.insert(0, TEL)
import i76tel  # noqa: E402

H = i76tel.Header()
H2 = i76tel.Header(i76tel.HEADER_V2)
C = H.consts


def pack_frame(h, **vals):
    """a frame buffer for header h: every field 0 except magic / version / size and the given flat names"""
    d = {n: 0 for n in h.frame_names}
    d.update(magic=h.consts["I76TEL_MAGIC"], version=h.consts["I76TEL_VERSION"], size=h.frame_size)
    d["weapon_name"] = b"gmg\0\0\0\0\0"
    d.update(vals)
    codes = re.findall(r"(\d*)([a-zA-Z])", h.frame_fmt.lstrip("<"))    # one token per flat name ('8s' for the name)
    flat = [float(d[n]) if code in "fd" else d[n] for (cnt, code), n in zip(codes, h.frame_names)]
    return struct.pack(h.frame_fmt, *flat)


def pack_event(h, seq, frame, typ, f=(), i=()):
    nf = sum(n.startswith("f_") for n in h.event_names)
    ni = sum(n.startswith("i_") for n in h.event_names)
    f = [float(x) for x in f] + [0.0] * (nf - len(f))
    i = list(i) + [0] * (ni - len(i))
    return struct.pack(h.event_fmt, seq, frame, typ, *f, *i)


def name2(s):
    return list(struct.unpack("<ii", s.encode().ljust(8, b"\0")[:8]))


def s32(v):
    return struct.unpack("<i", struct.pack("<I", v & 0xffffffff))[0]


# --- layout ------------------------------------------------------------------------------------------------------

def test_sizes_and_version():
    assert C["I76TEL_VERSION"] == 3 and H2.consts["I76TEL_VERSION"] == 2
    assert (H.frame_size, H.event_size, H.structs["i76tel_shm_t"][1]) == (664, 56, 8 + 664 + 64 * 56)
    assert (H2.frame_size, H2.event_size, H2.structs["i76tel_shm_t"][1]) == (628, 36, 8 + 628 + 64 * 36)


def test_v2_frame_offsets_unchanged():
    v3 = {f.name: (f.offset, f.size) for f in H.structs["i76tel_frame_t"][0]}
    for f in H2.structs["i76tel_frame_t"][0]:
        assert v3[f.name] == (f.offset, f.size), f.name
    assert H.offset("i76tel_frame_t", "wheelbase") == 628


def test_proxy_size_check_matches_header():
    src = open(os.path.join(REPO, "music-fix", "strlkproxy.c"), encoding="utf-8").read()
    m = re.search(r"sizeof\(i76tel_frame_t\) == (\d+) && sizeof\(i76tel_event_t\) == (\d+)", src)
    assert m and (int(m.group(1)), int(m.group(2))) == (H.frame_size, H.event_size)


def test_new_constants_present():
    for k in ("I76TEL_EV_SOUND_START", "I76TEL_EV_SOUND_STOP", "I76TEL_EV_DAMAGE_SIDE", "I76TEL_EV_WEAPON_UI",
              "I76TEL_SND_PLAYER", "I76TEL_SND_HAS_POS", "I76TEL_STOP_PLAYER", "I76TEL_DMG_KILLED", "I76TEL_HOOK_WEAPON_UI"):
        assert k in C, k
    assert (C["I76TEL_EV_SOUND_START"], C["I76TEL_EV_SOUND_STOP"], C["I76TEL_EV_DAMAGE_SIDE"], C["I76TEL_EV_WEAPON_UI"]) == (4, 5, 6, 7)


# --- v3 datagram -------------------------------------------------------------------------------------------------

def v3_datagram():
    bits = (1 | C["I76TEL_SND_PLAYER"] | C["I76TEL_SND_HAS_POS"] | (0x4f << C["I76TEL_SND_PRIO_SHIFT"]))
    evs = [
        pack_event(H, 10, 500, C["I76TEL_EV_SHOT"], (2, 699, 30, 0.01), (7, 3)),
        pack_event(H, 11, 500, C["I76TEL_EV_SOUND_START"], (8268.75, 100, 1200.5, 30.25, -800.0, 0), name2("eimarx") + [bits, 0x1234560, 0x7654320]),
        pack_event(H, 12, 500, C["I76TEL_EV_SOUND_START"], (11025, 50, 0, 0, 0, -2500), name2("cmike") + [C["I76TEL_SND_VOICE_LVL"] | (10000 << 16), 0, 0x7654400]),
        pack_event(H, 13, 500, C["I76TEL_EV_SOUND_STOP"], (1.5,), name2("tskid2") + [C["I76TEL_STOP_ENDED"] | C["I76TEL_STOP_PLAYER"], 0x1234560, 0x7654500]),
        pack_event(H, 14, 500, C["I76TEL_EV_SOUND_STOP"], (0.2,), name2("vmgun") + [0x40, 0x2222220, 0x7654600]),
        pack_event(H, 15, 500, C["I76TEL_EV_DAMAGE_SIDE"], (40, 37, -0.9, 0.1, 0.2), [1, 2, C["I76TEL_DMG_PLAYER"] | C["I76TEL_DMG_KILLED"], 1 | (0x10 << 16), 1]),
        pack_event(H, 16, 500, C["I76TEL_EV_WEAPON_UI"], (), [2]),
    ]
    fr = pack_frame(H, seq=5, frame=480, proxy_frame=500, player_present=1, speed=20.0, event_seq=16, event_count=len(evs),
                    wheelbase=2.45, front_track=1.6, steer_gain=1 / 4.9, grip_sum=4.0, grip_cap=31.36, ground_g=9.8,
                    music_track=3, event_hooks=0x7f, sound_voices=2)
    return fr + b"".join(evs)


def test_v3_datagram_roundtrip():
    fr, evs = i76tel.decode_datagram(H, v3_datagram())
    assert fr["version"] == 3 and fr["event_count"] == 7 and len(evs) == 7
    assert abs(fr["wheelbase"] - 2.45) < 1e-6 and abs(fr["grip_cap"] - 31.36) < 1e-4 and fr["music_track"] == 3
    assert fr["event_hooks"] == 0x7f and fr["sound_voices"] == 2
    assert [e["type"] for e in evs] == [1, 4, 4, 5, 5, 6, 7] and [e["seq"] for e in evs] == list(range(10, 17))
    shot, start, cb, stop, park, dmg, wui = evs
    assert shot["f_1"] == 699 and shot["i_0"] == 7 and shot["i_1"] == 3
    assert i76tel.ev_name(start) == "eimarx" and abs(start["f_0"] - 8268.75) < 1e-3 and start["f_2"] == 1200.5
    s = i76tel.sound_fields(H, start)
    assert s == {"mode": 1, "is_player": 1, "has_pos": 1, "detached": 0, "voice_level": 0, "prio": 0x4f}
    assert start["i_3"] == 0x1234560 and start["i_4"] == 0x7654320
    assert i76tel.sound_fields(H, cb)["prio"] == 10000 and i76tel.sound_fields(H, cb)["voice_level"] == 1 and cb["f_5"] == -2500
    assert i76tel.sound_fields(H, stop) == {"reason": 2, "is_player": 1} and i76tel.ev_name(stop) == "tskid2"
    assert i76tel.sound_fields(H, park) == {"reason": 0x40, "is_player": 0}
    assert dmg["i_0"] == 1 and dmg["i_1"] == 2 and dmg["f_0"] == 40 and dmg["f_1"] == 37 and dmg["i_3"] == 0x100001
    assert wui["i_0"] == 2


def test_event_lines():
    fr, evs = i76tel.decode_datagram(H, v3_datagram())
    lines = [i76tel.event_line(H, e) for e in evs]
    assert "SHOT" in lines[0]
    assert "SOUND+" in lines[1] and "eimarx" in lines[1] and "PLAYER" in lines[1] and "loop" in lines[1] and "(1200.5, 30.2, -800.0)" in lines[1]
    assert "2D" in lines[2] and "voice-level" in lines[2] and "prio 10000" in lines[2]
    assert "SOUND-" in lines[3] and "ended" in lines[3] and "1.50 s" in lines[3]
    assert "parked" in lines[4]
    assert "DAMAGE" in lines[5] and "side left" in lines[5] and "zone 2" in lines[5] and "KILLED" in lines[5] and "lost 37" in lines[5]
    assert lines[6].rstrip().endswith("WEAPON-UI unlink")


def test_checker_accepts_v3(capsys):
    data = v3_datagram()
    chk = i76tel.Checker(H)
    fr, evs = i76tel.decode_datagram(H, data)
    chk.frame(fr, len(data))
    assert chk.bad == 0 and chk.n_old == 0


def test_csv_columns(tmp_path):
    fr, evs = i76tel.decode_datagram(H, v3_datagram())
    c = i76tel.Csv(H, str(tmp_path / "run.csv"))
    c.frame(fr)
    for e in evs:
        c.event(e)
    c.close()
    head = open(tmp_path / "run.events.csv").readline().strip().split(",")
    assert head == H.event_names and "f_5" in head and "i_4" in head


# --- v2 producer, v3 reader --------------------------------------------------------------------------------------

def v2_datagram():
    evs = [pack_event(H2, 1, 90, 3, (9.0, 0.0, 1.0, 12.0), (1, 0x33)), pack_event(H2, 2, 90, 2, (1, 2, 3, 8.5), name2("X1_BULC1"))]
    return pack_frame(H2, seq=7, frame=88, proxy_frame=90, player_present=1, rpm=3000.0, event_seq=2, event_count=2) + b"".join(evs)


def test_v2_datagram_through_v3_reader():
    data = v2_datagram()
    assert len(data) == 628 + 2 * 36
    fr, evs = i76tel.decode_datagram(H, data)
    assert fr["version"] == 2 and fr["rpm"] == 3000.0 and fr["proxy_frame"] == 90
    assert fr["wheelbase"] == 0 and fr["event_hooks"] == 0 and list(fr) == H.frame_names
    assert [e["type"] for e in evs] == [3, 2] and evs[0]["f_3"] == 12.0 and evs[0]["i_1"] == 0x33
    assert evs[0]["f_4"] == 0 and evs[0]["i_4"] == 0 and list(evs[0]) == H.event_names
    assert "EXPLOSION X1_BULC1" in i76tel.event_line(H, evs[1])
    chk = i76tel.Checker(H)
    chk.frame(fr, len(data))
    assert chk.bad == 0 and chk.n_old == 1


def test_v3_frame_through_v2_header():
    """a reader still on the v2 header decodes a v3 frame's fields (they kept their offsets)"""
    data = v3_datagram()
    d = dict(zip(H2.frame_names, struct.unpack_from(H2.frame_fmt, data, 0)))
    assert d["proxy_frame"] == 500 and abs(d["speed"] - 20.0) < 1e-6 and d["event_seq"] == 16


# --- shared memory -----------------------------------------------------------------------------------------------

def shm_block(h, frame, ring_events):
    size = h.structs["i76tel_shm_t"][1]
    b = bytearray(size)
    struct.pack_into("<II", b, 0, 2, size)
    fo, ro = h.offset("i76tel_shm_t", "frame"), h.offset("i76tel_shm_t", "ring")
    b[fo:fo + len(frame)] = frame
    for seq, ev in ring_events:
        o = ro + (seq % 64) * h.event_size
        b[o:o + len(ev)] = ev
    return bytes(b)


def test_open_shm_falls_back_to_v2_size():
    suffix = ".t3test%d" % os.getpid()
    name = C["I76TEL_SHM_NAME"] + suffix
    size2 = H2.structs["i76tel_shm_t"][1]
    owner = mmap.mmap(-1, size2, tagname=name)            # a v2 proxy made the section first
    try:
        blk = shm_block(H2, pack_frame(H2, seq=3, proxy_frame=77, event_seq=65, player_present=1),
                        [(65, pack_event(H2, 65, 77, 1, (1, 2, 3, 4), (5, 6)))])
        owner[:] = blk
        m, size = i76tel.open_shm(H, suffix)
        assert size == size2
        buf = m[:size]
        lay = i76tel.shm_layout(H, buf)
        assert lay.consts["I76TEL_VERSION"] == 2
        fr = i76tel.decode_frame(H, buf[8:8 + H.frame_size])
        assert fr["version"] == 2 and fr["proxy_frame"] == 77 and fr["wheelbase"] == 0
        ev = i76tel.decode_event(H, buf, lay.offset("i76tel_shm_t", "ring") + (65 % 64) * lay.event_size, lay)
        assert ev["seq"] == 65 and ev["i_1"] == 6 and ev["i_2"] == 0
        m.close()
    finally:
        owner.close()


def test_v3_shm_ring():
    blk = shm_block(H, pack_frame(H, seq=9, proxy_frame=12, event_seq=130),
                    [(130, pack_event(H, 130, 12, C["I76TEL_EV_WEAPON_UI"], (), [1]))])
    lay = i76tel.shm_layout(H, blk)
    assert lay is H
    ev = i76tel.decode_event(H, blk, H.offset("i76tel_shm_t", "ring") + (130 % 64) * 56)
    assert ev["type"] == 7 and ev["i_0"] == 1 and ev["seq"] == 130


def test_rate_ab_live_tel_reads_both_versions():
    """lab/tools/framerate/rate-ab-live.py's Tel against a private mapping, v3 block then a v2 block"""
    spec = importlib.util.spec_from_file_location("rate_ab_live", os.path.join(REPO, "lab", "tools", "framerate", "rate-ab-live.py"))
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)
    for h, typ in ((H, C["I76TEL_EV_SOUND_START"]), (H2, 3)):
        suffix = ".t3live%d-%d" % (os.getpid(), h.consts["I76TEL_VERSION"])
        owner = mmap.mmap(-1, h.structs["i76tel_shm_t"][1], tagname=C["I76TEL_SHM_NAME"] + suffix)
        try:
            tel = live.Tel(TEL)
            tel.open(suffix)
            blk = bytearray(shm_block(h, pack_frame(h, seq=1, proxy_frame=5, event_seq=0), []))
            owner[:] = bytes(blk)
            assert tel.next(timeout=0.5)[1] == []
            blk2 = bytearray(shm_block(h, pack_frame(h, seq=2, proxy_frame=6, event_seq=1), [(1, pack_event(h, 1, 6, typ, (1.0,), (2,)))]))
            struct.pack_into("<I", blk2, 0, 4)
            owner[:] = bytes(blk2)
            fr, evs = tel.next(timeout=0.5)
            assert fr["proxy_frame"] == 6 and len(evs) == 1 and evs[0]["type"] == typ and evs[0]["i_0"] == 2
            tel.m.close()
        finally:
            owner.close()


def test_verify_sites_table_matches_proxy():
    """every site verify_v3_sites.py checks is patched in strlkproxy.c with the same expected bytes"""
    src = open(os.path.join(REPO, "music-fix", "strlkproxy.c"), encoding="utf-8").read()
    spec = importlib.util.spec_from_file_location("verify_v3_sites", os.path.join(TEL, "verify_v3_sites.py"))
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    for va, want, what in v.SITES:
        if want[0] == 0xE8:
            target = va + 5 + struct.unpack("<i", want[1:5])[0]
            assert re.search(r"tel_repoint_call\(0x%08x, 0x%08x," % (va, target), src), hex(va)
        else:
            arr = ", ".join("0x%02X" % b for b in want)
            assert arr in src and ("0x%08x" % va) in src, hex(va)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
