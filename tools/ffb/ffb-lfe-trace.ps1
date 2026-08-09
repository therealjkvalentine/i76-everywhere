<#
  ffb-lfe-trace.ps1 - inspect the signal chain stage by stage.

  This is a deterministic DSP chain, so it does not need to be played to anybody
  to be debugged. Every stage has an input and an output, and a stage that is
  behaving adds nothing its input did not already contain. This renders one
  source at a time, with its parameters HELD CONSTANT, and dumps the signal at
  each tap so the stage that introduces content can be named rather than guessed.

  Holding the parameters constant matters: a constant-amplitude, constant-
  frequency source is exactly a tone sweep step, and tone sweeps are known to be
  clean on this rig. So anything the chain adds to a constant source is a chain
  defect, and anything that only appears once parameters MOVE is a modulation
  defect. The two have completely different fixes and this separates them.

  Stages, in order:
    sum        all sources added, before any filtering
    post-HP    after the 2-pole high-pass
    post-LP    after the low-pass  (what Step returns normally)
    limited    after drive -> soft knee -> master
    quantised  after conversion to int16

      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-trace.ps1
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-trace.ps1 -Modulated
#>
param(
    [double]$Seconds = 4.0,
    [int]$Rate = 16000,
    [int]$FrameHz = 60,
    [double]$Drive = 1.0,
    [double]$Master = 0.9,
    [switch]$Modulated,      # let parameters move, to separate chain from modulation
    [string]$OutDir = ""
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'FfbMixer.ps1')
. (Join-Path $here 'LfeSynth.ps1')
if (-not $OutDir) { $OutDir = Join-Path $here 'trace' }
if (-not (Test-Path $OutDir)) { $null = New-Item -ItemType Directory -Path $OutDir }
$tune = Mix-DefaultTune

# Each source at a representative working amplitude, alone.
$SRC = @(
  # Amplitudes come from the tune, so the trace measures what actually ships.
  @{ N='engine'; Amp=@{e=[double]$tune.LfeEngineAmp};  Expect=@(30.0,60.0) }
  @{ N='road';   Amp=@{r=[double]$tune.LfeRoadAmp};    Expect=@(60.0) }
  @{ N='impact'; Amp=@{i=[double]$tune.LfeImpactAmp};  Expect=@([double]$tune.LfeImpactHz) }
  @{ N='weapon'; Amp=@{w=[double]$tune.LfeWeaponAmp};  Expect=@([double]$tune.LfeWeaponHz) }
  @{ N='heave';  Amp=@{h=[double]$tune.LfeHeaveAmp};   Expect=@([double]$tune.LfeCarrierHz) }
  @{ N='scrub';  Amp=@{s=[double]$tune.LfeScrubAmp};   Expect=@([double]$tune.LfeScrubHz) }
)
$TAPS = @(@{T=0;N='sum'}, @{T=1;N='post-HP'}, @{T=2;N='post-LP'})

$n = [int]($Seconds * $FrameHz)
function Track { param([double]$v, [switch]$Move)
    $a = New-Object double[] $n
    for ($i = 0; $i -lt $n; $i++) {
        # Modulated mode drives the amplitude at 3 Hz - fast enough to expose
        # zipper artefacts, slow enough to stay clear of the audio band itself.
        $a[$i] = if ($Move) { $v * (0.5 + 0.5 * [math]::Sin(2*[math]::PI*3.0*$i/$FrameHz)) } else { $v }
    }
    return ,$a
}

Write-Host ""
Write-Host ("CHAIN TRACE - one source at a time, {0} parameters" -f $(if ($Modulated) { 'MOVING' } else { 'CONSTANT' })) -ForegroundColor Cyan
Write-Host ("drive {0}  knee 0.8  master {1}  rate {2}" -f $Drive, $Master, $Rate) -ForegroundColor DarkGray
Write-Host ""

foreach ($src in $SRC) {
    foreach ($tap in $TAPS) {
        $ef = Track 30.0
        $rf = Track 60.0
        $ea = Track ([double]$(if ($src.Amp.e) { $src.Amp.e } else { 0.0 })) -Move:$Modulated
        $ra = Track ([double]$(if ($src.Amp.r) { $src.Amp.r } else { 0.0 })) -Move:$Modulated
        $ia = Track ([double]$(if ($src.Amp.i) { $src.Amp.i } else { 0.0 })) -Move:$Modulated
        $wa = Track ([double]$(if ($src.Amp.w) { $src.Amp.w } else { 0.0 })) -Move:$Modulated
        $ha = Track ([double]$(if ($src.Amp.h) { $src.Amp.h } else { 0.0 })) -Move:$Modulated
        $sa = Track ([double]$(if ($src.Amp.s) { $src.Amp.s } else { 0.0 })) -Move:$Modulated

        foreach ($lim in @($true, $false)) {
            # $lim=$true means BYPASS: stop before drive/limit/master.
            # Taps 0 and 1 are bypass-only; only tap 2 has a post-limiter twin.
            if (-not $lim -and $tap.T -ne 2) { continue }
            [LfeCore]::RenderTap = $tap.T
            [LfeCore]::RenderBypassLimit = $lim
            $pcm = [LfeCore]::RenderLive($ef,$ea,$rf,$ra,$ia,$wa,$ha,$sa,
                $Rate, $FrameHz, $Master, $Drive,
                [double]$tune.LfeEngineJitter, [double]$tune.LfeImpactHz, [double]$tune.LfeWeaponHz,
                [double]$tune.LfeCarrierHz, 11.0, 85.0,
                [double[]]$tune.LfeRespHz, [double[]]$tune.LfeRespRel, [double]$tune.LfeCompMax)
            $stage = if ($lim) { $tap.N } else { 'limited' }
            $name = "{0}--{1}" -f $src.N, $stage
            $path = Join-Path $OutDir "$name.wav"
            $fs=[System.IO.File]::Create($path); $bw=New-Object System.IO.BinaryWriter($fs); $b=$pcm.Length*2
            $bw.Write([char[]]'RIFF'); $bw.Write([uint32](36+$b)); $bw.Write([char[]]'WAVE'); $bw.Write([char[]]'fmt ')
            $bw.Write([uint32]16); $bw.Write([uint16]1); $bw.Write([uint16]1); $bw.Write([uint32]$Rate)
            $bw.Write([uint32]($Rate*2)); $bw.Write([uint16]2); $bw.Write([uint16]16)
            $bw.Write([char[]]'data'); $bw.Write([uint32]$b)
            foreach ($sm in $pcm) { $bw.Write([int16]$sm) }
            $bw.Flush(); $bw.Close(); $fs.Close()
        }
    }
    Write-Host ("  {0,-8} expected at {1} Hz" -f $src.N, ($src.Expect -join '/')) -ForegroundColor DarkGray
}
Write-Host ""
Write-Host ("wrote {0} - analyse with the companion python" -f $OutDir) -ForegroundColor Green
