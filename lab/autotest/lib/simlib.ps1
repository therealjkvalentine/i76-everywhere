<#
  simlib.ps1 — make sure the SIMULATION is actually running before you measure anything.

  Two different things stop the sim while the game still looks fine:
    1. the window is not focused  -> I'76 freezes the sim, renderer keeps drawing
    2. the in-mission pause menu ("Spanner's Cafe", opened by ESC) is up
  Both give bit-identical samples forever. Entry scripts spam ESC to skip cutscenes, and the
  last ESC often lands in-mission and opens that menu - so ALWAYS call Ensure-SimRunning
  after entering a mission and before any trace.

  Requires focuslib, inputlib and memlib to be dot-sourced first.
#>
function Test-SimAdvancing {
    param($Ctx, [int]$WaitMs = 500)
    $a = Mem-I32 $Ctx (Mem-Map).FrameCounter
    Start-Sleep -Milliseconds $WaitMs
    $b = Mem-I32 $Ctx (Mem-Map).FrameCounter
    return ($b -ne $a)
}
function Ensure-SimRunning {
    <#
      Focuses the game, closes the pause menu if present, and returns $true once the frame
      counter is advancing. Verifies rather than assumes.
    #>
    param($Ctx, [int]$Tries = 6)
    for ($i = 0; $i -lt $Tries; $i++) {
        Force-Foreground $Ctx.Proc.MainWindowHandle | Out-Null
        Start-Sleep -Milliseconds 400
        if (Test-SimAdvancing $Ctx 400) { return $true }
        Send-Key $VK.ESC          # toggle the pause menu shut
        Start-Sleep -Milliseconds 700
        if (Test-SimAdvancing $Ctx 400) { return $true }
    }
    return (Test-SimAdvancing $Ctx 500)
}
