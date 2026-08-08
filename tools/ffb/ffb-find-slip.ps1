<#
  ffb-find-slip.ps1 - find the engine's TRACTION-LOSS state by watching it change.

  WHY THIS EXISTS: the force model detects loss of control by comparing the yaw
  rate against what the steering commanded - and measured on real drives, that
  deviation only crosses its deadband during genuine spins, handbrake turns and
  impacts. Ordinary sliding does NOT deviate: the car slides visually while its
  yaw rate stays exactly what the steering asked for, which is what "no tyre
  model" means in practice (docs/HANDLING-MODEL.md).

  But the game clearly knows more than that. It plays skid sounds (skid1..skid4
  are in the exe) and it draws skid marks - the renderer even has a 'Skid ' timing
  bucket alongside 'Road ' and 'Terr '. Something decides, per frame, that a tyre
  is scrubbing. If we can read that, the wheel can communicate the approach to the
  limit instead of only the departure from it - which is the whole difference
  between a warning and a report.

  Neither the sound names nor the 'Skid' string are referenced from code in a way
  that leads anywhere (the sound names have no direct .text xrefs; 'Skid ' is a
  profiler label), so this takes the behavioural route that has worked three times
  in this project already: drive the car into the state, and see what moves.

  ---------------------------------------------------------------------------
  HOW TO RUN IT
  ---------------------------------------------------------------------------
      tools\ffb\ffb-find-slip.ps1

    * PHASE 1 (baseline, 12 s) - drive NORMALLY. Straight lines and gentle turns.
      No handbrake, no skidding, no collisions.
    * PHASE 2 (sliding, 15 s)  - SLIDE as continuously as you can. Handbrake
      turns, hard cornering, anything that makes the skid sound play. Try not to
      hit anything, since impacts move plenty of fields on their own.

  The trick is that both phases are DRIVING, so everything that merely tracks
  speed or steering moves in both and cancels out. What is left is what changes
  specifically when the tyres let go.

  Read-only. Nothing is written to the game.
#>
param(
    [int]$BaselineSeconds = 12,
    [int]$SlideSeconds = 15,
    [int]$Range = 0x240,
    [int]$HZ = 30
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')

$ctx = Tel-Open
Write-Host ("telemetry OK - entity 0x{0:X8}" -f $ctx.Ent) -ForegroundColor Green

function Capture {
    param([string]$Label, [int]$Seconds, [string]$Instruction)
    Write-Host ""
    Write-Host "--- $Label ---" -ForegroundColor Yellow
    Write-Host "  $Instruction" -ForegroundColor Yellow
    Write-Host "  Press Enter when you are ready to start." -ForegroundColor Yellow
    [void](Read-Host)
    $buf = New-Object byte[] $Range
    $n = 0
    $stats = @{}
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $last = -1
    $frames = 0
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        if ([I76Tel]::ReadProcessMemory($ctx.H, [IntPtr]$ctx.Ent, $buf, $Range, [ref]$n)) {
            for ($o = 0; $o -lt $Range; $o += 4) {
                $v = [BitConverter]::ToSingle($buf, $o)
                if ([double]::IsNaN($v) -or [double]::IsInfinity($v)) { continue }
                if (-not $stats.ContainsKey($o)) { $stats[$o] = [pscustomobject]@{ Min=$v; Max=$v; Sum=0.0; AbsSum=0.0; N=0 } }
                $st = $stats[$o]
                if ($v -lt $st.Min) { $st.Min = $v }
                if ($v -gt $st.Max) { $st.Max = $v }
                $st.Sum += $v; $st.AbsSum += [math]::Abs($v); $st.N++
            }
            $frames++
        }
        $el = [int]$sw.Elapsed.TotalSeconds
        if ($el -ne $last) { $last = $el; Write-Host ("`r    {0,3}s left  " -f ($Seconds - $el)) -NoNewline }
        Start-Sleep -Milliseconds ([int](1000 / $HZ))
    }
    Write-Host ""
    Write-Host ("    {0} frames" -f $frames) -ForegroundColor DarkGray
    return $stats
}

$base = Capture "PHASE 1: BASELINE" $BaselineSeconds `
    "Drive NORMALLY. Straight lines and gentle turns. No handbrake, no sliding."
$slide = Capture "PHASE 2: SLIDING" $SlideSeconds `
    "SLIDE as much as you can - handbrake turns, hard cornering. Make it skid."

# ---- compare -------------------------------------------------------------
# Two scores, because the interesting field could look like either:
#   RANGE  - it reaches values while sliding that it never reaches otherwise
#            (a slip magnitude, a scrub amount)
#   ACTIVE - its mean absolute value jumps (a flag, a per-wheel counter)
$rows = @()
foreach ($o in ($base.Keys | Sort-Object)) {
    if (-not $slide.ContainsKey($o)) { continue }
    $b = $base[$o]; $s = $slide[$o]
    if ($b.N -lt 10 -or $s.N -lt 10) { continue }
    $bAvg = $b.AbsSum / $b.N; $sAvg = $s.AbsSum / $s.N
    $bSpan = $b.Max - $b.Min;  $sSpan = $s.Max - $s.Min
    # ignore fields that are constant in BOTH phases - geometry, not state
    if ($bSpan -lt 1e-6 -and $sSpan -lt 1e-6) { continue }
    $actRatio = if ($bAvg -gt 1e-6) { $sAvg / $bAvg } elseif ($sAvg -gt 1e-4) { 999.0 } else { 0.0 }
    $spanRatio = if ($bSpan -gt 1e-6) { $sSpan / $bSpan } elseif ($sSpan -gt 1e-4) { 999.0 } else { 0.0 }
    $rows += [pscustomobject]@{
        Offset = ("+0x{0:X3}" -f $o)
        BaseAvg = [math]::Round($bAvg,4); SlideAvg = [math]::Round($sAvg,4)
        ActRatio = [math]::Round($actRatio,2)
        BaseSpan = [math]::Round($bSpan,4); SlideSpan = [math]::Round($sSpan,4)
        SpanRatio = [math]::Round($spanRatio,2)
        Score = [math]::Round([math]::Max($actRatio, $spanRatio),2)
    }
}

Write-Host ""
Write-Host "=== fields that behave DIFFERENTLY while sliding ===" -ForegroundColor Green
Write-Host "  (ranked by how much more active they are; known fields annotated)" -ForegroundColor DarkGray
Write-Host ""
$known = @{ 0xAC='speed'; 0xBC='vel x'; 0xC0='vel y'; 0xC4='vel z'; 0xC8='angvel x';
            0xCC='YAW RATE'; 0xD0='angvel z'; 0xD4='accel x'; 0xD8='accel y'; 0xDC='accel z';
            0xE0='steer'; 0xE4='throttle' }
$top = @($rows | Where-Object { $_.Score -gt 1.6 } | Sort-Object { -$_.Score } | Select-Object -First 22)
if (-not $top.Count) {
    Write-Host "  NOTHING stood out. Either the slide was too gentle, or the state is" -ForegroundColor Yellow
    Write-Host "  outside this struct - try -Range 0x400, or it may live per-wheel in a" -ForegroundColor Yellow
    Write-Host "  separate allocation reached by a pointer." -ForegroundColor Yellow
} else {
    Write-Host ("  {0,-8} {1,10} {2,10} {3,7}   {4}" -f "offset","base avg","slide avg","ratio","note")
    foreach ($r in $top) {
        $o = [Convert]::ToInt32($r.Offset.Substring(3),16)
        $note = if ($known.ContainsKey($o)) { "known: " + $known[$o] } else { "" }
        Write-Host ("  {0,-8} {1,10:0.####} {2,10:0.####} {3,7:0.0}x   {4}" -f `
            $r.Offset, $r.BaseAvg, $r.SlideAvg, $r.Score, $note)
    }
    Write-Host ""
    Write-Host "READING THIS: ignore the annotated rows - speed, yaw and steer all move" -ForegroundColor Gray
    Write-Host "more when you slide, which proves the capture worked but tells us nothing" -ForegroundColor Gray
    Write-Host "new. An UNANNOTATED offset with a high ratio is the candidate: something" -ForegroundColor Gray
    Write-Host "that is quiet during normal driving and alive while the tyres scrub." -ForegroundColor Gray
    Write-Host "A field that sits at 0 or 1 is a per-wheel skid FLAG; one that ranges" -ForegroundColor Gray
    Write-Host "smoothly is a slip magnitude, which is far more useful." -ForegroundColor Gray
}

$out = Join-Path $here 'ffb-slip-candidates.csv'
$rows | Sort-Object { -$_.Score } | Export-Csv -NoTypeInformation -Path $out
Write-Host ""
Write-Host "full table -> $out" -ForegroundColor Cyan
Tel-Close $ctx
