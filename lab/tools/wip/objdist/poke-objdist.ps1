<#
  poke-objdist.ps1 - hunt the object/road cull distance by POKING candidate constants in the
  live process and measuring the effect objectively.

  WHY THIS EXISTS: the terrain far clip is solved (docs/DRAW-DISTANCE.md), but objects, brush
  and road segments still pop in at their own much shorter distance. Static analysis found
  several squared-distance constants; this decides which (if any) actually gates object
  drawing, without the 60s patch-and-relaunch loop.

  THE MEASUREMENT: [0x59C568] is the per-frame render RECORD COUNT (12-byte records bump-
  allocated from the arena at [0x654380]). It reacts to how much geometry is submitted, so at
  a FIXED viewpoint it is an objective proxy for "how much is being drawn" - no screenshots,
  no colour thresholds (a pixel-counting attempt failed badly: it read 0 cacti in frames that
  plainly had them).

  METHOD: A/B/A with the control measured twice, so the natural frame-to-frame spread is known
  before any difference is believed.

  Usage (game must already be IN a mission, parked):
    tools\wip\objdist\poke-objdist.ps1                 # sweep the candidate list
    tools\wip\objdist\poke-objdist.ps1 -Va 0x4BCC6C -Value 810000
#>
param(
    [uint32]$Va = 0,
    [double]$Value = 0,
    [int]$Samples = 40,
    [switch]$Screenshot
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\..\autotest\lib\maplib.ps1"

# These constants live in read-only .rdata, so a plain WriteProcessMemory FAILS - and
# Mem-WriteF32 throws the result away, so it fails SILENTLY. An entire first sweep was run
# that way and produced nothing but frame noise, with two constants flagged as significant
# purely by chance. So: take VM_OPERATION rights, drop the page protection, write, restore -
# and ALWAYS read back and throw if the value did not actually change.
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Poke {
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool VirtualProtectEx(IntPtr h, IntPtr addr, UIntPtr size, uint newP, out uint oldP);
}
"@ -ErrorAction SilentlyContinue

function Poke-F32 {
    param($Ctx, [int64]$Addr, [single]$Val)
    $old = 0
    [void][Poke]::VirtualProtectEx($Ctx.H, [IntPtr]$Addr, [UIntPtr]::new(4), 0x40, [ref]$old)  # PAGE_EXECUTE_READWRITE
    Mem-WriteF32 $Ctx $Addr $Val
    $dummy = 0
    [void][Poke]::VirtualProtectEx($Ctx.H, [IntPtr]$Addr, [UIntPtr]::new(4), $old, [ref]$dummy)
    $back = Mem-F32 $Ctx $Addr
    if ([math]::Abs($back - $Val) -gt ([math]::Abs($Val) * 1e-4 + 1e-3)) {
        throw ("poke to 0x{0:X} did NOT take (wanted {1}, read back {2}) - measurement would be meaningless" -f $Addr, $Val, $back)
    }
    $back
}

$RECORDS = 0x59C568
$ARENA   = 0x654380
$POOL    = 0x5DD324

# squared-distance constants found by the full (resyncing) disassembly sweep
$CANDIDATES = @(
    @{ va = 0x4BCC6C; stock = 8100.0;  note = 'gates a model ptr + detail 22->11, 2 call sites feeding the frustum test' },
    @{ va = 0x4BCFE8; stock = 2025.0;  note = '45^2, near 500.0 at +4' },
    @{ va = 0x4BC800; stock = 1600.0;  note = '40^2' },
    @{ va = 0x4BC93C; stock = 625.0;   note = '25^2' },
    @{ va = 0x4BC60C; stock = 6400.0;  note = '80^2, the frustum-test constant itself' },
    @{ va = 0x4BE7C8; stock = 4096.0;  note = '64^2' },
    @{ va = 0x4BC9B8; stock = 400.0;   note = '20^2' }
)

$ctx = Mem-Open -Write
if (-not (Mem-InMission $ctx)) { Mem-Close $ctx; throw "load a mission and park first" }

function Sample-Records {
    $vals = @()
    for ($i = 0; $i -lt $Samples; $i++) { $vals += (Mem-I32 $ctx $RECORDS); Start-Sleep -Milliseconds 40 }
    $m = $vals | Measure-Object -Average -Minimum -Maximum
    [pscustomobject]@{ Mean = [math]::Round($m.Average,0); Min = $m.Minimum; Max = $m.Maximum; Spread = $m.Maximum - $m.Minimum }
}
function Arena-Used { $b = Mem-I32 $ctx $POOL; $c = Mem-I32 $ctx $ARENA; if ($b -gt 0 -and $c -gt $b) { $c - $b } else { 0 } }

function Test-One([uint32]$addr, [double]$stock, [double]$test, [string]$note) {
    $orig = Mem-F32 $ctx $addr
    $a1 = Sample-Records; $ar1 = Arena-Used
    Poke-F32 $ctx $addr $test | Out-Null
    Start-Sleep -Milliseconds 600
    $b  = Sample-Records; $arb = Arena-Used
    Poke-F32 $ctx $addr $orig | Out-Null
    Start-Sleep -Milliseconds 600
    $a2 = Sample-Records
    $ctrlSpread = [math]::Abs($a2.Mean - $a1.Mean)
    $effect     = $b.Mean - (($a1.Mean + $a2.Mean) / 2)
    [pscustomobject]@{
        VA        = ('0x{0:X}' -f $addr)
        Stock     = $stock
        Tested    = $test
        A1        = $a1.Mean
        B         = $b.Mean
        A2        = $a2.Mean
        CtrlDrift = $ctrlSpread          # how much the control moved on its own
        Effect    = [math]::Round($effect,0)
        Real      = ([math]::Abs($effect) -gt (3 * [math]::Max($ctrlSpread,1)))
        ArenaKB   = [math]::Round($arb/1KB,1)
        Note      = $note
    }
}

if ($Va -ne 0) {
    Test-One $Va (Mem-F32 $ctx $Va) $Value 'manual' | Format-List
} else {
    $out = foreach ($c in $CANDIDATES) {
        # multiply the SQUARED threshold by 100 => 10x the radius
        Test-One $c.va $c.stock ($c.stock * 100.0) $c.note
    }
    $out | Format-Table VA,Stock,Tested,A1,B,A2,CtrlDrift,Effect,Real -AutoSize
    Write-Host ""
    Write-Host "Real = |effect| > 3x the control drift. Notes:" -ForegroundColor Cyan
    $out | ForEach-Object { "  {0} {1}" -f $_.VA, $_.Note }
}
Mem-Close $ctx
