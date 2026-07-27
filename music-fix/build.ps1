<#
  Build the base-game in-mission music fix: a proxy Strlkup.dll that IAT-hooks
  the game's cdaudio MCI calls and plays GOG's music\N.mp3 instead. See README.md.

  Needs a 32-bit GCC (w64devkit). A prebuilt Strlkup.dll is committed beside this
  script, so building is only necessary if you change strlkproxy.c.

  Usage:  ./build.ps1 [-Gcc "C:\Games\_tools\w64devkit\bin\gcc.exe"]
#>
param([string]$Gcc = "C:\Games\_tools\w64devkit\bin\gcc.exe")
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
if (-not (Test-Path $Gcc)) {
    Write-Host "32-bit gcc not found at $Gcc." -ForegroundColor Red
    Write-Host "Install w64devkit (https://github.com/skeeto/w64devkit/releases) or pass -Gcc."
    exit 1
}
# All winmm entry points are resolved at runtime via GetProcAddress, so no -lwinmm.
& $Gcc -m32 -O2 -s -shared -o (Join-Path $here 'Strlkup.dll') `
      (Join-Path $here 'strlkproxy.c') (Join-Path $here 'strlkup.def')
if ($LASTEXITCODE) { throw "build failed ($LASTEXITCODE)" }
Write-Host "Built Strlkup.dll -> $here" -ForegroundColor Green
