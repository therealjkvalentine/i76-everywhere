<#
  ffb-find-rpm-wide.ps1 - find engine RPM anywhere in the game's memory.

  WHY THIS EXISTS. ffb-find-rpm.ps1 scans the vehicle entity struct and found
  nothing: across 555 parked frames, exactly FOUR slots in 0x400 bytes changed by
  any amount at all, and they were throttle and steer. That is not a threshold
  problem or a neutral-versus-in-gear problem - a field with no variance never
  reaches the ranking at all. Engine state simply is not in that struct.

  So the search has to widen. Two things were excluded before and are not now:

    * THE EXE'S OWN DATA SECTION. tools/i76-mem-dump.ahk takes only
      type=0x20000 (MEM_PRIVATE) regions. But this game keeps plenty in image
      memory - the FFB effect block sits at 0x4f2328 - so MEM_IMAGE is included
      here. RPM could have been sitting in plain sight and never dumped.
    * EVERYTHING OUTSIDE THE ENTITY. Engine state may live in a drivetrain
      struct, an audio-side variable, or a global.

  THE METHOD: alternate, do not correlate.

    Correlating a time series against throttle needs the whole heap stored per
    frame, which is not tractable here. Alternating is both cheaper and sharper:

        A = idle    B = full revs    C = idle again    D = full again

    RPM must go UP, then DOWN, then UP. Ask for three sign-correct transitions
    in a row and essentially nothing else survives - a counter only ever climbs,
    a timer never returns, and random churn does not reverse on cue three times.

    This is the Cheat Engine changed/unchanged workflow (docs/RE-METHODOLOGY.md),
    with the scan narrowed by the shape of the signal rather than by luck.

  MEMORY: only A and B are held in full. B's survivors are a short list of
  addresses, and C and D re-read just those - so the cost does not scale with
  four copies of the heap.

  NEUTRAL. Do all of this in NEUTRAL. In gear the engine is tied to the wheels
  and the revs cannot move at a standstill.

  Read-only. This script never writes to the game.

  RUN IT:
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-find-rpm-wide.ps1

  If you know the tachometer's range, pass it - it is a strong filter:
      ... -TachIdle 800 -TachMax 6000
#>
param(
    # The tach's real range, if known. A value that IS rpm should sit in it.
    # Left at 0 the scan reports everything that oscillates, whatever the units -
    # RPM may well be stored normalised (0..1) or as a fraction of redline.
    [double]$TachIdle = 0,
    [double]$TachMax  = 0,
    # A transition must move the value by at least this fraction of its own span.
    [double]$MinRise = 0.15,
    # Idle must return to near its earlier idle value.
    [double]$ReturnTol = 0.25,
    [int]$MaxCandidates = 400000
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public class I76Wide {
  [DllImport("kernel32.dll")]
  public static extern int VirtualQueryEx(IntPtr h, IntPtr addr, out MEMORY_BASIC_INFORMATION mbi, uint len);
  [DllImport("kernel32.dll")]
  public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, ref int read);

  [StructLayout(LayoutKind.Sequential)]
  public struct MEMORY_BASIC_INFORMATION {
    public IntPtr BaseAddress;      public IntPtr AllocationBase;
    public uint   AllocationProtect; public IntPtr RegionSize;
    public uint   State;            public uint   Protect;   public uint Type;
  }

  // Round one: every 4-aligned float that ROSE from a to b by a real margin.
  // Returns packed offsets; the caller turns them into virtual addresses.
  public static int[] Rose(byte[] a, byte[] b, double minRise, double lo, double hi) {
    List<int> hits = new List<int>();
    int n = Math.Min(a.Length, b.Length) - 4;
    for (int o = 0; o <= n; o += 4) {
      float va = BitConverter.ToSingle(a, o);
      float vb = BitConverter.ToSingle(b, o);
      if (float.IsNaN(va) || float.IsNaN(vb) || float.IsInfinity(va) || float.IsInfinity(vb)) continue;
      // Guard against denormals and absurd magnitudes - those are pointers and
      // packed bytes being misread as floats, not physical quantities.
      double aa = Math.Abs(va), ab = Math.Abs(vb);
      if ((aa != 0 && aa < 1e-6) || (ab != 0 && ab < 1e-6)) continue;
      if (aa > 1e9 || ab > 1e9) continue;
      if (vb <= va) continue;
      double span = Math.Max(ab, 1e-3);
      if ((vb - va) / span < minRise) continue;
      if (hi > 0 && (vb < lo * 0.5 || vb > hi * 1.5)) continue;
      hits.Add(o);
    }
    return hits.ToArray();
  }
}
'@

$ctx = Tel-Open
Write-Host ("attached - entity 0x{0:X8}" -f $ctx.Ent) -ForegroundColor Green
if ($TachMax -gt 0) {
    Write-Host ("tach filter: {0} .. {1} rpm" -f $TachIdle, $TachMax) -ForegroundColor Green
} else {
    Write-Host "no tach range given - reporting everything that oscillates, any units" -ForegroundColor DarkGray
}

# ---- region map ----------------------------------------------------------
# Committed and writable, private OR image. Image matters: the FFB block at
# 0x4f2328 proves this game keeps live state in its own data section, which the
# AHK dumper's private-only filter has always skipped.
function Get-Regions {
    $regions = New-Object System.Collections.Generic.List[object]
    $addr = [IntPtr]::Zero
    $mbi = New-Object I76Wide+MEMORY_BASIC_INFORMATION
    $sz = [System.Runtime.InteropServices.Marshal]::SizeOf($mbi)
    $total = 0
    while ($true) {
        $r = [I76Wide]::VirtualQueryEx($ctx.H, $addr, [ref]$mbi, $sz)
        if ($r -eq 0) { break }
        $base = [int64]$mbi.BaseAddress
        $size = [int64]$mbi.RegionSize
        if ($size -le 0) { break }
        $writable = ($mbi.Protect -eq 0x04) -or ($mbi.Protect -eq 0x40) -or
                    ($mbi.Protect -eq 0x08) -or ($mbi.Protect -eq 0x80)
        $wanted   = ($mbi.Type -eq 0x20000) -or ($mbi.Type -eq 0x1000000)  # PRIVATE or IMAGE
        if ($mbi.State -eq 0x1000 -and $writable -and $wanted -and $base -lt 0x7FFF0000) {
            $regions.Add([pscustomobject]@{ Base = $base; Size = [int]$size })
            $total += $size
        }
        $next = $base + $size
        if ($next -le [int64]$addr) { break }
        $addr = [IntPtr]$next
    }
    Write-Host ("{0} regions, {1:0.0} MB" -f $regions.Count, ($total / 1MB)) -ForegroundColor DarkGray
    return $regions
}

function Snapshot {
    param($Regions)
    $out = New-Object System.Collections.Generic.List[object]
    foreach ($rg in $Regions) {
        $buf = New-Object byte[] $rg.Size
        $n = 0
        if ([I76Wide]::ReadProcessMemory($ctx.H, [IntPtr]$rg.Base, $buf, $rg.Size, [ref]$n) -and $n -gt 0) {
            $out.Add([pscustomobject]@{ Base = $rg.Base; Buf = $buf; Len = $n })
        }
    }
    return $out
}

function ReadFloatAt {
    param([int64]$Va)
    $b = New-Object byte[] 4
    $n = 0
    if ([I76Wide]::ReadProcessMemory($ctx.H, [IntPtr]$Va, $b, 4, [ref]$n) -and $n -eq 4) {
        return [BitConverter]::ToSingle($b, 0)
    }
    return [double]::NaN
}

function Prompt-Step {
    param([string]$What, [string]$Detail)
    Write-Host ""
    Write-Host "--- $What ---" -ForegroundColor Yellow
    foreach ($l in $Detail -split "`n") { Write-Host "  $l" -ForegroundColor Yellow }
    Write-Host "  Hold it there, then press Enter." -ForegroundColor Yellow
    [void](Read-Host)
}

$regions = Get-Regions
if ($regions.Count -eq 0) { Write-Host "no readable regions" -ForegroundColor Red; Tel-Close $ctx; exit 1 }

Write-Host ""
Write-Host "Car in NEUTRAL for all four steps. In gear the revs cannot move." -ForegroundColor Cyan

Prompt-Step "STEP 1 of 4 - IDLE" `
    ("Foot completely OFF the throttle. Let the revs settle all the way down.")
$A = Snapshot $regions
Write-Host "  captured." -ForegroundColor DarkGray

Prompt-Step "STEP 2 of 4 - FULL REVS" `
    ("Throttle HARD ON and HOLD IT. Wait for the needle to stop climbing`n" +
     "before you press Enter - a value still on its way up is a weaker signal.")
$B = Snapshot $regions
Write-Host "  captured." -ForegroundColor DarkGray

# ---- round one: what rose? ----------------------------------------------
Write-Host ""
Write-Host "comparing idle -> full revs..." -ForegroundColor Cyan
$cands = New-Object System.Collections.Generic.List[object]
for ($i = 0; $i -lt $A.Count; $i++) {
    if ($A[$i].Base -ne $B[$i].Base) { continue }
    $offs = [I76Wide]::Rose($A[$i].Buf, $B[$i].Buf, $MinRise, $TachIdle, $TachMax)
    foreach ($o in $offs) {
        $cands.Add([pscustomobject]@{
            Va = $A[$i].Base + $o
            A  = [BitConverter]::ToSingle($A[$i].Buf, $o)
            B  = [BitConverter]::ToSingle($B[$i].Buf, $o)
        })
        if ($cands.Count -ge $MaxCandidates) { break }
    }
    if ($cands.Count -ge $MaxCandidates) { break }
}
$A = $null; $B = $null; [GC]::Collect()   # the heavy buffers are done with
Write-Host ("  {0} addresses rose" -f $cands.Count) -ForegroundColor DarkGray
if ($cands.Count -eq 0) {
    Write-Host ""
    Write-Host "NOTHING ROSE. Either the revs did not actually change between the two" -ForegroundColor Red
    Write-Host "steps (was the car in gear?), or RPM is not stored as a float." -ForegroundColor Red
    Tel-Close $ctx; exit 1
}

Prompt-Step "STEP 3 of 4 - IDLE AGAIN" `
    ("Off the throttle. Let it fall ALL the way back to idle.")
$survivors = New-Object System.Collections.Generic.List[object]
foreach ($c in $cands) {
    $v = ReadFloatAt $c.Va
    if ([double]::IsNaN($v)) { continue }
    # must have come back DOWN, and back to roughly where idle was before
    if ($v -ge $c.B) { continue }
    $span = [math]::Max([math]::Abs($c.B), 1e-3)
    if (($c.B - $v) / $span -lt $MinRise) { continue }
    if ([math]::Abs($v - $c.A) / $span -gt $ReturnTol) { continue }
    $survivors.Add([pscustomobject]@{ Va = $c.Va; A = $c.A; B = $c.B; C = $v })
}
Write-Host ("  {0} came back down to idle" -f $survivors.Count) -ForegroundColor DarkGray
if ($survivors.Count -eq 0) {
    Write-Host "NOTHING RETURNED. Try again, letting the revs fully settle each time." -ForegroundColor Red
    Tel-Close $ctx; exit 1
}

Prompt-Step "STEP 4 of 4 - FULL REVS AGAIN" `
    ("Throttle hard on once more and hold until the needle stops climbing.")
$final = New-Object System.Collections.Generic.List[object]
foreach ($s in $survivors) {
    $v = ReadFloatAt $s.Va
    if ([double]::IsNaN($v)) { continue }
    if ($v -le $s.C) { continue }
    $span = [math]::Max([math]::Abs($v), 1e-3)
    if (($v - $s.C) / $span -lt $MinRise) { continue }
    if ([math]::Abs($v - $s.B) / $span -gt $ReturnTol) { continue }   # and back near full
    $final.Add([pscustomobject]@{ Va = $s.Va; A = $s.A; B = $s.B; C = $s.C; D = $v })
}

# ---- report --------------------------------------------------------------
Write-Host ""
Write-Host "=== survived idle -> full -> idle -> full ===" -ForegroundColor Cyan
if ($final.Count -eq 0) {
    Write-Host "  nothing. Three sign-correct transitions is a hard filter - if the" -ForegroundColor Yellow
    Write-Host "  revs were settling as you pressed Enter, loosen it:" -ForegroundColor Yellow
    Write-Host "    -MinRise 0.08 -ReturnTol 0.45" -ForegroundColor Yellow
} else {
    Write-Host ("  {0} addresses. Sorted by how far they swing." -f $final.Count) -ForegroundColor Green
    Write-Host ""
    Write-Host ("  {0,-12} {1,12} {2,12} {3,12} {4,12}" -f 'address','idle','full','idle','full')
    Write-Host ("  " + ("-" * 64))
    $sorted = $final | Sort-Object -Property @{Expression={ [math]::Abs($_.B - $_.A) }} -Descending
    foreach ($f in ($sorted | Select-Object -First 40)) {
        Write-Host ("  0x{0:X8}   {1,12:0.###} {2,12:0.###} {3,12:0.###} {4,12:0.###}" -f `
            $f.Va, $f.A, $f.B, $f.C, $f.D) -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "  The one whose idle/full pair matches the TACHOMETER you can see is RPM." -ForegroundColor Gray
    Write-Host "  Values in 0..1 are a normalised fraction of redline and are just as" -ForegroundColor Gray
    Write-Host "  usable - possibly more, since no redline constant is then needed." -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Addresses at or above 0x400000 and below ~0x600000 are in the EXE's own" -ForegroundColor Gray
    Write-Host "  data section: fixed, and good to hard-code. Higher addresses are heap and" -ForegroundColor Gray
    Write-Host "  will move between runs - those need an offset from the entity instead." -ForegroundColor Gray
    if ($ctx.Ent) {
        Write-Host ""
        foreach ($f in ($sorted | Select-Object -First 40)) {
            $d = $f.Va - $ctx.Ent
            if ($d -ge 0 -and $d -lt 0x4000) {
                Write-Host ("  0x{0:X8} is entity +0x{1:X} - a stable offset, use this one." -f $f.Va, $d) -ForegroundColor Cyan
            }
        }
    }
}

Write-Host ""
Write-Host "Paste the whole output back. Read-only - nothing was written to the game." -ForegroundColor Cyan
Tel-Close $ctx
