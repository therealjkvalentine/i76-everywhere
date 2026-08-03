<#
  FFB recon - run on BOTH machines, diff the output.

  Force feedback works on one Windows box and not another. docs/FFB-LAPTOP-RECON.md
  records what is already settled by disassembly; this collects the machine-side
  facts in a fixed order so `fc` / `diff` on two runs shows the difference instead
  of two people reading two walls of text.

      powershell -ExecutionPolicy Bypass -File tools\ffb-recon.ps1 > recon-<machine>.txt

  Connect the wheel BEFORE running. Items marked [WHEEL] are blank without it, and
  a blank there is not a finding.

  Does NOT change anything. Recon only.

  NOTE: do NOT open the Thrustmaster control panel to answer any of this. It takes
  the DirectInput device exclusively, which is itself a cause of "FFB stopped
  working" (docs/WHEEL-T300.md). Everything below is read from the registry/PnP.
#>
$ErrorActionPreference = 'Continue'
# NOTE: helper names must not collide with PowerShell ALIASES. `H` is Get-History
# and `KV` was fine, but H silently turned every heading into a Get-History call
# that errored to stderr while the data still printed - looked like a broken script.
function Sect($t) { Write-Output ""; Write-Output ("=" * 72); Write-Output "== $t"; Write-Output ("=" * 72) }
function Item($k, $v) { Write-Output ("  {0,-26} {1}" -f $k, $v) }

Sect "MACHINE"
Item "computer"        $env:COMPUTERNAME
Item "OS"              (Get-CimInstance Win32_OperatingSystem).Caption
Item "build"           ("{0} UBR {1} ({2})" -f (Get-CimInstance Win32_OperatingSystem).BuildNumber,
                       (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR,
                       (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').DisplayVersion)

Sect "VIRTUAL JOYSTICKS  (change DirectInput enumeration ORDER - prime suspect)"
$virt = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
    $_.FriendlyName -match '(?i)vJoy|3Dconnexion|KMJ|x360ce|ViGEm|Nefarius|virtual (joystick|gamepad)|Emulator' }
if ($virt) {
    foreach ($v in $virt) {
        Item $v.Status ("{0}  [{1}]" -f $v.FriendlyName, $v.InstanceId)
        # A BUS with no children enumerates nothing. vJoy/KMJ present as real joysticks.
        $kids = (Get-PnpDeviceProperty -InstanceId $v.InstanceId -KeyName 'DEVPKEY_Device_Children' -ErrorAction SilentlyContinue).Data
        if ($kids) { foreach ($k in $kids) { Item "   child" $k } } else { Item "   children" "none (bus only - enumerates no joystick)" }
    }
} else { Item "none" "no vJoy / KMJ / x360ce / ViGEm" }

Sect "[WHEEL] THRUSTMASTER DEVICE + DRIVER"
$tm = Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { $_.DeviceID -match 'VID_044F' }
if ($tm) { foreach ($d in $tm) { Item $d.Status ("{0}  [{1}]" -f $d.Name, $d.DeviceID) } }
else { Item "NOT CONNECTED" "plug the wheel in and re-run - B66E=driven, B65D=generic pre-init" }
Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue | Where-Object { $_.DeviceID -match '044F' } |
    ForEach-Object { Item "driver" ("{0} | {1} | v{2}" -f $_.DeviceName, $_.Manufacturer, $_.DriverVersion) }

Sect "[WHEEL] WINMM ENUMERATION  (joyGetDevCaps 0-15 - what the engine reads)"
Add-Type @"
using System;using System.Runtime.InteropServices;using System.Text;
[StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)]
public struct JOYCAPSW{
 public ushort wMid,wPid;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)]public string szPname;
 public uint wXmin,wXmax,wYmin,wYmax,wZmin,wZmax,wNumButtons,wPeriodMin,wPeriodMax;
 public uint wRmin,wRmax,wUmin,wUmax,wVmin,wVmax,wCaps,wMaxAxes,wNumAxes,wMaxButtons;
 [MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)]public string szRegKey;
 [MarshalAs(UnmanagedType.ByValTStr,SizeConst=260)]public string szOEMVxD;}
public class WMM{
 [DllImport("winmm.dll")] public static extern uint joyGetNumDevs();
 [DllImport("winmm.dll",CharSet=CharSet.Unicode)] public static extern uint joyGetDevCapsW(uint id,ref JOYCAPSW c,uint sz);}
"@ -ErrorAction SilentlyContinue
Item "joyGetNumDevs (slots)" ([WMM]::joyGetNumDevs())
$found = 0
for ($i = 0; $i -lt 16; $i++) {
    $c = New-Object JOYCAPSW
    if ([WMM]::joyGetDevCapsW($i, [ref]$c, [Runtime.InteropServices.Marshal]::SizeOf($c)) -eq 0) {
        $found++
        Item ("slot $i (joystick$($i+1))") ("{0}  VID={1:X4} PID={2:X4}  axes={3} buttons={4}" -f $c.szPname,$c.wMid,$c.wPid,$c.wNumAxes,$c.wNumButtons)
    }
}
if (-not $found) { Item "(none)" "no winmm joystick present" }

Sect "JOYSTICK IDs  (which devices claim a winmm slot)"
$oem = 'HKCU:\System\CurrentControlSet\Control\MediaProperties\PrivateProperties\Joystick\OEM'
if (Test-Path $oem) {
    Get-ChildItem $oem | ForEach-Object {
        $n = (Get-ItemProperty $_.PSPath).OEMName
        if ($n) { Item $_.PSChildName $n }
    }
}

Sect "MediaResources\Joystick  (DirectInput's 'current joystick' - ABSENT is normal)"
$mr = 'HKCU:\System\CurrentControlSet\Control\MediaResources\Joystick'
if (Test-Path $mr) {
    Get-ChildItem $mr -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        Item "key" ($_.Name -replace '.*\\MediaResources\\Joystick\\','')
        foreach ($v in (Get-Item $_.PSPath).Property) {
            $val = (Get-ItemProperty $_.PSPath).$v
            if ($val -is [byte[]]) { $val = ($val | ForEach-Object { $_.ToString('x2') }) -join ' ' }
            Item "   $v" $val
        }
    }
} else { Item "ABSENT" "no CurrentJoystickSettings - DI uses default enumeration" }

Sect "DirectInput per-device store (HKLM)"
$di = 'HKLM:\SYSTEM\CurrentControlSet\Control\MediaProperties\PrivateProperties\DirectInput'
if (Test-Path $di) { Get-ChildItem $di | ForEach-Object { Item "device" $_.PSChildName } } else { Item "ABSENT" "" }

Sect "GAME FILES"
$gd = @("C:\Games\Interstate 76", "C:\Games\Interstate 76 Nitro Pack") | Where-Object { Test-Path (Join-Path $_ 'i76.exe') } | Select-Object -First 1
if (-not $gd) { $gd = "C:\Games\Interstate 76" }
Item "game dir" $gd
foreach ($f in 'i76.exe','I7_SFRCE.DLL') {
    $p = Join-Path $gd $f
    if (Test-Path $p) { Item $f ("MD5={0} size={1}" -f (Get-FileHash $p -Algorithm MD5).Hash.ToLower(), (Get-Item $p).Length) }
    else { Item $f "MISSING" }
}
Item "force\*.frc" ("{0} files" -f @(Get-ChildItem (Join-Path $gd 'force') -Filter *.FRC -ErrorAction SilentlyContinue).Count)
$gogPath = $null
foreach ($k in 'HKLM:\SOFTWARE\WOW6432Node\GOG.com\Games','HKLM:\SOFTWARE\GOG.com\Games') {
    if (Test-Path $k) { Get-ChildItem $k | ForEach-Object {
        $e = Get-ItemProperty $_.PSPath
        if ($e.gameName -match 'Interstate') { $gogPath = $e.path; Item "GOG entry" ("{0} -> {1}" -f $e.gameName, $e.path) } } }
}
if (-not $gogPath) { Item "GOG entry" "none (portable/zip copy?)" }

Sect "ACTIVISION REGISTRY"
foreach ($b in 'HKLM:\SOFTWARE\WOW6432Node\ACTIVISION','HKLM:\SOFTWARE\ACTIVISION') {
    if (Test-Path $b) {
        Get-ChildItem $b -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
            $props = (Get-Item $_.PSPath).Property
            Item "key" ($_.Name -replace '.*\\ACTIVISION\\','')
            foreach ($v in $props) { Item "   $v" (Get-ItemProperty $_.PSPath).$v }
        }
    } else { Item "$b" "absent" }
}

Sect "CONFIG"
$im = Join-Path $gd 'input.map'
if (Test-Path $im) {
    $t = Get-Content $im -Raw
    foreach ($sink in 'throttle','steer') {
        $m = [regex]::Match($t, "(?m)^$sink \{[^}]*\}")
        if ($m.Success) { $m.Value -split "`n" | ForEach-Object { Item "" $_.TrimEnd() } }
    }
}
$dv = Join-Path $gd 'dgVoodoo.conf'
if (Test-Path $dv) {
    Select-String -Path $dv -Pattern '^\s*(FPSLimit|FullScreenMode|ScalingMode|ForceVerticalSync)\s*=' |
        ForEach-Object { Item "" $_.Line.Trim() }
}

Sect "PROCESSES THAT COULD HOLD THE DEVICE"
$hold = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -match '(?i)tmJoycpl|TMController|Thrustmaster|FirmwareUpd|vJoyConf|x360ce|DS4|Steam$' }
if ($hold) { foreach ($p in $hold) { Item "RUNNING" ("{0} (pid {1}) - can take DirectInput exclusively" -f $p.ProcessName,$p.Id) } }
else { Item "none" "nothing obvious holding the wheel" }

Write-Output ""
Write-Output "Recon complete. Run tools\check-ffb.ps1 WHILE IN A MISSION for the engine's own verdict."
