<#
  apply-conf.ps1 - install one of the conf-*.conf graphics test variants into the SANDBOX game folder, or put the
  live conf back.

    .\apply-conf.ps1 -List                 # the variants and what each changes
    .\apply-conf.ps1 -Variant 2x           # back up game\dgVoodoo.conf (once), install conf-2x.conf
    .\apply-conf.ps1 -Variant 2x-msaa8     # switch variant; the ORIGINAL backup is kept, not overwritten
    .\apply-conf.ps1 -Status               # which variant is installed, and the keys that differ from the backup
    .\apply-conf.ps1 -Restore              # put the backup back and remove it

  Refuses while an i76 / nitro process runs (dgVoodoo reads the conf at start; swapping it under a live game only
  confuses the next measurement) and refuses any folder that is not the lab sandbox unless -Force is given: the
  portable install is the daily driver (i76-everywhere AGENTS.md). Every copy is read back and hash-checked.
#>
param(
    [string]$Variant,
    [switch]$Restore,
    [switch]$Status,
    [switch]$List,
    [string]$GameDir = (Join-Path $PSScriptRoot "..\..\game"),
    [switch]$Force
)
$ErrorActionPreference = "Stop"

function Get-Keys([string]$Path) {
    # section-qualified key = value pairs, comments and blanks dropped
    $sec = ""; $h = [ordered]@{}
    foreach ($l in [IO.File]::ReadAllLines($Path)) {
        $t = $l.Trim()
        if ($t -eq "" -or $t.StartsWith(";")) { continue }
        if ($t -match '^\[(.+?)\]') { $sec = $Matches[1]; continue }
        if ($t -match '^([^=]+?)\s*=\s*(.*)$') { $h["[$sec] $($Matches[1].Trim())"] = $Matches[2].Trim() }
    }
    return $h
}
function Show-Diff([string]$Base, [string]$Other) {
    $a = Get-Keys $Base; $b = Get-Keys $Other; $n = 0
    foreach ($k in $b.Keys) { if ($a[$k] -ne $b[$k]) { "    {0} = {1}   (backup: {2})" -f $k, $b[$k], $a[$k]; $n++ } }
    foreach ($k in $a.Keys) { if (-not $b.Contains($k)) { "    {0} missing   (backup: {1})" -f $k, $a[$k]; $n++ } }
    if ($n -eq 0) { "    (no key differs)" }
}
function Hash([string]$p) { (Get-FileHash $p -Algorithm SHA256).Hash }

if ($List) {
    Get-ChildItem $PSScriptRoot -Filter "conf-*.conf" | Sort-Object Name | ForEach-Object {
        $name = $_.BaseName.Substring(5)
        $why = (Get-Content $_.FullName -TotalCount 2)[1].TrimStart("; ")
        "{0,-20} {1}" -f $name, $why
    }
    exit 0
}

$G = (Resolve-Path $GameDir).Path
$Live = Join-Path $G "dgVoodoo.conf"
$Bak = Join-Path $G "dgVoodoo.conf.pre-graphics"
$Mark = Join-Path $G "dgVoodoo.conf.graphics-variant"   # name of the installed variant

if ($Status) {
    if (-not (Test-Path $Bak)) { "no graphics variant installed (no $Bak); the live conf is in place"; exit 0 }
    $v = if (Test-Path $Mark) { (Get-Content $Mark -Raw).Trim() } else { "unknown" }
    "installed variant: $v   (backup of the live conf: $Bak)"
    Show-Diff $Bak $Live
    exit 0
}

if (-not $Force -and $G -notmatch '\\i76-uncap-lab\\game$') {
    Write-Host "refusing: $G is not the lab sandbox (i76-uncap-lab\game). The portable install is never a test target; -Force overrides." -ForegroundColor Red
    exit 1
}
$running = Get-Process | Where-Object { $_.ProcessName -like "i76*" -or $_.ProcessName -like "nitro*" }
if ($running) {
    Write-Host "refusing: a game process is running ($(($running | ForEach-Object { "$($_.ProcessName) pid $($_.Id)" }) -join ', ')). Close it first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Live)) { Write-Host "no dgVoodoo.conf in $G" -ForegroundColor Red; exit 1 }

if ($Restore) {
    if (-not (Test-Path $Bak)) { Write-Host "nothing to restore: $Bak does not exist (the live conf is already in place)" -ForegroundColor Yellow; exit 0 }
    Copy-Item $Bak $Live -Force
    if ((Hash $Live) -ne (Hash $Bak)) { Write-Host "RESTORE FAILED: $Live does not match $Bak after the copy; the backup is kept" -ForegroundColor Red; exit 1 }
    Remove-Item $Bak; Remove-Item $Mark -ErrorAction SilentlyContinue
    Write-Host "restored the live conf (verified), backup removed" -ForegroundColor Green
    exit 0
}

if (-not $Variant) { Write-Host "give -Variant <name>, -Restore, -Status or -List" -ForegroundColor Red; exit 1 }
$name = $Variant -replace '^conf-', '' -replace '\.conf$', ''
$Src = Join-Path $PSScriptRoot "conf-$name.conf"
if (-not (Test-Path $Src)) { Write-Host "no such variant: $Src   (see -List)" -ForegroundColor Red; exit 1 }

# A variant generated from an older live conf would silently roll back unrelated settings: every key the variant
# changes is named in its header, so any OTHER difference from the backup means the variants are stale.
$declared = @(Get-Content $Src -TotalCount 12 | Where-Object { $_ -match '^;\s+(\[[^\]]+\]\s+\S+)\s*=' } | ForEach-Object { $Matches[1] -replace '\s+', ' ' })
$base = if (Test-Path $Bak) { $Bak } else { $Live }
$a = Get-Keys $base; $b = Get-Keys $Src
$stale = @($b.Keys | Where-Object { $a[$_] -ne $b[$_] -and $declared -notcontains $_ }) + @($a.Keys | Where-Object { -not $b.Contains($_) })
if ($stale.Count -gt 0) {
    Write-Host "refusing: conf-$name.conf differs from the live conf in keys it does not declare: $($stale -join ', ')" -ForegroundColor Red
    Write-Host "the live conf changed since the variants were generated - run: python $PSScriptRoot\make-variants.py" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Bak)) {
    Copy-Item $Live $Bak
    if ((Hash $Live) -ne (Hash $Bak)) { Write-Host "backup failed verification; nothing installed" -ForegroundColor Red; exit 1 }
    Write-Host "backed up the live conf to $Bak"
} else {
    Write-Host "keeping the existing backup $Bak (a variant was already installed)"
}
Copy-Item $Src $Live -Force
if ((Hash $Live) -ne (Hash $Src)) { Write-Host "INSTALL FAILED verification; run -Restore" -ForegroundColor Red; exit 1 }
Set-Content $Mark $name -Encoding ascii
Write-Host "installed conf-$name.conf (verified). Keys that differ from the live conf:" -ForegroundColor Green
Show-Diff $Bak $Live
Write-Host "put the live conf back with: $PSCommandPath -Restore"
