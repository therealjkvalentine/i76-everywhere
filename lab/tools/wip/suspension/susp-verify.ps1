<#
  susp-verify.ps1 - the decisive frame-coupling test for wheel-struct field 0x13C.
  If the per-frame spring impulse is applied 3x as often at 60fps, then 60fps with 0x13C scaled
  by 1/3 should reproduce 20fps-stock body motion. Robust oracle: 10s drive holding W on the
  desert, report roll stddev (deg) and roll direction-reversals/sec over frame-advanced samples.
  Field re-poked every loop so a rewrite can't wash it out.
  Conditions: 20fps stock; 60fps stock; 60fps x0.333; 60fps x0.577 (=1/sqrt3).
#>
$ErrorActionPreference = 'Stop'
$lab = "C:\Users\james\i76-uncap-lab"
. "$lab\autotest\lib\focuslib.ps1"; . "$lab\autotest\lib\inputlib.ps1"
. "$lab\autotest\lib\memlib.ps1";   . "$lab\autotest\lib\uiclick.ps1"
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class VP3 { [DllImport("kernel32.dll",SetLastError=true)] public static extern bool VirtualProtectEx(IntPtr h,IntPtr a,UIntPtr s,uint p,out uint o); }
"@ -ErrorAction SilentlyContinue
$OFF = 0x13C

function Set-Rate([int]$fps){ $on="$lab\game\I76PATCH.DLL"; $off="$on.disabled"
    if ($fps -le 30){ if(-not(Test-Path $on)){Rename-Item $off 'I76PATCH.DLL'} } else { if(Test-Path $on){Rename-Item $on 'I76PATCH.DLL.disabled'} } }
function Enter {
    $entered=$false
    for ($try=1; $try -le 4 -and -not $entered; $try++){
        Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue; Start-Sleep -Seconds 3
        Start-Process -FilePath "$lab\game\i76.exe" -ArgumentList '-glide' -WorkingDirectory "$lab\game"; Start-Sleep -Seconds 12
        $p=Get-GamePid; if(-not $p){continue}; if(-not(Ensure-GameFocus $p)){continue}
        for($i=0;$i -lt 5;$i++){Ensure-GameFocus $p|Out-Null;Send-Key $VK.ESC;Start-Sleep -Milliseconds 250;Send-Key $VK.ENTER;Start-Sleep -Milliseconds 700}
        Click-Ui 218 310 1800; Click-Ui 113 351 2500; Start-Sleep -Seconds 5
        $c=Mem-Open; for($i=0;$i -lt 20;$i++){ if(Mem-InMission $c){$entered=$true;break}; Start-Sleep -Seconds 1 }; Mem-Close $c
    }
    return $entered
}
function Acquire($ctx,$p){ $acq=$false;$dl=(Get-Date).AddSeconds(150);$t=0
    while(-not $acq -and (Get-Date) -lt $dl){ if(-not(Ensure-GameFocus $p)){Start-Sleep -Milliseconds 400;continue}
        Key-Down $VK.W;Start-Sleep -Milliseconds 70;Key-Up $VK.W;Start-Sleep -Milliseconds 90;$t++
        if($t%8 -eq 0 -and ((Mem-Player $ctx).Speed) -gt 5){$acq=$true} }
    return $acq }
function Poke($ctx,$wheels,$vals){ for($i=0;$i -lt 4;$i++){ $a=$wheels[$i]+$OFF;$o=0
        [void][VP3]::VirtualProtectEx($ctx.H,[IntPtr]$a,[UIntPtr]::new(4),0x40,[ref]$o); Mem-WriteF32 $ctx $a $vals[$i]
        $d=0;[void][VP3]::VirtualProtectEx($ctx.H,[IntPtr]$a,[UIntPtr]::new(4),$o,[ref]$d) } }
function DriveMeasure($ctx,$p,$wheels,$scaledVals,[double]$wantSamples){
    # Metric: roll direction-reversals per METRE (bumps/m is terrain, oscillation/bump is the
    # physics we want; dividing by distance cancels the speed confound that wrecked rev/sec).
    # Also roll_sd. Only samples with 12<=v<=45 on a frame advance count. distance integrated
    # from speed*wall_dt across valid stretches; stalls break the chain (no bridging).
    $rolls=@(); $prevR=$null;$prevF=$null; $revs=0; $lastSign=0
    $dist=0.0; $lastT=$null; $wall=(Get-Date).AddSeconds(45)
    while($rolls.Count -lt $wantSamples -and (Get-Date) -lt $wall){
        Ensure-GameFocus $p|Out-Null; Key-Down $VK.W
        if($scaledVals){ Poke $ctx $wheels $scaledVals }
        $e=Mem-EyeAngles $ctx; $fr=Mem-I32 $ctx 0x5A7E1C; $v=(Mem-Player $ctx).Speed; $now=Get-Date
        if($v -ge 12 -and $v -le 45 -and $null -ne $e -and $fr -ne $prevF){
            $rolls+=$e.Roll
            if($null -ne $lastT){ $dist += $v * ($now-$lastT).TotalSeconds }
            if($null -ne $prevR){ $d=$e.Roll-$prevR; while($d -gt 180){$d-=360}; while($d -lt -180){$d+=360}
                $s=[math]::Sign($d); if($s -ne 0 -and $lastSign -ne 0 -and $s -ne $lastSign){$revs++}; if($s -ne 0){$lastSign=$s} }
            $prevR=$e.Roll; $prevF=$fr; $lastT=$now
        } else { $lastT=$null; $prevR=$null }
        Start-Sleep -Milliseconds 8
    }
    Key-Up $VK.W
    if($rolls.Count -lt 20 -or $dist -lt 40){ return @{sd=-1;rpm=-1;v=(Mem-Player $ctx).Speed;n=$rolls.Count;dist=[math]::Round($dist)} }
    $m=($rolls|Measure-Object -Average).Average
    $sd=[math]::Sqrt((($rolls|ForEach-Object{($_-$m)*($_-$m)})|Measure-Object -Sum).Sum/$rolls.Count)
    return @{ sd=$sd; rpm=($revs/$dist); v=(Mem-Player $ctx).Speed; n=$rolls.Count; dist=[math]::Round($dist) }
}


$results=@()
function Fmt($tag,$r){ "{0,-20}: reversals/m={1,7:0.000}  roll_sd={2:0.000}  v={3:0.0}  dist={4}m  n={5}" -f $tag,$r.rpm,$r.sd,$r.v,$r.dist,$r.n }
# --- 20 fps stock ---
Set-Rate 20
if (Enter) { $p=Get-GamePid; $ctx=Mem-Open -Write
    if (Acquire $ctx $p) { $r=DriveMeasure $ctx $p $null $null 300; $results += (Fmt '20fps stock' $r) }
    Mem-Close $ctx }
# --- 60 fps: stock twice (noise floor), then x0.333 ---
Set-Rate 60
if (Enter) { $p=Get-GamePid; $ctx=Mem-Open -Write
    if (Acquire $ctx $p) {
        $ent=Mem-PlayerEntity $ctx
        $wheels=@(0x3A8,0x3AC,0x3B8,0x3BC)|ForEach-Object{ Mem-I32 $ctx ($ent+$_) }
        $orig=$wheels|ForEach-Object{ Mem-F32 $ctx ($_+$OFF) }
        $r=DriveMeasure $ctx $p $wheels $null 300;               $results += (Fmt '60fps stock A' $r)
        $r=DriveMeasure $ctx $p $wheels $null 300;               $results += (Fmt '60fps stock B' $r)
        $sv=@(0,1,2,3)|ForEach-Object{ [single]($orig[$_]*0.3333) }
        Poke $ctx $wheels $sv; Start-Sleep -Milliseconds 500
        $r=DriveMeasure $ctx $p $wheels $sv 300;                 $results += (Fmt '60fps 0x13C x0.333' $r)
        Poke $ctx $wheels $orig
    }
    Mem-Close $ctx }

Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Write-Host "===== RESULTS ====="
$results | ForEach-Object { Write-Host $_ }
$results | Set-Content "$lab\captures\suspension\susp-verify.txt"
