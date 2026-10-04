<#
  cursor-absolute-test.ps1 — is the game's cursor an ABSOLUTE function of the OS cursor?

  Everything else about clicking depends on this. If dgVoodoo (with CaptureMouse) feeds the app
  accumulated RELATIVE deltas, then no fixed screen<->OS mapping can exist and every calibration
  will silently drift depending on where the cursor came from - which is exactly the symptom
  we've been fighting.

  Test: park the cursor at the same target from three different previous positions and see
  whether the game draws it in the same place each time.
#>
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
. "$PSScriptRoot\..\lib\maplib.ps1"
Add-Type -AssemblyName System.Drawing
$out = "$PSScriptRoot\..\..\captures\cursorabs"
New-Item -ItemType Directory -Force $out | Out-Null

$proc = Get-GamePid
Force-Foreground $proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 600
$r = Get-ContentRect

function Shot640([string]$tag) {
    $b = New-Object Drawing.Bitmap $r.W, $r.H
    $g = [Drawing.Graphics]::FromImage($b)
    $g.CopyFromScreen($r.X, $r.Y, 0, 0, (New-Object Drawing.Size($r.W, $r.H)))
    $s = New-Object Drawing.Bitmap 640, 480
    $g2 = [Drawing.Graphics]::FromImage($s); $g2.InterpolationMode = 'HighQualityBicubic'
    $g2.DrawImage($b, 0, 0, 640, 480)
    $s.Save((Join-Path $out "$tag.png"), [Drawing.Imaging.ImageFormat]::Png)
    $bd = $s.LockBits((New-Object Drawing.Rectangle 0,0,640,480),
        [Drawing.Imaging.ImageLockMode]::ReadOnly, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $buf = New-Object byte[] (640*480*4)
    [Runtime.InteropServices.Marshal]::Copy($bd.Scan0, $buf, 0, $buf.Length)
    $s.UnlockBits($bd)
    $g.Dispose(); $g2.Dispose(); $b.Dispose(); $s.Dispose()
    return $buf
}
# bounding box of where two frames differ = where the cursor moved between them
function DiffBox($a, $b) {
    $x0=9999;$y0=9999;$x1=-1;$y1=-1;$n=0
    for ($y=0; $y -lt 480; $y++) {
        $row=$y*640*4
        for ($x=0; $x -lt 640; $x++) {
            $i=$row+$x*4
            $d=[math]::Abs([int]$a[$i]-[int]$b[$i])+[math]::Abs([int]$a[$i+1]-[int]$b[$i+1])+[math]::Abs([int]$a[$i+2]-[int]$b[$i+2])
            if ($d -gt 100) { $n++; if($x -lt $x0){$x0=$x}; if($x -gt $x1){$x1=$x}; if($y -lt $y0){$y0=$y}; if($y -gt $y1){$y1=$y} }
        }
    }
    if ($n -eq 0) { return "IDENTICAL" }
    return ("{0} px changed, box x{1}..{2} y{3}..{4}" -f $n,$x0,$x1,$y0,$y1)
}

$target = @(320, 240)
$froms  = @(@(100,100), @(600,450), @(320,470))
$bufs = @()
foreach ($f in $froms) {
    [Inp]::SetCursorPos($f[0], $f[1]) | Out-Null; Start-Sleep -Milliseconds 450
    [Inp]::SetCursorPos($target[0], $target[1]) | Out-Null; Start-Sleep -Milliseconds 450
    $bufs += ,(Shot640 ("from_{0}_{1}" -f $f[0], $f[1]))
    Write-Host ("  arrived at OS({0},{1}) from OS({2},{3})" -f $target[0],$target[1],$f[0],$f[1])
}
Write-Host ""
Write-Host "A vs B: $(DiffBox $bufs[0] $bufs[1])" -ForegroundColor Cyan
Write-Host "A vs C: $(DiffBox $bufs[0] $bufs[2])" -ForegroundColor Cyan
Write-Host ""
Write-Host "IDENTICAL on both = mapping is absolute, math can work." -ForegroundColor Green
Write-Host "Differences = dgVoodoo is feeding relative deltas; no fixed mapping exists." -ForegroundColor Yellow
