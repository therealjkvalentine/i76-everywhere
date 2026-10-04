<#
  log-clicks.ps1 — log every mouse click WITH a before/after screenshot.

  Purpose: map I'76's menus without guessing. The game maps the cursor into its own space, so
  an OS coordinate alone doesn't tell me which control you hit. This records, for every click:

      click number, OS cursor position, timestamp
      before.png   - the screen at the moment of the click
      after.png    - the screen ~500 ms later (so I can see what the click DID)

  With those I can build the OS-coordinate -> control table directly from your session, and
  correlate with anything you narrate in chat by click number.

  You do NOT need to narrate for this to work - the screenshots identify the targets - but
  saying "click 3 was CONFIGURE CHASSIS" removes any ambiguity.

  Polls the button state rather than installing a hook, so it needs no message pump and cannot
  interfere with the game's own input.

    autotest\log-clicks.ps1 -Label equip -Seconds 240
    (press F12 in the game, or let it time out, to stop)
#>
param(
    [string]$Label = 'clicks',
    [int]$Seconds = 240,
    [string]$OutDir = "$PSScriptRoot\..\captures\clicks"
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class ClickLog {
  [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int vKey);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out System.Drawing.Point p);
}
"@ -ReferencedAssemblies System.Drawing

$dir = Join-Path $OutDir $Label
New-Item -ItemType Directory -Force $dir | Out-Null
Get-ChildItem $dir -Filter *.png -EA SilentlyContinue | Remove-Item -Force

$vs = [Windows.Forms.SystemInformation]::VirtualScreen
function Shot([string]$path) {
    $b = New-Object Drawing.Bitmap $vs.Width, $vs.Height
    $g = [Drawing.Graphics]::FromImage($b)
    try { $g.CopyFromScreen($vs.X, $vs.Y, 0, 0, $b.Size); $b.Save($path, [Drawing.Imaging.ImageFormat]::Png) }
    finally { $g.Dispose(); $b.Dispose() }
}

Write-Host "=== CLICK LOGGER ===" -ForegroundColor Green
Write-Host "Click through the menus normally. Every click is logged with before/after shots."
Write-Host "Press F12 to stop (or it stops after $Seconds s)." -ForegroundColor Yellow
Write-Host ""

$rows = @('click,t_ms,osx,osy')
$sw = [Diagnostics.Stopwatch]::StartNew()
$n = 0
$wasDown = $false
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    if (([ClickLog]::GetAsyncKeyState(0x7B) -band 0x8000) -ne 0) { break }    # F12
    $down = ([ClickLog]::GetAsyncKeyState(0x01) -band 0x8000) -ne 0           # left button
    if ($down -and -not $wasDown) {
        $n++
        $p = New-Object System.Drawing.Point
        [void][ClickLog]::GetCursorPos([ref]$p)
        $t = [int]$sw.Elapsed.TotalMilliseconds
        Shot (Join-Path $dir ("c{0:D2}_before.png" -f $n))
        $rows += ("{0},{1},{2},{3}" -f $n, $t, $p.X, $p.Y)
        Write-Host ("  click {0,2}  OS({1,4},{2,4})  t={3} ms" -f $n, $p.X, $p.Y, $t) -ForegroundColor Cyan
        Start-Sleep -Milliseconds 500
        Shot (Join-Path $dir ("c{0:D2}_after.png" -f $n))
    }
    $wasDown = $down
    Start-Sleep -Milliseconds 15
}
$rows | Set-Content (Join-Path $dir 'clicks.csv')
Write-Host ""
Write-Host ("logged {0} clicks -> {1}" -f $n, $dir) -ForegroundColor Green
Write-Host "Tell me the label and I'll read the screenshots to map each click to its control."
