<#
  build-proxy.ps1 - build the proxy Strlkup.dll (music-fix\) from a COMMIT of this repo, the recipe every staged / shipped build
  uses (lab builds\nitro-port-20261021\build.ps1, moved here 2026-10-23 so the repo can build itself): git archive of music-fix +
  the two shared headers at -Ref, MSVC x86 /LD /MT /O2 /W3 /Brepro (VS 2019 Build Tools, vcvars32.bat). Never touches
  music-fix\Strlkup.dll in the working tree. Deterministic: the same commit gives the same bytes (/Brepro).

    tools\build-proxy.ps1 -Ref 9fe3510 -OutDir C:\builds\proxy-9fe3510       # -> <OutDir>\Strlkup.dll (+ src\, build.log)
  Prints "built <path> md5 <md5>"; exit 1 on a failed build. Used by tools\Build-From-GOG.ps1.
#>
param([string]$Ref = 'HEAD', [Parameter(Mandatory)][string]$OutDir,
      [string]$VcVars = 'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars32.bat')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $VcVars)) { Write-Host "build-proxy: MSVC not found ($VcVars) - install the VS 2019 Build Tools (C++ x86) or pass -VcVars" -ForegroundColor Red; exit 1 }
$sha = (git -C $repo rev-parse --short $Ref).Trim()
if (Test-Path -LiteralPath $OutDir) { Remove-Item -LiteralPath $OutDir -Recurse -Force }
$src = Join-Path $OutDir 'src'; New-Item -ItemType Directory -Force $src | Out-Null
$tar = Join-Path $OutDir 'src.tar'
git -C $repo archive -o $tar $sha music-fix tools/telemetry/i76tel.h tools/trainer/i76trn.h
tar -xf $tar -C $src; Remove-Item $tar
Remove-Item (Join-Path $src 'music-fix\*.dll') -ErrorAction SilentlyContinue
$sha | Set-Content (Join-Path $src 'COMMIT')
$bat = Join-Path $OutDir 'b.bat'
@"
@call "$VcVars" >nul
cd /d "$src\music-fix"
cl /nologo /LD /MT /O2 /W3 /Brepro /D_CRT_SECURE_NO_WARNINGS strlkproxy.c /Fe:"$OutDir\Strlkup.dll" /Fo:"$OutDir\\" /link user32.lib /Brepro
"@ | Set-Content $bat -Encoding ascii
$ErrorActionPreference = 'Continue'
& cmd.exe /c "`"$bat`" > `"$OutDir\build.log`" 2>&1"
$ErrorActionPreference = 'Stop'
$dll = Join-Path $OutDir 'Strlkup.dll'
if (-not (Test-Path -LiteralPath $dll)) { Get-Content (Join-Path $OutDir 'build.log') -Tail 30; Write-Host 'build-proxy: build failed' -ForegroundColor Red; exit 1 }
"built $dll md5 $((Get-FileHash -LiteralPath $dll -Algorithm MD5).Hash.ToLower()) (commit $sha)"
