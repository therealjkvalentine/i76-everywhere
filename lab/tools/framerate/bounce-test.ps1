<#
  bounce-test.ps1 — record the chassis vertical bob for the "car bounces too fast" bug.

  Anchored on the player entity (via the eye transform's vertical position and pitch), so unlike
  the sky it does NOT drift on a mission reset — the same stable chain that yields orientation.

  Captures two phases into one CSV:
    idle   — car parked, the suspension's own settling jitter (pure natural response, no forcing)
    drive  — hold throttle over the dunes, the bob under terrain forcing
  Compare across frame rates with analyse-bounce.py: if the bob OSCILLATION FREQUENCY scales
  with the frame rate, the spring/damper is integrated per-frame (frame-coupled); if it holds
  steady in Hz, it is dt-correct and the "too fast" impression is something else.

    tools\framerate\bounce-test.ps1 -Label bounce60
#>
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [double]$IdleSeconds = 4,
    [double]$DriveSeconds = 8,
    [string]$OutDir
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot '..\..\captures\bounce' }

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$out = Join-Path $OutDir "$Label.csv"
if (Test-Path $out) { Remove-Item $out -Force }

$VK_W = [byte]0x57
$ent = Mem-PlayerEntity $ctx
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
$rows = New-Object System.Collections.Generic.List[object]

function Sample($phase, $secs, $drive) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $secs) {
        if ($drive) { Key-Down $VK_W }
        $a = Mem-EyeAngles $ctx
        $s = Mem-Floats $ctx ($ent + 0xAC) 8    # speed .. vy
        if ($a -and $s) {
            $rows.Add([pscustomobject]@{
                phase = $phase
                t     = [math]::Round($sw.Elapsed.TotalSeconds, 4)
                frame = Mem-I32 $ctx 0x5A7E1C
                py    = [math]::Round($a.PY, 5)
                pitch = [math]::Round($a.Pitch, 5)
                roll  = [math]::Round($a.Roll, 5)
                speed = [math]::Round($s[0], 3)
                vy    = [math]::Round($s[5], 4)
            })
        }
        Start-Sleep -Milliseconds 6
    }
}

Sample 'idle'  $IdleSeconds  $false
Sample 'drive' $DriveSeconds $true
Key-Up $VK_W

$fps = ($rows[$rows.Count-1].frame - $rows[0].frame) / ($rows[$rows.Count-1].t + $IdleSeconds)
$rows | Export-Csv -NoTypeInformation $out
Mem-Close $ctx
Write-Host ("{0}: {1} samples, idle+drive -> {2}" -f $Label, $rows.Count, $out) -ForegroundColor Green
