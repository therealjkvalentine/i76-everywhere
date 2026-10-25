<#
  i76e-update.ps1 - what UPDATE.bat of the Patch Kit runs (kit-controls lane 2026-10-25, docs\records\KIT-CONTROLS-UPDATER-2026-10-25.md).

  Pulls the newest Patch Kit into this game folder without a reinstall. Windows PowerShell 5.1 only: no git, no gh, no dev tools.
    1. reads this folder's kit version (_i76e\VERSION.txt, first line "patch-kit-v<x.y.z> <commit>");
    2. asks GitHub's releases API for the newest published release that carries a Patch Kit zip (the kit releases are
       pre-releases, which /releases/latest does not return, so the list is read and sorted by version);
    3. --check stops here and says whether an update is there;
    4. downloads the zip into _i76e\update\, checks its SHA-256 against the release asset's digest, unpacks it beside the folder,
       checks every file against the new kit's own MD5SUMS, and refuses a zip that would write anything but the kit's own files
       (the PLAY / UPDATE / ... .bat files, README-PATCH-KIT.md and _i76e\);
    5. copies the new kit files in (the previous ones go to _i76e\update\previous\), removes kit files the new kit no longer has,
       and runs the setup again (i76e-prepare.ps1 -SetupOnly), which keeps the player's own controls (input.map, the gamepad
       layer scripts), I76PLYR.DEF, i76-settings.txt, presets\local.psd1, saves and extras;
    6. prints what changed.

    UPDATE.bat [--check] [--yes] [--source <kit zip>] [--sha256 <hex>] [--display WxH]
  --source applies a local zip instead of the GitHub release (a test build; with --sha256, or a <zip>.sha256 file beside it,
  the zip is checked against it, else only against its own MD5SUMS). Exit 0 = up to date / updated, 10 = (--check) an update
  is available, 1 = failed (nothing changed unless the message says so).
#>
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # PS 5.1's progress bar makes Invoke-WebRequest many times slower
$here = $PSScriptRoot; $gameDir = Split-Path -Parent $here
$Repo = 'therealjkvalentine/i76-everywhere'
$Check = $false; $Yes = $false; $Source = ''; $Sha = ''; $Display = ''; $NoPause = $false; $Force = $false
for ($i = 0; $i -lt $Rest.Count; $i++) {
    switch -Regex ($Rest[$i]) {
        '^-{1,2}check$' { $Check = $true }
        '^-{1,2}yes$' { $Yes = $true }
        '^-{1,2}force$' { $Force = $true }
        '^-{1,2}no-?pause$' { $NoPause = $true }
        '^-{1,2}source$' { $i++; $Source = $Rest[$i] }
        '^-{1,2}sha256$' { $i++; $Sha = $Rest[$i].ToLower() }
        '^-{1,2}display$' { $i++; $Display = $Rest[$i] }
        '^-{1,2}repo$' { $i++; $Repo = $Rest[$i] }
        default { Write-Host "UPDATE.bat: unknown option '$($Rest[$i])' (UPDATE.bat [--check] [--yes] [--source <zip>] [--sha256 <hex>])" -ForegroundColor Red; exit 1 }
    }
}
$logFile = Join-Path $here 'setup.log'
function Log([string]$m) { try { Add-Content -LiteralPath $logFile -Value ("{0}  update: {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) -Encoding ascii } catch { } }
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c; Log $m }
$interactive = -not $NoPause -and -not $env:I76E_NO_PAUSE
try { if ([Console]::IsOutputRedirected -or [Console]::IsInputRedirected) { $interactive = $false } } catch { $interactive = $false }
function Done([int]$rc) {
    if ($interactive) { Write-Host ''; Write-Host '  Press any key to close this window . . .' -ForegroundColor Cyan; try { [void]$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { } }
    exit $rc
}
function Fail([string]$m) { Say "  UPDATE: $m" 'Red'; Done 1 }
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }
function Read-Sums([string]$p) {
    $h = @{}
    if (Test-Path -LiteralPath $p) { foreach ($ln in (Get-Content -LiteralPath $p)) { if ($ln -match '^([0-9a-f]{32})\s+\*?(.+)$') { $h[$Matches[2].Trim()] = $Matches[1] } } }
    return $h
}
function Parse-Ver([string]$s) { if ($s -match 'v?(\d+)\.(\d+)\.(\d+)') { return [version]"$($Matches[1]).$($Matches[2]).$($Matches[3])" }; return $null }

# ---- 1. this folder's kit ----------------------------------------------------------------------------------------------------
$verFile = Join-Path $here 'VERSION.txt'
if (-not (Test-Path -LiteralPath $verFile)) { Fail "no _i76e\VERSION.txt here: run UPDATE.bat from the game folder the kit was unzipped into." }
$curLine = (Get-Content -LiteralPath $verFile -TotalCount 1).Trim()
$curVer = Parse-Ver $curLine
$curSha = if ($curLine -match '\s([0-9a-f]{7,})$') { $Matches[1] } else { '' }
Write-Host ''
Say "  Interstate '76 Patch Kit in $gameDir"
Say "  installed: $($curLine -replace '^patch-kit-', '')"

# ---- 2. the newest kit ---------------------------------------------------------------------------------------------------------
$zipRx = '^Interstate76-Patch-Kit-i76-everywhere-v(\d+\.\d+\.\d+)-([0-9a-f]{7,})\.zip$'
$new = $null
if ($Source) {
    if (-not (Test-Path -LiteralPath $Source)) { Fail "--source: no file $Source" }
    $Source = (Resolve-Path -LiteralPath $Source).Path
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $za = [IO.Compression.ZipFile]::OpenRead($Source)
    try {
        $e = $za.Entries | Where-Object { $_.FullName -replace '/', '\' -eq '_i76e\VERSION.txt' } | Select-Object -First 1
        if (-not $e) { Fail "--source: $Source is not a Patch Kit zip (no _i76e\VERSION.txt in it)" }
        $sr = New-Object IO.StreamReader($e.Open()); $line = $sr.ReadLine().Trim(); $sr.Close()
    } finally { $za.Dispose() }
    if (-not $Sha -and (Test-Path -LiteralPath "$Source.sha256")) { $Sha = ((Get-Content -LiteralPath "$Source.sha256" -TotalCount 1) -split '\s+')[0].ToLower() }
    $new = [pscustomobject]@{ Ver = (Parse-Ver $line); Line = $line; Name = (Split-Path -Leaf $Source); Url = ''; Path = $Source; Sha256 = $Sha; Tag = '(local file)'; Notes = '' }
} else {
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }
    $api = "https://api.github.com/repos/$Repo/releases?per_page=30"
    try { $rels = Invoke-RestMethod -UseBasicParsing -Uri $api -Headers @{ 'User-Agent' = 'i76e-update'; 'Accept' = 'application/vnd.github+json' } -TimeoutSec 30 }
    catch { Fail "could not reach GitHub ($api): $($_.Exception.Message). Check the internet connection, or download the kit by hand from https://github.com/$Repo/releases" }
    foreach ($r in @($rels)) {
        if ($r.draft) { continue }
        foreach ($a in @($r.assets)) {
            if ($a.name -notmatch $zipRx) { continue }
            $vs = $Matches[1]; $cs = $Matches[2]; $v = [version]$vs   # before the digest match below resets $Matches
            if (-not $new -or $v -gt $new.Ver) {
                $d = "$($a.digest)"; $h = if ($d -match '^sha256:([0-9a-f]{64})$') { $Matches[1] } else { '' }
                $new = [pscustomobject]@{ Ver = $v; Line = "patch-kit-v$vs $cs"; Name = $a.name; Url = $a.browser_download_url; Path = ''; Sha256 = $h; Tag = $r.tag_name; Size = $a.size; Notes = "$($r.html_url)" }
            }
        }
    }
    if (-not $new) { Fail "no Patch Kit zip found in the releases of $Repo." }
}
Say "  newest:    v$($new.Ver) $(if ($new.Line -match '\s([0-9a-f]{7,})$') { $Matches[1] }) ($($new.Tag)$(if ($new.Notes) { ", $($new.Notes)" }))"
$same = ($curVer -and $new.Ver -le $curVer) -and -not ($new.Ver -eq $curVer -and $Source -and $new.Line -ne $curLine)
if ($same -and -not $Force) {
    Say "  Up to date: nothing to do." 'Green'
    Done 0
}
if ($Check) { Say "  An update is available: v$($curVer) -> v$($new.Ver). Run UPDATE.bat (without --check) to install it." 'Yellow'; Done 10 }

# ---- 3. confirm, download, verify ---------------------------------------------------------------------------------------------
if (@(Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($gameDir + '\', [StringComparison]::OrdinalIgnoreCase) }).Count) { Fail 'close the game first, then run UPDATE.bat again.' }
if ($interactive -and -not $Yes) {
    $k = Read-Host "  Update v$curVer -> v$($new.Ver) now? Your controls, settings and saves stay as they are. [Y/n]"
    if ($k -and $k.Trim() -notmatch '^(y|yes)$') { Say '  Not updated.'; Done 0 }
}
$work = Join-Path $here 'update'
if (Test-Path -LiteralPath (Join-Path $work 'new')) { Remove-Item -LiteralPath (Join-Path $work 'new') -Recurse -Force }
New-Item -ItemType Directory -Force $work | Out-Null
if ($new.Url) {
    $zip = Join-Path $work $new.Name
    Say "  downloading $($new.Name) ($([Math]::Round($new.Size / 1MB, 1)) MB) ..."
    try { Invoke-WebRequest -UseBasicParsing -Uri $new.Url -OutFile $zip -Headers @{ 'User-Agent' = 'i76e-update' } -TimeoutSec 600 }
    catch { Fail "the download failed: $($_.Exception.Message)" }
} else { $zip = $new.Path }
if ($new.Sha256) {
    $got = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
    if ($got -ne $new.Sha256) { if ($new.Url) { Remove-Item -LiteralPath $zip -Force }; Fail "the zip's SHA-256 $got is not the release's $($new.Sha256): NOT installed (a broken download? run UPDATE.bat again)." }
    Say "  SHA-256 matches $(if ($new.Url) { 'the release' } else { 'the one given' }): $($got.Substring(0, 16))..."
} elseif ($new.Url) { Fail "the release gives no SHA-256 digest for $($new.Name): not installed. Download it by hand from https://github.com/$Repo/releases" }
else { Say "  (a local zip with no --sha256: checked against its own MD5SUMS only)" 'Yellow' }
$stage = Join-Path $work 'new'
try { Expand-Archive -LiteralPath $zip -DestinationPath $stage -Force } catch { Fail "the zip could not be unpacked: $($_.Exception.Message)" }
$newSums = Read-Sums (Join-Path $stage '_i76e\MD5SUMS')
if ($newSums.Count -lt 20) { Fail "the new kit has no usable _i76e\MD5SUMS: not installed." }
$files = @(Get-ChildItem -LiteralPath $stage -Recurse -File | ForEach-Object { $_.FullName.Substring($stage.Length + 1) })
$bad = @()
foreach ($rel in $files) {
    if ($rel -eq '_i76e\MD5SUMS') { continue }
    if (-not $newSums.ContainsKey($rel)) { $bad += "$rel (not in MD5SUMS)"; continue }
    if ((Md5 (Join-Path $stage $rel)) -ne $newSums[$rel]) { $bad += "$rel (md5 differs)" }
}
foreach ($rel in $newSums.Keys) { if (-not (Test-Path -LiteralPath (Join-Path $stage $rel))) { $bad += "$rel (missing)" } }
if ($bad.Count) { Fail "the new kit does not match its own MD5SUMS: $(($bad | Select-Object -First 5) -join '; ')" }
# only the kit's own files: the top-level .bat / README, and _i76e\ except the folder's own state
$state = '^_i76e\\(backup|update|downloads)\\|^_i76e\\(extras\.env|extras-installed\.txt|installed\.txt|display\.txt|setup\.log)$'
$notKit = @($files | Where-Object { -not (($_ -match '^[A-Za-z0-9_-]+\.(bat|md)$') -or ($_ -match '^_i76e\\' -and $_ -notmatch $state)) })
if ($notKit.Count) { Fail "the new zip would write files that are not the kit's ($(($notKit | Select-Object -First 5) -join ', ')): not installed." }
if (-not (Test-Path -LiteralPath (Join-Path $stage '_i76e\i76e-prepare.ps1'))) { Fail 'the new zip has no _i76e\i76e-prepare.ps1: not installed.' }
Say "  checked: $($files.Count) files match the new kit's MD5SUMS."

# ---- 4. apply ------------------------------------------------------------------------------------------------------------------
$oldSums = Read-Sums (Join-Path $here 'MD5SUMS')
$mapFile = Join-Path $gameDir 'input.map'
$mapBefore = if (Test-Path -LiteralPath $mapFile) { Md5 $mapFile } else { '' }
$added = @(); $changed = @(); $removed = @(); $keptMine = @()
$prev = Join-Path $work 'previous'
if (Test-Path -LiteralPath $prev) { Remove-Item -LiteralPath $prev -Recurse -Force }
foreach ($rel in ($files | Sort-Object)) {
    $dst = Join-Path $gameDir $rel; $src = Join-Path $stage $rel
    if (Test-Path -LiteralPath $dst) {
        $dm = Md5 $dst
        if ($dm -eq (Md5 $src)) { continue }
        $p = Join-Path $prev $rel; New-Item -ItemType Directory -Force (Split-Path -Parent $p) | Out-Null; Copy-Item -LiteralPath $dst -Destination $p -Force
        # a top-level .bat the player edited (not the old kit's): kept beside as <name>.pre-update
        if ($rel -notmatch '\\' -and $oldSums.ContainsKey($rel) -and $oldSums[$rel] -ne $dm) { Copy-Item -LiteralPath $dst -Destination "$dst.pre-update" -Force; $keptMine += "$rel (your edited copy: $rel.pre-update)" }
        $changed += $rel
    } else { $added += $rel; New-Item -ItemType Directory -Force (Split-Path -Parent $dst) | Out-Null }
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
foreach ($rel in ($oldSums.Keys | Sort-Object)) {
    if ($newSums.ContainsKey($rel) -or $rel -eq '_i76e\MD5SUMS') { continue }
    $dst = Join-Path $gameDir $rel
    if ((Test-Path -LiteralPath $dst) -and (Md5 $dst) -eq $oldSums[$rel] -and $rel -notmatch $state) {
        $p = Join-Path $prev $rel; New-Item -ItemType Directory -Force (Split-Path -Parent $p) | Out-Null; Move-Item -LiteralPath $dst -Destination $p -Force
        $removed += $rel
    }
}
Copy-Item -LiteralPath (Join-Path $stage '_i76e\MD5SUMS') -Destination (Join-Path $here 'MD5SUMS') -Force
$nowLine = (Get-Content -LiteralPath $verFile -TotalCount 1).Trim()
if ($nowLine -ne $new.Line -and -not $Source) { Say "  note: the new VERSION.txt says '$nowLine'" 'Yellow' }
Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
if ($new.Url) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue }
Log "applied $curLine -> ${nowLine}: $($changed.Count) changed, $($added.Count) added, $($removed.Count) removed"

# ---- 5. the setup again (keeps the player's files) ----------------------------------------------------------------------------
$games = @()
if (Test-Path -LiteralPath (Join-Path $gameDir 'i76.exe')) { $games += 'Gold' }
if (Test-Path -LiteralPath (Join-Path $gameDir 'nitro.exe')) { $games += 'Nitro' }
$setupOk = $true
foreach ($g in $games) {
    $pa = @('-Game', $g, '-SetupOnly', '-NoPause'); if ($Display) { $pa += @('-Display', $Display) }
    $global:LASTEXITCODE = 0; $ErrorActionPreference = 'Continue'
    $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'i76e-prepare.ps1') @pa 2>&1
    $rc = $LASTEXITCODE; $ErrorActionPreference = 'Stop'
    $out | ForEach-Object { Log "  prepare: $_" }
    if ($rc -ne 0) { $setupOk = $false; Say "  the setup step for $g stopped (exit $rc); PLAY.bat runs it again at the next start. _i76e\setup.log has the details." 'Yellow' }
}

# ---- 6. what changed ---------------------------------------------------------------------------------------------------------
Write-Host ''
Say "  Updated: $($curLine -replace '^patch-kit-', '') -> $($nowLine -replace '^patch-kit-', '')" 'Green'
Say ("  kit files: {0} changed, {1} added, {2} removed (the previous ones are in _i76e\update\previous\)" -f $changed.Count, $added.Count, $removed.Count)
foreach ($grp in @(@('changed', $changed), @('added', $added), @('removed', $removed))) {
    $l = @($grp[1]); if (-not $l.Count) { continue }
    $show = @($l | Select-Object -First 12)
    Say "    $($grp[0]): $($show -join ', ')$(if ($l.Count -gt 12) { " and $($l.Count - 12) more" })" 'DarkGray'
}
foreach ($k in $keptMine) { Say "    $k" 'Yellow' }
$kept = @()
if (Test-Path -LiteralPath (Join-Path $gameDir 'input.map.i76e-default')) { $kept += 'your own key bindings (input.map; the kit''s layout is beside it as input.map.i76e-default, CONTROLS.bat switches)' }
elseif ($mapBefore -and (Test-Path -LiteralPath $mapFile) -and (Md5 $mapFile) -eq $mapBefore) { $kept += 'input.map' }
elseif ($mapBefore) { Say "  input.map: you had not changed the kit's layout, so it is now the new kit's (the old one: input.map.before-i76e-* / .as-installed)." }
foreach ($n in 'i76-settings.txt', 'presets\local.psd1', 'savegame.dir') { if (Test-Path -LiteralPath (Join-Path $gameDir $n)) { $kept += $n } }
Say "  kept as they were: $($kept -join '; ')"
if (-not $setupOk) { Done 1 }
Say "  Start the game with PLAY.bat as before." 'Green'
Done 0
