# build-msvc.ps1 - the MSVC x86 build of Strlkup.dll, standalone (build.ps1's MSVC branch aborts under
# $ErrorActionPreference='Stop' because vcvars32.bat prints a benign 'vswhere.exe is not recognized' to stderr).
# Builds to Strlkup.build.dll, verifies the PE machine field is 0x14c, then replaces Strlkup.dll. Prints warnings.
$d = $PSScriptRoot
$vc = Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio" -Recurse -Filter vcvars32.bat -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $vc) { Write-Host "no vcvars32.bat" -ForegroundColor Red; exit 1 }
Remove-Item "$d\Strlkup.build.dll" -ErrorAction SilentlyContinue
$cmd = "call `"$($vc.FullName)`" && cd /d `"$d`" && cl /nologo /LD /MT /O2 /W3 /D_CRT_SECURE_NO_WARNINGS strlkproxy.c /Fe:Strlkup.build.dll /link user32.lib"
cmd.exe /c "$cmd > `"$d\build.log`" 2>&1"
Get-Content "$d\build.log" | Select-String "warning|error" | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
if (-not (Test-Path "$d\Strlkup.build.dll")) { Write-Host "BUILD FAILED" -ForegroundColor Red; Get-Content "$d\build.log" -Tail 15; exit 1 }
$b = [IO.File]::ReadAllBytes("$d\Strlkup.build.dll"); $pe = [BitConverter]::ToInt32($b, 0x3c); $m = [BitConverter]::ToUInt16($b, $pe + 4)
if ($m -ne 0x14c) { Write-Host ("WRONG ARCH 0x{0:X}" -f $m) -ForegroundColor Red; exit 1 }
Move-Item "$d\Strlkup.build.dll" "$d\Strlkup.dll" -Force
Write-Host "Built Strlkup.dll ($($b.Length) bytes, x86)" -ForegroundColor Green
