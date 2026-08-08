<#
  ffb-lfe-sweep.ps1 - measure the response of the WHOLE RIG, by body, and write
  the answer straight into a form the mixer can use.

  It PLAYS each step and asks you to rate it. No file to find, no output device
  to guess at, no table to transcribe.

  WHAT THIS MEASURES, AND WHY IT IS NOT THE DRIVER SPEC: an Aura AST-2B-4 is
  rated 20-80 Hz with resonance at 40. What you actually feel is that driver
  bolted to a desk, through a chair, into a body - and that system has its own
  peaks and nulls. On this rig 13 Hz is perceptible (below the driver's rated
  floor) and the peak sits nearer 35 than 40. The rig curve is the one that
  matters, and only measurement finds it.

  WHY PERCEIVED INTENSITY IS THE RIGHT TARGET: an accelerometer would give
  acceleration, but the goal is equal FELT intensity per unit of game event.
  Human vibrotactile sensitivity varies strongly across 10-100 Hz (this is what
  the ISO 2631 frequency weightings exist to express), so a rig made flat in
  acceleration still feels badly tilted. Rating it by body folds the rig and the
  body into one curve, which is exactly the curve the compensation needs.

  METHOD: every step is synthesised at the SAME amplitude. So any difference in
  what you feel is the system, not the signal. Rate each 0-10, where 10 is the
  strongest step in the run and 0 is nothing at all. Only the ratios matter.

  WHY winmm AND NOT System.Media.SoundPlayer: SoundPlayer can only reach the
  DEFAULT output device. Shakers are almost never the default - they hang off a
  second card or a spare output - so the one thing this script must be able to
  do is choose where the sound goes. waveOut takes a device index. This is also
  the interop the rest of the repo already uses (see ffb-buttons.ps1).

  RUN IT:
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-sweep.ps1 -List
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-sweep.ps1 -Device 2
#>
param(
    [switch]$List,
    [int]$Device = -1,          # -1 = WAVE_MAPPER, the system default
    [double[]]$Freqs = @(8,10,12,13,15,18,20,22,25,28,31,35,40,45,50,55,60,70,80,90,100),
    [double]$StepSeconds = 2.5,
    [int]$Rate = 8000,
    [double]$Amp = 0.55,
    [switch]$NoPrompt,          # play straight through without asking for ratings
    [string]$Out                # optionally also save the whole sweep as a WAV
)
$ErrorActionPreference = 'Stop'

# Audio device interop is shared - see LfeSynth.ps1.
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'LfeSynth.ps1')

# ---- device list ---------------------------------------------------------
$devs = [LfeOut]::Devices()
if ($List -or $devs.Count -eq 0) {
    Write-Host ""
    Write-Host "output devices (pass the number as -Device):" -ForegroundColor Cyan
    Write-Host ("  {0,3}  {1}" -f '-1', 'system default (WAVE_MAPPER)')
    for ($i = 0; $i -lt $devs.Count; $i++) { Write-Host ("  {0,3}  {1}" -f $i, $devs[$i]) }
    Write-Host ""
    Write-Host "Pick the one your SHAKERS are on, not your speakers." -ForegroundColor Yellow
    if ($List) { exit 0 }
}
$devName = if ($Device -lt 0 -or $Device -ge $devs.Count) { 'system default' } else { $devs[$Device] }

# ---- synth ---------------------------------------------------------------
# A raised-cosine fade on each step keeps the switch from clicking - a click is
# broadband, and a broadband transient is exactly what would let you "feel" a
# step whose own frequency you cannot feel at all.
function Step-Pcm {
    param([double]$Hz)
    $n = [int]($StepSeconds * $Rate)
    $nFade = [int](0.25 * $Rate)
    $b = New-Object byte[] ($n * 2)
    for ($k = 0; $k -lt $n; $k++) {
        $env = 1.0
        if ($k -lt $nFade) { $env = 0.5 - 0.5 * [math]::Cos([math]::PI * $k / $nFade) }
        elseif ($k -gt $n - $nFade) { $env = 0.5 - 0.5 * [math]::Cos([math]::PI * ($n - $k) / $nFade) }
        $v = $Amp * $env * [math]::Sin(2 * [math]::PI * $Hz * $k / $Rate)
        if ($v -gt 1.0) { $v = 1.0 } elseif ($v -lt -1.0) { $v = -1.0 }
        $s = [int16]($v * 32767)
        [BitConverter]::GetBytes($s).CopyTo($b, $k * 2)
    }
    return $b
}

Write-Host ""
Write-Host ("SWEEP: {0} steps, {1:0.0}s each, ALL AT THE SAME AMPLITUDE." -f $Freqs.Count, $StepSeconds) -ForegroundColor Green
Write-Host ("output: {0}" -f $devName) -ForegroundColor Green
Write-Host ""
Write-Host "Set the shaker to your normal driving volume NOW, and do not touch it" -ForegroundColor Yellow
Write-Host "again until the sweep ends - a mid-run change rewrites the curve." -ForegroundColor Yellow
if (-not $NoPrompt) {
    Write-Host ""
    Write-Host "After each step, type 0-10 and press Enter." -ForegroundColor Cyan
    Write-Host "  10 = the strongest step in the whole run, 0 = felt nothing at all." -ForegroundColor Cyan
    Write-Host "  Steps you feel NOTHING at are as valuable as strong ones - they set" -ForegroundColor DarkGray
    Write-Host "  where content must never be placed. Rate them 0, do not skip them." -ForegroundColor DarkGray
    Write-Host "  'r' replays the step. Enter alone repeats your previous rating." -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "Press Enter to begin." -ForegroundColor Yellow
[void](Read-Host)

$ratings = New-Object System.Collections.Generic.List[object]
$prev = $null
$all = New-Object System.Collections.Generic.List[byte]

for ($i = 0; $i -lt $Freqs.Count; $i++) {
    $hz = $Freqs[$i]
    $pcm = Step-Pcm $hz
    if ($Out) { $all.AddRange($pcm); $all.AddRange((New-Object byte[] ($Rate))) }

    while ($true) {
        Write-Host ("  [{0,2}/{1}]  {2,5:0.#} Hz  ... playing" -f ($i+1), $Freqs.Count, $hz) -NoNewline
        $err = [LfeOut]::Play($pcm, $Rate, $Device)
        if ($err) {
            Write-Host ""
            Write-Host "PLAYBACK FAILED: $err" -ForegroundColor Red
            Write-Host "Run with -List and pick a device that exists." -ForegroundColor Red
            exit 1
        }
        if ($NoPrompt) { Write-Host ""; break }
        Write-Host "   rate 0-10: " -NoNewline
        $ans = Read-Host
        if ($ans -eq 'r') { continue }
        if ([string]::IsNullOrWhiteSpace($ans)) {
            if ($null -eq $prev) { Write-Host "    (no previous rating - please type a number)" -ForegroundColor DarkGray; continue }
            $ans = $prev
        }
        $val = 0.0
        if (-not [double]::TryParse($ans, [ref]$val)) { Write-Host "    (not a number)" -ForegroundColor DarkGray; continue }
        if ($val -lt 0) { $val = 0 } elseif ($val -gt 10) { $val = 10 }
        $prev = $val
        $ratings.Add([pscustomobject]@{ Hz = $hz; R = $val })
        break
    }
}

if ($Out) {
    $outPath = if ([System.IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path (Get-Location).Path $Out }
    $fs = [System.IO.File]::Create($outPath); $bw = New-Object System.IO.BinaryWriter($fs)
    $bytes = $all.Count
    $bw.Write([char[]]'RIFF'); $bw.Write([uint32](36 + $bytes)); $bw.Write([char[]]'WAVE')
    $bw.Write([char[]]'fmt '); $bw.Write([uint32]16); $bw.Write([uint16]1); $bw.Write([uint16]1)
    $bw.Write([uint32]$Rate); $bw.Write([uint32]($Rate*2)); $bw.Write([uint16]2); $bw.Write([uint16]16)
    $bw.Write([char[]]'data'); $bw.Write([uint32]$bytes)
    $bw.Write($all.ToArray()); $bw.Close(); $fs.Close()
    Write-Host ("saved sweep to {0}" -f $outPath) -ForegroundColor DarkGray
}

if ($NoPrompt -or $ratings.Count -lt 2) {
    Write-Host ""; Write-Host "done." -ForegroundColor Green; exit 0
}

# ---- result --------------------------------------------------------------
# Normalise to the strongest step. Only ratios matter: the compensation inverts
# this curve, and an inverse is unchanged by an overall scale factor.
$peak = ($ratings | Measure-Object -Property R -Maximum).Maximum
if ($peak -le 0) {
    Write-Host ""
    Write-Host "Every step rated 0 - nothing reached the shaker. Check -Device and volume." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== measured rig response ===" -ForegroundColor Cyan
Write-Host ""
foreach ($r in $ratings) {
    $rel = $r.R / $peak
    $bar = '#' * [int]([math]::Round($rel * 40))
    $comp = if ($rel -lt 0.001) { 'dead' } else { ("x{0:0.0}" -f [math]::Min(3.2, 1.0 / $rel)) }
    Write-Host ("  {0,5:0.#} Hz  {1,-40}  {2,5:0.00}  comp {3}" -f $r.Hz, $bar, $rel, $comp)
}

$hzList  = ($ratings | ForEach-Object { ("{0:0.0}" -f $_.Hz) }) -join ', '
$relList = ($ratings | ForEach-Object { ("{0:0.00}" -f ($_.R / $peak)) }) -join ', '

Write-Host ""
Write-Host "Paste these two lines into Mix-DefaultTune in FfbMixer.ps1:" -ForegroundColor Cyan
Write-Host ""
Write-Host ("        LfeRespHz  = @({0})" -f $hzList) -ForegroundColor Green
Write-Host ("        LfeRespRel = @({0})" -f $relList) -ForegroundColor Green
Write-Host ""
Write-Host "The synth inverts that curve per source, so every band arrives at the" -ForegroundColor DarkGray
Write-Host "same felt strength. Steps rated 0 get no boost - they are unreachable," -ForegroundColor DarkGray
Write-Host "and pushing them would only burn headroom and heat the coil." -ForegroundColor DarkGray
