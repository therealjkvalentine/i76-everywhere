<#
  FfbCore - talk force feedback to a DirectInput wheel from PowerShell.

  WHY THIS EXISTS AND WHY IT IS SHAPED LIKE THIS
  Interstate '76's own FFB is a closed 1997 system: on fixed events it plays a
  pre-authored effect from force\*.frc. It has no concept of slip, load or road
  texture, because that vocabulary postdates it. To make the wheel communicative
  we have to synthesise forces ourselves from game state.

  Windows has exactly one API for that: DirectInput. There is no managed wrapper
  available offline (SharpDX is a NuGet package), and no C compiler on this
  machine - so this drives the COM interfaces by hand through their vtables,
  compiled at runtime by Add-Type. Ugly, but it needs nothing installed.

  ONE HARD CONSTRAINT: FFB requires EXCLUSIVE acquisition. The game takes it at
  startup, so while the game holds it we cannot. That is why the interposer is
  flag-optional - you get the engine's weapon effects OR our synthesised feel,
  not both. See tools/ffb/README.md.

  Usage (dot-source, then call):
      . tools\ffb\FfbCore.ps1
      $d = Ffb-Open                 # find + acquire the first FFB device
      Ffb-Constant $d 6000          # push right (-10000..10000)
      Ffb-Constant $d -6000         # push left
      Ffb-Rumble   $d 5000 30       # periodic buzz: magnitude, period ms
      Ffb-Stop     $d
      Ffb-Close    $d
#>

Add-Type -ErrorAction SilentlyContinue @"
using System;
using System.Runtime.InteropServices;

public static class DI {
    // ---- DirectInput8 entry point -------------------------------------------
    [DllImport("dinput8.dll", CharSet=CharSet.Ansi)]
    public static extern int DirectInput8Create(IntPtr hinst, uint ver, ref Guid riid, out IntPtr ppv, IntPtr punk);
    [DllImport("kernel32.dll")] public static extern IntPtr GetModuleHandle(string n);
    // GetModuleHandle(null) comes back NULL from PowerShell, and
    // DirectInput8Create rejects a NULL hinst with E_INVALIDARG (0x80070057) -
    // which cost a debugging round. LoadLibrary gives a handle that is always
    // valid; DirectInput only wants *some* live module, not specifically ours.
    [DllImport("kernel32.dll", CharSet=CharSet.Ansi)] public static extern IntPtr LoadLibraryA(string n);
    // EXCLUSIVE cooperative level needs a REAL window owned by this process -
    // a NULL hwnd returns E_HANDLE (0x80070006) even with DISCL_BACKGROUND.
    [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();

    public const uint DIRECTINPUT_VERSION = 0x0800;
    // IID_IDirectInput8A
    public static Guid IID_IDirectInput8A = new Guid("BF798030-483A-4DA2-AA99-5D64ED369700");
    // GUID_ConstantForce / GUID_Sine  (dinput.h)
    public static Guid GUID_ConstantForce = new Guid("13541C20-8E33-11D0-9AD0-00A0C9A06E35");
    public static Guid GUID_Sine          = new Guid("13541C31-8E33-11D0-9AD0-00A0C9A06E35");

    public const uint DI8DEVCLASS_GAMECTRL = 4;
    public const uint DIEDFL_ATTACHEDONLY  = 0x00000001;
    public const uint DIEDFL_FORCEFEEDBACK = 0x00000100;
    public const uint DISCL_EXCLUSIVE      = 0x00000001;
    public const uint DISCL_BACKGROUND     = 0x00000008;
    public const uint DIEP_DIRECTION       = 0x00000040;
    public const uint DIEP_TYPESPECIFICPARAMS = 0x00000100;
    public const uint DIEP_START           = 0x20000000;
    public const uint DIEFF_CARTESIAN      = 0x00000010;
    public const uint DIEFF_OBJECTOFFSETS  = 0x00000002;
    public const int  DI_OK = 0;

    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Ansi)]
    public struct DIDEVICEINSTANCEA {
        public uint dwSize; public Guid guidInstance; public Guid guidProduct;
        public uint dwDevType;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=260)] public string tszInstanceName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=260)] public string tszProductName;
        public Guid guidFFDriver; public ushort wUsagePage; public ushort wUsage;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct DIOBJECTDATAFORMAT {
        public IntPtr pguid; public uint dwOfs; public uint dwType; public uint dwFlags;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct DIDATAFORMAT {
        public uint dwSize, dwObjSize, dwFlags, dwDataSize, dwNumObjs; public IntPtr rgodf;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct DIEFFECT {
        public uint dwSize, dwFlags, dwDuration, dwSamplePeriod, dwGain, dwTriggerButton, dwTriggerRepeatInterval;
        public uint cAxes; public IntPtr rgdwAxes; public IntPtr rglDirection;
        public IntPtr lpEnvelope; public uint cbTypeSpecificParams; public IntPtr lpvTypeSpecificParams;
        public uint dwStartDelay;
    }
    [StructLayout(LayoutKind.Sequential)] public struct DICONSTANTFORCE { public int lMagnitude; }
    [StructLayout(LayoutKind.Sequential)] public struct DIPERIODIC {
        public uint dwMagnitude; public int lOffset; public uint dwPhase; public uint dwPeriod;
    }

    // ---- vtable plumbing -----------------------------------------------------
    // Manual because there is no managed DirectInput. Slot numbers are from
    // dinput.h's interface declaration order; getting one wrong is an instant
    // access violation, so they are named rather than inlined.
    public static IntPtr Vtbl(IntPtr obj, int slot) {
        IntPtr vtbl = Marshal.ReadIntPtr(obj);
        return Marshal.ReadIntPtr(vtbl, slot * IntPtr.Size);
    }
    public delegate int EnumDevicesCallback(ref DIDEVICEINSTANCEA lpddi, IntPtr pvRef);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_EnumDevices(IntPtr self, uint devType, EnumDevicesCallback cb, IntPtr pvRef, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_CreateDevice(IntPtr self, ref Guid rguid, out IntPtr dev, IntPtr punk);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_SetDataFormat(IntPtr self, ref DIDATAFORMAT df);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_SetCooperativeLevel(IntPtr self, IntPtr hwnd, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_Acquire(IntPtr self);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_Unacquire(IntPtr self);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_CreateEffect(IntPtr self, ref Guid rguid, ref DIEFFECT eff, out IntPtr ppeff, IntPtr punk);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_SetParameters(IntPtr self, ref DIEFFECT eff, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_Start(IntPtr self, uint iterations, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_Stop(IntPtr self);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate int D_Release(IntPtr self);

    // IDirectInput8: 3=CreateDevice 4=EnumDevices
    public const int DI8_CreateDevice = 3, DI8_EnumDevices = 4;
    // IDirectInputDevice8: 7=Acquire 8=Unacquire 11=SetDataFormat
    // 13=SetCooperativeLevel 18=CreateEffect
    public const int DEV_Acquire = 7, DEV_Unacquire = 8, DEV_SetDataFormat = 11,
                     DEV_SetCooperativeLevel = 13, DEV_CreateEffect = 18;
    // IDirectInputEffect: 6=SetParameters 7=Start 8=Stop
    public const int EFF_SetParameters = 6, EFF_Start = 7, EFF_Stop = 8;
    public const int IUnk_Release = 2;

    public static T Fn<T>(IntPtr obj, int slot) where T : class {
        return Marshal.GetDelegateForFunctionPointer(Vtbl(obj, slot), typeof(T)) as T;
    }
}
"@

# PowerShell 5.1 cannot call generic methods, so the vtable->delegate step lives
# here rather than as a generic helper on the C# side.
function Get-Fn {
    param([IntPtr]$Obj, [int]$Slot, [type]$Type)
    $fp = [DI]::Vtbl($Obj, $Slot)
    return [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer($fp, $Type)
}

# c_dfDIJoystick has to exist before Acquire will work. Rather than transcribe
# all 44 object entries, build the minimum viable format: the axes we care about
# in a DIJOYSTATE-shaped buffer. FFB only needs the format to be VALID, not
# complete - we never read device state through this object.
function New-JoystickDataFormat {
    $GUID_XAxis = [Guid]"A36D02E0-C9F3-11CF-BFC7-444553540000"
    $GUID_YAxis = [Guid]"A36D02E1-C9F3-11CF-BFC7-444553540000"
    $objs = @($GUID_XAxis, $GUID_YAxis)
    $odfSize = [Runtime.InteropServices.Marshal]::SizeOf([type][DI+DIOBJECTDATAFORMAT])
    $mem = [Runtime.InteropServices.Marshal]::AllocHGlobal($odfSize * $objs.Count)
    $guidMem = @()
    for ($i = 0; $i -lt $objs.Count; $i++) {
        $g = [Runtime.InteropServices.Marshal]::AllocHGlobal(16)
        [Runtime.InteropServices.Marshal]::Copy($objs[$i].ToByteArray(), 0, $g, 16)
        $guidMem += $g
        $o = New-Object DI+DIOBJECTDATAFORMAT
        $o.pguid   = $g
        $o.dwOfs   = [uint32]($i * 4)
        # DIDFT_AXIS (0x03) | DIDFT_ANYINSTANCE (0x00FFFF00). Getting the
        # instance mask wrong (0x0000FF00) makes SetDataFormat return
        # E_INVALIDARG with no other clue.
        $o.dwType  = 0x00000003 -bor 0x00FFFF00
        $o.dwFlags = 0
        [Runtime.InteropServices.Marshal]::StructureToPtr($o, [IntPtr]($mem.ToInt64() + $i * $odfSize), $false)
    }
    $df = New-Object DI+DIDATAFORMAT
    $df.dwSize     = [uint32][Runtime.InteropServices.Marshal]::SizeOf([type][DI+DIDATAFORMAT])
    $df.dwObjSize  = [uint32]$odfSize
    $df.dwFlags    = 1                       # DIDF_ABSAXIS
    $df.dwDataSize = [uint32](4 * $objs.Count)
    $df.dwNumObjs  = [uint32]$objs.Count
    $df.rgodf      = $mem
    return @{ Format = $df; Mem = $mem; Guids = $guidMem }
}

function Ffb-Open {
    param([string]$MatchName = "")
    $hinst = [DI]::LoadLibraryA("dinput8.dll")
    if ($hinst -eq [IntPtr]::Zero) { throw "could not obtain a module handle for DirectInput8Create" }
    $iid = [DI]::IID_IDirectInput8A
    $di = [IntPtr]::Zero
    $hr = [DI]::DirectInput8Create($hinst, [DI]::DIRECTINPUT_VERSION, [ref]$iid, [ref]$di, [IntPtr]::Zero)
    if ($hr -ne 0) { throw "DirectInput8Create failed 0x$('{0:X8}' -f $hr)" }

    # enumerate FORCE FEEDBACK capable game controllers only
    $found = New-Object System.Collections.ArrayList
    $cb = [DI+EnumDevicesCallback]{
        param([ref]$ddi, $pv)
        $null = $found.Add([pscustomobject]@{
            Name = $ddi.Value.tszProductName
            Guid = $ddi.Value.guidInstance
        })
        return 1   # DIENUM_CONTINUE
    }
    $enum = Get-Fn $di ([DI]::DI8_EnumDevices) ([DI+D_EnumDevices])
    $hr = $enum.Invoke($di, [DI]::DI8DEVCLASS_GAMECTRL, $cb, [IntPtr]::Zero,
                       ([DI]::DIEDFL_ATTACHEDONLY -bor [DI]::DIEDFL_FORCEFEEDBACK))
    if ($hr -ne 0) { throw "EnumDevices failed 0x$('{0:X8}' -f $hr)" }
    if ($found.Count -eq 0) { throw "No force-feedback device found (is the game holding it exclusively?)" }

    $pick = if ($MatchName) { $found | Where-Object { $_.Name -like "*$MatchName*" } | Select-Object -First 1 }
            else { $found[0] }
    if (-not $pick) { throw "No FFB device matching '$MatchName'. Found: $($found.Name -join ', ')" }

    $create = Get-Fn $di ([DI]::DI8_CreateDevice) ([DI+D_CreateDevice])
    $g = $pick.Guid
    $dev = [IntPtr]::Zero
    $hr = $create.Invoke($di, [ref]$g, [ref]$dev, [IntPtr]::Zero)
    if ($hr -ne 0) { throw "CreateDevice failed 0x$('{0:X8}' -f $hr)" }

    $dfInfo = New-JoystickDataFormat
    $df = $dfInfo.Format
    $sdf = Get-Fn $dev ([DI]::DEV_SetDataFormat) ([DI+D_SetDataFormat])
    $hr = $sdf.Invoke($dev, [ref]$df)
    if ($hr -ne 0) { throw "SetDataFormat failed 0x$('{0:X8}' -f $hr)" }

    # EXCLUSIVE is mandatory for FFB; BACKGROUND so we keep it without focus.
    # The hwnd must be a real, live window owned by THIS process. GetConsoleWindow
    # is not good enough - a child powershell may share or lack a console, and
    # Acquire then fails with ERROR_INVALID_WINDOW_HANDLE (0x80070578) even though
    # SetCooperativeLevel returned OK. A hidden WinForms window always works, and
    # is kept referenced on the returned object so the GC cannot destroy it.
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "i76-ffb"
    $form.ShowInTaskbar = $false
    $form.WindowState = 'Minimized'
    $form.FormBorderStyle = 'FixedToolWindow'
    $null = $form.Handle          # force window creation
    $hwnd = $form.Handle
    $scl = Get-Fn $dev ([DI]::DEV_SetCooperativeLevel) ([DI+D_SetCooperativeLevel])
    $hr = $scl.Invoke($dev, $hwnd, ([DI]::DISCL_EXCLUSIVE -bor [DI]::DISCL_BACKGROUND))
    if ($hr -ne 0) { throw "SetCooperativeLevel failed 0x$('{0:X8}' -f $hr)" }

    $acq = Get-Fn $dev ([DI]::DEV_Acquire) ([DI+D_Acquire])
    $hr = $acq.Invoke($dev)
    if ($hr -lt 0) { throw "Acquire failed 0x$('{0:X8}' -f $hr) - something else holds the device (the GAME?)" }

    return [pscustomobject]@{
        DI = $di; Dev = $dev; Name = $pick.Name; DfMem = $dfInfo.Mem; Guids = $dfInfo.Guids
        Form = $form          # MUST stay referenced - if the window dies, so does the acquisition
        Effects = @{}
    }
}

function New-Effect {
    # 4294967295 not 0xFFFFFFFF: PowerShell parses the hex literal as Int32 -1,
    # which will not coerce to UInt32 (INFINITE duration).
    param($D, [Guid]$Guid, [IntPtr]$TypeParams, [int]$TypeSize, [uint32]$Duration = 4294967295)
    $axes = [Runtime.InteropServices.Marshal]::AllocHGlobal(4)
    [Runtime.InteropServices.Marshal]::WriteInt32($axes, 0)          # object offset 0 = X
    $dir = [Runtime.InteropServices.Marshal]::AllocHGlobal(4)
    [Runtime.InteropServices.Marshal]::WriteInt32($dir, 0)
    $eff = New-Object DI+DIEFFECT
    $eff.dwSize                = [uint32][Runtime.InteropServices.Marshal]::SizeOf([type][DI+DIEFFECT])
    $eff.dwFlags               = ([DI]::DIEFF_CARTESIAN -bor [DI]::DIEFF_OBJECTOFFSETS)
    $eff.dwDuration            = $Duration
    $eff.dwSamplePeriod        = 0
    $eff.dwGain                = 10000
    $eff.dwTriggerButton       = 4294967295      # DIEB_NOTRIGGER (see the hex/Int32 note above)
    $eff.dwTriggerRepeatInterval = 0
    $eff.cAxes                 = 1
    $eff.rgdwAxes              = $axes
    $eff.rglDirection          = $dir
    $eff.lpEnvelope            = [IntPtr]::Zero
    $eff.cbTypeSpecificParams  = [uint32]$TypeSize
    $eff.lpvTypeSpecificParams = $TypeParams
    $eff.dwStartDelay          = 0
    $ce = Get-Fn $D.Dev ([DI]::DEV_CreateEffect) ([DI+D_CreateEffect])
    $g = $Guid
    $pe = [IntPtr]::Zero
    $hr = $ce.Invoke($D.Dev, [ref]$g, [ref]$eff, [ref]$pe, [IntPtr]::Zero)
    if ($hr -ne 0) { throw "CreateEffect failed 0x$('{0:X8}' -f $hr)" }
    return [pscustomobject]@{ Ptr = $pe; Eff = $eff; Axes = $axes; Dir = $dir; Type = $TypeParams }
}

# Returns the HRESULT from the device. 0 = applied.
#
# WHY THE RETURN VALUE MATTERS: an exclusive DirectInput acquisition can be taken
# away from us (DIERR_INPUTLOST 0x8007001E when another app grabs the device, or
# DIERR_NOTACQUIRED 0x8007000C after a focus change). This used to discard the
# HRESULT, so a lost device looked exactly like a working one - the loop kept
# happily "sending" force to nothing and the panel kept reporting numbers. Any
# negative HRESULT here means the caller should Ffb-Reacquire.
function Ffb-Constant {
    param($D, [int]$Magnitude)   # -10000 .. 10000 ; sign = direction
    if (-not $D.Effects.ContainsKey('constant')) {
        $tp = [Runtime.InteropServices.Marshal]::AllocHGlobal(4)
        [Runtime.InteropServices.Marshal]::WriteInt32($tp, $Magnitude)
        $e = New-Effect -D $D -Guid ([DI]::GUID_ConstantForce) -TypeParams $tp -TypeSize 4
        $D.Effects['constant'] = $e
        $start = Get-Fn $e.Ptr ([DI]::EFF_Start) ([DI+D_Start])
        $null = $start.Invoke($e.Ptr, 1, 0)
    } else {
        $e = $D.Effects['constant']
        [Runtime.InteropServices.Marshal]::WriteInt32($e.Type, $Magnitude)
        $sp = Get-Fn $e.Ptr ([DI]::EFF_SetParameters) ([DI+D_SetParameters])
        return $sp.Invoke($e.Ptr, [ref]$e.Eff, ([DI]::DIEP_TYPESPECIFICPARAMS -bor [DI]::DIEP_START))
    }
    return 0
}

function Ffb-Reacquire {
    <#
      Try to take the device back after losing it. Returns $true on success.

      Losing an exclusive acquisition is normal, not exceptional: alt-tabbing,
      another app opening the wheel, the Thrustmaster control panel being
      launched, or the game reacquiring on focus will all do it. So the loop
      treats loss as a state to recover from rather than an error to die on -
      dying would leave the last force latched on the device.

      Effects have to be re-primed after a reacquire: the device may have dropped
      the downloaded effect, so we push the full parameter set again with START
      rather than assuming the handle survived.
    #>
    param($D)
    $acq = Get-Fn $D.Dev ([DI]::DEV_Acquire) ([DI+D_Acquire])
    $hr = $acq.Invoke($D.Dev)
    if ($hr -lt 0) { return $false }
    foreach ($k in @($D.Effects.Keys)) {
        $e = $D.Effects[$k]
        $sp = Get-Fn $e.Ptr ([DI]::EFF_SetParameters) ([DI+D_SetParameters])
        $null = $sp.Invoke($e.Ptr, [ref]$e.Eff, ([DI]::DIEP_TYPESPECIFICPARAMS -bor [DI]::DIEP_START))
    }
    return $true
}

# Periodic (GUID_Sine) effects are NOT usable on this wheel - CreateEffect
# returns REGDB_E_CLASSNOTREG (0x80040154) even though constant force works. So
# texture and buzz are synthesised by MODULATING the constant force instead. That
# is not a workaround so much as the better design here anyway: one primitive,
# one place where magnitude is decided, and the mixer stays additive.
#
# Call this every tick from the mixer with a phase that advances; it just sets a
# constant force, so it composes with the steady forces rather than fighting them.
function Ffb-Texture {
    param($D, [int]$Magnitude, [int]$Phase)
    $sign = if (($Phase % 2) -eq 0) { 1 } else { -1 }
    Ffb-Constant $D ($Magnitude * $sign)
}

function Ffb-Stop {
    param($D)
    foreach ($k in @($D.Effects.Keys)) {
        $e = $D.Effects[$k]
        $stop = Get-Fn $e.Ptr ([DI]::EFF_Stop) ([DI+D_Stop])
        $null = $stop.Invoke($e.Ptr)
    }
}

function Ffb-Close {
    param($D)
    Ffb-Stop $D
    foreach ($k in @($D.Effects.Keys)) {
        $e = $D.Effects[$k]
        $rel = Get-Fn $e.Ptr ([DI]::IUnk_Release) ([DI+D_Release]); $null = $rel.Invoke($e.Ptr)
    }
    $un = Get-Fn $D.Dev ([DI]::DEV_Unacquire) ([DI+D_Unacquire]); $null = $un.Invoke($D.Dev)
    $rel = Get-Fn $D.Dev ([DI]::IUnk_Release) ([DI+D_Release]);    $null = $rel.Invoke($D.Dev)
    $rel = Get-Fn $D.DI ([DI]::IUnk_Release) ([DI+D_Release]);    $null = $rel.Invoke($D.DI)
}
