<#
  Build the USER32 proxy (u32x.dll) from u32x_min.c + u32x.def with MSVC x86.

  NON-DESTRUCTIVE: the result is written to u32x.build.dll and the committed, live-verified
  u32x.dll is left alone. A rebuild has a new md5 (MSVC stamps the link time), so it is a new,
  UNVERIFIED binary until it has been run on the sandbox (README.md "Promoting a rebuild").
  -Replace overwrites u32x.dll with the build; do that only after the sandbox run, and update
  the md5 in README.md and deploy-u32x.ps1 ($KnownGood) in the same commit.

      powershell -ExecutionPolicy Bypass -File u32x\build.ps1            # -> u32x.build.dll
      powershell -ExecutionPolicy Bypass -File u32x\build.ps1 -Replace   # -> u32x.dll

  Needs the Visual Studio C++ x86 tools (vcvars32.bat). The game is 32-bit; an x64 DLL does
  not load and the failure looks like a game bug, so the PE machine field is checked.
#>
param([switch]$Replace)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$tmp  = Join-Path $here 'u32x.build.dll'
$out  = Join-Path $here 'u32x.dll'
$log  = Join-Path $here 'build.log'

$vcvars = $null
foreach ($root in @("${env:ProgramFiles(x86)}\Microsoft Visual Studio", "${env:ProgramFiles}\Microsoft Visual Studio")) {
    if (-not $root -or -not (Test-Path $root)) { continue }
    $f = Get-ChildItem $root -Recurse -Filter 'vcvars32.bat' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($f) { $vcvars = $f.FullName; break }
}
if (-not $vcvars) { Write-Host "vcvars32.bat not found - install the Visual Studio C++ x86 build tools." -ForegroundColor Red; exit 1 }

if (Test-Path $tmp) { Remove-Item $tmp -Force }
# Redirect INSIDE cmd, never `2>&1` in PowerShell: vcvars32.bat prints a benign
# "'vswhere.exe' is not recognized" to stderr, which PowerShell 5.1 turns into a
# NativeCommandError and, under ErrorActionPreference Stop, into an abort of a clean build.
# The parentheses matter: without them the redirect binds to the last command only and
# vcvars' stderr still reaches PowerShell.
$cmd = "call `"$vcvars`" && cd /d `"$here`" && " +
       "cl /nologo /O2 /LD u32x_min.c /Fo:u32x.build.obj /link /DEF:u32x.def user32.lib /OUT:u32x.build.dll"
$ErrorActionPreference = 'Continue'
& cmd.exe /c "($cmd) > `"$log`" 2>&1"
$ErrorActionPreference = 'Stop'
# LNK4070 is expected: the .def says LIBRARY u32x (the name the game imports) and the scratch output is u32x.build.dll.
Get-Content $log -ErrorAction SilentlyContinue | Select-String 'warning|error' | Where-Object { $_ -notmatch 'LNK4070|vswhere' } |
    ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
if (-not (Test-Path $tmp)) {
    Write-Host "BUILD FAILED - tail of $log" -ForegroundColor Red
    Get-Content $log -Tail 15 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed }
    exit 1
}

$b = [IO.File]::ReadAllBytes($tmp)
$pe = [BitConverter]::ToInt32($b, 0x3c)
$machine = [BitConverter]::ToUInt16($b, $pe + 4)
if ($machine -ne 0x14c) { Write-Host ("ABORT: built for 0x{0:X}, the game is 32-bit (0x14C)." -f $machine) -ForegroundColor Red; exit 1 }
# The one behavioural change over the 2026-08-16 build is this call; its name must be in the image.
$txt = [Text.Encoding]::ASCII.GetString($b)
if ($txt.IndexOf('DisableProcessWindowsGhosting') -lt 0) { Write-Host "ABORT: no DisableProcessWindowsGhosting string in the build." -ForegroundColor Red; exit 1 }
$md5 = (Get-FileHash $tmp -Algorithm MD5).Hash.ToLower()
Write-Host ("Built u32x.build.dll  {0} bytes  x86  md5 {1}" -f $b.Length, $md5) -ForegroundColor Green
Remove-Item (Join-Path $here 'u32x.build.obj'), (Join-Path $here 'u32x.build.lib'), (Join-Path $here 'u32x.build.exp') -ErrorAction SilentlyContinue

if ($Replace) {
    Move-Item $tmp $out -Force
    Write-Host "u32x.dll REPLACED by this build (md5 $md5)." -ForegroundColor Yellow
    Write-Host "It is unverified until run on the sandbox. Update README.md and `$KnownGood in deploy-u32x.ps1." -ForegroundColor Yellow
} else {
    Write-Host "u32x.dll (the verified binary) was not touched. Test the build on the sandbox:" -ForegroundColor DarkGray
    Write-Host "  u32x\deploy-u32x.ps1 -GameDir ..\i76-uncap-lab\game -U32xDll u32x\u32x.build.dll -AllowUnverified" -ForegroundColor DarkGray
}
