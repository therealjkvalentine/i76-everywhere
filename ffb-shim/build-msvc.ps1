# build-msvc.ps1 [-OutDir <dir>] - the MSVC x86 build of the ffb-shim (I7_SFRCE.DLL) for Windows hosts without mingw
# (2026-10-25, Deck lane: the Deck runs it under Proton). Static CRT (/MT), exports from i7_sfrce.def, x86 checked.
# Same source as build.sh (mingw, the Mac's); DllMain is the entry under _MSC_VER. No binary is committed.
param([string]$OutDir = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$vc = 'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars32.bat'
if (-not (Test-Path -LiteralPath $vc)) { Write-Host "no VS 2019 Build Tools (x86) at $vc"; exit 1 }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$src = Join-Path $PSScriptRoot 'i7ffshim.c'; $out = Join-Path $OutDir 'I7_SFRCE.DLL'
# MSVC's .def takes the undecorated internal name (the linker adds _ and @n); i7_sfrce.def is mingw's spelling.
$def = Join-Path $OutDir 'i7_sfrce.msvc.def'
(Get-Content -LiteralPath (Join-Path $PSScriptRoot 'i7_sfrce.def')) -replace '"(I7FF_\w+)" = (shim_\w+)@\d+', '$1 = $2' | Set-Content -LiteralPath $def -Encoding ascii
Remove-Item -LiteralPath $out -ErrorAction SilentlyContinue
Push-Location $OutDir
try {
    cmd /c "`"$vc`" >nul 2>nul && cl /nologo /O2 /MT /LD /W3 /D_CRT_SECURE_NO_WARNINGS `"$src`" /Fe:`"$out`" /link /DEF:`"$def`" /BREPRO ws2_32.lib user32.lib kernel32.lib 2>&1" | Select-Object -Last 6
} finally { Pop-Location }
if (-not (Test-Path -LiteralPath $out)) { Write-Host 'build failed'; exit 1 }
$b = [IO.File]::ReadAllBytes($out); $pe = [BitConverter]::ToInt32($b, 0x3c); $m = [BitConverter]::ToUInt16($b, $pe + 4)
if ($m -ne 0x14c) { Write-Host ('not x86 (machine 0x{0:x})' -f $m); exit 1 }
"built: $out  md5 $((Get-FileHash -LiteralPath $out -Algorithm MD5).Hash.ToLower())"
