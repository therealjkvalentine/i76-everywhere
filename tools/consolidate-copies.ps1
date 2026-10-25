<#
.SYNOPSIS
  Consolidate the I'76 game copies into dev / test / rc / daily-driver (+ Nitro equivalents). PLAN 2026-10-24 - NOT RUN.
  See docs\COPIES-PLAN-2026-10-24.md. DRY-RUN BY DEFAULT: prints every action, size and lock verdict, changes nothing.

.PARAMETER Execute      Really do it. Without it nothing is moved, deleted or linked.
.PARAMETER Phase        Archive | Rename | Cruft | All (default All). Order inside All: Archive, Rename, Cruft.
.PARAMETER Only         Restrict to plan rows whose Name matches this wildcard (e.g. 'game-scott*'); Cruft: matches the role name.
.PARAMETER QuietMinutes A folder with a file written in the last N minutes (default 30) counts as held by a lane.
.PARAMETER HeldOk       Names (wildcards) you have personally confirmed idle; skips the quiet-time test only (never the process test).
.PARAMETER Release      Plan rows marked WaitFor (a lane was using them on 2026-10-24) are skipped unless named here (wildcards; '*' = all).
.PARAMETER IncludeRcLaunchers  Also prune stale PLAY-*.bat in release-candidate / daily-driver / nitro-lan (default: listed only for dev/test).
.PARAMETER ArchiveRoot  Where archived copies and quarantined cruft go (D: only).

  Safety: never touches a folder when (1) any process has an exe/command line under the folder (the link path or its target),
  (2) .console-test.lock exists in it, (3) the lab .console-owner / .fps-queue / .fps-lock text names it, (4) a file in it was written in
  the last QuietMinutes. Nothing is ever deleted outright: archive = verified copy to D:, then remove the C: source; cruft = moved into
  $ArchiveRoot\cruft. Saves (savegame*, *.sav, *.dir, SAVE*) and _rollback are never touched.
#>
[CmdletBinding()]
param(
  [switch]$Execute,
  [ValidateSet('Archive','Rename','Cruft','All')][string]$Phase = 'All',
  [string]$Only = '*',
  [int]$QuietMinutes = 30,
  [string[]]$HeldOk = @(),
  [string[]]$Release = @(),
  [switch]$IncludeRcLaunchers,
  [string]$ArchiveRoot = 'D:\i76-archive\consolidated-20261025',
  [string]$CruftRoot = 'D:\i76-archive\cruft-20261025'
)
$ErrorActionPreference = 'Stop'
$Lab = (Join-Path $env:USERPROFILE 'i76-uncap-lab'); $Games = (Join-Path $env:USERPROFILE 'Games\I76')
if ($ArchiveRoot -notmatch '^[Dd]:\\') { throw 'ArchiveRoot must be on D:' }
$mode = if ($Execute) { 'EXECUTE' } else { 'DRY-RUN' }
Write-Host "== consolidate-copies ($mode) phase=$Phase only=$Only quiet=${QuietMinutes}min"

# ---- the plan. Action: Keep | Rename | Archive. WaitFor = a lane was running on the evening of 2026-10-24; the lock checks decide at run time.
# Junction=$true: leave a junction at the OLD path pointing at the new one, because tools/docs still use the old name.
$Plan = @(
  # --- OWNER RULING 2026-10-24: three tiers per game (dev / test / main); main copies are "Interstate 76 Gold" / "Interstate 76 Nitro". No golden copy.
  # main Gold = the release candidate content; the old daily driver is archived as the rollback.
  @{Name='daily-driver';      Root=$Games; Action='Archive'; Junction=$false; To='D:\i76-archive\daily-driver-pre-20261025'; Alt='daily-driver'},
  @{Name='release-candidate'; Root=$Games; Action='Rename'; To="$Games\Interstate 76 Gold"; Junction=$true; After='daily-driver'},
  @{Name='exp-polish2';       Root=$Lab; Action='Rename'; To="$Lab\dev-gold";   Junction=$true},
  @{Name='rc-twin-20261024';  Root=$Lab; Action='Rename'; To="$Lab\test-gold";  Junction=$true},
  @{Name='exp-nitro-owner';   Root=$Lab; Action='Rename'; To="$Games\Interstate 76 Nitro"; Junction=$true; Alt='nitro-owner|nitro-mp'},
  @{Name='exp-nitro-polish';  Root=$Lab; Action='Rename'; To="$Lab\test-nitro"; Junction=$true; Alt='nitro-polish|nitro-parity'},
  @{Name='nitro-lan';         Root=$Games; Action='Archive'; Junction=$true; WaitFor='after Interstate 76 Nitro is main and LAN-capable'},
  # the family LAN pack goes only after the Gold-LAN lane has merged it into the RC stage
  @{Name='lan';               Root=$Games; Action='Archive'; Junction=$true; WaitFor='Gold-LAN merge into RC stage'},
  # read-only references that docs/tools name (junction only because tools still name them)
  @{Name='golden';Root=$Games;Action='Archive';Junction=$true}, @{Name='nitro';Root=$Games;Action='Archive';Junction=$true},
  @{Name='nitro-plus-original';Root=$Games;Action='Archive';Junction=$true}, @{Name='_archive';Root=$Games;Action='Archive';Junction=$false},
  @{Name='game';Root=$Lab;Action='Archive';Junction=$true},
  # idle lab copies
  @{Name='exp-debug';Root=$Lab;Action='Archive';Junction=$true}, @{Name='exp-jump2';Root=$Lab;Action='Archive';Junction=$true},
  @{Name='exp-morph';Root=$Lab;Action='Archive';Junction=$true}, @{Name='exp-nitro-mp-gold';Root=$Lab;Action='Archive';Junction=$true},
  @{Name='exp-nitro-port';Root=$Lab;Action='Archive';Junction=$true}, @{Name='exp-nitro-stockgl';Root=$Lab;Action='Archive';Junction=$true},
  @{Name='exp-p19-twin';Root=$Lab;Action='Archive';Junction=$true}, @{Name='game-sp';Root=$Lab;Action='Archive';Junction=$true},
  @{Name='game-fresh-gold';Root=$Lab;Action='Archive';Junction=$true}, @{Name='game-fresh-nitro';Root=$Lab;Action='Archive';Junction=$true},
  @{Name='game-scott-c';Root=$Lab;Action='Archive';Junction=$true}, @{Name='game-scott-motw';Root=$Lab;Action='Archive';Junction=$true},
  @{Name='game-scott-uninst';Root=$Lab;Action='Archive';Junction=$true},
  @{Name='exp-mac';Root=$Lab;Action='Archive';Junction=$false}, @{Name='exp-rcdraw';Root=$Lab;Action='Archive';Junction=$false},
  # lane-held on 2026-10-24 evening
  @{Name='game-scott';Root=$Lab;Action='Archive';Junction=$true;WaitFor='Scott kit lane (PLAY.bat cmd.exe alive)'},
  @{Name='game-scott-b';Root=$Lab;Action='Archive';Junction=$true;WaitFor='Scott kit lane (PLAY-PREVIEW.bat alive)'},
  @{Name='exp-nitro-mp';Root=$Lab;Action='Archive';Junction=$true;WaitFor='Nitro MP lane (.fps-queue nitro-mp-design)'},
  @{Name='exp-nitro-mp-b';Root=$Lab;Action='Archive';Junction=$true;WaitFor='Nitro MP lane'},
  @{Name='exp-nitro-types';Root=$Lab;Action='Archive';Junction=$true;WaitFor='Nitro MP / types lane'},
  @{Name='exp-nitro-types-b';Root=$Lab;Action='Archive';Junction=$true;WaitFor='Nitro MP / types lane'},
  @{Name='exp-faredge';Root=$Lab;Action='Archive';Junction=$true;WaitFor='owner ruling (far-edge)'},
  @{Name='exp-rebase';Root=$Lab;Action='Archive';Junction=$true;WaitFor='owner ruling (rebase)'},
  @{Name='controls-twin-20261024';Root=$Lab;Action='Archive';Junction=$true;WaitFor='FFB / controls lane'},
  @{Name='dgv2875-twin-20261024';Root=$Lab;Action='Archive';Junction=$true;WaitFor='launcher / dgVoodoo 2.87.5 lane'},
  @{Name='stab-gold-20261024';Root=$Lab;Action='Archive';Junction=$true;WaitFor='stability lane report'},
  @{Name='stab-nitro-20261024';Root=$Lab;Action='Archive';Junction=$true;WaitFor='stability lane report'}
)
# Already junctions into D: (archived 2026-10-23, skipped automatically): exp-airespawn exp-difficulty(-b) exp-jump exp-nitro(-base,-port-gold)
# exp-p19 exp-polish exp-rebase-trace twin-driver game-mpo-a..d autotest-p19 captures. game-mpo-c/-d and exp-nitro-port-gold are LIVE
# on 2026-10-24 (Gold LAN fixes lane runs i76.exe from them via the junction): the process test refuses them even if they were listed.
# game-tick -> release-candidate and game-dd-20261003 -> twin-driver stay as compatibility junctions.

# ---- lock checks ----
$script:Procs = Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -or $_.CommandLine }
$lockText = ''
foreach ($f in '.console-owner','.fps-queue','.fps-lock') { $p = Join-Path $Lab $f; if (Test-Path $p) { $lockText += "`n" + (Get-Content $p -Raw) } }
function Resolve-Real($path) {
  $i = Get-Item $path -Force -ErrorAction SilentlyContinue
  if ($i -and ($i.Attributes -band 'ReparsePoint') -and $i.Target) { return @($path, ($i.Target | Select-Object -First 1)) }
  return @($path)
}
function Test-Held($name, $full, $alt = '') {
  $why = @()
  foreach ($r in (Resolve-Real $full)) {
    $rx = [regex]::Escape($r) + '(?=[\\"''\s]|$)'
    $hit = @($script:Procs | Where-Object { ($_.ExecutablePath -and $_.ExecutablePath -match "(?i)^$rx") -or ($_.CommandLine -and $_.CommandLine -match "(?i)$rx") })
    if ($hit.Count) { $why += "process $((@($hit.ProcessId) | Select-Object -First 4) -join ',') uses $r" }
    if (Test-Path (Join-Path $r '.console-test.lock')) { $why += '.console-test.lock present' }
  }
  if ($lockText -and $lockText -match ("(?i)(?<![\w-])" + [regex]::Escape($name) + "(?![\w-])")) { $why += 'named in lab lock/queue file' }
  if ($alt -and $lockText -and $lockText -match ("(?i)(?<![\w-])(" + $alt + ")(?![\w-])")) { $why += "lane alias ($alt) in lab lock/queue file" }
  $checkQuiet = $true; foreach ($m in $HeldOk) { if ($name -like $m) { $checkQuiet = $false } }
  if ($checkQuiet) {
    $new = Get-ChildItem $full -Recurse -Force -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($new -and $new.LastWriteTime -gt (Get-Date).AddMinutes(-$QuietMinutes)) { $why += "file written $($new.LastWriteTime.ToString('HH:mm')) (<${QuietMinutes}min): $($new.Name)" }
  }
  return $why
}
function Get-GB($p) { [math]::Round(((Get-ChildItem $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum)/1GB, 2) }

# ---- Archive / Rename ----
if ($Phase -in 'Archive','Rename','All') {
  $tot = 0.0
  foreach ($row in $Plan | Where-Object { $_.Name -like $Only -and $_.Action -in 'Archive','Rename' }) {
    if ($Phase -ne 'All' -and $row.Action -ne $Phase) { continue }
    $src = Join-Path $row.Root $row.Name
    if (-not (Test-Path $src)) { Write-Host "skip   $($row.Name): not there"; continue }
    $it = Get-Item $src -Force
    if ($it.Attributes -band 'ReparsePoint') { Write-Host "skip   $($row.Name): already a junction -> $($it.Target)"; continue }
    if ($row.WaitFor) { $rel = $false; foreach ($m in $Release) { if ($row.Name -like $m) { $rel = $true } }; if (-not $rel) { Write-Host "WAIT   $($row.Name): $($row.WaitFor) (add -Release $($row.Name) once that lane reports)"; continue } }
    $held = @(Test-Held $row.Name $src $row.Alt)
    if ($held.Count) { Write-Host ("HELD   {0}: {1}{2}" -f $row.Name, ($held -join '; '), $(if ($row.WaitFor) { "  [waiting for: $($row.WaitFor)]" })); continue }
    $gb = Get-GB $src
    $sub = if ($row.Root -eq $Games) { 'Games-I76' } else { 'lab' }
    $dst = if ($row.To) { $row.To } else { Join-Path $ArchiveRoot "$sub\$($row.Name)" }
    Write-Host ("{0,-8}{1} ({2} GB) -> {3}{4}" -f $row.Action.ToUpper(), $row.Name, $gb, $dst, $(if ($row.Junction) { "  + junction $src -> $dst" }))
    if ($row.Action -eq 'Archive') { $tot += $gb }
    if (-not $Execute) { continue }
    if (Test-Path $dst) { Write-Host "  REFUSE: $dst exists"; continue }
    if ($row.Action -eq 'Rename') {
      Move-Item $src $dst
    } else {
      New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
      robocopy $src $dst /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
      if ($LASTEXITCODE -ge 8) { Write-Host "  robocopy failed ($LASTEXITCODE), source kept"; continue }
      $a = Get-ChildItem $src -Recurse -Force -File | Measure-Object Length -Sum
      $b = Get-ChildItem $dst -Recurse -Force -File | Measure-Object Length -Sum
      if ($a.Count -ne $b.Count -or $a.Sum -ne $b.Sum) { Write-Host "  VERIFY FAILED ($($a.Count)/$($a.Sum) vs $($b.Count)/$($b.Sum)); source kept"; continue }
      if (@(Test-Held $row.Name $src $row.Alt).Count) { Write-Host '  became held during the copy; source kept'; continue }
      try { Remove-Item $src -Recurse -Force -ErrorAction Stop } catch {
        # a copy is verified on D: already; some files (e.g. an in-use .ttf) refuse deletion: remove what can go, report the rest
        Get-ChildItem $src -Recurse -Force -File -ErrorAction SilentlyContinue | ForEach-Object { try { Remove-Item $_.FullName -Force -ErrorAction Stop } catch { Write-Host "  LEFT BEHIND (locked): $($_.Exception.Message)" } }
        Write-Host "  REMOVE INCOMPLETE for $($row.Name): verified copy is on $dst; delete the remainder later, no junction made"; continue
      }
    }
    if ($row.Junction) { New-Item -ItemType Junction -Path $src -Target $dst | Out-Null; Write-Host '  junction created' }
  }
  Write-Host ("Archive rows free ~{0:N2} GB on C: this run (HELD rows not counted)" -f $tot)
}

# ---- Cruft in the KEPT folders (moved into $ArchiveRoot\cruft, never deleted) ----
if ($Phase -in 'Cruft','All') {
  $Kept = @(
    @{Dir="$Games\Interstate 76 Gold"; Role='Interstate 76 Gold'}, @{Dir="$Games\Interstate 76 Nitro"; Role='Interstate 76 Nitro'},
    @{Dir="$Lab\dev-gold"; Role='dev-gold'},   @{Dir="$Lab\test-gold"; Role='test-gold'},
    @{Dir="$Lab\dev-nitro"; Role='dev-nitro'}, @{Dir="$Lab\test-nitro"; Role='test-nitro'}
  )
  # before the Rename phase the new names do not exist yet: use the old ones so a dry-run lists the right folders
  $alias = @{ "$Games\Interstate 76 Gold"="$Games\release-candidate"; "$Games\Interstate 76 Nitro"="$Lab\exp-nitro-owner"; "$Lab\dev-gold"="$Lab\exp-polish2"; "$Lab\test-gold"="$Lab\rc-twin-20261024"; "$Lab\dev-nitro"="$Lab\exp-nitro-owner"; "$Lab\test-nitro"="$Lab\exp-nitro-polish" }
  $keepNames = '(?i)\.(u32x)?orig$|^strlkup_orig\.dll$'                       # the real originals stay (strlkup_orig.dll, i76.exe.u32xorig, i76shell.dll.orig)
  $never     = '(?i)^(savegame.*|.*\.sav|.*\.dir|SAVE.*|.*\.def)$|\\(_rollback|saves?|SAVE[^\\]*)\\'
  $staleBat  = '(?i)^PLAY-(TICK-(33|36|39|44|47|66|CHOOSE)|OWNER-(2300-(ATMOS|BIGBLEND|FEATHER|FOG|HAZE|MIRROR|MORPH|SHADE|SMOOTH|SPARSE|TEX|ALL-MENU)|MORPH-STATELESS|NEXT-2300|SKY-.*)|WITH-.*)\.bat$'
  $grand = 0L
  foreach ($k in $Kept) {
    if ($Only -ne '*' -and $k.Role -notlike $Only) { continue }
    $dir = $k.Dir
    if (-not (Test-Path $dir) -and $alias[$dir] -and (Test-Path $alias[$dir])) { $dir = $alias[$dir] }
    if (-not (Test-Path $dir)) { Write-Host "skip   $($k.Role): $dir not there"; continue }
    $held = @(Test-Held (Split-Path $dir -Leaf) $dir)
    if ($held.Count) { Write-Host "HELD   cruft in $($k.Role) ($dir): $($held -join '; ')"; continue }
    $ver = (Get-ChildItem $dir -Recurse -Depth 1 -Filter 'VERSION*' -File -ErrorAction SilentlyContinue | ForEach-Object { Get-Content $_.FullName -Raw }) -join "`n"
    $files = @(Get-ChildItem $dir -Recurse -Force -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName.Substring($dir.Length) -notmatch $never -and $_.Name -notmatch $never -and $_.Name -notmatch '(?i)^(savegame|SAVE)' -and $_.Name -notmatch $keepNames })
    $maps = @($files | Where-Object { $_.Name -like 'input.map.*' } | Sort-Object @{e={$_.Name -match 'known-good'};Descending=$true}, @{e='LastWriteTime';Descending=$true})   # keep one: a known-good backup if there is one, else the newest
    $hit = New-Object System.Collections.ArrayList
    foreach ($f in $files) {
      $n = $f.Name; $why = $null
      if ($n -match '(?i)^strlkup\.dll\..+') { $h = [regex]::Match($n,'[0-9a-f]{8}').Value; if (-not ($h -and $ver -match $h)) { $why = 'proxy backup not named in VERSION' } }
      elseif ($n -like 'input.map.*') { if ($f.FullName -ne $maps[0].FullName) { $why = 'input.map backup beyond the newest' } }
      elseif ($n -match '\.(pre|driver)-' -or $n -match '\.bak(-|$)') { $why = 'pre-/driver-/bak backup' }
      elseif ($n -match '^(mciproxy|ipxwrapper)\.log$|^histogram\.txt$') { $why = 'log (rotates; recreated by the next run)' }
      elseif ($n -match $staleBat -and ($IncludeRcLaunchers -or $k.Role -like 'dev-*' -or $k.Role -like 'test-*')) { $why = 'stale launcher variant' }
      elseif ($f.DirectoryName -match '\\presets$' -and $n -match '(?i)scratch|tmp|test-|\.old') { $why = 'scratch preset' }
      elseif ($f.DirectoryName -match '\\_superseded[^\\]*') { $why = '_superseded (older than the current build)' }
      if ($why) { [void]$hit.Add([pscustomobject]@{ F=$f; Why=$why }) }
    }
    $sum = ($hit | ForEach-Object { $_.F.Length } | Measure-Object -Sum).Sum
    Write-Host ("`n[{0}] {1}: {2} cruft files, {3:N1} MB" -f $k.Role, $dir, $hit.Count, ($sum/1MB))
    foreach ($h in $hit) { Write-Host ("   {0,8:N0} KB  {1}   ({2})" -f ($h.F.Length/1KB), $h.F.FullName.Substring($dir.Length+1), $h.Why) }
    $grand += [int64]$sum
    if ($Execute) {
      foreach ($h in $hit) {
        $rel = $h.F.FullName.Substring($dir.Length+1); $to = Join-Path $CruftRoot "$($k.Role)\$rel"
        New-Item -ItemType Directory -Force (Split-Path $to) | Out-Null; Move-Item $h.F.FullName $to -Force
      }
    }
  }
  Write-Host ("`nCruft total {0:N1} MB ({1})" -f ($grand/1MB), $mode)
}
Write-Host "== done ($mode). Nothing changed unless -Execute was given."

