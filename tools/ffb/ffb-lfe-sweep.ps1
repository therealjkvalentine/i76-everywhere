<#
  ffb-lfe-sweep.ps1 - measure the response of the WHOLE RIG, by ear and body.

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
  what you feel is the system, not the signal. Rate each step 0-10, where 0 is
  nothing at all and 10 is the strongest step in the run. Use the whole scale -
  relative values are all that matter, absolute ones do not.

  Play the WAV through the shaker channel at your NORMAL driving volume, and do
  not touch the volume control once it starts.

  RUN IT:
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-sweep.ps1
  then play the WAV, write down 0-10 per step, and paste the numbers back.
#>
param(
    [string]$Out = "lfe-sweep.wav",
    [double[]]$Freqs = @(8,10,12,13,15,18,20,22,25,28,31,35,40,45,50,55,60,70,80,90,100),
    [double]$StepSeconds = 3.0,
    [double]$GapSeconds  = 1.0,
    [int]$Rate = 8000,
    [double]$Amp = 0.55
)
$ErrorActionPreference = 'Stop'

# Equal amplitude everywhere. A raised-cosine fade on each step keeps the switch
# from clicking - a click is broadband, and a broadband transient is exactly what
# would let you "feel" a step whose own frequency you cannot feel at all.
$fadeS = 0.25
$total = [int](($StepSeconds + $GapSeconds) * $Freqs.Count * $Rate)
$pcm = New-Object int16[] $total   # 'short' is a C# alias, not a PowerShell one
$i = 0
$schedule = New-Object System.Collections.Generic.List[object]

foreach ($f in $Freqs) {
    $start = $i / $Rate
    $nStep = [int]($StepSeconds * $Rate)
    $nFade = [int]($fadeS * $Rate)
    for ($k = 0; $k -lt $nStep; $k++) {
        $env = 1.0
        if ($k -lt $nFade) { $env = 0.5 - 0.5 * [math]::Cos([math]::PI * $k / $nFade) }
        elseif ($k -gt $nStep - $nFade) { $env = 0.5 - 0.5 * [math]::Cos([math]::PI * ($nStep - $k) / $nFade) }
        $v = $Amp * $env * [math]::Sin(2 * [math]::PI * $f * $k / $Rate)
        $pcm[$i] = [int16]([math]::Max(-1.0, [math]::Min(1.0, $v)) * 32767); $i++
    }
    $i += [int]($GapSeconds * $Rate)   # silence: array is already zeroed
    $schedule.Add([pscustomobject]@{ Hz = $f; StartS = [math]::Round($start,1) })
}

# Resolve relative to the caller's directory, but leave an absolute path alone.
# Join-Path would mangle one, and Get-Location returns a PathInfo, not a string.
$outPath = if ([System.IO.Path]::IsPathRooted($Out)) { $Out }
           else { Join-Path (Get-Location).Path $Out }
$fs = [System.IO.File]::Create($outPath)
$bw = New-Object System.IO.BinaryWriter($fs)
$bytes = $i * 2
$bw.Write([char[]]'RIFF'); $bw.Write([uint32](36 + $bytes)); $bw.Write([char[]]'WAVE')
$bw.Write([char[]]'fmt '); $bw.Write([uint32]16); $bw.Write([uint16]1); $bw.Write([uint16]1)
$bw.Write([uint32]$Rate); $bw.Write([uint32]($Rate*2)); $bw.Write([uint16]2); $bw.Write([uint16]16)
$bw.Write([char[]]'data'); $bw.Write([uint32]$bytes)
for ($k = 0; $k -lt $i; $k++) { $bw.Write($pcm[$k]) }
$bw.Close(); $fs.Close()

Write-Host ""
Write-Host ("wrote {0}  -  {1} steps, {2:0.0}s total, all at identical amplitude" -f `
    $outPath, $Freqs.Count, ($i / $Rate)) -ForegroundColor Green
Write-Host ""
Write-Host "Play it through the SHAKER at your normal driving volume." -ForegroundColor Cyan
Write-Host "Do not adjust the volume once it starts - that would rewrite the curve." -ForegroundColor Cyan
Write-Host "Rate each step 0-10. 10 = the strongest step in the run, 0 = felt nothing." -ForegroundColor Cyan
Write-Host ""
Write-Host ("  {0,6}  {1,8}   your rating" -f 'Hz','starts at')
Write-Host ("  " + ("-" * 40))
foreach ($s in $schedule) {
    Write-Host ("  {0,6:0.#}  {1,7:0.0}s   ____" -f $s.Hz, $s.StartS)
}
Write-Host ""
Write-Host "Paste the ratings back and they become LfeRespHz/LfeRespRel in" -ForegroundColor Cyan
Write-Host "Mix-DefaultTune, which the synth inverts to flatten the rig." -ForegroundColor Cyan
Write-Host ""
Write-Host "Steps you feel NOTHING at are as valuable as strong ones - they set" -ForegroundColor DarkGray
Write-Host "where content should never be placed. Rate them 0, do not skip them." -ForegroundColor DarkGray
