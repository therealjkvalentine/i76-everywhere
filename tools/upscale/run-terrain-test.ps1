<#
  run-terrain-test.ps1 - in-game A/B of an upscaled terrain set (terrain_pack.py) in the lab copy game-tex
  (sprint 2026-10-03 TERRAIN1). Never touches I76.ZFS, the sandbox (game) or any daily-driver install.

  Conditions (each one boot of -Mission through autotest\proxy-run.ps1, captures start view + F3 + F4):
    marker   ADDON\tp04m6.* = the magenta-X marker pack (proves the loose ADDON terrain override loads)
    stock    the set's ADDON override moved aside (I76.ZFS terrain)
    pack     the upscaled pack as installed in ADDON
  Append "-tt8" to a condition (e.g. stock-tt8) to run with I76_TERRAIN_TEX=8 (256 px level pushed to 400 m,
  far levels to 400..3200 m).

    .\run-terrain-test.ps1 -Conditions marker,stock,pack,stock-tt8,pack-tt8

  Follows i76-uncap-lab\CONSOLE-LOCK.md (exclusive .console-owner, no i76 process, no .console-test.lock; owner
  file and ADDON state restored in finally). Captures: i76-uncap-lab\captures\terrain1\<stamp>-<cond>-*.png
  (gitignored decoded game art).
#>
param(
    [string[]]$Conditions = @("marker", "stock", "pack", "stock-tt8", "pack-tt8"),
    [string]$Set = "tp04",
    [string]$Mission = "t01",
    [string]$MarkerDir = "C:\Users\james\i76-upscale-work\runs\terrain1\marker",
    [string]$Owner = "TERRAIN1 terrain-pack",
    [string]$ProxyDll = "C:\Users\james\i76-uncap-lab\game-tex\Strlkup.u5test.dll"
)
$ErrorActionPreference = "Stop"
$Lab = "C:\Users\james\i76-uncap-lab"
$G = Join-Path $Lab "game-tex"
$Addon = Join-Path $G "ADDON"
$Aside = Join-Path $Addon ".terrain-test-aside"
$OwnerFile = Join-Path $Lab ".console-owner"
$capDir = Join-Path $Lab "captures\terrain1"
New-Item -ItemType Directory -Force $capDir, $Aside | Out-Null
$names = "${Set}m6.pak", "${Set}m6.pix"

if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { throw "an i76 process is running: console busy" }
foreach ($d in "game", "game-alt", "game-dd-20261003") {
    if (Test-Path (Join-Path $Lab "$d\.console-test.lock")) { throw "$d\.console-test.lock exists: console busy" }
}
New-Item -ItemType File -Path $OwnerFile -ErrorAction Stop | Out-Null
Set-Content $OwnerFile "$Owner $(Get-Date -Format s)"
# keep the installed pack aside for the whole batch; each condition copies in what it needs
foreach ($n in $names) { Copy-Item (Join-Path $Addon $n) (Join-Path $Aside $n) -Force }
try {
    foreach ($cond in $Conditions) {
        $base = $cond -replace "-tt8$", ""
        foreach ($n in $names) { Remove-Item (Join-Path $Addon $n) -ErrorAction SilentlyContinue }
        if ($base -eq "pack") { foreach ($n in $names) { Copy-Item (Join-Path $Aside $n) (Join-Path $Addon $n) } }
        elseif ($base -eq "marker") { foreach ($n in $names) { Copy-Item (Join-Path $MarkerDir $n) (Join-Path $Addon $n) } }
        elseif ($base -ne "stock") { throw "unknown condition $cond" }
        $md5 = if (Test-Path (Join-Path $Addon $names[0])) { (Get-FileHash (Join-Path $Addon $names[0]) -Algorithm MD5).Hash.ToLower() } else { "(none)" }
        $env:I76_TERRAIN_TEX = $null; Remove-Item Env:I76_TERRAIN_TEX -ErrorAction SilentlyContinue
        $extra = @{}
        if ($cond -like "*-tt8") { $extra["I76_TERRAIN_TEX"] = "8" }
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        "[$cond] ADDON $($names[0]) md5 $md5; env $(($extra.Keys | ForEach-Object { "$_=$($extra[$_])" }) -join ' ')"
        $Tag = $cond
        $run = {
            $cf = "C:\Users\james\i76-uncap-lab\tools\graphics\capture-frame.ps1"
            Start-Sleep -Seconds 5
            & $cf -Out (Join-Path $capDir "$stamp-$Tag-start.png")
            Send-Key 0x72; Start-Sleep -Seconds 2          # F3 = PRESET_VIEW_3
            & $cf -Out (Join-Path $capDir "$stamp-$Tag-F3.png")
            Send-Key 0x73; Start-Sleep -Seconds 2          # F4 = PRESET_VIEW_12
            & $cf -Out (Join-Path $capDir "$stamp-$Tag-F4.png")
        }
        & (Join-Path $Lab "autotest\proxy-run.ps1") -GameDir $G -Dll $ProxyDll -Mission $Mission -Hold 2 -Run $run -Env $extra
        Start-Sleep -Seconds 3
    }
} finally {
    foreach ($n in $names) { Copy-Item (Join-Path $Aside $n) (Join-Path $Addon $n) -Force }
    Remove-Item $OwnerFile -ErrorAction SilentlyContinue
    "console released; ADDON pack restored; captures: $capDir"
}
