<#
  Promote-To-Driver.ps1 - apply one recorded promotion to the daily driver AND the golden copy.

    tools\Promote-To-Driver.ps1 -What "<one line>" -Gate "<what was run, n, result>" -Files @{ "<relative dest>" = "<source file>"; ... } [-Plan]

  Rules (NEW-DAILY-DRIVER-RECIPE.md): the same files go into both folders; a replaced file is kept in
  _rollback\<id>\ in each; one row is appended to PROMOTIONS.md in the golden copy (and in the driver if it has
  one); refuses while an i76 process is running; every copy is read back by md5. -Plan writes nothing.
  Relative dest is from the portable root (the folder that holds "Interstate 76\").
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$What,
    [Parameter(Mandatory = $true)] [string]$Gate,
    [Parameter(Mandatory = $true)] [hashtable]$Files,
    [string]$Driver = 'C:\Users\james\Games\Interstate76-2026-10-03',
    [string]$Golden = 'C:\Users\james\Games\Interstate76-golden-2026-10-03',
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }
if (-not $Plan -and (Get-Process i76* -ErrorAction SilentlyContinue | Where-Object { $_.Path -and ($_.Path.StartsWith($Driver, 'OrdinalIgnoreCase') -or $_.Path.StartsWith($Golden, 'OrdinalIgnoreCase')) })) { Write-Host 'REFUSED: the game is running. Close it and run again.' -ForegroundColor Red; exit 1 }
foreach ($root in $Driver, $Golden) { if (-not (Test-Path (Join-Path $root 'Interstate 76\i76.exe'))) { Write-Host "REFUSED: $root is not a driver folder" -ForegroundColor Red; exit 1 } }
foreach ($src in $Files.Values) { if (-not (Test-Path -LiteralPath $src)) { Write-Host "REFUSED: missing source $src" -ForegroundColor Red; exit 1 } }

$prom = Join-Path $Golden 'PROMOTIONS.md'
$rows = @(Get-Content $prom | Where-Object { $_ -match '^\|\s*\d+\s*\|' })
$id = if ($rows.Count) { [int](($rows[-1] -split '\|')[1].Trim()) + 1 } else { 1 }
$detail = @()
foreach ($rel in ($Files.Keys | Sort-Object)) {
    $src = $Files[$rel]; $after = Md5 $src
    foreach ($root in $Driver, $Golden) {
        $dst = Join-Path $root $rel
        $before = if (Test-Path -LiteralPath $dst) { Md5 $dst } else { 'new' }
        if ($root -eq $Driver) { $detail += "$rel ($($before.Substring(0, [Math]::Min(8, $before.Length))) -> $($after.Substring(0, 8)))" }
        if ($Plan) { Write-Host "plan: $dst  $before -> $after"; continue }
        if ($before -eq $after) { continue }
        if ($before -ne 'new') {
            $rb = Join-Path $root "_rollback\$id\$rel"; New-Item -ItemType Directory -Force (Split-Path $rb) | Out-Null
            Copy-Item -LiteralPath $dst $rb -Force
        }
        New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
        Copy-Item -LiteralPath $src $dst -Force
        if ((Md5 $dst) -ne $after) { Write-Host "FAILED read-back: $dst" -ForegroundColor Red; exit 1 }
    }
}
$row = "| $id | $(Get-Date -Format 'yyyy-MM-dd HH:mm') | $What | $($detail -join '; ') | $Gate | _rollback\$id |"
if ($Plan) { Write-Host "plan row: $row"; Write-Host '-Plan: nothing written.'; exit 0 }
Add-Content -LiteralPath $prom -Value $row -Encoding utf8
$dp = Join-Path $Driver 'PROMOTIONS.md'
if (-not (Test-Path $dp)) { Copy-Item $prom $dp } else { Add-Content -LiteralPath $dp -Value $row -Encoding utf8 }
Write-Host "promotion $id applied to both folders." -ForegroundColor Green
