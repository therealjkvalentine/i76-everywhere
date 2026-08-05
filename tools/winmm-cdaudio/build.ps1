<#
  build.ps1 - compile the 32-bit winmm proxy.

  Needs MSVC. This machine has Visual Studio 2019 Build Tools with an x86
  cross-compiler at
      Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC\<ver>\bin\Hostx64\x86\cl.exe
  which is found automatically below - `cl.exe` is not on PATH, and its absence
  from PATH is not the same as its absence from the machine (an assumption that
  wasted a round here).

  MUST BE 32-BIT. i76.exe is a 32-bit process and will not load a 64-bit DLL.
  The build asserts this on the output rather than trusting the toolchain choice.

      tools\winmm-cdaudio\build.ps1
      tools\winmm-cdaudio\build.ps1 -Install     # also copy into the game folder
#>
param(
    [switch]$Install,
    [string]$GameDir = ""
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# ---- find the x86 toolchain ----------------------------------------------
$vcvars = $null
foreach ($root in @(
    "${env:ProgramFiles}\Microsoft Visual Studio",
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio")) {
    if (-not (Test-Path $root)) { continue }
    $found = Get-ChildItem -Path $root -Recurse -Filter 'vcvars32.bat' -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if ($found) { $vcvars = $found.FullName; break }
}
if (-not $vcvars) {
    Write-Host "Could not find vcvars32.bat - MSVC with the C++ x86 toolchain is required." -ForegroundColor Red
    Write-Host "Install 'Desktop development with C++' in the Visual Studio Installer." -ForegroundColor Yellow
    exit 1
}
Write-Host "toolchain: $vcvars" -ForegroundColor DarkGray

# ---- compile -------------------------------------------------------------
# /LD   build a DLL
# /MT   static CRT, so the game folder needs no redistributable beside it
# /DEF  export the nine names the game imports, undecorated
#
# DELIBERATELY NOT linking winmm.lib: that would put an import on winmm.dll into
# a DLL *named* winmm.dll, i.e. an import on itself. Everything from the real
# winmm is resolved at runtime by GetProcAddress on an absolute path instead.
$src = Join-Path $here 'winmm_proxy.c'
$def = Join-Path $here 'winmm.def'
$out = Join-Path $here 'winmm.dll'
$log = Join-Path $here 'build.log'

# Redirection happens INSIDE cmd, writing straight to the log, and stderr is NOT
# piped back through PowerShell. Two reasons:
#   * `& cmd.exe ... 2>&1` wraps every stderr line in an ErrorRecord
#     (NativeCommandError), which with $ErrorActionPreference='Stop' aborts this
#     script even when the compiler succeeded. That happened here: vcvars32.bat
#     emits a benign "'vswhere.exe' is not recognized" warning, and the build died
#     on it before writing any log at all.
#   * `call vcvars32.bat` must not be gated behind && on its own exit code, since
#     it can warn and still set the environment correctly.
$cmd = "call `"$vcvars`" && cd /d `"$here`" && " +
       "cl /nologo /LD /MT /O2 /W3 /D_CRT_SECURE_NO_WARNINGS `"$src`" /Fe:`"$out`" " +
       "/link /DEF:`"$def`" user32.lib"

Write-Host "compiling..." -ForegroundColor Cyan
if (Test-Path $out) { Remove-Item $out -Force }
& cmd.exe /c "$cmd > `"$log`" 2>&1"
$fail = -not (Test-Path $out)
$output = if (Test-Path $log) { Get-Content $log } else { @() }

if ($fail -or -not (Test-Path $out)) {
    Write-Host "BUILD FAILED - see $log" -ForegroundColor Red
    $output | Select-Object -Last 25 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed }
    exit 1
}

# ---- verify it is a 32-bit DLL exporting the right nine ------------------
# The whole thing is inert if the architecture is wrong, and a 64-bit DLL in the
# game folder fails to load with an error that looks like a game problem.
$bytes = [System.IO.File]::ReadAllBytes($out)
$peOff = [BitConverter]::ToInt32($bytes, 0x3c)
$machine = [BitConverter]::ToUInt16($bytes, $peOff + 4)
$arch = switch ($machine) { 0x14c { 'x86 (32-bit)' } 0x8664 { 'x64 (64-BIT - WRONG)' } default { "unknown 0x$('{0:X}' -f $machine)" } }
Write-Host ("built {0}  ({1} bytes, {2})" -f $out, $bytes.Length, $arch) -ForegroundColor Green
if ($machine -ne 0x14c) { Write-Host "ABORT: i76.exe is 32-bit and cannot load this." -ForegroundColor Red; exit 1 }

$expected = @('mciSendCommandA','mciGetErrorStringA','auxGetDevCapsA','auxGetNumDevs',
              'auxSetVolume','joyGetDevCapsA','joyGetNumDevs','joyGetPosEx','timeGetTime')
$dumpbin = Get-ChildItem -Path (Split-Path (Split-Path $vcvars)) -Recurse -Filter 'dumpbin.exe' -ErrorAction SilentlyContinue |
           Select-Object -First 1
if ($dumpbin) {
    $ex = & cmd.exe /c "call `"$vcvars`" >nul && `"$($dumpbin.FullName)`" /EXPORTS `"$out`"" 2>&1
    $missing = @($expected | Where-Object { -not ($ex -match [regex]::Escape($_)) })
    if ($missing.Count) {
        Write-Host ("MISSING EXPORTS: {0}" -f ($missing -join ', ')) -ForegroundColor Red
        exit 1
    }
    Write-Host "all 9 exports present" -ForegroundColor Green
}

# ---- optional install ----------------------------------------------------
if ($Install) {
    if (-not $GameDir) {
        $p = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($p) { try { $GameDir = Split-Path $p.Path } catch { } }
    }
    if (-not $GameDir -or -not (Test-Path $GameDir)) {
        Write-Host "Pass -GameDir to install (or start the game first so it can be detected)." -ForegroundColor Yellow
        exit 0
    }
    if (-not (Test-Path (Join-Path $GameDir 'i76.exe'))) {
        Write-Host "$GameDir does not look like the game folder (no i76.exe)." -ForegroundColor Red
        exit 1
    }
    $dest = Join-Path $GameDir 'winmm.dll'
    if (Test-Path $dest) { Copy-Item $dest "$dest.bak" -Force }
    Copy-Item $out $dest -Force
    Write-Host "installed -> $dest" -ForegroundColor Green
    Write-Host "To undo: delete that file. Nothing else was changed." -ForegroundColor Cyan
    Write-Host "The game must be RESTARTED - DLLs are resolved at process start." -ForegroundColor Cyan
}
