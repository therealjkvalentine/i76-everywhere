<#
  projectile-test.ps1 — do projectiles behave the same at 20 Hz and 60 Hz?

  Mortar/rocket "range collapse" at high FPS is one of the classic reports. Rockets are the
  same projectile class and are already equipped on the mission-6 save car (#2 Top = FireRite
  Rkt, fired with the '2' key per input.map hardpoint2_fire).

  A fired projectile appears as a NEW entity in the world position table, so this watches the
  table for slots that appear, tracks them frame to frame, and reports each projectile's speed
  and how far it travelled before vanishing. Range and speed are the numbers that must match
  across frame rates.
#>
param([int]$Shots = 6, [string]$Label = 'proj', [int]$SampleMs = 40,
      [string]$OutDir = "$PSScriptRoot\..\..\captures\traces")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"
New-Item -ItemType Directory -Force $OutDir | Out-Null

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }

# Baseline: which slots are occupied before firing. Anything new is a projectile.
$baseline = @{}
foreach ($e in Mem-Entities $ctx) { $baseline[$e.Index] = $true }
$p0 = Mem-Player $ctx
$f0 = $p0.Frame
Write-Host ("baseline entities: {0}" -f $baseline.Count)

$tracks = @{}          # index -> list of samples
$inv = [Globalization.CultureInfo]::InvariantCulture
$sw = [Diagnostics.Stopwatch]::StartNew()
$nextShot = 0.0
$shotsFired = 0
while ($sw.Elapsed.TotalSeconds -lt ($Shots * 1.5 + 3)) {
    if ($shotsFired -lt $Shots -and $sw.Elapsed.TotalSeconds -ge $nextShot) {
        Send-Key ([byte]0x32) 60      # '2' = hardpoint2_fire (FireRite Rkt)
        $shotsFired++; $nextShot += 1.5
    }
    foreach ($e in Mem-Entities $ctx) {
        if (-not $baseline.ContainsKey($e.Index)) {
            if (-not $tracks.ContainsKey($e.Index)) { $tracks[$e.Index] = @() }
            $tracks[$e.Index] += [pscustomobject]@{ T = $sw.Elapsed.TotalMilliseconds; X = $e.X; Y = $e.Y; Z = $e.Z }
        }
    }
    Start-Sleep -Milliseconds $SampleMs
}
$p1 = Mem-Player $ctx
$fps = ($p1.Frame - $f0) / $sw.Elapsed.TotalSeconds
Mem-Close $ctx

Write-Host ("{0}: {1:N1} fps, {2} shots, {3} projectile tracks" -f $Label, $fps, $shotsFired, $tracks.Count) -ForegroundColor Cyan
$rows = @('track,samples,life_ms,dist_m,speed_mps')
foreach ($k in ($tracks.Keys | Sort-Object)) {
    $t = $tracks[$k]
    if ($t.Count -lt 2) { continue }
    $life = $t[-1].T - $t[0].T
    $d = [math]::Sqrt([math]::Pow($t[-1].X - $t[0].X,2) + [math]::Pow($t[-1].Y - $t[0].Y,2) + [math]::Pow($t[-1].Z - $t[0].Z,2))
    $spd = if ($life -gt 0) { $d / ($life/1000.0) } else { 0 }
    Write-Host ("  slot {0}: {1} samples, {2:N0} ms alive, {3:N1} m travelled, {4:N1} m/s" -f $k, $t.Count, $life, $d, $spd)
    $rows += ("{0},{1},{2},{3},{4}" -f $k, $t.Count, [int]$life, $d.ToString('R',$inv), $spd.ToString('R',$inv))
}
$rows | Set-Content (Join-Path $OutDir "$Label.csv")
