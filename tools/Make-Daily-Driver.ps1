<#
  Make-Daily-Driver.ps1 - DRAFT (2026-10-02). Written, parsed, NEVER RUN. Read docs\NEW-DAILY-DRIVER-RECIPE.md first.

  Assembles a NEW, self-contained Interstate '76 folder from the current daily driver plus the
  parts the integrator names, and (optionally) a golden copy of the result.

    tools\Make-Daily-Driver.ps1 -Source <current driver root> -Dest <new folder> [-GoldenDest <folder>]
                                -DgVoodooConf <the conf that parses> [-U32xDll <gated build>] [-Plan]

  -Source is the PORTABLE ROOT (the folder that contains "Interstate 76\"), e.g.
      C:\Users\james\Downloads\Interstate76-i76-everywhere-portable-20260801

  Rules this script keeps:
    * COPIES ONLY. Nothing under -Source is written, renamed or deleted. A fingerprint of the
      source (file count, bytes, newest write time) is taken before and after and compared.
    * Refuses if -Dest or -GoldenDest already exists, or lies inside -Source.
    * Refuses while an i76 process started from -Source is running (a save in flight would be
      copied torn).
    * Every file written is hashed after the copy. Dest\MANIFEST.md lists every file with its
      md5, size and where it came from.
    * Every overlay (a file the new folder gets from somewhere other than the driver) keeps the
      driver's file beside it as <name>.driver-<md5 8>, so "what did the old driver have" is one
      rename away.
    * -Plan prints what would be done and writes nothing at all.

  What it does NOT do: start the game, touch the registry, touch %APPDATA%, create shortcuts,
  validate that dgVoodoo accepts the conf (only a console launch can: see the recipe's checklist).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$Source,
    [Parameter(Mandatory = $true)] [string]$Dest,
    [string]$GoldenDest = '',

    # The dgVoodoo.conf the new folder gets. No default on purpose: on 2026-10-02 dgVoodoo 2.87.3
    # was found to REJECT the sandbox's conf and fall back to %APPDATA%\dgVoodoo\dgVoodoo.conf, and
    # the driver's conf is the same file family. The integrator supplies the conf that parses.
    [string]$DgVoodooConf = '',
    [switch]$KeepSourceConf,      # explicit opt-out: carry the driver's conf unchanged (NOT independent)

    [string]$StrlkupDll = (Join-Path $PSScriptRoot '..\music-fix\Strlkup.dll'),
    [string]$U32xDll    = (Join-Path $PSScriptRoot '..\u32x\u32x.dll'),
    [switch]$AllowUnrecordedU32x, # accept a u32x build whose md5 is not in u32x\deploy-u32x.ps1's $KnownGood
    [string]$GameExe    = '',     # optional replacement i76.exe (must already import u32x.dll)

    [string]$Preset = 'smooth-120',
    [switch]$KeepI76Patch,        # leave GOG's I76PATCH.DLL (20 fps cap) active
    [switch]$NoLosslessScaling,   # do not carry "Lossless Scaling\" (175 MB, licensed app)
    [switch]$IncludeFfbTools,     # copy tools\ffb\*.ps1 to "Interstate 76\_ffb" (PLAY-i76.ps1 -Ffb looks there)
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Die([string]$m) { Write-Host "REFUSED: $m" -ForegroundColor Red; exit 1 }
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }
function FullPath([string]$p) { [IO.Path]::GetFullPath($p).TrimEnd('\') }

# ---- 0. resolve and guard ----------------------------------------------------------------------
$Source = FullPath $Source
$Dest   = FullPath $Dest
if ($GoldenDest) { $GoldenDest = FullPath $GoldenDest }
$srcGame = Join-Path $Source 'Interstate 76'

if (-not (Test-Path -LiteralPath (Join-Path $srcGame 'i76.exe'))) { Die "-Source must be the portable root: no 'Interstate 76\i76.exe' under $Source" }
if (Test-Path -LiteralPath $Dest) { Die "-Dest already exists: $Dest (this script never overwrites; pick a new name)" }
if ($GoldenDest -and (Test-Path -LiteralPath $GoldenDest)) { Die "-GoldenDest already exists: $GoldenDest" }
foreach ($d in @($Dest, $GoldenDest) | Where-Object { $_ }) {
    if (($d + '\').StartsWith($Source + '\', [StringComparison]::OrdinalIgnoreCase)) { Die "$d lies inside the source" }
    if (($Source + '\').StartsWith($d + '\', [StringComparison]::OrdinalIgnoreCase)) { Die "the source lies inside $d" }
}
if ($GoldenDest -and ($GoldenDest -ieq $Dest)) { Die "-GoldenDest equals -Dest" }
if ($GoldenDest -and (($GoldenDest + '\').StartsWith($Dest + '\', [StringComparison]::OrdinalIgnoreCase))) { Die "-GoldenDest lies inside -Dest" }

$running = @(Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($Source, [StringComparison]::OrdinalIgnoreCase) })
if ($running.Count) { Die "the game is running from the source (PID $($running[0].Id)); close it first" }

if (-not $KeepSourceConf) {
    if (-not $DgVoodooConf) { Die "-DgVoodooConf <file> is required (the conf that dgVoodoo accepts), or pass -KeepSourceConf to carry the driver's conf knowingly" }
    if (-not (Test-Path -LiteralPath $DgVoodooConf)) { Die "-DgVoodooConf not found: $DgVoodooConf" }
    $confBytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $DgVoodooConf).Path)
    if (@($confBytes | Where-Object { $_ -gt 127 }).Count) { Die "-DgVoodooConf contains non-ASCII bytes" }
    $confText = [Text.Encoding]::ASCII.GetString($confBytes)
    if ($confText -notmatch '(?m)^\s*Version\s*=\s*0x[0-9A-Fa-f]+') { Die "-DgVoodooConf has no 'Version = 0x...' line" }
    foreach ($sec in 'General', 'Glide', 'DirectX') { if ($confText -notmatch "(?m)^\s*\[$sec\]") { Die "-DgVoodooConf has no [$sec] section" } }
}
foreach ($f in @($StrlkupDll, $U32xDll)) { if (-not (Test-Path -LiteralPath $f)) { Die "not found: $f" } }
$StrlkupDll = (Resolve-Path -LiteralPath $StrlkupDll).Path
$U32xDll    = (Resolve-Path -LiteralPath $U32xDll).Path
if ($GameExe) {
    if (-not (Test-Path -LiteralPath $GameExe)) { Die "-GameExe not found: $GameExe" }
    $GameExe = (Resolve-Path -LiteralPath $GameExe).Path
    $exeText = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($GameExe))
    if ($exeText -notmatch 'u32x\.dll') { Die "-GameExe does not import u32x.dll (the save screen would wedge); deploy u32x to it first" }
}

# 32-bit PE check for the two DLLs (a 64-bit build would stop the game loading)
function PeMachine([string]$p) { $b = [IO.File]::ReadAllBytes($p); $o = [BitConverter]::ToInt32($b, 0x3C); [BitConverter]::ToUInt16($b, $o + 4) }
foreach ($f in @($StrlkupDll, $U32xDll)) { if ((PeMachine $f) -ne 0x14C) { Die "$f is not a 32-bit x86 image" } }

# u32x: recorded verified builds only, unless told otherwise. The list is read from deploy-u32x.ps1
# so there is one place that says which builds passed the bookmark route.
$u32xMd5 = Md5 $U32xDll
$knownGood = @()
$deployScript = Join-Path $repo 'u32x\deploy-u32x.ps1'
if (Test-Path -LiteralPath $deployScript) {
    $knownGood = @([regex]::Matches((Get-Content -LiteralPath $deployScript -Raw), "'([0-9a-f]{32})'\s*=") | ForEach-Object { $_.Groups[1].Value })
}
if (($knownGood -notcontains $u32xMd5) -and -not $AllowUnrecordedU32x) {
    Die "u32x build $u32xMd5 is not in u32x\deploy-u32x.ps1's KnownGood list ($($knownGood -join ', ')). Record it there after its gate, or pass -AllowUnrecordedU32x."
}

$presetFile = Join-Path $repo "presets\$Preset.psd1"
if (-not (Test-Path -LiteralPath $presetFile)) { Die "no preset $Preset in $repo\presets" }
if (-not (Test-Path -LiteralPath (Join-Path $srcGame 'strlkup_orig.dll'))) { Die "the source has no strlkup_orig.dll: the music-fix proxy would have nothing to forward to" }

# The driver's i76.exe and i76shell.dll must already import u32x.dll, because this script only
# replaces the DLL file and never patches an import table.
if (-not $GameExe) {
    $t = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes((Join-Path $srcGame 'i76.exe')))
    if ($t -notmatch 'u32x\.dll') { Die "the source i76.exe does not import u32x.dll; run u32x\deploy-u32x.ps1 on the NEW folder after assembly instead" }
}

function Fingerprint([string]$root) {
    $n = 0; $bytes = [long]0; $newest = [long]0
    foreach ($f in Get-ChildItem -LiteralPath $root -Recurse -File -Force) {
        $n++; $bytes += $f.Length; if ($f.LastWriteTimeUtc.Ticks -gt $newest) { $newest = $f.LastWriteTimeUtc.Ticks }
    }
    "{0} files, {1} bytes, newest {2}" -f $n, $bytes, $newest
}

# ---- 1. classify the source ----------------------------------------------------------------------
# Residue = backups, logs and experiment leftovers in the driver's game folder. Nothing is dropped:
# residue goes to <Dest>\_carried-over\Interstate 76\ so the playable folder is clean and no saved
# state is lost.
$residueFiles = @('*.pre-*', '*.bak-*', '*.bak', '*.trunc-*', '*.old-*', '*.log', '*.stackdump', '*.CORRUPTED-*',
                  '*.ship', '*.dgvoodoo', '*.2017galaxy', '*.25fps', 'histogram.txt')
$residueDirs  = @('save-backup-*', 'weekend-state-*')
# Kept in place although they match: PLAY-i76.ps1's input.map guard restores from the newest
# input.map.* backup with intact analog sinks, so the known-good copy must sit beside the live file.
$keepInPlace  = @('input.map.bak-*-known-good')

function IsResidue([string]$rel) {
    $parts = $rel.Split('\')
    if ($parts.Count -gt 1) { foreach ($p in $residueDirs) { if ($parts[0] -like $p) { return $true } } }
    $leaf = $parts[$parts.Count - 1]
    foreach ($k in $keepInPlace) { if ($leaf -like $k) { return $false } }
    foreach ($p in $residueFiles) { if ($leaf -like $p) { return $true } }
    return $false
}

$dstGame   = Join-Path $Dest 'Interstate 76'
$dstCarry  = Join-Path $Dest '_carried-over\Interstate 76'
$actions   = New-Object System.Collections.ArrayList     # {From, To, Origin}

foreach ($f in Get-ChildItem -LiteralPath $srcGame -Recurse -File -Force) {
    $rel = $f.FullName.Substring($srcGame.Length + 1)
    if (IsResidue $rel) { [void]$actions.Add([pscustomobject]@{ From = $f.FullName; To = (Join-Path $dstCarry $rel); Origin = 'driver (residue, set aside)' }) }
    else                { [void]$actions.Add([pscustomobject]@{ From = $f.FullName; To = (Join-Path $dstGame $rel);  Origin = 'driver' }) }
}
# Top of the portable tree: the small helper files, and Lossless Scaling unless declined. The
# bundled i76-everywhere\ clone (a July snapshot with its own .git) is NOT carried: the repo is
# the source of scripts now.
$topKeep = @('CAMSWEEP.bat', 'HEADTRACK.bat', 'HEADTRACK-TEST.bat', 'Setup-FrameGen.ps1')
foreach ($n in $topKeep) {
    $p = Join-Path $Source $n
    if (Test-Path -LiteralPath $p) { [void]$actions.Add([pscustomobject]@{ From = $p; To = (Join-Path $Dest $n); Origin = 'driver (top level)' }) }
}
$srcLS = Join-Path $Source 'Lossless Scaling'
$haveLS = (-not $NoLosslessScaling) -and (Test-Path -LiteralPath (Join-Path $srcLS 'LosslessScaling.exe'))
if ($haveLS) {
    foreach ($f in Get-ChildItem -LiteralPath $srcLS -Recurse -File -Force) {
        [void]$actions.Add([pscustomobject]@{ From = $f.FullName; To = (Join-Path $Dest ('Lossless Scaling\' + $f.FullName.Substring($srcLS.Length + 1))); Origin = 'driver (Lossless Scaling)' })
    }
}

# Overlays: (source file, name inside "Interstate 76", label). Applied after the driver copy.
$overlays = New-Object System.Collections.ArrayList
[void]$overlays.Add(@{ From = $StrlkupDll; Name = 'STRLKUP.DLL'; Label = 'overlay: music-fix proxy' })
[void]$overlays.Add(@{ From = $U32xDll;    Name = 'u32x.dll';    Label = 'overlay: u32x' })
if ($GameExe)            { [void]$overlays.Add(@{ From = $GameExe; Name = 'i76.exe'; Label = 'overlay: game exe' }) }
if (-not $KeepSourceConf) { [void]$overlays.Add(@{ From = (Resolve-Path -LiteralPath $DgVoodooConf).Path; Name = 'dgVoodoo.conf'; Label = 'overlay: dgVoodoo conf' }) }
[void]$overlays.Add(@{ From = (Join-Path $repo 'PLAY-i76.ps1'); Name = 'PLAY-i76.ps1'; Label = 'overlay: launcher (repo)' })

$disablePatch = (-not $KeepI76Patch) -and ($Preset -ne 'stock')

# ---- plan ----------------------------------------------------------------------------------------
$nGame  = @($actions | Where-Object { $_.Origin -eq 'driver' }).Count
$nCarry = @($actions | Where-Object { $_.Origin -like '*residue*' }).Count
Say "Source      : $Source" 'Cyan'
Say "Dest        : $Dest" 'Cyan'
Say "Golden      : $(if ($GoldenDest) { $GoldenDest } else { '(none)' })" 'Cyan'
Say ("Game files  : {0} to 'Interstate 76\', {1} residue files to '_carried-over\'" -f $nGame, $nCarry)
Say ("Lossless Scaling : {0}" -f $(if ($haveLS) { 'carried' } else { 'not carried' }))
foreach ($o in $overlays) { Say ("Overlay     : {0,-14} <- {1}  (md5 {2})" -f $o.Name, $o.From, (Md5 $o.From)) }
Say ("Presets     : {0}\presets\*.psd1 -> 'Interstate 76\presets\'; PLAY.bat uses -Preset {1}" -f $repo, $Preset)
Say ("I76PATCH.DLL: {0}" -f $(if ($disablePatch) { 'renamed to I76PATCH.DLL.disabled in the NEW folder (20 fps cap off)' } else { 'left active' }))
if ($KeepSourceConf) { Say "dgVoodoo.conf: the DRIVER'S conf is carried unchanged. If dgVoodoo rejects it, the new folder depends on %APPDATA%\dgVoodoo\dgVoodoo.conf and is not independent." 'Yellow' }
if ($Plan) { Say "`n-Plan: nothing written." 'Yellow'; exit 0 }

# ---- 2. copy -------------------------------------------------------------------------------------
$fpBefore = Fingerprint $Source
$manifest = New-Object System.Collections.ArrayList     # {Rel, Bytes, Md5, Origin}

function CopyVerified([string]$from, [string]$to, [string]$origin) {
    $dir = Split-Path -Parent $to
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    Copy-Item -LiteralPath $from -Destination $to -Force
    # a copy carries the read-only bit (the portable's top-level files have it); clear it on the copy
    $it = Get-Item -LiteralPath $to -Force
    if ($it.IsReadOnly) { $it.IsReadOnly = $false }
    $a = Md5 $from; $b = Md5 $to
    if ($a -ne $b) { throw "copy verify failed: $to ($b) != $from ($a)" }
    [void]$manifest.Add([pscustomobject]@{ Rel = $to.Substring($Dest.Length + 1); Bytes = (Get-Item -LiteralPath $to).Length; Md5 = $b; Origin = $origin })
}
function NoteWritten([string]$path, [string]$origin) {
    [void]$manifest.Add([pscustomobject]@{ Rel = $path.Substring($Dest.Length + 1); Bytes = (Get-Item -LiteralPath $path).Length; Md5 = (Md5 $path); Origin = $origin })
}
function DropFromManifest([string]$path) {
    $rel = $path.Substring($Dest.Length + 1)
    $hit = @($manifest | Where-Object { $_.Rel -ieq $rel })
    foreach ($h in $hit) { $manifest.Remove($h) }
}

New-Item -ItemType Directory -Path $Dest | Out-Null      # fails if it appeared meanwhile: intended
Say "`nCopying $($actions.Count) files ..." 'Cyan'
foreach ($a in $actions) { CopyVerified $a.From $a.To $a.Origin }

# ---- 3. overlays ---------------------------------------------------------------------------------
foreach ($o in $overlays) {
    $target = Join-Path $dstGame $o.Name
    $newMd5 = Md5 $o.From
    if (Test-Path -LiteralPath $target) {
        $oldMd5 = Md5 $target
        if ($oldMd5 -eq $newMd5) { Say ("  {0}: the driver already has this build ({1})" -f $o.Name, $newMd5.Substring(0, 8)); continue }
        $aside = "$target.driver-$($oldMd5.Substring(0, 8))"
        DropFromManifest $target
        Move-Item -LiteralPath $target -Destination $aside       # inside Dest only
        NoteWritten $aside "driver's $($o.Name), set aside by the overlay"
    }
    CopyVerified $o.From $target $o.Label
    Say ("  {0}: {1}" -f $o.Name, $o.Label) 'Green'
}

# presets beside the launcher
$dstPresets = Join-Path $dstGame 'presets'
foreach ($p in Get-ChildItem -LiteralPath (Join-Path $repo 'presets') -Filter '*.psd1') { CopyVerified $p.FullName (Join-Path $dstPresets $p.Name) 'repo: presets' }

# GOG's 20 fps cap: with it loaded a 60/120 preset runs under the cap and looks like it does nothing
if ($disablePatch) {
    $patch = Join-Path $dstGame 'I76PATCH.DLL'
    if (Test-Path -LiteralPath $patch) {
        DropFromManifest $patch
        Rename-Item -LiteralPath $patch -NewName 'I76PATCH.DLL.disabled'
        NoteWritten (Join-Path $dstGame 'I76PATCH.DLL.disabled') 'driver (renamed: 20 fps cap off)'
        Say "  I76PATCH.DLL -> I76PATCH.DLL.disabled" 'Green'
    }
}

# save editor (current repo build; the driver's top-level html is the 2026-07-21 pre-fix parser)
foreach ($n in 'i76-save-editor.html', 'i76-save-editor.py') {
    $p = Join-Path $repo $n
    if (Test-Path -LiteralPath $p) { CopyVerified $p (Join-Path $Dest $n) 'repo: save editor' }
}
$lint = Join-Path $repo 'tools\lint-input-map.py'
if (Test-Path -LiteralPath $lint) { CopyVerified $lint (Join-Path $Dest '_tools\lint-input-map.py') 'repo: input.map linter' }

if ($IncludeFfbTools) {
    foreach ($p in Get-ChildItem -LiteralPath (Join-Path $repo 'tools\ffb') -Filter '*.ps1') { CopyVerified $p.FullName (Join-Path $dstGame ('_ffb\' + $p.Name)) 'repo: tools\ffb (working tree)' }
}

# ---- 4. launchers --------------------------------------------------------------------------------
# "-LosslessScaling none": powershell.exe -File swallows an empty-string argument, so a word that
# is not a path is used to say "do not start it". PLAY-i76.ps1 only starts it if the path exists.
function WriteAscii([string]$path, [string]$text) {
    [IO.File]::WriteAllText($path, ($text -replace "`r?`n", "`r`n"), [Text.Encoding]::ASCII)
    NoteWritten $path 'generated by Make-Daily-Driver.ps1'
}
WriteAscii (Join-Path $Dest 'PLAY.bat') @"
@echo off
REM Interstate '76 daily driver. Preset: $Preset (see "Interstate 76\presets").
REM Run at the physical console, never over Remote Desktop. Plug the wheel/pad in first.
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Interstate 76\PLAY-i76.ps1" -GameDir "%~dp0Interstate 76" -Exe i76.exe -Preset $Preset -LosslessScaling none
"@
WriteAscii (Join-Path $Dest 'PLAY-stock.bat') @"
@echo off
REM The same folder with NO engine switches (preset stock). Frame rate is whatever dgVoodoo paces
REM (60) unless I76PATCH.DLL.disabled is renamed back to I76PATCH.DLL (GOG's 20 fps cap).
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Interstate 76\PLAY-i76.ps1" -GameDir "%~dp0Interstate 76" -Exe i76.exe -Preset stock -LosslessScaling none
"@
if ($haveLS) {
    WriteAscii (Join-Path $Dest 'PLAY-with-FrameGen.bat') @"
@echo off
REM As PLAY.bat, with the bundled Lossless Scaling started first (its "Interstate '76 Gold Edition"
REM profile in %LOCALAPPDATA%\Lossless Scaling\Settings.xml engages by window title: LSFG x2).
REM At $Preset the game already renders every frame; frame generation on top is optional.
start "" "%~dp0Lossless Scaling\LosslessScaling.exe"
timeout /t 3 /nobreak >nul
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Interstate 76\PLAY-i76.ps1" -GameDir "%~dp0Interstate 76" -Exe i76.exe -Preset $Preset -LosslessScaling none
"@
}
WriteAscii (Join-Path $Dest 'BACKUP-SAVES.bat') @'
@echo off
REM Copies the save set to save-backups\<timestamp>\ beside this file. Run it after a session.
REM Close the game first: savegame.dir and the .cmp files are only consistent with the game closed.
setlocal
tasklist /FI "IMAGENAME eq i76.exe" | find /I "i76.exe" >nul && (echo The game is running - close it first.& pause & exit /b 1)
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set TS=%%t
set OUT=%~dp0save-backups\%TS%
mkdir "%OUT%"
for %%f in (savegame.dir save*.cmp reconfig.spc trip*.spc user.* I76PLYR.DEF I76DFLT.DEF NSCR.DAT victory.rec *.fot input.map) do if exist "%~dp0Interstate 76\%%f" copy /y "%~dp0Interstate 76\%%f" "%OUT%\" >nul
echo Saved to %OUT%
dir /b "%OUT%"
pause
'@

# ---- 5. read-only checks on the NEW folder (results go in the manifest) ---------------------------
$checks = New-Object System.Collections.ArrayList
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $r = (& python (Join-Path $repo 'tools\lint-input-map.py') $dstGame 2>&1 | Out-String).Trim()
    [void]$checks.Add("lint-input-map: exit $LASTEXITCODE - " + ($r -split "`n")[-1].Trim())
    $r = (& python (Join-Path $repo 'i76-save-editor.py') --dir $dstGame --check 2>&1 | Out-String).Trim()
    [void]$checks.Add("save editor --check: exit $LASTEXITCODE - " + ($r -split "`n")[0].Trim())
} else { [void]$checks.Add('python not found: lint-input-map and save --check NOT run') }
$sh = [IO.File]::ReadAllBytes((Join-Path $dstGame 'i76shell.dll'))
[void]$checks.Add(("i76shell.dll text-entry bytes +0x1B52C/+0x1B535 = {0:X2}/{1:X2} (want 41/08)" -f $sh[0x1B52C], $sh[0x1B535]))
$dir = [IO.File]::ReadAllBytes((Join-Path $dstGame 'savegame.dir'))
$cnt = [BitConverter]::ToUInt32($dir, 0)
[void]$checks.Add(("savegame.dir: {0} records, {1} B (want {2})" -f $cnt, $dir.Length, (4 + 60 * $cnt)))
foreach ($n in 'i76.exe', 'i76shell.dll') {
    $t = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes((Join-Path $dstGame $n)))
    [void]$checks.Add(("{0} imports u32x.dll: {1}" -f $n, ($t -match 'u32x\.dll')))
}
[void]$checks.Add(("strlkup_orig.dll present: {0}; I76PATCH.DLL active: {1}" -f (Test-Path -LiteralPath (Join-Path $dstGame 'strlkup_orig.dll')), (Test-Path -LiteralPath (Join-Path $dstGame 'I76PATCH.DLL'))))

# ---- 6. manifest ---------------------------------------------------------------------------------
function WriteManifest([string]$root, [string]$title, [string[]]$extra) {
    $key = @('Interstate 76\i76.exe', 'Interstate 76\i76shell.dll', 'Interstate 76\u32x.dll', 'Interstate 76\STRLKUP.DLL',
             'Interstate 76\strlkup_orig.dll', 'Interstate 76\dgVoodoo.conf', 'Interstate 76\Glide2x.dll', 'Interstate 76\DDraw.dll',
             'Interstate 76\input.map', 'Interstate 76\PLAY-i76.ps1', 'Interstate 76\savegame.dir', 'Interstate 76\I7_SFRCE.DLL',
             'Interstate 76\i76wheel.exe', 'Interstate 76\_ahk\i76-remap.ahk')
    $L = New-Object System.Collections.ArrayList
    [void]$L.Add("# $title")
    [void]$L.Add('')
    [void]$L.Add("Assembled $(Get-Date -Format 'yyyy-MM-dd HH:mm') by tools\Make-Daily-Driver.ps1 (repo $((& git -C $repo rev-parse --short HEAD 2>$null))).")
    [void]$L.Add('')
    [void]$L.Add("- source driver: ``$Source``")
    [void]$L.Add("- preset in PLAY.bat: ``$Preset``")
    foreach ($o in $overlays) { [void]$L.Add("- $($o.Label): ``$($o.From)`` md5 ``$(Md5 $o.From)``") }
    foreach ($e in $extra) { [void]$L.Add("- $e") }
    [void]$L.Add('')
    [void]$L.Add('## Checks at assembly (read-only, no game run)')
    [void]$L.Add('')
    foreach ($c in $checks) { [void]$L.Add("- $c") }
    [void]$L.Add('')
    [void]$L.Add('## Key files')
    [void]$L.Add('')
    [void]$L.Add('| file | bytes | md5 | origin |')
    [void]$L.Add('|---|---|---|---|')
    foreach ($k in $key) { $m = $manifest | Where-Object { $_.Rel -ieq $k } | Select-Object -First 1; if ($m) { [void]$L.Add("| ``$($m.Rel)`` | $($m.Bytes) | ``$($m.Md5)`` | $($m.Origin) |") } }
    [void]$L.Add('')
    [void]$L.Add("## Every file ($($manifest.Count))")
    [void]$L.Add('')
    [void]$L.Add('| file | bytes | md5 | origin |')
    [void]$L.Add('|---|---|---|---|')
    foreach ($m in ($manifest | Sort-Object Rel)) { [void]$L.Add("| ``$($m.Rel)`` | $($m.Bytes) | ``$($m.Md5)`` | $($m.Origin) |") }
    [IO.File]::WriteAllLines((Join-Path $root 'MANIFEST.md'), [string[]]$L, [Text.Encoding]::ASCII)
}
WriteManifest $Dest "Interstate '76 daily driver - manifest" @()
Say "MANIFEST.md written ($($manifest.Count) files)." 'Green'

# ---- 7. golden copy ------------------------------------------------------------------------------
if ($GoldenDest) {
    Say "`nGolden copy -> $GoldenDest ..." 'Cyan'
    New-Item -ItemType Directory -Path $GoldenDest | Out-Null
    foreach ($m in $manifest) {
        $from = Join-Path $Dest $m.Rel; $to = Join-Path $GoldenDest $m.Rel
        $dir = Split-Path -Parent $to
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        Copy-Item -LiteralPath $from -Destination $to -Force
        if ((Md5 $to) -ne $m.Md5) { throw "golden verify failed: $to" }
    }
    Copy-Item -LiteralPath (Join-Path $Dest 'MANIFEST.md') -Destination (Join-Path $GoldenDest 'MANIFEST.md')
    $manifestMd5 = Md5 (Join-Path $GoldenDest 'MANIFEST.md')
    [IO.File]::WriteAllLines((Join-Path $GoldenDest 'GOLDEN-DO-NOT-PLAY.txt'), [string[]]@(
        "This is the GOLDEN copy of the Interstate '76 daily driver. Do not play from it and do not test in it.",
        "It changes only by a recorded promotion (PROMOTIONS.md). The folder to play from is:",
        "  $Dest",
        "Its save files are the snapshot taken at assembly; live progress is in the daily driver."), [Text.Encoding]::ASCII)
    [IO.File]::WriteAllLines((Join-Path $GoldenDest 'PROMOTIONS.md'), [string[]]@(
        "# Promotions into the golden copy",
        "",
        "One row per promotion, newest last. A promotion replaces named files here AND in the daily driver,",
        "after the change passed its gate on the sandbox. The replaced files go to _rollback\<id>\ in both.",
        "",
        "| id | date | what | files (md5 before -> after) | gate (what was run, n, result) | rollback folder |",
        "|---|---|---|---|---|---|",
        "| 0 | $(Get-Date -Format 'yyyy-MM-dd HH:mm') | initial assembly from $Source | MANIFEST.md md5 $manifestMd5 | assembly checks only (see MANIFEST.md); console gate pending | none |"), [Text.Encoding]::ASCII)
    Say "Golden copy written and verified ($($manifest.Count) files)." 'Green'
}

# ---- 8. the source must be exactly as it was -----------------------------------------------------
$fpAfter = Fingerprint $Source
if ($fpAfter -ne $fpBefore) {
    Say "SOURCE CHANGED DURING THE RUN:`n  before: $fpBefore`n  after : $fpAfter" 'Red'
    Say "This script wrote nothing there; something else did (the game, another session). Re-check the copy." 'Red'
    exit 2
}
Say "`nSource unchanged ($fpAfter)." 'Green'
Say "DONE. Next: docs\NEW-DAILY-DRIVER-RECIPE.md section 5 (verification), at the physical console." 'Green'
foreach ($c in $checks) { Say "  $c" }
exit 0
