<#
  wheel-field-sweep.ps1 - confirm the damper field by poking wheel-struct offsets live.
  Drives the bumpy desert at 60fps holding W (focus-guarded), measures roll-activity (deg/s of
  |d roll| per frame-advanced sample), and for each candidate offset does baseline / poke x Mult
  on all 4 wheels / revert, with verified writes. A field that CALMS the buzz when scaled up is
  a damping term; one that AMPLIFIES it when scaled up is stiffness.
#>
param([double]$Mult = 3.0, [string]$OutDir = "$PSScriptRoot\..\..\..\captures\suspension")
$ErrorActionPreference = 'Stop'
$lab = "C:\Users\james\i76-uncap-lab"
. "$lab\autotest\lib\focuslib.ps1"; . "$lab\autotest\lib\inputlib.ps1"
. "$lab\autotest\lib\memlib.ps1";   . "$lab\autotest\lib\uiclick.ps1"
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class VP2 { [DllImport("kernel32.dll",SetLastError=true)] public static extern bool VirtualProtectEx(IntPtr h,IntPtr a,UIntPtr s,uint p,out uint o); }
"@ -ErrorAction SilentlyContinue

$on = "$lab\game\I76PATCH.DLL"; if (Test-Path $on) { Rename-Item $on "$on.disabled" }
$entered=$false
for ($try=1; $try -le 4 -and -not $entered; $try++) {
    Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue; Start-Sleep -Seconds 3
    Start-Process -FilePath "$lab\game\i76.exe" -ArgumentList '-glide' -WorkingDirectory "$lab\game"; Start-Sleep -Seconds 12
    $p = Get-GamePid; if (-not $p) { continue }
    if (-not (Ensure-GameFocus $p)) { continue }
    for ($i=0; $i -lt 5; $i++) { Ensure-GameFocus $p|Out-Null; Send-Key $VK.ESC; Start-Sleep -Milliseconds 250; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 700 }
    Click-Ui 218 310 1800; Click-Ui 113 351 2500; Start-Sleep -Seconds 5
    $ctx = Mem-Open
    for ($i=0;$i -lt 20;$i++){ if (Mem-InMission $ctx){$entered=$true;break}; Start-Sleep -Seconds 1 }
    if (-not $entered) { Mem-Close $ctx }
}
if (-not $entered) { Write-Host "ENTRY FAILED"; exit 1 }
$p = Get-GamePid
$ctx = Mem-Open -Write
# acquire control
$acq=$false; $dl=(Get-Date).AddSeconds(150); $taps=0
while (-not $acq -and (Get-Date) -lt $dl) {
    if (-not (Ensure-GameFocus $p)) { Start-Sleep -Milliseconds 400; continue }
    Key-Down $VK.W; Start-Sleep -Milliseconds 70; Key-Up $VK.W; Start-Sleep -Milliseconds 90
    $taps++; if ($taps % 8 -eq 0 -and ((Mem-Player $ctx).Speed) -gt 5) { $acq=$true }
}
if (-not $acq) { Write-Host "NO CONTROL"; exit 1 }
$ent = Mem-PlayerEntity $ctx
$wheels = @(0x3A8,0x3AC,0x3B8,0x3BC) | ForEach-Object { Mem-I32 $ctx ($ent + $_) }
Write-Host ("wheels: {0}" -f (($wheels | ForEach-Object { '0x{0:X}' -f $_ }) -join ' '))

function PokeAll([int]$off,[single]$v){
    foreach ($w in $wheels) {
        $a = $w + $off; $o=0
        [void][VP2]::VirtualProtectEx($ctx.H,[IntPtr]$a,[UIntPtr]::new(4),0x40,[ref]$o)
        Mem-WriteF32 $ctx $a $v
        $d=0; [void][VP2]::VirtualProtectEx($ctx.H,[IntPtr]$a,[UIntPtr]::new(4),$o,[ref]$d)
    }
}
function ReadAll([int]$off){ $wheels | ForEach-Object { Mem-F32 $ctx ($_ + $off) } }

function RollAct([double]$sec){
    Ensure-GameFocus $p | Out-Null
    Key-Down $VK.W
    $prevR=$null; $prevF=$null; $acc=@(); $end=(Get-Date).AddSeconds($sec)
    while ((Get-Date) -lt $end) {
        $e = Mem-EyeAngles $ctx; $fr = Mem-I32 $ctx 0x5A7E1C
        if ($null -ne $e -and $null -ne $prevR -and $fr -ne $prevF) {
            $d = $e.Roll - $prevR; while($d -gt 180){$d-=360}; while($d -lt -180){$d+=360}
            $acc += [math]::Abs($d)
        }
        if ($null -ne $e) { $prevR=$e.Roll; $prevF=$fr }
        Start-Sleep -Milliseconds 8
    }
    Key-Up $VK.W
    if ($acc.Count -gt 5) { ($acc | Measure-Object -Average).Average } else { -1 }
}

# candidate STATIC offsets from wheel-probe (real non-zero values); include the doubles' low+high dwords
$cands = @(0x40,0x44,0x50,0x54,0x108,0x138,0x13C,0xF8,0x100)
New-Item -ItemType Directory -Force $OutDir | Out-Null
$rows = @('off,stock_w0,base,poked,reverted,verdict')
Write-Host ("candidate sweep, poke x{0}:" -f $Mult)
Write-Host ("{0,-7} {1,-12} {2,-8} {3,-8} {4,-8}" -f 'off','stock','base','poked','revert')
foreach ($off in $cands) {
    $p2 = Get-Process i76 -EA SilentlyContinue; if (-not $p2) { Write-Host "DIED"; break }
    $stock = (ReadAll $off)[0]
    if ([double]::IsNaN($stock) -or [math]::Abs($stock) -lt 1e-6 -or [math]::Abs($stock) -gt 1e6) {
        Write-Host ("0x{0:X3}  skip (value {1})" -f $off,$stock); continue
    }
    $orig = ReadAll $off
    $base = RollAct 2.2
    for ($i=0;$i -lt 4;$i++){ PokeAll $off ([single]($orig[$i]*$Mult)) }  # per-wheel keep sign/scale
    Start-Sleep -Milliseconds 400
    $poked = RollAct 2.2
    for ($i=0;$i -lt 4;$i++){ $a=$wheels[$i]+$off; $o=0; [void][VP2]::VirtualProtectEx($ctx.H,[IntPtr]$a,[UIntPtr]::new(4),0x40,[ref]$o); Mem-WriteF32 $ctx $a $orig[$i]; $d=0; [void][VP2]::VirtualProtectEx($ctx.H,[IntPtr]$a,[UIntPtr]::new(4),$o,[ref]$d) }
    Start-Sleep -Milliseconds 400
    $rev = RollAct 2.0
    $chg = if ($base -gt 0) { ($poked-$base)/$base } else { 0 }
    $verdict = if ([math]::Abs($chg) -gt 0.25 -and [math]::Abs($rev-$base) -lt [math]::Abs($poked-$base)) { if ($chg -lt 0) {'CALMS <<<'} else {'amplifies'} } else { 'no effect' }
    $rows += ('0x{0:X},{1},{2:0.000},{3:0.000},{4:0.000},{5}' -f $off,$stock,$base,$poked,$rev,$verdict)
    Write-Host ("0x{0,-4:X3} {1,-12:G6} {2,-8:0.000} {3,-8:0.000} {4,-8:0.000} {5}" -f $off,$stock,$base,$poked,$rev,$verdict)
}
$rows | Set-Content (Join-Path $OutDir 'wheel-field-sweep.csv')
Write-Host "done"
Mem-Close $ctx
Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
