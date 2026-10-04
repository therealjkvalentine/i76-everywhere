#!/usr/bin/env python3
r"""make-harness.py - generate tools\harness\*.ps1 from the proven autotest scripts by LITERAL replacement.

    python tools\harness\make-harness.py            # regenerate every ported script, print the ledger
    python tools\harness\make-harness.py --check    # exit 1 if any generated file differs from what is on disk

Source: C:\Users\james\i76-uncap-lab\autotest\*.ps1 (never modified). Target: this directory.
Every edit is an exact-string replacement with an expected occurrence count; a miss is an error, never a
silent no-op (H3: the write is read back by --check). Output is pure ASCII, no BOM, CRLF preserved from
the source (gate G-ENC: the earlier copy in captures\002-idle-null carried a BOM and the "â€”" doubled
encoding of the header's em dash).

What changes and why (p3-harness-pause):
  (a) lib dot-sources -> absolute C:\Users\james\i76-uncap-lab\autotest\lib paths
  (b) Get-GamePid -> matches -ProcName (default i76_pristine_fix; focuslib's only matches i76/nitro)
      Mem-Open   -> same process lookup (memlib's only matches i76/nitro)  [scripts that use memlib]
  (c) -Exe (default i76_pristine_fix.exe): the launch path delegates to tools\launch.ps1 (H0 md5 gate,
      H10 session gate, which_build stamp) instead of a bare Start-Process of i76.exe
  (d) $GameDir defaults to C:\Users\james\i76-uncap-lab\game
  (e) Focus-Game: Test-WindowPumping (WM_NULL, SMTO_ABORTIFHUNG) before every blocking focus call
  (f) Sync-CursorMap: maplib's Init-CursorMap looks up the window with `Get-Process i76, nitro`, so under
      i76_pristine_fix it silently falls back to desktop-derived geometry; the port recomputes from the real
      client rect once the process is known and prints both so a drift is visible (H5).
"""
import argparse
import os
import sys

SRC = r"C:\Users\james\i76-uncap-lab\autotest"
DST = os.path.dirname(os.path.abspath(__file__))
LIB = r"C:\Users\james\i76-uncap-lab\autotest\lib"
GAME = r"C:\Users\james\i76-uncap-lab\game"
LAB = r"C:\Users\james\i76-uncap-lab"
MAPROOT = r"C:\Users\james\i76-map"

# ---- shared snippets (CRLF is applied at write time; write them with \n here) -----------------------
GAMEPID = (
    '# --- harness overrides (tools\\harness\\make-harness.py) ---------------------------------------\n'
    '# (b) focuslib\'s Get-GamePid matches process names i76/nitro only; the H0 build is i76_pristine_fix.exe.\n'
    'function Get-GamePid {\n'
    '    Get-Process -Name $ProcName -ErrorAction SilentlyContinue |\n'
    '        Where-Object { $_.Path -and $_.Path -like "*i76-uncap-lab*" } | Select-Object -First 1\n'
    '}\n'
    '# (e) H10 runbook rule: never run the blocking focus dance against a window that is not pumping\n'
    '#     (the shell\'s modal dialogs). SetCursorPos + mouse_event still work in that state.\n'
    'function Focus-Game($p) {\n'
    '    if (-not (Test-WindowPumping $p.MainWindowHandle)) {\n'
    '        Write-Warning "game window is not pumping (modal shell dialog?) - skipping the focus calls"\n'
    '        return $false\n'
    '    }\n'
    '    return (Force-Foreground $p.MainWindowHandle)\n'
    '}\n'
    '# (f) maplib\'s Init-CursorMap ran at dot-source time and looked for `i76`/`nitro`; recompute the\n'
    '#     screen-side transform from THIS process\'s client rect (same math as maplib, kept in step by hand).\n'
    'function Sync-CursorMap($p) {\n'
    '    $before = "UiLeft={0} UiTop={1} UnitPx={2} UnitPxX={3}" -f $script:UI_LEFT, $script:UI_TOP, $script:UI_U, $script:UI_UX\n'
    '    $rc = New-Object WinRect+RECT\n'
    '    if (-not [WinRect]::GetClientRect($p.MainWindowHandle, [ref]$rc)) { Write-Warning "GetClientRect failed; keeping $before"; return }\n'
    '    $pt = New-Object WinRect+POINT; [void][WinRect]::ClientToScreen($p.MainWindowHandle, [ref]$pt)\n'
    '    if ($rc.R -le 0 -or $rc.B -le 0) { Write-Warning "empty client rect; keeping $before"; return }\n'
    '    $winW = [double]$rc.R; $winH = [double]$rc.B; $winX = [double]$pt.X; $winY = [double]$pt.Y\n'
    '    $rw = 1680.0; $rh = 1050.0; $mode = \'stretched_ar\'\n'
    '    $conf = Join-Path $GameDir \'dgVoodoo.conf\'\n'
    '    if (Test-Path $conf) {\n'
    '        $m = Select-String -Path $conf -Pattern \'^\\s*Resolution\\s*=\\s*(\\d+)\\s*x\\s*(\\d+)\' | Select-Object -First 1\n'
    '        if ($m) { $rw = [double]$m.Matches[0].Groups[1].Value; $rh = [double]$m.Matches[0].Groups[2].Value }\n'
    '        $s = Select-String -Path $conf -Pattern \'^\\s*ScalingMode\\s*=\\s*(\\S+)\' | Select-Object -First 1\n'
    '        if ($s) { $mode = $s.Matches[0].Groups[1].Value.ToLower() }\n'
    '    }\n'
    '    $ch = $winH; $cw = $ch * ($rw / $rh)\n'
    '    if ($cw -gt $winW) { $cw = $winW; $ch = $cw * ($rh / $rw) }\n'
    '    $cl = $winX + ($winW - $cw) / 2.0; $ct = $winY + ($winH - $ch) / 2.0\n'
    '    if ($mode -like \'*_ar\' -or $mode -eq \'centered\' -or $mode -eq \'unspecified\') {\n'
    '        $u = $ch / 480.0; $pillarUnits = (($cw / $u) - 640.0) / 2.0\n'
    '        $script:UI_U = $u; $script:UI_UX = $u; $script:UI_LEFT = $cl + $pillarUnits * $u\n'
    '    } else {\n'
    '        $u = $ch / 480.0; $script:UI_U = $u; $script:UI_UX = $cw / 640.0; $script:UI_LEFT = $cl\n'
    '    }\n'
    '    $script:UI_TOP = $ct; $script:FR_L = $cl; $script:FR_T = $ct; $script:FR_W = $cw; $script:FR_H = $ch\n'
    '    $after = "UiLeft={0} UiTop={1} UnitPx={2} UnitPxX={3}" -f $script:UI_LEFT, $script:UI_TOP, $script:UI_U, $script:UI_UX\n'
    '    Write-Host ("cursor map: dot-source fallback [{0}] -> from client rect {1}x{2}@{3},{4} [{5}]" -f $before, $rc.R, $rc.B, $pt.X, $pt.Y, $after) -ForegroundColor DarkGray\n'
    '}\n'
)
MEMOPEN = (
    '# (b) memlib\'s Mem-Open matches i76/nitro only; same body, harness process lookup.\n'
    'function Mem-Open {\n'
    '    param([string]$RequirePath = \'i76-uncap-lab\', [switch]$Write)\n'
    '    $proc = Get-GamePid\n'
    '    if (-not $proc) { throw "Interstate \'76 ($ProcName, path *$RequirePath*) is not running." }\n'
    '    $access = if ($Write) { 0x38 } else { 0x10 }   # VM_OP|VM_READ|VM_WRITE : VM_READ\n'
    '    $h = [I76Mem]::OpenProcess($access, $false, $proc.Id)\n'
    '    if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed (same user as the game?)." }\n'
    '    [pscustomobject]@{ Proc = $proc; H = $h; Buf4 = (New-Object byte[] 4) }\n'
    '}\n'
)
LAUNCH = (
    '    # (c) H0/H10: the launch goes through tools\\launch.ps1 (md5 gate, session gate, which_build stamp);\n'
    '    #     exit 0 = launched and H0 PASS. Anything else stops here with the launcher\'s own reason.\n'
    '    & powershell -NoProfile -ExecutionPolicy Bypass -File "C:\\Users\\james\\i76-map\\tools\\launch.ps1" -GameDir $GameDir -Exe $Exe -CaptureId $CaptureId -SettleSeconds $SettleSeconds\n'
    '    if ($LASTEXITCODE -ne 0) { throw "launch.ps1 exit $LASTEXITCODE (0 = launched + H0 pass; 3 md5 refused; 4 session/RDP refused; 5 exited early; 1 H0 FAIL)" }\n'
)


def port_entry(name, dst_name, extra_libs, has_mem):
    """The three entry scripts share one pattern."""
    src = open(os.path.join(SRC, name), "rb").read().decode("utf-8")
    edits = []
    # header usage lines (enter-melee only has them)
    if name == "enter-melee.ps1":
        edits += [
            ("enter-melee.ps1 \u2014 launch I'76 (sandbox)", "enter-melee-pristine.ps1 - launch I'76 (sandbox, H0 build i76_pristine_fix.exe)", 1),
            ("powershell -ExecutionPolicy Bypass -File tools\\enter-melee.ps1            # launch + enter",
             "powershell -ExecutionPolicy Bypass -File tools\\harness\\enter-melee-pristine.ps1                 # launch via tools\\launch.ps1 + enter", 1),
            ("powershell -ExecutionPolicy Bypass -File tools\\enter-melee.ps1 -NoLaunch  # already running",
             "powershell -ExecutionPolicy Bypass -File tools\\harness\\enter-melee-pristine.ps1 -NoLaunch -Area AirBase  # already running (the sitting)", 1),
            ('param([switch]$NoLaunch, [switch]$KeepAI, [string]$GameDir = "$PSScriptRoot\\..\\game",',
             'param([switch]$NoLaunch, [switch]$KeepAI, [string]$GameDir = "' + GAME + '",\n'
             '      [string]$Exe = "i76_pristine_fix.exe", [string]$ProcName = "i76_pristine_fix",\n'
             '      [string]$CaptureId = ("launch-" + (Get-Date -Format "yyyyMMdd-HHmmss")), [int]$SettleSeconds = 8,', 1),
            ('. "$PSScriptRoot\\lib\\focuslib.ps1"; . "$PSScriptRoot\\lib\\inputlib.ps1"; . "$PSScriptRoot\\lib\\maplib.ps1"',
             '$AutotestLib = "' + LIB + '"   # (a)\n'
             '. "$AutotestLib\\focuslib.ps1"; . "$AutotestLib\\inputlib.ps1"; . "$AutotestLib\\maplib.ps1"\n' + GAMEPID, 1),
            ("    Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue\n    Start-Sleep -Seconds 1\n"
             "    Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir\n"
             "    Start-Sleep -Seconds 8\n",
             "    Get-GamePid | Stop-Process -Force -EA SilentlyContinue\n    Start-Sleep -Seconds 1\n" + LAUNCH, 1),
        ]
    elif name == "enter-mission5.ps1":
        edits += [
            ("enter-mission5.ps1 \u2014 load", "enter-mission5-pristine.ps1 - load", 1),
            ("Mission 5 is the canonical", "Ported to the H0 build by tools\\harness\\make-harness.py; needs save002 in the SANDBOX game folder.\n  Mission 5 is the canonical", 1),
            ('param([switch]$NoLaunch, [string]$GameDir = "$PSScriptRoot\\..\\game",\n      [int]$SceneY = 782, [switch]$StopAtGarage)',
             'param([switch]$NoLaunch, [string]$GameDir = "' + GAME + '",\n'
             '      [string]$Exe = "i76_pristine_fix.exe", [string]$ProcName = "i76_pristine_fix",\n'
             '      [string]$CaptureId = ("launch-" + (Get-Date -Format "yyyyMMdd-HHmmss")), [int]$SettleSeconds = 9,\n'
             '      [int]$SceneY = 782, [switch]$StopAtGarage)', 1),
            ('. "$PSScriptRoot\\lib\\focuslib.ps1"; . "$PSScriptRoot\\lib\\inputlib.ps1"\n'
             '. "$PSScriptRoot\\lib\\maplib.ps1";   . "$PSScriptRoot\\lib\\memlib.ps1"\n'
             '. "$PSScriptRoot\\lib\\simlib.ps1"',
             '$AutotestLib = "' + LIB + '"   # (a)\n'
             '. "$AutotestLib\\focuslib.ps1"; . "$AutotestLib\\inputlib.ps1"\n'
             '. "$AutotestLib\\maplib.ps1";   . "$AutotestLib\\memlib.ps1"\n'
             '. "$AutotestLib\\simlib.ps1"\n' + GAMEPID + MEMOPEN, 1),
            ("    Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue\n    Start-Sleep -Seconds 2\n"
             "    Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir\n"
             "    Start-Sleep -Seconds 9\n",
             "    Get-GamePid | Stop-Process -Force -EA SilentlyContinue\n    Start-Sleep -Seconds 2\n" + LAUNCH, 1),
        ]
    elif name == "enter-trip1.ps1":
        edits += [
            ("enter-trip1.ps1 \u2014 cold launch", "enter-trip1-pristine.ps1 - cold launch (via tools\\launch.ps1, H0 build i76_pristine_fix.exe)", 1),
            ('param([switch]$NoLaunch, [string]$GameDir = "$PSScriptRoot\\..\\game")',
             'param([switch]$NoLaunch, [string]$GameDir = "' + GAME + '",\n'
             '      [string]$Exe = "i76_pristine_fix.exe", [string]$ProcName = "i76_pristine_fix",\n'
             '      [string]$CaptureId = ("launch-" + (Get-Date -Format "yyyyMMdd-HHmmss")), [int]$SettleSeconds = 9)', 1),
            ('. "$PSScriptRoot\\lib\\focuslib.ps1"; . "$PSScriptRoot\\lib\\inputlib.ps1"; . "$PSScriptRoot\\lib\\maplib.ps1"; . "$PSScriptRoot\\lib\\memlib.ps1"',
             '$AutotestLib = "' + LIB + '"   # (a)\n'
             '. "$AutotestLib\\focuslib.ps1"; . "$AutotestLib\\inputlib.ps1"; . "$AutotestLib\\maplib.ps1"; . "$AutotestLib\\memlib.ps1"\n' + GAMEPID + MEMOPEN, 1),
            ("    Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue\n    Start-Sleep -Seconds 2\n"
             "    Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir\n"
             "    Start-Sleep -Seconds 9\n",
             "    Get-GamePid | Stop-Process -Force -EA SilentlyContinue\n    Start-Sleep -Seconds 2\n" + LAUNCH, 1),
        ]
    elif name == "enter-training.ps1":
        edits += [
            ("enter-training.ps1 — launch into", "enter-training-pristine.ps1 - launch (via tools\\launch.ps1, H0 build i76_pristine_fix.exe) into", 1),
            ('param([switch]$NoLaunch, [switch]$NoStop, [string]$GameDir = "$PSScriptRoot\\..\\game")',
             'param([switch]$NoLaunch, [switch]$NoStop, [string]$GameDir = "' + GAME + '",\n'
             '      [string]$Exe = "i76_pristine_fix.exe", [string]$ProcName = "i76_pristine_fix",\n'
             '      [string]$CaptureId = ("launch-" + (Get-Date -Format "yyyyMMdd-HHmmss")), [int]$SettleSeconds = 9)', 1),
            ('. "$PSScriptRoot\\lib\\focuslib.ps1"; . "$PSScriptRoot\\lib\\inputlib.ps1"\n'
             '. "$PSScriptRoot\\lib\\maplib.ps1";   . "$PSScriptRoot\\lib\\memlib.ps1"\n'
             '. "$PSScriptRoot\\lib\\simlib.ps1"',
             '$AutotestLib = "' + LIB + '"   # (a)\n'
             '. "$AutotestLib\\focuslib.ps1"; . "$AutotestLib\\inputlib.ps1"\n'
             '. "$AutotestLib\\maplib.ps1";   . "$AutotestLib\\memlib.ps1"\n'
             '. "$AutotestLib\\simlib.ps1"\n' + GAMEPID + MEMOPEN, 1),
            ("    Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue\n    Start-Sleep -Seconds 2\n"
             "    Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir\n"
             "    Start-Sleep -Seconds 9\n",
             "    Get-GamePid | Stop-Process -Force -EA SilentlyContinue\n    Start-Sleep -Seconds 2\n" + LAUNCH, 1),
        ]
    # common: first pid lookup + cursor-map sync, and every blocking focus call
    edits += [
        ('$proc = Get-GamePid; if (-not $proc) { throw "game not running" }\nForce-Foreground $proc.MainWindowHandle | Out-Null\n',
         '$proc = Get-GamePid; if (-not $proc) { throw "game not running ($ProcName under i76-uncap-lab; launch with tools\\launch.ps1 first)" }\n'
         'Sync-CursorMap $proc   # (f)\n'
         'Focus-Game $proc | Out-Null\n', 1),
        ("Force-Foreground $proc.MainWindowHandle|Out-Null", "Focus-Game $proc|Out-Null", None),
        ("Force-Foreground $proc.MainWindowHandle | Out-Null", "Focus-Game $proc | Out-Null", None),
    ]
    return apply(src, edits, dst_name)


def port_record_replay(name, dst_name):
    src = open(os.path.join(SRC, name), "rb").read().decode("utf-8")
    common = [
        ("$lab  = Split-Path $PSScriptRoot -Parent", "$lab  = '" + LAB + "'   # harness lives in i76-map; the lab tree holds src\\ and captures\\inputs", None),
        ("$lab = Split-Path $PSScriptRoot -Parent", "$lab = '" + LAB + "'   # harness lives in i76-map; the lab tree holds src\\ and captures\\inputs", None),
        ("(Join-Path $PSScriptRoot 'enter-training.ps1')", "(Join-Path $PSScriptRoot 'enter-training-pristine.ps1')", None),
        ("(Join-Path $PSScriptRoot 'enter-melee.ps1')", "(Join-Path $PSScriptRoot 'enter-melee-pristine.ps1')", None),
        ("(Join-Path $PSScriptRoot 'enter-mission5.ps1')", "(Join-Path $PSScriptRoot 'enter-mission5-pristine.ps1')", None),
        ("Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like '*i76-uncap-lab*' } | Select-Object -First 1",
         "Get-Process -Name i76_pristine_fix -EA SilentlyContinue | Where-Object { $_.Path -like '*i76-uncap-lab*' } | Select-Object -First 1", None),
    ]
    if name == "record-session.ps1":
        edits = [
            ("record-session.ps1 \u2014 record YOUR input",
             "record-session-pristine.ps1 - record YOUR input\n\n"
             "  HARNESS PORT (tools\\harness\\make-harness.py). WARNING: this injects src\\i76uncap.dll into the process, so\n"
             "  the run is class `patched-build-only` under gate H0 (which_build.py reports the injected module); never use it\n"
             "  for a capture that must carry the pristine+i76fix-p1 stamp. Entry scripts are the -pristine ports.", 1),
            ("    autotest\\record-session.ps1 -To Training -Label jump", "    tools\\harness\\record-session-pristine.ps1 -To Training -Label jump", 1),
            ("    autotest\\record-session.ps1 -To MeleeForm -Label equip-flamer", "    tools\\harness\\record-session-pristine.ps1 -To MeleeForm -Label equip-flamer", 1),
            ("    autotest\\record-session.ps1 -To Mission5Garage -Label equip-m5", "    tools\\harness\\record-session-pristine.ps1 -To Mission5Garage -Label equip-m5", 1),
            ('Write-Host ("replay with:  autotest\\replay-session.ps1 -Label {0} -Fps 20" -f $Label)',
             'Write-Host ("replay with:  tools\\harness\\replay-session-pristine.ps1 -Label {0} -Fps 20" -f $Label)', 1),
        ] + common
    else:
        edits = [
            ("replay-session.ps1 \u2014 reproduce a recorded session",
             "replay-session-pristine.ps1 - reproduce a recorded session\n\n"
             "  HARNESS PORT (tools\\harness\\make-harness.py). WARNING: injects src\\i76uncap.dll -> gate H0 class\n"
             "  `patched-build-only`; not for pristine-stamped captures. Entry scripts are the -pristine ports.", 1),
            ("      autotest\\replay-session.ps1 -Label jump -Fps 20 -Trace", "      tools\\harness\\replay-session-pristine.ps1 -Label jump -Fps 20 -Trace", 1),
            ("      autotest\\replay-session.ps1 -Label jump -Fps 60 -Trace", "      tools\\harness\\replay-session-pristine.ps1 -Label jump -Fps 60 -Trace", 1),
            ('. "$PSScriptRoot\\lib\\focuslib.ps1"\n$p2 = Get-GamePid\nForce-Foreground $p2.MainWindowHandle | Out-Null',
             '. "' + LIB + '\\focuslib.ps1"\n'
             'function Get-GamePid { Get-Process -Name i76_pristine_fix -EA SilentlyContinue | Where-Object { $_.Path -like \'*i76-uncap-lab*\' } | Select-Object -First 1 }\n'
             '$p2 = Get-GamePid\n'
             'if (Test-WindowPumping $p2.MainWindowHandle) { Force-Foreground $p2.MainWindowHandle | Out-Null } else { Write-Warning "game window not pumping - skipping focus" }', 1),
        ] + common
    return apply(src, edits, dst_name, strict=False)   # `common` lists both $lab spellings; each file has one


def apply(src, edits, dst_name, strict=True):
    text = src.replace("\r\n", "\n")
    ledger = []
    for old, new, expect in edits:
        n = text.count(old)
        if expect is not None and n != expect:
            raise SystemExit("%s: expected %d occurrence(s) of %r, found %d" % (dst_name, expect, old[:60], n))
        if strict and n == 0:
            raise SystemExit("%s: 0 occurrences of %r" % (dst_name, old[:60]))
        text = text.replace(old, new)
        ledger.append((old[:50].replace("\n", "\\n"), n))
    # header stamp so nobody edits the output by hand
    stamp = ("# GENERATED by tools\\harness\\make-harness.py from autotest\\%s - edit the generator, not this file.\n" % dst_name.replace("-pristine", ""))
    text = stamp + text
    # em dashes elsewhere -> ASCII
    text = text.replace("\u2014", "-").replace("\u2192", "->")
    data = text.replace("\n", "\r\n").encode("ascii")   # raises on any non-ASCII byte (G-ENC)
    return data, ledger


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    outputs = {
        "enter-melee-pristine.ps1": port_entry("enter-melee.ps1", "enter-melee-pristine.ps1", [], False),
        "enter-mission5-pristine.ps1": port_entry("enter-mission5.ps1", "enter-mission5-pristine.ps1", ["memlib", "simlib"], True),
        "enter-trip1-pristine.ps1": port_entry("enter-trip1.ps1", "enter-trip1-pristine.ps1", ["memlib"], True),
        "record-session-pristine.ps1": port_record_replay("record-session.ps1", "record-session-pristine.ps1"),
        "replay-session-pristine.ps1": port_record_replay("replay-session.ps1", "replay-session-pristine.ps1"),
    }
    if os.path.exists(os.path.join(SRC, "enter-training.ps1")):
        outputs["enter-training-pristine.ps1"] = port_entry("enter-training.ps1", "enter-training-pristine.ps1", ["memlib", "simlib"], True)
    rc = 0
    for name, (data, ledger) in outputs.items():
        path = os.path.join(DST, name)
        if a.check:
            on_disk = open(path, "rb").read() if os.path.exists(path) else b""
            same = on_disk == data
            print("%-32s %s (%d B)" % (name, "same" if same else "DIFFERS", len(data)))
            if not same:
                rc = 1
            continue
        with open(path, "wb") as f:
            f.write(data)
        back = open(path, "rb").read()          # H3 read-back
        assert back == data, name
        print("%-32s %6d B  edits: %s" % (name, len(data), ", ".join("%r x%d" % e for e in ledger)))
    sys.exit(rc)


if __name__ == "__main__":
    main()
