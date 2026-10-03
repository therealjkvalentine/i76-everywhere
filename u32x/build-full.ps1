<#
  Build the full USER32 proxy from u32x_full.c + u32x_full.def with MSVC x86, and compare the
  result with the committed, gated binary u32x_full.dll (md5 054fb411).

  NON-DESTRUCTIVE: the result is written to u32x_full.build.dll. u32x_full.dll is never
  written by this script. A rebuild has a new md5 because MSVC stamps the link time in two
  places (the PE header and the debug directory); the script reports whether those are the
  only bytes that differ. A rebuild is a new, UNVERIFIED binary until it has been through the
  gate (README.md "Promoting a rebuild").

      powershell -ExecutionPolicy Bypass -File u32x\build-full.ps1

  Port of ..\i76-uncap-lab\src\build-u32x.ps1 (same compiler line; only the file names differ).
  Needs the Visual Studio C++ x86 tools (vcvars32.bat). The gated binary was built with
  Visual Studio 2019 Build Tools (linker 14.29); another compiler version will differ in code
  bytes, not only in the stamps.
#>
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$tmp  = Join-Path $here 'u32x_full.build.dll'
$ref  = Join-Path $here 'u32x_full.dll'
$log  = Join-Path $here 'build-full.log'

$vcvars = $null
foreach ($root in @("${env:ProgramFiles(x86)}\Microsoft Visual Studio", "${env:ProgramFiles}\Microsoft Visual Studio")) {
    if (-not $root -or -not (Test-Path $root)) { continue }
    $f = Get-ChildItem $root -Recurse -Filter 'vcvars32.bat' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($f) { $vcvars = $f.FullName; break }
}
if (-not $vcvars) { Write-Host "vcvars32.bat not found - install the Visual Studio C++ x86 build tools." -ForegroundColor Red; exit 1 }

if (Test-Path $tmp) { Remove-Item $tmp -Force }
# Redirect INSIDE cmd, never `2>&1` in PowerShell (see build.ps1 for why).
$cmd = "call `"$vcvars`" && cd /d `"$here`" && " +
       "cl /nologo /O2 /LD u32x_full.c /Fo:u32x_full.build.obj /link /DEF:u32x_full.def user32.lib /OUT:u32x_full.build.dll"
$ErrorActionPreference = 'Continue'
& cmd.exe /c "($cmd) > `"$log`" 2>&1"
$ErrorActionPreference = 'Stop'
# LNK4070 is expected: the .def says LIBRARY u32x (the name the game imports) and the output is u32x_full.build.dll.
Get-Content $log -ErrorAction SilentlyContinue | Select-String 'warning|error' | Where-Object { $_ -notmatch 'LNK4070|vswhere' } |
    ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
if (-not (Test-Path $tmp)) {
    Write-Host "BUILD FAILED - tail of $log" -ForegroundColor Red
    Get-Content $log -Tail 15 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed }
    exit 1
}
Remove-Item (Join-Path $here 'u32x_full.build.obj'), (Join-Path $here 'u32x_full.build.lib'), (Join-Path $here 'u32x_full.build.exp') -ErrorAction SilentlyContinue

$b = [IO.File]::ReadAllBytes($tmp)
$pe = [BitConverter]::ToInt32($b, 0x3c)
$machine = [BitConverter]::ToUInt16($b, $pe + 4)
if ($machine -ne 0x14c) { Write-Host ("ABORT: built for 0x{0:X}, the game is 32-bit (0x14C)." -f $machine) -ForegroundColor Red; exit 1 }
$md5 = (Get-FileHash $tmp -Algorithm MD5).Hash.ToLower()
Write-Host ("Built u32x_full.build.dll  {0} bytes  x86  md5 {1}" -f $b.Length, $md5) -ForegroundColor Green

# ---- compare with the gated binary: which bytes differ, and are they only link-time stamps? ----
if (-not (Test-Path $ref)) { Write-Host "u32x_full.dll is not here; nothing to compare with." -ForegroundColor Yellow; exit 0 }
$r = [IO.File]::ReadAllBytes($ref)
$refMd5 = (Get-FileHash $ref -Algorithm MD5).Hash.ToLower()
if ($md5 -eq $refMd5) { Write-Host "IDENTICAL to u32x_full.dll (md5 $refMd5)." -ForegroundColor Green; exit 0 }
if ($r.Length -ne $b.Length) {
    Write-Host ("DIFFERENT SIZE: u32x_full.dll is {0} bytes. This is not the same build (other source or other compiler)." -f $r.Length) -ForegroundColor Red
    exit 2
}
function Rva-Off([byte[]]$img, [int]$peOff, [uint32]$rva) {
    $nsec = [BitConverter]::ToUInt16($img, $peOff + 6); $st = $peOff + 24 + [BitConverter]::ToUInt16($img, $peOff + 20)
    for ($i = 0; $i -lt $nsec; $i++) {
        $o = $st + 40 * $i
        $va = [BitConverter]::ToUInt32($img, $o + 12); $rs = [BitConverter]::ToUInt32($img, $o + 16); $raw = [BitConverter]::ToUInt32($img, $o + 20)
        if ($rva -ge $va -and $rva -lt ($va + $rs)) { return [int]($rva - $va + $raw) }
    }
    -1
}
# The stamp fields: PE header TimeDateStamp, each debug-directory entry's stamp, the export directory's stamp.
$stamp = New-Object 'System.Collections.Generic.HashSet[int]'
foreach ($k in 0..3) { [void]$stamp.Add($pe + 8 + $k) }
$opt = $pe + 24
$dbgRva = [BitConverter]::ToUInt32($r, $opt + 144); $dbgSize = [BitConverter]::ToUInt32($r, $opt + 148)
if ($dbgRva) { $d = Rva-Off $r $pe $dbgRva; if ($d -ge 0) { for ($e = 0; $e -lt $dbgSize; $e += 28) { foreach ($k in 0..3) { [void]$stamp.Add($d + $e + 4 + $k) } } } }
$expRva = [BitConverter]::ToUInt32($r, $opt + 96)
if ($expRva) { $d = Rva-Off $r $pe $expRva; if ($d -ge 0) { foreach ($k in 0..3) { [void]$stamp.Add($d + 4 + $k) } } }
$diff = 0; $outside = 0
for ($i = 0; $i -lt $r.Length; $i++) { if ($r[$i] -ne $b[$i]) { $diff++; if (-not $stamp.Contains($i)) { $outside++ } } }
if ($outside -eq 0) {
    Write-Host ("Same build as u32x_full.dll (md5 $refMd5) apart from the link time: $diff bytes differ, all inside the time stamps.") -ForegroundColor Green
} else {
    Write-Host ("DIFFERS from u32x_full.dll in $diff bytes, $outside of them outside the time stamps: not the same code (other compiler version?).") -ForegroundColor Red
    exit 2
}
Write-Host "u32x_full.dll (the gated binary) was not touched." -ForegroundColor DarkGray
