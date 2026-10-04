<#
  probe-loop.ps1 — instrumentation for the 60 Hz uncap effort (READ-ONLY).

  Reads Interstate '76 process memory (ReadProcessMemory only — never writes) to
  answer the three questions the 60 Hz plan is blocked on. Model the game window at
  the PHYSICAL CONSOLE, never over RDP (the game's 3D won't init on RDP, and any
  measurement taken under RDP is invalid — see the parent repo AGENTS.md).

  Addresses: Gold i76.exe MD5 60ABF7BC..., loaded at 0x400000, no ASLR under Wine
  or native. Frame counter + render map are in docs/ENGINE-LOOP-MAP.md; entity
  chain is the parent repo's ([[[0x54a264]]+0x70]).

  MODES
    -Fps           Poll the frame counter (0x5A7E1C) and print real frames/sec.
                   Proves 0x5A7E1C is the per-frame counter and measures the
                   current cap (expect ~20 with the AiO/dgVoodoo limiter on).
    -Coupling      Poll frame counter AND player speed together. Reports sim-state
                   changes per frame — settles sim==render live (expect 1:1).
    -FindPos       THE position-offset hunt. DRIVE IN A STRAIGHT LINE at steady
                   speed while this runs; it finds the float3 in the entity struct
                   whose per-frame delta matches velocity*dt. Unblocks interpolation.

  Usage:
    powershell -ExecutionPolicy Bypass -File tools\probe-loop.ps1 -Fps
    powershell -ExecutionPolicy Bypass -File tools\probe-loop.ps1 -Coupling
    powershell -ExecutionPolicy Bypass -File tools\probe-loop.ps1 -FindPos
#>
param(
    [switch]$Fps,
    [switch]$Coupling,
    [switch]$FindPos,
    [int]$Seconds = 8,
    [int]$ScanBytes = 0x200
)
$ErrorActionPreference = 'Stop'

# --- addresses ---------------------------------------------------------------
$FRAME_COUNTER = 0x5A7E1C   # inc'd once per rendered frame (0x49C920)
$WORLD_ROOT    = 0x54A264   # [[[0x54a264]]+0x70] = player entity
$OFF_SPEED     = 0xAC       # float |velocity|
$OFF_VEL       = 0xBC       # float3 world-space velocity
$ENT_SCAN      = $ScanBytes # bytes of entity struct to scan for position

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class I76Probe {
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int read);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@

function Open-Ctx {
    $proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $proc) { throw "Interstate '76 is not running." }
    $h = [I76Probe]::OpenProcess(0x10, $false, $proc.Id)   # PROCESS_VM_READ
    if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed (run as the same user as the game)." }
    [pscustomobject]@{ Proc = $proc; H = $h }
}
function RInt  ($Ctx, [int64]$Addr) { $b = New-Object byte[] 4; $n = 0
    if ([I76Probe]::ReadProcessMemory($Ctx.H, [IntPtr]$Addr, $b, 4, [ref]$n) -and $n -eq 4) { [BitConverter]::ToInt32($b,0) } else { $null } }
function RFloat($Ctx, [int64]$Addr) { $b = New-Object byte[] 4; $n = 0
    if ([I76Probe]::ReadProcessMemory($Ctx.H, [IntPtr]$Addr, $b, 4, [ref]$n) -and $n -eq 4) { [BitConverter]::ToSingle($b,0) } else { $null } }
function RBlock($Ctx, [int64]$Addr, [int]$Size) { $b = New-Object byte[] $Size; $n = 0
    if ([I76Probe]::ReadProcessMemory($Ctx.H, [IntPtr]$Addr, $b, $Size, [ref]$n) -and $n -eq $Size) { $b } else { $null } }
function Resolve-Entity ($Ctx) {
    $p = RInt $Ctx $WORLD_ROOT; if (-not $p) { return 0 }
    $p = RInt $Ctx $p;          if (-not $p) { return 0 }
    $e = RInt $Ctx ($p + 0x70); if (-not $e) { return 0 }
    return $e
}

$ctx = Open-Ctx
Write-Host ("Attached to {0} (pid {1})." -f $ctx.Proc.ProcessName, $ctx.Proc.Id) -ForegroundColor Cyan

# --- -Fps --------------------------------------------------------------------
if ($Fps) {
    $f0 = RInt $ctx $FRAME_COUNTER
    if ($null -eq $f0) { throw "Could not read the frame counter." }
    Write-Host "Measuring the frame counter at 0x5A7E1C for $Seconds s. Be in a mission (not a menu)." -ForegroundColor Yellow
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Start-Sleep -Milliseconds 250
    $samples = @()
    $last = $f0; $lastT = 0.0
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        Start-Sleep -Milliseconds 500
        $now = RInt $ctx $FRAME_COUNTER; $t = $sw.Elapsed.TotalSeconds
        if ($now -ne $null -and $now -ge $last) {
            $instFps = ($now - $last) / ($t - $lastT)
            $samples += $instFps
            Write-Host ("  t={0,5:N1}s  frames={1,7}  inst_fps={2,6:N1}" -f $t, $now, $instFps)
        }
        $last = $now; $lastT = $t
    }
    if ($samples.Count) {
        $avg = ($samples | Measure-Object -Average).Average
        Write-Host ("REAL frame rate: {0:N1} FPS (avg over {1} samples)." -f $avg, $samples.Count) -ForegroundColor Green
        Write-Host "If this is ~20, the cap is on. That is the number the 60 Hz work must beat." -ForegroundColor Green
    }
    [I76Probe]::CloseHandle($ctx.H) | Out-Null
    return
}

# --- -Coupling ---------------------------------------------------------------
if ($Coupling) {
    $ent = Resolve-Entity $ctx
    if (-not $ent) { throw "Player entity is NULL - load a mission first." }
    Write-Host "Watching frame counter vs sim state for $Seconds s. Drive around so speed changes." -ForegroundColor Yellow
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $lastFrame = RInt $ctx $FRAME_COUNTER
    $lastSpeed = RFloat $ctx ($ent + $OFF_SPEED)
    $frameAdv = 0; $simAdv = 0; $polls = 0
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        Start-Sleep -Milliseconds 10
        $polls++
        $f = RInt $ctx $FRAME_COUNTER
        $s = RFloat $ctx ($ent + $OFF_SPEED)
        if ($f -ne $lastFrame) { $frameAdv += ($f - $lastFrame); $lastFrame = $f }
        if ($s -ne $null -and [math]::Abs($s - $lastSpeed) -gt 1e-6) { $simAdv++; $lastSpeed = $s }
    }
    Write-Host ("polls={0}  frame_advances={1}  sim_changes={2}" -f $polls, $frameAdv, $simAdv)
    if ($frameAdv -gt 0) {
        Write-Host ("sim changes / frame = {0:N2}" -f ($simAdv / [double]$frameAdv)) -ForegroundColor Green
        Write-Host "~1.0 (while moving) => sim advances once per rendered frame = sim==render, as expected." -ForegroundColor Green
    }
    [I76Probe]::CloseHandle($ctx.H) | Out-Null
    return
}

# --- -FindPos : the position/orientation offset hunt -------------------------
if ($FindPos) {
    $ent = Resolve-Entity $ctx
    if (-not $ent) { throw "Player entity is NULL - load a mission first." }
    Write-Host "POSITION HUNT. Drive in a STRAIGHT LINE at steady speed now (hold throttle)." -ForegroundColor Yellow
    Write-Host "Looking for a float3 whose per-frame delta == velocity*dt ..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2

    # Two samples a known wall-time apart, plus velocity, and the frame counter so
    # we know how many sim steps elapsed. Displacement over the interval should be
    # velocity * elapsed for the true world-position triple.
    $vx = RFloat $ctx ($ent + $OFF_VEL);       $vy = RFloat $ctx ($ent + $OFF_VEL + 4); $vz = RFloat $ctx ($ent + $OFF_VEL + 8)
    $spd = RFloat $ctx ($ent + $OFF_SPEED)
    if ($spd -lt 2.0) { Write-Host ("Speed is only {0:N1} m/s - drive faster for a cleaner signal." -f $spd) -ForegroundColor Red }

    $a = RBlock $ctx $ent $ENT_SCAN
    $fA = RInt $ctx $FRAME_COUNTER
    $t0 = [Diagnostics.Stopwatch]::StartNew()
    Start-Sleep -Milliseconds 700
    $b = RBlock $ctx $ent $ENT_SCAN
    $fB = RInt $ctx $FRAME_COUNTER
    $elapsed = $t0.Elapsed.TotalSeconds
    if (-not $a -or -not $b) { throw "Entity read failed." }

    # Expected displacement over the interval (world space).
    $ex = $vx * $elapsed; $ey = $vy * $elapsed; $ez = $vz * $elapsed
    $expLen = [math]::Sqrt($ex*$ex + $ey*$ey + $ez*$ez)
    Write-Host ("velocity=({0:N2},{1:N2},{2:N2})  elapsed={3:N3}s  frames={4}  expected|d|={5:N3} m" -f $vx,$vy,$vz,$elapsed,($fB-$fA),$expLen)
    if ($expLen -lt 0.3) { Write-Host "Expected displacement too small - drive faster/straighter and re-run." -ForegroundColor Red }

    # Scan every 4-aligned offset; treat [o],[o+4],[o+8] as a float3 delta and
    # score against the expected displacement vector.
    $cands = @()
    for ($o = 0; $o -le $ENT_SCAN - 12; $o += 4) {
        $dx = [BitConverter]::ToSingle($b,$o)   - [BitConverter]::ToSingle($a,$o)
        $dy = [BitConverter]::ToSingle($b,$o+4) - [BitConverter]::ToSingle($a,$o+4)
        $dz = [BitConverter]::ToSingle($b,$o+8) - [BitConverter]::ToSingle($a,$o+8)
        if ([double]::IsNaN($dx) -or [double]::IsNaN($dy) -or [double]::IsNaN($dz)) { continue }
        $dlen = [math]::Sqrt($dx*$dx + $dy*$dy + $dz*$dz)
        if ($dlen -lt 1e-3) { continue }
        # error vs expected displacement (want small)
        $err = [math]::Sqrt((($dx-$ex)*($dx-$ex)) + (($dy-$ey)*($dy-$ey)) + (($dz-$ez)*($dz-$ez)))
        $cands += [pscustomobject]@{ Off = ('+0x{0:X}' -f $o); Delta = ('({0:N2},{1:N2},{2:N2})' -f $dx,$dy,$dz); Len = $dlen; Err = $err }
    }
    Write-Host "`nBest position-offset candidates (lowest Err = closest to velocity*dt):" -ForegroundColor Cyan
    $cands | Sort-Object Err | Select-Object -First 8 | Format-Table Off, Delta, @{n='Len';e={'{0:N2}' -f $_.Len}}, @{n='Err';e={'{0:N3}' -f $_.Err}} -AutoSize
    Write-Host "The winning offset is the world-position float3. Orientation is usually a 3x3 or quaternion just before/after it." -ForegroundColor Green
    Write-Host "Re-run 2-3 times driving different headings to confirm the same offset wins each time." -ForegroundColor Green
    [I76Probe]::CloseHandle($ctx.H) | Out-Null
    return
}

Write-Host "Pick a mode: -Fps | -Coupling | -FindPos   (see the header comment)." -ForegroundColor Yellow
[I76Probe]::CloseHandle($ctx.H) | Out-Null
