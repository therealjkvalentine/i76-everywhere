<#
  patch-camera-rate.ps1 — fix the frame-coupled camera rotation (the "death camera spins too
  fast at 60 fps" bug). SANDBOX ONLY; fully reversible.

  THE BUG, measured 2026-08-10:
    The post-death camera orbits ~7-8 degrees per FRAME regardless of frame rate:
        20 Hz  -7.06 deg/frame = -143 deg/s
        60 Hz  -7.87 deg/frame = -476 deg/s
    deg/frame ratio 1.12 (constant), deg/s ratio 3.32 (scales with frame rate) => frame-coupled.

  THE CAUSE:
    Camera rotation is `angle -= input_degrees * DEG2RAD`, applied once per frame with no frame
    delta-time anywhere:
        fild  dword [0x536794 / 0x53679C]   ; pitch / yaw step, an INTEGER NUMBER OF DEGREES
        fmul  dword [0x4BC528]              ; * -0.017453292  (= -1 degree in radians)
        fsubr dword [0x4C2918 / 0x4C291C]   ; angle - that
        fst   dword [0x4C2918 / 0x4C291C]
    This appears twice (identical inlined copies at 0x405BC0 and 0x4061D0), giving the four
    references to 0x4BC528 - and those are its ONLY references in the binary, so the constant is
    camera-private and safe to scale. (Its sibling +1 degree at 0x4BC52C has 11 references spread
    across the exe and must NOT be touched.)

  THE FIX:
    Scale that degree constant by 20/target so a frame's step becomes what 20 Hz used to give.
    At 60 fps that is 1/3: -0.017453292 -> -0.005817764. Because all camera rotation runs through
    this one constant, this corrects the death orbit AND any other per-frame camera motion at
    once. It is a DATA patch - no code is moved, nothing is relocated.

    Note this makes the camera correct for ONE target frame rate; it is not true dt-scaling
    (that would need a code cave to multiply by the frame time). For a fixed-60 build, which is
    where this project landed, that is the right trade.

    tools\framerate\patch-camera-rate.ps1               # scale for 60 fps (divide by 3)
    tools\framerate\patch-camera-rate.ps1 -TargetFps 90
    tools\framerate\patch-camera-rate.ps1 -Restore
    tools\framerate\patch-camera-rate.ps1 -Status
#>
param([double]$TargetFps = 60, [switch]$Restore, [switch]$Status)
$ErrorActionPreference = 'Stop'
$exe  = Join-Path $PSScriptRoot '..\..\game\i76.exe'
$orig = "$exe.camorig"
$OFFSET = 0x0BB928           # file offset of the -1-degree constant (VA 0x4BC528, .rdata)
$STOCK  = -0.017453292       # -1 degree in radians

if (-not (Test-Path $exe)) { throw "sandbox i76.exe not found at $exe" }
$bytes = [IO.File]::ReadAllBytes($exe)
$cur = [BitConverter]::ToSingle($bytes, $OFFSET)

if ($Status) {
    $ratio = $cur / $STOCK
    Write-Host ("camera degree constant: {0:N9} rad ({1:N4} deg)  = stock x {2:N4}" -f $cur, ($cur * 180 / [math]::PI), $ratio)
    Write-Host ("  => camera is tuned for {0:N0} fps" -f (20 / $ratio))
    exit 0
}

if ($Restore) {
    if (Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -eq (Resolve-Path $exe) }) { throw "close the game first" }
    if (Test-Path $orig) { Copy-Item $orig $exe -Force; Write-Host "restored original i76.exe" -ForegroundColor Green }
    else {
        $b = [BitConverter]::GetBytes([single]$STOCK)
        [Array]::Copy($b, 0, $bytes, $OFFSET, 4); [IO.File]::WriteAllBytes($exe, $bytes)
        Write-Host "no backup found - wrote the stock constant back" -ForegroundColor Yellow
    }
    exit 0
}

if (Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -eq (Resolve-Path $exe) }) { throw "close the game first (it locks i76.exe)" }
# sanity: refuse unless we recognise what is there
if ([math]::Abs($cur - $STOCK) -gt 1e-6 -and [math]::Abs($cur) -gt 1e-6) {
    Write-Host ("value at 0x{0:X} is {1:N9}, not the stock {2:N9} - already patched? use -Status / -Restore" -f $OFFSET, $cur, $STOCK) -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path $orig)) { Copy-Item $exe $orig; Write-Host "backed up -> i76.exe.camorig" }

$new = $STOCK * (20.0 / $TargetFps)
$nb = [BitConverter]::GetBytes([single]$new)
[Array]::Copy($nb, 0, $bytes, $OFFSET, 4)
[IO.File]::WriteAllBytes($exe, $bytes)
Write-Host ("patched for {0:N0} fps: {1:N9} -> {2:N9} rad/step ({3:N4} -> {4:N4} deg)" -f `
    $TargetFps, $STOCK, $new, ($STOCK * 180 / [math]::PI), ($new * 180 / [math]::PI)) -ForegroundColor Green
Write-Host "relaunch and verify with tools\framerate\death-orbit.ps1" -ForegroundColor Cyan
