<#
  package-deck-kit.ps1 - the "I'76 Deck Kit (i76-everywhere)" zip: Steam Deck users build Interstate '76 Gold from their own GOG copy
  (owner 2026-10-25: "What about end users building the Steam Deck version?"; record docs\records\DECK-2026-10-25.md). The sibling of
  package-patch-kit.ps1 (Windows) and package-mac-kit.ps1 (Mac): nothing of the game is inside, and every third-party download
  (innoextract, dgVoodoo 2.78.2, IPXWrapper, optionally GE-Proton) is fetched on the Deck, pinned by SHA-256 (deck\kit\pins.txt).

  ONE zip with one folder, Interstate76-Deck-Kit\:
    i76-deck-kit.sh, README.md, pins.txt, VERSION.txt, MD5SUMS, i76-env.sh (the Deck preset), i76-env-mp.sh, i76-env.local.sh.example,
    dgVoodoo.conf (the Deck's 2.78.2 conf), tools\ (bspatch.py, add-to-steam.py, gpw-envelopes.py, zfs_extract.py)
    payload\gold\    STRLKUP.DLL (the proxy), i7_sfrce.dll (the ffb-shim rumble DLL), input.map (controls\input.map); no u32x (see below)
    payload\deck\    i76-deck-launch.sh, i76-deck-launch-mp.sh, controller_neptune_i76_pad.vdf
    payload\ahk\     AutoHotkeyU32.exe 1.1.37.02 (GPL v2) + license.txt + i76-remap.ahk
    payload\patches\ deck\kit\tools\make-deck-patches.py's output (BSDIFF40 against GOG 2.1.0.17 files) + patches.txt: the Mac Kit's
                     Gold set without its u32x step (with u32x the proxy's pad menu / cursor map cannot hook: no Deck menu pointer)

    tools\package-deck-kit.ps1 -Proxy <STRLKUP.DLL> -Shim <I7_SFRCE.DLL> -PatchesDir <make-patches.py out> -AhkDir <AutoHotkey dir>
                               [-GogGold <re-archive>\sandbox-gog\main\app] [-OutDir ...\downloads\deck-kit] [-Version 0.1.0]
  Shell scripts and text are written with LF line endings (a CRLF .sh fails on the Deck with "\r: command not found").
#>
param(
    [Parameter(Mandatory)][string]$Proxy,
    [Parameter(Mandatory)][string]$Shim,
    [Parameter(Mandatory)][string]$PatchesDir,
    [Parameter(Mandatory)][string]$AhkDir,
    [string]$GogGold = (Join-Path $env:USERPROFILE 'i76-map\sandbox-gog\main\app'),
    [string]$OutDir = (Join-Path $env:USERPROFILE 'i76-uncap-lab\downloads\deck-kit'),
    [string]$Version = '0.1.0',
    [string]$Stage = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$kit = Join-Path $repo 'deck\kit'
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Die([string]$m) { Write-Host "package-deck-kit: $m" -ForegroundColor Red; exit 1 }
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$sha = (git -C $repo rev-parse --short HEAD).Trim()
$dirty = @(git -C $repo status --porcelain -- deck/kit deck/i76-deck-launch.sh deck/i76-deck-launch-mp.sh deck/add-to-steam.py deck/controller_neptune_i76_pad.vdf controls/input.map i76-remap.ahk u32x/u32x_full.dll tools/gpw-envelopes.py tools/zfs_extract.py)
if ($dirty.Count) { Say "WARNING: uncommitted changes in shipped files:`n  $($dirty -join "`n  ")" 'Yellow' }
if (-not $Stage) { $Stage = Join-Path $env:TEMP "deck-kit-stage-$sha" }
if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
$top = Join-Path $Stage 'Interstate76-Deck-Kit'
New-Item -ItemType Directory -Force $top | Out-Null
function Put([string]$from, [string]$rel) {
    if (-not (Test-Path -LiteralPath $from)) { Die "missing: $from" }
    $to = Join-Path $top $rel; New-Item -ItemType Directory -Force (Split-Path -Parent $to) | Out-Null
    Copy-Item -LiteralPath $from -Destination $to -Force
}
function PutLf([string]$from, [string]$rel) {   # text: CRLF -> LF, no BOM
    if (-not (Test-Path -LiteralPath $from)) { Die "missing: $from" }
    $to = Join-Path $top $rel; New-Item -ItemType Directory -Force (Split-Path -Parent $to) | Out-Null
    $t = [IO.File]::ReadAllText($from) -replace "`r`n", "`n"
    [IO.File]::WriteAllText($to, $t, (New-Object Text.UTF8Encoding $false))
}

# ---- the kit's own text ----------------------------------------------------------------------------------------------------
foreach ($n in 'i76-deck-kit.sh', 'README.md', 'pins.txt', 'i76-env.sh', 'i76-env-mp.sh', 'i76-env.local.sh.example', 'dgVoodoo.conf') { PutLf (Join-Path $kit $n) $n }
PutLf (Join-Path $kit 'tools\bspatch.py') 'tools\bspatch.py'
PutLf (Join-Path $repo 'deck\add-to-steam.py') 'tools\add-to-steam.py'
PutLf (Join-Path $repo 'tools\gpw-envelopes.py') 'tools\gpw-envelopes.py'
PutLf (Join-Path $repo 'tools\zfs_extract.py') 'tools\zfs_extract.py'
PutLf (Join-Path $repo 'deck\i76-deck-launch.sh') 'payload\deck\i76-deck-launch.sh'
PutLf (Join-Path $repo 'deck\i76-deck-launch-mp.sh') 'payload\deck\i76-deck-launch-mp.sh'
PutLf (Join-Path $repo 'deck\controller_neptune_i76_pad.vdf') 'payload\deck\controller_neptune_i76_pad.vdf'
PutLf (Join-Path $repo 'i76-remap.ahk') 'payload\ahk\i76-remap.ahk'
Put (Join-Path $repo 'controls\input.map') 'payload\gold\input.map'
foreach ($n in 'capsule_p.png', 'header.png', 'hero.png', 'logo.png', 'icon.png') { Put (Join-Path $repo "deck\artwork\$n") "artwork\$n" }   # generated art (deck\make-art.py), no game assets

# ---- our binaries, md5-pinned (a different build must be a deliberate edit here) --------------------------------------------
$pins = [ordered]@{
    $Proxy                                       = @('5d6f9828', 'payload\gold\STRLKUP.DLL')    # the family proxy (= main 810caf2, every Mac / the Deck)
    $Shim                                        = @('d6e9add5', 'payload\gold\i7_sfrce.dll')   # ffb-shim, MSVC build of 6853d7b (ffb-shim\build-msvc.ps1)
    (Join-Path $AhkDir 'AutoHotkeyU32.exe')      = @('b6af97aa', 'payload\ahk\AutoHotkeyU32.exe')   # AutoHotkey 1.1.37.02, GPL v2
    (Join-Path $AhkDir 'license.txt')            = @('e3f2ad77', 'payload\ahk\license.txt')
}
foreach ($k in $pins.Keys) {
    $m = Md5 $k; if (-not $m.StartsWith($pins[$k][0])) { Die "$k md5 $m is not the pinned $($pins[$k][0])" }
    Put $k $pins[$k][1]
}

# ---- the Gold patches (the Nitro row stays out: the Deck Kit is Gold only) ---------------------------------------------------
$plist = Join-Path $PatchesDir 'patches.txt'; if (-not (Test-Path -LiteralPath $plist)) { Die "no patches.txt in $PatchesDir (tools\mac-kit\make-patches.py)" }
$rows = @(Get-Content -LiteralPath $plist | Where-Object { $_ -notmatch '^#' -and $_.Split("`t")[0] -eq 'gold' })
if ($rows.Count -lt 3) { Die "only $($rows.Count) gold rows in $plist" }
$hdr = '# I''76 Deck Kit patches (Gold rows of tools/mac-kit/make-patches.py): app, target, source, source md5, target md5, patch'
New-Item -ItemType Directory -Force (Join-Path $top 'payload\patches') | Out-Null
[IO.File]::WriteAllText((Join-Path $top 'payload\patches\patches.txt'), (@($hdr) + $rows -join "`n") + "`n", (New-Object Text.UTF8Encoding $false))
foreach ($r in $rows) { $pf = $r.Split("`t")[5]; Put (Join-Path $PatchesDir $pf) "payload\patches\$pf" }
Say "    $($rows.Count) Gold patches"

# ---- VERSION + the game-byte guard + MD5SUMS ----------------------------------------------------------------------------------
[IO.File]::WriteAllText((Join-Path $top 'VERSION.txt'), "$Version ($sha, $(Get-Date -Format 'yyyy-MM-dd'))`n", (New-Object Text.UTF8Encoding $false))
$gogMd5 = @{}
if (Test-Path -LiteralPath $GogGold) { Get-ChildItem -LiteralPath $GogGold -Recurse -File | ForEach-Object { $gogMd5[(Md5 $_.FullName)] = $_.FullName } }
else { Say 'WARNING: no pristine GOG folder: the content guard cannot run' 'Yellow' }
$files = Get-ChildItem -LiteralPath $top -Recurse -File
foreach ($f in $files) { $m = Md5 $f.FullName; if ($gogMd5.ContainsKey($m)) { Die "GUARD: $($f.FullName) is byte-identical to the GOG file $($gogMd5[$m])" } }
Say "    guard: $($files.Count) files, none byte-identical to any of $($gogMd5.Count) GOG files"
$sums = $files | ForEach-Object { "$(Md5 $_.FullName)  $($_.FullName.Substring($top.Length + 1).Replace('\', '/'))" }
[IO.File]::WriteAllText((Join-Path $top 'MD5SUMS'), ($sums -join "`n") + "`n", (New-Object Text.UTF8Encoding $false))

New-Item -ItemType Directory -Force $OutDir | Out-Null
$zip = Join-Path $OutDir "Interstate76-Deck-Kit-i76-everywhere-v$Version-$sha.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
& python -I (Join-Path $kit 'tools\make-zip.py') $Stage 'Interstate76-Deck-Kit' $zip | Out-Null   # forward slashes + Unix modes
if (-not (Test-Path -LiteralPath $zip)) { Die 'zip not written' }
"$(Md5 $zip)  $(Split-Path -Leaf $zip)" | Set-Content -LiteralPath "$zip.MD5SUMS" -Encoding ascii
Say "=== $zip ($([math]::Round((Get-Item $zip).Length / 1MB, 2)) MB, md5 $(Md5 $zip)) ===" 'Green'
