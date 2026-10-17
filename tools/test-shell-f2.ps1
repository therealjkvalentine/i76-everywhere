<#
  test-shell-f2.ps1 - one-click owner test for shell fix F2 (the orphaned Save Bookmark), i76-map shell\LIVE-TESTS.md T3.

  F2 (tools\patch-shell-modals.py --with-f2; i76-map shell\FIXES.md F2, SAVE.md s.4): SaveMenu_Edit 0x100147a0 resets the
  slot variable to -1 every time the edit field is entered. Re-entering it after the bookmark record was already added
  makes the save write slot -1: savegame.dir names saveNNN, the disk gets save-001.cmp, and after a restart the bookmark
  is missing from the load list. F2 removes the reset (10 bytes) and nothing else.

  What this script does, in -GameDir (a TEST copy; the daily driver, golden copy and Downloads are refused):
    1. copies savegame.dir and save*.cmp to save-backup-f2test-<time>\ and remembers the bookmark list;
    2. -Mode F2: keeps i76shell.dll as i76shell.dll.pre-f2 (once) and copies i76shell.dll.F2 over it (md5 read back);
       -Mode Control: leaves the shell as it is (the stock-behaviour control);
    3. starts the game exactly as PLAY.bat does (PLAY-i76.ps1 -Preset best-wide, wide conf) and waits for it to close;
    4. -Mode F2: puts the original shell back (md5 read back), so the folder is as before except the saves;
    5. compares savegame.dir with step 1 and prints every new or changed bookmark, whether its .cmp exists, and any new
       .cmp no bookmark names (the orphan). The same text goes to F2-TEST-<mode>-<time>.txt next to the game.

  Steps in the game (the trigger sequence, T3): load any bookmark -> garage -> Options -> Save Bookmark; type ORPHANA;
  click once on empty paper to the right of the list (not a row, not a button); click the name field; type ORPHANB;
  click SAVE; quit the game.  Prediction: Control = ORPHAN (ORPHANB names saveNNN, saveNNN.cmp missing, save-001.cmp
  new); F2 = OK (saveNNN.cmp exists, and ORPHANB is in the load list after a restart).

    powershell -ExecutionPolicy Bypass -File tools\test-shell-f2.ps1 -GameDir "<test copy>\Interstate 76" -Mode Control
    powershell -ExecutionPolicy Bypass -File tools\test-shell-f2.ps1 -GameDir "<test copy>\Interstate 76" -Mode F2
    ... -Mode Report    (no game: only compare savegame.dir with the newest backup)
#>
param(
    [Parameter(Mandatory)][string]$GameDir,
    [ValidateSet('Control', 'F2', 'Report')][string]$Mode = 'F2',
    [string]$Preset = 'best-wide',
    [switch]$NoGame
)
$ErrorActionPreference = 'Stop'
$GameDir = (Resolve-Path $GameDir).Path.TrimEnd('\')
foreach ($bad in @('\Games\Interstate76-2026-10-03', '\Games\Interstate76-golden', '\Downloads\')) {
    if ($GameDir.IndexOf($bad, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
        Write-Host "REFUSED: $GameDir is the daily driver, the golden copy or the portable install. Use a test copy." -ForegroundColor Red
        exit 2
    }
}
function Md5([string]$p) { (Get-FileHash -Algorithm MD5 -LiteralPath $p).Hash.ToLower() }
function Read-Dir([string]$p) {
    $out = @()
    if (-not (Test-Path -LiteralPath $p)) { return $out }
    $b = [IO.File]::ReadAllBytes($p)
    $n = [BitConverter]::ToUInt32($b, 0)
    for ($k = 0; $k -lt $n -and (4 + 60 * $k + 60) -le $b.Length; $k++) {
        $o = 4 + 60 * $k
        $name = [Text.Encoding]::ASCII.GetString($b, $o + 4, 32).Split([char]0)[0]
        $file = [Text.Encoding]::ASCII.GetString($b, $o + 0x24, 16).Split([char]0)[0]
        $out += [pscustomobject]@{ Index = $k; Scene = [BitConverter]::ToUInt32($b, $o); Name = $name; File = $file }
    }
    if ($b.Length -ne 4 + 60 * $n) { Write-Host "note: savegame.dir is $($b.Length) bytes, 4 + 60 x $n = $(4 + 60 * $n)" -ForegroundColor Yellow }
    return $out
}

$dirFile = Join-Path $GameDir 'savegame.dir'
$shell = Join-Path $GameDir 'i76shell.dll'
$f2 = Join-Path $GameDir 'i76shell.dll.F2'
$pre = Join-Path $GameDir 'i76shell.dll.pre-f2'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

if ($Mode -eq 'Report') {
    $bk = Get-ChildItem -LiteralPath $GameDir -Directory -Filter 'save-backup-f2test-*' | Sort-Object Name | Select-Object -Last 1
    if (-not $bk) { Write-Host 'no save-backup-f2test-* folder: nothing to compare against' -ForegroundColor Red; exit 1 }
    $backup = $bk.FullName
} else {
    $backup = Join-Path $GameDir "save-backup-f2test-$stamp"
    New-Item -ItemType Directory -Path $backup | Out-Null
    Get-ChildItem -LiteralPath $GameDir -File | Where-Object { $_.Name -eq 'savegame.dir' -or $_.Name -like 'save*.cmp' } |
        Copy-Item -Destination $backup
    Write-Host "saves backed up to $backup ($((Get-ChildItem $backup).Count) files)"
}
$before = Read-Dir (Join-Path $backup 'savegame.dir')
$cmpBefore = @(Get-ChildItem -LiteralPath $backup -File -Filter '*.cmp' | ForEach-Object Name)

$origMd5 = Md5 $shell
$swapped = $false
try {
    if ($Mode -eq 'F2') {
        if (-not (Test-Path -LiteralPath $f2)) { throw "i76shell.dll.F2 is missing in $GameDir" }
        $f2Md5 = Md5 $f2
        if ($origMd5 -ne $f2Md5) {
            if (-not (Test-Path -LiteralPath $pre)) { Copy-Item -LiteralPath $shell -Destination $pre }
            elseif ((Md5 $pre) -ne $origMd5) { throw "i76shell.dll ($origMd5) differs from i76shell.dll.pre-f2 ($(Md5 $pre)): restore it first" }
            Copy-Item -LiteralPath $f2 -Destination $shell -Force
            $swapped = $true
            if ((Md5 $shell) -ne $f2Md5) { throw 'F2 shell copy did not read back' }
        }
        Write-Host "shell for this run: F2 $f2Md5 (original $origMd5 kept as i76shell.dll.pre-f2)"
    } elseif ($Mode -eq 'Control') {
        Write-Host "shell for this run: unchanged $origMd5 (control)"
    }
    if ($Mode -ne 'Report' -and -not $NoGame) {
        Write-Host ''
        Write-Host 'IN THE GAME: load any bookmark -> garage -> Options -> Save Bookmark; type ORPHANA; click once on empty paper' -ForegroundColor Cyan
        Write-Host 'right of the list (not a row, not a button); click the name field; type ORPHANB; click SAVE; quit the game.' -ForegroundColor Cyan
        $wide = Join-Path $GameDir 'dgVoodoo.wide.conf'
        if ($Preset -like 'best-wide*' -and (Test-Path -LiteralPath $wide)) { Copy-Item -LiteralPath $wide -Destination (Join-Path $GameDir 'dgVoodoo.conf') -Force }
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $GameDir 'PLAY-i76.ps1') -GameDir $GameDir -Exe i76.exe -Preset $Preset -LosslessScaling none
    }
} finally {
    if ($swapped) {
        Copy-Item -LiteralPath $pre -Destination $shell -Force
        $back = Md5 $shell
        if ($back -eq $origMd5) { Write-Host "shell restored: $back" } else { Write-Host "SHELL RESTORE FAILED: $back, expected $origMd5 (copy i76shell.dll.pre-f2 over i76shell.dll)" -ForegroundColor Red }
    }
}

$after = Read-Dir $dirFile
$cmpAfter = @(Get-ChildItem -LiteralPath $GameDir -File -Filter '*.cmp' | ForEach-Object Name)
$lines = @("F2 bookmark test, mode $Mode, $stamp, $GameDir", "shell during the run: $(if ($Mode -eq 'F2') { 'F2 ' + (Md5 $f2) } else { $origMd5 })",
           "bookmarks before: $($before.Count), after: $($after.Count)")
$verdict = 'NO NEW BOOKMARK (was SAVE clicked?)'
foreach ($r in $after) {
    $old = $before | Where-Object { $_.Index -eq $r.Index } | Select-Object -First 1
    if ($old -and $old.Name -eq $r.Name -and $old.File -eq $r.File -and $old.Scene -eq $r.Scene) { continue }
    $has = Test-Path -LiteralPath (Join-Path $GameDir ($r.File + '.cmp'))
    $lines += ("  {0} bookmark #{1} '{2}' scene {3} file {4}.cmp {5}" -f $(if ($old) { 'changed' } else { 'new' }), $r.Index, $r.Name, $r.Scene, $r.File, $(if ($has) { 'EXISTS' } else { 'MISSING' }))
    if (-not $old) { $verdict = if ($has) { 'OK: the new bookmark has its file' } else { 'ORPHAN: the new bookmark names a file that was not written' } }
}
$named = @($after | ForEach-Object { $_.File + '.cmp' })
foreach ($c in $cmpAfter) {
    if ($cmpBefore -notcontains $c -and $named -notcontains $c) { $lines += "  new file no bookmark names: $c (the orphan's data)" }
}
$lines += "VERDICT: $verdict"
$lines += "Prediction: Control = ORPHAN, F2 = OK. Then start PLAY.bat once and check ORPHANB is in the Load Bookmark list (F2) / missing (Control)."
$lines += "Saves before the run: $backup"
$report = Join-Path $GameDir "F2-TEST-$Mode-$stamp.txt"
$lines | Set-Content -LiteralPath $report -Encoding ascii
$lines | ForEach-Object { Write-Host $_ }
Write-Host "written: $report"
