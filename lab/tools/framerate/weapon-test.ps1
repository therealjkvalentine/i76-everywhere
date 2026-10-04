<#
  weapon-test.ps1 — is the weapon FIRE RATE frame-coupled?

  Community reports say weapons misbehave at high FPS (flamethrower won't extend, mortar range
  collapses). The measurable core of that is emission cadence: if a weapon emits once per FRAME
  rather than on a timer, then at 60 Hz it fires 3x as fast and drains ammo 3x as fast, which
  also shortens sustained-effect weapons.

  Measures rounds/second by watching the ammo counter while holding fire.

  Ammo lives in the vehicle-LOGIC object: logic = [player_entity + 0x108], weapon pointer
  array at logic + 0xa71c, ammo is an int32 countdown inside each weapon object.
#>
param([int]$Seconds = 6, [string]$Label = 'weap')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }

$ent   = Mem-PlayerEntity $ctx
$logic = Mem-I32 $ctx ($ent + 0x108)
Write-Host ("entity=0x{0:X} logic=0x{1:X}" -f $ent, $logic)

# Find ammo candidates: int32s in the weapon-pointer region that look like a round count and
# DECREASE while firing. Scan the weapon array region and snapshot before/after.
$region = @()
for ($o = 0xa700; $o -lt 0xa800; $o += 4) { $region += ,@($o, (Mem-I32 $ctx ($logic + $o))) }
$ptrs = @()
for ($i = 0; $i -lt 8; $i++) {
    $p = Mem-I32 $ctx ($logic + 0xa71c + $i * 4)
    if ($p -gt 0x400000 -and $p -lt 0x7FFFFFFF) { $ptrs += $p }
}
Write-Host ("weapon pointers: {0}" -f ($ptrs.Count))
$before = @{}
foreach ($p in $ptrs) { for ($o = 0; $o -lt 0x60; $o += 4) { $before["$p-$o"] = Mem-I32 $ctx ($p + $o) } }

$f0 = (Mem-Player $ctx).Frame
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $Seconds) { Send-Key $VK.ENTER 40; Start-Sleep -Milliseconds 30 }
$real = $sw.Elapsed.TotalSeconds
$f1 = (Mem-Player $ctx).Frame
$frames = $f1 - $f0

$drops = @()
foreach ($p in $ptrs) {
    for ($o = 0; $o -lt 0x60; $o += 4) {
        $b = $before["$p-$o"]; $a = Mem-I32 $ctx ($p + $o)
        if ($b -gt 0 -and $a -lt $b -and ($b - $a) -lt 100000) {
            $drops += [pscustomobject]@{ Ptr = ('0x{0:X}' -f $p); Off = ('+0x{0:X}' -f $o); Before = $b; After = $a; Fired = ($b - $a) }
        }
    }
}
Mem-Close $ctx
Write-Host ("{0}: {1:N1} fps over {2:N2}s ({3} frames)" -f $Label, ($frames / $real), $real, $frames) -ForegroundColor Cyan
if ($drops.Count -eq 0) { Write-Host "  no counter decreased - weapon may not have fired (out of ammo, or SPACE not bound)" -ForegroundColor Yellow }
foreach ($d in $drops) {
    Write-Host ("  {0}{1}: {2} -> {3}  fired {4}   = {5:N2}/sec  |  {6:N4}/frame" -f `
        $d.Ptr, $d.Off, $d.Before, $d.After, $d.Fired, ($d.Fired / $real), ($d.Fired / [math]::Max($frames,1)))
}
