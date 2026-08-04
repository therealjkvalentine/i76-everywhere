<#
  ffb-find-fire.ps1 - find the weapon-fire flag by watching it change.

  WHY: docs/MEMORY-MAP-INDEX.md lists `0x5367db` as the weapon_fire input, and it
  may well be right - but the whole input-globals block reads zero on a parked car
  with no input, which cannot distinguish "correct address, nothing happening" from
  "wrong address". Rather than build a force channel on an address I have not seen
  move, this watches the region and reports which bytes actually change when you
  pull the trigger.

  Same method that pinned velocity: separate the candidates by BEHAVIOUR, not by
  plausible-looking values.

  ---------------------------------------------------------------------------
  HOW TO RUN IT
  ---------------------------------------------------------------------------
      tools\ffb\ffb-find-fire.ps1

  Then, in a mission:
    * PHASE 1 (baseline, 4 s) - hands OFF everything. Do not steer, drive or fire.
    * PHASE 2 (fire, 8 s)     - FIRE REPEATEDLY, and DO NOT steer or accelerate.

  Not steering during phase 2 is the whole trick: steer and throttle live in the
  same block, so anything that moves while you are only firing is a fire-related
  flag. Whatever changes in phase 2 but not phase 1 is the candidate.

  Writes ffb-fire-candidates.txt. Read-only; nothing is written to the game.
#>
param(
    [int]$BaselineSeconds = 4,
    [int]$FireSeconds = 8,
    # Input globals block. 0x536770..0x5367e0 covers the documented pilot-look,
    # throttle, steer and weapon_fire entries with room either side.
    [int64]$From = 0x536700,
    [int64]$To   = 0x536800
)
$ErrorActionPreference = 'Stop'

if (-not ('FireFind' -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class FireFind {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
}

$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { Write-Host "The game is not running." -ForegroundColor Red; exit 1 }
$h = [FireFind]::OpenProcess(0x38, $false, $proc.Id)
$len = [int]($To - $From)
$buf = New-Object byte[] $len

function Sample-Block {
    $n = 0
    if ([FireFind]::ReadProcessMemory($h, [IntPtr]$From, $buf, $len, [ref]$n)) { return $buf.Clone() }
    return $null
}

function Watch {
    param([string]$Label, [int]$Seconds)
    Write-Host ""
    Write-Host ("--- $Label for $Seconds s ---") -ForegroundColor Yellow
    $seen = @{}          # offset -> hashtable of distinct values
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $last = -1
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        $s = Sample-Block
        if ($s) {
            for ($o = 0; $o -lt $len; $o++) {
                if (-not $seen.ContainsKey($o)) { $seen[$o] = @{} }
                $seen[$o][$s[$o]] = $true
            }
        }
        $el = [int]$sw.Elapsed.TotalSeconds
        if ($el -ne $last) { $last = $el; Write-Host ("`r    {0}s left " -f ($Seconds - $el)) -NoNewline }
        Start-Sleep -Milliseconds 15
    }
    Write-Host ""
    # offsets that took MORE THAN ONE distinct value = they moved
    $moved = @{}
    foreach ($o in $seen.Keys) { if ($seen[$o].Count -gt 1) { $moved[$o] = $seen[$o].Keys } }
    return $moved
}

Write-Host ("watching 0x{0:X6}..0x{1:X6} in pid {2}" -f $From, $To, $proc.Id) -ForegroundColor Cyan
Write-Host ""
Write-Host "PHASE 1: hands OFF. Do not steer, drive or fire." -ForegroundColor Yellow
Write-Host "Press Enter when ready..." -ForegroundColor Yellow
[void](Read-Host)
$base = Watch "BASELINE - hands off" $BaselineSeconds

Write-Host ""
Write-Host "PHASE 2: FIRE REPEATEDLY. Do NOT steer and do NOT accelerate." -ForegroundColor Yellow
Write-Host "Press Enter when ready..." -ForegroundColor Yellow
[void](Read-Host)
$fire = Watch "FIRING" $FireSeconds

# Anything that moved in the baseline is ambient (timers, animation, AI) and is
# not a fire flag no matter how it behaves later.
$candidates = @()
foreach ($o in ($fire.Keys | Sort-Object)) {
    if ($base.ContainsKey($o)) { continue }
    $vals = @($fire[$o] | Sort-Object)
    $candidates += [pscustomobject]@{
        Addr   = ('0x{0:X6}' -f ($From + $o))
        Offset = $o
        Values = ($vals -join ',')
        Distinct = $vals.Count
    }
}

Write-Host ""
Write-Host "=== changed while FIRING but not while idle ===" -ForegroundColor Green
if (-not $candidates.Count) {
    Write-Host "  NOTHING. Either the trigger was not pulled, or the flag lives" -ForegroundColor Red
    Write-Host "  outside this range. Try a wider window:" -ForegroundColor Red
    Write-Host "     ffb-find-fire.ps1 -From 0x536000 -To 0x537000" -ForegroundColor Yellow
} else {
    $candidates | Format-Table Addr, Values, Distinct -AutoSize | Out-String | Write-Host
    Write-Host "READING THIS:" -ForegroundColor Gray
    Write-Host "  A weapon-fire flag should take exactly TWO values (0 and something)," -ForegroundColor Gray
    Write-Host "  and 0x5367db is the documented candidate - see whether it is listed." -ForegroundColor Gray
    Write-Host "  A byte cycling through many values is more likely an animation or" -ForegroundColor Gray
    Write-Host "  cooldown counter, which is also usable but behaves differently." -ForegroundColor Gray
    $doc = $candidates | Where-Object { $_.Addr -eq '0x5367DB' }
    Write-Host ""
    if ($doc) {
        Write-Host ("  0x5367DB DID move (values $($doc.Values)) - the documented address is good.") -ForegroundColor Green
    } else {
        Write-Host "  0x5367DB did NOT move. The documented address is wrong or is not" -ForegroundColor Yellow
        Write-Host "  the input path this weapon uses - prefer whatever is listed above." -ForegroundColor Yellow
    }
}

$out = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'ffb-fire-candidates.txt'
$candidates | Format-Table -AutoSize | Out-String | Set-Content -Path $out -Encoding ASCII
Write-Host ""
Write-Host "-> $out" -ForegroundColor Cyan
Write-Host ""
Write-Host "Then set the address in ffb-calib.json as TEL_FIRE_ADDR (decimal or 0x hex)" -ForegroundColor Cyan
Write-Host "and the weapon channel will use it. Until then that channel stays silent." -ForegroundColor Cyan
[void][FireFind]::CloseHandle($h)
