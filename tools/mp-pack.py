#!/usr/bin/env python3
"""Build the LAN multiplayer pack (game night, docs/GAME-NIGHT.md) from the Windows daily driver, READ-ONLY.

    python tools/mp-pack.py <pack dir> [--driver "<driver game folder>"] [--proxy <STRLKUP.DLL to ship instead>]

<pack dir>/mac must already hold the Mac-only files (pulled from James's Mac game folder: OpenGLide Glide2x.dll,
glide.dll, glide2x.ovl, OpenGLid.INI, I76PLYR.DEF, the cutscene-music SMACKW32.DLL + smackorg.dll, the rumble
i7_sfrce.dll + i7_sfrce_org.dll + rumble-envelopes.ini, music\\, AutoHotkeyU32.exe and the small .ahk/.env files).
This script writes:

  common\\   the files every machine gets byte-identical: the daily driver's exe, shell, u32x.dll, STRLKUP.DLL proxy,
            I76.ZFS, missions, ADDON (stock valepre4.vcf de680a86), NVCL, ...; the repo's controls\\input.map;
            IPXWrapper 0.7.2 (ipxwrapper.dll, wsock32.dll, mswsock.dll); the scenarios and the co-op campaign
            (tools/coop-install.py: ADDON\\auto01..auto07.lvl "Oil Well Well (Scenario)" .. and coop01..coop17.lvl
            "Scene 1 (Co-op)" .. (lower case: the shells' .lvl test is case-sensitive), listed as their own arenas
            after the 15 stock ones; the stock arenas, The Crater included, stay stock); the AI melee arenas
            ADDON\\ai_hs2 / ai_hs4 / ai_hs6.lvl "Hope Springs (2 AI)" .. (tools/aimelee-mission.py, run by coop-install.py).
  win\\      Windows-only: dgVoodoo DLLs + confs, launcher PLAY-i76.ps1 + presets, AutoHotkey layers (repo
            i76-remap.ahk), music, I76PLYR.DEF, SMACKW32.DLL, i7_sfrce.dll, ...; and PLAY-LAN.bat.
  MANIFEST.md + common.md5 / win.md5 / mac.md5 (md5 of every file; common.md5 is what each machine is checked
  against).

Left out of every part: saves (save*.cmp, savegame.dir), the driver's backups (*.driver-*, *.orig, *.u32xorig,
*.bak*), logs, victory.rec.
"""
import hashlib, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DRIVER = r"C:\Users\james\Games\Interstate76-2026-10-03\Interstate 76"
IPX = r"C:\Users\james\i76-uncap-lab\refs\ipxwrapper\bin\ipxwrapper-0.7.2"
IPX_FILES = ("ipxwrapper.dll", "wsock32.dll", "mswsock.dll")

# lower-case names (top level of the game folder) that are per-platform, not common
WIN_ONLY = {"d3d8.dll", "d3d9.dll", "d3dimm.dll", "ddraw.dll", "glide.dll", "glide2x.dll", "glide3x.dll",
            "dgvoodoo.conf", "dgvoodoo.wide.conf", "dgvoodoo.16x10.conf", "dgvoodoocpl.exe", "openglid.ini",
            "play-i76.ps1", "play-i76.bat", "play-i76-dgvoodoo.bat", "presets", "_ahk", "tools", "i76wheel.exe",
            "enable-force-feedback.bat", "what-this-is.txt", "manual.pdf", "music", "i76plyr.def", "smackw32.dll",
            "i7_sfrce.dll"}
SKIP_TOP = {"victory.rec", "mciproxy.log", "savegame.dir", "lee.fot"}   # Lee.fot: written by the game at every start


def skipped(name):
    n = name.lower()
    return (n in SKIP_TOP or (n.startswith("save") and (n.endswith(".cmp") or ".cmp." in n))
            or n.startswith("savegame.dir") or ".driver-" in n or n.endswith((".orig", ".u32xorig", ".log"))
            or ".bak" in n or ".pre-" in n)


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def copy(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def listing(root):
    out = []
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            out.append((os.path.relpath(p, root).replace("\\", "/"), md5(p), os.path.getsize(p)))
    return sorted(out, key=lambda r: r[0].lower())


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pack = os.path.abspath(sys.argv[1])
    driver = sys.argv[sys.argv.index("--driver") + 1] if "--driver" in sys.argv else DRIVER
    common, win, mac = (os.path.join(pack, x) for x in ("common", "win", "mac"))
    if not os.path.isdir(mac):
        sys.exit("no %s - pull the Mac-only files first (see the docstring)" % mac)
    for d in (common, win):
        if os.path.exists(d):
            sys.exit("%s exists - refusing (build into a fresh pack folder)" % d)
    for name in os.listdir(driver):
        src = os.path.join(driver, name)
        if skipped(name):
            continue
        copy(src, os.path.join(win if name.lower() in WIN_ONLY else common, name))
    # the unified control map and the matching wheel/pad layer
    shutil.copy2(os.path.join(REPO, "controls", "input.map"), os.path.join(common, "input.map"))
    shutil.copy2(os.path.join(REPO, "i76-remap.ahk"), os.path.join(win, "_ahk", "i76-remap.ahk"))
    for f in IPX_FILES:
        shutil.copy2(os.path.join(IPX, f), os.path.join(common, f))
    # anti-cheat car check: stock car data only
    vcf = os.path.join(common, "ADDON", "valepre4.vcf")
    assert md5(vcf).startswith("de680a86"), "ADDON valepre4.vcf is not the stock file"
    for d, _, fs in os.walk(os.path.join(common, "ADDON")):
        bad = [f for f in fs if f.lower().endswith((".vdf", ".wdf", ".gdf", ".cdf"))]
        assert not bad, "car data in ADDON: %s" % bad
    subprocess.run([sys.executable, os.path.join(HERE, "coop-install.py"), common], check=True)
    if "--proxy" in sys.argv:   # e.g. the co-op fix build ba2b45c1 before it reaches the daily driver
        for n in os.listdir(common):
            if n.lower() == "strlkup.dll":
                shutil.copy2(sys.argv[sys.argv.index("--proxy") + 1], os.path.join(common, n))
    with open(os.path.join(win, "PLAY-LAN.bat"), "w", newline="\r\n") as f:
        f.write("@echo off\n"
                "REM Interstate '76 LAN / co-op (docs/GAME-NIGHT.md). Same picture and physics as the daily driver's\n"
                "REM PLAY.bat (preset best-wide), plus the co-op switches. Arena list (MULTI MELEE > HOST): the 15 stock\n"
                "REM arenas = normal melee, then \"<name> (Scenario)\" = the 7 auto-melee scenarios with their AI cars\n"
                "REM (joiners respawn; the host's death restarts the scenario), then \"Scene 1..17 (Co-op)\" = the co-op campaign.\n"
                "REM \"Hope Springs (2 / 4 / 6 AI)\" (before the scenarios) = melee against computer cars the host runs\n"
                "REM (proxy I76_AIMELEE, on with I76_COOP_AI; docs/records/AI-MELEE-M1-2026-10-19.md).\n"
                "REM IPX through IPXWrapper (the three DLLs beside i76.exe). I76_MP_MENU=1: HOST / JOIN go straight\n"
                "REM to IPX (2 = show only the IPX button, 0 = the stock MODEM / IPX / INTERNET / NULLMODEM row).\n"
                "set I76_COOP_AI=1\n"
                "set I76_COOP_CHAIN=1\n"
                "set I76_MP_MENU=1\n"
                "copy /y \"%~dp0dgVoodoo.wide.conf\" \"%~dp0dgVoodoo.conf\" >nul\n"
                "start \"\" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "
                "\"%~dp0PLAY-i76.ps1\" -GameDir \"%~dp0.\" -Exe i76.exe -Preset best-wide -LosslessScaling none\n")
    lines = ["# Interstate '76 LAN pack - manifest", "",
             "Built by tools/mp-pack.py from `%s` (read-only). A machine's game folder = common + its platform part." % driver,
             ""]
    for part, root in (("common", common), ("win", win), ("mac", mac)):
        rows = listing(root)
        with open(os.path.join(pack, part + ".md5"), "w", newline="\n") as f:
            for r, h, _ in rows:
                f.write("%s  %s\n" % (h, r))
        lines += ["## %s (%d files, %.1f MB)" % (part, len(rows), sum(s for *_, s in rows) / 1e6), "",
                  "| file | bytes | md5 |", "|---|---|---|"]
        lines += ["| `%s` | %d | `%s` |" % (r, s, h) for r, h, s in rows] + [""]
    with open(os.path.join(pack, "MANIFEST.md"), "w", newline="\n") as f:
        f.write("\n".join(lines))
    print("pack written:", pack)


if __name__ == "__main__":
    main()
