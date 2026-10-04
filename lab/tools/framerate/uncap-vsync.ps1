<#
  uncap-vsync.ps1 - remove (or restore) the 60fps vsync wall in the SANDBOX renderer.

  CORRECTED 2026-10-03: the premise below is wrong. This patch was measured at 60.1 fps, unchanged
  (docs\framerate\README.md section 6), so the swap interval is NOT the 60fps cap. The cap is the
  refresh code ZGLIDE passes to grSstWinOpen (GR_REFRESH_60Hz), which dgVoodoo paces windowed
  presents at; the proxy's I76_GLIDE_REFRESH=120 substitutes it (i76-everywhere
  docs\records\FPS-120.md). "FPSLimit (proven inert)" is void: it was measured while dgVoodoo was
  rejecting the sandbox conf (docs\DGVOODOO-CONF-REJECTED.md). Kept as a working byte-patch example.

  The exact-60fps ceiling is not dgVoodoo's FPSLimit (proven inert) and not the monitor (held
  at 179 Hz). It is the game's own Glide renderer plugin, zglide.dll, calling grBufferSwap(1) -
  "swap on the next vertical retrace" - against a device it opened at GR_REFRESH_60Hz. That
  one-retrace wait every frame is the 60fps cap, and it also explains why FPSLimit did nothing:
  the swap wait dominates it.

  This flips the swap interval from 1 to 0 (push 1 -> push 0 at file offset 0x2303, VA
  0x10002F03), so grBufferSwap returns without waiting. The frame rate is then bounded by the
  CPU/GPU and by whatever soft limiter you set (dgVoodoo FPSLimit or the DLL's fpscap), which
  can finally take effect.

  SANDBOX ONLY - patches game\zglide.dll in the lab copy; the playable install is never touched.
  Fully reversible: keeps zglide.dll.orig and restores from it.

    tools\framerate\uncap-vsync.ps1            # patch (swap interval 1 -> 0)
    tools\framerate\uncap-vsync.ps1 -Restore   # put the original renderer back
    tools\framerate\uncap-vsync.ps1 -Status    # report current state
#>
param([switch]$Restore, [switch]$Status)
$ErrorActionPreference = 'Stop'
$dll  = Join-Path $PSScriptRoot '..\..\game\zglide.dll'
$orig = "$dll.orig"
$OFFSET = 0x2303          # file offset of the swap-interval immediate (push 1 = 6A 01)

if (-not (Test-Path $dll)) { throw "zglide.dll not found at $dll" }
$bytes = [IO.File]::ReadAllBytes($dll)

function State {
    if ($bytes[$OFFSET] -eq 0x6A -and $bytes[$OFFSET + 1] -eq 0x01) { 'CAPPED (grBufferSwap(1), vsync to 60Hz)' }
    elseif ($bytes[$OFFSET] -eq 0x6A -and $bytes[$OFFSET + 1] -eq 0x00) { 'UNCAPPED (grBufferSwap(0), no vsync wait)' }
    else { ('UNKNOWN - bytes {0:X2} {1:X2} at 0x{2:X}' -f $bytes[$OFFSET], $bytes[$OFFSET + 1], $OFFSET) }
}

if ($Status) { Write-Host ("zglide.dll: {0}" -f (State)); exit 0 }

if ($Restore) {
    if (Test-Path $orig) {
        if (Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -eq (Resolve-Path $dll) }) {
            throw "game is running - close it first (it locks zglide.dll)"
        }
        Copy-Item $orig $dll -Force
        Write-Host "restored original zglide.dll" -ForegroundColor Green
    } else { Write-Host "no .orig backup - nothing to restore" -ForegroundColor Yellow }
    exit 0
}

# patch
if ($bytes[$OFFSET] -ne 0x6A -or $bytes[$OFFSET + 1] -ne 0x01) {
    Write-Host ("not the expected 'push 1' (found {0:X2} {1:X2}) - already patched? see -Status" -f `
        $bytes[$OFFSET], $bytes[$OFFSET + 1]) -ForegroundColor Yellow
    exit 1
}
if (Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -eq (Resolve-Path $dll) }) {
    throw "game is running - close it first (it locks zglide.dll)"
}
if (-not (Test-Path $orig)) { Copy-Item $dll $orig; Write-Host "backed up -> zglide.dll.orig" }
$bytes[$OFFSET + 1] = 0x00
[IO.File]::WriteAllBytes($dll, $bytes)
Write-Host "patched: grBufferSwap(1) -> grBufferSwap(0). Relaunch and measure with probe-loop.ps1 -Fps." -ForegroundColor Green
