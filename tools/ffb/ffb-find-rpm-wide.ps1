<#
  ffb-find-rpm-wide.ps1 - find engine RPM anywhere in the game's memory.

  WHY THIS EXISTS. ffb-find-rpm.ps1 scans the vehicle entity struct and found
  nothing: across 555 parked frames, exactly FOUR slots in 0x400 bytes changed by
  any amount, and they were throttle and steer. A field with no variance never
  reaches the ranking, so that null was not a threshold or in-gear problem.
  Engine state is not in that struct.

  Two exclusions are lifted here:

    * THE EXE'S OWN DATA SECTION. tools/i76-mem-dump.ahk takes only
      type=0x20000 (MEM_PRIVATE). This game keeps live state in image memory -
      the FFB effect block sits at 0x4f2328 - so MEM_IMAGE is included too.
    * EVERYTHING OUTSIDE THE ENTITY. Engine state may sit in a drivetrain
      struct, an audio-side variable, or a global.

  THE METHOD: alternate, do not correlate.

        A = idle    B = full revs    C = idle again    D = full again

    RPM must go UP, then DOWN, then UP. Three sign-correct transitions is a hard
    filter - counters only climb, timers never return, and random churn does not
    reverse on cue three times. This is the Cheat Engine changed/unchanged
    workflow (docs/RE-METHODOLOGY.md), narrowed by the shape of the signal.

    Each step is HELD until the needle stops moving, then Enter. The settled
    value is the measurement, so no rhythm-keeping is needed.

  WHAT THE FIRST RUN TAUGHT US. 29 addresses survived, and none was RPM:
    * 0x005DDEAC..0x005DEE2C - nine slots at ~0x80 stride, snapping between
      exactly repeated values. An array of structs: the SOUND pitch multipliers,
      driven by RPM but not RPM itself. Still useful as a rev proxy.
    * 0x007EAF84..0x007EAFC4 - stride 8, a smooth curve, neighbours going
      negative. An audio MIXING BUFFER: waveform samples, louder when revving.
    * 0x005DEE30 = -107374200, which is 0xCCCCCCCC - MSVC uninitialised fill.
  The tachometer swings by a factor of about 4.3 and nothing in that list moved
  anywhere near that much. So:

    THREE WIDTHS, NOT ONE. The first pass scanned 4-byte floats only - the struct
    scanner had always checked int32 as well, and the wide one lost it. A 1997
    title may hold revs as an int or a double just as readily. All three now.

    RANK BY RATIO, DO NOT FILTER BY VALUE. An absolute range filter would hide a
    value stored normalised (rpm/redline), which is a likely representation and
    arguably the better find - no redline constant needed. A RATIO is unit-free:
    literal 1350->5750 and normalised 0.225->0.958 both read as 4.3. So the tach
    reading ranks candidates instead of excluding them.

  Read-only. This script never writes to the game.

  RUN IT, with the tach range you can see on the dashboard:
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-find-rpm-wide.ps1 -TachIdle 1350 -TachMax 5750
#>
param(
    # What the dashboard tachometer actually reads at idle and at full revs.
    # Used to RANK candidates by ratio, never to exclude them - see above.
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

  // kind: 0 = float32, 1 = int32, 2 = double
  public static double Val(byte[] b, int o, int kind) {
    if (kind == 0) return BitConverter.ToSingle(b, o);
    if (kind == 1) return BitConverter.ToInt32(b, o);
    return BitConverter.ToDouble(b, o);
  }

  // Round one: every value that ROSE from a to b by a real margin.
  public static int[] Rose(byte[] a, byte[] b, double minRise, int kind) {
    List<int> hits = new List<int>();
    int width = (kind == 2) ? 8 : 4;
    int step  = (kind == 2) ? 8 : 4;   // doubles are 8-aligned in practice
    int n = Math.Min(a.Length, b.Length) - width;
    for (int o = 0; o <= n; o += step) {
      double va = Val(a, o, kind), vb = Val(b, o, kind);
      if (double.IsNaN(va) || double.IsNaN(vb) ||
          double.IsInfinity(va) || double.IsInfinity(vb)) continue;
      double aa = Math.Abs(va), ab = Math.Abs(vb);
      // Denormals are pointers and packed bytes misread as reals, not physics.
      // Integers are exempt: a small int is a perfectly ordinary integer.
      if (kind != 1 && ((aa != 0 && aa < 1e-6) || (ab != 0 && ab < 1e-6))) continue;
      if (aa > 1e9 || ab > 1e9) continue;
      if (vb <= va) continue;
      double span = Math.Max(ab, 1e-3);
      if ((vb - va) / span < minRise) continue;
      hits.Add(o);
    }
    return hits.ToArray();
  }
}
'@

$KINDS = @(
    @{ Id = 0; Name = 'f32'; Width = 4 },
    @{ Id = 1; Name = 'i32'; Width = 4 },
    @{ Id = 2; Name = 'f64'; Width = 8 }
)

$ctx = Tel-Open
Write-Host ("attached - entity 0x{0:X8}" -f $ctx.Ent) -ForegroundColor Green
$ratioTarget = 0.0
if ($TachIdle -gt 0 -and $TachMax -gt 0) {
    $ratioTarget = $TachMax / $TachIdle
    Write-Host ("tach {0} -> {1} rpm: ranking by ratio {2:0.00} (not filtering by value)" -f `
        $TachIdle, $TachMax, $ratioTarget) -ForegroundColor Green
} else {
    Write-Host "no tach range given - results ranked by swing only" -ForegroundColor DarkGray
}

# ---- region map ----------------------------------------------------------
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

function ReadValueAt {
    param([int64]$Va, [int]$Kind, [int]$Width)
    $b = New-Object byte[] $Width
    $n = 0
    if ([I76Wide]::ReadProcessMemory($ctx.H, [IntPtr]$Va, $b, $Width, [ref]$n) -and $n -eq $Width) {
        return [I76Wide]::Val($b, 0, $Kind)
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

# ---- round one: what rose, at any of the three widths? -------------------
Write-Host ""
Write-Host "comparing idle -> full revs (float32, int32, float64)..." -ForegroundColor Cyan
$cands = New-Object System.Collections.Generic.List[object]
foreach ($k in $KINDS) {
    $before = $cands.Count
    for ($i = 0; $i -lt $A.Count; $i++) {
        if ($A[$i].Base -ne $B[$i].Base) { continue }
        $offs = [I76Wide]::Rose($A[$i].Buf, $B[$i].Buf, $MinRise, $k.Id)
        foreach ($o in $offs) {
            $cands.Add([pscustomobject]@{
                Va = $A[$i].Base + $o; Kind = $k.Id; KindName = $k.Name; Width = $k.Width
                A  = [I76Wide]::Val($A[$i].Buf, $o, $k.Id)
                B  = [I76Wide]::Val($B[$i].Buf, $o, $k.Id)
            })
            if ($cands.Count -ge $MaxCandidates) { break }
        }
        if ($cands.Count -ge $MaxCandidates) { break }
    }
    Write-Host ("  {0,-4} {1} rose" -f $k.Name, ($cands.Count - $before)) -ForegroundColor DarkGray
}
$A = $null; $B = $null; [GC]::Collect()
if ($cands.Count -eq 0) {
    Write-Host ""
    Write-Host "NOTHING ROSE at any width. Either the revs did not change between the" -ForegroundColor Red
    Write-Host "two steps (was the car in gear?), or RPM is not a 4/8-byte number." -ForegroundColor Red
    Tel-Close $ctx; exit 1
}

Prompt-Step "STEP 3 of 4 - IDLE AGAIN" `
    ("Off the throttle. Let it fall ALL the way back to idle.")
$survivors = New-Object System.Collections.Generic.List[object]
foreach ($c in $cands) {
    $v = ReadValueAt $c.Va $c.Kind $c.Width
    if ([double]::IsNaN($v)) { continue }
    if ($v -ge $c.B) { continue }
    $span = [math]::Max([math]::Abs($c.B), 1e-3)
    if (($c.B - $v) / $span -lt $MinRise) { continue }
    if ([math]::Abs($v - $c.A) / $span -gt $ReturnTol) { continue }
    $survivors.Add([pscustomobject]@{
        Va=$c.Va; Kind=$c.Kind; KindName=$c.KindName; Width=$c.Width; A=$c.A; B=$c.B; C=$v })
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
    $v = ReadValueAt $s.Va $s.Kind $s.Width
    if ([double]::IsNaN($v)) { continue }
    if ($v -le $s.C) { continue }
    $span = [math]::Max([math]::Abs($v), 1e-3)
    if (($v - $s.C) / $span -lt $MinRise) { continue }
    if ([math]::Abs($v - $s.B) / $span -gt $ReturnTol) { continue }
    # Ratio is unit-free, so it matches whether the field is literal rpm or a
    # normalised fraction of redline. Averaged over both idle/full pairs.
    $r1 = if ([math]::Abs($s.A) -gt 1e-9) { $s.B / $s.A } else { [double]::NaN }
    $r2 = if ([math]::Abs($s.C) -gt 1e-9) { $v / $s.C } else { [double]::NaN }
    $ratio = if ([double]::IsNaN($r1)) { $r2 } elseif ([double]::IsNaN($r2)) { $r1 } else { ($r1 + $r2) / 2 }
    $score = [double]::MaxValue
    if ($ratioTarget -gt 0 -and -not [double]::IsNaN($ratio) -and $ratio -gt 0) {
        $score = [math]::Abs([math]::Log($ratio) - [math]::Log($ratioTarget))
    }
    $final.Add([pscustomobject]@{
        Va=$s.Va; KindName=$s.KindName; A=$s.A; B=$s.B; C=$s.C; D=$v; Ratio=$ratio; Score=$score })
}

# ---- report --------------------------------------------------------------
Write-Host ""
Write-Host "=== survived idle -> full -> idle -> full ===" -ForegroundColor Cyan
if ($final.Count -eq 0) {
    Write-Host "  nothing. Three sign-correct transitions is a hard filter - if the" -ForegroundColor Yellow
    Write-Host "  revs were still settling as you pressed Enter, loosen it:" -ForegroundColor Yellow
    Write-Host "    -MinRise 0.08 -ReturnTol 0.45" -ForegroundColor Yellow
    Tel-Close $ctx; exit 0
}

$sorted = if ($ratioTarget -gt 0) {
    $final | Sort-Object Score, @{Expression={ [math]::Abs($_.B - $_.A) }; Descending=$true}
} else {
    $final | Sort-Object -Property @{Expression={ [math]::Abs($_.B - $_.A) }} -Descending
}

Write-Host ("  {0} addresses." -f $final.Count) -ForegroundColor Green
if ($ratioTarget -gt 0) {
    Write-Host ("  Ranked by how close their swing ratio is to the tach's {0:0.00}." -f $ratioTarget) -ForegroundColor Green
}
Write-Host ""
Write-Host ("  {0,-12} {1,-4} {2,10} {3,10} {4,10} {5,10} {6,7}" -f `
    'address','type','idle','full','idle','full','ratio')
Write-Host ("  " + ("-" * 72))
foreach ($f in ($sorted | Select-Object -First 40)) {
    $rs = if ([double]::IsNaN($f.Ratio)) { '   n/a' } else { ("{0,7:0.00}" -f $f.Ratio) }
    $hit = ($ratioTarget -gt 0 -and $f.Score -lt 0.22)   # within ~25% of the tach ratio
    Write-Host ("  0x{0:X8}   {1,-4} {2,10:0.###} {3,10:0.###} {4,10:0.###} {5,10:0.###} {6}" -f `
        $f.Va, $f.KindName, $f.A, $f.B, $f.C, $f.D, $rs) `
        -ForegroundColor $(if ($hit) { 'Green' } else { 'Gray' })
}

Write-Host ""
Write-Host "  Green rows swing by the same factor as the tachometer does. If one also" -ForegroundColor Gray
Write-Host "  READS like the tach (1350 -> 5750), that is RPM outright. A 0..1 pair with" -ForegroundColor Gray
Write-Host "  the right ratio is RPM normalised to redline - equally usable." -ForegroundColor Gray
Write-Host ""
Write-Host "  0x400000-0x600000 is the EXE's own data section: fixed, safe to hard-code." -ForegroundColor Gray
Write-Host "  Higher addresses are heap and move between runs - those need an offset." -ForegroundColor Gray
if ($ctx.Ent) {
    foreach ($f in ($sorted | Select-Object -First 40)) {
        $d = $f.Va - $ctx.Ent
        if ($d -ge 0 -and $d -lt 0x4000) {
            Write-Host ("  0x{0:X8} is entity +0x{1:X} - a stable offset, prefer this one." -f $f.Va, $d) -ForegroundColor Cyan
        }
    }
}

Write-Host ""
Write-Host "Paste the whole output back. Read-only - nothing was written to the game." -ForegroundColor Cyan
Tel-Close $ctx
