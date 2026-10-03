<#
  run-tex-scale-test.ps1 - the in-game test for "does the original game render an M16 texture larger than the file it
  replaces?" (lab docs\TEXTURE-DELIVERY.md section 5). Drives the lab copy game-tex only.

  Prepare once (writes 2x marker packs of every Piranha paint scheme into game-tex\ADDON; never touches I76.ZFS):
    python m16_scale_marker.py --game C:\Users\james\i76-uncap-lab\game-tex --out C:\Users\james\i76-uncap-lab\game-tex\ADDON `
        --pak pirana16 --pak pirana26 --pak pirana36 --pak pirana46 --scale 2

  Run (physical console, nothing else running the game):
    .\run-tex-scale-test.ps1                    # 2x marker packs as installed
    .\run-tex-scale-test.ps1 -Control           # same run with the pirana*6 overrides moved aside (stock paint)
    .\run-tex-scale-test.ps1 -Tag tmu16 -Conf C:\Users\james\i76-uncap-lab\game-tex\dgVoodoo.tmu16.conf -ZglideFix
                                                # 16 MB TMU conf + the 1-byte allocator fix, this run only

  Follows i76-uncap-lab\CONSOLE-LOCK.md: exclusive create of .console-owner, no i76 process, no .console-test.lock in
  game / game-alt / game-dd-20261003; the owner file is removed in finally. One run takes about a minute.
  Boots t01 through autotest\proxy-run.ps1 -KeepInstalledDll (game-tex's own STRLKUP.DLL, so a proxy rebuild in
  progress elsewhere cannot leak in), then captures the presented frame in the start view, after F3 and after F4
  (preset views 3 and 12; one of them is the chase view). Captures: i76-uncap-lab\captures\texscale\<stamp>-<tag>-*.png
  (captures\ is gitignored: decoded game art, never commit).
#>
param(
    [switch]$Control,
    [string]$Tag = "",
    [string]$Conf = "",
    [switch]$ZglideFix,            # run with game-tex\ZGLIDE.tmufix.dll (zglide_tmu_patch.py) in place of ZGLIDE.DLL
    [string]$Mission = "t01",
    [string]$Owner = "U5 texture-scale"
)
$ErrorActionPreference = "Stop"
$Lab = "C:\Users\james\i76-uncap-lab"
$G = Join-Path $Lab "game-tex"
$Addon = Join-Path $G "ADDON"
$Aside = Join-Path $Addon ".scale-test-aside"
$OwnerFile = Join-Path $Lab ".console-owner"
if (-not $Tag) { $Tag = if ($Control) { "control" } else { "marker2x" } }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$capDir = Join-Path $Lab "captures\texscale"
New-Item -ItemType Directory -Force $capDir | Out-Null

if (-not (Test-Path (Join-Path $G "i76.exe"))) { throw "no game-tex copy at $G (tools\renderers\make-renderer-copy.ps1 -Source ..\..\game-alt -Dest ..\..\game-tex -HardLinkAssets)" }
if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { throw "an i76 process is running: console busy" }
foreach ($d in "game", "game-alt", "game-dd-20261003") {
    if (Test-Path (Join-Path $Lab "$d\.console-test.lock")) { throw "$d\.console-test.lock exists: console busy" }
}
New-Item -ItemType File -Path $OwnerFile -ErrorAction Stop | Out-Null      # exclusive: fails if another agent holds it
Set-Content $OwnerFile "$Owner $(Get-Date -Format s)"
$moved = @(); $confBak = $null; $zBak = $null
try {
    if ($Control) {
        New-Item -ItemType Directory -Force $Aside | Out-Null
        foreach ($f in Get-ChildItem $Addon -File | Where-Object { $_.Name -match '^pirana\d6\.(pak|pix)$' }) {
            Move-Item $f.FullName (Join-Path $Aside $f.Name); $moved += $f.Name
        }
        "control: moved aside $($moved -join ', ')"
    }
    if ($Conf) {
        $live = Join-Path $G "dgVoodoo.conf"; $confBak = "$live.pre-texscale"
        Copy-Item $live $confBak -Force; Copy-Item $Conf $live -Force
        "conf: $Conf -> $live (original kept as $confBak)"
    }
    if ($ZglideFix) {
        $z = Join-Path $G "ZGLIDE.DLL"; $zBak = "$z.pre-texscale"
        Copy-Item $z $zBak -Force; Copy-Item (Join-Path $G "ZGLIDE.tmufix.dll") $z -Force
        "zglide: tmufix in place, md5 $((Get-FileHash $z -Algorithm MD5).Hash.ToLower())"
    }
    $addonNow = (Get-ChildItem $Addon -File | Where-Object { $_.Name -match '^pirana' } | ForEach-Object { "$($_.Name)=$($_.Length)" }) -join ' '
    "addon pirana files this run: $(if ($addonNow) { $addonNow } else { '(none)' })"
    $run = {
        $cf = "C:\Users\james\i76-uncap-lab\tools\graphics\capture-frame.ps1"
        Start-Sleep -Seconds 3
        & $cf -Out (Join-Path $capDir "$stamp-$Tag-start.png")
        Send-Key 0x72; Start-Sleep -Seconds 2          # F3 = PRESET_VIEW_3
        & $cf -Out (Join-Path $capDir "$stamp-$Tag-F3.png")
        Send-Key 0x73; Start-Sleep -Seconds 2          # F4 = PRESET_VIEW_12
        & $cf -Out (Join-Path $capDir "$stamp-$Tag-F4.png")
    }   # no GetNewClosure: dynamic scope must reach proxy-run's Send-Key (inputlib) and this script's $capDir/$stamp/$Tag
    & (Join-Path $Lab "autotest\proxy-run.ps1") -GameDir $G -KeepInstalledDll -Mission $Mission -Hold 2 -Run $run
} finally {
    foreach ($n in $moved) { Move-Item (Join-Path $Aside $n) (Join-Path $Addon $n) -Force }
    if ($zBak) { Copy-Item $zBak (Join-Path $G "ZGLIDE.DLL") -Force; Remove-Item $zBak }
    if ($confBak) { Copy-Item $confBak (Join-Path $G "dgVoodoo.conf") -Force; Remove-Item $confBak }
    Remove-Item $OwnerFile -ErrorAction SilentlyContinue
    "console released; captures: $capDir\$stamp-$Tag-*.png"
}
