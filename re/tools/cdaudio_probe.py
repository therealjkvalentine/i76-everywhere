r"""cdaudio_probe.py - can the MCI cdaudio device be opened right now? (M12: shell_cb_17 0x470f90 skips the CD-2 scan
only when the game's own MCI cdaudio open succeeds; a killed instance never closes the device.)

    python tools\cdaudio_probe.py            -> prints open ok / error text and exits 0 (ok) or 1 (fails)
    python tools\cdaudio_probe.py --wait 30  -> retry every second up to 30 s, exit 0 as soon as it opens

Uses winmm!mciSendStringW("open cdaudio alias i76probe") then "close i76probe". The probe itself closes the device, so
it does not hold it against the game.
"""
import ctypes, sys, time
winmm = ctypes.windll.winmm


def try_open():
    buf = ctypes.create_unicode_buffer(256)
    rc = winmm.mciSendStringW("open cdaudio alias i76probe wait", buf, 255, None)
    if rc == 0:
        info = []
        for q in ("status i76probe mode", "status i76probe number of tracks", "status i76probe media present", "status i76probe ready"):
            b = ctypes.create_unicode_buffer(256); r2 = winmm.mciSendStringW(q, b, 255, None)
            info.append("%s=%s" % (q.split("i76probe ")[1], b.value if r2 == 0 else "err%d" % r2))
        winmm.mciSendStringW("close i76probe", None, 0, None)
        return True, "ok " + " ".join(info)
    err = ctypes.create_unicode_buffer(256)
    winmm.mciGetErrorStringW(rc, err, 255)
    return False, "mci error %d: %s" % (rc, err.value)


def volume_probe():
    """GetVolumeInformationA on every CD-ROM drive (what 0x470ed0 / shell_cb_17 do); returns [(drive, label or error)]."""
    k = ctypes.windll.kernel32
    mask = k.GetLogicalDrives(); out = []
    for i in range(26):
        if not (mask >> i) & 1:
            continue
        root = "%s:\\" % chr(65 + i)
        if k.GetDriveTypeW(root) != 5:
            continue
        name = ctypes.create_unicode_buffer(64); fs = ctypes.create_unicode_buffer(64)
        ser = ctypes.c_ulong(); mx = ctypes.c_ulong(); fl = ctypes.c_ulong()
        ok = k.GetVolumeInformationW(root, name, 64, ctypes.byref(ser), ctypes.byref(mx), ctypes.byref(fl), fs, 64)
        out.append((root[:2], name.value if ok else "GetVolumeInformation error %d" % ctypes.get_last_error()))
    return out


def main():
    wait = 0
    if "--wait" in sys.argv:
        wait = int(sys.argv[sys.argv.index("--wait") + 1])
    t0 = time.time()
    while True:
        ok, msg = try_open()
        vols = volume_probe()
        print("cdaudio open: %s | cd volumes: %s (+%.1fs)" % (msg, vols, time.time() - t0))
        ok = ok and any(not v[1].startswith("GetVolumeInformation error") for v in vols)
        if ok or time.time() - t0 >= wait:
            sys.exit(0 if ok else 1)
        time.sleep(1)


if __name__ == "__main__":
    main()
